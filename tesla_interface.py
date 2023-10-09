import teslapy
import database
import datetime
import json
import math
import time
from logger import logger

from config import home
from config import tesla_login

import requests.exceptions

# install
# pip install requests_oauthlib
# pip install websocket

logToFile = False


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


class Car:
    def __init__(self, _tesla_login):
        self.login = _tesla_login

        self.last_seen_s = None  # check, how precise we know the state (age)

        ### stuff to remember from last input for "is_ready"
        self.last_distance = 0
        self.last_distance_time = 0
        self.is_ready_to_charge = False
        self.current_request = 0
        self.current_actual = 0
        self.is_charging = False
        self.charge_actual_W = 0.0
        self.charger_allowed_max_W = 0.0

        self.cardata = database.MeasurementList()

        _myCar = self.get_car_data()
        if _myCar is None:
            logger.log("Tesla connect failed")
            return

        logger.log(f"Tesla: {_myCar['display_name']} last seen {_myCar.last_seen()} at {str(_myCar['charge_state']['battery_level'])} % SoC with API {_myCar['api_version']}")
        logger.info(f"Tesla: {_myCar['display_name']} last seen {_myCar.last_seen()} at {str(_myCar['charge_state']['battery_level'])} % SoC with API {_myCar['api_version']}")
        print(f"Tesla: {_myCar['display_name']} last seen {_myCar.last_seen()} at {str(_myCar['charge_state']['battery_level'])} % SoC with API {_myCar['api_version']}")

        if logToFile:
            file_name = f"{_myCar['display_name']}_{datetime.datetime.now().isoformat()[:-7].replace(':', '-').replace('T', '_')}.txt"

            with open(file_name, "w") as file:
                json.dump(_myCar, file, indent=4)

        # configure database channels
        self.cardata.add_item(name="CAR_state", unit="", filter_jump=1, send_min_diff=1)  # refresh manually, because there would be no source array!
        self.cardata.add_item(name="CAR_battery_level", source=('charge_state', 'battery_level'), unit="%", filter_jump=3, send_min_diff=1)
        self.cardata.add_item(name="CAR_usable_battery_level", source=('charge_state', 'usable_battery_level'), unit="%", filter_jump=3, send_min_diff=1)
        self.cardata.add_item(name="CAR_charge_amps", source=('charge_state', 'charge_amps'), unit="A", filter_jump=1, send_min_diff=1)
        self.cardata.add_item(name="CAR_charger_actual_current", source=('charge_state', 'charger_actual_current'), unit="A", filter_jump=1, send_min_diff=1)
        self.cardata.add_item(name="CAR_charge_current_request", source=('charge_state', 'charge_current_request'), unit="A", filter_jump=1, send_min_diff=1)
        self.cardata.add_item(name="CAR_charge_limit_soc", source=('charge_state', 'charge_limit_soc'), unit="%", filter_jump=1, send_min_diff=1)
        self.cardata.add_item(name="CAR_charger_phases", source=('charge_state', 'charger_phases'), unit="n", filter_jump=1, send_min_diff=1)
        self.cardata.add_item(name="CAR_charger_power", source=('charge_state', 'charger_power'), unit="W", filter_jump=100, send_min_diff=100)
        self.cardata.add_item(name="CAR_charger_voltage", source=('charge_state', 'charger_voltage'), unit="V", filter_jump=5, send_min_diff=1)
        self.cardata.add_item(name="CAR_charging_state", source=('charge_state', 'charging_state'), unit="")  # can be 'Disconnected', 'Charging', 'Stopped', 'Complete', 'Starting'
        self.cardata.add_item(name="CAR_minutes_to_full_charge", source=('charge_state', 'minutes_to_full_charge'), unit="min")
        self.cardata.add_item(name="CAR_time_to_full_charge", source=('charge_state', 'time_to_full_charge'), unit="h")  # h
        self.cardata.add_item(name="CAR_inside_temp", source=('climate_state', 'inside_temp'), unit="°C", filter_jump=1, send_min_diff=0.5)
        self.cardata.add_item(name="CAR_outside_temp", source=('climate_state', 'outside_temp'), unit="°C")
        self.cardata.add_item(name="CAR_latitude", source=('drive_state', 'latitude'), unit="°")
        self.cardata.add_item(name="CAR_longitude", source=('drive_state', 'longitude'), unit="°")

        self.cardata.add_item(name="CAR_tpms_pressure_fl", source=('vehicle_state', 'tpms_pressure_fl'), unit="bar", filter_jump=0.1, send_min_diff=0.1)
        self.cardata.add_item(name="CAR_tpms_pressure_fr", source=('vehicle_state', 'tpms_pressure_fr'), unit="bar", filter_jump=0.1, send_min_diff=0.1)
        self.cardata.add_item(name="CAR_tpms_pressure_rl", source=('vehicle_state', 'tpms_pressure_rl'), unit="bar", filter_jump=0.1, send_min_diff=0.1)
        self.cardata.add_item(name="CAR_tpms_pressure_rr", source=('vehicle_state', 'tpms_pressure_rr'), unit="bar", filter_jump=0.1, send_min_diff=0.1)

        self.cardata.add_item(name="CAR_distance", unit="km")
        self.cardata.add_item(name="CAR_charge_W", unit="W")
        self.cardata.add_item(name="CAR_seen_ago", unit="s")

        self.refresh(_myCar)  # write all initial data into

    def get_car_data(self):
        try:
            tesla = teslapy.Tesla(self.login)
            vehicles = tesla.vehicle_list()  # asks over API for the list
            _myCar = vehicles[0]
            _myCar.get_vehicle_data()  # inserted
        except ConnectionError as _e:
            logger.log("Tesla ConnectionError", _e)
            return None
        except requests.exceptions.HTTPError as _e:
            logger.log("Tesla HTTPError", _e)
            return None
        except requests.exceptions.ConnectionError as _e:
            logger.log("Tesla Connection Error", _e)
            return None
        except requests.exceptions.ReadTimeout as _e:
            logger.log("Tesla Timeout", _e)
            return None

        if _myCar['api_version'] != 63:
            logger.log("Wrong Tesla API version!")  # fixme send mail
            file_name = f"API{_myCar['api_version']}_{_myCar['display_name']}_{datetime.datetime.now().isoformat()[:-7].replace(':', '-').replace('T', '_')}.txt"

            with open(file_name, "w") as file:
                json.dump(_myCar, file, indent=4)

            return None # instead of exception

        return _myCar

    def refresh(self, _myCar=None):
        if _myCar is None:
            _myCar = self.get_car_data()

        if _myCar is None:
            logger.log("Tesla connect failed")
            return None

        # logger.info("read: " + _myCar['display_name'] + ' last seen ' + _myCar.last_seen() + ' at ' + str(_myCar['charge_state']['battery_level']) + '% SoC')

        if logToFile:
            file_name = f"{_myCar['display_name']}_{datetime.datetime.now().isoformat()[:-7].replace(':', '-').replace('T', '_')}.txt"
            with open(file_name, "w") as file:
                json.dump(_myCar, file, indent=4)

        # update hand-calculated values
        self.cardata.update_value('CAR_state', _myCar['state'])

        if (_myCar['charge_state']['charging_state'] == 'Charging' or _myCar['charge_state']['charging_state'] == 'Starting') and \
                _myCar['charge_state']['charger_actual_current'] is not None and \
                _myCar['charge_state']['charger_voltage'] is not None:
            self.is_charging = True
            # this is 3 phase charging
            if _myCar['charge_state']['charger_phases'] == 2:
                self.charge_actual_W = _myCar['charge_state']['charger_actual_current'] * _myCar['charge_state']['charger_voltage'] * 3
                self.charger_allowed_max_W = _myCar['charge_state']['charge_current_request_max'] * _myCar['charge_state']['charger_voltage'] * 3
            elif _myCar['charge_state']['charger_phases'] == 1:
                self.charge_actual_W = _myCar['charge_state']['charger_actual_current'] * _myCar['charge_state']['charger_voltage']
                self.charger_allowed_max_W = _myCar['charge_state']['charge_current_request_max'] * _myCar['charge_state']['charger_voltage']
            else:
                logger.log("Phases are hard", _myCar['charge_state']['charger_phases'])
                self.charge_actual_W = 0
                self.charger_allowed_max_W = 0



        else:
            self.is_charging = False
            self.charge_actual_W = 0
            self.charger_allowed_max_W = 1000

        self.cardata.update_value("CAR_charge_W", self.charge_actual_W)

        if "drive_state" in _myCar:
            loc = (_myCar["drive_state"]["latitude"], _myCar["drive_state"]["longitude"])
            self.last_distance = calculate_distance(home[0], home[1], loc[0], loc[1])
            self.last_distance_time = _myCar['drive_state']['timestamp'] / 1000
            # logger.log(f"The distance between the coordinates is {self.last_distance:.2f} km.")
            self.cardata.update_value("CAR_distance", self.last_distance)

        self.last_seen_s = time.time() - _myCar['charge_state']['timestamp'] / 1000
        self.cardata.update_value("CAR_seen_ago", self.last_seen_s)

        # update member values
        self.current_request = _myCar['charge_state']['charge_current_request']  # avoid control at 16A
        self.current_actual = _myCar['charge_state']['charger_actual_current']

        # = _myCar['charge_state']['charger_actual_current']
        self.is_ready_to_charge = _myCar['charge_state']['conn_charge_cable'] == 'IEC' and _myCar['charge_state']['charging_state'] in ['Charging', 'Stopped']  # not , 'Complete'

        # update all values with a defined source
        for i in self.cardata.get_name_list():
            s = self.cardata.get_source(i)
            if s is not None:
                v = get_item(_myCar, s)
                if v is not None:  # do not update None values as this is completely normal for e.g. "drive_state" to not be in the data
                    self.cardata.update_value(i, v)
                    # logger.info(i,v,s)
                else:
                    pass
                    # logger.info(i, "NONE", s)

        self.cardata.write_measurements()

        return _myCar

    def wake_up(self):
        _myCar = self.get_car_data()
        if _myCar is None:
            logger.log("Tesla connect fail on wake")
            return

        if _myCar['state'] == "asleep":
            logger.info("waiting for wake")
            try:
                _myCar.sync_wake_up(timeout=30)  ### wakes vehicle up !!!
            except Exception as e:
                logger.log(f"Tesla did not wake up within 30s {type(e)}: {e}")
            self.refresh()  # update data / read again!

    def is_ready(self):  # check, if car is ready according last data - without asking!

        kmph = 60
        kmps = kmph / 3600
        fastetst_time_to_return_s = self.last_distance / kmps
        # Car is not here
        if self.last_distance > 0.3:
            # logger.info(f"Car is {self.last_distance}km away, time to return {fastetst_time_to_return_s / 60}[min]")
            return False

        # check car state
        if not self.is_ready_to_charge:
            # logger.info("Car is not connected")
            return False

        if self.current_request == 16:
            # logger.info("Überschuss-laden nicht gewünscht - Ende hier!")
            return False

        # also at night, we can ignore the car.
        # Get the current time
        current_time = datetime.datetime.now().time()
        start_time = datetime.time(6, 0)
        end_time = datetime.time(20, 0)
        if start_time <= current_time <= end_time:
            pass
        else:
            # logger.info("Too late for charging, there will be no sun")
            pass  # return False fixme

        # Info too old
        '''
        # avoid wake due to program start and older than return time + 5h -> wake up
        if self.last_distance_time != 0 and (time.time() - self.last_distance_time) > fastetst_time_to_return_s + 60 * 60 * 5:
            self.wake_up()
            logger.info("Wake up car, cos I don't know where it is.")
            return False
        '''
        return True

    def set_charge(self, _do_charge, _req_power_w):
        _myCar = self.get_car_data()
        if _myCar is None:
            logger.log("Tesla connect fail on set_charge")
            return False

        self.refresh(_myCar)  # update data

        if not self.is_ready():  # do this after the update to get fresh info.
            logger.info("Car is not ready, but should be!")
            return False

        if _myCar['state'] == "asleep" and _do_charge and _req_power_w > 500:
            logger.info("Wake up car, cos I want to charge")
            self.wake_up()

        # I = P / U
        if _myCar['charge_state']['charger_phases'] == 2:
            amps = _req_power_w / (230 * 3)
        elif _myCar['charge_state']['charger_phases'] == 1:
            amps = _req_power_w / 230
        else:
            logger.log("Unexpected value: charging phases are weird.")
            return False

        ampere_rounded = round(amps, 0)

        if ampere_rounded < 1:
            _do_charge = False

            # charge_state can be 'Disconnected', 'Charging', 'Stopped', 'Complete', 'Starting'
        if _myCar['charge_state']['charging_state'] == 'Charging' and not _do_charge:
            logger.info(f"charging stopped at {self.charge_actual_W:.2f} W")
            try:
                _myCar.command('STOP_CHARGE')
                _myCar.command('CHARGING_AMPS', charging_amps=1)  # set minimum amps after stop
            except Exception as e:
                logger.log(f"Exception during stopping charge {type(e)}: {e}")
            self.refresh()  # read again
            return True  # finished here, as all else is related to setting the current

        if _req_power_w > 11000:
            logger.log("WATT is wrong with you", _req_power_w)
            return False

        if _myCar['charge_state']['charging_state'] == 'Stopped' and _do_charge:
            try:
                _myCar.command('START_CHARGE')
            except Exception as e:
                logger.log(f'Exception during starting charge {type(e)}: {e}')
            logger.info("car charging started")
            _myCar = self.refresh()  # read again and forward the new info for calculating the new powah

        if not (_myCar['charge_state']['charging_state'] == 'Charging' or _myCar['charge_state']['charging_state'] == 'Starting'):
            # ampere_rounded = 5
            # logger.info(f"Car is not charging and we set the amps to {ampere_rounded}")
            return False

        if ampere_rounded > 15:
            logger.log("too many amps requested", ampere_rounded)
            return False

        if _myCar['charge_state']['charge_current_request'] != ampere_rounded:  # only send, if different
            r = False
            try:
                r = _myCar.command('CHARGING_AMPS', charging_amps=int(ampere_rounded))
            except Exception as e:
                logger.log(f"Exception during changing charge request {type(e)}: {e}")
            # logger.info("Charge current changed", ampere_rounded, r)
            # self.refresh()  # read again! not needed - works great without.
            return r
        else:
            logger.info("Charge current ok", ampere_rounded)
            return True


# test stuff, if run directly


if __name__ == '__main__':
    # import database
    # import time

    myTesla = Car(tesla_login)

    time.sleep(15)

    myTesla.refresh()

    time.sleep(15)

    myTesla.refresh()

    # myTesla.set_charge(False, 1230)

'''
'''
