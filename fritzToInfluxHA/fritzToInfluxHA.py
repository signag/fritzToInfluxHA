#!/usr/bin/python3
"""
Module fritzToInfluxHA

This module periodically reads data from Fritz!Box Home Automation modules
and and stores related measurement date in an InfluxDB
"""

import time
import datetime
import math
import os.path
import json
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from fritz.FritzBox import FritzBox, FritzBoxError, FritzBoxIgnoreableError

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
    "measurementInterval": 120,
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
    fLogger = logging_plus.getLogger(FritzBox.__module__)
    fLogger.addHandler(logging.NullHandler())
    rLogger = logging_plus.getLogger()
    rLogger.addHandler(logging.NullHandler())

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
        handler.setFormatter(formatter2)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        fLogger.addHandler(handler)
        fLogger.setLevel(logging.DEBUG)

    if args.Full:
        # Full logging
        handler.setFormatter(formatter2)
        rLogger.addHandler(handler)
        rLogger.setLevel(logging.DEBUG)
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
            fLogger.addHandler(handler)
            fLogger.setLevel(logging.WARNING)

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
    logger.info("    Devices:%s", len(cfg["devices"]))
    for ind in range(0, len(cfg["devices"])):
        dev = cfg["devices"][ind]
        logger.info("       %s (%s - %s)", dev["ain"], dev["location"], dev["sublocation"])


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

def logDeviceInconsistencies(cfgDefs, fritzDevs):
    for dev in fritzDevs:
        if not dev.isMonitored:
            logger.error("Missing configuretion for device ain=%s name=%s", dev.ain, dev.name)
    for ind in range(0, len(cfg["devices"])):
        devc = cfg["devices"][ind]
        cnt = 0
        for dev in fritzDevs:
            if dev.ain == devc["ain"]:
                cnt = cnt + 1
                break
        if cnt == 0:
            logger.error("No device found for configuration ain=%s", devc["ain"])

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

fb = None
influxClient = None
influxWriteAPI = None

try:
    # Log in to FritzBox
    fb = FritzBox(cfg["FritzBoxURL"], cfg["FritzBoxUser"], cfg["FritzBoxPassword"])
    logger.debug("FritzBox fb instantiated")

    # Complete device data from configiration data
    fb.completeDeviceData(cfg["devices"])
    logger.debug("Device data completed from config for %s devices", len(cfg["devices"]))

    # Log inconsistencies between configured devices and devices found on FritzBox
    logDeviceInconsistencies(cfg["devices"], fb.devices)

    # Instatntiate InfluxDB access
    if cfg["InfluxOutput"]:
        influxClient = influxdb_client.InfluxDBClient(
            url=cfg["InfluxURL"],
            token=cfg["InfluxToken"],
            org=cfg["InfluxOrg"]
        )
        influxWriteAPI = influxClient.write_api(write_options=SYNCHRONOUS)
        logger.debug("Influx interface instantiated")

    noWait = False
    stop = False

except FritzBoxError as error:
    logger.critical("Unexpected error: %s", error.message)
    stop = True
    fb = None
    influxClient = None
    influxWriteAPI = None

failcount = 0
while not stop:
    try:
        # Wait unless noWait is set in case of sensor error.
        # Akip waiting for test run
        if not noWait and not testRun:
            waitForNextCycle()
        noWait = False

        ### Test FritzBox down (simulated through invalid URL)
        ### Start Test
        #if failcount == 0:
        #    testRun = False
        #    # Make URL invalid
        #    fb.url = "http://fritzy.box"
        #    # Make sid invalid which would be the case for a FritzBox update
        #    fb.sid = "xyz"
        #if failcount == 2:
        #    fb.url = cfg["FritzBoxURL"]
        #    testRun = True
        ### End Test

        # Get measurements for all devices
        fb.evaluateDeviceInfo()
        if not servRun:
            logger.info("Measurement completed")

        # Write data to CSV
        if cfg["csvOutput"]:
            fp = cfg["csvFile"]
            fb.writeDataToCsv(fp)

        # Write data to InfluxDB
        if cfg["InfluxOutput"]:
            fb.writeDataToInflux(influxWriteAPI, cfg["InfluxOrg"], cfg["InfluxBucket"])
            if not servRun:
                logger.info("Data written to InfluxDB")

        if testRun:
            # Stop in case of test run
            stop = True

    except FritzBoxIgnoreableError as error:
        failcount = failcount + 1
        logger.error("Ignored FritzBoxIgnoreableError (%s): %s", failcount, error.message)

        noWait = True
        if testRun:
            # Stop in case of test run
            stop = True
        else:
            time.sleep(2.0)
            continue

    except FritzBoxError as error:
        logger.critical("Unexpected error: %s", error.message)
        if fb:
            del fb
        if influxClient:
            del influxClient
        if influxWriteAPI:
            del influxWriteAPI

    except Exception as e:
        logger.critical("Unexpected error (%s): %s", e.__class__, e.__cause__)
        if fb:
            del fb
        if influxClient:
            del influxClient
        if influxWriteAPI:
            del influxWriteAPI
        raise error

    except KeyboardInterrupt:
        if fb:
            del fb
        if influxClient:
            del influxClient
        if influxWriteAPI:
            del influxWriteAPI

if fb:
    del fb
if influxClient:
    del influxClient
if influxWriteAPI:
    del influxWriteAPI

logger.info("=============================================================")
logger.info("fritzToInfluxHA terminated")
logger.info("=============================================================")
