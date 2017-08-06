#!/usr/bin/python

import os
import web
import sys
import time
import json
import logging
import socket
import datetime
import threading
import logging.handlers

from subprocess import Popen, PIPE
from functools import wraps

from websocket_server import WebsocketServer

_HVAC_FILE = '/var/www/html/tmp/hvacrtcu.log'
_LIRC_COMMAND = "irsend SEND_ONCE inventor"
_READ_TEMPERATURE_SCRIPT = '/usr/local/temperature.py'
_HVAC_PAYLOAD_TEMPLATE = {"state": None, "fan": None, "temp": {'target':None, 'now':None}}
#==================================================================================================#
#==================================== RCommon SECTION =============================================#
#==================================================================================================#

class RCommon(object):

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    @classmethod
    def request(cls, webObject, preflighted):
        def wrapper(f):
            @wraps(f)
            def inner(self, *args, **kwargs):

                # add header
                webObject.header('Cache-control', 'no-cache')
                webObject.header('Access-Control-Allow-Origin', '*')
                webObject.header("Access-Control-Allow-Headers", "origin, content-type, accept, x-requested-with")
                webObject.header('Content-Type', 'text/plain')


                if preflighted:
                    webObject.header("Access-Control-Allow-Methods", 'DELETE, OPTIONS, PUT')
                else:
                    webObject.header("Access-Control-Allow-Methods", 'GET, POST')

                return f(self, *args, **kwargs)
            return inner
        return wrapper

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    @classmethod
    def temparatureNow(self):

        temp = None

        target = _READ_TEMPERATURE_SCRIPT

        try:
            process = Popen([target], stdout=PIPE, shell=True)
            stdout, stderr = process.communicate()
            temp = stdout.rstrip('\r\n')

            logger.debug("STDOUT: %s" %(temp))

            if stderr != None:
                logger.error("STDERR: %s" %(stderr))

        except Exception as e:
            logger.error("Error: %s" %(e))
            logger.error("Can't read file content", exc_info=True)

        return ("%0.2f" % float(temp)) if temp is not None else None

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    @classmethod
    def read(self, files):

        promise = _HVAC_PAYLOAD_TEMPLATE

        try:
            with open(_HVAC_FILE) as json_data:
                promise = json.load(json_data)

        except Exception as e:
            logger.error("Error: %s" %(e))
            logger.error("Can't read file content", exc_info=True)

        finally:
            promise['temp']['now'] = RCommon.temparatureNow()

        return promise

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    @classmethod
    def store(self, file, data):

        promise = True

        try:
            with open(file, 'w') as outfile:
                json.dump(data, outfile)

        except Exception as e:
            logger.error("Error: %s" %(e))
            logger.error("Can't write file content", exc_info=True)
            promise = False
        finally:
            return promise

#==================================================================================================#
#======================================== HVACRTCU SECTION ========================================#
#==================================================================================================#

class HVACRTCU(object):

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    @RCommon.request(web, True)
    def OPTIONS(self):
        logger.debug("request from: %s" % (web.ctx.ip))
        return "'preflighted'"

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    @RCommon.request(web, False)
    def GET(self):

        status = _HVAC_PAYLOAD_TEMPLATE
        status = RCommon.read(_HVAC_FILE)

        return json.dumps(status)

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    @RCommon.request(web, True)
    def PUT(self):

        status = True
        lirc_key = None

        data = json.loads(web.data())

        state = data['state']
        temp = data['temp']
        fan = data['fan']

        promise = _HVAC_PAYLOAD_TEMPLATE
        promise['temp']['now'] = RCommon.temparatureNow()
        logger.debug("received parameters: (%s, %s, %s)" % (state, temp, fan))

        promise["state"] = state

        if state == 'off':

            lirc_key = state

        elif state == 'on':

            promise["fan"] = fan
            promise['temp']['target'] = temp

            lirc_key = "cool%sCfan%s" % (temp, fan)

        # common
        lirc_command = "%s %s" % (_LIRC_COMMAND, lirc_key)

        logger.debug("lirc_key: %s" % (lirc_key))
        logger.debug("lirc_command: %s" % (lirc_command))


        try:
            process = Popen([lirc_command], stdout=PIPE, shell=True)
            stdout, stderr = process.communicate()

            logger.debug("STDOUT: %s" %(stdout.rstrip('\r\n')))

            if stderr != None:
                logger.error("STDERR: %s" %(stderr))
                status = False

        except Exception as e:
            status = False
            logger.error("Error: %s" %(e))
            logger.error("Can't read file content", exc_info=True)

        finally:
            if status:
                websocketServer.server.send_message_to_all(json.dumps(promise))
                logger.info("Action send_message_to_all %s" % (json.dumps(promise)))
                RCommon.store(_HVAC_FILE, promise)

            return ("executing action succeeded <%s>" % lirc_key) if state else ("executing action failed <%s>" % lirc_key)

#==================================================================================================#
#================================== Login SECTION =================================================#
#==================================================================================================#
class Login(object):

    @RCommon.request(web, False)
    def GET(self, passwd):

        return True if passwd == '2709' else False


#==================================================================================================#
#================================== Command SECTION ===============================================#
#==================================================================================================#

