import logging

import pytz

from lib.measurementlist import MeasurementList
from lib.logger import Logger
logger = Logger(log_level=logging.DEBUG, log_path="ai_edge.log")
import requests
import time
import imagelogger
from config import tasmota_ips, tasmota_meter_ip
from datetime import datetime, timedelta, timezone

def get_ai_edge_data(server_url):
    try:
        response = requests.get(server_url,timeout=5)
        data = response.json()

        # Accessing data from the JSON response
        main_data = data.get("main", {})
        value = main_data.get("value")
        error = main_data.get("error")
        timestamp_str = main_data.get("timestamp")

        # Convert timestamp string to datetime object
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S%z')

        # Compare timestamp with current time
        current_time = datetime.now(timezone.utc)
        time_diff = current_time - timestamp

        if error != "no error":
            logger.error(f"AI edge error {server_url}: {error}")
            return None

        # Reject value if timestamp is older than 5 minutes
        if time_diff > timedelta(minutes=5):
            logger.error(f"AI edge error {server_url}: Timestamp {timestamp_str} older than 5 minutes now:{current_time}. Rejecting value {value}.")
            return None
        return float(value)
    except ValueError:
        logger.error(f"Value error {server_url}: {value} at {timestamp_str}")
        return None

    except requests.exceptions.RequestException as e:
        logger.error(f"AI edge error {server_url}: Error making request to {server_url} {e}")
        return None



class AiEdge:
    def __init__(self):
        logger.info("Start AI on the edge client")

        # AI on the edge
        self.aidat = MeasurementList()
        self.aidat.add_item("Water volume", source="http://192.168.1.97/json", send_min_diff=0.01, filter_jump=100)
        self.aidat.add_item("Gas volume", source="http://192.168.1.96/json", send_min_diff=0.01, filter_jump=100)


    def update(self):
        for i in list(self.aidat.get_name_list()):
            # print(i)
            v = get_ai_edge_data(self.aidat.get_source(i))
            self.aidat.update_value(i,v)
        self.aidat.write_measurements()



# test stuff
if __name__ == '__main__':

    ts = AiEdge()

    #ts.update_sml()
    #time.sleep(3)
    #ts.update(0)

    ts.update()

