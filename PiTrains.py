#!/usr/bin/env python3
# Customisation variables
# Expects DARWIN_WEBSERVICE_API_KEY environment variable (you will need to sign up for an API key for OpenLDBWS)
# Expects DEPARTURE_CRS_CODE environment variable (e.g. "GTW" - the departure station that we're interested in)
# Expects DESTINATION_CRS_CODE environment variable (e.g. "BTN" - the destination station that we're interested in)

import argparse
import json
import os
import signal
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pprint import pprint

from nredarwin.webservice import DarwinLdbSession

try:
    from blinkt import set_clear_on_exit, set_pixel, show

    GOT_BLINKT = True
except (ImportError, RuntimeError):
    GOT_BLINKT = False


AVAILABLELEDCOUNT = 8  # Total number of LEDs available; this should be 8 if you're using a Blinkt!

# White=5=imminent/just left, Green=4=on time, yellow=3=late, blue=2=unspecified delay, red=1=cancelled, black=0=none
COLOUR_LOOKUP_TABLE = ["Black", "Red", "Blue", "Yellow", "Green", "White"]


def collect_train_data():
    current_ymd = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now()
    darwin_session = DarwinLdbSession(wsdl="https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx")
    departure_board = darwin_session.get_station_board(
        os.environ["DEPARTURE_CRS_CODE"], destination_crs=os.environ["DESTINATION_CRS_CODE"]
    )

    human_readable_services = []
    parsed_services = []
    leds = [0] * AVAILABLELEDCOUNT

    train_services = departure_board.train_services or []

    # Populate human_readable_services and parsed_services.
    # We also check and deal with trains that wrap over midnight
    for service in train_services:
        human_readable_services.append(
            {"ScheduledTime": service.std, "ExpectedTime": service.etd, "OperatorName": service.operator_name}
        )
        std = datetime.strptime(current_ymd + service.std, "%Y-%m-%d%H:%M")

        if service.etd == "On time":
            if std < current_time:
                std += timedelta(1)
            time_delta = std - current_time
            if int(time_delta.total_seconds() / 60 / 5) <= AVAILABLELEDCOUNT - 1:
                parsed_services.append((int(time_delta.total_seconds() / 60 / 5), 4, COLOUR_LOOKUP_TABLE[4]))
            elif int(time_delta.total_seconds() / 60 / 5) > 250:
                parsed_services.append((0, 5, COLOUR_LOOKUP_TABLE[5]))

        elif service.etd == "Delayed":
            if std < current_time:
                std += timedelta(1)
            time_delta = std - current_time
            if int(time_delta.total_seconds() / 60 / 5) <= AVAILABLELEDCOUNT - 1:
                parsed_services.append((int(time_delta.total_seconds() / 60 / 5), 2, COLOUR_LOOKUP_TABLE[2]))
            elif int(time_delta.total_seconds() / 60 / 5) > 250:
                parsed_services.append((0, 5, COLOUR_LOOKUP_TABLE[5]))

        elif service.etd == "Cancelled":
            if std < current_time:
                std += timedelta(1)
            time_delta = std - current_time
            if int(time_delta.total_seconds() / 60 / 5) <= AVAILABLELEDCOUNT - 1:
                parsed_services.append((int(time_delta.total_seconds() / 60 / 5), 1, COLOUR_LOOKUP_TABLE[1]))

        else:
            etd = datetime.strptime(current_ymd + service.etd, "%Y-%m-%d%H:%M")
            if etd < current_time:
                etd += timedelta(1)
            time_delta = etd - current_time
            if int(time_delta.total_seconds() / 60 / 5) <= AVAILABLELEDCOUNT - 1:
                parsed_services.append((int(time_delta.total_seconds() / 60 / 5), 3, COLOUR_LOOKUP_TABLE[3]))
            elif int(time_delta.total_seconds() / 60 / 5) > 250:
                parsed_services.append((0, 5, COLOUR_LOOKUP_TABLE[5]))

    # Dedupe parsed_services to create leds. If one time slot contains more than one
    # train, the "best" LED state is set - White>Green>Yellow>Blue>Red>Black
    for service in parsed_services:
        if service[1] > leds[service[0]]:
            leds[service[0]] = service[1]

    return {
        "DEPARTURE_CRS_CODE": os.environ["DEPARTURE_CRS_CODE"],
        "DESTINATION_CRS_CODE": os.environ["DESTINATION_CRS_CODE"],
        "HumanReadableServices": human_readable_services,
        "ParsedServices": parsed_services,
        "LEDs": leds,
        "RetrievedAt": datetime.now().isoformat(),
    }


def set_blinkt_leds(leds):
    if not GOT_BLINKT:
        return

    for idx, led_to_set in enumerate(leds):
        if led_to_set == 5:
            set_pixel(AVAILABLELEDCOUNT - 1 - idx, 1, 1, 1)
        elif led_to_set == 4:
            set_pixel(AVAILABLELEDCOUNT - 1 - idx, 0, 1, 0)
        elif led_to_set == 3:
            set_pixel(AVAILABLELEDCOUNT - 1 - idx, 1, 1, 0)
        elif led_to_set == 2:
            set_pixel(AVAILABLELEDCOUNT - 1 - idx, 0, 0, 1)
        elif led_to_set == 1:
            set_pixel(AVAILABLELEDCOUNT - 1 - idx, 1, 0, 0)
    set_clear_on_exit(False)
    show()


def run_polling_server(host, port, path):
    class HomeAssistantPollingHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != path:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"Not found"}')
                return

            try:
                data = collect_train_data()
                set_blinkt_leds(data["LEDs"])
                payload = json.dumps(data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (KeyError, ValueError, TimeoutError, ConnectionError, OSError) as ex:
                payload = json.dumps({"error": str(ex)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        def log_message(self, fmt, *args):
            return

    server = HTTPServer((host, port), HomeAssistantPollingHandler)
    print(f"Home Assistant polling endpoint listening on http://{host}:{port}{path}")

    def shutdown_server(*_):
        server.shutdown()

    signal.signal(signal.SIGINT, shutdown_server)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown_server)

    try:
        server.serve_forever()
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Live train notification tool for Raspberry Pi and Blinkt!")
    parser.add_argument("--chatty", action="store_true", help="enable CLI output even if a Blinkt! is detected")
    parser.add_argument(
        "--serve-home-assistant",
        action="store_true",
        help="run an HTTP endpoint so Home Assistant can poll train status",
    )
    parser.add_argument("--host", default="127.0.0.1", help="host for the Home Assistant polling endpoint")
    parser.add_argument("--port", type=int, default=8765, help="port for the Home Assistant polling endpoint")
    parser.add_argument("--path", default="/status", help="path for the Home Assistant polling endpoint")
    args = parser.parse_args()

    if args.serve_home_assistant:
        run_polling_server(args.host, args.port, args.path)
        return

    data_to_output = collect_train_data()
    set_blinkt_leds(data_to_output["LEDs"])

    # Print to CLI if requested or if we don't have a Blinkt!
    if args.chatty or not GOT_BLINKT:
        pprint(data_to_output)


if __name__ == "__main__":
    main()
