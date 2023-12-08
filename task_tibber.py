import pytz

import config
from lib.tibber import Tibber
from datetime import datetime, timedelta

from lib.tibber.tibber import tibber_time_to_datetime
from lib.measurementlist import MeasurementList

myTibber = Tibber(config.tibber_api_token)
data = MeasurementList()
do_get_price = True


def do_tibber():
    global myTibber
    global do_get_price

    current_time = datetime.now().time()

    if current_time.hour == 13 and current_time.minute == 00:
        do_get_price = True # re-arm the prize getting machine, which runs every 10 min.

    if current_time.minute % 10 == 0 and do_get_price:
        r = myTibber.update_price_info()
        if r:
            do_get_price = False
            dat=[]
            for i in myTibber.prices:
                tim = tibber_time_to_datetime(i['startsAt'])
                val = i['total']
                nam = "Tibber price"
                dat.append((nam, tim, val))
            data.write_list(dat)

def check_battery(_house_soc):
    global myTibber

    LOOK_HOURS_FORWARD = 12
    SPREAD_FOR_CHARGE = 0.10
    MAX_SOC_FOR_CHARGE = 50


    prices = myTibber.prices
    # Define current time and 24 hours from now
    timezone = pytz.timezone('Europe/Berlin')
    current_time = datetime.now(timezone)
    time_h_later = current_time + timedelta(hours=LOOK_HOURS_FORWARD)

    # Filter prices within the next 24 hours
    prices_next_h = [item['total'] for item in prices if current_time <= tibber_time_to_datetime(item['startsAt']) < time_h_later]

    # Find max and min prices
    if prices_next_h:
        spread = max(prices_next_h) - min(prices_next_h)
        print(f"Price spread in the next {LOOK_HOURS_FORWARD} hours: {spread}")
        if spread > SPREAD_FOR_CHARGE and _house_soc < MAX_SOC_FOR_CHARGE:
            print("Ok, it may be useful to charge the batt")
            # todo set charge at right time
            # set start time of planned charge
            # set max SOC to charge to
    else:
        print("No prices available in the next 24 hours.")





# test stuff
if __name__ == '__main__':
    # check_battery(45) # testing stuff

    soc = 68
    soclim = 80

    dt = myTibber.cheapest_charging_time(soc, soclim)
    print( dt)