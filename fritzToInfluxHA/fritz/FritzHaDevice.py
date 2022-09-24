#!/usr/bin/python3
"""Module FritzHaDevice

This module includes classes for an abstraction of a Fritz Home Automation device.
"""

#Setup logging
import influxdb_client
from influxdb_client.client.write_api import WritePrecision
import logging
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
        pass

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

    def writeMeasurmentsToInfluxDB(self, write_api, org, bucket):
        ts = self.measurementTime.strftime("%Y-%m-%dT%H:%M:%S.%f+02")
        if "voltage" in self.measurements:
            if self.measurements["voltage"] and self.voltage:
                point = influxdb_client.Point("voltage") \
                       .tag("ain", self.ain) \
                       .tag("location", self.location) \
                       .tag("sublocation", self.sublocation) \
                       .tag("state", self.state) \
                       .field("value", self.voltage)
                write_api.write(bucket=bucket, org=org, record=point)

        if "power" in self.measurements:
            if self.measurements["power"] and self.power:
                point = influxdb_client.Point("power") \
                       .tag("ain", self.ain) \
                       .tag("location", self.location) \
                       .tag("sublocation", self.sublocation) \
                       .tag("state", self.state) \
                       .field("value", self.power)
                write_api.write(bucket=bucket, org=org, record=point)

        if "energy" in self.measurements:
            if self.measurements["energy"] and self.energy:
                point = influxdb_client.Point("energy") \
                       .tag("ain", self.ain) \
                       .tag("location", self.location) \
                       .tag("sublocation", self.sublocation) \
                       .tag("state", self.state) \
                       .field("value", self.energy)
                write_api.write(bucket=bucket, org=org, record=point)

        if "temperature" in self.measurements:
            if self.measurements["temperature"] and self.temperature:
                state = self.state
                if not state:
                    state = "1"
                point = influxdb_client.Point("temperature") \
                       .tag("ain", self.ain) \
                       .tag("location", self.location) \
                       .tag("sublocation", self.sublocation) \
                       .tag("state", state) \
                       .field("value", self.temperature)
                write_api.write(bucket=bucket, org=org, record=point)
