#!/usr/bin/python3
"""Module FritzHaDevice

This module includes classes for an abstraction of a Fritz Home Automation device.
"""

#Setup logging
import logging
from tkinter import N
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

    def __del__(self):
        self.terminate()

    def terminate(self):
        self.logoff()
