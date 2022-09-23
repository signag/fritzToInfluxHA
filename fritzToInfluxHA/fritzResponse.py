#!/usr/bin/python3
"""
Module fritzToInfluxHA

This module reads data from Fritz!Box Home Automation modules
and and stores related measurement date in an InfluxDB
"""
import argparse
import hashlib

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=
"""
This program calculates the response value for Fritz!Box login
from challenge and password
"""
)
parser.add_argument("-c", "--challenge", help="Challenge")
parser.add_argument("-p", "--password", help="Password")

args = parser.parse_args()

challenge = None
password = None

if args.challenge:
    challenge = args.challenge
if args.password:
    password = args.password

if not challenge or not password:
    print("challenge or password missing")
else:
    md5 = hashlib.md5()
    md5.update(challenge.encode('utf-16le'))
    md5.update('-'.encode('utf-16le'))
    md5.update(password.encode('utf-16le'))
    response = challenge + '-' + md5.hexdigest()

    print("response: " + response)


