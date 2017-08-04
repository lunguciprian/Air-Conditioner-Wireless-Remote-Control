#!C:\Python27\python.exe

#--------------------------------------------------------------------------------------------------
#
#   File          :     eurekaWebService.py
#   Author        :     Industrialisation Team
#   Date          :     2016-09-21
#   Description   :     Classes that serve to EurekaWebService
#
#--------------------------------------------------------------------------------------------------

#====================== CLASSES SECTION ========================#

import os
import re
import web
import time
import json
import glob
import suds
import shutil
import base64
import sqlite3
import string
import smtplib
import random
import datetime
import threading
import ConfigParser
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler

from subprocess import Popen
from suds.client import Client
from suds.transport.https import HttpAuthenticated

from xml.dom import minidom
from functools import wraps


import utils
import _constants
from websocket_server import WebsocketServer

class SingletonCls(object):

    """ singleton template class """
    __singleton_lock = threading.Lock()
    __singleton_instance = None

    @classmethod
    def instance(cls):
        if not cls.__singleton_instance:
            with cls.__singleton_lock:
                if not cls.__singleton_instance:
                    cls.__singleton_instance = cls()
        return cls.__singleton_instance

class RCommon:
    @classmethod
    def request(cls, webObject, preflighted, textContent):
        def wrapper(f):
            @wraps(f)
            def inner(self, *args, **kwargs):

                utils.debug("{0}.{1}('{2}')".format(self.__class__.__name__, f.__name__, '/'.join(args)))

                # add header
                webObject.header('Cache-control', 'no-cache')
                webObject.header('Access-Control-Allow-Origin', '*')
                webObject.header("Access-Control-Allow-Headers", "origin, content-type, accept, x-requested-with")
                if textContent:
                    webObject.header('Content-Type', 'text/plain')
                else:
                    webObject.header('Content-Type', 'application/zip')
                if( preflighted ):
                    webObject.header("Access-Control-Allow-Methods", 'DELETE, OPTIONS, PUT' )
                else:
                    webObject.header("Access-Control-Allow-Methods", 'GET, POST' )

                return f(self, *args, **kwargs)
            return inner
        return wrapper

class ProcomConfiguration(object):
    """ class used to store config values """

    def __init__( self, username, password, address ):

        self.wsdlUsername = username
        self.wsdlPassword = password
        self.wsdlAddress  = address

class ControlMessage(object):

    def __init__(self, file):
        self.file = file
        self.jsonList = []
        self.jsonBTLDs = {}
        if os.path.isfile(self.file):
            self.setLogistics()

    def getBTLDs(self):
        return self.jsonBTLDs

    def getLogistics(self):
        return self.jsonList

    def getTimestamp(self):
        print time.ctime(os.path.getmtime(self.file))
        return time.ctime(os.path.getmtime(self.file))

    def setLogistics(self):
        with open(self.file, "rb") as f:
            lines = f.readlines()

        section = ""
        section_title = ""
        regex = re.compile("\w{4}-\w{8}-\d{3}\.\d{3}\.\d{3}")

        for line in lines:
            if not line.strip():
                match = regex.search(section)
                if match is not None:
                    logistics["cust_part_no"] = section_title.split()[0]
                    logistics["cust_name"] = ' '.join(section_title.split()[1:])

                    logistics["swe"] = {}
                    infos = [x.strip().strip(' ]').strip() for x in section.split("[")][1:]
                    sis = []

                    for info in infos:
                        process = info[0:4]
                        swe = info[5:13]
                        sgbmid = swe[4:]
                        version = info[14:25]
                        name = info[25:]

                        if process == "BTLD":
                            logistics["BTLD"] = version

                        if process == "HWEL":
                            logistics["SGBD"] = sgbmid
                            logistics["HWEL"] = version

                        logistics["swe"][swe] = { 'version' : version, 'name' : name, 'process' : process }

                    if logistics["BTLD"] not in self.jsonBTLDs:
                        self.jsonBTLDs[logistics["BTLD"]] = []

                    self.jsonBTLDs[logistics["BTLD"]].append(logistics["SGBD"])
                    self.jsonList.append(logistics)

                section = ""
                section_title = ""
            else:
                if section_title == "":
                    logistics = {}
                    section_title = line.strip("\r\n")
                else:
                    section = "%s%s" % (section, line.strip("\r\n"))

class ControlMessageDelete(object):

    def __init__(self, project, swlabel, target, istep):

        # init atrib
        self.project    = project
        self.swlabel    = swlabel
        self.istep      = istep
        self.target     = target

        # generated atrib
        self.retuJsonData     = {
            'general' : 'ControlMessage', \
            'header':{
                        'project': project, \
                        'release': swlabel, \
                        'target': target, \
                        'istep': istep}, \
            'payload':{
                        'returncode' : 0, \
                        'deleted': False, \
                        'message': ""}, \
            }

        self.sessionDir = utils.unixPath(os.path.join(_constants.DATA_CM_PATH, self.project, self.swlabel, self.target, self.istep))
        self.sessionFile= utils.unixPath(os.path.join(self.sessionDir, 'ControlMessage.txt'))

    def do(self):

        if os.path.isfile(self.sessionFile):

            try:
                os.remove(self.sessionFile)
                self.retuJsonData['payload']['deleted'] = True
                self.retuJsonData['payload']['message'] = "Success"

            except Exception, e:

                self.retuJsonData['payload']['returncode'] = 1
                self.retuJsonData['payload']['message'] = "Can't remove file"
        else:
            self.retuJsonData['payload']['returncode'] = 1

