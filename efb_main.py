# electron flux balancer

"""
we have a post-commit hook in place to push the *.py  to the pi.

# ssh login over another port behind NAT:
# ssh -p 2222 pi@my.ip.adr.ess

# crontab as follows and implements the autostart and a watchdog
@reboot sleep 20 && /usr/bin/python3 /home/pi/efb_main.py > /home/pi/out.txt 2>&>
@reboot sleep 90 && /home/pi/mount_backupdrive.sh

# watchdog, which copies the out.txt and restarts the app
*/10 * * * * /home/pi/checker.sh >> check.txt 2>&1

# check for presence of the backup mount
0  14 * * * /home/pi/backup_checker.sh >> check.txt 2>&1

# do the database backup
30 14 * * * /usr/bin/influxd backup -portable /home/pi/backup

#EOF crontab

# Create a backup in the portable format
influxd backup -portable /path/to/backup-destination

# Restore from a portable backup
influxd restore -portable /path/to/backup-destination

"""
from datetime import datetime

import modbus
import database
import tesla_interface
import time
import sungrow
from logger import logger
import tasmota
import os
import openDTU
import IntervalTask

from config import sungrow_ip
from config import openDTU_ip
from config import tesla_login

temp_setpoint = 60 # fixme do proper parameters

def measure_pi_temp():
    temp = os.popen("vcgencmd measure_temp").readline()
    temp = temp.replace("temp=", "")
    temp = temp.replace("'C", "")
    return float(temp.replace("temp=", ""))


def map_to_percentage(value, min_range, max_range):
    # Ensure that the value is within the specified range
    value = max(min_range, min(max_range, value))

    # Calculate the percentage
    percentage = (value - min_range) / (max_range - min_range) * 100

    return percentage


