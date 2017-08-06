#!/usr/bin/python

import logging
import logging.handlers

logger  = logging.getLogger('wacrc')

loggerFile = '/var/www/html/tmp/acwificontroller.log'
format  = logging.Formatter("%(asctime)-20s [%(processName)-20s] [%(threadName)-20s] [%(levelname)-5s] [%(funcName)-15s] %(message)s","%Y-%m-%d %H:%M:%S")
handler = logging.handlers.RotatingFileHandler( loggerFile, maxBytes=(1024**2), backupCount=5)

handler.setFormatter(format)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
