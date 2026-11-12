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
import urllib.request

filename = input("Podaj nazwę pliku do zapisu danych (np. 'dane'): ")
current_time = datetime.now()
filename += current_time.strftime("%Y-%m-%d_%H_%M_%S")
filename += ".csv"

krok_probkowania = timedelta(seconds = int(input("Podaj krok próbkowania w sekundach (np. 60): ")))

# Automatyczne zakończenie pomiaru, gdy |T_wylot - T_wlot| < DT_PROG.
# Warunek jest "uzbrajany" dopiero, gdy |dT| raz przekroczy próg (na starcie dT ~ 0),
# a pomiar kończy się po DT_LICZBA_ODCZYTOW kolejnych odczytach poniżej progu (odporność na szum).
DT_PROG = 1.5  # °C
DT_LICZBA_ODCZYTOW = 2
DT_UZBROJENIE = 3.0             # °C - |dT| musi raz osiągnąć tę wartość (lub DT_PROG + 1, jeśli wyższe), zanim zadziałają ostrzeżenie i koniec pomiaru
DT_MARGINES_OSTRZEZENIA = 0.5   # °C - ostrzeżenie, gdy |dT| < DT_PROG + margines
koniec_bliski = False  # Flaga, czy wysłano już powiadomienie o zbliżającym się końcu pomiaru
prog_input = input(f"Podaj próg |dT| zakończenia pomiaru w °C (Enter = {DT_PROG}): ").strip()
if prog_input:
    DT_PROG = float(prog_input.replace(",", "."))

czas_pomiaru = timedelta(seconds = 0)

# Inicjalizacja magistrali I2C
i2c = busio.I2C(board.SCL, board.SDA)
sensors = [None, None, None, None]  # Lista do przechowywania czujników SHT85
# Inicjalizacja multipleksera Gravity (TCA9548A)
tca = TCA9548A(i2c)

# A dictionary of Pico IPs to poll
PICO_NAMES = {
    # "10.99.200.50": "Sternik",
    "192.168.255.182": "Ster"
}
pico_connections = {}  # Persistent WebSocket connections, keyed by IP
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

calibration_offsets = [[1.0, 0.0],[1.0, 0.0],[1.0, 0.0],[1.0, 0.0]]
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

def connect_pico(ip):
    """Open (or reopen) a persistent WebSocket connection to a Pico."""
    uri = f"ws://{ip}:5000/ws"
    try:
        ws = websocket.create_connection(uri, timeout=5)
        ws.settimeout(1)  # Short timeout so recv() returns when buffer is empty
        pico_connections[ip] = ws
        print(f"Connected to Pico at {ip} ({PICO_NAMES[ip]})")
    except Exception as e:
        pico_connections[ip] = None
        print(f"Could not connect to Pico at {ip}: {e}")

def poll_picos():  
    now = time.time()
    pico_data = [None, None]
    for ip in PICO_NAMES:
        ws = pico_connections.get(ip)
        if ws is None:
            connect_pico(ip)
            ws = pico_connections.get(ip)
        if ws is None:
            continue
        try:
            # Drain all buffered messages; keep only the latest one
            latest_raw = None
            while True:
                try:
                    latest_raw = json.loads(ws.recv())
                except websocket.WebSocketTimeoutException:
                    break  # Buffer is empty, exit drain loop
            if latest_raw is not None:
                pico_data = [latest_raw["T0"], latest_raw["RH0"]]
                last_pico_reception[ip] = now
        except Exception as e:
            print(f"Error receiving from {ip}, reconnecting: {e}")
            try:
                ws.close()
            except Exception:
                pass
            pico_connections[ip] = None

    # Mark data as stale if no new data received within STALE_TIMEOUT
    for ip in PICO_NAMES:
        last_recv = last_pico_reception.get(ip)
        if last_recv is not None and (now - last_recv) > STALE_TIMEOUT:
            print(f"Data from {ip} is stale (last new data received {now - last_recv:.1f} seconds ago)")
            pico_data = [None, None]
    return pico_data

# Powiadomienia przez ntfy.sh - subskrybuj ten temat na https://ntfy.sh/<NTFY_TOPIC>
# Temat jest publiczny, więc jego nazwa działa jak hasło - nie udostępniaj jej.
NTFY_URL = "https://ntfy.sh/"
NTFY_TOPIC = "tches_pomiar_7486d42493cd"

def send_notification(title, message, priority=3, tags=None):
    """Wysyła powiadomienie ntfy; błąd sieci nie przerywa pomiaru."""
    payload = {"topic": NTFY_TOPIC, "title": title, "message": message, "priority": priority}
    if tags:
        payload["tags"] = tags
    try:
        req = urllib.request.Request(NTFY_URL, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).close()
        print(f"Wysłano powiadomienie: {title}")
    except Exception as e:
        print(f"UWAGA: nie udało się wysłać powiadomienia ntfy: {e}")


