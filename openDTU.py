# openDTU client
# polling the info

import requests
from lib.measurementlist import MeasurementList
from lib.logger import Logger
logger = Logger()

def access_nested_dict(data, keys):
    try:
        value = data
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        # Handle cases where keys are not found or the structure is not a dictionary
        return None

class OpenDTU:
    def __init__(self, _ip_address):
        self.ip_address = _ip_address
        self.dat = MeasurementList()
        self.dat.add_item(name="HOY Garage N Power",unit="W",send_min_diff=2, filter_time=60,filter_jump=1000,source=("112183227643","AC","0","Power","v"),filter_std_time=0)
        self.dat.add_item(name="HOY Garage N Temp", unit="°C", send_min_diff=0.5, filter_time=60, filter_jump=1000, source=("112183227643", "INV","0","Temperature","v"), filter_std_time=0)
        self.dat.add_item(name="HOY Garage N Volt", unit="V", send_min_diff=0.5, filter_time=60, filter_jump=1000, source=("112183227643", "DC", "0", "Voltage", "v"), filter_std_time=0)
        self.dat.add_item(name="HOY Garage N Curr", unit="A", send_min_diff=0.1,filter_time=60, filter_jump=1000, source=("112183227643", "DC", "0", "Current", "v"), filter_std_time=0)

        self.dat.add_item(name="HOY Garage S Power", unit="W", send_min_diff=2, filter_time=60, filter_jump=1000, source=("112183213297", "AC", "0", "Power", "v"), filter_std_time=0)
        self.dat.add_item(name="HOY Garage S Temp", unit="°C", send_min_diff=0.5, filter_time=60, filter_jump=1000, source=("112183213297", "INV","0","Temperature","v"), filter_std_time=0)
        self.dat.add_item(name="HOY Garage S Volt", unit="V", send_min_diff=0.5, filter_time=60, filter_jump=1000, source=("112183213297", "DC", "0", "Voltage", "v"), filter_std_time=0)
        self.dat.add_item(name="HOY Garage S Curr", unit="A", send_min_diff=0.1, filter_time=60, filter_jump=1000, source=("112183213297", "DC", "0", "Current", "v"), filter_std_time=0)

    def update(self):
        url = f"http://{self.ip_address}/api/livedata/status"

        # some brain decided, that every converter must be polled individually. /api/livedata/status?inv=inverter-serialnumber
        try:
            # Send a GET request to the URL
            response = requests.get(url, timeout= 5)

            # Check if the request was successful (status code 200)
            if response.status_code == 200:
                # Parse the JSON response as a dictionary
                data = response.json()
                #logger.log("JSON Response:")
                #logger.log(data)
                if data is None:
                    logger.log("DTU response is none")
                    return
            else:
                logger.log(f"DTU Failed to retrieve data. Status code: {response.status_code}")
                response = None
                return
        except requests.exceptions.RequestException as e:
            logger.log(f"DTU Request error: {e}")
            return
        except ValueError as e:
            logger.log(f"DTU JSON decoding error: {e}")
            return

        # get the data for each inverter and hack them into the tree.
        inverters = data["inverters"]
        inverters_all = inverters
        for inverter in inverters:
            invser = inverter.get("serial")
            response = requests.get(url + "?inv=" + invser, timeout=5)
            data = response.json()
            # merge data into original tree

            for i, da in enumerate(inverters_all):
                if da["serial"] == inverter["serial"]:
                    inverters_all[i] = data["inverters"][0].copy()

        # and now check for the values
        for item in self.dat.get_name_list():
            ser = self.dat.get_source(item)[0]
            keys = self.dat.get_source(item)[1:]
            for inverter in inverters_all:
                if inverter["reachable"] == True and ser == inverter["serial"]:
                    nd = access_nested_dict(inverter,keys)
                    self.dat.update_value(item,nd)

        self.dat.write_measurements()

if __name__ == "__main__":
    # Example usage:
    dtu = OpenDTU("192.168.1.69")
    dtu.update()

