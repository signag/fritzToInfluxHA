# fritzToInfluxHA

The program periodically reads data from AVM Fritz!Box HA devices (voltage, power, energy, temperature) and stores these as measurements in an InfluxDB database.

In order to use the program you need
- A Fritz!Box supporting Home Automation (HA) devices
- One or more DECT HA devices or DECT Repeaters registered for the Fritz!Box
- An Influx DB V2.4 or later running on the same or another machine

AVM Information on interfaces and protocols for Fritz!Box access can be found at <https://avm.de/service/schnittstellen/>

InfluxDB (<https://www.influxdata.com/products/influxdb-overview/>) is a time series database which can be used as cloud version or local installation on various platforms.

## Getting started

| Step | Action                                                                                                                                       |
|------|----------------------------------------------------------------------------------------------------------------------------------------------|
| 1.   | Install **fritzToInfluxHA** (```[sudo] pip install fritzToInfluxHA```) on a Linux system (e.g. Raspberry Pi)                                 |
| 2.   | On the Fritz!Box configure a specific user with Smart Home permission. It is recommended not to allow internet access.                       |
| 3.   | Install and configure an InfluxDB V2.4 (<https://docs.influxdata.com/influxdb/v2.4/install/>)                                                |
| 4.   | In InfluxDB, create a new bucket (<https://docs.influxdata.com/influxdb/v2.4/organizations/buckets/create-bucket/>)                          |
| 5.   | In InfluxDB, create an API Token with write access to the bucket (<https://docs.influxdata.com/influxdb/v2.4/security/tokens/create-token/>) |
| 6.   | Create and stage configuration file for **fritzToInfluxHA** (see [Configuration](#configuration))                                            |
| 7.   | Do a test run (see [Usage](#usage))                                                                                                          |
| 8.   | Set up **fritzToInfluxHA** service (see [Serviceconfiguration](#serviceconfiguration))                               |

## Usage

```shell
usage: fritzToInfluxHA.py [-h] [-t] [-s] [-l] [-L] [-F] [-f FILE] [-v] [-c CONFIG]

    This program periodically reads data from Fritz!Box HA components
    and stores these as measurements in an InfluxDB database.

    If not otherwises specified on the command line, a configuration file
       fritzToInfluxHA.json
    will be searched sequentially under ./tests/data, $HOME/.config or /etc.

    This configuration file specifies credentials for Fritz!Box access,
    the devices to read from, the connection to the InfluxDB and other runtime parameters.


options:
  -h, --help            show this help message and exit
  -t, --test            Test run - single cycle - no wait
  -s, --service         Run as service - special logging
  -l, --log             Shallow (module) logging
  -L, --Log             Deep logging
  -F, --Full            Full logging
  -f FILE, --file FILE  Logging configuration from specified JSON dictionary file
  -v, --verbose         Verbose - log INFO level
  -c CONFIG, --config CONFIG
                        Path to config file to be used
```

## Configuration

Configuration for **fritzToInfluxHA** needs to be provided in a specific configuration file.
By default, a configuration file "fritzToInfluxHA.json" is searched under ```$HOME/.config``` or under ```/etc```.

For testing in a development environment, primarily the location ```../tests/data``` is searched for a configuration file.

Alternatively, the path to the configuration file can be specified on the command line.

### Structure of JSON Configuration File

The following is an example of a configuration file:
A a template can be found under
```./data``` in the installation folder.

```json
{
    "measurementInterval": 120,
    "FritzBoxURL" : "http://fritz.box/",
    "FritzBoxUser" : "FritzBoxMonitorUser",
    "FritzBoxPassword" : "FritzBoxMonitorUserPassword",
    "InfluxOutput" : true,
    "InfluxURL" : "http://InfluxServer:8086",
    "InfluxOrg" : "Home",
    "InfluxToken" : "InfluxToken",
    "InfluxBucket" : "FritzHA",
    "csvOutput" : false,
    "csvFile" : "tests/output/fritzBoxHAData.csv",
    "devices" : [
        {
            "ain" : "123456789012",
            "location" : "LivingRoom",
            "sublocation" : "Infotainment",
            "measurements" : {
                "voltage" : true,
                "power" : true,
                "energy" : true,
                "temperature" : true
            }
        },
        {
            "ain" : "123456789013",
            "location" : "Office",
            "sublocation" : "Desk",
            "measurements" : {
                "voltage" : true,
                "power" : true,
                "energy" : true,
                "temperature" : true
            }
        }
    ]
}
```

### Parameters

| Parameter            | Description                                                                                                       | Mandatory          |
|----------------------|-------------------------------------------------------------------------------------------------------------------|--------------------|
| measurementInterval  | Measurement interval in seconds. (Default: 120) (Note that the Fritz!Box will updata data only every 2 min.)      | No                 | 
| FritzBoxURL          | URL of the Fritz!Box (Default: "http://fritz.box/")                                                               | No                 |
| FritzBoxUser         | User to be used for FritzBox access. Needs th have "Smart Home" permission                                        | Yes                |
| FritzBoxPassword     | Password for Fritz!Box user                                                                                       | Yes                |
| InfluxOutput         | Specifies whether measurement shall be stored in InfluxDB (Default: false)                                        | No                 |
| InfluxURL            | URL for access to Influx DB                                                                                       | Yes                |
| InfluxOrg            | Organization Name specified during InfluxDB installation                                                          | Yes                |
| InfluxToken          | Influx API Token (see [Getting started](#gettingstarted))                                                         | Yes                |
| InfluxBucket         | Bucket to be used for storage of measurements                                                                     | Yes                |
| csvOutput            | Specifies whether measurement data shall be written to a csv file (Default: false)                                | No                 |
| csvFile              | Path to the csv file                                                                                              | For csvOutput=true |
| **devices**          | list of devices to be monitored. The program will notify any inconsistencies with devoces found on the Fritz!Box  | Yes                |
| - ain                | Actor Identification Number of the device                                                                         | Yes                |
| - location           | Location where the device is located (not available in Fritz!Box)                                                 | Yes                |
| - sublocation        | Location detail where the device is located (not available in Fritz!Box)                                          | Yes                |
| - **measurements**   | List of measurements to be performed                                                                              | Yes                |
| -- voltage           | Specifies whether voltage shall be measured (true, false)                                                         | Yes                |
| -- power             | Specifies whether power shall be measured (true, false)                                                           | Yes                |
| -- energy            | Specifies whether enrgy shall be measured (true, false)                                                           | Yes                |
| -- temperature       | Specifies whether temperature shall be measured (true, false)                                                     | Yes                |

## InfluxDB Data Schema
**fritzToInfluxHA** uses the following schema when storing measurements in the database:

|Data Element     |Description                                        |
|-----------------|---------------------------------------------------|
| timestamp       | timestamp when data is written to InfluxDB        |
| _measuerement   | "voltage", "power", "energy", "temperature"       |
| _field          | "value"                                           |
| _value          | value of the measurement received from Fritz!Box  |
| **tags**        | The following tags will be used:                  |
| - "ain"         | Actor identification number of the device         |
| - "location"    | Location specified in the device configuration    |
| - "sublocation" | Sublocation specified in the device configuration |
| - "state"       | State of the device: 0=Off, 1=On                  |

## Serviceconfiguration

To continuously log weather data, **fritzToInfluxHA** should be run as service.

A service configuration file template can be found under
```./data``` in the installation folder.

| Step | Action                                                                                             |
|------|----------------------------------------------------------------------------------------------------|
| 1.   | Adjust the service configuration file, if required, especially check python path and user          |
| 2.   | Stage configuration file: ```sudo cp fritzToInfluxHA.service /etc/systemd/system ```               |
| 3.   | Start service: ```sudo systemctl start fritzToInfluxHA.service ```                                 |
| 4.   | Check log: ```sudo journalctl -e ``` should show that **fritzToInfluxHA** has successfully started |
| 5.   | In case of errors adjust service configuration file and restart service                            |
| 6.   | To enable your service on every reboot: ```sudo systemctl enable fritzToInfluxHA.service```        |
