# Sungrow modbus TCP interface
# works with SH10RT
import datetime
import logging
import lib.intervaltask
from pymodbus.client import ModbusTcpClient
from lib.measurementlist import MeasurementList
from lib.logger import Logger
logger = Logger(log_level=logging.ERROR, log_path="sungrow.log")

def checked_multiply(a,b):
    if a is not None and b is not None:
        return a*b
    else:
        return None

class SungrowSH:
    def __init__(self, ip, port):
        self.init_thread_id = None
        self.call_counter = 0
        logger.info(f"Start SungrowSH, {ip}")

        self.measurements = MeasurementList()
        self.client = ModbusTcpClient(ip, port, timeout=2, retries=1)

        self.forced_charge = 0 # remember the last forced charge state to avoid sending all the time. init with zero, as this requires reactivation. 

        r = self.client.read_input_registers(address=4949, count=2 + 2 + 15 + 15, slave=1)  # 4968
        ver = ''.join(f' {reg:04x}' for reg in r.registers[0:4])
        sw_ARM = extract_string_from_data(r.registers, 4, 15)
        sw_DSP = extract_string_from_data(r.registers, 4 + 15, 15)

        logger.info(f"SungrowSH, {ver}, {sw_ARM}, {sw_DSP}")
        with open("sungrow_version.txt", "a") as f: f.write(f"{datetime.datetime.now()} SungrowSH, {ver}, {sw_ARM}, {sw_DSP}\n")

        self.measurements.add_item(name='ELE Nominal Output Power', unit="W", send_min_diff=10.0, filter_time=30, filter_jump=2000, source={'address': 5000, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Inside Temperature', unit='°C', send_min_diff=0.5, filter_time=30, filter_jump=5, source={'address': 5007, 'data_type': 'int16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE MPPT 1 Voltage', unit='V', send_min_diff=1.0, filter_time=30, filter_jump=10, source={'address': 5010, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE MPPT 1 Current', unit='A', send_min_diff=0.1, filter_time=30, filter_jump=1, source={'address': 5011, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE MPPT 2 Voltage', unit='V', send_min_diff=1.0, filter_time=30, filter_jump=10, source={'address': 5012, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE MPPT 2 Current', unit='A', send_min_diff=0.1, filter_time=30, filter_jump=1, source={'address': 5013, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Total DC Power', unit='W', send_min_diff=10.0, filter_time=30, filter_jump=2000 ,source={'address': 5016, 'data_type': 'uint32sw', 'factor': 1})
        self.measurements.add_item(name='ELE Phase A Voltage', unit='V', send_min_diff=0.1, filter_time=30, filter_jump=5, source={'address': 5018, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Phase B Voltage', unit='V', send_min_diff=0.1, filter_time=30, filter_jump=5, source={'address': 5019, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Phase C Voltage', unit='V', send_min_diff=0.1, filter_time=30, filter_jump=5, source={'address': 5020, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Grid Frequency', unit='Hz', send_min_diff=0.01, filter_time=30, filter_jump=1, source={'address': 5035, 'data_type': 'uint16be', 'factor': 0.01})

        self.measurements.add_item(name='ELE Load power', unit='W', send_min_diff=10.0, filter_time=30, filter_jump=2000, source={'address': 13007, 'data_type': 'uint32sw', 'factor': 1})
        self.measurements.add_item(name='ELE Export power', unit='W', send_min_diff=10.0, filter_time=30, filter_jump=2000, source={'address': 13009, 'data_type': 'int32sw', 'factor': 1})
        self.measurements.add_item(name='ELE Battery voltage', unit='V', send_min_diff=5.0, filter_time=30, filter_jump=10, source={'address': 13019, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Battery power', unit='W', send_min_diff=10.0, filter_time=30, filter_jump=2000,  source={'address': 13021, 'data_type': 'uint16be', 'factor': 1})
        self.measurements.add_item(name='ELE Battery level', unit='%', send_min_diff=1.0, filter_time=30, filter_jump=3, source={'address': 13022, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Battery state of health', unit='%', send_min_diff=1.0, filter_time=30, filter_jump=1, source={'address': 13023, 'data_type': 'uint16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Battery Temperature', unit='°C', send_min_diff=1.0, filter_time=30, filter_jump=2, source={'address': 13024, 'data_type': 'int16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Phase A Current', unit='A', send_min_diff=0.1, filter_time=30, filter_jump=1,  source={'address': 13030, 'data_type': 'int16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Phase B Current', unit='A', send_min_diff=0.1, filter_time=30, filter_jump=1, source={'address': 13031, 'data_type': 'int16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Phase C Current', unit='A', send_min_diff=0.1, filter_time=30, filter_jump=1, source={'address': 13032, 'data_type': 'int16be', 'factor': 0.1})
        self.measurements.add_item(name='ELE Total active power', unit='W', send_min_diff=10.0, filter_time=30, filter_jump=2000, source={'address': 13033, 'data_type': 'int32sw', 'factor': 1})

        # add extra elements - calculated with this code
        self.measurements.add_item(name="ELE String S power", unit="W", filter_time=30, filter_jump=1000, send_min_diff=10)
        self.measurements.add_item(name="ELE String N power", unit="W", filter_time=30, filter_jump=1000, send_min_diff=10)
        self.measurements.add_item(name="ELE Battery power c", unit="W", filter_time=30, filter_jump=1000, send_min_diff=10)


    # decode the data into the measurements-array using the addresses provided in source.
    def decode_array(self, data, startaddress):
        minaddr = startaddress
        maxaddr = startaddress + len(data)

        all_zero = True
        for element in data:
            if element != 0:
                all_zero = False
                break
        if all_zero:
            logger.error("All elements are zero")  # Thanks Sungrow!
            return

        # proceed through address list and fissle out the data from the data.
        for i in self.measurements.get_name_list():
            if self.measurements.get_source(i) is not None and \
                    minaddr <= self.measurements.get_source(i)['address'] <= maxaddr:
                index = self.measurements.get_source(i)['address'] - minaddr
                data_type = self.measurements.get_source(i)['data_type']

                decoded = None
                if data_type == 'int8be':
                    decoded = data[index]
                if data_type == 'int16be':
                    decoded = data[index]
                elif data_type == 'uint16be':
                    decoded = data[index] if data[index] < 32768 else data[index] - 65536
                elif data_type == 'int32sw':
                    decoded = (data[index + 1] << 16) | (data[index] & 0xFFFF)
                    if decoded >= 2147483648:  # Check if the value is negative
                        decoded -= 4294967296  # Convert to signed 32-bit value
                elif data_type == 'uint32sw':
                    decoded = (data[index + 1] << 16) | (data[index] & 0xFFFF)

                if decoded is None:
                    logger.error(f"Sungrow decoding error, {data_type}, {i}")
                else:
                    scaled = decoded * self.measurements.get_source(i)['factor']
                    self.measurements.update_value(i, scaled)

    @lib.intervaltask.intervaltask.thread_alert
    def update(self, _test=False):
        try:
            # Connect to the device - connection closed in "finally"
            self.client.connect()
        except Exception as e:
            logger.error(f'Modbus TCP connect {type(e)}: {e}')
            return

        try:
            if self.call_counter == 0:
                # Call the first set of registers to read and process
                self.read_and_process_registers(4999, 5036 - 4999 + 2)
                self.call_counter = 1
            elif self.call_counter == 1:
                # Call the second set of registers to read and process
                self.read_and_process_registers(13007, 13038 - 13007 + 2)
                self.call_counter = 0

        except Exception as e:
            logger.error(f'Modbus TCP error: {type(e)}: {e}')


        finally:
            # Close the connection in any case - done also at a return!
            self.client.close()

        # calculated values:
        self.measurements.update_value('ELE String S power', checked_multiply(self.measurements.get_value('ELE MPPT 1 Voltage') , self.measurements.get_value('ELE MPPT 1 Current')))
        self.measurements.update_value('ELE String N power', checked_multiply(self.measurements.get_value('ELE MPPT 2 Voltage') , self.measurements.get_value('ELE MPPT 2 Current')))
        tdc = self.measurements.get_value('ELE Total DC Power')
        tap = self.measurements.get_value('ELE Total active power')
        if tdc is not None and tap is not None:
            self.measurements.update_value('ELE Battery power c', tdc - tap) # yes, this is provided by the inverter, but it is always positive! (There is another possibility to use the status word and calculate the sign using this, but this comment is already getting out of hand....)

        if not _test: self.measurements.write_measurements()


    enable_log = False # log all (expected) modbus errors

    @lib.intervaltask.intervaltask.thread_alert
    def read_and_process_registers(self, start, count):
        # yes, a lot of hardcoded numbers in here.
        try:
            result = self.client.read_input_registers(start, count=count, slave=1)
            if result.isError():
                logger.error(f"Modbus TCP error: {result}")
                return
            registers = result.registers

            if start == 4999:
                if registers[0] != 0x0E0F:
                    if self.enable_log: logger.error("Modbus-TCP: Not the correct ID")
                    hex_string = ''.join(f'{reg:04x} ' for reg in registers)
                    if self.enable_log: logger.info(f"Modbus-TCP: malformed data {start} (hex): {hex_string}")
                    return
                if registers[5000-start] != 100:
                    if self.enable_log: logger.error("Modbus-TCP: Nominal output power is not as expected")
                    hex_string = ''.join(f'{reg:04x} ' for reg in registers)
                    if self.enable_log: logger.info(f"Modbus-TCP: malformed data {start} (hex): {hex_string}")
                    return
                if registers[5007-start] == 0:
                    if self.enable_log: logger.error("Modbus-TCP: internal temperature is Zero")
                    hex_string = ''.join(f'{reg:04x} ' for reg in registers)
                    if self.enable_log: logger.info(f"Modbus-TCP: malformed data {start} (hex): {hex_string}")
                    return

                self.decode_array(registers, start)

            elif start == 13007:
                if registers[13038 - start] != 960:
                    if self.enable_log: logger.error("Modbus-TCP: Received not my battery capacity")
                    hex_string = ''.join(f'{reg:04x} ' for reg in registers)
                    if self.enable_log: logger.info(f"Modbus-TCP: malformed data {start + count - 1} (hex): {hex_string}")
                    return
                if 950 > registers[13023 - start] > 1000:
                    if self.enable_log: logger.error("Modbus-TCP: Battery SOH not as expected.")
                    hex_string = ''.join(f'{reg:04x} ' for reg in registers)
                    if self.enable_log: logger.info(f"Modbus-TCP: malformed data {start + count - 1} (hex): {hex_string}")
                    return

                self.decode_array(registers, start)
        except Exception as e:
            logger.error(f'Modbus TCP error {type(e)}: {e}')

    @lib.intervaltask.intervaltask.thread_alert
    def set_forced_charge(self, _power):
        """
        Command the battery to charge or discharge with set power.
        Only writes, if different from actual setting.
        :param _power: Charge Watts. Negative is discharge. None is back to work.
        :return:
        """
        if self.forced_charge == _power:  # avoid execution, when wanted status is equal to the desired state.
            return

        try:
            self.client.connect()
        except Exception as e:
            logger.error(f'Modbus TCP connect {type(e)}: {e}')
            return
        else:
            # write power command - but only if it has changed!
            try:
                r = self.client.read_holding_registers(13049, 3, 1)
                if not hasattr(r, 'registers'):
                    logger.error(f"Modbus read error on set charge to {_power} W")
                    return

                read_registers = r.registers
                """
                13049: EMS mode selection
                    0: Self-consumption mode (Default);
                    2: Forced mode(charge/discharge/stop);
                    3: External EMS mode
                13050: Charge/discharge command
                    0xAA: Charge;
                    0xBB: Discharge;
                    0xCC: Stop ( Default );
                13051: Charge/discharge power [W] 0-5000
                 """
                if _power is None:
                    # normal op at None values
                    log_info_txt="Battery set to normal operation"
                    set_registers = [0, 0xCC, 0]
                elif _power == 0:
                    # stop
                    log_info_txt=f"Battery set to stop operation"
                    set_registers = [2, 0xCC, 0]
                elif 5000 >= _power > 0:
                    # charge
                    log_info_txt=f"Battery set to charge operation with {_power} W"
                    set_registers = [2, 0xAA, abs(_power)]
                elif -5000 <= _power < 0:
                    # discharge
                    log_info_txt=f"Battery set to discharge operation with {_power} W"
                    set_registers = [2, 0xBB, abs(_power)]
                else:
                    logger.error(f"Battery power request out of range with {_power} W!")
                    # normal op at abnormal values
                    log_info_txt="Battery set to normal operation on error"
                    set_registers = [0, 0xCC, 0]
                    _power = None

                if set_registers != read_registers:
                    logger.info(log_info_txt)
                    self.client.write_registers(13049, set_registers, 1)

                    ''' for i in range(3):
                        if set_registers[i] != read_registers[i]:
                            self.client.write_register(13049+i, set_registers[i] , 1)'''
                    self.forced_charge = _power

            except Exception as e:
                logger.error(f'Modbus write error on set charge {type(e)}: {e}')
                return

    @lib.intervaltask.intervaltask.thread_alert
    def set_soc_reserve(self,prc):
        """
        Set SOC reserve for battery
        :param prc: Percentage
        :return: -
        """
        # set the minimum state of charge during grid operation
        if prc < 5:
            prc = 5
            logger.warning(f'Set discharge min SOC to 5 %, not {prc} %, which is lower than allowed!')
        elif prc < 10:
            logger.warning(f'Set discharge min SOC to {prc} %, which is lower than recommended!')
        try:
            self.client.connect()
        except Exception as e:
            logger.error(f'Modbus TCP connect {type(e)}: {e}')
            return
        else:
            r = self.client.read_holding_registers(13099, 1, 1)
            if not hasattr(r, 'registers'):
                logger.error(f"Modbus read error on set soc reserve to {prc}")
                return
            soc = r.registers[0]
            if soc != prc:
                # write power command
                try:
                    self.client.write_register(13099, prc, 1)
                    logger.info(f'Battery discharge min SOC set to {prc} %')
                except Exception as e:
                    logger.error(f'Modbus write error {type(e)}: {e}')
                    return


def extract_string_from_data(data, position, length):
    # Extract bytes for the string
    string_bytes = []
    for i in range(position , (position + length) ):
        byte1 = (data[i] >> 8) & 0xFF  # Extract upper 8 bits
        byte2 = data[i] & 0xFF  # Extract lower 8 bits
        if byte1 == 0:
            break  # Zero termination found
        string_bytes.append(byte1)
        if byte2 == 0:
            break  # Zero termination found
        string_bytes.append(byte2)

    # Convert the bytes to a string
    extracted_string = ''.join([chr(byte) for byte in string_bytes])
    return extracted_string


# test stuff, if run directly (PC!)
if __name__ == '__main__':
    from config import sungrow_test_ip

    logger.logger.setLevel(logging.DEBUG)

    sg = SungrowSH(sungrow_test_ip, 502)
    #sg.update(_test=True)
    #sg.update(_test=True) # call twice to process all data!

    #sg.set_forced_charge(None)
    sg.set_soc_reserve(10)

    '''r= sg.client.read_holding_registers(13049,3,1)
    registers = r.registers
    hex_string = ''.join(f' {reg:04x} ' for reg in registers)
    dec_string = ''.join(f'{reg:05} ' for reg in registers)
    print(f"Data value (hex): {hex_string}")
    print(f"Data value (dec): {dec_string}")'''

    '''

    cl = ModbusTcpClient(sungrow_test_ip, 502)
    cl.connect()
    r = cl.read_input_registers(address=13029, count=20, slave=1) #  4968
    registers = r.registers
    hex_string = ''.join(f' {reg:04x} ' for reg in registers)
    dec_string = ''.join(f'{reg:05} ' for reg in registers)
    print(f"Data value (hex): {hex_string}")
    print(f"Data value (dec): {dec_string}")

    utf8_string = ''.join([struct.pack('>H', reg).decode('utf-16be').encode('utf-8').decode('utf-8') for reg in registers])
    print(f"Data value (UTF-8): {utf8_string}")

    bytes_list = [byte for reg in registers for byte in struct.pack('>H', reg)]
    byte_string = ' '.join([f'{byte:02x}' for byte in bytes_list])
    print(f"Data value (bytes): {byte_string}")
    byte_string = ' '.join([f'{byte:03}' for byte in bytes_list])
    print(f"Data value (bytes): {byte_string}")

    ascii_characters = ''.join([chr(byte) for reg in registers for byte in struct.pack('>H', reg)])
    print(f"Data value (ASCII characters): {ascii_characters}")

  
    # cl.write_register(13086, 0x55, 1) # no limit - did not werk

    
  
    r = cl.read_holding_registers(address=13099, count=10, slave=1)
    registers = r.registers
    hex_string = ''.join(f' {reg:04x} ' for reg in registers)
    dec_string = ''.join(f'{reg:05} ' for reg in registers)
    print(f"Data value (hex): {hex_string}")
    print(f"Data value (dec): {dec_string}")
    
    
    13049: EMS mode selection
            0: Self-consumption mode (Default);
            2: Forced mode(charge/discharge/stop);
            3: External EMS mode
    13050: Charge/discharge command
            0xAA: Charge;
            0xBB:Discharge;
            0xCC: Stop ( Default );
    13051: Charge/discharge power [W] 0-5000
            
            
    13057 Max SOC 0.1% (returns 1000 = 100%)
    
    13058 Min SOC 0.1% (returns 50 = 5%) fixme this is not true, as the controller setting is 15% !
    
    13073 Export Power Limitation W 0 = nominal power
    
    13086 Export Power Limitation
            0xAA : Enable
            0x55 : Disable
    
    13099 Reserved SOC for backup  0~100%
    '''