class ElectronFluxBalancer:
    def __init__(self):
        self.stop_heater = False
        self.stop_tesla = False
        self.island_mode = False

        self.heating_measurements = database.MeasurementList()

        # configure database channels
        self.heating_measurements.add_item(name="HEAT Boiler Oben", unit="°C", filter_jump=5, filter_time=60, source=0, filter_std_time=30, send_min_diff=0.5)
        self.heating_measurements.add_item(name="HEAT Boiler Unten", unit="°C", filter_jump=5, filter_time=60, source=1, filter_std_time=30, send_min_diff=0.5)
        self.heating_measurements.add_item(name="HEAT Boiler 3", unit="°C", filter_jump=5, filter_time=60, source=2, filter_std_time=30, send_min_diff=0.5)
        self.heating_measurements.add_item(name="HEAT Aussen", unit="°C", filter_jump=5, filter_time=60, source=3, filter_std_time=30, send_min_diff=0.5)
        self.heating_measurements.add_item(name="HEAT Ruecklauf", unit="°C", filter_jump=5, filter_time=60, source=4, filter_std_time=30, send_min_diff=0.5)
        self.heating_measurements.add_item(name="HEAT Vorlauf", unit="°C", filter_jump=5, filter_time=60, source=5, filter_std_time=30, send_min_diff=0.5)
        self.heating_measurements.add_item(name="HEAT spare", unit="°C", filter_jump=5, filter_time=60, source=6, filter_std_time=30, send_min_diff=0.5)

        self.heating_measurements.add_item(name="Pi Temp", unit="°C", filter_jump=5, filter_time=60, source=None, filter_std_time=30, send_min_diff=1.0)
        self.heating_measurements.add_item(name="Pi Time", unit="s", filter_jump=3, filter_time=30, source=None, filter_std_time=5, send_min_diff=1.0)
        self.heating_measurements.add_item(name="Pi Time of Day", unit="s", filter_jump=3, filter_time=30, source=None, filter_std_time=5, send_min_diff=0.1 , send_max_time=60*60)
        self.heating_measurements.add_item(name="HEAT Water prc", unit="%", filter_jump=1.5, filter_time=60, source=None, filter_std_time=30, send_min_diff=1.0)

        self.heating_measurements.add_item(name="CAR Charge command", unit="%", filter_jump=1000, filter_time=60, source=None, filter_std_time=0, send_min_diff=100)  # updated only if value changes
        self.heating_measurements.add_item(name="HEAT power command", unit="%", filter_jump=1000, filter_time=60, source=None, filter_std_time=0, send_min_diff=100)

        self.myTesla = tesla_interface.Car(tesla_login)

        # timing stuff
        #self.last_car_update = time.time()
        # self.last_car_charge_update = time.time()
        self.last_car_charge_current_sync = time.time()
        #self.last_heater_update = time.time()
        #self.last_tasmota_update = time.time()

        self.EMERGENCY_HEATER_OFF = False

        self.sg = sungrow.SungrowSH(sungrow_ip, 502)
        RS485_bus = modbus.Bus("/dev/ttyUSB0")
        self.temperatures_heating = modbus.Nt18b07TemperatureIn(RS485_bus, 1)
        self.rel1 = modbus.Bestep2Relays(RS485_bus, 0xff)

        self.allowHeater = False

        self.hour_marked = False

        self.heatpower = 0

        self.car_charge_amp = 0
        self.car_charging_phases = 3

        self.tas = tasmota.Tasmotas()

        self.dtu = openDTU.OpenDTU(openDTU_ip)

        logger.info("Start ####################################################################")
        logger.log("Start ####################################################################")

        taskctl = IntervalTask.TaskController()
        taskctl.add_task("tesla", self.do_car_update, 5*60,30)
        taskctl.add_task("tesla_charge", self.do_car_charge, 30, 10)
        taskctl.add_task("sungrow", self.do_sungrow_update, 2, 8)
        # taskctl.add_task("temperature", self.do_temperature_update, 3, 10)
        taskctl.add_task("tasmota", self.do_tasmota_stuff,10,10)
        taskctl.add_task("heater", self. do_heater_update, 10,5)


    def set_heater(self, watt):
        if self.EMERGENCY_HEATER_OFF or self.stop_heater:
            self.rel1.off(0)
            return

        watt = min(watt, 3000)
        watt = max(watt, 0)

        timout = 90
        if 500 < watt <= 1500:
            self.rel1.on(2, timout)
            self.rel1.off(1)
            self.heatpower = 1000
        elif 1500 < watt <= 2500:
            self.rel1.on(1, timout)
            self.rel1.off(2)
            self.heatpower = 2000
        elif 2500 < watt <= 3500:
            self.rel1.on(0, timout)
            self.heatpower = 3000
        else:
            self.rel1.off(0)
            self.heatpower = 0

        self.heating_measurements.update_value("HEAT power command", self.heatpower)


    def do_car_update(self):  # every 5 min
        self.myTesla.refresh()

    def do_sungrow_update(self):
        self.sg.update()  # get values from Wechselrichter

    def do_temperature_update(self): # every 2s

        self.temperatures_heating.get_temperatures()
        for i in self.heating_measurements.get_name_list():
            if self.heating_measurements.get_source(i) is not None:
                self.heating_measurements.update_value(i, self.temperatures_heating.values[self.heating_measurements.get_source(i)])

        self.heating_measurements.update_value("Pi Temp", measure_pi_temp())

        boiler_temp_sum = (self.heating_measurements.get_value("HEAT Boiler Oben") + self.heating_measurements.get_value("HEAT Boiler Unten") + self.heating_measurements.get_value(
            "HEAT Boiler 3")) / 3.0
        self.heating_measurements.update_value("HEAT Water prc", map_to_percentage(boiler_temp_sum, (35 + 30 + 25) / 3.0, temp_setpoint))

        # prepare values:
        boiler_temp_bot = self.heating_measurements.get_value('HEAT Boiler Unten')
        over_temperature = self.heating_measurements.get_value('HEAT spare')  # magnetic extra sensor at cabinet outer surface

        if over_temperature > 60 or boiler_temp_bot > 63 or self.EMERGENCY_HEATER_OFF:
            self.rel1.off(1)  # emergency switch off
            logger.log("HEATER EMERGENCY OFF")
            self.EMERGENCY_HEATER_OFF = True

        # write time of day as a separate variable
        # Get current date and time
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        current_second = current_time.second

        # Check if it's roughly a full hour (within the first 10 seconds)
        if current_minute == 0 and current_second < 10:
            if not self.hour_marked:
                # Set flag to true
                self.hour_marked = True

                # If it's midnight, use 24 instead of 0
                if current_hour == 0:
                    float_hour = 24.00
                else:
                    float_hour = float(current_hour)

                # time_of_day = (lambda t: t.hour * 3600 + t.minute * 60 + t.second)(datetime.datetime.fromtimestamp(time.time()))
                self.heating_measurements.update_value("Pi Time of Day", float_hour)
        else:
            # Reset the flag when we're away from the top of the hour
            self.hour_marked = False

        self.heating_measurements.write_measurements()

    def do_car_charge(self):
        # prepare values:
        export_power = self.sg.measurements.get_value_filtered('ELE Export power')
        battery_power = self.sg.measurements.get_value_filtered('ELE Battery power c')

        battery_soc = self.sg.measurements.get_value('ELE Battery level')
        if self.myTesla.is_ready() and not self.stop_tesla and not (
                export_power is None or
                battery_power is None or
                battery_soc is None
        ):
            # avoid charging with wrong value for too long
            # actual_set_charger_W = self.myTesla.charge_actual_W
            if self.myTesla.current_actual > self.car_charge_amp and time.time() - self.last_car_charge_current_sync > 6 * 60:
                logger.info(f"CAR charge current sync: was {self.car_charge_amp}, now {self.myTesla.current_actual}")
                self.car_charge_amp = self.myTesla.current_actual
                self.last_car_charge_current_sync = time.time()

            if battery_soc > 30 and battery_power > -4000 and export_power > (-4500 if self.island_mode else -200):  # only allow charging over x% battery

                if battery_soc < 95 or not self.island_mode:  # avoid idling around with nothing to do as long as export_power is limited to -50W
                    phantasy_power = 0
                elif 95 <= battery_soc <= 100:
                    phantasy_power = 200 * (battery_soc - 95)  # 0..5
                else:
                    phantasy_power = 1000

                if battery_soc < 80 and self.island_mode:
                    phantasy_power = -750  # leave room for batt to charge - does not work at 500w charge power

                if (export_power + battery_power + phantasy_power) > 750 and self.car_charge_amp < 15:
                    self.car_charge_amp += 1
                    self.myTesla.set_charge(True, self.car_charge_amp * 230 * self.car_charging_phases)
                    # logger.info("Tesla inc", self.car_charge_amp)

                if (export_power + battery_power + phantasy_power) < (-500 if self.island_mode else 0) and self.car_charge_amp > 0:
                    self.car_charge_amp -= 1
                    self.myTesla.set_charge(True, self.car_charge_amp * 230 * self.car_charging_phases)

                    # logger.info("Tesla dec", self.car_charge_amp)

            elif self.myTesla.is_charging:
                self.myTesla.set_charge(False, 0)
                self.car_charge_amp = 0
                logger.info("Charging end - too much power draw or batt empty")
            else:
                self.car_charge_amp = 0
                # logger.info("too much power draw or batt empty")
        else:
            self.car_charge_amp = 0  # Tesla not ready
            # logger.info("Car not ready")

        self.heating_measurements.update_value("CAR Charge command", self.car_charge_amp * 230 * self.car_charging_phases)

        if self.car_charge_amp > 0 or self.myTesla.is_charging:
            self.allowHeater = False
        else:
            self.allowHeater = True

    def do_heater_update(self):
        #  every 10s

        # prepare values:
        export_power = self.sg.measurements.get_value_filtered('ELE Export power')
        battery_power = self.sg.measurements.get_value_filtered('ELE Battery power c')
        generated_power_S = self.sg.measurements.get_value_filtered('ELE String S power')
        generated_power_N = self.sg.measurements.get_value_filtered('ELE String N power')
        if generated_power_S is None or generated_power_N is None:
            generated_power = None
        else:
            generated_power = generated_power_S + generated_power_N
        battery_soc = self.sg.measurements.get_value('ELE Battery level')
        boiler_temp_bot = self.heating_measurements.get_value('HEAT Boiler Unten')
        over_temperature = self.heating_measurements.get_value('HEAT spare')  # magnetic extra sensor at cabinet outer surface

        if not self.allowHeater:
            # no heat today
            hw = 0
        elif (
                export_power is None or
                battery_power is None or
                generated_power is None or
                battery_soc is None or
                boiler_temp_bot is None or
                over_temperature is None
        ):
            logger.log("We have None values!", export_power, battery_power, generated_power, battery_soc, boiler_temp_bot, over_temperature)
            hw = 0
        else:
            # ok, we try to control it
            hw = self.heatpower  # the remembered value
            '''
            generated_power is only checked for 50W, because Nulleinspeisung
            '''
            if (
                    (self.island_mode and
                     ((battery_soc > 90 and battery_power > 1000) or
                      (battery_soc > 95 and generated_power > 50)) and export_power > -500)
                    or
                    not self.island_mode and
                    (export_power > 1100)
            ) and \
                    boiler_temp_bot < temp_setpoint and \
                    self.allowHeater and \
                    over_temperature < 57 and \
                    not self.stop_heater:  # and ep > -100: # and bp > xx
                hw += 1000
                # logger.info("inc heater", self.allowHeater, export_power, boiler_temp_bot, battery_soc, hw)
            elif export_power < (-1000 if self.island_mode else 0) or boiler_temp_bot > temp_setpoint or battery_power < -1000:
                hw -= 1000
                # logger.info("dec heater", self.allowHeater, export_power, boiler_temp_bot, battery_soc, hw)

            # no discussion, if something is off, we switch off.
            if self.island_mode and (export_power < -3000 or battery_power < -2000 or battery_soc < 80 or boiler_temp_bot > temp_setpoint + 3):
                hw = 0
                # logger.info("disable heater in island mode", self.allowHeater, export_power, boiler_temp_bot, battery_soc)
            if not self.island_mode and (export_power + battery_power < -1000 or battery_soc < 95 or boiler_temp_bot > temp_setpoint + 3):
                hw = 0
                # logger.info("disable heater", self.allowHeater, export_power, boiler_temp_bot, battery_soc)
        self.set_heater(hw)


    def do_tasmota_stuff(self):

        self.dtu.update()  # just hang in the same interval - 10s

        generated_power_S = self.sg.measurements.get_value_filtered('ELE String S power')
        generated_power_N = self.sg.measurements.get_value_filtered('ELE String N power')
        if generated_power_S is None or generated_power_N is None:
            generated_power = None
        else:
            generated_power = generated_power_S + generated_power_N

        self.tas.update(generated_power)  # updates one at a time.

        # fixme runtime self.heating_measurements.update_value("Pi Time", time.time()-startTime)







if __name__ == '__main__':
    efb = ElectronFluxBalancer()
    while True:
        efb.do_temperature_update()
        time.sleep(2)
