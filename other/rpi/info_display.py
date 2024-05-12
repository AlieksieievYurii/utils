"""
Script that waits until the button is triggered. Once trigger happens,
the script print basic information about RBi, in I2C Display, such as:
    * IP address in the local netword
    * Hostname
    * CPU usage
    * RAM usage
    * Disk usage

Prerequisites:
1. Enable I2C Interface
    - Run: sudo raspi-config
    - A blue screen will appear. Now select Interfacing option
    - After this, we need to select I2C option and enable it.
    - Reboot
2. Install Pillow Library - needed for adafruit-circuitpython-ssd1306
    - Better to install via package manager: sudo apt-get install python3-pil
3. Install adafruit-circuitpython-ssd1306
    - pip install adafruit-circuitpython-ssd1306
4. Install RPi GPIO that manages the board
    - pip install RPi.GPIO
"""

import subprocess

from collections import namedtuple
import time
from typing import Final, Tuple

import board
import busio
import adafruit_ssd1306
import RPi.GPIO as GPIO

BUTTON: Final[int] = 17


def get_ip_and_host_name() -> Tuple[str, str]:
    ip = subprocess.check_output(
        "hostname -I | cut -d' ' -f1", shell=True, encoding="utf-8"
    )
    hostname = subprocess.check_output(
        "hostname", shell=True, encoding="utf-8"
    )

    return ip.rstrip(), hostname.rstrip()


def get_cpu_load_in_percentage() -> float:
    cmd = (
        "top -bn2 | grep '%Cpu' | tail -1 | "
        "grep -P '(....|...) id,'|awk '{print 100-$8}'"
    )
    cup_usage = subprocess.check_output(cmd, shell=True, encoding="utf-8")

    return cup_usage.rstrip()


def get_ram_memory_usage() -> dict:
    stats = namedtuple("MemUsage", ["used", "max", "used_in_percentage"])
    cmd = "free -m | awk 'NR==2{printf \"%s %s %.2f\", $3,$2,$3*100/$2 }'"
    mem_usage = subprocess.check_output(cmd, encoding="utf-8", shell=True)
    used, max, used_in_percentage = mem_usage.split()
    return stats(int(used), int(max), float(used_in_percentage))


def get_disk_usage():
    stats = namedtuple("DiskUsage", ["used", "max", "used_in_percentage"])
    cmd = 'df -h | awk \'$NF=="/"{printf "%d %d %d", $3,$2,$5}\''
    disk_usage = subprocess.check_output(cmd, encoding="utf-8", shell=True)
    used, max, used_in_percentage = disk_usage.split()
    return stats(int(used), int(max), int(used_in_percentage))


def print_information(oled: adafruit_ssd1306.SSD1306_I2C) -> None:
    oled.text(f"Hi, Loading Info...", 10, 30, True)
    oled.show()

    ip, host = get_ip_and_host_name()
    cpu = get_cpu_load_in_percentage()
    mem_usage = get_ram_memory_usage()
    disk_usage = get_disk_usage()

    oled.fill(0)
    oled.show()

    oled.text(f"IP: {ip}", 1, 0, True)
    oled.text(f"Host: {host}", 1, 8, True)
    oled.text(f"CPU: {cpu} %", 1, 16, True)
    oled.text(
        f"RAM: {str(mem_usage.used)}/{str(mem_usage.max)} MiB", 1, 24, True
    )
    oled.text(f"({mem_usage.used_in_percentage} %)", 30, 32, True)
    oled.text(
        f"Disk: {disk_usage.used}/{disk_usage.max} "
        f"Gb {disk_usage.used_in_percentage}%",
        1,
        40,
        True,
    )
    oled.show()
    time.sleep(10)
    oled.fill(0)
    oled.show()


def main() -> None:
    print("Start. Waiting for button trigger")
    GPIO.setwarnings(True)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    i2c = busio.I2C(board.SCL, board.SDA)
    oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
    oled.fill(0)
    oled.show()

    while True:
        while GPIO.input(BUTTON):
            pass
        print("Button has been triggered")
        print_information(oled)


if __name__ == "__main__":
    main()
