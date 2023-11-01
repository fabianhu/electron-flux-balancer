from datetime import datetime, timedelta
from influxdb import InfluxDBClient
import pytz  # Import the pytz library

# Initialize InfluxDB client
client = InfluxDBClient(host='127.0.0.1', port=8086, database='home')

# Define the time zone
local_tz = pytz.timezone('Europe/Berlin')  # Replace with your local time zone

# Define the time frame
day_start = local_tz.localize(datetime(2023, 8, 1))  # Make the datetime object timezone-aware
day_end = local_tz.localize(datetime(2023, 10, 11))  # Make the datetime object timezone-aware

# Initialize time delta for 1 hour
one_hour = timedelta(hours=1)

# Initialize current time to the start of the day
current_time = day_start

# Loop over each hour in the time range
while current_time < day_end:
    # Convert the hour to float
    if current_time.hour == 0:  # If it's midnight, use 24
        float_hour = 24.0
    else:
        float_hour = float(current_time.hour)

    # Create a new data point
    data_point = {
        "measurement": "Pi Time of Day",
        "time": current_time.astimezone(pytz.utc).isoformat(),  # Convert to UTC time for InfluxDB
        "fields": {
            "value": float_hour
        }
    }

    # Write the data point to the InfluxDB database
    client.write_points([data_point])

    print(f"Data written for {current_time}: {float_hour}")

    # Increment the current time by 1 hour
    current_time += one_hour
