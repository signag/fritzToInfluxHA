#!/usr/bin/python3
#MIT License
#
#Copyright (c) 2022 signag
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.
"""Module FritzBox

This module includes classes for an abstraction of a Fritz!Box.
"""
import requests
import hashlib
import os
import xml.etree.ElementTree as ET
from enum import Enum
import datetime
import influxdb_client
from .FritzHaDevice import FritzHaDevice

#Setup logging
import logging
import logging_plus
logger = logging_plus.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Supported device types
class HaDeviceType(Enum):
    SWITCH = 1
    REPEATER = 2
    LAMP = 3
    UNKNOWN = 9

class FritzBoxError(Exception):
    """
    Base exception class for this module
    """
    pass

class FritzBoxLoginError(FritzBoxError):
    """
    Fritzbox Login exception class for this module
    """
    def __init__(self):
        self.message = "Fritz!Box login failed"

class FritzBox:
    """
    Class representing a Fritz!Box
    """
    def __init__(self, url, user, pwd):
        """
        Constructor for Fritz!Box
        """
        self.url = url
        if self.url[-1] != "/":
            self.url = self.url + "/"

        self.sid = "0000000000000000"
        self.user = user
        self.pwd = pwd
        self.devices = []

        # Login
        self.login()

        # Get list of devices
        self.getHaDevices()


    def __del__(self):
        self.terminate()

    def terminate(self):
        self.logoff()

    def login(self):
        """
        Login with Session-ID
        """
        #Try login with current sid
        theUrl = self.url + "login_sid.lua" + "?sid=" + self.sid
        resp = self.sendRequest(theUrl)
        root = ET.fromstring(resp)
        if root.findtext("SID") == "0000000000000000":
            #invalid SID. Need to get new SID
            challenge = root.findtext("Challenge")
            if challenge:
                self.getSid(challenge)
            else:
                raise FritzBoxLoginError

    def logoff(self):
        """
        Log off from Fritz!Box
        """
        theUrl = self.url + "?logout=1&sid=" + self.sid
        self.sendRequest(theUrl)


    def getSid(self, challenge):
        """
        Get the session ID
        """
        md5 = hashlib.md5()
        md5.update(challenge.encode('utf-16le'))
        md5.update('-'.encode('utf-16le'))
        md5.update(self.pwd.encode('utf-16le'))
        response = challenge + '-' + md5.hexdigest()
        theUrl = f"{self.url}login_sid.lua?username={self.user}&response={response}"
        resp = self.sendRequest(theUrl)
        if resp:
            root = ET.fromstring(resp)
            self.sid = root.findtext("SID")
            logger.debug("SID: %s", self.sid)
        else:
            raise FritzBoxLoginError

    def sendRequest(self, url):
        """
        Send a request with given URL and return response
        """
        logger.debug("Request URL: %s", url)
        resp = requests.get(url)
        if resp.status_code == requests.codes.OK:
            respTxt = resp.text.strip()
            logger.debug("Response: %s", respTxt)
            return respTxt
        else:
            logger.error("HTTP request [" + resp.url + "] failed with status code " + resp.status_code + " reason " + resp.reason)
            resp.raise_for_status
            return None

    def getHaDevices(self):
        """
        Get the Home Automation devices registered for the Fritz!Box
        """
        # Get the device list infos
        # This is preferred to get switch list because it includes all devices
        theUrl = self.url + "webservices/homeautoswitch.lua" + "?switchcmd=getdevicelistinfos&sid=" + self.sid
        resp = self.sendRequest(theUrl)
        root = ET.fromstring(resp)

        # Loop through devices
        for dev in root:
            ain = dev.attrib['identifier']
            ain = ain.strip()
            ain = ain.replace(" ", "")
            product = dev.attrib['productname']
            haDev = FritzHaDevice(ain)

            if product == "FRITZ!DECT 200" or product == "FRITZ!DECT 210":
                haDev.type = HaDeviceType.SWITCH
                haDev.hasState = True
                switch = dev.find("switch")
                haDev.state = switch.findtext("state")
            elif product == "FRITZ!DECT Repeater 100":
                haDev.type = HaDeviceType.REPEATER
                haDev.hasTemperature = True
            else:
                haDev.type = HaDeviceType.UNKNOWN

            haDev.name = dev.findtext("name")
            haDev.present = dev.findtext("present")

            if dev.find("powermeter"):
                haDev.hasPower = True
            if dev.find("temperature"):
                haDev.hasTemperature = True

            self.devices.append(haDev)

    def completeDeviceData(self, data):
        """
        Complete device data with given data        
        """
        for dev in self.devices:
            ain = dev.ain
            for ref in data:
                if ref["ain"] == ain:
                    dev.completeData(ref)
    
    def evaluateDeviceInfo(self):
        """
        Query device info from Fritzbox and update devices with measurements
        """
        try:
            measurementTime = datetime.datetime.now()
            theUrl = self.url + "webservices/homeautoswitch.lua" + "?switchcmd=getdevicelistinfos&sid=" + self.sid
            resp = self.sendRequest(theUrl)
            if not resp:
                # In case of request error: login with new SID
                self.login()
                resp = self.sendRequest(theUrl)
                if not resp:
                    # In case of repeated error throw exception
                    logger.error("Error sending request for getdevicelistinfos after successful logib")
                    raise FritzBoxError

            root = ET.fromstring(resp)
            for dev in root:
                ain = dev.attrib['identifier']
                ain = ain.strip()
                ain = ain.replace(" ", "")
                device = None
                for sdev in self.devices:
                    if sdev.ain == ain:
                        device = sdev
                        break
                if device:
                    powermeter = dev.find("powermeter")
                    if powermeter:
                        voltage = powermeter.findtext("voltage")
                        if voltage:
                            device.voltage = int(voltage)/1000
                        power = powermeter.findtext("power")
                        if power:
                            device.power = int(power)/1000
                        energy = powermeter.findtext("energy")
                        if energy:
                            device.energy = int(energy)/1000
                    temperature = dev.find("temperature")
                    if temperature:
                        celsius = temperature.findtext("celsius")
                        if celsius:
                            device.temperature = int(celsius)/10
                    device.measurementTime = measurementTime

        except FritzBoxError as error:
            raise

    def writeDataToCsv(self, fp):
        """
        Write measurement values to a csv file
        """
        f = None
        newFile=True
        if os.path.exists(fp):
            newFile = False
        if newFile:
            f = open(fp, 'w')
        else:
            f = open(fp, 'a')
        logger.debug("File opened: %s", fp)

        sep = ","
        if newFile:
            txt = "Time" + sep \
                + "AIn" + sep \
                + "Type" + sep \
                + "Name" + sep \
                + "Location" + sep \
                + "Sublocation" + sep \
                + "State" + sep \
                + "Present" + sep \
                + "Voltage" + sep \
                + "Power" + sep \
                + "Energy" + sep \
                + "Temperature" \
                + "\n"
            f.write(txt)

        for dev in self.devices:
            txt = ""
            if dev.measurementTime:
                ts = dev.measurementTime.strftime("%Y-%m-%d %H:%M:%S.%f")
                txt = txt + ts + sep
            else:
                txt = txt + sep
            if dev.ain:
                txt = txt + dev.ain + sep
            else:
                txt = txt + sep
            if dev.type:
                txt = txt + dev.type.name + sep
            else:
                txt = txt + sep
            if dev.name:
                txt = txt + dev.name + sep
            else:
                txt = txt + sep
            if dev.location:
                txt = txt + dev.location + sep
            else:
                txt = txt + sep
            if dev.sublocation:
                txt = txt + dev.sublocation + sep
            else:
                txt = txt + sep
            if dev.state:
                txt = txt + dev.state + sep
            else:
                txt = txt + sep
            if dev.present:
                txt = txt + dev.present + sep
            else:
                txt = txt + sep
            if dev.voltage:
                txt = txt + format(dev.voltage) + sep
            else:
                txt = txt + sep
            if dev.power:
                txt = txt + format(dev.power) + sep
            else:
                txt = txt + sep
            if dev.energy:
                txt = txt + format(dev.energy) + sep
            else:
                txt = txt + sep
            if dev.temperature:
                txt = txt + format(dev.temperature)
            txt = txt + "\n"
            f.write(txt)

        f.close()

    def writeDataToInflux(self, write_api, org, bucket):
        """
        Write measurements to InfluxDB
        """
        for dev in self.devices:
            dev.writeMeasurmentsToInfluxDB(write_api, org, bucket)
