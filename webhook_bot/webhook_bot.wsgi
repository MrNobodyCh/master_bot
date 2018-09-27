#!/usr/bin/env python
import sys

# activate virtualenv
activate_this = '/var/www/env/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

# path to flask app
sys.path.insert(0, '/var/www/env/master_bot/webhook_bot')

from webhook_bot import app as application