from flask import Flask, redirect, request, g
from oauth2client.client import flow_from_clientsecrets, FlowExchangeError
from oauth2client.service_account import ServiceAccountCredentials
import httplib2
from apiclient.discovery import build
from flask_login import login_required, LoginManager, current_user, UserMixin
import requests
# import psycopg2

flow = flow_from_clientsecrets('private/oauth_client_secrets.json', scope="profile email", redirect_uri="https://betterinformatics.com/drive/auth_return")

drive_credentials = ServiceAccountCredentials.from_json_keyfile_name(
    'private/drive_keyfile.json',
    scopes='https://www.googleapis.com/auth/drive')

teamDriveID = '0AIKEqWfeWuQQUk9PVA'

app = Flask(__name__)
app.config.from_object('config')

login_manager = LoginManager(app)

class User(UserMixin):
    def __init__(self, login_token, attrs):
        self.login_token = login_token
        self.__dict__.update(attrs)

    def get_id(self):
        return self.login_token

    def get_username(self):
        return self.Principal

@login_manager.request_loader
def get_user(request):
    if 'cosign-betterinformatics.com' in request.cookies:
        payload = {
            'cookie': request.cookies.get('cosign-betterinformatics.com', ''),
            'ip': request.remote_addr,
        }

        r = requests.get('http://localhost:6663/check/' + app.config['DICE_API_NAME'] + '/' + app.config['DICE_API_KEY'], params=payload)
        obj = r.json()

        if obj['status'] == 'success':
            return User('test_token', obj['data'])


@app.route('/drive')
def main():
    if not current_user.is_authenticated:
        return redirect('https://weblogin.inf.ed.ac.uk/cosign-bin/cosign.cgi?cosign-betterinformatics.com&https://betterinformatics.com'+request.full_path)

    return redirect(flow.step1_get_authorize_url(state=request.args.get("next", teamDriveID)))

# @app.teardown_appcontext
# def close_db(error):
#     """Closes the database again at the end of the request."""
#     if hasattr(g, 'db'):
#         g.db.close()

# def get_db():
#     """Opens a new database connection if there is none yet for the
#     current application context.
#     """
#     if not hasattr(g, 'db'):
#         g.db = psycopg2.connect(app.config['DATABASE_URI'])
#     return g.db

@app.route('/drive/auth_return')
@login_required
def auth_return():
    # Explicit error message
    error = request.args.get("error", "")
    if error:
        return "Google said: " + error

    code = request.args.get("code", "")
    if not code:
        return "No code provided"

    try:
        credentials = flow.step2_exchange(code)

        http = httplib2.Http()
        http = credentials.authorize(http)

        people = build('people', 'v1', http=http).people()
        result = people.get(resourceName='people/me', personFields='emailAddresses').execute()
        primaries = list(filter(lambda x: x['metadata'].get('primary', False), result['emailAddresses']))

        if len(primaries) != 1:
            return "Expected 1 primary email address. Got " + str(len(primaries))

        email = primaries[0]['value']
        print(result['resourceName'])

        drive = build(
            'drive', 'v3',
            http=drive_credentials.authorize(httplib2.Http())
        )

        result = drive.permissions().create(
            fileId=teamDriveID,
            supportsTeamDrives=True,
            body={
                'emailAddress': email,
                'type': 'user',
                'role': 'writer',
            }
        ).execute()

        return redirect("https://drive.google.com/drive/u/" + email + "/folders/" + request.args.get('state', teamDriveID))
    except Exception as e:
        return "Error: " + str(e)
