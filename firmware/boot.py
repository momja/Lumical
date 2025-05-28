"""
Boot script for LED strip calibrator firmware.

This script runs on ESP32 boot and sets up the system.
"""

import gc
import time

import esp
import network

# Disable debug to reduce memory usage
esp.osdebug(None)

# Enable garbage collection
gc.collect()


# Connect to WiFi if needed for debugging/configuration
def connect_wifi(ssid="your_wifi_ssid", password="your_wifi_password"):
    """
    Connect to WiFi network.

    Args:
        ssid: WiFi network name
        password: WiFi password

    Returns:
        True if connected successfully, False otherwise
    """
    wlan = network.WLAN(network.STA_IF)

    if not wlan.active():
        wlan.active(True)

    if not wlan.isconnected():
        print(f"Connecting to WiFi network: {ssid}")
        wlan.connect(ssid, password)

        # Wait for connection with timeout
        max_wait = 20
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            time.sleep(1)

    if wlan.isconnected():
        print("WiFi connected. Network config:", wlan.ifconfig())
        return True
    else:
        print("WiFi connection failed")
        return False


# Uncomment to enable WiFi and WebREPL for remote debugging
# if connect_wifi():
#     webrepl.start()

print("Boot completed - LED strip calibrator starting...")
