#!/usr/bin/python

import os
import sys
import socket
import threading

from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler

#==================================================================================================#
#================================== TemperatureWatchdog SECTION =======================================#
#==================================================================================================#
class TemperatureWatchdog(LoggingEventHandler):

    def __init__(self):
        self.retuJsonData   = {'returncode' : 0,'temp': 0}
        print "TemperatureWatchdog __init__"

    def notify(self, src):
        print "TemperatureWatchdog notify"
        print src

        if os.path.isfile(src) > 0:
			print "os.path.isfile(src) > 0"
            
			temp = None

			try:
				with open('/sys/bus/w1/devices/28-000008cb797c/w1_slave',  'r') as data:
					temp = data.read()
					print temp

			except Exception as e:
				print e

			if temp is not None:
				self.retuJsonData['returncode'] = 0
				self.retuJsonData['temp'] = temp.rstrip('\r\n')
			else:
				self.retuJsonData['returncode'] = 1

        print("send_message_to_all %s" % json.dumps(self.retuJsonData))

    def on_modified(self, event):

        print "TemperatureWatchdog on_modified"
        print event
        # Skip other files excepr progress.xml
        if os.path.basename(event.src_path) != 'w1_slave':
            return

        self.notify(event.src_path)


# -------------------------------- CopyBuildStatus ---------------------------------
class TemperatureMonitor(threading.Thread):

    def init(self):

        self.watchdog   = TemperatureWatchdog()
        self.observer   = Observer()

    def run(self):

        devices = '/sys/bus/w1/devices/28-000008cb797c'
        print devices
        try:

            if os.path.exists(devices):
                print "path exists"
                self.observer.schedule(self.watchdog, devices, recursive=False)
                self.observer.start()

                while os.path.exists('/sys/bus/w1/devices/28-000008cb797c/w1_slave'):
                    # stop execution until scan thread ends
                    pass

                self.observer.stop()
                self.observer.join()
                logger.info("stop watch")
        except Exception, e:
            logger.info("exception opening source folder: %s" % (devices))

if __name__ == '__main__':

    temperatureMonitor = TemperatureMonitor()

    temperatureMonitor.setName('temperatureMonitor')

    try:
        temperatureMonitor.init()
        temperatureMonitor.start()
    except (SystemExit, KeyboardInterrupt):
        raise
    except socket.error as msg:
        print("Seems that other application is using this port. Please use other port for now ")
        print(msg)
    except:
        print("Unexpected error: %s" % (sys.exc_info()[1]))
