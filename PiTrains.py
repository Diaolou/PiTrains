#!/usr/bin/env python3
# Customisation variables
# Expects DARWIN_WEBSERVICE_API_KEY environment variable (you will need to sign up for an API key for OpenLDBWS)
# Expects DEPARTURE_CRS_CODE environment variable (e.g. "GTW" - the departure station that we're interested in)
# Expects DESTINATION_CRS_CODE environment variable (e.g. "BTN" - the destination station that we're interested in)

import argparse
import os
from datetime import datetime, timedelta
from nredarwin.webservice import DarwinLdbSession
from pprint import pprint
try:
    from blinkt import set_pixel, set_clear_on_exit, show
    GOT_BLINKT=True
except (ImportError, RuntimeError):
    GOT_BLINKT=False

# Handle args
parser = argparse.ArgumentParser(description="Live train notification tool for Raspberry Pi and Blinkt!")
parser.add_argument("--chatty", action="store_true", help="enable CLI output even if a Blinkt! is detected")
args = parser.parse_args()

# Initialise constants
AVAILABLELEDCOUNT = 8 # Total number of LEDs available; this should be 8 if you're using a Blinkt!
CURRENTYMD=datetime.now().strftime("%Y-%m-%d")
CURRENTTIME=datetime.now()
DARWINSESSION = DarwinLdbSession(wsdl='https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx')
DEPARTUREBOARD = DARWINSESSION.get_station_board(os.environ["DEPARTURE_CRS_CODE"],destination_crs=os.environ["DESTINATION_CRS_CODE"])

# Initialise lists
HumanReadableServices = []
ParsedServices = []
LEDs = [0]*AVAILABLELEDCOUNT

# White=5=imminent/just left, Green=4=on time, yellow=3=late, blue=2=unspecified delay, red=1=cancelled, black=0=none
COLOUR_LOOKUP_TABLE = [
    "Black",
    "Red",
    "Blue",
    "Yellow",
    "Green",
    "White"
]

train_services = DEPARTUREBOARD.train_services

# Populate HumanReadableServices and ParsedServices.
# We also check and deal with trains that wrap over midnight
for service in train_services:

    HumanReadableServices.append({"ScheduledTime": service.std, "ExpectedTime": service.etd, "OperatorName": service.operator_name})
    STD = datetime.strptime(CURRENTYMD+service.std, '%Y-%m-%d%H:%M')

    if(service.etd=="On time"):
        if STD < CURRENTTIME:
            STD += timedelta(1)
        TimeDelta = STD-CURRENTTIME
        if(int(TimeDelta.total_seconds()/60/5)<=AVAILABLELEDCOUNT-1):
            ParsedServices.append((int(TimeDelta.total_seconds()/60/5),4,COLOUR_LOOKUP_TABLE[4]))
        elif(int(TimeDelta.total_seconds()/60/5)>250):
            ParsedServices.append((0,5,COLOUR_LOOKUP_TABLE[5]))

    elif(service.etd=="Delayed"):
        if STD < CURRENTTIME:
            STD += timedelta(1)
        TimeDelta = STD-CURRENTTIME
        if(int(TimeDelta.total_seconds()/60/5)<=AVAILABLELEDCOUNT-1):
            ParsedServices.append((int(TimeDelta.total_seconds()/60/5),2,COLOUR_LOOKUP_TABLE[2]))
        elif(int(TimeDelta.total_seconds()/60/5)>250):
            ParsedServices.append((0,5,COLOUR_LOOKUP_TABLE[5]))

    elif(service.etd=="Cancelled"):
        if STD < CURRENTTIME:
            STD += timedelta(1)
        TimeDelta = STD-CURRENTTIME
        if(int(TimeDelta.total_seconds()/60/5)<=AVAILABLELEDCOUNT-1):
            ParsedServices.append((int(TimeDelta.total_seconds()/60/5),1,COLOUR_LOOKUP_TABLE[1]))

    else:
        ETD = datetime.strptime(CURRENTYMD+service.etd, '%Y-%m-%d%H:%M')
        if ETD < CURRENTTIME:
            ETD += timedelta(1)
        TimeDelta = ETD-CURRENTTIME
        if(int(TimeDelta.total_seconds()/60/5)<=AVAILABLELEDCOUNT-1):
            ParsedServices.append((int(TimeDelta.total_seconds()/60/5),3,COLOUR_LOOKUP_TABLE[3]))
        elif(int(TimeDelta.total_seconds()/60/5)>250):
            ParsedServices.append((0,5,COLOUR_LOOKUP_TABLE[5]))

# Dedupe ParsedServices to create LEDs. If one time slot contains more than one
# train, the "best" LED state is set - White>Green>Yellow>Blue>Red>Black
for Service in ParsedServices:
        if(Service[1]>LEDs[Service[0]]):
            LEDs[Service[0]]=Service[1]

# Set Blinkt! LEDs, if we have one
if GOT_BLINKT:
    for idx,LEDToSet in enumerate(LEDs):
        if(LEDToSet==5):
            set_pixel(AVAILABLELEDCOUNT-1-idx,1,1,1)
        elif(LEDToSet==4):
            set_pixel(AVAILABLELEDCOUNT-1-idx,0,1,0)
        elif(LEDToSet==3):
            set_pixel(AVAILABLELEDCOUNT-1-idx,1,1,0)
        elif(LEDToSet==2):
            set_pixel(AVAILABLELEDCOUNT-1-idx,0,1,0)
        elif(LEDToSet==1):
            set_pixel(AVAILABLELEDCOUNT-1-idx,1,0,0)
    set_clear_on_exit(False)
    show()

# Print to CLI if requested or if we don't have a Blinkt!
if args.chatty or not GOT_BLINKT:
    DATA_TO_OUTPUT = {
        "DEPARTURE_CRS_CODE": os.environ["DEPARTURE_CRS_CODE"],
        "DESTINATION_CRS_CODE": os.environ["DESTINATION_CRS_CODE"],
        "HumanReadableServices": HumanReadableServices,
        "ParsedServices": ParsedServices,
        "LEDs": LEDs
    }
    pprint(DATA_TO_OUTPUT)