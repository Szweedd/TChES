import time
import board
import busio
import adafruit_sht31d

# Inicjalizacja magistrali I2C
i2c = busio.I2C(board.SCL, board.SDA)

# Inicjalizacja czujnika SHT (domyślny adres 0x44)
sensor = adafruit_sht31d.SHT31D(i2c)

# Pojedynczy pomiar
temperature = sensor.temperature
humidity = sensor.relative_humidity

print(f"Temperatura: {temperature:.2f} °C")
print(f"Wilgotność: {humidity:.2f} %")