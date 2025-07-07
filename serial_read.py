#!/usr/bin/env python3
import minimalmodbus
import paho.mqtt.client as mqtt
from datetime import datetime
import time
import json
import sys

# ───────────────────────── MQTT CONFIG ─────────────────────────
MQTT_BROKER = "yourMQTTbroker"
MQTT_PORT = 1883
MQTT_ROOT_TOPIC = "bms"
MQTT_CLIENT_ID = "bms_monitor"

# ───────────────────────── BMS CONFIG ──────────────────────────
BMS_PORT = "/dev/ttyUSB0"      # Confirm your correct device
BMS_SLAVE_ADDRESS = 1
POLL_INTERVAL = 10             # seconds

# ───────────────────────── HELPERS ─────────────────────────────
def twos_complement(value, bits=16):
    """Convert unsigned integer to signed two's complement."""
    if value >= (1 << (bits - 1)):
        value -= 1 << bits
    return value

def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected to MQTT broker" if rc == 0 else f"MQTT connection failed with code {rc}")

def setup_mqtt():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID)
        client.on_connect = on_connect
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        return client
    except Exception as e:
        print(f"MQTT setup failed: {e}")
        return None

def read_all_bms_registers(instrument):
    """Read all 125 registers from BMS in 32‑register chunks."""
    try:
        chunks = []
        for addr in range(0, 125, 32):
            chunk = instrument.read_registers(addr, min(32, 125 - addr), functioncode=3)
            chunks.extend(chunk)
        return chunks
    except Exception as e:
        print(f"Failed to read registers: {e}")
        return None

# ──────────────────────── DECODE & ENRICH ──────────────────────
def decode_bms_data(raw_data):
    """Decode register list into structured dict and add max/min/delta."""
    if not raw_data or len(raw_data) < 125:
        print("Incomplete BMS data received")
        return None

    try:
        cell_voltages = [raw_data[i] for i in range(15, 31)]          # mV list of length 16
        max_val = max(cell_voltages)
        min_val = min(cell_voltages)
        max_idx = cell_voltages.index(max_val) + 1                    # +1 for human‑friendly 1‑based index
        min_idx = cell_voltages.index(min_val) + 1
        delta_val = max_val - min_val

        data = {
            "timestamp": datetime.now().isoformat(),
            "basic": {
                "current": twos_complement(raw_data[0]) / 100.0,      # A
                "voltage": raw_data[1] / 100.0,                       # V
                "soc": raw_data[2],                                   # %
                "soh": raw_data[3],                                   # %
                "remaining_capacity": raw_data[4] / 10.0,             # Ah
                "full_capacity": raw_data[5] / 10.0,                  # Ah
                "designed_capacity": raw_data[6] / 10.0,              # Ah
                "cycle_count": raw_data[7],
            },
            "status": {
                "warning_flags": raw_data[9],
                "protection_flags": raw_data[10],
                "fault_flags": raw_data[11],
                "balance_status": raw_data[12],
            },
            "cells": {
                "voltages": cell_voltages,                            # list, mV
                "max":   {"number": max_idx, "voltage": max_val},     # new
                "min":   {"number": min_idx, "voltage": min_val},     # new
                "delta": delta_val,                                   # new, mV
                "temps": [raw_data[i] / 10.0 for i in range(31, 35)], # °C
            },
            "temperatures": {
                "mosfet": raw_data[35] / 10.0,                        # °C
                "ambient": raw_data[36] / 10.0,                       # °C
            },
            "protection": {
                "pack_ov": {
                    "alarm":   raw_data[60],
                    "protect": raw_data[61],
                    "release": raw_data[62],
                    "delay":   raw_data[63] / 10.0,                   # s
                },
                "cell_ov": {
                    "alarm":   raw_data[64],
                    "protect": raw_data[65],
                    "release": raw_data[66],
                    "delay":   raw_data[67] / 10.0,                   # s
                },
                "pack_uv": {
                    "alarm":   raw_data[68],
                    "protect": raw_data[69],
                    "release": raw_data[70],
                    "delay":   raw_data[71] / 10.0,                   # s
                },
                "cell_uv": {
                    "alarm":   raw_data[72],
                    "protect": raw_data[73],
                    "release": raw_data[74],
                    "delay":   raw_data[75] / 10.0,                   # s
                },
            },
            "balance_settings": {
                "start_voltage": raw_data[105],                       # mV
                "delta_voltage": raw_data[106],                       # mV
            },
        }
        return data
    except Exception as e:
        print(f"Data decoding failed: {e}")
        return None

