import requests
from lib.logger import Logger
logger = Logger()

url1 = 'http://192.168.1.78/data'
url2 = 'http://192.168.1.80/data'

names = [ "Gen", "nil", "Bat", "BatP", "Car", "CarP", "Heat", "HeatP", "Exp", "Eur"]

def send_display_request(url,data):
    try:
        response = requests.post(url, data=data, timeout=3)
        # print(response.text)
    except requests.exceptions.ConnectionError as e:
        pass  # no alarm
        # logger.log(f"Display {url1} Exception: {e}")
    except Exception as e:
        logger.log(f"Display {url} Exception: {e}")

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


def push_displays(Gen_pwr, Bat_soc, Bat_pwr, Car_soc, Car_pwr, Heat_soc, Heat_pwr, Export_W, Price_eur):
    if Export_W is None:
        Export_W = 0
    if Price_eur is None:
        Price_eur = 0
    values = [Gen_pwr, 0, Bat_soc, Bat_pwr, Car_soc, Car_pwr, Heat_soc, Heat_pwr, Export_W, Price_eur]
    data = {}
    for i in range(10):
        data['name' + str(i)] = names[i]
        data['value' + str(i)] = values[i]

    send_display_request(url1, data)
    send_display_request(url2, data)



if __name__ == '__main__':
    push_displays( 50, 75,-75,60,30,100,33,50,0.15)