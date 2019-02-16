# -*- coding: utf-8 -*-
import os
import time

import requests
import flask
from flask import render_template
from requests import ConnectionError

from common.config import WebhooksSetting

app = flask.Flask(__name__, template_folder='templates')

bot_url = WebhooksSetting.WEBHOOK_URL_BASE


@app.route('/run_bot', methods=['GET', 'HEAD'])
def run_button():
    return render_template('run_button.html')


@app.route('/run_bot', methods=['POST'])
def run_bot():
    try:
        r = requests.get(url=bot_url, verify=False)
        if r.status_code == 200:
            return render_template('works_fine.html')
        else:
            return render_template('error.html')
    except ConnectionError:
        os.system("source ../bin/activate")
        os.system("cd webhook_bot/ && python2.7 webhook_bot.py")
        time.sleep(15)
        try:
            r = requests.get(url=bot_url, verify=False)
            if r.status_code == 200:
                return render_template('success.html')
            else:
                return render_template('error.html')
        except ConnectionError:
            return render_template('error.html')


if __name__ == '__main__':
    app.run(host=WebhooksSetting.SERVER_HOST, debug=True)
