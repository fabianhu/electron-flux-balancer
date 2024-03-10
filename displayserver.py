import requests
from lib.logger import Logger
logger = Logger()

url1 = 'http://192.168.1.78/data'
url2 = 'http://192.168.1.80/data'
url_analog = 'http://192.168.1.76/data'


def send_display_request(url,data):
    try:
        response = requests.post(url, data=data, timeout=3)
        # print(response.text)
    except requests.exceptions.ConnectionError as e:
        pass  # no alarm
        # logger.log(f"Display {url} Exception: {e}")
    except Exception as e:
        logger.error(f"Display {url} Exception: {e}")

    '''
        r.raise_for_status() 
except requests.exceptions.HTTPError as errh: 
    print("HTTP Error") 
    print(errh.args[0]) 
except requests.exceptions.ReadTimeout as errrt: 
    print("Time out") 
except requests.exceptions.ConnectionError as conerr: 
    print("Connection error") 
except requests.exceptions.RequestException as errex: 
    print("Exception request") 
    '''

def send_display_analog(url,prc):
    try:
        #import urllib.request
        #contents = urllib.request.urlopen("http://example.com/foo/bar").read()
        url = url + "?prc=" + str(prc)
        response = requests.get(url, data=None, timeout=3)
        print(response.text)
    except requests.exceptions.ConnectionError as e:
        pass  # no alarm
        # logger.log(f"Display {url} Exception: {e}")
    except Exception as e:
        logger.error(f"Display {url} Exception: {e}")

def to_percent(value, min_range, max_range):
        if value is None:
            return 0
        # Ensure that the value is within the specified range
        # value = max(min_range, min(max_range, value))
        # Calculate the percentage
        percentage = (value - min_range) / (max_range - min_range) * 100
        # Ensure that the percentage is within the range 0-100
        percentage = max(-100, min(100, percentage))
        return round(percentage)

def push_displays(Gen_pwr, Export_W, Bat_soc, Bat_pwr, Car_soc, Car_pwr, Heat_soc, Heat_pwr, Price_eur, nil):
    if Export_W is None:
        Export_W = 0
    if Price_eur is None:
        Price_eur = 0

    # todo par

    names = [ "Sol", "Bat", "Car", "Heat", "ct"]
    percent_bar = [to_percent(Gen_pwr,0,10000), Bat_soc, Car_soc, Heat_soc, to_percent(Price_eur, 0.15,0.3)]
    percent_sidebar = [to_percent(Export_W, 0, 5000), to_percent(Bat_pwr, 0,5000), to_percent(Car_pwr, 0,11000), to_percent(Heat_pwr, 0,3000), nil]
    values = [Gen_pwr, Bat_soc, Car_soc, Heat_soc, round(Price_eur*100)]

    data = {}
    for i in range(5):
        data['name' + str(i)] = names[i]
        data['perc' + str(i)] = percent_bar[i]
        data['side' + str(i)] = percent_sidebar[i]
        data['value' + str(i)] = values[i]

    send_display_request(url1, data)
    send_display_request(url2, data)
    send_display_analog(url_analog, to_percent(Bat_soc,8,100)) # todo par



if __name__ == '__main__':
    send_display_analog(url_analog,33)
    #push_displays( 9000, -8000, 75, -4000,30,8000,90,2000,0.15, 0)