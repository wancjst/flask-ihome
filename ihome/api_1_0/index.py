# coding:utf-8

from . import api
from ihome import db, models
import logging
from flask import current_app


@api.route('/index')
def index():
    current_app.logger.error("error msg")
    current_app.logger.warn("warn msg")
    current_app.logger.info("info msg")
    current_app.logger.debug("debugpython  msg")
    return 'index page'