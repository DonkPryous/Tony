**Tony**
-----

Acronym of _**The one named yummy**_

[![Python package](https://github.com/DonkPryous/Tony/actions/workflows/python-package.yml/badge.svg)](https://github.com/DonkPryous/Tony/actions/workflows/python-package.yml) [![Pylint](https://github.com/DonkPryous/Tony/actions/workflows/pylint.yml/badge.svg)](https://github.com/DonkPryous/Tony/actions/workflows/pylint.yml) [![CodeQL](https://github.com/DonkPryous/Tony/actions/workflows/codeql.yml/badge.svg)](https://github.com/DonkPryous/Tony/actions/workflows/codeql.yml)

Overview
-----

Tony is a slack integration based on python framework - [tornado](https://www.tornadoweb.org).

It is lightweight yet powerful solution for integrating your workspace and gives plenty of tools to process requests.

The main goal of this implementation was to come up with a web app that gives more flexibility in area of manipulating server's resources (at 

least more than php) without need to bring up additional helpers, external software and more.

List of functions
-----

Currently it's tuned to server Metin2 workspace.
Supported functions:
- Checking git branch of listed paths
- Changing git branch of listed paths
- Listing git branches of listed paths
- Updating git repository of listed paths
- Starting server
- Stopping server
- Restarting server
- Recompiling server
- Rebuilding quests
- Sending request to patcher's server to check branch
- Answering request to check patcher's branch
- Sending request to patcher's server to switch branch
- Answering request to switch patcher's branch
- Rebuilding patcher's list upon request
And more to come..

App serves up to slack security measures and implements request's veritifacation upon this [doc](https://api.slack.com/authentication/best-practices)

Configuration
----
App is ready to run. Everything you need to adjust is contained in environment file.

For those who want to run it behind load balancer, nginx config is included.

More to read over [here](https://www.tornadoweb.org/en/stable/guide/running.html).

Moreover manifest file to build a slack app is attached as well.

Installation and launch
-----
To install and run tony simply clone the repo and install package using pip:

`pip install .`

Then launch it with start script included:

`python start.py`

**Keep in mind that minimal python's runtime version is 3.10**

Dependencies
-----

Dependencies used to build that little guy:
- Tornado Web framework
- Python-DotEnv
- Cryptography
