from apiclient.discovery import build

from flask import Flask, escape, redirect, render_template, request

from flask_login import LoginManager, UserMixin, current_user, login_required

from googleapiclient.errors import HttpError

import httplib2

from oauth2client.client import flow_from_clientsecrets
from oauth2client.service_account import ServiceAccountCredentials

import requests
import time
# import psycopg2

flow = flow_from_clientsecrets('private/oauth_client_secrets.json',
                               scope="profile email",
                               redirect_uri="https://betterinformatics.com/drive/auth_return")

# drive_credentials = ServiceAccountCredentials.from_json_keyfile_name(
#     'private/drive_keyfile.json',
#     scopes=['https://www.googleapis.com/auth/drive'])

undelegated_group_credentials = ServiceAccountCredentials.from_json_keyfile_name(
    'private/drive_keyfile.json',
    scopes=['https://www.googleapis.com/auth/admin.directory.group.member'])

group_credentials = undelegated_group_credentials.create_delegated("qaisjp@betterinformatics.com")

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

        r = requests.get('http://bi:6663/check/' + app.config['DICE_API_NAME'] + '/' +
                         app.config['DICE_API_KEY'],
                         params=payload)
        obj = r.json()

        if obj['status'] == 'success':
            return User('test_token', obj['data'])


@app.route('/drive')
def main():
    if not current_user.is_authenticated:
        return redirect('https://weblogin.inf.ed.ac.uk/cosign-bin/cosign.cgi?'
                        'cosign-betterinformatics.com&https://betterinformatics.com' +
                        request.full_path)

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
        primaries = list(filter(lambda x: x['metadata'].get('primary', False),
                                result['emailAddresses']))

        if len(primaries) != 1:
            return "Expected 1 primary email address. Got " + str(len(primaries))

        email = primaries[0]['value']
        url = ("https://drive.google.com/open?authuser=" + email + "&id=" +
               request.args.get('state', teamDriveID))

        directory = build(
            'admin', 'directory_v1',
            http=group_credentials.authorize(httplib2.Http())
        )

        # Apparently hasMember does not work for non CompSoc org addresses
        # result = directory.members().hasMember(groupKey="users@betterinformatics.com",
        #                                        memberKey=email).execute()

        # If they aren't already a member, make them a member!
        # if not result['isMember']:
        #     .. proceed to insert directory ite

        isMember = False

        # First check if they are a user
        try:
            # We don't need to use the below result. If it does not throw anything
            # then they exist in this list
            directory.members().get(groupKey="users@betterinformatics.com",
                                    memberKey=email).execute()
            isMember = True
        except HttpError as err:
            if err.resp.status == 404:
                pass
            else:
                raise

        # They aren't a  user, so make them a "regular" user (not full-users).
        if not isMember:
            directory.members().insert(groupKey="users@betterinformatics.com", body={
                'status': 'ACTIVE',
                'role': 'MEMBER',
                'type': 'USER',
                'email': email
            }).execute()
            isMember = True

            # Log this registration to disk, so we can store this in a database later
            with open("private/registrations.csv", "a") as f:
                f.write(f"{current_user.get_username()},{email},{time.time()}")

            return render_template('redirect.html', url=url)

        return redirect(url)
    except Exception as e:
        return render_template('error.html', message=escape(str(e)))
