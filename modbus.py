import serial
import struct
from lib.logger import Logger
logger = Logger()

# Define the hex string to send to the Modbus RTU device

### the 2 relay board from Aldeepen Shop, bestep brand
# hex_string = "00 10 00 00 00 01 02 00 XX Set the device address to XX
# hex_string = "FF 10 00 03 00 02 04 00 04 00 32"  # rel 1 for 5s (0x32 = 50 *0.1s)
# hex_string = "FF 10 00 08 00 02 04 00 04 00 32"  # rel 2 for 5s (0x32 = 50 *0.1s)
# hex_string = "FF 0F 00 00 00 08 01 FF" # Turn on all relays
# hex_string = "FF 0F 00 00 00 08 01 00" # Turn off all relays
# hex_string = "FF 05 00 00 FF 00" # Turn on the No. 1 relay (manual mode)
# hex_string = "FF 05 00 00 00 00" # Turn off the No. 1 relay (manual mode)
# hex_string = "FF 05 00 01 FF 00" # Turn on the No. 2 relay (manual mode)
# hex_string = "FF 05 00 01 00 00" # Turn off the No. 2 relay (manual mode)
# hex_string = "FF 01 00 00 00 08" # Read the relay status -> ff 01 01 SS XX XX
# hex_string = "FF 02 00 00 00 08" # Read the opto status  -> ff 01 01 SS XX XX


### the 7 NTC temperature measurement board
# "01 03 00 00 00 07" #read 7 temperatures
# "01 03 00 08 00 07" #read 7 temperature correction values
# "01 06 00 08 AA AA" #write first temperature correction value
# "01 03 00 FE 00 ff" #read modbus address
# "01 06 00 FE 00 AA" #write modbus address AA 1-247

debug = False


def _int_to_hex16(num):
    return '{:04x}'.format(num & 0xffff)


def _crc(msg: bytes) -> int:
    crc = 0xFFFF
    for n in range(len(msg)):
        crc ^= msg[n]
        for i in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc


def _checkcrc(msg: bytes) -> bool:
    crc = _crc(msg[:-2]).to_bytes(2, "little")
    return crc == msg[-2:]


def _unpack_bytes_to_ints(data):
    num_ints = (len(data) - 1) // 2
    # Unpack the byte array into an array of 16-bit signed integers
    int_array = struct.unpack('>{}h'.format(num_ints), data[1:])
    return int_array


class Bus:
    def __init__(self, device):
        self.device = device
        if debug: logger.info(f"init bus {device}")

    def send_request(self, hex_string):
        if debug: logger.info(">" + hex_string)
        data = bytearray.fromhex(hex_string)  # Convert the hex string to bytes
        crc = _crc(data)  # Calculate the CRC of the _data
        data += crc.to_bytes(2, byteorder='little', signed=False)  # Append the CRC to the _data
        # Open a serial connection to the Modbus RTU device
        try:
            ser = serial.Serial(port=self.device, baudrate=9600, parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=0.15)
            ser.write(data)  # Send the _data to the Modbus RTU device
            response = ser.read(1000)  # Read the response from the Modbus RTU device
            ser.close()  # Close the serial connection
        except:
            logger.log("Modbus RTU - Serial Port init error")
            return ""

        shortponse = response[:-2]
        response_hex = ' '.join('{:02x}'.format(b) for b in shortponse)

        # Print the response in hex
        if _checkcrc(response):
            if debug: logger.info("<" + response_hex)  # [:-2])
            # if debug: logger.info(unpack_bytes_to_ints(shortponse))
            return shortponse[2:]
        else:
            if debug: logger.info("CRC error", response_hex)
            return ""


class Device:
    def __init__(self, bus, address):
        self.bus = bus
        self.address = address