class PatchLogistic(object):

    def __init__(self, project, swlabel, target, istep, data):

        # init atrib
        self.webData    = json.loads(data)
        self.project    = project
        self.swlabel    = swlabel
        self.istep      = istep
        self.target     = target
        self.logContent = None

        # generated atrib
        self.retuJsonData     = {
            'general' : 'PatchLogistic', \
            'header':{
                        'project': project, \
                        'release': swlabel, \
                        'target': target, \
                        'istep': istep}, \
            'payload':{
                        'returncode' : 0, \
                        'patched': False, \
                        'message': "", \
                        'filename': "", \
                        'log': ""}, \
            }

        self.sessionLogDir = utils.unixPath(os.path.join(_constants.RELEASES_PATCH_PATH, self.project, self.swlabel, self.target, self.istep))
        self.sessionCMDir = utils.unixPath(os.path.join(_constants.DATA_CM_PATH, self.project, self.swlabel, self.target, self.istep))
        self.sessionCMFile = utils.unixPath(os.path.join(self.sessionCMDir, 'ControlMessage.txt'))
        self.sessionLogFile = utils.unixPath(os.path.join(self.sessionLogDir, 'patchLogistic'+datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d_%H%M%S')+'.log'))
        self.patchtool = utils.unixPath(os.path.join(_constants.TOOLS_DIR, self.project, _constants.PATCH_LOGISTIC))

        if not os.path.exists(self.patchtool):

            self.retuJsonData['payload']['returncode'] = 1
            self.retuJsonData['payload']['message'] = "Missing patch tool"

        elif self.webData == None:

            self.retuJsonData['payload']['returncode'] = 1
            self.retuJsonData['payload']['message'] = "Empty content"

        else:

            if 'dstPath' not in self.webData:

                self.retuJsonData['payload']['returncode'] = 1
                self.retuJsonData['payload']['message'] = self.retuJsonData['payload']['message'] + " Invalid destination folder"

            if 'btld' not in self.webData:

                self.retuJsonData['payload']['returncode'] = 1
                self.retuJsonData['payload']['message'] = self.retuJsonData['payload']['message'] + " Invalid BTLD"

    def do(self):

        if not os.path.exists(self.sessionLogDir):
            os.makedirs(self.sessionLogDir)

        if self.retuJsonData['payload']['returncode'] == 0:

            syscommand = ' '.join(['perl ', self.patchtool, ' -b ', "\"%s\"" % self.webData['btld'], ' -c ', "\"%s\"" % self.sessionCMFile, ' -d ', "\"%s\"" % self.webData['dstPath'], ' > ', "\"%s\"" % self.sessionLogFile])

            utils.debug('patchLogistic: <' + syscommand + '>')

            d = dict(os.environ)
            proc = Popen( syscommand, shell=True, env=d )
            proc.wait()
            self.retuJsonData['payload']['returncode'] = proc.returncode

            self.retuJsonData['payload']['patched'] == True

            try:
                with open(self.sessionLogFile, "r") as f:
                    self.retuJsonData['payload']['log'] = "".join(f.readlines())
                    self.retuJsonData['payload']['filename'] = 'patchLogistic'+datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d_%H%M%S')+'.log'

            except Exception, e:
                self.retuJsonData['payload']['returncode'] = 1
                self.retuJsonData['payload']['message'] = e

class PostGenerate(object):

    def __init__(self, project, swlabel, target, istep, data):


        # init atrib
        self.webData    = json.loads(data['json'])
        self.file       = data['file']
        self.project    = project
        self.swlabel    = swlabel
        self.istep      = istep
        self.target     = target
        self.logContent = None

        # generated atrib
        self.retuJsonData     = {
            'general' : 'PostGenerate', \
            'header':{
                        'project': project, \
                        'release': swlabel, \
                        'target': target, \
                        'istep': istep}, \
            'payload':{
                        'returncode' : 0, \
                        'generated': False, \
                        'message': "", \
                        'filename': "", \
                        'log': ""}, \
            }

        self.sessionLogDir = utils.unixPath(os.path.join(_constants.RELEASES_POST_GENERATE_PATH, self.project, self.swlabel, self.target, self.istep, datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d_%H%M%S')))
        self.sessionEK6File = utils.unixPath(os.path.join(self.sessionLogDir, 'postgenerate.ek6'))
        self.sessionLogFile = utils.unixPath(os.path.join(self.sessionLogDir, 'postgenerate.log'))
        self.postgeneratetool = utils.unixPath(os.path.join(_constants.TOOLS_DIR, self.project, _constants.POST_GENERATE))

        if not os.path.exists(self.postgeneratetool):

            self.retuJsonData['payload']['returncode'] = 1
            self.retuJsonData['payload']['message'] = "Missing postgenerate tool"

        elif self.webData == None:

            self.retuJsonData['payload']['returncode'] = 1
            self.retuJsonData['payload']['message'] = "Empty content"

        else:

            if 'dstPath' not in self.webData:

                self.retuJsonData['payload']['returncode'] = 1
                self.retuJsonData['payload']['message'] = self.retuJsonData['payload']['message'] + " Invalid destination folder"

            if 'file' not in data:

                self.retuJsonData['payload']['returncode'] = 1
                self.retuJsonData['payload']['message'] = self.retuJsonData['payload']['message'] + " Invalid file"

    def do(self):

        if not os.path.exists(self.sessionLogDir):
            os.makedirs(self.sessionLogDir)

        try:
            with open(self.sessionEK6File, "wb") as f:
                f.write(self.file)

        except Exception, e:

            self.retuJsonData['payload']['returncode'] = 1
            self.retuJsonData['payload']['message'] = "Can't write content on file" + self.sessionEK6File

        if self.retuJsonData['payload']['returncode'] == 0:

            syscommand = ' '.join(['perl ', self.postgeneratetool, ' -d ', "\"%s\"" % self.webData['dstPath'], ' -e ', "\"%s\"" % self.sessionEK6File, ' -i ', "\"%s\"" % self.istep, ' -t ', "\"%s\"" % self.target, ' > ', "\"%s\"" % self.sessionLogFile])

            utils.debug('post generate command: <' + syscommand + '>')

            d = dict(os.environ)
            proc = Popen( syscommand, shell=True, env=d )
            proc.wait()
            self.retuJsonData['payload']['returncode'] = proc.returncode

            self.retuJsonData['payload']['generated'] == True

            try:
                with open(self.sessionLogFile, "r") as f:
                    self.retuJsonData['payload']['log'] = "".join(f.readlines())
                    self.retuJsonData['payload']['filename'] = 'postgenerate_'+datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d_%H%M%S')+'.log'

            except Exception, e:
                self.retuJsonData['payload']['returncode'] = 1
                self.retuJsonData['payload']['message'] = e

class GetLogisticData(object):

    def __init__(self, project, swlabel, target, data):

        # init atrib
        self.webData    = json.loads(data)
        self.project    = project
        self.swlabel    = swlabel
        self.target     = target
        self.logContent = None

        # generated atrib
        self.retuJsonData     = {
            'general' : 'GetLogisticData', \
            'header':{
                        'project': project, \
                        'release': swlabel, \
                        'target': target}, \
            'payload':{
                        'returncode' : 0, \
                        'success': False, \
                        'message': "", \
                        'filename': "", \
                        'log': ""}, \
            }

        self.sessionLogDir = utils.unixPath(os.path.join(_constants.RELEASES_LOGISTIC_DATA_PATH, self.swlabel, self.target, \
                    datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d_%H%M%S')))
        self.sessionFile = utils.unixPath(os.path.join(self.sessionLogDir, _constants.LOGISTIC_DATA_FILE))

        if self.webData == None:
            self.retuJsonData['payload']['returncode'] = 1
            self.retuJsonData['payload']['message'] = "Empty content"

    def do(self):

        if not os.path.exists(self.sessionLogDir):
            os.makedirs(self.sessionLogDir)

        if self.retuJsonData['payload']['returncode'] == 0:
            path = self.webData.get('srcRoot')

            pattern = _constants.SVT_PATTERN.replace("###PATH###", path).replace("###TARGET###", self.target)
            files = glob.glob(pattern)

            if len(files) == 0:
                self.retuJsonData['payload']['returncode'] = 1
                self.retuJsonData['payload']['message'] = "No SVT file found for pattern %s" % pattern
            else:
                xmlPath = files[0]
                xmlContent = utils.getXMLFileContent(xmlPath)

                if xmlContent is not None:
                    entries = []
                    for sgmbid in xmlContent.findall('.//ns0:partIdentification', _constants.SVT_NS):
                        processClass = sgmbid.find('ns0:processClass', _constants.SVT_NS).text
                        id = sgmbid.find('ns0:id', _constants.SVT_NS).text.lower()
                        mainVersion  = hex(int(sgmbid.find('ns0:mainVersion', _constants.SVT_NS).text)).upper().replace("0X", "").zfill(2).lower()
                        subVersion   = hex(int(sgmbid.find('ns0:subVersion', _constants.SVT_NS).text)).upper().replace("0X", "").zfill(2).lower()
                        patchVersion = hex(int(sgmbid.find('ns0:patchVersion', _constants.SVT_NS).text)).upper().replace("0X", "").zfill(2).lower()

                        if "SWFK" in processClass:
                            entries.append("SGBMID: 0d%s%s%s%s 1\n" % (id, mainVersion, subVersion, patchVersion))
                        elif "SWFL" in processClass:
                            entries.append("SGBMID: 08%s%s%s%s 1\n" % (id, mainVersion, subVersion, patchVersion))

                    try:
                        with open(self.sessionFile, 'w') as f:
                            for e in sorted(entries):
                                f.write(e)
        
                            f.write("ProgDep: 0\n")
                            f.write("ProgCntr: 0\n")
                            f.write("PartitionSide: 2\n")
        
                        self.retuJsonData['payload']['returncode'] = 0
                        self.retuJsonData['payload']['success'] == True

                        with open(self.sessionFile, "r") as f:
                            self.retuJsonData['payload']['content'] = "".join(f.readlines())
                            self.retuJsonData['payload']['filename'] = os.path.basename(self.sessionFile)

                    except Exception, e:
                        self.retuJsonData['payload']['returncode'] = 1
                        self.retuJsonData['payload']['message'] = e

                else:
                    self.retuJsonData['payload']['returncode'] = 1
                    self.retuJsonData['payload']['message'] = "No XML Content"


class ControlMessagePost(object):

    def __init__(self, project, swlabel, target, istep, data):

        # init atrib
        self.webData    = data
        self.project    = project
        self.swlabel    = swlabel
        self.istep      = istep
        self.target     = target

        # generated atrib
        # init atrib
        self.project    = project
        self.swlabel    = swlabel
        self.istep      = istep
        self.target     = target

        # generated atrib
        self.retuJsonData     = {
            'general' : 'ControlMessage', \
            'header':{
                        'project': project, \
                        'release': swlabel, \
                        'target': target, \
                        'istep': istep}, \
            'payload':{
                        'returncode' : 0, \
                        'post': False, \
                        'message': ""}, \
            }

        self.sessionDir = utils.unixPath(os.path.join(_constants.DATA_CM_PATH, self.project, self.swlabel, self.target, self.istep))
        self.sessionFile= utils.unixPath(os.path.join(self.sessionDir, 'ControlMessage.txt'))

    def do(self):

        if not os.path.exists(self.sessionDir):
            os.makedirs(self.sessionDir)

        if self.webData == None:

            self.retuJsonData['payload']['returncode'] = 1
            self.retuJsonData['payload']['message'] = "Empty file uploaded"

        else:

            try:
                with open(self.sessionFile, "wb") as f:
                    f.write(self.webData)

                self.retuJsonData['payload']['post'] = True
                self.retuJsonData['payload']['message'] = "Success"

            except Exception, e:

                self.retuJsonData['payload']['returncode'] = 1
                self.retuJsonData['payload']['message'] = "Can't write content on file"

class SWCLUploader(object):

    def __init__(self, project, swlabel, target, istep, data):

        # init atrib
        self.webJsonData= json.loads(data)
        self.base64data = self.webJsonData.get('encodedSWCL')
        self.initiator  = self.webJsonData.get('initiator')
        self.project    = project
        self.swlabel    = swlabel
        self.istep      = istep
        self.target     = target

        if self.project == 'MGU':
            self.swlabel = self.swlabel.replace("W",  "w")

        # generated atrib
        self.retuJsonData = {
                            'general' : 'SWCL', \
                            'header':{
                                        'project': str(project), \
                                        'release': str(swlabel), \
                                        'target': str(target), \
                                        'istep': str(istep)}, \
                            'payload':{
                                        'returncode' : 0, \
                                        'uploaded': False, \
                                        'message': "", \
                                        'state': "unknown", \
                                        'procom':""}, \
                            }

        self.returncode = 0
        self.sessionDir = _constants.UPLOADED_LOGS + '/'.join([self.project, self.swlabel, self.target, self.istep, 'SWCLS'])
        self.swclXls    = utils.unixPath(self.getXLSFile())
        self.swclXml    = utils.unixPath('/'.join([self.sessionDir, 'SoftwareChecklist.xml']))
        self.timestamp  = datetime.datetime.fromtimestamp(time.time()).strftime('%Y.%m.%d %H:%M:%S')
        self.description= datetime.datetime.fromtimestamp(time.time()).strftime('%d.%m.%Y %H:%M:%S') + ' ' + str('%04d' % random.randrange(1000))

    def loadHelperObjects(self, websocketServer, scheduler):
        self.ws         = websocketServer
        self.cron       = scheduler

    def do(self):

        self.retuJsonData['payload']['uploaded'] = True
        self.retuJsonData['payload']['message'] = 'Triggering upload ...'
        self.retuJsonData['payload']['state'] = 'pending'

        if not os.path.exists(self.sessionDir):
            os.makedirs(self.sessionDir)

        with open(self.swclXml, "w") as f:
            f.write(base64.b64decode(self.base64data))

        # convert xml to xsl
        self.convertXML2XSL()
        if(self.returncode):
            self.retuJsonData['payload']['returncode'] = self.returncode
            self.retuJsonData['payload']['uploaded'] = True
            self.retuJsonData['payload']['message'] = 'Upload failed on ' + utils.get_dt()
            self.retuJsonData['payload']['state'] = 'failure'

            self.wsSend()
            return

        time.sleep(3)

        # upload xls
        self.uploadXLS()
        if(self.returncode):
            self.retuJsonData['payload']['returncode'] = self.returncode
            self.retuJsonData['payload']['uploaded'] = True
            self.retuJsonData['payload']['message'] = 'Upload failed on ' + utils.get_dt()
            self.retuJsonData['payload']['state'] = 'failure'

            self.wsSend()
            return

        ResourcesManager.instance().addPendingSWCL(self.swclXls, self.project, self.swlabel, self.istep, self.target, self.timestamp, self.description, self.initiator)

        self.retuJsonData['payload']['returncode'] = self.returncode
        self.retuJsonData['payload']['uploaded'] = True
        self.retuJsonData['payload']['message'] = 'Pending since ' + utils.get_dt()
        self.retuJsonData['payload']['state'] = 'pending'

        self.wsSend()

        if not self.cron.is_alive():
            threading.Timer(15,  self.cron.run).start()
            utils.info("Scheduler rescheduled overs: %d s" % 15)

    def wsSend(self):

        utils.warning("send_message_to_all %s" % json.dumps(self.retuJsonData))
        self.ws.server.send_message_to_all(json.dumps(self.retuJsonData))

    def is_exe(self, fpath):
        if ( os.path.isfile(fpath) and os.access(fpath, os.X_OK) ):
            pass
        else:
            utils.error("Procom file: %s is not exe" % fpath )
            self.returncode = 1

    def file_exists( self, fpath ):
        if ( os.path.isfile(fpath) ):
            pass
        else:
            utils.error("Procom file: %s not exist" % fpath )
            self.returncode = 1

    def getXLSFile(self):
        xlsFile = self.sessionDir + _constants.OUT_XSL
        xlsFile = string.replace(xlsFile, "###PROJECT###",  self.project )
        xlsFile = string.replace(xlsFile, "###SWLABEL###",  self.swlabel )
        xlsFile = string.replace(xlsFile, "###ISTEP###",    self.istep   )
        return ( xlsFile + '_' + self.target +'.xls' )

    def convertXML2XSL( self ):

        xlsmap     = _constants.XSL_MAP_XML
        xlsmap     = string.replace(xlsmap, "###PROJECT###",  self.project )
        swclxsl    = _constants.SWCL_XSL
        swclxsl    = string.replace(swclxsl, "###PROJECT###",  self.project )

        syscommand = ' '.join(['java', '-jar', "\"%s\"" % _constants.JAVA_JAR_TOOL, '-s', "\"%s\"" % self.swclXml, '-m', "\"%s\"" % xlsmap, '-t', "\"%s\"" % swclxsl, '-d', "\"%s\"" % self.swclXls])

        # test if needed files exists
        self.is_exe     (_constants.JAVA_JAR_TOOL)
        self.file_exists(_constants.JAVA_JAR_TOOL)
        self.file_exists(swclxsl)
        self.file_exists(xlsmap)

        utils.debug('xml2xls: <' + syscommand + '>')

        d = dict(os.environ)
        proc = Popen( syscommand, shell=True, env=d )
        proc.wait()
        self.returncode = proc.returncode

    def uploadXLS( self ):
        source     = self.swclXls
        # source     = string.replace(source, _constants.WEBSERVICE_ABS_PATH,  _constants.PROCOM_REL_PATH)
        syscommand = 'perl \"' + utils.unixPath(os.path.join(_constants.UPLOADER_DIR, _constants.UPLOADER_FILE)) + "\" " + _constants.UPLOADER_CMD
        syscommand = string.replace(syscommand, "###PROJECT###",  self.project)
        syscommand = string.replace(syscommand, "###FILE###",     source)
        syscommand = string.replace(syscommand, "###ECU###",      self.target)
        syscommand = string.replace(syscommand, "###ID###",       self.description)

        utils.debug( 'upload: <' + syscommand + '>' )
        d = dict(os.environ)
        proc = Popen( syscommand, shell=True, env=d )
        proc.wait()

        self.returncode = proc.returncode

#====================== CLASS SQLiteConnection ========================#

class SQLiteConnection(object):

    #---------------------------- Project constructor
    def __init__(self, database=_constants.UPLOADED_SWCLS_DB):

        self.database   = database
        self.connection = None

        if not os.path.isfile(self.database):
            self.connect()
            self.initializeDatabase()
            self.checkDatabaseConsistency()
        else:
            self.connect()

    def connect(self):
        self.connection = self.openDBConnection(self.database)

    def disconnect(self):
        self.closeDBConnection(self.connection)

    def checkDatabaseConsistency(self):

        cursor  = self.connection.cursor()
        cursor.execute('PRAGMA integrity_check')
        data    = cursor.fetchall()

        if str(data[0][0]) == 'ok':
            utils.info("Database consistency check result: %s" % data[0])
        else:
            utils.error("Database consistency check result: |%s|" % data[0])
            sys.exit()

    def initializeDatabase(self):

        self.connection.execute(_constants.TABLE_UPLOADED_SWCLS_STRUCTURE)
        utils.info("Table: INTEGRATION_RELEASES created successfully")

    def insert(self, query):

        try:
            utils.debug("SQLiteConnection insert: %s" % query)
            self.connection.execute(query)
            self.connection.commit()
        except Exception, e:
            utils.error("Exception insert !!! %s %s" % (e, query))

    def select(self, query):

        retu = []
        try:
            utils.debug("SQLiteConnection select: %s" % query)
            cursor = self.connection.cursor()
            cursor.execute(query)
            data  = cursor.fetchall()
            if data is not None:
                retu = data
        except Exception, e:
            utils.error("Exception select !!! %s %s" % (e, query))
        finally:
            return retu

    def update(self, query):

        try:
            utils.debug("SQLiteConnection update: %s" % query)
            cursor = self.connection.cursor()
            cursor.execute(query)
            self.connection.commit()
        except Exception, e:
            utils.error("Exception select !!! %s %s" % (e, query))

    def delete(self, query):
        try:
            utils.debug("SQLiteConnection delete: %s" % query)
            self.connection.execute(query)
            self.connection.commit()
            self.connection.execute("VACUUM")
        except Exception, e:
            utils.error("Exception delete !!! %s %s" % (e, query))

    def rowsCount(self, query):
        retu = 0
        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            data  = cursor.fetchall()
            if data is not None:
                retu = len(data)
        except Exception, e:
            utils.error("Exception rows count id!!! %s %s" % (e, query))
        finally:
            return retu

    def getNumberOfBuilds(self, project):
        return self.rowsCount("SELECT ROWID FROM INTEGRATION_RELEASES WHERE PROJECT='%s'" % (project.upper()))

    def openDBConnection(self, database):
        conn = None
        try:
            conn = sqlite3.connect(database)
        except Exception, e:
            utils.error("Exception could not open database connection!!! database:%s error:%s" % (database, e))
            sys.exit()
        finally:
            return conn

    def closeDBConnection(self, connection):
        if connection:
            connection.close()

class ResourcesManager(SingletonCls):
    """ This class will manage all resource access.
    Is thread safe, using mutex from decorators method @synchronized(mutex) """

    mutex       = threading.Lock()

    def getCopyReleaseHistory(self):

        retuJsonData     = {
            'general' : 'History', \
            'header':{
                        'project': 'all', \
                        'release': 'all', \
                        'target': 'all'}, \
            'payload':{
                        'returncode' : 0, \
                        'content': []}, \
            }

        logPattern  = _constants.RELEASES_LOGS_PATH + '/*/progress.xml'

        content = {}
        for file in sorted(glob.iglob(os.path.join(_constants.RELEASES_LOGS_PATH, "*", "*", "*", "*", "progress.xml"))): #"*" is for subdirectory
            progress = utils.xml2json(file)
            path = utils.unixPath(file).split('/')
            if len(path) == 11:
                foldername = path[len(path) - 2]
                folderpath = '/'.join(path[4:-1])
                progress['folder'] = folderpath
                content[foldername] = progress

        for key in reversed(sorted(content)):
            if content[key] is not None:
                retuJsonData['payload']['content'].append(content[key])

        return json.dumps(retuJsonData)

    @utils.synchronized(mutex)         # make operation thread safe
    def getReleaseClientStatus(self):

        response = {'returncode' : 0}
        response['status'] = {}
        sqlConnection   = SQLiteConnection(_constants.RELEASES_DB)

        response['status']["nbt_total"] = sqlConnection.getNumberOfBuilds("NBT")
        response['status']["evo_total"] = sqlConnection.getNumberOfBuilds("EVO")
        response['status']["ram_total"] = sqlConnection.getNumberOfBuilds("RAM")
        response['status']["mgu_total"] = sqlConnection.getNumberOfBuilds("MGU")

        response['status']["last_updated"] = "N/A"
        response['status']["last_duration"] = "N/A"
        response['status']["uploader_status"] = "available"
        response['status']["rel_status"] = "available"
        sqlConnection.disconnect()

        return json.dumps(response)

    def getCopyReleaseStatus(self, project, release, target):

        retuJsonData     = {
            'general' : 'Delivery', \
            'header':{
                        'project': project, \
                        'release': release, \
                        'target': target}, \
            'payload':{
                        'returncode' : 0, \
                        'delivered': False, \
                        'progress': None, \
                        'availableSince': None}, \
            }

        logRoot     = os.path.join(_constants.RELEASES_LOGS_PATH, project.upper(), release.upper(), target.upper())
        logPattern  = '\d{8}_\d{6}' + ".*"

        if os.path.exists(logRoot):
            logDirs     = [f for f in os.listdir(logRoot) if re.match(logPattern, f)]
            logDirs.sort(reverse=True)

            if len(logDirs) > 0:
                retuJsonData['payload']['delivered'] = True
                progress = utils.xml2json(os.path.join(logRoot, logDirs[0], 'progress.xml'))
                if progress is not None:
                    retuJsonData['payload']['progress'] = progress
                    path = utils.unixPath(os.path.join(logRoot, logDirs[0])).split('/')
                    print path, len(path)
                    if len(path) == 10:
                        folderpath = '/'.join(path[4:])
                        retuJsonData['payload']['progress']['folder'] = folderpath
                else:
                    retuJsonData['payload']['returncode'] = 1

        # get SWDAT info
        sqlConnection   = SQLiteConnection(_constants.RELEASES_DB)
        releaseRowID    = sqlConnection.select("SELECT ROWID FROM PRODUCTION_RELEASES WHERE PROJECT='%s' AND BUILD_NAME='%s'" % (project.upper(), release.upper()))
        sqlConnection.disconnect()

        if len(releaseRowID):

            sqlConnection   = SQLiteConnection(_constants.RELEASES_DB)
            sqlResponse     = sqlConnection.select("SELECT BUILD_DATE FROM PRODUCTION_BUILD_DATES WHERE RELEASE_ID ='%s' AND TARGET_NAME='%s'" % (releaseRowID[0][0], target.upper()))
            sqlConnection.disconnect()

            if len(sqlResponse):

                availableSince  = str(sqlResponse[0][0])
                retuJsonData['payload']['delivered'] = True
                retuJsonData['payload']['availableSince'] = availableSince

        return json.dumps(retuJsonData)

    @utils.synchronized(mutex)         # make operation thread safe
    def updateStatus( self, status, filename, description, docUrl=None ):
        """ change the status of files from DB """

        sqlConnection   = SQLiteConnection()
        retu            = sqlConnection.update("UPDATE UPLOADED_SWCLS SET STATUS='%s', URL='%s' WHERE DESCRIPTION='%s' AND FILENAME='%s'" %(status, docUrl, description, filename))
        sqlConnection.disconnect()

    @utils.synchronized(mutex)         # make operation thread safe
    def getPendingSWCLs(self):
        """ return list of pending file types from uploaded """

        sqlConnection   = SQLiteConnection()
        retu            = sqlConnection.select("SELECT DESCRIPTION, FILENAME, INITIATOR, BUILD, ISTEP FROM UPLOADED_SWCLS WHERE STATUS='pending'")
        sqlConnection.disconnect()

        return retu

    @utils.synchronized(mutex)         # make operation thread safe
    def addPendingSWCL( self, filename, project, swlabel, istep, target, timestamp, description, initiator ):
        """ add a new swcl to DB with pending status """

        filename = re.sub('^.*/',"", filename) # remove path to filename
        sqlConnection  = SQLiteConnection()
        sqlConnection.insert("INSERT INTO UPLOADED_SWCLS (PROJECT, BUILD, ISTEP, TARGET, FILENAME, STATUS, TIMESTAMP, DESCRIPTION, INITIATOR) VALUES ('%s', '%s', '%s', '%s', '%s', 'pending', '%s', '%s', '%s')" % (project, swlabel, istep, target, filename, timestamp, description, initiator))
        sqlConnection.disconnect()

    def getControlMessage( self, project, swlabel, target, istep ):
        """ return status of specific swcl from DB """

        retuJsonData     = {
                    'general' : 'ControlMessage', \
                    'header':{
                                'project': project, \
                                'release': swlabel, \
                                'target': target, \
                                'istep': istep}, \
                    'payload':{
                                'returncode' : 0, \
                                'uploaded': False, \
                                'content': "", \
                                'availableSince': "unknown"}, \
                    }

        sessionDir = utils.unixPath(os.path.join(_constants.DATA_CM_PATH, project, swlabel, target, istep))
        sessionFile= utils.unixPath(os.path.join(sessionDir, 'ControlMessage.txt'))

        if os.path.isfile(sessionFile):
            controlMessage = ControlMessage(sessionFile)
            retuJsonData['payload']['uploaded'] = True
            retuJsonData['payload']['BTLDs'] = controlMessage.getBTLDs()
            retuJsonData['payload']['content'] = controlMessage.getLogistics()
            retuJsonData['payload']['availableSince'] = controlMessage.getTimestamp()

        utils.debug("return %s " % json.dumps( retuJsonData ) )
        return json.dumps(retuJsonData)

    def getUploadedSWCLStatus( self, project, swlabel, target, istep ):
        """ return status of specific swcl from DB """

        if project == 'MGU':
            swlabel = swlabel.replace('W', 'w')

        retuJsonData     = {
                    'general' : 'SWCL', \
                    'header':{
                                'project': project, \
                                'release': swlabel, \
                                'target': target, \
                                'istep': istep}, \
                    'payload':{
                                'returncode' : 0, \
                                'uploaded': False, \
                                'message': "", \
                                'state': "unknown", \
                                'procom':""}, \
                    }

        sqlConnection   = SQLiteConnection()
        response        = sqlConnection.select("SELECT STATUS, DESCRIPTION, URL FROM UPLOADED_SWCLS WHERE PROJECT='%s' AND BUILD='%s' AND ISTEP='%s' AND TARGET='%s' order by TIMESTAMP DESC limit 1" % (project, swlabel, istep, target))
        sqlConnection.disconnect()

        if len(response):

            swclDetails = response[0]
            status      = str(swclDetails[0])
            description = str(swclDetails[1])
            url         = str(swclDetails[2])

            retuJsonData['payload']['uploaded'] = True
            retuJsonData['payload']['state'] = status

            if  status == 'pending':
                retuJsonData['payload']['message'] = 'Pending since ' + description.split(' ')[0]
            elif status == 'uploaded':
                retuJsonData['payload']['message'] = 'Uploaded successfully on ' + description.split(' ')[0]
                retuJsonData['payload']['procom'] = url
            elif status == 'failure':
                retuJsonData['payload']['message'] = 'Upload failed on ' + description.split(' ')[0]

        utils.debug("return %s " % json.dumps( retuJsonData ) )
        return json.dumps(retuJsonData)

    @utils.synchronized(mutex)         # make operation thread safe
    def getProcomConfiguration(self):
        """ return config.ini file content """

        config = ConfigParser.ConfigParser()

        try:
            config.read(_constants.CONFIG_INI_FILE)
        except:
            utils.warning("resource file : %s not exists" % _constants.CONFIG_INI_FILE )
            return None

        # WSDL
        wsdlUsername = config.get("EurekaCredentials","username")
        wsdlPassword = config.get("EurekaCredentials","password")
        wsdlAddress  = config.get("ProcomWSDL","wsdl")

        return ProcomConfiguration(wsdlUsername, wsdlPassword, wsdlAddress)

class Scheduler(threading.Thread):
    """ execute a Scheduler Procom check for uploaded file
    This class use his own thread """

    def loadWebsocketServer(self, ws):
        self.ws = ws

    def sendMail(self, success, filename, initiator, build, istep):
        config = ConfigParser.ConfigParser()

        try:
            config.read(_constants.CONFIG_INI_FILE)
        except:
            utils.warning("resource file : %s not exists" % _constants.CONFIG_INI_FILE )
            return

        smtpServer = config.get("SMTP","server")
        sender = _constants.EUREKA_EMAIL
        recipients = _constants.EUREKA_EMAIL
        if initiator is not None and initiator != "":
            for name in config.items("EMAILS"):
                if initiator.lower() in name[0].lower():
                    recipients = "%s,%s" % (_constants.EUREKA_EMAIL, name[1])
                    break

        if success:
            subject = "Upload succesful"
            html = _constants.MAIL_UPLOAD_OK
            utils.info("Send mail for upload successful to: %s" % recipients)
        else:
            subject = "Upload failure"
            html = _constants.MAIL_UPLOAD_NOK
            utils.info("Send mail for upload failure to: %s" % recipients)

        html = html.replace("###FILENAME###", filename)
        html = html.replace("###BUILD###", build)
        html = html.replace("###ISTEP###", istep)
        utils.send_mail(subject, sender, recipients, html, smtpServer)

    def sendNotification(self, filename, description):

        sqlConnection   = SQLiteConnection()
        response        = sqlConnection.select("SELECT PROJECT, BUILD, TARGET, ISTEP FROM UPLOADED_SWCLS WHERE DESCRIPTION='%s' AND FILENAME='%s'" %(description, filename))
        sqlConnection.disconnect()

        if len(response):

            swclDetails = response[0]
            project     = str(swclDetails[0])
            swlabel     = str(swclDetails[1])
            target      = str(swclDetails[2])
            istep       = str(swclDetails[3])

            retuJsonData = ResourcesManager.instance().getUploadedSWCLStatus(project.upper(), swlabel.upper(), target.upper(), istep.upper())
            self.ws.server.send_message_to_all(retuJsonData)

    def run(self):

        pendingSWCLCount = 0
        utils.info("Scheduler started")
        for row in ResourcesManager.instance().getPendingSWCLs():

            description = row[0]
            filename    = row[1]
            initiator   = row[2]
            build       = row[3]
            istep       = row[4]

            # each pending file will be verified if is uploaded successfully or not
            utils.debug("pending file filename: %s description: %s" % (filename, description))
            uploadedFileProcomUrl = ProcomConnector.instance().verifyIfSWCLIsUploaded(filename, description)
            utils.info("uploadedFileProcomUrl: %s" % (uploadedFileProcomUrl))

            if uploadedFileProcomUrl is not None:

                # if file is uploaded OK change file status from pending to uploaded in xml files """
                ResourcesManager.instance().updateStatus('uploaded', filename, description, uploadedFileProcomUrl)
                self.sendNotification(filename, description)
                self.sendMail(True, filename, initiator, build, istep)
                utils.debug("pending filename: %s description: %s status changed from: pending to: uploaded" %(filename, description))

            else:
                # if file is not uploaded OK and upload time stamp is higher that 60 min change file status from pending to failure in xml files """
                timestamp = description.split(' ')
                swclDate  = timestamp[0].split('.')
                swclTime  = timestamp[1].split(':')
                fileDT    = datetime.datetime(int(swclDate[2]), int(swclDate[1]), int(swclDate[0]), int(swclTime[0]), int(swclTime[1]), int(swclTime[2]))
                now       = datetime.datetime.fromtimestamp( time.time() ).strftime('%Y,%m,%d,%H,%M,%S').split(',')
                nowDT     = datetime.datetime(int(now[0]), int(now[1]), int(now[2]), int(now[3]), int(now[4]), int(now[5]))

                if ( ( nowDT - fileDT ).total_seconds() > 3600 ):
                    ResourcesManager.instance().updateStatus( 'failure', filename, description)
                    utils.info("pending file filename: %s description: %s status changed from: pending to: failure" % (filename, description))
                    self.sendNotification(filename, description)
                    self.sendMail(False, filename, initiator, build, istep)
                else:
                    utils.info("pending filename: %s description: %s status not changed" % (filename, description))
                    pendingSWCLCount = pendingSWCLCount + 1


        utils.info("Scheduler ended")

        # detect if main thread is still alive
        for i in threading.enumerate():
            if i.name == "MainThread" and i.is_alive() and pendingSWCLCount > 0:
                # call scheduler_file_check() again in 15 * 60 seconds
                threading.Timer( 15 * 60,  self.run ).start()
                utils.info("Scheduler rescheduled overs: %d s" %(15 * 60))

class ProcomConnector(SingletonCls):
    """ class used to verify Procom status of specific upload swcl file """
    def __init__(self):

        self.config = ResourcesManager.instance().getProcomConfiguration()
        basicAuthentication = HttpAuthenticated(username=self.config.wsdlUsername, password=self.config.wsdlPassword)

        # Initiate soapclient
        self.authClient     = Client(url=self.config.wsdlAddress,transport=basicAuthentication)

    def verifyIfSWCLIsUploaded(self, filename, description):
        try:
            result = self.authClient.service.Query( 'wt.doc.WTDocument', "title='" + filename + "'&description='" + description + "'" )
            utils.debug("result: %s for filename: %s description: %s" % (result, filename, description))
            if hasattr( result, 'item' ):
                docUrl = 'https://procom.harman.com/EngineeringPortal/app/#ptc1/tcomp/infoPage?oid='+':'.join(result.item[0].ufid.split(':')[:3])
                return docUrl
            else:
                return None
        except suds.WebFault, e:
            utils.warning("suds.WebFaults caught: " % e)
            return None

# -------------------------------- ScanProductionBuild ---------------------------------
class ScanProductionBuild(threading.Thread):

    def init(self, project, release, target, webData, websocketServer):

        self.ws         = websocketServer
        self.project    = project.upper()
        self.release    = release.upper()
        self.target     = target.upper()
        self.returncode = 0
        self.webJsonData    = json.loads(webData)

        self.retuJsonData   = {
            'general' : 'Production', \
            'header':{
                        'project': project, \
                        'release': release, \
                        'target': target}, \
            'payload':{
                        'returncode' : 0}, \
            }

        utils.warning("Scan Production Build %s" % self.webJsonData)

    def run(self):

        # long running process
        environ = dict(os.environ)
        command = 'python ' + _constants.RELEASES_SCAN_PATH + ' -p \"' + self.project + '\" -t \"' + self.target + '\" -f \"' + self.webJsonData.get('swPath') + '\"'

        utils.info("command %s" % command)

        process = Popen(command, shell=True, env=environ)
        process.wait()

        self.retuJsonData['payload']['returncode'] = process.returncode

        utils.warning("send_message_to_all %s" % json.dumps(self.retuJsonData))
        self.ws.server.send_message_to_all(json.dumps(self.retuJsonData))

# -------------------------------- CopyBuild ---------------------------------
class CopyBuild(threading.Thread):

    def init(self, project, release, target, webData, websocketServer):

        self.ws         = websocketServer
        self.project    = project.upper()
        self.release    = release.upper()
        self.target     = target.upper()
        self.returncode = 0
        self.webJsonData    = json.loads(webData)

        if self.project == 'MGU':
            self.release = self.release.replace("W",  "w")

        self.retuJsonData   = {
            'general' : 'Delivery', \
            'header':{
                        'project': project, \
                        'release': release, \
                        'target': target}, \
            'payload':{
                        'returncode' : 0, \
                        'delivered': False, \
                        'progress': None, \
                        'availableSince': None}, \
            }

        utils.warning("CopyBuild %s" % self.webJsonData)

    def run(self):

        # long running process
        environ = dict(os.environ)
        sourceFile = self.webJsonData.get('srcFile') if self.webJsonData.get('srcFile') else self.webJsonData.get('srcRoot')
        command = 'python ' + _constants.RELEASES_COPY_SCRIPT + ' -p \"' + self.project + '\" -t \"' + self.target  + '\" -l \"' + self.release \
                            + '\" -s \"' + sourceFile + '\" -d \"' + self.webJsonData.get('dstPath') + '\"'  + ' -a \"' + self.webJsonData.get('action') \
                            + '\" -i \"' + self.webJsonData.get('initiator' ) + '\" -r \"' + self.webJsonData.get('srcRoot') + '\"'

        utils.info("command %s" % command)

        t0 = time.time()
        process = Popen(command, shell=True, env=environ)
        process.wait()
        t1 = time.time()

        # check for instanr error
        # in cases that progress.xml was not created
        if t1 - t0 < 2:
            utils.info("instant failure for: %s" % command)
            utils.info("exit code: %s" % process.returncode)

            self.retuJsonData['payload']['returncode'] = process.returncode

            utils.debug("send_message_to_all %s" % json.dumps(self.retuJsonData))
            self.ws.server.send_message_to_all(json.dumps(self.retuJsonData))

class ProgressWatchdog(LoggingEventHandler):

    def __init__(self, websocketServer, retuJsonData):
        self.websocketServer = websocketServer
        self.retuJsonData    = retuJsonData

    def notify(self, src):
        if os.path.isfile(src) > 0:
            progress = utils.xml2json(src)
            if progress is not None:
                self.retuJsonData['payload']['returncode'] = 0
                self.retuJsonData['payload']['progress'] = progress
                self.retuJsonData['payload']['delivered'] = True
            else:
                self.retuJsonData['payload']['returncode'] = 1

        # utils.debug("send_message_to_all %s" % json.dumps(self.retuJsonData))
        self.websocketServer.server.send_message_to_all(json.dumps(self.retuJsonData))

    def on_modified(self, event):

        # Skip other files excepr progress.xml
        if os.path.basename(event.src_path) != _constants.PROGRESS_XML:
            return

        self.notify(event.src_path)

# -------------------------------- CopyBuildStatus ---------------------------------
class CopyBuildStatus(threading.Thread):

    def init(self, scanThread, project, release, target, websocketServer):

        retuJsonData   = {
            'general' : 'Delivery', \
            'header':{
                        'project': project, \
                        'release': release, \
                        'target': target}, \
            'payload':{
                        'returncode' : 0, \
                        'delivered': False, \
                        'progress': None, \
                        'availableSince': None}, \
            }

        self.watchdog   = ProgressWatchdog(websocketServer, retuJsonData)
        self.observer   = Observer()
        self.scanThread = scanThread
        self.ws         = websocketServer
        self.project    = project.upper()
        self.release    = release.upper()
        self.target     = target.upper()
        self.logRoot    = os.path.join(_constants.RELEASES_LOGS_PATH, self.project.upper(), self.release.upper(), self.target.upper())

    def run(self):

        # let time to copy script to initiate copy process
        time.sleep(2)

        logPattern  = '\d{8}_\d{6}' + ".*"

        try:
            logDirs     = [f for f in os.listdir(self.logRoot) if re.match(logPattern, f)]

            if len(logDirs) > 0:
                logDirs.sort(reverse=True)
                self.observer.schedule(self.watchdog, os.path.join(self.logRoot, logDirs[0]), recursive=False)
                self.observer.start()

                while self.scanThread.isAlive():
                    # stop execution until scan thread ends
                    pass

                self.observer.stop()
                self.observer.join()
                utils.info("stop watch")
        except Exception, e:
            utils.info("exception opening source folder: %s %s" % (self.logRoot, e))

# -------------------------------- ScanScrs ---------------------------------
class Scrs(object):

    def __init__(self, websocketServer):

        self.retuJsonData   = {
            'general' : 'Scrs', \
            'header'  :{}, \
            'payload' :{
                        'returncode' : 0, \
                        'update': False,}, \
            }



        self.ws         = websocketServer
        self.returncode = 0

        utils.warning("Starting SCRs scan process")

    def run(self):

        # long running process
        environ = dict(os.environ)
        command = 'perl ' + _constants.SCRS_SCAN_PATH

        utils.info("command %s" % command)

        process = Popen(command, shell=True, env=environ)
        process.wait()

        self.retuJsonData['payload']['returncode'] = process.returncode

        utils.warning("send_message_to_all %s" % json.dumps(self.retuJsonData))
        self.ws.server.send_message_to_all(json.dumps(self.retuJsonData))


# -------------------------------- ScanIntegrationBuild ---------------------------------
class ScanIntegrationBuild(threading.Thread):

    def init(self, project, webData, websocketServer):

        self.retuJsonData   = {
            'general' : 'Integration', \
            'header':{
                        'project': project, \
                        'release': None, \
                        'target': None}, \
            'payload':{
                        'returncode' : 0, \
                        'delivered': False, \
                        'progress': None, \
                        'availableSince': None}, \
            }



        self.ws         = websocketServer
        self.project    = project.upper()
        self.returncode = 0
        self.webJsonData= json.loads(webData)

        utils.warning("Scan Integration Build %s" % self.webJsonData)

    def run(self):

        # long running process
        environ = dict(os.environ)
        command = 'python ' + _constants.RELEASES_SCAN_PATH + ' -p \"' + self.project + '\" -i \"' + self.webJsonData.get('swPath') + '\"'

        utils.info("command %s" % command)

        process = Popen(command, shell=True, env=environ)
        process.wait()

        self.retuJsonData['payload']['returncode'] = process.returncode

        utils.warning("send_message_to_all %s" % json.dumps(self.retuJsonData))
        self.ws.server.send_message_to_all(json.dumps(self.retuJsonData))

# -------------------------------- WebsocketServer ---------------------------------
class EurekaWebsocketServer(threading.Thread):

    def run(self):
        self.server = WebsocketServer(9001)
        self.server.set_fn_new_client(self.new_client)
        self.server.set_fn_client_left(self.client_left)
        self.server.set_fn_message_received(self.message_received)
        self.server.run_forever()

    def new_client(self, client, server):
        print datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "EurekaWebsocketServer Client(%d) connected" % client['id']

    def client_left(self, client, server):
        print datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "EurekaWebsocketServer Client(%d) disconnected" % client['id']

    def message_received(self, client, server, message):
        if len(message) > 200:
            message = message[:200]+'..'
        print datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "EurekaWebsocketServer Client(%d) said: %s" % (client['id'], message)
