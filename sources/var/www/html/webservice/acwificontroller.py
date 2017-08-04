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

_STATUS_FILE = '/var/www/html/tmp/status.log'

#==================================================================================================#
#==================================== RCommon SECTION =============================================#
#==================================================================================================#

class RCommon(object):
    @classmethod
    def request(cls, webObject, preflighted, textContent):
        def wrapper(f):
            @wraps(f)
            def inner(self, *args, **kwargs):

                # add header
                webObject.header('Cache-control', 'no-cache')
                webObject.header('Access-Control-Allow-Origin', '*')
                webObject.header("Access-Control-Allow-Headers", "origin, content-type, accept, x-requested-with")
                if textContent:
                    webObject.header('Content-Type', 'text/plain')
                else:
                    webObject.header('Content-Type', 'application/zip')

                if preflighted:
                    webObject.header("Access-Control-Allow-Methods", 'DELETE, OPTIONS, PUT')
                else:
                    webObject.header("Access-Control-Allow-Methods", 'GET, POST')

                return f(self, *args, **kwargs)
            return inner
        return wrapper

    @classmethod
    def store(self, data):

        promise = True

        try:
            with open(_STATUS_FILE, 'w') as outfile:
                json.dump(data, outfile)
                promise = True

        except Exception as e:
            logger.error("Error: %s" %(e))
            logger.error("Can't write file content", exc_info=True)
            promise = False
        finally:
            return promise

    @classmethod
    def readStoredInfo(self):

        promise = {}

        try:
            with open(_STATUS_FILE) as json_data:
                promise = json.load(json_data)

        except Exception as e:
            logger.error("Error: %s" %(e))
            logger.error("Can't read file content", exc_info=True)

        finally:
            return promise

#==================================================================================================#
#================================== Command SECTION ===============================================#
#==================================================================================================#

class IRPulse(object):

    @RCommon.request(web, False, True)
    def POST(self, temperature, fan):

        command = "cool" + temperature + "Cfan" + fan
        state = False

        logger.debug("GET: %s" % (command))
        fullCMD = "irsend SEND_ONCE inventor %s" % (command)
        print fullCMD
        logger.debug("fullCMD: %s" % (fullCMD))

        try:
            process = Popen([fullCMD], stdout=PIPE, shell=True)
            stdout, stderr = process.communicate()

            logger.debug("STDOUT: %s" %(stdout.rstrip('\r\n')))
            if stderr != None:
				logger.error("STDERR: %s" %(stderr))

            state = True
            if not RCommon.store({'temperature':temperature, 'fan':fan, 'state':'on'}):
                state = False

        except Exception as e:
            logger.error("Error: %s" %(e))
            state = False
        finally:
            status = RCommon.readStoredInfo()
            websocketServer.server.send_message_to_all(json.dumps(status))
            logger.info("IRPulse send_message_to_all %s" % (json.dumps(status)))

            return ("sending IR Pulse succeeded <%s>" % command) if state else ("sending IR Pulse failed <%s>" % command)

#==================================================================================================#
#================================== Command SECTION ===============================================#
#==================================================================================================#

class Action(object):

    @RCommon.request(web, False, True)
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

        else:
            fullCMD = "irsend SEND_ONCE inventor %s" % (command)
            logger.debug("fullCMD: %s" % (fullCMD))

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
                logger.error("Can't read file content", exc_info=True)


        newState = RCommon.readStoredInfo()
        websocketServer.server.send_message_to_all(json.dumps(newState))
        logger.info("Action send_message_to_all %s" % (json.dumps(newState)))

        return ("executing action succeeded <%s>" % command) if state else ("executing action failed <%s>" % command)

#==================================================================================================#
#================================== Temperature SECTION ===========================================#
#==================================================================================================#
class Temperature(object):

    @RCommon.request(web, False, True)
    def GET(self):

        temp = "0.0"
        fullCMD = "/usr/local/temperature.py"
        logger.debug("fullCMD: %s" % (fullCMD))

        try:
            process = Popen([fullCMD], stdout=PIPE, shell=True)
            stdout, stderr = process.communicate()
            temp = stdout.rstrip('\r\n')

            logger.debug("STDOUT: %s" %(temp))
            if stderr != None:
                logger.error("STDERR: %s" %(stderr))

        except Exception as e:
            logger.error("Error: %s" %(e))
            logger.error("Can't read file content", exc_info=True)

        return ("%0.2f" % float(temp))

#==================================================================================================#
#================================== Status SECTION ================================================#
#==================================================================================================#
class Status(object):

    @RCommon.request(web, False, True)
    def GET(self):

        status = RCommon.readStoredInfo()

        return json.dumps(status)

#==================================================================================================#
#================================== Login SECTION =================================================#
#==================================================================================================#
class Login(object):

    @RCommon.request(web, False, True)
    def GET(self, passwd):

		return True if passwd == '2709' else False


#==================================================================================================#
#================================== Command SECTION ===============================================#
#==================================================================================================#

class Favicon(object):

    @RCommon.request(web, False, True)
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

# -------------------------------- CopyBuildStatus ---------------------------------
class TemperatureMonitorScheduler(threading.Thread):

    def init(self):

        self.stdout = ""
        self.temp = "0.0"
        self.retuJsonData   = {'returncode' : 0, 'temperature' : 0}

    def run(self):

        fullCMD = "/usr/local/temperature.py"
        logger.debug("fullCMD: %s" % (fullCMD))

        try:
            process = Popen([fullCMD], stdout=PIPE, shell=True)
            stdout, stderr = process.communicate()
            self.stdout = stdout.rstrip('\r\n')

            logger.debug("STDOUT: %s" %(self.stdout))
            if stderr != None:
				logger.error("STDERR: %s" %(stderr))

        except Exception as e:
            logger.error("Error: %s" %(e))
            logger.error("Can't read file content", exc_info=True)

        if self.temp != self.stdout:
            self.temp = self.stdout
            self.retuJsonData['temperature'] = "%0.2f" % float(self.temp)
            websocketServer.server.send_message_to_all(json.dumps(self.retuJsonData))
            logger.info("TemperatureMonitorScheduler send_message_to_all %s" % (self.retuJsonData))

        # detect if main thread is still alive
        for i in threading.enumerate():
            if i.name == "MainThread" and i.is_alive():
                # call scheduler_file_check() again in 5 seconds
                threading.Timer( 5 * 1,  self.run ).start()
                logger.info("Scheduler rescheduled overs: %d s" %(5 * 1))

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

    print "fac schimbarile pe placa si documentez in Git"
    print "Toate rasounsurile sa continu setul full de informatii"
    print "Sa las aerul sa vad daca trece de temperatura setata de mine cu mult sau face el auto singur"
    print "auto ??? e novoie sau stie AC..."
    print "Sa fac pagina de temp history"
    print "se poate docker"
    print "se node.js si angular ?"

    logger.info("##################### WebService started #####################")
    """ urls used by webservice """
    urls    = ( '/acwificontroller/favicon.ico','Favicon',
                '/acwificontroller/action/(.*)','Action',
                '/acwificontroller/login/(.*)','Login',
                '/acwificontroller/temperature','Temperature',
                '/acwificontroller/status','Status',
                '/acwificontroller/(.+)/(.+)',  'IRPulse')

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

