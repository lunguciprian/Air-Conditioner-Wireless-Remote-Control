#!/usr/bin/python

import os
import sys
import time
import getopt
import logging
import logging.handlers
from subprocess import Popen, PIPE

#---------------------------- initialise and configure logger object
def getLogger(name, file):
    """ return logger object """

    retu    = logging.getLogger(name)
    format  = logging.Formatter("%(asctime)-20s %(message)s", "%Y-%m-%d %H:%M:%S")
    handler = logging.handlers.RotatingFileHandler(file, maxBytes=(1024**2)*25, backupCount=1)

    handler.setFormatter(format)
    retu.setLevel(logging.DEBUG)
    retu.addHandler(handler)

    return retu

def envTemp():

    temp = 0
    fullCMD = "/usr/local/temperature.py"

    try:
        process = Popen([fullCMD], stdout=PIPE, shell=True)
        stdout, stderr = process.communicate()
        temp = float(stdout)
    except Exception as e:
        logger.error("Error: %s" %(e))
        logger.error("Can't read env temp", exc_info=True)

    return (temp)

def sendIRPulse(fan, temperature, off=False):

    command = "cool" + str(temperature) + "Cfan" + str(fan) if not off else "off"
    state = False

    logger.debug("lirc send _once: %s" % (command))
    fullCMD = "irsend SEND_ONCE inventor %s" % (command)
    logger.debug("sendIRPulse: %s" % (fullCMD))

    try:
        process = Popen([fullCMD], stdout=PIPE, shell=True)
        stdout, stderr = process.communicate()
        logger.debug("STDOUT: %s" %(stdout))
        state = True
    except Exception as e:
        logger.error("Error: %s" %(e))
        state = False

    finally:
        logger.debug("sending IR Pulse succeeded <%s>" % command) if state else ("sending IR Pulse failed <%s>" % command)
        return state

if __name__ == '__main__':

    fan = 0
    temp = 24
    ON = False

    logfile = '/var/www/html/tmp/tempmonitoring.log'
    logger = getLogger(__file__, logfile)

    try:
        opts, sys.argv[1:] = getopt.getopt(sys.argv[1:], "t:f:")
    except getopt.GetoptError:
        sys.exit(1)

    for opt, arg in opts:

        if opt == '-t':
            temp = float(arg)
        elif opt == '-f':
            fan = int(arg)

    logger.info("############## Temperature monitoring started ###############")
    logger.info("AC Fan %s" %(fan))
    logger.info("AC Temp %s" %(temp))

    ON = sendIRPulse(fan, int(temp))

    t_end = time.time() + 60 * 120

    while time.time() < t_end:

		time.sleep(60 * 5)
		envT = envTemp()
		logger.info("while ON: %s temp: %s envT: %s" % (ON, str(temp), str(envT)))

		if temp > envT:

			if ON:

				logger.info("I will stop AC due to lower temperature temp: %s envT: %s ON: %s" % (str(temp), str(envT), ON))

				if sendIRPulse(fan, int(temp), True):
					ON = False
					logger.info("I succesfully stoped AC")
				else:
					logger.info("I failed to stop AC")

		else:
			
			if not ON:

				ON = sendIRPulse(fan, int(temp))
				logger.info("I will start AC due to higher temperature temp: %s envT: %s ON: %s" % (str(temp), str(envT), ON))

				if ON:
					logger.info("I succesfully started AC")
				else:
					logger.info("I failed to start AC")



	# close the air automation
	logger.info("I will stop AC due to automation period expired temp: %s envT: %s ON: %s" % (str(temp), str(envT), ON))

	if sendIRPulse(fan, int(temp), True):
		ON = False
		logger.info("I succesfully stoped AC")
	else:
		logger.info("I failed to stop AC")
