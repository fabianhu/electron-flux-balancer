# the general database magic.

import math
import time
from logger import logger

from influxdb import InfluxDBClient


class MeasurementList:
    def __init__(self, host='127.0.0.1', port=8086, database='home'):
        self.__data = {}
        self.client = InfluxDBClient(host=host, port=port, database=database)

    def add_item(self, name,
                 unit = "",
                 send_min_diff = 0.25,
                 send_max_time = 5*60,
                 filter_time = 60,
                 filter_jump = 0,
                 source = None,
                 filter_std_time = 0,):
        lastTime = time.time()
        self.__data[name] = {'value': None,
                           'value_filtered': None,
                           'unit': unit,
                           'value_last_update_time':lastTime,
                           'send_last_value':None,
                           'send_last_time':lastTime,
                           'send_min_diff':send_min_diff,
                           'send_max_time':send_max_time,
                           'filter_time':filter_time,
                           'filter_jump':filter_jump,
                           'source':source,
                           'filter_std_time':filter_std_time,
                             }
    def get_name_list(self):
        return self.__data.keys()


    # the value is also filtered by the filter_std_time factor.
    def update_value(self, name, new_value):
        if name in self.__data:
            # if self.__data[name]['value'] is None: logger.info(f"Data {name} is None")  # debug
            # take unfiltered?
            if new_value is None or \
                    isinstance(new_value, str) or\
                    self.__data[name]['value'] is None or \
                    self.__data[name]['value_filtered'] is None:

                self.__data[name]['value_last_update_time'] = time.time()
                self.__data[name]['value_filtered'] = new_value
                self.__data[name]['value'] = new_value
            else:
                current_time = time.time()
                delta_time = current_time - self.__data[name]['value_last_update_time']

                alpha_std = delta_time / (self.__data[name]['filter_std_time'] + delta_time)
                v = alpha_std * new_value + (1 - alpha_std) * self.__data[name]['value']
                self.__data[name]['value'] = v # normal filter does not do jumps

                alpha_flt = delta_time / (self.__data[name]['filter_time'] + delta_time)
                vf = alpha_flt * new_value + (1 - alpha_flt) * self.__data[name]['value_filtered']
                if abs(new_value - self.__data[name]['value_filtered']) >= self.__data[name]['filter_jump']:
                    self.__data[name]['value_filtered'] = new_value
                else:
                    self.__data[name]['value_filtered'] = vf

                self.__data[name]['value_last_update_time'] = current_time

        else:
            logger.log(f"{name} does not exist in the data.")


    def get_value(self, name):
        if name in self.__data:
            return self.__data[name]['value']
        else:
            logger.log(f"{name} does not exist in the data.")
            return None

    def get_value_filtered(self, name):
        if name in self.__data:
            return self.__data[name]['value_filtered']
        else:
            logger.log(f"{name} does not exist in the data.")
            return None

    def get_source(self, name):
        if name in self.__data:
            return self.__data[name]['source']
        else:
            logger.log(f"{name} does not exist in the data.")
            return None

    def get_wellformed_array(self):
        # translate into shape, the Influx likes
        r=[]
        for i in self.__data:
            difTime = time.time() - self.__data[i]['send_last_time']

            #decide, if the value can be filtered
            if (type(self.__data[i]['value']) == float or type(self.__data[i]['value']) == int) and self.__data[i]['send_last_value']  is not None:
                # check, if __data has changed enough
                difValue = abs(self.__data[i]['send_last_value'] - self.__data[i]['value'])
                try:
                    if self.__data[i]['value'] is not None and (difValue >= self.__data[i]['send_min_diff'] or difTime >= self.__data[i]['send_max_time']):
                        r.append({
                        "measurement": i,
                        "tags": {"type": self.__data[i]['unit']},
                        "fields": {"value": float(self.__data[i]['value']), # avoid storing as int !!!! - database does not like floats on top of ints.
                                   "value_": float(self.__data[i]['value_filtered'])},
                        })
                        self.__data[i]['send_last_value'] = self.__data[i]['value']
                        self.__data[i]['send_last_time'] = time.time()
                except:
                    logger.log("Database encode FAIL",i,self.__data[i]['value'])

            else:
                # non calculatable stuff
                if self.__data[i]['value'] is not None and (self.__data[i]['send_last_value'] != self.__data[i]['value'] or difTime >= self.__data[i]['send_max_time']):
                    if type(self.__data[i]['value']) == int:
                        nv = float(self.__data[i]['value']) # avoid storing value as int on new DB
                    else:
                        nv = self.__data[i]['value']

                    r.append({
                    "measurement": i,
                    "tags": {"type": self.__data[i]['unit']},
                    "fields": {"value": nv},
                    })
                    self.__data[i]['send_last_value'] = self.__data[i]['value']
                    self.__data[i]['send_last_time'] = time.time()
        return r

    def write_measurements(self):
        self.client.write_points(self.get_wellformed_array())



