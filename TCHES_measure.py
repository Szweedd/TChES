import time
import board
import busio
from adafruit_tca9548a import TCA9548A
import adafruit_sht31d
import minimalmodbus
from datetime import datetime, timedelta
import serial
import websocket
import json

filename = input("Podaj nazwę pliku do zapisu danych (np. 'dane'): ")
current_time = datetime.now()
filename += current_time.strftime("%Y-%m-%d_%H_%M_%S")
filename += ".csv"

krok_probkowania = timedelta(seconds = int(input("Podaj krok próbkowania w sekundach (np. 60): ")))

czas_pomiaru = timedelta(seconds = 0)

# Inicjalizacja magistrali I2C
i2c = busio.I2C(board.SCL, board.SDA)
sensors = [None, None, None, None]  # Lista do przechowywania czujników SHT85
# Inicjalizacja multipleksera Gravity (TCA9548A)
tca = TCA9548A(i2c)

# A dictionary of Pico IPs to poll
PICO_NAMES = {
    "10.99.200.50": "Sternik"
}
data_payload = {}  # Shared data structure to hold latest values from picos

# Track last pico tstamp and last reception time separately
last_pico_timestamps = {}      # pico_ip: last tstamp received from pico
last_pico_reception = {}       # pico_ip: parent time.time() when last new data received

STALE_TIMEOUT = 60  # seconds

# Inicjalizacja 4 czujników SHT85 na kanałach 0, 1, 2, 3
try:
    sensors[0]= adafruit_sht31d.SHT31D(tca[0]) #Otoczenie
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 0")
    sensors[0] = None
try:
    sensors[1] = adafruit_sht31d.SHT31D(tca[1]) #Zimny
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 1")
    sensors[1] = None
try:
    sensors[2] = adafruit_sht31d.SHT31D(tca[2]) #Wlata
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 2")
    sensors[2] = None
try:
    sensors[3] = adafruit_sht31d.SHT31D(tca[3]) #Wylata
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 3")
    sensors[3] = None
    
# Inicjalizacja klienta Modbus RTU (minimalmodbus)t
# Uwaga: port, adresy i parametry dostosuj do swoich urządzeń!
keller_addresses = [1, 2]
PRESSURE_REGISTER = 2  # rejestr z ciśnieniem (sprawdź dokumentację Keller)
INSTRUMENT_PORT = '/dev/ttyUSB0'

calibration_offsets = [[1.0, 0.0],[2.0, +100.0],[-10.0, -1000.0],[50.0, -55.0]]
# calibration_offsets = [[1.0, 0.0], [1.3735487923071448, -26.372142926536362], [1.5677919149868214, -49.98906059130657], [1.1692621358991013, -14.223351567758813]] # Offsety kalibracyjne a, b dla każdego czujnika SHT85, gdzie y = a*x + b
SHT_dict = {0: "Otoczenie", 1: "Zimny", 2: "Wlata", 3: "Wylata"}
def read_sensors():
    results = []
    for i in range(len(sensors)):
        try:
            temp = sensors[i].temperature
            hum_raw = sensors[i].relative_humidity
            hum = hum_raw*calibration_offsets[i][0] + calibration_offsets[i][1]
            print(f"{SHT_dict.get(i)}: Temperatura: {temp:.2f} °C, Wilgotność: {hum_raw:.2f} %, Wilgotność_skalibrowana: {hum:.2f} %")
            results.extend([temp, hum_raw, hum])
        except Exception as e:
            print(f"Błąd odczytu z czujnika {SHT_dict.get(i)}: {e}")
            results.extend([None, None, None])
    return results