class Nt18b07TemperatureIn(Device):
    # eletechsup NT18B07
    values = [None] * 7

    def get_temperatures(self):
        ret = self.bus.send_request('{:02x}'.format(self.address) + "03 00 00 00 07")  # read a fixed number of 7 data
        if ret is not None and len(ret) == 15:
            # unpack and check for value > -100
            unpacked_values = _unpack_bytes_to_ints(ret)
            self.values = [float(i) / 10 if i >= -1000 else None for i in unpacked_values]
            # self.values = [float(i)/10 for i in _unpack_bytes_to_ints(ret)]
        else:
            self.values = [None] * 7

    def get_cal(self):
        ret = self.bus.send_request('{:02x}'.format(self.address) + "03 00 08 00 07")
        if ret is not None and len(ret) == 15:
            return [float(i) / 10 for i in _unpack_bytes_to_ints(ret)]

    def set_cal(self, chan, value):
        # "01 06 00 08 AA AA" #write first temperature correction value
        value = int(value * 10)
        hex_string = '{:02x}'.format(self.address) + "06 00 " + '{:02x}'.format(chan + 8) + _int_to_hex16(value)
        self.bus.send_request(hex_string)

    def set_addr(self):
        # "01 06 00 FE 00 AA" #write modbus address AA 1-247
        hex_string = "00 06 00 FE 00 " + '{:02x}'.format(self.address)
        self.bus.send_request(hex_string)
        if debug: logger.info("Address " + self.address + " set. - " + hex_string)


class Bestep2Relays(Device):
    # ACHTUNG pay attention, what numbers you send as a channel!
    last_status = None
    last_input = None

    def off(self, num=0):
        if debug: logger.info("off")
        if num == 0:
            hex_string = '{:02x}'.format(self.address) + "0F 00 00 00 08 01 00"  # Turn off all relays
        else:
            hex_string = '{:02x}'.format(self.address) + "05 00 " + '{:02x}'.format(
                num - 1) + " 00 00"  # Turn on the No. x relay (manual mode)
        self.bus.send_request(hex_string)

    def on(self, num=0, timeout=0):
        if debug: logger.info("on")
        if num == 0:
            if debug: logger.info('switch on all relays at once')
            hex_string = '{:02x}'.format(self.address) + "0F 00 00 00 08 01 FF"  # Turn on all relays
            self.bus.send_request(hex_string)
        elif timeout == 0:
            # hex_string = '{:02x}'.format(addr) + "05 00 00 FF 00" # Turn on the No. 1 relay (manual mode)
            # hex_string = '{:02x}'.format(addr) + "05 00 01 FF 00" # Turn on the No. 2 relay (manual mode)
            hex_string = '{:02x}'.format(self.address) + "05 00 " + '{:02x}'.format(
                num - 1) + " FF 00"  # Turn on the No. x relay (manual mode)
            self.bus.send_request(hex_string)
        else:
            relay_addresses = [0x0003, 0x0008, 0x000d, 0x0012, 0x0017, 0x001c, 0x0021, 0x0026]
            relay_address = relay_addresses[num - 1]
            # hex_string = '{:02x}'.format(addr) + "10 00 03 00 02 04 00 04 00 32"  # rel 1 for 5s (0x32 = 50 *0.1s)
            # hex_string = '{:02x}'.format(addr) + "10 00 03 00 02 04 00 02 00 1E" UUUUh
            if timeout > 6553:
                logger.log(f"timeout for Relais too long!, {timeout}")
                return
            hex_string = '{:02x}'.format(self.address) + "10 00 " + '{:02x}'.format(
                relay_address) + " 00 02 04 00 04" + '{:04x}'.format(int(timeout * 10))
            self.bus.send_request(hex_string)

    def get_status(self):
        if debug: logger.info("get status")
        ret = self.bus.send_request('{:02x}'.format(self.address) + "01 00 00 00 08")
        if ret is not None and len(ret) == 2:
            self.last_status = [(ret[-1] >> i) & 1 for i in range(8)]
        else:
            self.last_status = None
        return self.last_status
        # hex_string = "FF 01 00 00 00 08" # Read the relay status -> ff 01 01 SS XX XX

    def get_input(self):
        if debug: logger.info("get input")
        ret = self.bus.send_request('{:02x}'.format(self.address) + "02 00 00 00 08")
        if ret is not None and len(ret) == 2:
            self.last_input = [(ret[-1] >> i) & 1 for i in range(8)]
        else:
            self.last_input = None
        return self.last_input
        # hex_string = "FF 02 00 00 00 08" # Read the opto status  -> ff 01 01 SS XX XX

    def set_addr(self):
        # hex_string = "00 10 00 00 00 01 02 00 XX Set the device address to XX
        hex_string = "00 10 00 00 00 01 02 00 " + '{:02x}'.format(self.address)
        self.bus.send_request(hex_string)
        if debug: logger.info("set Address " + self.address + " set. - " + hex_string)
