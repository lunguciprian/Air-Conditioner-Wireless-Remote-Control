#!/usr/bin/python

import os
import sys
import time
import getopt
import logging
import logging.handlers

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


def readTemperature(sensorFile, logger):

    text = None
    temperature = None

    try:
        with open(sensorFile) as tfile:
            text = tfile.read()
            secondline = text.split("\n")[1]
            temperaturedata = secondline.split(" ")[9]
            temperature = float(temperaturedata[2:])
            temperature = temperature / 1000 
    except Exception, e:
        logger.critical("Sensor file %s" %(sensorFile))
    finally:
        logger.info(temperature)
        print temperature

if __name__ == '__main__':

    sensorID = '28-000008cb797c'
    busDir = '/sys/bus/w1/devices'
    w1Slave = 'w1_slave'

    logfile = '/var/log/temperature.log'
    logger = getLogger(__file__, logfile)

    try:
        opts, sys.argv[1:] = getopt.getopt(sys.argv[1:], "s:")
    except getopt.GetoptError:
        sys.exit(1)

    for opt, arg in opts:

        if opt == '-s':
            sensorID = arg

    sensorFile = os.path.join(busDir, sensorID, w1Slave)

    logger.info("############## Temperature monitoring started ###############")
    logger.info("Sensor ID %s" %(sensorID))
    logger.info("Sensor file %s" %(sensorFile))

    readTemperature(sensorFile, logger)