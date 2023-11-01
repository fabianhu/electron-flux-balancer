from datetime import datetime

import pytz

import database
from logger import logger
import requests
import time
import imagelogger
from config import tasmota_ips, tasmota_meter_ip


lastImageTime = time.time()
class Tasmotas:
    def __init__(self):
        logger.log("Start Tasmota client")

        self.iterator = 0

        self.dat = database.MeasurementList()
        # source: ip, on_w,
        self.dat.add_item("TAS 31 Power", source={"ip": tasmota_ips[0], "on_w": 100}, send_min_diff=5, filter_std_time=10, filter_jump=500)
        self.dat.add_item("TAS 32 Power", source={"ip": tasmota_ips[1], "on_w": 0  }, send_min_diff=5, filter_std_time=10, filter_jump=500)
        self.dat.add_item("TAS 33 Power", source={"ip": tasmota_ips[2], "on_w": 0  }, send_min_diff=5, filter_std_time=10, filter_jump=500)
        self.dat.add_item("TAS 34 Power", source={"ip": tasmota_ips[3], "on_w": 0  }, send_min_diff=5, filter_std_time=10, filter_jump=500)
        self.dat.add_item("TAS 35 Power", source={"ip": tasmota_ips[4], "on_w": 0  }, send_min_diff=5, filter_std_time=10, filter_jump=500)
        self.dat.add_item("TAS 36 Power", source={"ip": tasmota_ips[5], "on_w": 0  }, send_min_diff=5, filter_std_time=10, filter_jump=500)
        self.dat.add_item("TAS 37 Power", source={"ip": tasmota_ips[6], "on_w": 0  }, send_min_diff=5, filter_std_time=10, filter_jump=500)
        self.dat.add_item("TAS 38 Power", source={"ip": tasmota_ips[7], "on_w": 0  }, send_min_diff=5, filter_std_time=10, filter_jump=500)


        # hardcoded Stromzähler
        self.smldat = database.MeasurementList()
        self.smldat.add_item("SML purchase", source="purchase", send_min_diff=10, filter_jump=1000)
        self.smldat.add_item("SML export", source="export", send_min_diff=10, filter_jump=1000)
        self.smldat.add_item("SML power", source="power", send_min_diff=10, filter_jump=1000)


    def update(self, actPower = None):
        li = list(self.dat.get_name_list())
        le = len(li)
        if self.iterator < le-1:
            self.iterator += 1
        else:
            self.iterator = 0

        adr = self.dat.get_source(li[self.iterator])["ip"]
        onw = self.dat.get_source(li[self.iterator])["on_w"]
        # ask the guys
        try:
            response = requests.get(f'http://{adr}/cm?cmnd=Status%200', timeout= 0.5)
        except requests.exceptions.Timeout:
            # logger.log(f"TAS {li[self.iterator]} timeout")  # can happen quite frequently, as WIFI is switched off.
            self.dat.update_value(li[self.iterator], None)
            return

        except requests.exceptions.RequestException as e:
            logger.log(f"TAS {li[self.iterator]} Request failed: {e}")
            self.dat.update_value(li[self.iterator], None)
            return

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the JSON response
            stat = response.json()['Status']['Power']   # info: may crash here during tasmota upgrade (minimal Tasmota answers, but without content)
            powr = response.json()['StatusSNS']['ENERGY']['Power']

            if stat == 0:
                powr = -10

            self.dat.update_value(li[self.iterator], powr)

            if actPower is not None and onw >0:
                command = None
                if actPower > onw and stat == 0:
                    command = 'POWER ON'
                if actPower < onw and stat == 1:
                    command = 'POWER OFF'

                if command is not  None:
                    try:
                        response = requests.get(f'http://{adr}/cm?cmnd={command}', timeout=2)
                    except requests.exceptions.Timeout:
                        logger.log("TAS timeout")
                    except requests.exceptions.RequestException as e:
                        logger.log(f"TAS '{command}' Request failed: {e}")

                    if response.status_code == 200:
                        logger.info(f"TAS {adr} Command '{command}' successful")
                    else:
                        logger.log(f"TAS {adr} Request failed with status code: {response.status_code}")
        else:
            logger.log(f"TAS {adr} Request failed with status code: {response.status_code}")

        self.dat.write_measurements()

        self.update_sml()

        # image logger stuff
        do_image_logger = False # defunct because camera is offline!
        if do_image_logger:
            t=time.time()
            global lastImageTime
            L = self.dat.get_value("TAS 35 Power")
            if L is None: L=0;

            R = self.dat.get_value("TAS 34 Power")
            if R is None: R=0

            if t-lastImageTime >=60 and L+R>3:
                imagelogger.get_image(L,R)
                lastImageTime = t


    def update_sml(self):
        # ask the Stromzähler - this is hardcoded!
        try:
            response = requests.get(f'http://{tasmota_meter_ip}/cm?cmnd=Status%208', timeout= 0.5)
        except requests.exceptions.Timeout:
            # logger.log(f"sml timeout")  # can happen quite frequently, as WIFI is switched off.
            for el in list(self.smldat.get_name_list()):
                self.smldat.update_value(el, None)
            self.smldat.write_measurements()
            return

        except requests.exceptions.RequestException as e:
            logger.log(f"sml Request failed: {e}")
            for el in list(self.smldat.get_name_list()):
                self.smldat.update_value(el, None)
            self.smldat.write_measurements()
            return

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the JSON response
            r = response.json()
            lasttime = pytz.utc.localize(datetime.strptime(r['StatusSNS']['Time'], '%Y-%m-%dT%H:%M:%S')).timestamp()
            if time.time()-lasttime > 10:
                logger.log(f"sml Request data too old {r['StatusSNS']['Time']}")
                for el in list(self.smldat.get_name_list()):
                    self.smldat.update_value(el, None)
            else:
                for el in list(self.smldat.get_name_list()):
                    self.smldat.update_value(el, r['StatusSNS'][''][self.smldat.get_source(el)])
        else:
            logger.log(f"sml Request failed with status code: {response.status_code}")
            for el in list(self.smldat.get_name_list()):
                self.smldat.update_value(el, None)

        self.smldat.write_measurements()


# test stuff
if __name__ == '__main__':

    ts = Tasmotas()

    ts.update_sml()
    #time.sleep(3)
    #ts.update(0)

