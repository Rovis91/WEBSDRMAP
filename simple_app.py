#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return 'Server is running'

@app.route('/health')
def health():
    return '{"status": "ok"}'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080) 