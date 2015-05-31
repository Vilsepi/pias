
## Pias

Automated interaction with a website.

> Play it again, Sam!

### Usage

Tested on Ubuntu 14.04. Requires Firefox. You need to obtain a valid `config.py` file.

    sudo pip install -r requirements.txt

Run with Flask's development web server:

    python server.py

Or with a real WSGI server:

    gunicorn server:app
