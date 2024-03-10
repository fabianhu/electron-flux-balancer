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
import logging

import config
import modbus
import tesla_interface
import lib.tesla_api.tesla_api_2024
import lib.tibber
from lib.measurementlist import MeasurementList
import time
import sungrow
from lib.logger import Logger
logger = Logger(log_level=logging.DEBUG)
import tasmota
import os
import openDTU
import lib.intervaltask
from datetime import datetime, timedelta

from config import sungrow_ip
from config import openDTU_ip
from displayserver import push_displays
from task_tibber import myTibber

temp_setpoint = 60 # fixme do proper parameters using ParameterServer

def measure_pi_temp():
    temp = os.popen("vcgencmd measure_temp").readline()
    temp = temp.replace("temp=", "")
    temp = temp.replace("'C", "")
    return float(temp.replace("temp=", ""))


def map_to_percentage(value, min_range, max_range):
    if value is None:
        return 0
    # Ensure that the value is within the specified range
    value = max(min_range, min(max_range, value))
    # Calculate the percentage
    percentage = (value - min_range) / (max_range - min_range) * 100
    return percentage


def map_sym_to_percentage(value, srange):
    if value is None:
        return 0
    # Calculate the percentage
    percentage = value / srange * 100
    return percentage


class ElectronFluxBalancer:
    def __init__(self):
        self.stop_heater = False
        self.stop_tesla = False
        self.island_mode = False

        self.heating_measurements = MeasurementList()

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

        self.myTesla = tesla_interface.TeslaCar(config.tesla_vin, lib.tesla_api.tesla_api_2024.TeslaAPI())

        # timing stuff
        self.last_car_charge_current_sync = time.time()

        self.EMERGENCY_HEATER_OFF = False

        self.sg = sungrow.SungrowSH(sungrow_ip, 502)

        RS485_bus = modbus.Bus("/dev/ttyUSB0")
        self.temperatures_heating = modbus.Nt18b07TemperatureIn(RS485_bus, 1)
        self.rel1 = modbus.Bestep2Relays(RS485_bus, 0xff)

        self.allowHeater = False

        self.hour_marked = False  # update hour of day

        self.heatpower = 0

        self.car_charge_amp_command_integrator = 0

        self.last_tibber_schedule = datetime.now()-timedelta(days=2) # set to the past

        self.tas = tasmota.Tasmotas()

        self.dtu = openDTU.OpenDTU(openDTU_ip)

        taskctl = lib.intervaltask.TaskController()
        taskctl.add_task("tesla", self.do_car_update, 5*60,30)
        taskctl.add_task("tesla_charge", self.do_car_charge, 30, 20)
        taskctl.add_task("sungrow", self.do_sungrow_update, 2, 8)
        taskctl.add_task("tasmota", self.do_tasmota_stuff,10,10)
        taskctl.add_task("displays", self.do_display_update, 10, 10)

        import task_tibber
        taskctl.add_task("tibber", task_tibber.do_tibber_to_influx, 60, 30)

        # do them inside the main task, because of modbus being picky.
        # taskctl.add_task("temperature", self.do_temperature_update, 3, 10)
        # taskctl.add_task("heater", self. do_heater_update, 10,5)


    def set_heater(self, watt):
        if self.EMERGENCY_HEATER_OFF or self.stop_heater:
            self.rel1.off(0)
            self.heatpower = 0
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
            self.rel1.on(0, timout) # both
            self.heatpower = 3000
        else:
            self.rel1.off(0)
            self.heatpower = 0

        self.heating_measurements.update_value("HEAT power command", self.heatpower)


    def do_car_update(self):  # every 5 min
        self.myTesla.get_car_life_data()

        self.do_tesla_tibber_planning()


    def do_car_charge(self):
        # solar power overhang charge

        # prepare values:
        house_export_power = self.sg.measurements.get_value_filtered('ELE Export power')
        house_battery_power = self.sg.measurements.get_value_filtered('ELE Battery power c')
        house_battery_soc = self.sg.measurements.get_value('ELE Battery level')
        phases = self.myTesla.CAR_charger_real_phases # We need this here!
        CAR_charger_actual_current = self.myTesla.car_db_data.get_value('CAR_charger_actual_current')
        CAR_charge_current_request = self.myTesla.car_db_data.get_value('CAR_charge_current_request')

        # ready for solar overflow charging
        if self.myTesla.is_here_and_connected() and not self.stop_tesla and not CAR_charge_current_request == 16 and not (
                house_export_power is None or
                house_battery_power is None or
                house_battery_soc is None
        ):
            # avoid charging with wrong value for too long
            # actual_set_charger_W = self.myTesla.charge_actual_W
            if CAR_charger_actual_current > self.car_charge_amp_command_integrator and time.time() - self.last_car_charge_current_sync > 6 * 60:
                logger.info(f"CAR charge current sync: was {self.car_charge_amp_command_integrator}, now {CAR_charger_actual_current}")
                self.car_charge_amp_command_integrator = CAR_charger_actual_current
                self.last_car_charge_current_sync = time.time()

            if house_battery_soc > 30 and house_battery_power > -4000 and house_export_power > (-4500 if self.island_mode else -200):  # only allow charging over x% battery

                if house_battery_soc < 95 or not self.island_mode:  # avoid idling around with nothing to do as long as house_export_power is limited to -50W
                    phantasy_power = 0
                elif 95 <= house_battery_soc <= 100:
                    phantasy_power = 200 * (house_battery_soc - 95)  # 0..5
                else:
                    phantasy_power = 1000

                if house_battery_soc < 80 and self.island_mode:
                    phantasy_power = -750  # leave room for batt to charge - does not work at 500w charge power

                if (house_export_power + house_battery_power + phantasy_power) > 750 and self.car_charge_amp_command_integrator < 15:
                    self.car_charge_amp_command_integrator += 1
                    self.myTesla.set_charge(True, self.car_charge_amp_command_integrator)
                    # logger.info(f"Tesla inc {self.car_charge_amp_command_integrator}")

                if (house_export_power + house_battery_power + phantasy_power) < (-500 if self.island_mode else 0) and self.car_charge_amp_command_integrator > 0:
                    self.car_charge_amp_command_integrator -= 1
                    self.myTesla.set_charge(True, self.car_charge_amp_command_integrator)
                    # logger.info(f"Tesla dec {self.car_charge_amp_command_integrator}")

            elif self.myTesla.is_charging: # do not charge anymore (conditions not met)
                self.myTesla.set_charge(False, 0)
                self.car_charge_amp_command_integrator = 0
                logger.info("Charging end - too much power draw or batt empty")
            else:
                self.car_charge_amp_command_integrator = 0
                logger.info("too much power draw or batt empty")
        else:
            self.car_charge_amp_command_integrator = 0  # Tesla not ready
            logger.info("Car not ready")

        # send to DB what we actually commanded tight now.
        self.heating_measurements.update_value("CAR Charge command", self.car_charge_amp_command_integrator * 230 * phases)

        if self.car_charge_amp_command_integrator > 0 or self.myTesla.is_charging:
            self.allowHeater = False
        else:
            self.allowHeater = True


    def do_sungrow_update(self):
        self.sg.update()  # get values from Wechselrichter

        car_charge_power = self.myTesla.car_db_data.get_value('CAR_charge_W')

        # battery_soc = self.sg.measurements.get_value('ELE Battery level')
        # fixme batrecommend = task_tibber.check_battery(battery_soc)

        is_here_and_connected = self.myTesla.is_here_and_connected()

        # logger.debug(f"Car charge power {car_charge_power} W and is here: {is_here_and_connected}")

        # stop DISCHARGING the battery on high load from car and control battery at same point.
        if  is_here_and_connected and car_charge_power > 10000:  # fixme check this decision!!
            self.sg.set_forced_charge(0)
            # logger.debug(f"Car charge power {car_charge_power} W -> House batt off")
        else:
            self.sg.set_forced_charge(None)


    def do_temperature_update(self): # every 2s

        self.temperatures_heating.get_temperatures()

        # update all temperature values
        for i in self.heating_measurements.get_name_list():
            if self.heating_measurements.get_source(i) is not None:
                self.heating_measurements.update_value(i, self.temperatures_heating.values[self.heating_measurements.get_source(i)])

        self.heating_measurements.update_value("Pi Temp", measure_pi_temp())

        try:
            temp_top_prc = map_to_percentage(self.heating_measurements.get_value("HEAT Boiler Oben"),50,temp_setpoint)
            temp_mid_prc = map_to_percentage(self.heating_measurements.get_value("HEAT Boiler 3"), 25, temp_setpoint)
            temp_low_prc = map_to_percentage(self.heating_measurements.get_value("HEAT Boiler Unten"), 20, temp_setpoint)
            temp_prc = (temp_top_prc+temp_mid_prc+temp_low_prc)/3

            self.heating_measurements.update_value("HEAT Water prc", temp_prc)
        except TypeError:  # catch exception if value is None ! (RTU init error)
            self.heating_measurements.update_value("HEAT Water prc", None)
            logger.error("Water heater values not present.")

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
            logger.log(f"We have None values! exp{export_power}, bat{battery_power}, gen{generated_power}, soc{battery_soc}, boi{boiler_temp_bot}, ovt{over_temperature}")

            self.rel1.off(1)  # emergency switch off
            logger.error("Heater off due to None values!")

            return # do not continue
        else:
            # ok, we try to control it
            hw = self.heatpower  # the remembered value

            if self.island_mode: # todo par
                if(
                        ((battery_soc > 90 and battery_power > 1000) or (battery_soc > 95 and generated_power > 50))
                        and export_power > -500  # generated_power is only checked for 50W, because Nulleinspeisung
                        and boiler_temp_bot < temp_setpoint
                        and self.allowHeater
                        and over_temperature < 57
                        and not self.stop_heater
                        and hw < 3000
                ):
                    hw += 1000
                    # logger.info("inc heater", self.allowHeater, export_power, boiler_temp_bot, battery_soc, hw)
                elif export_power < -1000 or boiler_temp_bot > temp_setpoint or battery_power < -1000:
                    hw -= 1000
                    # logger.info("dec heater", self.allowHeater, export_power, boiler_temp_bot, battery_soc, hw)

                # no discussion, if something is off, we switch off.
                if export_power < -3000 or battery_power < -2000 or battery_soc < 80 or boiler_temp_bot > temp_setpoint + 3:
                    hw = 0
                    # logger.info("disable heater in island mode", self.allowHeater, export_power, boiler_temp_bot, battery_soc)

            else:  # not island mode
                if (
                        export_power > 1100
                        and boiler_temp_bot < temp_setpoint
                        and self.allowHeater
                        and not self.stop_heater
                        and hw < 3000
                ):
                    hw += 1000
                    # logger.info("inc heater", self.allowHeater, export_power, boiler_temp_bot, battery_soc, hw)
                elif export_power <  0 or boiler_temp_bot > temp_setpoint or battery_power < -1000:
                    hw -= 1000
                    # logger.info("dec heater", self.allowHeater, export_power, boiler_temp_bot, battery_soc, hw)

                # no discussion, if something is off, we switch off.
                if (
                        (export_power + battery_power < -2000 or battery_soc < 95 or boiler_temp_bot > temp_setpoint + 3)
                        and hw > 0
                ):
                    hw = 0
                    logger.debug(f"disable heater, ht{self.allowHeater}, exp{export_power}, boi{boiler_temp_bot}, soc{battery_soc}")

        if over_temperature > 60 or boiler_temp_bot > 65 or self.EMERGENCY_HEATER_OFF:
            hw = 0
            logger.error(f"EMERGENCY heater, emo{self.EMERGENCY_HEATER_OFF}, exp{export_power}, boi{boiler_temp_bot}, ovt{over_temperature}")

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


    def do_display_update(self):
        generated_power_S = self.sg.measurements.get_value_filtered('ELE String S power')
        generated_power_N = self.sg.measurements.get_value_filtered('ELE String N power')
        generated_power_gar_S = self.dtu.dat.get_value_filtered('HOY Garage S Power')
        generated_power_gar_N = self.dtu.dat.get_value_filtered('HOY Garage N Power')
        if generated_power_S is None: generated_power_S = 0
        if generated_power_N is None: generated_power_N = 0
        if generated_power_gar_S is None: generated_power_gar_S = 0
        if generated_power_gar_N is None: generated_power_gar_N = 0

        generated_power = generated_power_S + generated_power_N + generated_power_gar_S + generated_power_gar_N
        battery_soc = self.sg.measurements.get_value('ELE Battery level')
        battery_pwr = self.sg.measurements.get_value_filtered('ELE Battery power c')
        car_soc = self.myTesla.car_db_data.get_value('CAR_battery_level')
        carpwr_W = self.myTesla.car_db_data.get_value('CAR_charge_W')

        heat_soc = self.heating_measurements.get_value('HEAT Water prc')
        heat_pwr = self.heating_measurements.get_value('HEAT power command')
        export_power = self.sg.measurements.get_value('ELE Export power')

        # get price from tibber module
        price = myTibber.get_price()

        push_displays(generated_power, export_power, battery_soc, battery_pwr, car_soc, carpwr_W, heat_soc, heat_pwr, price, 0)
        #logger.info(generated_power, battery_soc, battery_pwr, car_soc, car_pwr, heat_soc, heat_pwr, export_power, price)


    def do_tesla_tibber_planning(self):  # every 5 min directly after reading car data
        TIBBER_CAR_CHARGE_CURRENT = 16 # todo par - must be the same value as the decision, if solar overflow charging!!

        now = datetime.now()

        if not self.myTesla.is_here_and_connected():
            self.last_tibber_schedule = now - timedelta(days=2) # set to the past

        if now-self.last_tibber_schedule > timedelta(hours=12) and self.myTesla.is_here_and_connected():  # we only plan, if car is here and connected and only once every 12h.
            soc = self.myTesla.car_db_data.get_value("CAR_battery_level")
            soclim = self.myTesla.car_db_data.get_value("CAR_charge_limit_soc")
            charge_current_request = self.myTesla.car_db_data.get_value("CAR_charge_current_request")
            state = self.myTesla.car_db_data.get_value("CAR_charging_state")

            if soc is None or soclim is None or state is None:
                logger.error("Tibber Car Charge Plan no info from Tesla")
                return

            if charge_current_request != TIBBER_CAR_CHARGE_CURRENT:
                logger.debug(f"Tibber charging cancelled due to requested {charge_current_request} A instead of {TIBBER_CAR_CHARGE_CURRENT} A.")
                # just leave it. self.myTesla.tesla_api.cmd_charge_cancel_schedule(self.myTesla.vin) # will immediately start
                return

            if state != "Stopped":
                logger.debug(f"Tibber charging cancelled due to state being {state} instead of Stopped.")
                return

            mins = lib.tibber.tibber.datetime_to_minutes_after_midnight(myTibber.cheapest_charging_time(soc,soclim))
            if mins is None:
                logger.error(f"Tibber we had no result from {myTibber.prices} with SOC: {soc} and limit: {soclim}")
                return

            self.myTesla.tesla_api.cmd_charge_set_schedule(self.myTesla.vin, mins)

            self.last_tibber_schedule = now
            logger.info(f"Tibber Car charge plan is start at {mins/60} h")


zzz=0

if __name__ == '__main__':
    efb = ElectronFluxBalancer()
    while True: # every 2s

        efb.do_temperature_update() # fixme we do not have a watchdog here!
        zzz+=1
        if zzz == 5:
            efb.do_heater_update()  # every 10s
            zzz = 0

        time.sleep(2)