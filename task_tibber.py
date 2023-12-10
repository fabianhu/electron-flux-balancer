

import pytz

import config
from lib.tibber import Tibber
from datetime import datetime, timedelta
from lib.logger import Logger
import logging
logger = Logger(logging.DEBUG, "tibber.log")

from lib.tibber.tibber import tibber_time_to_datetime
from lib.measurementlist import MeasurementList

myTibber = Tibber(config.tibber_api_token)
data = MeasurementList()
do_get_price = True


def do_tibber_to_influx():
    global myTibber
    global do_get_price

    current_time = datetime.now().time()

    if current_time.hour == 13 and current_time.minute == 00:
        do_get_price = True # re-arm the prize getting machine, which runs every 10 min.

    if current_time.minute % 10 == 0 and do_get_price:
        r = myTibber.update_price_info()
        if r:
            logger.debug("Tibber refreshed")
            if len(myTibber.prices) == 48:
                logger.debug("Tibber refreshed with all data")
                do_get_price = False
            else:
                logger.debug(f"Tibber refreshed, but did only get {len(myTibber.prices)} data")

            dat=[]
            for i in myTibber.prices:
                tim = tibber_time_to_datetime(i['startsAt'])
                val = i['total']
                nam = "Tibber price"
                dat.append((nam, tim, val))
            r= data.write_list(dat)
            if r:
                logger.debug("Tibber data written")
            else:
                logger.error("Tibber data could not be written")
        else:
            logger.error("Tibber data could not be obtained")

charge_start_dt = None
is_battery_planning_init = True

def check_battery(_house_soc):
    global myTibber
    global charge_start_dt
    global is_battery_planning_init

    PLANNING_SCHEDULE_HOUR = 21
    LOOK_HOURS_FORWARD = 12 # how far to plan the next charge
    LOOK_HOURS_SPREAD = LOOK_HOURS_FORWARD + 6 # how far to look for the spread e.g. 21 + 12 = 9 +6 = 15 h
    SPREAD_FOR_CHARGE = 0.065
    SOC_TARGET = 50

    capacity_kWh = 10
    max_power_kW = 5

    timezone = pytz.timezone('Europe/Berlin')
    current_time = datetime.now(timezone)

    # we plan every hour
    if current_time.minute == 0 and current_time.minute == PLANNING_SCHEDULE_HOUR or is_battery_planning_init:  # fixme avoid to do twice at 30s interval (but nevermind, should not bother)
        # calculate the best charging time
        is_battery_planning_init = False

        prices = myTibber.prices
        time_h_later = current_time + timedelta(hours=LOOK_HOURS_SPREAD)

        # Filter prices for the time to check
        prices_next_h = [item['total'] for item in prices if current_time <= tibber_time_to_datetime(item['startsAt']) < time_h_later]

        # Find max and min prices
        if prices_next_h:
            spread = max(prices_next_h) - min(prices_next_h)
            logger.debug(f"Price spread in the next {LOOK_HOURS_SPREAD} hours: {spread}")
            if spread > SPREAD_FOR_CHARGE and _house_soc < SOC_TARGET:
                # set start time of planned charge
                charge_start_dt = myTibber.cheapest_charging_time(_house_soc, SOC_TARGET, capacity_kWh, max_power_kW)
                logger.debug(f"Ok, it may be useful to charge the batt at {charge_start_dt}")
            else:
                charge_start_dt = None
        else:
            logger.error(f"No prices available in the next {LOOK_HOURS_SPREAD} hours.")
            charge_start_dt = None

    if charge_start_dt is None:
        return None

    #safety timer
    if 5 < current_time.hour < 22:
        logger.debug("outside of business hours")
        return None

    # Calculate required energy to charge to 100%
    required_kWh = (100 - _house_soc) / 100 * capacity_kWh

    # Calculate the expected end time based on current charge percent
    hours_required = required_kWh / max_power_kW
    calculated_end_time = charge_start_dt + timedelta(hours=hours_required)

    # If current time is near the ideal start time and we're not already charging, start charging
    if calculated_end_time >= current_time >= charge_start_dt and _house_soc < SOC_TARGET:
        return max_power_kW*1000
    else:
        # Stop the charging process
        charge_start_dt = None
        return None



# test stuff
if __name__ == '__main__':
    check_battery(23) # testing stuff

    #do_tibber()

    soc = 68
    soclim = 80

    #dt = myTibber.cheapest_charging_time(soc, soclim)
    #print( dt)