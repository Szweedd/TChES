import time
import board
import busio
from adafruit_tca9548a import TCA9548A
import adafruit_sht31d
from datetime import datetime, timedelta

# filename = input("Podaj nazwę pliku do zapisu danych (np. 'dane'):")
filename = "test_rozne_SHT_to_samo_RH_1_15C_NaCl_"
# filename = "test_regeneracja_SHT_15C_NaCl_0_3_stare_4_7_regenerowane"
path = "/home/zdalny_dostep/SHT_Calibration/TChES/"
current_time = datetime.now()
filename += current_time.strftime("%Y-%m-%d_%H_%M_%S")
filename += ".csv"

krok_probkowania = timedelta(seconds = 2)

czas_pomiaru = timedelta(seconds = 0)

# Inicjalizacja magistrali I2C
i2c = busio.I2C(board.SCL, board.SDA)
sensors = 8*[None]  # Lista do przechowywania czujników SHT85
# Inicjalizacja multipleksera Gravity (TCA9548A)
tca = TCA9548A(i2c)

# Inicjalizacja czujników SHT85 na kanałach 0-7 multipleksera
for i in range(len(sensors)):
    try:
        sensors[i] = adafruit_sht31d.SHT31D(tca[i]) 
    except:
        print(f"Błąd inicjalizacji czujnika SHT85 na kanale {i}")
        sensors[i] = None
# try:
#     sensors[1] = adafruit_sht31d.SHT31D(tca[1]) #Sterujący 
# except:
#     print("Błąd inicjalizacji czujnika SHT85 na kanale 1")
#     sensors[1] = None
# try:
#     sensors[3] = adafruit_sht31d.SHT31D(tca[3]) #Wylata
# except:
#     print("Błąd inicjalizacji czujnika SHT85 na kanale 3")
#     sensors[3] = None
# try:
#     sensors[4] = adafruit_sht31d.SHT31D(tca[4]) #Zimny
# except:
#     print("Błąd inicjalizacji czujnika SHT85 na kanale 4")
#     sensors[4] = None
    
# try:
#     sensors[5] = adafruit_sht31d.SHT31D(tca[5]) #Testowy
# except:
#     print("Błąd inicjalizacji czujnika SHT85 na kanale 5")
#     sensors[5] = None
    

calibration_offsets = 8*[[1.0,0.0]]

SHT_dict = {0: "Wlata", 1: "Sterujący", 2: "Wylata", 3: "Zimny", 4: "Kiełek", 5: "Świeżak", 6: "Szczypior", 7: "Młody"}
def read_sensors():
    results = []
    for i in range(0,len(sensors)):
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
    with open(path + filename, "w") as f:
        f.write("timestamp;SHT85_0_temp;SHT85_0_hum;SHT85_1_temp;SHT85_1_hum;SHT85_2_temp;SHT85_2_hum;SHT85_3_temp;SHT85_3_hum;SHT85_4_temp;SHT85_4_hum;SHT85_5_temp;SHT85_5_hum;SHT85_6_temp;SHT85_6_hum;SHT85_7_temp;SHT85_7_hum\n")
       
       
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
                    with open(path + filename, "a") as f:
                        line = f"{timestamp}"
                        for value in sht_data:
                            if value is not None:
                                line += f";{value:.2f}"
                            else:
                                line += ";N/A"
                        f.write(line + "\n")
                except Exception as e:
                    print(f"Błąd zapisu do pliku: {e}")
            
