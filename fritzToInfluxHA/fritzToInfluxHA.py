#!/usr/bin/python3
"""
Module fritzToInfluxHA

This module reads data from Fritz!Box Home Automation modules
and and stores related measurement date in an InfluxDB
"""

import time
import datetime
import math
import os.path
import json
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from fritz.FritzBox import FritzBox

# Set up logging
import logging
from logging.config import dictConfig
import logging_plus
logger = logging_plus.getLogger("main")

testRun = False
servRun = False

# Configuration defaults
cfgFile = ""
cfg = {
    "measurementInterval": 2,
    "FritzBoxURL" : "http://fritz.box/",
    "FritzBoxUser" : None,
    "FritzBoxPassword" : None,
    "InfluxOutput" : False,
    "InfluxURL" : None,
    "InfluxOrg" : None,
    "InfluxToken" : None,
    "InfluxBucket" : None,
    "csvOutput" : False,
    "csvFile" : "",
    "devices" : []
}

# Constants
CFGFILENAME = "fritzToInfluxHA.json"

def getCl():
    """
    getCL: Get and process command line parameters
    """

    import argparse
    import os.path

    global logger
    global testRun
    global servRun
    global cfgFile

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=
    """
    This program periodically reads data from Fritz!Box HA components
    and stores these as measurements in an InfluxDB database.

    If not otherwises specified on the command line, a configuration file
       fritzToInfluxHA.json
    will be searched sequentially under ./tests/data, $HOME/.config or /etc.

    This configuration file specifies credentials for Fritz!Box access,
    the devices to read from, the connection to the InfluxDB and other runtime parameters.
    """
    )
    parser.add_argument("-t", "--test", action = "store_true", help="Test run - single cycle - no wait")
    parser.add_argument("-s", "--service", action = "store_true", help="Run as service - special logging")
    parser.add_argument("-l", "--log", action = "store_true", help="Shallow (module) logging")
    parser.add_argument("-L", "--Log", action = "store_true", help="Deep logging")
    parser.add_argument("-F", "--Full", action = "store_true", help="Full logging")
    parser.add_argument("-f", "--file", help="Logging configuration from specified JSON dictionary file")
    parser.add_argument("-v", "--verbose", action = "store_true", help="Verbose - log INFO level")
    parser.add_argument("-c", "--config", help="Path to config file to be used")

    args = parser.parse_args()

    # Disable logging
    logger = logging_plus.getLogger("main")
    logger.addHandler(logging.NullHandler())

    # Set handler and formatter to be used
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    formatter2 = logging.Formatter('%(asctime)s %(name)-33s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)

    if args.log:
        # Shallow logging
        handler.setFormatter(formatter2)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    if args.Log:
        # Deep logging
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        # Activate logging of function entry and exit
        logging_plus.registerAutoLogEntryExit()

    if args.Full:
        # Full logging
        # Activate logging of function entry and exit
        logging_plus.registerAutoLogEntryExit()

    if args.file:
        # Logging configuration from file
        logDictFile = args.file
        if not os.path.exists(logDictFile):
            raise ValueError("Logging dictionary file from command line does not exist: " + logDictFile)

        # Load dictionary
        with open(logDictFile, 'r') as f:
            logDict = json.load(f)

        # Set config file for logging
        dictConfig(logDict)
        logger = logging.getLogger()
        # Activate logging of function entry and exit
        #logging_plus.registerAutoLogEntryExit()

    # Explicitly log entry
    if args.Log or args.Full:
        logger.logEntry("getCL")
    if args.log:
        logger.debug("Shallow logging (main only)")
    if args.Log:
        logger.debug("Deep logging")
    if args.file:
        logger.debug("Logging dictionary from %s", logDictFile)

    if args.verbose or args.service:
        if not args.log and not args.Log and not args.Full:
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    if args.test:
        testRun = True

    if args.service:
        servRun = True

    if testRun:    
        logger.debug("Test run mode activated")
    else:
        logger.debug("Test run mode deactivated")
        
    if servRun:    
        logger.debug("Service run mode activated")
    else:
        logger.debug("Service run mode deactivated")

    if args.config:
        cfgFile = args.config
        logger.debug("Config file: %s", cfgFile)
    else:
        logger.debug("No Config file specified on command line")

    if args.Log or args.Full:
        logger.logExit("getCL")

def getConfig():
    """
    Get configuration for fritzToInfluxHA
    """
    global cfgFile
    global cfg
    global logger

    # Check config file from command line
    if cfgFile != "":
        if not os.path.exists(cfgFile):
            raise ValueError("Configuration file from command line does not exist: ", cfgFile)
        logger.info("Using cfgFile from command line: %s", cfgFile)

    if cfgFile == "":
        # Check for config file in ./tests/data directory
        curDir = os.path.dirname(os.path.realpath(__file__))
        curDir = os.path.dirname(curDir)
        cfgFile = curDir + "/tests/data/" + CFGFILENAME
        if not os.path.exists(cfgFile):
            # Check for config file in /etc directory
            logger.info("Config file not found: %s", cfgFile)
            cfgFile = ""

    if cfgFile == "":
        # Check for config file in home directory
        homeDir = os.environ['HOME']
        cfgFile = homeDir + "/.config/" + CFGFILENAME
        if not os.path.exists(cfgFile):
            # Check for config file in /etc directory
            logger.info("Config file not found: %s", cfgFile)
            cfgFile = "/etc/" + CFGFILENAME
            if not os.path.exists(cfgFile):
                logger.info("Config file not found: %s", cfgFile)
                cfgFile = ""

    if cfgFile == "":
        # No cfg available 
        logger.info("No config file available. Using default configuration")
    else:
        logger.info("Using cfgFile: %s", cfgFile)
        with open(cfgFile, 'r') as f:
            conf = json.load(f)
            if "measurementInterval" in conf:
                cfg["measurementInterval"] = conf["measurementInterval"]
            if "FritzBoxURL" in conf:
                cfg["FritzBoxURL"] = conf["FritzBoxURL"]
            if "FritzBoxUser" in conf:
                cfg["FritzBoxUser"] = conf["FritzBoxUser"]
            if "FritzBoxPassword" in conf:
                cfg["FritzBoxPassword"] = conf["FritzBoxPassword"]
            if "InfluxOutput" in conf:
                cfg["InfluxOutput"] = conf["InfluxOutput"]
            if "InfluxURL" in conf:
                cfg["InfluxURL"] = conf["InfluxURL"]
            if "InfluxOrg" in conf:
                cfg["InfluxOrg"] = conf["InfluxOrg"]
            if "InfluxToken" in conf:
                cfg["InfluxToken"] = conf["InfluxToken"]
            if "InfluxBucket" in conf:
                cfg["InfluxBucket"] = conf["InfluxBucket"]
            if "csvOutput" in conf:
                cfg["csvOutput"] = conf["csvOutput"]
            if "csvFile" in conf:
                cfg["csvFile"] = conf["csvFile"]
            if cfg["csvFile"] == "":
                cfg["csvOutput"] = False
            if "devices" in conf:
                cfg["devices"] = conf["devices"]

    logger.info("Configuration:")
    logger.info("    measurementInterval:%s", cfg["measurementInterval"])
    logger.info("    FritzBoxURL:%s", cfg["FritzBoxURL"])
    logger.info("    FritzBoxUser:%s", cfg["FritzBoxUser"])
    logger.info("    FritzBoxPassword:%s", cfg["FritzBoxPassword"])
    logger.info("    InfluxOutput:%s", cfg["InfluxOutput"])
    logger.info("    InfluxURL:%s", cfg["InfluxURL"])
    logger.info("    InfluxOrg:%s", cfg["InfluxOrg"])
    logger.info("    InfluxToken:%s", cfg["InfluxToken"])
    logger.info("    InfluxBucket:%s", cfg["InfluxBucket"])
    logger.info("    csvOutput:%s", cfg["csvOutput"])
    logger.info("    csvFile:%s", cfg["csvFile"])


def waitForNextCycle():
    """
    Wait for next measurement cycle.

    This function assures that measurements are done at specific times depending on the specified interval
    In case that measurementInterval is an integer multiple of 60, the waiting time is calculated in a way,
    that one measurement is done every full hour.
    """
    global cfg

    if (cfg["measurementInterval"] % 60 == 0)\
    or (cfg["measurementInterval"] % 120 == 0)\
    or (cfg["measurementInterval"] % 240 == 0)\
    or (cfg["measurementInterval"] % 300 == 0)\
    or (cfg["measurementInterval"] % 360 == 0)\
    or (cfg["measurementInterval"] % 600 == 0)\
    or (cfg["measurementInterval"] % 720 == 0)\
    or (cfg["measurementInterval"] % 900 == 0)\
    or (cfg["measurementInterval"] % 1200 == 0)\
    or (cfg["measurementInterval"] % 1800 == 0):
        tNow = datetime.datetime.now()
        seconds = 60 * tNow.minute
        period = math.floor(seconds/cfg["measurementInterval"])
        waitTimeSec = (period + 1) * cfg["measurementInterval"] - (60 * tNow.minute + tNow.second + tNow.microsecond / 1000000)
        logger.debug("At %s waiting for %s sec.", datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S,"), waitTimeSec)
        time.sleep(waitTimeSec)
    elif (cfg["measurementInterval"] % 2 == 0)\
      or (cfg["measurementInterval"] % 4 == 0)\
      or (cfg["measurementInterval"] % 5 == 0)\
      or (cfg["measurementInterval"] % 6 == 0)\
      or (cfg["measurementInterval"] % 10 == 0)\
      or (cfg["measurementInterval"] % 12 == 0)\
      or (cfg["measurementInterval"] % 15 == 0)\
      or (cfg["measurementInterval"] % 20 == 0)\
      or (cfg["measurementInterval"] % 30 == 0):
            tNow = datetime.datetime.now()
            seconds = 60 * tNow.minute + tNow.second
            period = math.floor(seconds/cfg["measurementInterval"])
            waitTimeSec = (period + 1) * cfg["measurementInterval"] - seconds
            logger.debug("At %s waiting for %s sec.", datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S,"), waitTimeSec)
            time.sleep(waitTimeSec)
    else:
        waitTimeSec =cfg["measurementInterval"]
        logger.debug("At %s waiting for %s sec.", datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S,"), waitTimeSec)
        time.sleep(waitTimeSec)

#============================================================================================
# Start __main__
#============================================================================================
#
# Get Command line options
getCl()

logger.info("=============================================================")
logger.info("fritzToInfluxHA started")
logger.info("=============================================================")

# Get configuration
getConfig()

# Log in to FritzBox
fb = FritzBox(cfg["FritzBoxURL"], cfg["FritzBoxUser"], cfg["FritzBoxPassword"])

# Complete device data from configiration data
fb.completeDeviceData(cfg["devices"])

# Instatntiate InfluxDB access
if cfg["InfluxOutput"]:
    influxClient = influxdb_client.InfluxDBClient(
        url=cfg["InfluxURL"],
        token=cfg["InfluxToken"],
        org=cfg["InfluxOrg"]
    )
    influxWriteAPI = influxClient.write_api(write_options=SYNCHRONOUS)

noWait = False
stop = False

while not stop:
    try:
        # Wait unless noWait is set in case of sensor error.
        # Akip waiting for test run
        if not noWait and not testRun:
            waitForNextCycle()
        noWait = False

        # Get measurements for all devices
        fb.evaluateDeviceInfo()
        logger.info("Measurement completed")

        # Write data to CSV
        if cfg["csvOutput"]:
            fp = cfg["csvFile"]
            fb.writeDataToCsv(fp)

        # Write data to InfluxDB
        if cfg["InfluxOutput"]:
            fb.writeDataToInflux(influxWriteAPI, cfg["InfluxOrg"], cfg["InfluxBucket"])
            logger.info("Data written to InfluxDB")

        if testRun:
            # Stop in case of test run
            stop = True


    except RuntimeError as error:
        # Errors 
        if not servRun:
            logger.error("Ignored RuntimeError: %s", error.args[0])

        noWait = True
        if testRun:
            # Stop in case of test run
            stop = True
        else:
            time.sleep(2.0)
            continue

    except Exception as error:
        if fb:
            del fb
        raise error

    except KeyboardInterrupt:
        if fb:
            del fb

if fb:
    del fb

logger.info("=============================================================")
logger.info("fritzToInfluxHA terminated")
logger.info("=============================================================")
