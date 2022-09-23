#!/usr/bin/python3
"""Module FritzHaDevice

This module includes classes for an abstraction of a Fritz Home Automation device.
"""

#Setup logging
import logging
from math import fabs
from tkinter import N
from tkinter.messagebox import NO
import logging_plus
logger = logging_plus.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class FritzHaDeviceError(Exception):
    """
    Base exception class for this module
    """
    pass

class FritzHaDevice:
    """
    Class representing a Fritz Home Automation device
    """
    def __init__(self, ain):
        """
        Constructor for Fritz device
        """
        self.ain = ain
        self.type = None
        self.name = None
        self.location = None
        self.sublocation = None
        self.state = None
        self.present = None
        self.voltage = None
        self.power = None
        self.energy = None
        self.temperature = None
        self.measurementTime = None

        self.hasState = False
        self.hasTemperature = False
        self.hasPower = False

        self.measureVoltage = False
        self.measurements = {}

    def __del__(self):
        self.terminate()

    def terminate(self):
        self.logoff()

    def completeData(self, data):
        """
        Complete data with given data
        """
        if "location" in data:
            self.location = data["location"]
        if "sublocation" in data:
            self.sublocation = data["sublocation"]
        if "measurements" in data:
            self.measurements = data["measurements"]