class Favicon(object):

    @RCommon.request(web, False)
    def GET(self):

        logger.debug("GET: Favicon.ico")
        return None

#==================================================================================================#
#================================== WebsocketServer SECTION =======================================#
#==================================================================================================#

class IoTWebsocketServer(threading.Thread):

    def run(self):
        self.server = WebsocketServer(9001, '0.0.0.0')
        self.server.set_fn_new_client(self.new_client)
        self.server.set_fn_client_left(self.client_left)
        self.server.set_fn_message_received(self.message_received)
        self.server.run_forever()

    def new_client(self, client, server):
        logger.debug("Client(%d) connected" % client['id'])

    def client_left(self, client, server):
        logger.debug("Client(%d) disconnected" % client['id'])

    def message_received(self, client, server, message):
        if len(message) > 200:
            message = message[:200]+'..'
        logger.debug("Client(%d) said: %s" % (client['id'], message))

#==================================================================================================#
#================================== Command SECTION ===============================================#
#==================================================================================================#

class Action(object):

    @RCommon.request(web, False)
    def GET(self, command):

        logger.debug("executing action %s!" % command)

        state = False
        if command == 'auto':
            status = RCommon.readStoredInfo()
            if "fan" in status and "temperature" in status:

                fullCMD = "/usr/local/tempmonitoring.py -t %s -f %s" % (status["temperature"], status["fan"])

                print fullCMD
                try:
                    process = Popen([fullCMD], stdout=PIPE, shell=True)
                    stdout, stderr = process.communicate()

                    logger.debug("STDOUT: %s" %(stdout.rstrip('\r\n')))
                    if stderr != None:
                        logger.error("STDERR: %s" %(stderr))

                    state = True

                    currentState = RCommon.readStoredInfo()

                    if not RCommon.store({'temperature':currentState.get('temperature', 24), 'fan':currentState.get('fan', 0), 'state':'off'}):
                        state = False

                except Exception as e:
                    logger.error("Error: %s" %(e))
                    logger.error("Can't call script", exc_info=True)

        newState = RCommon.readStoredInfo()
        websocketServer.server.send_message_to_all(json.dumps(newState))
        logger.info("Action send_message_to_all %s" % (json.dumps(newState)))

        return ("executing action succeeded <%s>" % command) if state else ("executing action failed <%s>" % command)

# -------------------------------- CopyBuildStatus ---------------------------------
class TemperatureMonitorScheduler(threading.Thread):

    def init(self):

        self.temp = 0.00

    def run(self):

        nowTemp = RCommon.temparatureNow()

        if nowTemp != self.temp:

            self.temp = nowTemp
            promise = RCommon.read(_HVAC_FILE)

            websocketServer.server.send_message_to_all(json.dumps(promise))
            logger.info("TemperatureMonitorScheduler send_message_to_all %s" % (promise))

        # detect if main thread is still alive
        for i in threading.enumerate():
            if i.name == "MainThread" and i.is_alive():
                # call scheduler_file_check() again in 30 seconds
                threading.Timer( 30 * 1,  self.run ).start()
                logger.info("Scheduler rescheduled overs: %d s" %(30 * 1))

#==================================================================================================#
#========================================= MAIN SECTION ===========================================#
#==================================================================================================#

if __name__ == '__main__':

    global web
    global logger
    global websocketServer

    name = os.path.basename(__file__)
    logger  = logging.getLogger(name)

    loggerFile = '/var/www/html/tmp/%s.log' % name
    format  = logging.Formatter("%(asctime)-20s [%(processName)-20s] [%(threadName)-20s] [%(levelname)-5s] [%(funcName)-15s] %(message)s","%Y-%m-%d %H:%M:%S")
    handler = logging.handlers.RotatingFileHandler( loggerFile, maxBytes=(1024**2), backupCount=5)

    handler.setFormatter(format)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    print "Sa las aerul sa vad daca trece de temperatura setata de mine cu mult sau face el auto singur"
    print "auto ??? e novoie sau stie AC..."
    print "Sa fac pagina de temp history"
    print "se poate docker"
    print "se node.js si angular ?"

    logger.info("##################### WebService started #####################")
    """ urls used by webservice """
    urls    = ( '/acwificontroller/favicon.ico','Favicon',
                '/acwificontroller/login/(.*)','Login',
                '/acwificontroller/hvacrtcu',  'HVACRTCU')

    web.config.debug=False
    web.webapi.internalerror = web.debugerror

    app = web.application(urls, globals())
    websocketServer = IoTWebsocketServer()
    temperatureMonitor = TemperatureMonitorScheduler()

    temperatureMonitor.setName('temperatureMonitor')

    try:
        websocketServer.start()
        temperatureMonitor.init()
        temperatureMonitor.start()
        app.run()
    except (SystemExit, KeyboardInterrupt):
        raise
    except socket.error as msg:
        logger.error("Seems that other application is using this port. Please use other port for now ")
        logger.error("Socket error: %s" % (msg))
        logger.error('Failed to start', exc_info=True)
    except:
        logger.error("Unexpected error: %s" % (sys.exc_info()[1]))
        logger.error('Failed to start', exc_info=True)

