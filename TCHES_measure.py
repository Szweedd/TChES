import time
import board
import busio
from adafruit_tca9548a import TCA9548A
import adafruit_sht31d
import minimalmodbus
from datetime import datetime, timedelta
import serial

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

# Inicjalizacja 4 czujników SHT85 na kanałach 0, 1, 2, 3
try:
    sensors[0]= adafruit_sht31d.SHT31D(tca[0]) #Otoczenie
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 0")
    sensors[0] = None
try:
    sensors[1] = adafruit_sht31d.SHT31D(tca[1]) #Sterujacy na potrzeby testow, zwykle Zimny
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

# calibration_offsets = [[1.0, 0.0], [1.8485373400241858, -57.11269923046575], [1.6923853514484328, -42.28769239617964], [1.4856200785013094, -42.771567110695834]] # Offsety kalibracyjne a, b dla każdego czujnika SHT85, gdzie y = a*x + b
calibration_offsets = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [1.0, 0.0]] # Offsety kalibracyjne a, b dla każdego czujnika SHT85, gdzie y = a*x + b
SHT_dict = {0: "Otoczenie", 1: "Sterujacy", 2: "Zimny", 3: "Wylata"}
def read_sensors():
    results = []
    for i in range(len(sensors)):
        try:
            temp = sensors[i].temperature
            hum = sensors[i].relative_humidity*calibration_offsets[i][0] + calibration_offsets[i][1]
            print(f"{SHT_dict.get(i)}: Temperatura: {temp:.2f} °C, Wilgotność: {hum:.2f} %")
            results.extend([temp, hum])
        except Exception as e:
            print(f"Błąd odczytu z czujnika {sensors[i]}: {e}")
            results.extend([None, None])
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
            print(f"Keller {addr}: Ciśnienie: {pressure:.3f} bar")
            pressures.append(pressure)
        except Exception as e:
            pressures.append(None)
    return pressures

if __name__ == "__main__":
    # Nagłówek pliku
    with open(filename, "w") as f:
        f.write("timestamp;SHT85_1_temp;SHT85_1_hum;SHT85_2_temp;SHT85_2_hum;SHT85_3_temp;SHT85_3_hum;Keller_1;Keller_2\n")
       
       
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
                print()
                try:
                    with open(filename, "a") as f:
                        line = f"{timestamp}"
                        for value in sht_data:
                            line += f";{value:.2f}"
                        for value in keller_data:
                            if value is not None:
                                line += f";{value:.2f}"
                            else:
                                line += ";N/A"
                        f.write(line + "\n")
                except Exception as e:
                    print(f"Błąd zapisu do pliku: {e}")
            
