"""
This is using the NEW 2024 Tesla API.
"""
import logging

import config
from lib.measurementlist import MeasurementList
import datetime
import json
import math
import time
from lib.logger import Logger
logger = Logger(logging.DEBUG, "tesla.log")

from config import home

from lib.tesla_api import tesla_api_2024

logToFile = False
APIVERSION = 73


# extract the value from a multi index
def get_item(_dict, _indices):
    value = _dict.copy()  # initialize with whole dict as a COPY because it will be cut down!
    for i in _indices:
        if i in value:
            value = value[i]  # prune the tree to the last element. Ends with last index
        else:
            # logger.info(f"index {i} not found in {value}")  # this is normal for e.g. "drive_state"
            return None
    return value


def calculate_distance(lat1, lon1, lat2, lon2):
    # Earth's radius in kilometers
    earth_radius = 6371

    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius * c


class TeslaCar:
    def __init__(self, _vin, _api: tesla_api_2024.TeslaAPI):
        self.vin = _vin
        self.tesla_api = _api

        ### stuff to remember from last input for "is_ready"
        self.last_distance = 0 # ok
        self.CAR_charger_real_phases = 3 # kept in because numbering is different!! this here is real phases!
        self.is_charging = False # ok # raus

        self.car_db_data = MeasurementList()
        self.car_data_cache = None

        # configure database channels
        self.car_db_data.add_item(name="CAR_state", unit="", filter_jump=1, send_min_diff=1)  # manually, because there is no source array in sleep!
        self.car_db_data.add_item(name="CAR_battery_level", source=('charge_state', 'battery_level'), unit="%", filter_jump=3, send_min_diff=1)
        self.car_db_data.add_item(name="CAR_usable_battery_level", source=('charge_state', 'usable_battery_level'), unit="%", filter_jump=3, send_min_diff=1)
        self.car_db_data.add_item(name="CAR_charge_amps", source=('charge_state', 'charge_amps'), unit="A", filter_jump=1, send_min_diff=1)
        self.car_db_data.add_item(name="CAR_charger_actual_current", source=('charge_state', 'charger_actual_current'), unit="A", filter_jump=1, send_min_diff=1)
        self.car_db_data.add_item(name="CAR_charge_current_request", source=('charge_state', 'charge_current_request'), unit="A", filter_jump=1, send_min_diff=1)
        self.car_db_data.add_item(name="CAR_charge_limit_soc", source=('charge_state', 'charge_limit_soc'), unit="%", filter_jump=1, send_min_diff=1)
        self.car_db_data.add_item(name="CAR_charger_phases", source=('charge_state', 'charger_phases'), unit="n", filter_jump=1, send_min_diff=1)  # can be '0' while not charging and is '2' at three-phase charge!
        self.car_db_data.add_item(name="CAR_charger_power", source=('charge_state', 'charger_power'), unit="kW", filter_jump=1, send_min_diff=1)
        self.car_db_data.add_item(name="CAR_charger_voltage", source=('charge_state', 'charger_voltage'), unit="V", filter_jump=5, send_min_diff=1)
        self.car_db_data.add_item(name="CAR_charging_state", source=('charge_state', 'charging_state'), unit="")  # can be 'Disconnected', 'Charging', 'Stopped', 'Complete', 'Starting'
        self.car_db_data.add_item(name="CAR_minutes_to_full_charge", source=('charge_state', 'minutes_to_full_charge'), unit="min")
        self.car_db_data.add_item(name="CAR_time_to_full_charge", source=('charge_state', 'time_to_full_charge'), unit="h")  # h
        self.car_db_data.add_item(name="CAR_inside_temp", source=('climate_state', 'inside_temp'), unit="°C", filter_jump=1, send_min_diff=0.5)
        self.car_db_data.add_item(name="CAR_outside_temp", source=('climate_state', 'outside_temp'), unit="°C")
        self.car_db_data.add_item(name="CAR_latitude", source=('drive_state', 'latitude'), unit="°")
        self.car_db_data.add_item(name="CAR_longitude", source=('drive_state', 'longitude'), unit="°")

        self.car_db_data.add_item(name="CAR_tpms_pressure_fl", source=('vehicle_state', 'tpms_pressure_fl'), unit="bar", filter_jump=0.1, send_min_diff=0.1)
        self.car_db_data.add_item(name="CAR_tpms_pressure_fr", source=('vehicle_state', 'tpms_pressure_fr'), unit="bar", filter_jump=0.1, send_min_diff=0.1)
        self.car_db_data.add_item(name="CAR_tpms_pressure_rl", source=('vehicle_state', 'tpms_pressure_rl'), unit="bar", filter_jump=0.1, send_min_diff=0.1)
        self.car_db_data.add_item(name="CAR_tpms_pressure_rr", source=('vehicle_state', 'tpms_pressure_rr'), unit="bar", filter_jump=0.1, send_min_diff=0.1)

        self.car_db_data.add_item(name="CAR_distance", unit="km")
        self.car_db_data.add_item(name="CAR_charge_W", unit="W")
        self.car_db_data.add_item(name="CAR_seen_ago", unit="s")



    def get_car_life_data(self):
        r = self.tesla_api.get_vehicle_data(self.vin, 'charge_state;drive_state;location_data;vehicle_state;climate_state')  # requests LIVE data only -> None if asleep!
        if r is  None:
            if self.car_data_cache is not None:
                self.car_data_cache['state']="asleep" # fake the state
            self.refresh(self.car_data_cache) # refresh with cached data, just because.
        else:
            self.car_data_cache = r
            self.refresh(r)


    def refresh(self, _my_car_data=None):

        if _my_car_data is None:
            return
        api = _my_car_data["api_version"]
        if logToFile or api != APIVERSION:  # check API version and dump when necessary.
            file_name = f"API{api}_{_my_car_data['vin']}_{datetime.datetime.now().isoformat()[:-7].replace(':', '-').replace('T', '_')}.txt"
            with open(file_name, "w") as file:
                json.dump(_my_car_data, file, indent=4)

            logger.error(f"Tesla API version {api}")

        # update hand-calculated values
        self.car_db_data.update_value('CAR_state', _my_car_data['state'])

        if (_my_car_data['charge_state']['charging_state'] == 'Charging' or _my_car_data['charge_state']['charging_state'] == 'Starting') and \
                _my_car_data['charge_state']['charger_actual_current'] is not None and \
                _my_car_data['charge_state']['charger_voltage'] is not None:
            self.is_charging = True
            # this is 3 phase charging
            if _my_car_data['charge_state']['charger_phases'] == 2:
                charge_actual_W = _my_car_data['charge_state']['charger_actual_current'] * _my_car_data['charge_state']['charger_voltage'] * 3
                self.CAR_charger_real_phases = 3
            elif _my_car_data['charge_state']['charger_phases'] == 1:
                charge_actual_W = _my_car_data['charge_state']['charger_actual_current'] * _my_car_data['charge_state']['charger_voltage']
                self.CAR_charger_real_phases = 1
            else:
                logger.error(f"Phases are hard, {_my_car_data['charge_state']['charger_phases']}")
                charge_actual_W = 0
        else:
            self.is_charging = False
            charge_actual_W = 0
            #logger.debug("not charging - no Watts")

        self.car_db_data.update_value("CAR_charge_W", charge_actual_W)

        if "drive_state" in _my_car_data:
            if "latitude" in _my_car_data["drive_state"]:
                loc = (_my_car_data["drive_state"]["latitude"], _my_car_data["drive_state"]["longitude"])
                self.last_distance = calculate_distance(home[0], home[1], loc[0], loc[1])
                #last_distance_time = _my_car_data['drive_state']['timestamp'] / 1000
                # logger.log(f"The distance between the coordinates is {self.last_distance:.2f} km.")
                self.car_db_data.update_value("CAR_distance", self.last_distance)

        last_seen_s = time.time() - _my_car_data['charge_state']['timestamp'] / 1000
        self.car_db_data.update_value("CAR_seen_ago", last_seen_s)

        # update all values with a pre-defined source
        for i in self.car_db_data.get_name_list():
            s = self.car_db_data.get_source(i)
            if s is not None:
                # print(s)
                v = get_item(_my_car_data, s)
                if v is not None:  # do not update None values as this is completely normal for e.g. "drive_state" to not be in the data
                    self.car_db_data.update_value(i, v)
                    # logger.debug(f"Updated item: {i}, Source {s}, Value: {v}")
                else:
                    logger.debug(f"Missing item: {i}, Source {s}")
            else:
                pass
                # logger.debug(f"Skipped item: {i}")

        self.car_db_data.write_measurements()

        return _my_car_data



    def is_here_and_connected(self):  # check, if car is ready according last data - without asking!
        # Car is not here
        if self.last_distance > 0.3:
            logger.debug(f"Tesla is {self.last_distance}km away")
            return False

        if self.car_data_cache is None or not 'charge_state' in self.car_data_cache:
            logger.debug("Tesla no info")
            return False

        # check car state
        if not self.car_data_cache['charge_state']['conn_charge_cable'] == 'IEC':
            logger.debug("Tesla is not connected")
            return False

        if not self.car_data_cache['charge_state']['charging_state'] in ['Charging', 'Stopped']:  # not 'Complete'
            logger.debug("Tesla is connected, but not in right mood")
            return False
        return True


    def set_charge(self, _do_charge, _req_amps):
        if not self.is_here_and_connected():
            logger.warning("Tesla is not ready, but should be!")
            return False

        if self.car_data_cache['state'] == "asleep" and _do_charge and _req_amps > 0:
            logger.info("Tesla - Wake up car, cos I want to charge")
            self.tesla_api.cmd_wakeup(self.vin)
            #leave here and set the commanded value later - so we will have a re-entry.
            return

        maxamps = self.car_data_cache['charge_state']['charge_current_request_max']
        if _req_amps > maxamps:
            logger.error(f"Tesla: prevent to charge more than {maxamps} A. - {_req_amps} A requested.")
            _req_amps = maxamps

        ampere_rounded = round(_req_amps, 0)

        if ampere_rounded < 1:
            _do_charge = False

            # charge_state can be 'Disconnected', 'Charging', 'Stopped', 'Complete', 'Starting'
        if self.car_data_cache['charge_state']['charging_state'] == 'Charging' and not _do_charge:
            logger.info(f"charging stopped at {self.car_data_cache['charge_state']['charger_actual_current']} A")
            try:
                r = self.tesla_api.cmd_charge_stop(self.vin)
                if r:
                    logger.debug("car charging stopped")
                    self.car_data_cache['charge_state']['charging_state'] = 'Stopped'  # remember / fake the state!
                    self.refresh(self.car_data_cache)  # publish again
                    self.tesla_api.cmd_charge_set_amps(self.vin, 5) # reset to lowest "legal" value to be starting low at next start.
            except Exception as e:
                logger.error(f"Exception during stopping charge {type(e)}: {e}")

            return True  # finished here, as all else is related to setting the current

        req_power_w = _req_amps * self.CAR_charger_real_phases * 230
        if req_power_w > 11000:
            logger.error(f"WATT is wrong with you, {req_power_w} W")
            return False

        if self.car_data_cache['charge_state']['charging_state'] == 'Stopped' and _do_charge:
            try:
                r = self.tesla_api.cmd_charge_start(self.vin)
                if r:
                    logger.debug("car charging started")
                    self.car_data_cache['charge_state']['charging_state'] = 'Starting'  # remember / fake the state!
                    self.refresh(self.car_data_cache)  # publish again
            except Exception as e:
                logger.error(f'Exception during starting charge {type(e)}: {e}')


        if not (self.car_data_cache['charge_state']['charging_state'] == 'Charging' or self.car_data_cache['charge_state']['charging_state'] == 'Starting'):
            # ampere_rounded = 5
            # logger.info(f"Car is not charging and we set the amps to {ampere_rounded}")
            return False

        if ampere_rounded > 15:
            logger.log(f"too many amps requested, {ampere_rounded}")
            return False

        if self.car_data_cache['charge_state']['charge_current_request'] != ampere_rounded:  # only send, if different
            try:
                r = self.tesla_api.cmd_charge_set_amps(self.vin, int(ampere_rounded))
                if r is True:
                    # if successful, we update the self.car_data_cache['charge_state']['charge_current_request']
                    # so we do not have to read it back.
                    self.car_data_cache['charge_state']['charge_current_request'] = int(ampere_rounded)
                    return True

            except Exception as e:
                logger.log(f"Exception during changing charge request {type(e)}: {e}")

            return False
        else:
            logger.debug(f"Charge current ok, {ampere_rounded}")
            return True


# test stuff, if run directly


if __name__ == '__main__':

    myTeslaAPI = tesla_api_2024.TeslaAPI()

    myTesla = TeslaCar(config.tesla_vin, myTeslaAPI)

    time.sleep(1)

    myTesla.get_car_life_data()

    time.sleep(15)

    myTesla.get_car_life_data()

    # myTesla.set_charge(False, 1230)

'''
'''
