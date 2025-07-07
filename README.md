# MUST_Battery_to_MQTT
Pulling data from RS485 and publish to MQTT Broker

Tutorial: Setting Up BMS Monitoring on Raspberry Pi with Python

This tutorial will guide you through setting up a Python script to communicate with a Battery Management System (BMS) over RS485/Modbus RTU on a Raspberry Pi. We'll cover:

    Identifying the correct serial port

    Configuring the BMS communication protocol

    Setting up the Python environment

    Running the script automatically at startup

🔧 Step 1: Identify the Correct Serial Port

Most BMS systems connect via USB-to-RS485 or UART (GPIO serial).
Method 1: Check USB-to-RS485 Adapter

Plug in your USB-to-RS485 adapter and run:
bash

ls /dev/tty*

Look for devices like:

    /dev/ttyUSB0 (most common)

    /dev/ttyAMA0 (Raspberry Pi UART)

    /dev/ttyS0 (secondary serial)

If nothing appears, install drivers:
bash

sudo apt install usbutils
lsusb  # Check if the adapter is detected

Method 2: Test Serial Communication

Check if the port is working:
bash

sudo apt install screen
screen /dev/ttyUSB0 9600  # Replace with your port and baud rate

(Exit with Ctrl+A then :quit)
⚙️ Step 2: Configure the BMS Protocol

On the BMS set the RS485 to WOW_MODBUS

Test the BMS Comunication with the following command 
mbpoll -b 9600 -P none -m rtu -a 1 -t 4:hex -r 1 -c 32 /dev/ttyUSB0
You should see the following :
 Polling slave 1... Ctrl-C to stop)
[1]:    0xFE18
[2]:    0x14A6
[3]:    0x0040
[4]:    0x0064
[5]:    0x4B4C
[6]:    0x7530
[7]:    0x7530

If you dont , there is a good chanse that you have swaped A and B

🐍 Step 3: Set Up Python Environment
1. Install Python & Dependencies
bash

sudo apt update
sudo apt install python3 python3-pip python3-venv

2. Create a Virtual Environment
bash

mkdir ~/bms-monitor && cd ~/bms-monitor
python3 -m venv .venv
source .venv/bin/activate

3. Install Required Libraries
bash

pip install minimalmodbus paho-mqtt

📜 Step 4: Python Script for BMS Communication




python3 bms_monitor.py

If you see PermissionError, fix it with:
bash

sudo usermod -a -G dialout $USER
sudo chmod a+rw /dev/ttyUSB0

🚀 Step 5: Run at Startup (systemd Service)
1. Create a systemd Service
bash

sudo nano /etc/systemd/system/bms-monitor.service

Paste:
ini

[Unit]
Description=BMS Monitor Service
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bms-monitor
ExecStart=/home/pi/bms-monitor/.venv/bin/python /home/pi/bms-monitor/bms_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

2. Enable & Start the Service
bash

sudo systemctl daemon-reload
sudo systemctl enable bms-monitor.service
sudo systemctl start bms-monitor.service

3. Check Logs
bash

journalctl -u bms-monitor.service -f

🔍 Troubleshooting
Issue	Solution
No /dev/ttyUSB0	Check lsusb & dmesg
Permission Denied	sudo chmod a+rw /dev/ttyUSB0
Modbus Timeout	Check baud rate & slave ID
Python Crashes	Test script manually first
✅ Conclusion

Now you have:
✔ A working Python script reading BMS data
✔ Automatic startup via systemd
✔ Debugging steps if issues arise

Next steps:

    Send data to MQTT (for Node-RED/Home Assistant)

    Log to a database (InfluxDB, SQLite)

    Set up alerts for low voltage/current

Let me know if you need help with any step! 🚀
