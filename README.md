# bi-config

This page outlines the architecture of Better Informatics.

## Service: main website

The main website is reliant on several moving parts, listed below:

* [betterinformatics](https://github.com/compsoc-edinburgh/betterinformatics): statically generated Jekyll site with lots of magic templating code
* [cosign-webapi](https://github.com/qaisjp/cosign-webapi): an internal-only web API exposing Informatics' authentication system (CoSign weblogin) over an easy-to-use API. Written in Go.
* [bi-drive-link](https://github.com/compsoc-edinburgh/bi-drive-link): a lightweight webapp to authenticate users against weblogin + Google, subsequently adding users to the Better Informatics Google Group (this gives them access to the team drive)
* [updater](#updater): pulls the local GitHub repo whenever a commit occurs
* [nginx](https://www.nginx.com/): web server and reverse proxy. Serves Jekyll build output, exams.is.ed.ac.uk CORS proxy, mapp, and other stuff. See [config](https://github.com/compsoc-edinburgh/bi-config/tree/master/nginx.conf.d) and [updater](#updater).

### Platforms

* Google Team Drive ([Better Informatics](https://drive.google.com/drive/u/0/folders/0AIKEqWfeWuQQUk9PVA)): this is generously hosted by [CompSoc](https://comp-soc.com) on their G Suite license.
* Google Groups ([Better Informatics](https://groups.google.com/a/betterinformatics.com/forum/#!forum/users)): group members have access to the Team Drive. Also serves as a mailing list.

**Team Drive Caps**

Team Drives have a cap on how many users can be added as members. This cap is much higher if you add _groups_ as members.

We have hit the first cap, requiring us to use Google Groups.

See "Team Drive membership" in [this article](https://support.google.com/a/answer/7338880?hl=en), copied below:

> - Limit for individuals and groups directly added as members: 600
>
>   **Note:** A group and an individual are both counted as one member against the limit
>
> - Total limit of individuals (direct members, or indirect members due to Google Group membership): 50,000
>
>   **Note:** An individual who is a member of several groups that are added as direct members of the Team Drive still only count as a single individual



### updater

This is a Flask webapp triggered by a GitHub webhook. The webapp is exposed as a secret URL on the main website, reverse proxied via nginx.

The [`./docker-build-watch.sh`](https://github.com/compsoc-edinburgh/betterinformatics/blob/master/docker-build-watch.sh) script is used to build updates.

```python
from flask import Flask, redirect, request, g, escape, render_template

import os

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def main():
    os.system("git -C /var/www/betterinformatics pull --ff-only")
    return "Done!"
```


## Service: The Marauder's App

A dockerised flask app, dependent on cosign-webapi.
