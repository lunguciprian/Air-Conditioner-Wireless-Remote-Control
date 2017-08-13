#!/usr/bin/python

import os
import sys
import time
import json
import requests
import threading
from subprocess import Popen, PIPE

_HVAC_CMDS_FILE = '/var/log/hvacrtcu.cmds'

#==================================================================================================#
#================================== HVACIRWatchdog SECTION ========================================#
#==================================================================================================#
class HVACIRWatchdog(threading.Thread):

    def run(self):
        
        target = 'sudo irw > ' + _HVAC_CMDS_FILE

        try:
            os.remove(_HVAC_CMDS_FILE)
        except Exception as e:
            print e

        try:
            process = Popen([target], stdout=PIPE, shell=True)
            stdout, stderr = process.communicate()
        except Exception as e:
            print e


#==================================================================================================#
#================================== HVACIRParser SECTION ==========================================#
#==================================================================================================#
class HVACIRParser(object):

    def __init__(self):
        
        time.sleep(5)

    def start(self):

        cmds = []

        while True:
            try:
                with open(_HVAC_CMDS_FILE, 'r') as f:

                    lines = f.readlines()
                    lines = [x.strip() for x in lines]

                    if len(lines) > len(cmds):
                        tail = lines[-1]
                        cmd = tail.split(' ')

                        if len(cmd) == 4:
                            while len(cmds) < len(lines):
                                command = cmd[2]
                                payload = {'state':'', 'fan':'0', 'temp':'0', 'lirc_key':command}

                                if command == 'off':
                                    payload['state'] = 'off'
                                else:
                                    payload['state'] = 'on'
                                    payload['fan'] = command[-1:]
                                    payload['temp'] = command[-7:-5]

                                cmds.append(command)
                                headers = {}
                                headers["Content-Type"] = "application/json"
                                response = requests.put('http://localhost:8080/acwificontroller/notify', data=json.dumps(payload), headers=headers)

                                print response

                    time.sleep(5)

            except Exception as e:
                print e

if __name__ == '__main__':

    HVACWatchdogObject = HVACIRWatchdog()

    try:
        HVACWatchdogObject.start()
        HVACIRParser().start()
    except Exception as e:
        print e