if __name__ == "__main__":
    # Nagłówek pliku
    with open(filename, "w") as f:
        f.write("timestamp;SHT85_1_temp;SHT85_1_hum_raw;SHT85_1_hum;SHT85_2_temp;SHT85_2_hum_raw;SHT85_2_hum;SHT85_3_temp;SHT85_3_hum_raw;SHT85_3_hum;SHT85_4_temp;SHT85_4_hum_raw;SHT85_4_hum;Keller_1;Keller_2;SHT85_pico_temp;SHT85_pico_hum_raw;dT_wylot_wlot\n")
    
    # Pre-connect to all Picos before entering the measurement loop
    for ip in PICO_NAMES:
        connect_pico(ip)

    # Powiadomienie startowe - potwierdza, że kanał działa, zanim pomiar potrwa godzinami
    send_notification("Pomiar TChES rozpoczęty",
                      f"Plik: {filename}\nKoniec, gdy |dT| < {DT_PROG} °C", priority=2, tags=["thermometer"])

    n = 0
    poczatek_pomiaru = datetime.now()
    dt_uzbrojony = False
    dt_licznik = 0

    while True:
        
        current_time = datetime.now() 
        czas_pomiaru = current_time - poczatek_pomiaru
        
        if czas_pomiaru >= krok_probkowania * n:
            n+= 1
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            sht_data = read_sensors()
            keller_data = read_keller_pressure()
            pico_data = poll_picos()
            # sht_data: [temp, hum_raw, hum] dla każdego czujnika; kanał 2 = Wlata, kanał 3 = Wylata
            t_wlot = sht_data[2*3]
            t_wylot = sht_data[3*3]
            dT = t_wylot - t_wlot if t_wlot is not None and t_wylot is not None else None
            try:
                with open(filename, "a") as f:
                    line = f"{timestamp}"
                    for value in sht_data:
                        if value is not None:
                            line += f";{value:.2f}"
                        else:
                            line += ";N/A"
                    for value in keller_data:
                        if value is not None:
                            line += f";{value:.4f}"
                        else:
                            line += ";N/A"
                    for value in pico_data:
                        if value is not None:
                            line += f";{value:.2f}"
                        else:
                            line += ";N/A;N/A"
                            break
                    line += f";{dT:.2f}" if dT is not None else ";N/A"
                    f.write(line + "\n")
            except Exception as e:
                print(f"Błąd zapisu do pliku: {e}")

            # Brak odczytu któregoś z czujników - nie zmieniamy stanu warunku
            if dT is not None:
                if not dt_uzbrojony:
                    if abs(dT) >= max(DT_UZBROJENIE, DT_PROG + 1):
                        dt_uzbrojony = True
                        print(f"dT = {dT:.2f} °C - warunek zakończenia uzbrojony (próg {DT_PROG} °C)")
                    else:
                        print(f"dT = {dT:.2f} °C (oczekiwanie na |dT| >= {max(DT_UZBROJENIE, DT_PROG + 1)} °C)")
                else:
                    # Tylko po uzbrojeniu: jednorazowe ostrzeżenie o zbliżającym się końcu
                    if not koniec_bliski and abs(dT) < DT_PROG + DT_MARGINES_OSTRZEZENIA:
                        koniec_bliski = True
                        print(f"dT = {dT:.2f} °C - pomiar niedługo się skończy, wysyłam ostrzeżenie")
                        send_notification("Pomiar niedługo się skończy",
                                          f"|dT| wynosi: {dT:.2f} °C przy progu: {DT_PROG} °C. Kieruj się do labu.",
                                          priority = 4, tags=["thermometer", "warning"])

                    # Licznik końca - działa na każdym odczycie po uzbrojeniu, także tym z ostrzeżeniem
                    if abs(dT) < DT_PROG:
                        dt_licznik += 1
                        print(f"dT = {dT:.2f} °C < {DT_PROG} °C ({dt_licznik}/{DT_LICZBA_ODCZYTOW})")
                    else:
                        dt_licznik = 0
                        print(f"dT = {dT:.2f} °C")

                if dt_licznik >= DT_LICZBA_ODCZYTOW:
                    print("=" * 60)
                    print(f"KONIEC POMIARU {timestamp}: |dT| < {DT_PROG} °C przez {DT_LICZBA_ODCZYTOW} kolejnych odczytów.")
                    print(f"Wyłącz pomiar i zważ materiał. Dane zapisano w pliku: {filename}")
                    print("=" * 60)
                    send_notification("Koniec pomiaru TChES - zważ materiał",
                                      f"{timestamp}: |dT| < {DT_PROG} °C (ostatnio dT = {dT:.2f} °C).\n"
                                      f"Zapis zakończony, zważ materiał.\nPlik: {filename}",
                                      priority=5, tags=["scales", "warning"])
                    break

    for ws in pico_connections.values():
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
