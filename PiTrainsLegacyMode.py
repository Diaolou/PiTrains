#!/usr/bin/env python3

# Customisation variables
# Expects DARWIN_WEBSERVICE_API_KEY environment variable (you will need to sign up for an API key for OpenLDBWS)
# Expects DEPARTURE_CRS_CODE environment variable (e.g. "GTW" - the departure station that we're interested in)
# Expects DESTINATION_CRS_CODE environment variable (e.g. "BTN" - the destination station that we're interested in)
AvailableLEDCount = 8 # Total number of LEDs available; this should be 8 if you're using a Blinkt!

# Uses nre-darwin-py package (install with pip)
from nredarwin.webservice import DarwinLdbSession
from blinkt import set_all, set_pixel, set_clear_on_exit, show
from datetime import datetime, timedelta
import os
import syslog

DarwinSession = DarwinLdbSession(wsdl='https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx')
DepartureBoard = DarwinSession.get_station_board(os.environ["DEPARTURE_CRS_CODE"],destination_crs=os.environ["DESTINATION_CRS_CODE"])

# Initialise lists
ServiceStatus = []
LEDs = []

# Each LED represents a train on the departure board. Green=on time, yellow=up to
# 10 minutes late, red=cancelled or more than 10 minutes late, blue=unspecified delay
for idx, service in enumerate(DepartureBoard.train_services):
    if(idx<=(AvailableLEDCount-1)):
        ServiceStatus.append((service.std, service.etd))
        if(service.etd=="On time"):
            LEDs.append("Green")
        elif(service.etd=="Delayed"):
            LEDs.append("Blue")
        elif(service.etd=="Cancelled"):
            LEDs.append("Red")
        else:
            ETD = datetime.strptime(service.etd, '%H:%M')
            STD = datetime.strptime(service.std, '%H:%M')
            if ETD < STD:
                ETD += timedelta(1)
            TimeDelta = ETD-STD
            if(TimeDelta.total_seconds() <= 600):
                LEDs.append("Yellow")
            else:
                LEDs.append("Red")

# Syslog the info
syslog.syslog(str(ServiceStatus))
syslog.syslog(str(LEDs))

# Set LEDs. All lights white means too many trains to display
if(len(LEDs)<1 or len(LEDs)>AvailableLEDCount):
    set_all(1,1,1)
else:
    for idx, LED in enumerate(LEDs):
        if(LED=="Green"):
            set_pixel(7-idx,0,1,0)
        elif(LED=="Blue"):
            set_pixel(7-idx,0,0,1)
        elif(LED=="Yellow"):
            set_pixel(7-idx,1,1,0)
        elif(LED=="Red"):
            set_pixel(7-idx,1,0,0)

set_clear_on_exit(False)
show()