def read_keller_pressure():
    pressures = []
    for addr in keller_addresses:
        try:
            instrument = minimalmodbus.Instrument(INSTRUMENT_PORT, addr)
            instrument.serial.baudrate = 9600        # lub 19200 – zależy od konfiguracji urządzenia
            instrument.serial.bytesize = 8
            instrument.serial.parity   = serial.PARITY_NONE
            instrument.serial.stopbits = 1
            instrument.serial.timeout  = 1    
            # Odczyt 2 rejestrów jako float (32-bit, big-endian)
        
            pressure = instrument.read_float(2, functioncode=3, number_of_registers=2, byteorder=minimalmodbus.BYTEORDER_BIG)
            print(f"Keller {addr}: Ciśnienie: {pressure:.4f} bar")
            pressures.append(pressure)
        except Exception as e:
            print(f"Błąd odczytu z Keller {addr}: {e}")
            pressures.append(None)
    return pressures

def poll_picos():  
    now = time.time()
    pico_data = None
    for ip in PICO_NAMES:
        try:
            uri = f"ws://{ip}:5000/ws"
            ws = websocket.create_connection(uri)
            pico_data_raw = json.loads(ws.recv())
            pico_data = {"T": pico_data_raw["T0"], "RH": pico_data_raw["RH0"]}
            print(pico_data)
            return pico_data
                    
            # for msg in ws:
            #     pico_data = json.loads(msg)
            #     pico_ts = pico_data.get("tstamp")
            #     if pico_ts is not None:
            #         # Only update if pico's tstamp is new
            #         if last_pico_timestamps.get(ip) != pico_ts:
            #             last_pico_timestamps[ip] = pico_ts
            #             last_pico_reception[ip] = now  # Mark when RP received new data
            #             expected_keys = ["Temperature", "RH"]
            #             if all(key in pico_data for key in expected_keys):
            #                 data_payload["T_stamp"] = pico_ts
            #                 for key in pico_data:
            #                     data_payload[key] = {pico_data[key]}

            #                 # data_payload[expected_keys] = pico_data[expected_keys]
            #                 # data_payload[f"T_stamp_{PICO_NAMES[ip]}"] = pico_ts
            #                 # print(f"Updated {expected_keys}: {pico_data[expected_keys]} (pico ts={pico_ts})")
            #             else:
            #                 print(f"Expected keys {expected_keys} not in pico data: {pico_data}")
            #         else:
            #             print(f"No new data from {ip} (pico timestamp unchanged)")
            #     else:
            #         print(f"No timestamp in data from {ip}")
        except Exception as e:
            print(f"Error polling {ip}: {e}")
    # Mark data as stale if RP hasn't received new data in STALE_TIMEOUT seconds
    for ip in PICO_NAMES:
        last_recv = last_pico_reception.get(ip)
        if last_recv is not None and (now - last_recv) > STALE_TIMEOUT:
            print(f"Data from {ip} is stale (last new data received {now - last_recv:.1f} seconds ago)")
            pico_data = None
            # for key in pico_data:
            #     data_payload[key] = None
    return pico_data



if __name__ == "__main__":
    # Nagłówek pliku
    with open(filename, "w") as f:
        f.write("timestamp;SHT85_1_temp;SHT85_1_hum_raw;SHT85_1_hum;SHT85_2_temp;SHT85_2_hum_raw;SHT85_2_hum;SHT85_3_temp;SHT85_3_hum_raw;SHT85_3_hum;SHT85_4_temp;SHT85_4_hum_raw;SHT85_4_hum;Keller_1;Keller_2\n")
              
        n = 0
        poczatek_pomiaru = datetime.now()
         
        while True:
            
            current_time = datetime.now() 
            czas_pomiaru = current_time - poczatek_pomiaru
            
            if czas_pomiaru >= krok_probkowania * n:
                n+= 1
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                sht_data = read_sensors()
                keller_data = read_keller_pressure()
                pico_data = poll_picos()
                try:
                    with open(filename, "a") as f:
                        line = f"{timestamp}"
                        for value in sht_data:
                            line += f";{value:.2f}"
                        for value in keller_data:
                            if value is not None:
                                line += f";{value:.4f}"
                            else:
                                line += ";N/A"
                        for value in pico_data:
                            if value is not None:
                                line += f";{value:.2f}"
                        f.write(line + "\n")
                except Exception as e:
                    print(f"Błąd zapisu do pliku: {e}")
        
