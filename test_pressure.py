import minimalmodbus
import serial
import time

# Inicjalizacja instrumentu Modbus
instrument = minimalmodbus.Instrument('/dev/ttyUSB0', 2)  # Port i adres slave

# Ustawienia portu szeregowego
instrument.serial.baudrate = 9600        # lub 19200 – zależy od konfiguracji urządzenia
instrument.serial.bytesize = 8
instrument.serial.parity   = serial.PARITY_NONE
instrument.serial.stopbits = 1
instrument.serial.timeout  = 1            # sekundy

instrument.mode = minimalmodbus.MODE_RTU

# W niektórych konwerterach FTDI warto dodać:
instrument.clear_buffers_before_each_transaction = True

# Przykład: odczyt ciśnienia (rejestr 0x1000 = 4096)
try:
    raw_pressure = instrument.read_float(2, functioncode=3, number_of_registers=2, byteorder=minimalmodbus.BYTEORDER_BIG)
    print(f"Ciśnienie: {raw_pressure:.3f} bar")

    # Odczyt temperatury (rejestr 0x1002 = 4098)
    raw_temp = instrument.read_float(4098, functioncode=3, number_of_registers=2, byteorder=minimalmodbus.BYTEORDER_BIG)
    print(f"Temperatura: {raw_temp:.2f} °C")

except IOError:
    print("Błąd komunikacji z czujnikiem.")
