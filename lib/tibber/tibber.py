import logging

import requests
import json
from datetime import datetime, timezone, timedelta
import config
from typing import List, Tuple
from influxdb import InfluxDBClient
from lib.logger import Logger
logger = Logger(log_level=logging.DEBUG, log_path="tibber.log")

def datetime_to_influxdb_time(dt_object: datetime) -> str:
    # Function to convert time to InfluxDB format
    # dt_object = datetime.fromisoformat(time_string)
    dt_object_utc = dt_object.astimezone(timezone.utc)
    return dt_object_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def tibber_time_to_datetime(time_string: str)-> datetime:
    # Convert string to datetime object
    dt = datetime.strptime(time_string, '%Y-%m-%dT%H:%M:%S.%f%z')
    # If you want to work with UTC time, you can convert to UTC
    #utc_time = dt - dt.utcoffset()
    return dt

def datetime_to_minutes_after_midnight(dt: datetime)-> int:
    if dt is None:
        return None

    # Return the start time based on 'startsAt'
    minutes_after_midnight = dt.hour * 60 + dt.minute

    return minutes_after_midnight


def fetch_influx_data(bucket: str, measurement: str, time_range: str = '-1h') -> Tuple[List[str], List[float]]:
    """
    Fetches data from an InfluxDB and returns time and value as arrays. fixme untested

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
    client = InfluxDBClient()

    # Execute query
    query = f'from(bucket: "{bucket}") |> range(start: {time_range}) |> filter(fn: (r) => r._measurement == "{measurement}")'
    tables = client.query(query=query)

    # Extract data
    time_array = []
    value_array = []

    for table in tables:
        for record in table.records:
            time_array.append(record.get_time())
            value_array.append(record.get_value())

    # Close connection
    client.close()

    return time_array, value_array


class Tibber:
    def __init__(self, token = None):
        self.prices = None # the current known day ahead prices
        self.prices_ext = None # if the second day is not yet known, the max of the current day is assumed for all day for tomorrow.
        self.price_time = datetime.now()-timedelta(days=2)

        if token is None:
            logger.error("Tibber: no token specified!")
            return
        else:
            self.token = token

        self.update_price_info()


    def update_price_info(self):
        """
        update the prices from the API
        :return: True on success
        """
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

        response = self.post_request(query)

        if response is not None and response.status_code==200:
            # Parse the response
            data = json.loads(response.text)

            # Extract current and tomorrow's price
            try:
                current_price = data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']['current']['total']
            except (KeyError, IndexError) as e:
                current_price = None
                logger.error(f"No current price exception {e}")
                self.prices = None
                self.price_time = datetime.now() - timedelta(days=2)  # old!!
                return False

            try:
                prices_today = data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']['today']
            except (KeyError, IndexError) as e:
                current_price = None
                logger.error(f"No prices today exception {e}")
                self.prices = None
                self.price_time = datetime.now() - timedelta(days=2)  # old!!
                return False

            try:
                prices_tomorrow = data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']['tomorrow']
            except (KeyError, IndexError) as e:
                current_price = None
                logger.error(f"No prices tomorrow exception {e}")
                self.prices = None
                self.price_time = datetime.now() - timedelta(days=2)  # old!!
                return False

            '''print(f"Current Price: {current_price}")
            
                        # Loop through and display tomorrow's prices
                        print("Today's Prices:")
                        for price in prices_today:
                            dt = tibber_time_to_datetime(price['startsAt'])
                            print(f"Starts At: {dt}, Total: {price['total']}")
            
                        print("Tomorrow's Prices:")
                        for price in prices_tomorrow:
                            dt = tibber_time_to_datetime(price['startsAt'])
                            print(f"Starts At: {dt}, Total: {price['total']}")'''

            # If prices for tomorrow are None, replace them with today's maximum prices
            if prices_tomorrow is None or prices_tomorrow == []:
                self.prices = prices_today
                max_today_price = max([hour_data['total'] for hour_data in prices_today])
                prices_tomorrow = [
                    {
                        'level': 'EXPENSIVE',
                        'total': max_today_price,
                        'startsAt': (datetime.fromisoformat(prices_today[-1]['startsAt']) + timedelta(hours=i + 1)).strftime("%Y-%m-%dT%H:%M:%S.%f%z")
                    } for i in range(24)
                ]
            else:
                self.prices = prices_today + prices_tomorrow

            self.prices_ext = prices_today + prices_tomorrow  # extended prizes contain unknown high prizes to get a result for optimum.
            self.price_time = datetime.now()
            return True
        else:
            self.prices = None
            self.price_time = datetime.now()-timedelta(days=2) # old!!
            return False


    def post_request(self, query):
        # Create the header
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        response = None # pre-fill in the case of exception

        # Make the API request
        try:
            response = requests.post(
                'https://api.tibber.com/v1-beta/gql',
                headers=headers,
                json={'query': query},
                timeout=20
            )
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err}")
        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f"Connection error occurred: {conn_err}")
        except requests.exceptions.Timeout as timeout_err:
            logger.error(f"Timeout error occurred: {timeout_err}")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request exception occurred: {req_err}")

        return response


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

        response = self.post_request(mutation)
        if response is not None:
            # Parse and return the response
            data = json.loads(response.text)
            return data['data']['sendPushNotification']
        else:
            return None


    def cheapest_charging_time(self, _current_soc, _target_soc, capacity_kWh=77, max_power_kW=11):
        # refresh price info when old.
        if datetime.now()-self.price_time > timedelta(hours=6):
            self.update_price_info()

        target_hour = 8  #todo parameter
        latest_end = (datetime.now(timezone.utc).replace(hour=target_hour, minute=0, second=0, microsecond=0) + timedelta(days=(datetime.now().hour >= target_hour)))

        new_dict = {}
        current_time = datetime.now(timezone.utc) # Make current_time offset-aware
        current_hour_start = current_time.replace(minute=0, second=0, microsecond=0)
        for data in self.prices_ext:  # use the extended list (highest prize from today extrapolated to tomorrow, if not known yet.
            time_string = data['startsAt']
            value = data['total']
            dt = tibber_time_to_datetime(time_string) # Convert time string to datetime
            if dt >= current_hour_start:
                new_dict[dt] = value # Use the datetime as the key in the new dictionary

        # Calculate required energy to charge to 100%
        required_kWh = (_target_soc - _current_soc) / 100 * capacity_kWh * 1.05

        # Calculate number of hours required to charge
        hours_required = required_kWh / max_power_kW
        logger.info(f"need to charge {required_kWh} kWh in {hours_required} h")
        charging_time_interval = timedelta(hours=hours_required)

        # Find starting time for cheapest charge
        min_interval_sum = float('inf')  # set to positive infinity initially
        min_interval_start = None

        sorted_keys = sorted(new_dict.keys())

        # Iterate through the sorted keys of the dictionary
        for i, start_time in enumerate(sorted_keys):
            end_time = start_time + charging_time_interval

            # Check if end time exceeds the maximum time in the dictionary
            if i == len(sorted_keys) - 1 or end_time > sorted_keys[-1]:
                logger.info(f"Amount of remaining time shards not sufficient: Last time interval: {sorted_keys[-1]}")
                break  # Stop if the remaining time intervals are not sufficient

            # Check, if charging after next morning
            if end_time > latest_end:
                logger.info(f"Charging would not be finished until {target_hour} h - end: {end_time} latest:{latest_end} if next line found a time, there is no issue")
                break  # Stop if end would be too late

            # Sum values within the time interval
            interval_sum = sum(value for time, value in new_dict.items() if start_time <= time < end_time)

            # Update minimal interval information if the sum is smaller
            if interval_sum < min_interval_sum:
                min_interval_sum = interval_sum
                min_interval_start = start_time

        if min_interval_start is None:
            logger.error("No interval could be found")
        else:
            logger.info(f"Start time of the minimal interval: {min_interval_start}")

        return min_interval_start



    def get_price(self):
        current_datetime = datetime.now()
        # Find the price for the current hour
        current_price = None
        for item in self.prices:
            item_dt = tibber_time_to_datetime(item['startsAt'])
            if item_dt.hour == current_datetime.hour and item_dt.date() == current_datetime.date():
                current_price = item['total']
                break
        return current_price


if __name__ == '__main__':

    tb = Tibber(config.tibber_api_token)
    #tb.get_price_info()

    # Test
    current_charge_percent = 39

    _start_time = tb.cheapest_charging_time(current_charge_percent, 80)
    print(f"Best time to start charging is: {datetime_to_minutes_after_midnight(_start_time)} min after midnight")

    print(tb.get_price())

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


'''
hourly consumption:
{
  viewer {
    homes {
      consumption(resolution: HOURLY, last: 100) {
        nodes {
          from
          to
          cost
          unitPrice
          unitPriceVAT
          consumption
          consumptionUnit
        }
      }
    }
  }
}

result:
{
  "data": {
    "viewer": {
      "homes": [
        {
          "consumption": {
            "nodes": [
              {
                "from": "2023-12-01T00:00:00.000+01:00",
                "cost": 0.0663327063,
                "consumption": 0.243,
                "consumptionUnit": "kWh"
              },
              {
                "from": "2023-12-01T01:00:00.000+01:00",
                "cost": 3.0795588264,
                "consumption": 11.496,
                "consumptionUnit": "kWh"
              },
              ...

'''
