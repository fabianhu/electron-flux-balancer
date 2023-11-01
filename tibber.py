import requests
import json
from datetime import datetime, timezone, timedelta
from config import tibber_api_token
from typing import List, Tuple
#from influxdb_client import InfluxDBClient

def to_influxdb_time(time_string):
    # Function to convert time to InfluxDB format
    dt_object = datetime.fromisoformat(time_string)
    dt_object_utc = dt_object.astimezone(timezone.utc)
    return dt_object_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


class Tibber:
    def __init__(self, token = None):
        if token is None:
            self.token = "5K4MVS-OjfWhK_4yrjOlFe1F6kJXPVf7eQYggo8ebAE" # sample token fromm tibber
        else:
            self.token = token

        self.prizeinfo = (0, 0)

    def get_priceInfo(self):
        # Define the GraphQL query for fetching current and tomorrow's energy price
        query = """
        {
          viewer {
            homes {
              currentSubscription {
                priceInfo {
                  current {
                    total
                    startsAt
                  }
                  today {
                    total
                    startsAt
                    level
                  }
                  tomorrow {
                    total
                    startsAt
                    level
                  }
                }
              }
            }
          }
        }
        """

        # Create the header
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

        # Make the API request
        response = requests.post(
            'https://api.tibber.com/v1-beta/gql',
            headers=headers,
            json={'query': query}
        )

        # Parse the response
        data = json.loads(response.text)

        # Extract current and tomorrow's price
        current_price = data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']['current']['total']
        today_prices = data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']['today']
        tomorrow_prices = data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']['tomorrow']

        print(f"Current Price: {current_price}")
        print(tomorrow_prices)

        # Loop through and display tomorrow's prices with InfluxDB-formatted timestamps
        print("Tomorrow's Prices:")
        for price in tomorrow_prices:
            influxdb_time = to_influxdb_time(price['startsAt'])
            print(f"Starts At: {influxdb_time}, Total: {price['total']}")

        print("Today's Prices:")
        for price in today_prices:
            influxdb_time = to_influxdb_time(price['startsAt'])
            print(f"Starts At: {influxdb_time}, Total: {price['total']}")


    def send_push_notification(self, title, message, screen_to_open):
        # Define the GraphQL mutation
        mutation = f"""
        mutation {{
          sendPushNotification(input: {{
            title: "{title}",
            message: "{message}",
            screenToOpen: {screen_to_open}
          }}){{
            successful
            pushedToNumberOfDevices
          }}
        }}
        """

        # Create headers
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

        # Make the API request
        response = requests.post(
            'https://api.tibber.com/v1-beta/gql',
            headers=headers,
            json={'query': mutation}
        )

        # Parse and return the response
        data = json.loads(response.text)
        return data['data']['sendPushNotification']




    def fetch_influx_data(self, bucket: str, org: str, token: str, url: str, measurement: str, time_range: str = '-1h') -> Tuple[List[str], List[float]]:
        """
        Fetches data from an InfluxDB and returns time and value as arrays.

        Parameters:
        - bucket: Name of the bucket
        - org: Name of the organization
        - token: Access token
        - url: URL of the InfluxDB
        - measurement: Name of the measurement
        - time_range: Time range (default is '-1h', i.e., last hour)

        Returns:
        - Tuple of two lists: Time and Value
        """

        # Establish connection
        client = InfluxDBClient(url=url, token=token)

        # Execute query
        query = f'from(bucket: "{bucket}") |> range(start: {time_range}) |> filter(fn: (r) => r._measurement == "{measurement}")'
        tables = client.query_api().query(org=org, query=query)

        # Extract data
        time_array = []
        value_array = []

        for table in tables:
            for record in table.records:
                time_array.append(record.get_time())
                value_array.append(record.get_value())

        # Close connection
        client.__del__()

        return time_array, value_array


tb = Tibber(tibber_api_token)
tb.get_priceInfo()
'''
result = tb.send_push_notification("Titelzeile", "Nachricht, keinen Plan, wie lang die sein kann.", "HOME")
print(f"Successful: {result['successful']}")
print(f"Pushed to Number of Devices: {result['pushedToNumberOfDevices']}")


bucket = "your_bucket_name"
org = "your_org_name"
token = "your_access_token"
url = "http://localhost:8086"
measurement = "your_measurement_name"
time_range = "-1h"  # Optional; defaults to the last hour

# Fetch data
time_array, value_array = fetch_influx_data(bucket, org, token, url, measurement, time_range)

# Output the results
print("Time Array:", time_array)
print("Value Array:", value_array)

'''