# ─────────────────── MQTT PUBLISH (unchanged) ──────────────────
def publish_mqtt_data(client, data):
    if not client or not data:
        return
    try:
        client.publish(f"{MQTT_ROOT_TOPIC}/full", json.dumps(data), qos=1)
        for category, values in data.items():
            if isinstance(values, dict):
                for subkey, subvalue in values.items():
                    if isinstance(subvalue, (list, dict)):
                        client.publish(f"{MQTT_ROOT_TOPIC}/{category}/{subkey}", json.dumps(subvalue), qos=1)
                    else:
                        client.publish(f"{MQTT_ROOT_TOPIC}/{category}/{subkey}", str(subvalue), qos=1)
            else:
                client.publish(f"{MQTT_ROOT_TOPIC}/{category}", str(values), qos=1)
    except Exception as e:
        print(f"MQTT publish error: {e}")

# ──────────────────── CONSOLE OUTPUT ───────────────────────────
def print_console_data(data):
    if not data:
        return

    print(f"\n[{datetime.now()}] BMS Data:")
    print("-" * 60)
    print(f"Voltage: {data['basic']['voltage']:.2f} V | Current: {data['basic']['current']:.2f} A")
    print(f"SOC: {data['basic']['soc']} % | SOH: {data['basic']['soh']} %")
    print(f"Capacity: {data['basic']['remaining_capacity']:.1f}/{data['basic']['full_capacity']:.1f} Ah")
    print(f"Cycles: {data['basic']['cycle_count']}")

    # New: max / min / delta display
    max_info = data['cells']['max']
    min_info = data['cells']['min']
    delta_mv = data['cells']['delta']
    print(f"\nMax Cell : #{max_info['number']:02d}  {max_info['voltage']} mV")
    print(f"Min Cell : #{min_info['number']:02d}  {min_info['voltage']} mV")
    print(f"Delta    : {delta_mv} mV")

    print("\nCell Voltages (mV):")
    for i, volt in enumerate(data['cells']['voltages'], 1):
        print(f"{i:2d}: {volt:4d}", end=' | ')
        if i % 4 == 0:
            print()

    print("\n\nTemperatures (°C):")
    print(f"Cells  : {', '.join(f'{t:.1f}' for t in data['cells']['temps'])}")
    print(f"MOSFET : {data['temperatures']['mosfet']:.1f} | Ambient: {data['temperatures']['ambient']:.1f}")

    print("\nProtection Settings:")
    print(f"Pack OV Alarm: {data['protection']['pack_ov']['alarm']} mV")
    print(f"Cell OV Alarm: {data['protection']['cell_ov']['alarm']} mV")
    print("-" * 60)

# ──────────────────── MAIN LOOP ────────────────────────────────
def main():
    instrument = minimalmodbus.Instrument(BMS_PORT, BMS_SLAVE_ADDRESS)
    instrument.serial.baudrate = 9600
    instrument.serial.parity   = 'N'
    instrument.serial.timeout  = 1.0

    mqtt_client = setup_mqtt()

    try:
        while True:
            t0 = time.time()

            raw = read_all_bms_registers(instrument)
            data = decode_bms_data(raw)

            if data:
                print_console_data(data)
                publish_mqtt_data(mqtt_client, data)

            time.sleep(max(0, POLL_INTERVAL - (time.time() - t0)))
    except KeyboardInterrupt:
        print("\nStopping BMS monitor…")
    finally:
        if mqtt_client:
            mqtt_client.disconnect()
            mqtt_client.loop_stop()

if __name__ == "__main__":
    main()
