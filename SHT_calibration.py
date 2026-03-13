import time
import board
import busio
from adafruit_tca9548a import TCA9548A
import adafruit_sht31d
from datetime import datetime, timedelta

# filename = input("Podaj nazwę pliku do zapisu danych (np. 'dane'):")
filename = "test_rozne_SHT_to_samo_RH_5C_NaCl_"
current_time = datetime.now()
filename += current_time.strftime("%Y-%m-%d_%H_%M_%S")
filename += ".csv"

krok_probkowania = timedelta(seconds = 2)

czas_pomiaru = timedelta(seconds = 0)

# Inicjalizacja magistrali I2C
i2c = busio.I2C(board.SCL, board.SDA)
sensors = [None, None, None, None, None, None]  # Lista do przechowywania czujników SHT85
# Inicjalizacja multipleksera Gravity (TCA9548A)
tca = TCA9548A(i2c)

# Inicjalizacja 6 czujników SHT85 na kanałach 0, 1, 2, 3, 4, 5
try:
    sensors[0]= adafruit_sht31d.SHT31D(tca[0]) #Otoczenie
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 0")
    sensors[0] = None
try:
    sensors[1] = adafruit_sht31d.SHT31D(tca[1]) #Wlata
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 1")
    sensors[1] = None
try:
    sensors[2] = adafruit_sht31d.SHT31D(tca[2]) #Sterujący 
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 2")
    sensors[2] = None
try:
    sensors[3] = adafruit_sht31d.SHT31D(tca[3]) #Wylata
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 3")
    sensors[3] = None
try:
    sensors[4] = adafruit_sht31d.SHT31D(tca[4]) #Zimny
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 4")
    sensors[4] = None
    
try:
    sensors[5] = adafruit_sht31d.SHT31D(tca[5]) #Testowy
except:
    print("Błąd inicjalizacji czujnika SHT85 na kanale 5")
    sensors[5] = None
    

calibration_offsets = [[1.0, 0.0],[1.0, 0.0],[1.0, 0.0],[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]
# calibration_offsets = [[1.0, 0.0], [1.3735487923071448, -26.372142926536362], [1.5677919149868214, -49.98906059130657], [1.1692621358991013, -14.223351567758813]] # Offsety kalibracyjne a, b dla każdego czujnika SHT85, gdzie y = a*x + b
SHT_dict = {0: "Otoczenie",  1: "Wlata", 2: "Sterujący", 3: "Wylata", 4: "Zimny", 5: "Testowy"}
def read_sensors():
    results = []
    for i in range(len(sensors)):
        try:
            temp = sensors[i].temperature
            hum = sensors[i].relative_humidity*calibration_offsets[i][0] + calibration_offsets[i][1]
            print(f"{SHT_dict.get(i)}: Temperatura: {temp:.2f} °C, Wilgotność: {hum:.2f} %")
            results.extend([temp, hum])
        except Exception as e:
            print(f"Błąd odczytu z czujnika {SHT_dict.get(i)}: {e}")
            results.extend([None, None])
    return results


if __name__ == "__main__":
    # Nagłówek pliku
    with open(filename, "w") as f:
        f.write("timestamp;SHT85_0_temp;SHT85_0_hum;SHT85_1_temp;SHT85_1_hum;SHT85_2_temp;SHT85_2_hum;SHT85_3_temp;SHT85_3_hum;SHT85_4_temp;SHT85_4_hum\n")
       
       
        n = 0
        poczatek_pomiaru = datetime.now()
         
        while True:
            
            current_time = datetime.now() 
            czas_pomiaru = current_time - poczatek_pomiaru
            
            if czas_pomiaru >= krok_probkowania * n:
                n+= 1
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                sht_data = read_sensors()
                print()
                try:
                    with open(filename, "a") as f:
                        line = f"{timestamp}"
                        for value in sht_data:
                            line += f";{value:.2f}"
                        f.write(line + "\n")
                except Exception as e:
                    print(f"Błąd zapisu do pliku: {e}")
            
