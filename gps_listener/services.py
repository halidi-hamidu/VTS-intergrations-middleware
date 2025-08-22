import socket
import json
import struct
import datetime
import decimal
import time
import requests
from django.conf import settings
from django.db import connection
from vehicles.models import Vehicle
from data_reported.models import ReportedData
from concurrent.futures import ThreadPoolExecutor

# Activity codes mapping based on Teltonika FMB120 Event IDs and LATRA specifications
ACTIVITY_CODES = {
    # Default/Common events
    0: "No Event",
    1: "Movement/Logging (Default)",
   
    # LATRA Standard Activity IDs
    2: "Engine ON",
    3: "Engine OFF",
    4: "Speeding",
    5: "Hash Braking",
    6: "Hash Turning",
    7: "Hash Acceleration",
    8: "Panic Button (Driver)",
    9: "Internal Battery Low",
    10: "External Power Disconnected",
    11: "Excessive Idle",
    12: "Accident",
    13: "Panic Button (Passenger)",
    14: "Device Tempering",
    15: "Black Box Data Logging",
    16: "Fuel data report",
    17: "Invalid Scan",
    18: "Engine Start",
    19: "Engine Stop",
    20: "Enter Boundary",
    21: "Leave Boundary",
    22: "Enter Checkpoint",
    23: "Leave Checkpoint",
    24: "Ibutton Scan (Regular)",
    25: "GPS Antenna Disconnected",
    26: "GPS Signal Lost",
    27: "GPS Signal Restored",
    28: "Main Power Disconnected",
    29: "Main Power Connected",
    30: "Emergency Button",
    31: "Driver Identification",
    32: "Unauthorized Driver",
    33: "Vehicle Theft",
    34: "Maintenance Alert",
    35: "Service Reminder",
    36: "Low Fuel Alert",
    37: "High Temperature Alert",
    38: "Low Temperature Alert",
    39: "Door Open",
    40: "Door Close",
    41: "Hood Open",
    42: "Hood Close",
    43: "Trunk Open",
    44: "Trunk Close",
    45: "Seatbelt Unfastened",
    46: "Seatbelt Fastened",
    47: "Airbag Deployed",
    48: "Collision Detected",
    49: "Rollover Detected",
    50: "Emergency Call",
   
    # Teltonika Eventual I/O elements (Event IDs) mapped to LATRA activities
    155: "20",  # Geofence zone 01 -> Enter/Leave Boundary
    156: "20",  # Geofence zone 02 -> Enter/Leave Boundary
    157: "20",  # Geofence zone 03 -> Enter/Leave Boundary
    158: "20",  # Geofence zone 04 -> Enter/Leave Boundary
    159: "20",  # Geofence zone 05 -> Enter/Leave Boundary
    61: "20",   # Geofence zone 06 -> Enter/Leave Boundary
    62: "20",   # Geofence zone 07 -> Enter/Leave Boundary
    63: "20",   # Geofence zone 08 -> Enter/Leave Boundary
    64: "20",   # Geofence zone 09 -> Enter/Leave Boundary
    65: "20",   # Geofence zone 10 -> Enter/Leave Boundary
    70: "20",   # Geofence zone 11 -> Enter/Leave Boundary
    88: "20",   # Geofence zone 12 -> Enter/Leave Boundary
    91: "20",   # Geofence zone 13 -> Enter/Leave Boundary
    92: "20",   # Geofence zone 14 -> Enter/Leave Boundary
    93: "20",   # Geofence zone 15 -> Enter/Leave Boundary
    94: "20",   # Geofence zone 16 -> Enter/Leave Boundary
    95: "20",   # Geofence zone 17 -> Enter/Leave Boundary
    96: "20",   # Geofence zone 18 -> Enter/Leave Boundary
    97: "20",   # Geofence zone 19 -> Enter/Leave Boundary
    98: "20",   # Geofence zone 20 -> Enter/Leave Boundary
    99: "20",   # Geofence zone 21 -> Enter/Leave Boundary
   
    250: "18",  # Trip Start -> Engine Start (when state=1) / Trip Stop -> Engine Stop (when state=0)
    251: "11",  # Idling Start/Stop -> Excessive Idle
    252: "9",   # Battery Unplug -> Internal Battery Low
    253: "5",   # Green Driving Event (harsh braking) -> Hash Braking
    254: "7",   # Green Driving Value (harsh acceleration) -> Hash Acceleration
    255: "4",   # Over Speeding -> Speeding
    246: "33",  # Towing Detection -> Vehicle Theft
    247: "12",  # Crash Detection -> Accident
    248: "24",  # Immobilizer -> Ibutton Scan (Regular)
    249: "26",  # Jamming -> GPS Signal Lost
   
    # Permanent I/O based events mapped to LATRA activities
    239: "2",   # Ignition Event -> Engine ON (when state=1) / Engine OFF (when state=0)
    240: "1",   # Movement Event -> Movement/Logging (Default)
   
    # Additional Teltonika Event IDs mapped to LATRA activities
    175: "20",  # Auto Geofence -> Enter/Leave Boundary
    236: "8",   # Alarm -> Panic Button (Driver)
    257: "12",  # Crash trace data -> Accident
    285: "31",  # Blood alcohol content -> Driver Identification
    318: "26",  # GNSS Jamming -> GPS Signal Lost
    391: "14",  # Private mode -> Device Tempering
    449: "2",   # Ignition On Counter -> Engine ON
   
    # System events that should generate activities
    1: "1",     # System event 1 -> Movement/Logging
    2: "1",     # System event 2 -> Movement/Logging
    3: "1",     # System event 3 -> Movement/Logging
    4: "1",     # System event 4 -> Movement/Logging
    5: "1",     # System event 5 -> Movement/Logging
    6: "1",     # System event 6 -> Movement/Logging
    7: "1",     # System event 7 -> Movement/Logging
    8: "1",     # System event 8 -> Movement/Logging
   
    # Power management events - More comprehensive coverage
    113: "9",   # Battery Level (when low) -> Internal Battery Low
    66: "10",   # External Voltage (when low) -> External Power Disconnected
    67: "9",    # Battery Voltage (when low) -> Internal Battery Low
    68: "9",    # Battery Current (monitoring) -> Internal Battery Low
    200: "15",  # Sleep Mode -> Black Box Data Logging
   
    # GPS/GNSS Status Events
    69: "26",   # GNSS Status (when OFF or no fix) -> GPS Signal Lost
    21: "27",   # GSM Signal (when restored) -> GPS Signal Restored
    205: "15",  # GSM Cell ID -> Black Box Data Logging
    206: "15",  # GSM Area Code -> Black Box Data Logging
    241: "15",  # Active GSM Operator -> Black Box Data Logging
    237: "15",  # Network Type -> Black Box Data Logging
   
    # Digital Input/Output Events
    1: "39",    # Digital Input 1 -> Door Open/Close
    2: "8",     # Digital Input 2 -> Panic Button (Driver)
    3: "39",    # Digital Input 3 -> Door Open/Close
    179: "39",  # Digital Output 1 -> Door Open/Close
    180: "39",  # Digital Output 2 -> Door Open/Close
    380: "39",  # Digital Output 3 -> Door Open/Close
    381: "14",  # Ground Sense -> Device Tempering
   
    # Fuel and Engine Monitoring
    12: "16",   # Fuel Used GPS -> Fuel data report
    13: "16",   # Fuel Rate GPS -> Fuel data report
    48: "36",   # OBD Fuel Level -> Low Fuel Alert
    84: "36",   # CAN Fuel Level -> Low Fuel Alert
    89: "36",   # CAN Fuel Level % -> Low Fuel Alert
   
    # Temperature Monitoring
    72: "37",   # Dallas Temperature 1 (high temp) -> High Temperature Alert
    73: "37",   # Dallas Temperature 2 (high temp) -> High Temperature Alert
    74: "37",   # Dallas Temperature 3 (high temp) -> High Temperature Alert
    75: "37",   # Dallas Temperature 4 (high temp) -> High Temperature Alert
    32: "37",   # OBD Coolant Temperature (high) -> High Temperature Alert
    39: "37",   # OBD Intake Air Temperature (high) -> High Temperature Alert
   
    # Vehicle Speed and Movement
    24: "4",    # Speed (when over limit) -> Speeding
    37: "4",    # OBD Vehicle Speed (when over limit) -> Speeding
    81: "4",    # CAN Vehicle Speed (when over limit) -> Speeding
    303: "1",   # Instant Movement -> Movement/Logging
   
    # Accelerometer Events (Harsh Driving)
    17: "7",    # Axis X (harsh acceleration) -> Hash Acceleration
    18: "6",    # Axis Y (harsh turning) -> Hash Turning
    19: "5",    # Axis Z (harsh braking) -> Hash Braking
    383: "15",  # AXL Calibration Status -> Black Box Data Logging
   
    # Trip and Odometer
    199: "15",  # Trip Odometer -> Black Box Data Logging
    16: "15",   # Total Odometer -> Black Box Data Logging (removed from transmission but tracked)
   
    # RFID and Access Control
    207: "24",  # RFID -> Ibutton Scan (Regular)
    78: "24",   # iButton -> Ibutton Scan (Regular)
    264: "24",  # Barcode ID -> Ibutton Scan (Regular)
   
    # Environmental Sensors
    10: "15",   # SD Status -> Black Box Data Logging
    9: "15",    # Analog Input 1 -> Black Box Data Logging
    6: "15",    # Analog Input 2 -> Black Box Data Logging
   
    # Communication Status
    263: "27",  # BT Status (when connected) -> GPS Signal Restored
    1148: "15", # Connectivity Quality -> Black Box Data Logging
   
    # Pulse Counters (Activity Monitoring)
    4: "15",    # Pulse Counter Din1 -> Black Box Data Logging
    5: "15",    # Pulse Counter Din2 -> Black Box Data Logging
    622: "15",  # Frequency DIN1 -> Black Box Data Logging
    623: "15",  # Frequency DIN2 -> Black Box Data Logging
   
    # Extended Sensor Network (EYE Sensors)
    10800: "37", # EYE Temperature 1 (high temp) -> High Temperature Alert
    10801: "37", # EYE Temperature 2 (high temp) -> High Temperature Alert
    10802: "37", # EYE Temperature 3 (high temp) -> High Temperature Alert
    10803: "37", # EYE Temperature 4 (high temp) -> High Temperature Alert
    10820: "9",  # EYE Low Battery 1 -> Internal Battery Low
    10821: "9",  # EYE Low Battery 2 -> Internal Battery Low
    10822: "9",  # EYE Low Battery 3 -> Internal Battery Low
    10823: "9",  # EYE Low Battery 4 -> Internal Battery Low
    10812: "1",  # EYE Movement 1 -> Movement/Logging
    10813: "1",  # EYE Movement 2 -> Movement/Logging
    10814: "1",  # EYE Movement 3 -> Movement/Logging
    10815: "1",  # EYE Movement 4 -> Movement/Logging
   
    # Advanced I/O Elements for Enhanced Detection
    252: "9",   # Unplug (Battery Unplugged) -> Internal Battery Low
    246: "33",  # Towing -> Vehicle Theft
    251: "11",  # Idling -> Excessive Idle
    283: "2",   # Driving State (Ignition ON) -> Engine ON
    284: "15",  # Driving Records -> Black Box Data Logging
   
    # Driver Card Events
    403: "31",  # Driver Name -> Driver Identification
    404: "31",  # Driver card license type -> Driver Identification
    405: "31",  # Driver Gender -> Driver Identification
    406: "31",  # Driver Card ID -> Driver Identification
    407: "31",  # Driver card expiration date -> Driver Identification
    408: "31",  # Driver Card place of issue -> Driver Identification
    409: "31",  # Driver Status Event -> Driver Identification
   
    # OBD Events
    256: "16",  # VIN -> Fuel data report
    30: "34",   # Number of DTC -> Maintenance Alert
    281: "34",  # Fault Codes -> Maintenance Alert
   
    # CAN Adapter Events
    90: "39",   # Door Status -> Door Open/Close
    235: "34",  # Oil Level -> Maintenance Alert
    160: "34",  # DTC Faults -> Maintenance Alert
   
    # BLE Sensor Events
    385: "22",  # Beacon -> Enter/Leave Checkpoint
    548: "22",  # Advanced BLE Beacon data -> Enter/Leave Checkpoint
   
    # COMPREHENSIVE I/O PARAMETER MAPPING - Complete coverage of Teltonika FMB130
   
    # Extended Power Management (complete coverage)
    65: "10",   # Power Input 2 -> External Power Disconnected
    114: "10",  # LVCAN Power -> External Power Disconnected
    115: "9",   # Battery Current (12V) -> Internal Battery Low
    116: "9",   # Battery Voltage (24V) -> Internal Battery Low
    117: "10",  # Backup Battery Voltage -> External Power Disconnected
    118: "10",  # Module Supply Voltage -> External Power Disconnected
   
    # Enhanced CAN Bus Coverage
    80: "15",   # CAN Engine Hours -> Black Box Data Logging  
    82: "37",   # CAN Engine Temperature -> High Temperature Alert
    83: "16",   # CAN Fuel Consumed -> Fuel data report
    85: "1",    # CAN Total Vehicle Distance -> Movement/Logging
    86: "15",   # CAN Axle Weight -> Black Box Data Logging
    87: "15",   # CAN Engine Load -> Black Box Data Logging
    88: "15",   # CAN Engine Coolant Level -> Black Box Data Logging
    90: "4",    # CAN Wheel Based Speed -> Speeding (if over limit)
    91: "15",   # CAN Accelerator Pedal -> Black Box Data Logging
    92: "11",   # CAN Parking Brake -> Excessive Idle
    93: "11",   # CAN PTO Drive Engaged -> Excessive Idle
    94: "34",   # CAN Service Distance -> Maintenance Alert
    95: "15",   # CAN Cruise Control Speed -> Black Box Data Logging
    96: "15",   # CAN Transmission Oil Temperature -> Black Box Data Logging
    97: "15",   # CAN Engine Oil Temperature -> Black Box Data Logging
    98: "37",   # CAN Engine Coolant Temperature -> High Temperature Alert
    99: "15",   # CAN Brake Application Pressure -> Black Box Data Logging
    100: "15",  # CAN Engine Retarder -> Black Box Data Logging
   
    # Complete OBD-II Parameter Coverage
    30: "15",   # OBD Engine RPM -> Black Box Data Logging
    31: "15",   # OBD Engine Load -> Black Box Data Logging
    33: "34",   # OBD Fuel System Status -> Maintenance Alert
    34: "16",   # OBD Short Fuel Trim -> Fuel data report
    35: "16",   # OBD Long Fuel Trim -> Fuel data report
    36: "16",   # OBD Fuel Rail Pressure -> Fuel data report
    38: "15",   # OBD Intake Manifold Pressure -> Black Box Data Logging
    40: "15",   # OBD Timing Advance -> Black Box Data Logging
    41: "16",   # OBD MAF Air Flow Rate -> Fuel data report
    42: "15",   # OBD Throttle Position -> Black Box Data Logging
    43: "15",   # OBD Run Time Since Start -> Black Box Data Logging
    44: "34",   # OBD Distance with MIL -> Maintenance Alert
    45: "37",   # OBD Catalytic Converter Temperature -> High Temperature Alert
    46: "9",    # OBD Control Module Voltage -> Internal Battery Low
    47: "15",   # OBD Engine Load Absolute -> Black Box Data Logging
    49: "15",   # OBD Exhaust Gas Recirculation -> Black Box Data Logging
    50: "16",   # OBD Commanded EGR -> Fuel data report
    51: "34",   # OBD EGR Error -> Maintenance Alert
    52: "16",   # OBD Commanded Evaporative Purge -> Fuel data report
    53: "16",   # OBD Fuel Tank Level Input -> Fuel data report
    54: "34",   # OBD Warm-ups since codes cleared -> Maintenance Alert
    55: "34",   # OBD Distance traveled since codes cleared -> Maintenance Alert
    56: "15",   # OBD Evap System Vapor Pressure -> Black Box Data Logging
    57: "15",   # OBD Absolute Barometric Pressure -> Black Box Data Logging
   
    # Extended Fuel Level System (complete 201-215 range)
    201: "16",  # Fuel Level 1 -> Fuel data report
    202: "16",  # Fuel Level 2 -> Fuel data report
    203: "16",  # Fuel Used 1 -> Fuel data report
    204: "16",  # Fuel Used 2 -> Fuel data report
    207: "16",  # Fuel Rate 1 -> Fuel data report
    208: "16",  # Fuel Rate 2 -> Fuel data report
    209: "16",  # Fuel Consumption GPS -> Fuel data report
    210: "16",  # Fuel Tank Capacity -> Fuel data report
    211: "36",  # Fuel Level Warning (Low) -> Low Fuel Alert
    212: "16",  # Fuel Temperature -> Fuel data report
    213: "16",  # Fuel Density -> Fuel data report
    214: "16",  # Fuel Flow Rate -> Fuel data report
    215: "16",  # Fuel Economy -> Fuel data report
   
    # Complete Driver Identification System (400-409 range)
    400: "24",  # Driver Card 1 -> Ibutton Scan (Regular)
    401: "24",  # Driver Card 2 -> Ibutton Scan (Regular)
    402: "24",  # Driver Card 3 -> Ibutton Scan (Regular)
    403: "24",  # Driver 1 ID -> Ibutton Scan (Regular)
    404: "24",  # Driver 2 ID -> Ibutton Scan (Regular)
    405: "24",  # Driver 3 ID -> Ibutton Scan (Regular)
    406: "24",  # Driver 4 ID -> Ibutton Scan (Regular)
    407: "24",  # Driver 5 ID -> Ibutton Scan (Regular)
    408: "17",  # Unknown Driver -> Invalid Scan
    409: "17",  # Driving without Card -> Invalid Scan
   
    # Additional iButton and RFID elements
    245: "24",  # Driver Identification -> Ibutton Scan (Regular)
    78: "24",   # iButton ID -> Ibutton Scan (Regular)  
    207: "24",  # RFID Tag -> Ibutton Scan (Regular)
    264: "24",  # Barcode ID -> Ibutton Scan (Regular)
    100: "24",  # Magnetic Card ID -> Ibutton Scan (Regular)
   
    # Complete Geofence Zone Coverage (155-231 comprehensive)
    161: "20",  # Geofence Zone 04 Enter -> Enter Boundary
    162: "21",  # Geofence Zone 04 Exit -> Leave Boundary
    163: "20",  # Geofence Zone 05 Enter -> Enter Boundary
    164: "21",  # Geofence Zone 05 Exit -> Leave Boundary
    165: "20",  # Geofence Zone 06 Enter -> Enter Boundary
    166: "21",  # Geofence Zone 06 Exit -> Leave Boundary
    167: "20",  # Geofence Zone 07 Enter -> Enter Boundary
    168: "21",  # Geofence Zone 07 Exit -> Leave Boundary
    169: "20",  # Geofence Zone 08 Enter -> Enter Boundary
    170: "21",  # Geofence Zone 08 Exit -> Leave Boundary
    171: "20",  # Geofence Zone 09 Enter -> Enter Boundary
    172: "21",  # Geofence Zone 09 Exit -> Leave Boundary
    173: "20",  # Geofence Zone 10 Enter -> Enter Boundary
    174: "21",  # Geofence Zone 10 Exit -> Leave Boundary
    175: "20",  # Auto Geofence -> Enter/Leave Boundary
    176: "20",  # Geofence Zone 11 Enter -> Enter Boundary
    177: "21",  # Geofence Zone 11 Exit -> Leave Boundary
    178: "20",  # Geofence Zone 12 Enter -> Enter Boundary
    179: "21",  # Geofence Zone 12 Exit -> Leave Boundary
    180: "20",  # Geofence Zone 13 Enter -> Enter Boundary
    181: "21",  # Geofence Zone 13 Exit -> Leave Boundary
    182: "20",  # Geofence Zone 14 Enter -> Enter Boundary
    183: "21",  # Geofence Zone 14 Exit -> Leave Boundary
    184: "20",  # Geofence Zone 15 Enter -> Enter Boundary
    185: "21",  # Geofence Zone 15 Exit -> Leave Boundary
   
    # Advanced Sensor Network (Environmental)
    76: "15",   # Dallas ID 1 -> Black Box Data Logging
    77: "15",   # Dallas ID 2 -> Black Box Data Logging
    79: "37",   # Dallas Temperature 5 -> High Temperature Alert
    100: "15",  # Magnetic Card ID -> Black Box Data Logging
    101: "37",  # Temperature 1 -> High Temperature Alert
    102: "37",  # Temperature 2 -> High Temperature Alert  
    103: "37",  # Temperature 3 -> High Temperature Alert
    104: "37",  # Temperature 4 -> High Temperature Alert
   
    # Complete Wireless Sensor Network (WSN) Coverage
    10500: "37", # WSN Temperature 1 -> High Temperature Alert
    10501: "37", # WSN Temperature 2 -> High Temperature Alert
    10502: "37", # WSN Temperature 3 -> High Temperature Alert
    10503: "37", # WSN Temperature 4 -> High Temperature Alert
    10504: "37", # WSN Temperature 5 -> High Temperature Alert
    10505: "37", # WSN Temperature 6 -> High Temperature Alert
    10510: "9",  # WSN Battery Level 1 -> Internal Battery Low
    10511: "9",  # WSN Battery Level 2 -> Internal Battery Low
    10512: "9",  # WSN Battery Level 3 -> Internal Battery Low
    10513: "9",  # WSN Battery Level 4 -> Internal Battery Low
    10514: "9",  # WSN Battery Level 5 -> Internal Battery Low
    10515: "9",  # WSN Battery Level 6 -> Internal Battery Low
    10520: "39", # WSN Door Sensor 1 -> Door Open/Close
    10521: "39", # WSN Door Sensor 2 -> Door Open/Close
    10522: "39", # WSN Door Sensor 3 -> Door Open/Close
    10523: "39", # WSN Door Sensor 4 -> Door Open/Close
   
    # Complete EYE Sensor Coverage (IoT sensors)
    10800: "37", # EYE Temperature 1 -> High Temperature Alert
    10801: "37", # EYE Temperature 2 -> High Temperature Alert
    10802: "37", # EYE Temperature 3 -> High Temperature Alert
    10803: "37", # EYE Temperature 4 -> High Temperature Alert
    10804: "37", # EYE Temperature 5 -> High Temperature Alert
    10805: "37", # EYE Temperature 6 -> High Temperature Alert
    10810: "39", # EYE Door Sensor 1 -> Door Open/Close
    10811: "39", # EYE Door Sensor 2 -> Door Open/Close
    10820: "9",  # EYE Low Battery 1 -> Internal Battery Low
    10821: "9",  # EYE Low Battery 2 -> Internal Battery Low
    10822: "9",  # EYE Low Battery 3 -> Internal Battery Low
    10823: "9",  # EYE Low Battery 4 -> Internal Battery Low
    10824: "9",  # EYE Low Battery 5 -> Internal Battery Low
    10825: "9",  # EYE Low Battery 6 -> Internal Battery Low
    10830: "1",  # EYE Movement 1 -> Movement/Logging
    10831: "1",  # EYE Movement 2 -> Movement/Logging
    10832: "1",  # EYE Movement 3 -> Movement/Logging
    10833: "1",  # EYE Movement 4 -> Movement/Logging
   
    # Advanced Telemetry Parameters
    11: "15",   # HDOP -> Black Box Data Logging
    14: "15",   # External Voltage Backup -> Black Box Data Logging
    15: "37",   # Internal Temperature (if high) -> High Temperature Alert
    20: "27",   # GSM Signal Level (when good) -> GPS Signal Restored
    22: "4",    # Speed from OBD -> Speeding (if over limit)
    23: "15",   # PDOP -> Black Box Data Logging
    25: "27",   # GSM Signal Quality -> GPS Signal Restored
    26: "15",   # Ignition Status (detailed) -> Black Box Data Logging
    27: "15",   # Movement Status (detailed) -> Black Box Data Logging
    28: "15",   # Datamode Status -> Black Box Data Logging
    29: "15",   # GSM Registration Status -> Black Box Data Logging
   
    # Extended Digital I/O Coverage
    379: "39",  # Digital Input 4 -> Door Open/Close
    380: "39",  # Digital Output 3 -> Door Open/Close
    381: "14",  # Ground Sense -> Device Tempering
    382: "15",  # Immobilizer Status -> Black Box Data Logging
    383: "15",  # AXL Calibration Status -> Black Box Data Logging
    384: "15",  # AXL X Axis -> Black Box Data Logging
    385: "15",  # AXL Y Axis -> Black Box Data Logging
    386: "15",  # AXL Z Axis -> Black Box Data Logging
   
    # Complete Vehicle Parameter Coverage  
    600: "15",  # PCB Temperature -> Black Box Data Logging
    601: "37",  # Module Temperature -> High Temperature Alert
    602: "15",  # Humidity -> Black Box Data Logging
    603: "15",  # Pressure -> Black Box Data Logging
    604: "15",  # Luminosity -> Black Box Data Logging
   
    # Advanced Event Detection
    1000: "33", # Vehicle Theft Detection -> Vehicle Theft
    1001: "12", # Collision Detection Advanced -> Accident
    1002: "14", # Device Tampering Advanced -> Device Tempering
    1003: "8",  # Emergency Button -> Panic Button (Driver)
    1004: "13", # Passenger Emergency -> Panic Button (Passenger)
    1005: "26", # GPS Jamming Detection -> GPS Signal Lost
    1006: "15", # Communication Lost -> Black Box Data Logging
    1007: "34", # Maintenance Required -> Maintenance Alert
    1008: "36", # Critical Fuel Level -> Low Fuel Alert
    1009: "37", # Critical Temperature -> High Temperature Alert
    1010: "9",  # Critical Battery Level -> Internal Battery Low
}

# Hardware fault codes for activity 16
HARDWARE_FAULT_CODES = {
    0: "Normal",
    1: "Sensor Communication Error",
    2: "Sensor Data Error",
    3: "Sensor Hardware Fault",
    4: "Sensor Configuration Error"
}

class GPSListener:
    def __init__(self):
        self.host = '0.0.0.0'
        self.port = 2000
        self.executor = ThreadPoolExecutor(max_workers=10)  # For async processing
        self.vehicle_cache = {}  # Cache for vehicle lookups
        self.cache_timeout = 300  # 5 minutes cache timeout
        self.last_cache_clean = time.time()
        self.mgs_id_counter = 10000  # Starting counter for dynamic MGS_ID
       
        # IMEI Filter Configuration
        # self.allowed_imeis = set()  # Set of allowed IMEIs
        # self.filter_enabled = False  # Enable/disable IMEI filtering
        # self.load_imei_filter_config()

    def start_listener(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            print(f"Listening on {self.host}:{self.port}")

            while True:
                try:
                    conn, addr = s.accept()
                    conn.settimeout(30)  # Set timeout for connection
                    print(f"Connection from {addr}")
                   
                    # Handle connection in a separate thread
                    self.executor.submit(self.handle_connection, conn, addr)
                   
                except Exception as e:
                    print(f"Error accepting connection: {e}")
                    time.sleep(1)  # Prevent tight loop on errors

    def handle_connection(self, conn, addr):
        device_imei = None
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break

                hex_data = data.hex()
               
                # Check if this is an IMEI packet
                if self.imei_checker(hex_data):
                    device_imei = self.ascii_imei_converter(hex_data)
                    print(f"IMEI received: {device_imei}")
                    conn.sendall((1).to_bytes(1, byteorder="big"))
                    continue

                # Process data if we have an IMEI
                if device_imei:
                    if self.codec_8e_checker(hex_data):
                        try:
                            # Parse the data
                            parsed_data = self.codec_8e_parser(hex_data, device_imei)
                           
                            # Process asynchronously to not block the connection
                            self.executor.submit(
                                self.process_parsed_data,
                                device_imei,
                                hex_data,
                                parsed_data
                            )
                           
                            # Send response to device immediately
                            conn.sendall((len(parsed_data['records'])).to_bytes(4, byteorder="big"))
                           
                        except Exception as e:
                            print(f"Error parsing data: {e}")
                            break

        except socket.timeout:
            print(f"Connection with {addr} timed out")
        except Exception as e:
            print(f"Error handling connection from {addr}: {e}")
        finally:
            conn.close()
            print(f"Connection with {addr} closed")

    def process_parsed_data(self, device_imei, hex_data, parsed_data):
        """Process parsed data asynchronously"""
        try:
            # Clean cache periodically
            if time.time() - self.last_cache_clean > self.cache_timeout:
                self.clean_vehicle_cache()
                self.last_cache_clean = time.time()
           
            # Get vehicle from cache or database
            vehicle = self.get_cached_vehicle(device_imei)
            if not vehicle:
                print(f"⚠️ No vehicle found with IMEI {device_imei} - BUT WILL STILL SEND TO LATRA")
                # Create a temporary vehicle object for LATRA transmission
                from types import SimpleNamespace
                temp_imei = SimpleNamespace()
                temp_imei.imei_number = device_imei
                vehicle = SimpleNamespace()
                vehicle.imei = temp_imei
                vehicle.id = 999999  # Temporary ID for unregistered vehicles
                vehicle.name = device_imei[-6:]  # Use last 6 digits of IMEI without prefix
                vehicle.registration_number = device_imei[-6:]  # Use last 6 digits as registration
                print(f"🚀 SENDING TO LATRA with temporary vehicle profile: {vehicle.name}")
           
            # Send to LATRA (ALWAYS send regardless of vehicle registration)
            success, response = self.send_to_latra(vehicle, parsed_data)
           
            # Save to database only if vehicle exists in database
            if hasattr(vehicle, '_state'):  # Check if it's a real Django model instance
                self.save_reported_data(vehicle, hex_data, parsed_data, response, success)
            else:
                print(f"📝 Skipping database save for unregistered vehicle {device_imei} - LATRA transmission completed")
           
        except Exception as e:
            print(f"Error processing data: {e}")
        finally:
            # Ensure database connection is closed
            connection.close()

    def get_cached_vehicle(self, imei):
        """Get vehicle from cache or database with cache invalidation"""
        now = time.time()
       
        # Check cache first
        if imei in self.vehicle_cache:
            vehicle, timestamp = self.vehicle_cache[imei]
            if now - timestamp < self.cache_timeout:
                return vehicle
       
        # Not in cache or expired, query database
        vehicle = Vehicle.objects.filter(imei__imei_number=imei).first()
        if vehicle:
            self.vehicle_cache[imei] = (vehicle, now)
        return vehicle

    def clean_vehicle_cache(self):
        """Clean expired cache entries"""
        now = time.time()
        expired = [k for k, (_, t) in self.vehicle_cache.items()
                  if now - t > self.cache_timeout]
        for k in expired:
            del self.vehicle_cache[k]

    def save_reported_data(self, vehicle, hex_data, parsed_data, response, success):
        """Save reported data with bulk create optimization if needed"""
        try:
            ReportedData.objects.create(
                vehicle=vehicle,
                raw_data={"hex": hex_data},
                processed_data=parsed_data,
                latra_response=response,
                is_success=success
            )
        except Exception as e:
            print(f"Error saving to database: {e}")

    def imei_checker(self, hex_imei):
        """Check if hex string is a valid IMEI packet"""
        try:
            if len(hex_imei) < 4:
                return False
               
            imei_length = int(hex_imei[:4], 16)
            actual_length = len(hex_imei[4:]) // 2
            return imei_length == actual_length
        except ValueError:
            return False

    def ascii_imei_converter(self, hex_imei):
        """Convert hex IMEI to ASCII"""
        try:
            return bytes.fromhex(hex_imei[4:]).decode('ascii')
        except Exception:
            return "INVALID_IMEI"

    def codec_8e_checker(self, codec8_packet):
        """Check if packet is valid Codec8/8E format"""
        try:
            if len(codec8_packet) < 18:
                return False
           
            codec_type = codec8_packet[16:18]
            return codec_type.upper() in ["8E", "08"]
        except Exception:
            return False

    def safe_hex_to_int(self, hex_str, default=0):
        """Safely convert hex string to integer with error handling"""
        try:
            return int(hex_str, 16) if hex_str else default
        except ValueError:
            return default

    def codec_8e_parser(self, codec8_packet, device_imei):
        """Parse Codec8/8E packet with error handling"""
        result = {
            "device_imei": device_imei,
            "server_time": self.time_stamper_for_json(),
            "raw_data": codec8_packet,
            "records": [],
            "parse_errors": []
        }

        try:
            # Get codec type (8 or 8E)
            codec_type = codec8_packet[16:18]
            data_step = 4 if codec_type.upper() == "8E" else 2

            # Number of records (1 byte after codec type)
            number_of_records = self.safe_hex_to_int(codec8_packet[18:20])
           
            # Start parsing records (skip first 10 bytes of header)
            avl_data_start = codec8_packet[20:]
            data_field_position = 0

            for record_num in range(number_of_records):
                try:
                    record = {
                        "record_number": record_num + 1,
                        "imei": device_imei,
                        "parse_errors": []
                    }

                    # Timestamp (8 bytes)
                    timestamp = avl_data_start[data_field_position:data_field_position+16]
                    record["timestamp"] = self.device_time_stamper(timestamp)
                    record["timestamp_delay"] = self.record_delay_counter(timestamp)
                    data_field_position += 16

                    # Priority (1 byte)
                    priority = avl_data_start[data_field_position:data_field_position+2]
                    record["priority"] = self.safe_hex_to_int(priority)
                    data_field_position += 2

                    # Longitude (4 bytes)
                    longitude = avl_data_start[data_field_position:data_field_position+8]
                    record["longitude"] = self.coordinate_formater(longitude)
                    print(f"DEBUG: Longitude - Hex: {longitude}, Parsed: {record['longitude']}")
                    data_field_position += 8

                    # Latitude (4 bytes)
                    latitude = avl_data_start[data_field_position:data_field_position+8]
                    record["latitude"] = self.coordinate_formater(latitude)
                    print(f"DEBUG: Latitude - Hex: {latitude}, Parsed: {record['latitude']}")
                    data_field_position += 8

                    # Altitude (2 bytes)
                    altitude = avl_data_start[data_field_position:data_field_position+4]
                    record["altitude"] = self.safe_hex_to_int(altitude)
                    data_field_position += 4

                    # Angle (2 bytes)
                    angle = avl_data_start[data_field_position:data_field_position+4]
                    record["angle"] = self.safe_hex_to_int(angle)
                    data_field_position += 4

                    # Satellites (1 byte)
                    satellites = avl_data_start[data_field_position:data_field_position+2]
                    record["satellites"] = self.safe_hex_to_int(satellites)
                    data_field_position += 2

                    # Speed (2 bytes)
                    speed = avl_data_start[data_field_position:data_field_position+4]
                    parsed_speed = self.safe_hex_to_int(speed)
                    record["speed"] = parsed_speed
                   
                    # Debug: Print speed information
                    if parsed_speed > 0:
                        print(f"DEBUG: Speed detected - Raw hex: {speed}, Parsed: {parsed_speed} km/h")
                   
                    data_field_position += 4

                    # Event IO ID (1 or 2 bytes)
                    event_io_id = avl_data_start[data_field_position:data_field_position+data_step]
                    record["event_id"] = self.safe_hex_to_int(event_io_id)
                    data_field_position += data_step

                    # Total IO elements (1 or 2 bytes)
                    total_io_elements = avl_data_start[data_field_position:data_field_position+data_step]
                    total_io_elements_parsed = self.safe_hex_to_int(total_io_elements)
                    data_field_position += data_step

                    # Parse I/O elements
                    io_elements = {}

                    # 1 byte I/O count
                    byte1_io_number = avl_data_start[data_field_position:data_field_position+data_step]
                    byte1_io_number_parsed = self.safe_hex_to_int(byte1_io_number)
                    data_field_position += data_step

                    for _ in range(byte1_io_number_parsed):
                        try:
                            key = avl_data_start[data_field_position:data_field_position+data_step]
                            data_field_position += data_step
                            value = avl_data_start[data_field_position:data_field_position+2]
                            
                            # Special debugging for iButton-related elements
                            key_int = self.safe_hex_to_int(key)
                            if key_int in [245, 78, 403, 404, 405, 406, 407, 207, 264, 100]:
                                print(f"🔑 IBUTTON I/O (1-byte) DETECTED - Key: {key_int}, Raw Hex Value: '{value}'")
                            
                            io_elements[key_int] = self.sorting_hat(
                                key_int,
                                value
                            )
                            data_field_position += 2
                        except Exception as e:
                            record["parse_errors"].append(f"1-byte IO parse error: {str(e)}")
                            continue

                    # 2 byte I/O count
                    byte2_io_number = avl_data_start[data_field_position:data_field_position+data_step]
                    byte2_io_number_parsed = self.safe_hex_to_int(byte2_io_number)
                    data_field_position += data_step

                    for _ in range(byte2_io_number_parsed):
                        try:
                            key = avl_data_start[data_field_position:data_field_position+data_step]
                            data_field_position += data_step
                            value = avl_data_start[data_field_position:data_field_position+4]
                            io_elements[self.safe_hex_to_int(key)] = self.sorting_hat(
                                self.safe_hex_to_int(key),
                                value
                            )
                            data_field_position += 4
                        except Exception as e:
                            record["parse_errors"].append(f"2-byte IO parse error: {str(e)}")
                            continue

                    # 4 byte I/O count
                    byte4_io_number = avl_data_start[data_field_position:data_field_position+data_step]
                    byte4_io_number_parsed = self.safe_hex_to_int(byte4_io_number)
                    data_field_position += data_step

                    for _ in range(byte4_io_number_parsed):
                        try:
                            key = avl_data_start[data_field_position:data_field_position+data_step]
                            data_field_position += data_step
                            value = avl_data_start[data_field_position:data_field_position+8]
                            
                            # Special debugging for iButton-related elements
                            key_int = self.safe_hex_to_int(key)
                            if key_int in [245, 78, 403, 404, 405, 406, 407, 207, 264, 100]:
                                print(f"🔑 IBUTTON I/O (4-byte) DETECTED - Key: {key_int}, Raw Hex Value: '{value}'")
                            
                            io_elements[key_int] = self.sorting_hat(
                                key_int,
                                value
                            )
                            data_field_position += 8
                        except Exception as e:
                            record["parse_errors"].append(f"4-byte IO parse error: {str(e)}")
                            continue

                    # 8 byte I/O count
                    byte8_io_number = avl_data_start[data_field_position:data_field_position+data_step]
                    byte8_io_number_parsed = self.safe_hex_to_int(byte8_io_number)
                    data_field_position += data_step

                    for _ in range(byte8_io_number_parsed):
                        try:
                            key = avl_data_start[data_field_position:data_field_position+data_step]
                            data_field_position += data_step
                            value = avl_data_start[data_field_position:data_field_position+16]
                            
                            # Special debugging for iButton-related elements
                            key_int = self.safe_hex_to_int(key)
                            if key_int in [245, 78, 403, 404, 405, 406, 407, 207, 264, 100]:
                                print(f"🔑 IBUTTON I/O DETECTED - Key: {key_int}, Raw Hex Value: '{value}'")
                            
                            io_elements[key_int] = self.sorting_hat(
                                key_int,
                                value
                            )
                            data_field_position += 16
                        except Exception as e:
                            record["parse_errors"].append(f"8-byte IO parse error: {str(e)}")
                            continue

                    # X byte I/O count (Codec 8E only)
                    if codec_type.upper() == "8E":
                        byteX_io_number = avl_data_start[data_field_position:data_field_position+4]
                        byteX_io_number_parsed = self.safe_hex_to_int(byteX_io_number)
                        data_field_position += 4

                        for _ in range(byteX_io_number_parsed):
                            try:
                                key = avl_data_start[data_field_position:data_field_position+4]
                                data_field_position += 4
                                value_length = avl_data_start[data_field_position:data_field_position+4]
                                data_field_position += 4
                                value = avl_data_start[data_field_position:data_field_position+(2 * self.safe_hex_to_int(value_length))]
                                
                                # Special debugging for iButton-related elements
                                key_int = self.safe_hex_to_int(key)
                                if key_int in [245, 78, 403, 404, 405, 406, 407, 207, 264, 100]:
                                    print(f"🔑 IBUTTON I/O (X-byte) DETECTED - Key: {key_int}, Value Length: {value_length}, Raw Hex Value: '{value}'")
                                
                                io_elements[key_int] = self.sorting_hat(
                                    key_int,
                                    value
                                )
                                data_field_position += len(value)
                            except Exception as e:
                                record["parse_errors"].append(f"X-byte IO parse error: {str(e)}")
                                continue

                    # Add I/O elements to record
                    record["io_elements"] = io_elements

                    # Get event_id for logging
                    event_id = record.get("event_id", 0)

                    # Log all detected events and I/O elements for debugging
                    print(f"\n=== EVENT DETECTION DEBUG FOR RECORD {record_num + 1} ===")
                    print(f"IMEI: {device_imei}")
                    print(f"Timestamp: {record.get('timestamp', 'N/A')}")
                    print(f"Event ID: {event_id} (0x{event_id:02X})")
                    print(f"Available I/O Elements: {list(io_elements.keys())}")
                    if io_elements:
                        print("I/O Element Details:")
                        for io_id, io_value in io_elements.items():
                            print(f"  - I/O {io_id}: {io_value}")
                    print(f"Speed: {record.get('speed', 0)} km/h")
                    print(f"Location: {record.get('latitude', 0)}, {record.get('longitude', 0)}")
                    print("=== END EVENT DETECTION DEBUG ===\n")

                    # Check for activity code and event ID - Priority: Event ID > I/O Elements
                    detected_activity = None
                    latra_activity_id = None
                   
                    # Primary: Check Event ID field (most reliable source)
                    if event_id and event_id != 0:
                        # Map Teltonika Event ID to LATRA Activity ID
                        latra_activity_id = ACTIVITY_CODES.get(event_id)
                        if latra_activity_id and isinstance(latra_activity_id, str) and latra_activity_id.isdigit():
                            detected_activity = int(latra_activity_id)
                            event_activity_name = f"Event ID {event_id} -> LATRA Activity {detected_activity}"
                        else:
                            # For unmapped Event IDs, create reasonable LATRA activity mappings
                            if event_id in [1, 2, 3, 4, 5, 6, 7, 8]:  # Common system events
                                detected_activity = 1  # Default to Movement/Logging
                                event_activity_name = f"System Event {event_id} -> Movement/Logging"
                            else:
                                detected_activity = event_id if event_id <= 50 else 1  # Use event ID if valid LATRA range
                                event_activity_name = ACTIVITY_CODES.get(event_id, f"Event ID {event_id}")
                       
                        print(f"🔥 EVENT ID DETECTED: {event_id} (0x{event_id:02X}) -> LATRA Activity: {detected_activity} ({event_activity_name})")
                        record["activity"] = f"{detected_activity} - {event_activity_name} (Event ID)"
                        # Display activity-specific data for Event ID based activities
                        self.display_activity_specific_data(detected_activity, record)
                   
                    # Secondary: Check I/O element 240 (Movement) if no Event ID
                    elif 240 in io_elements:
                        movement_state = io_elements[240]
                        if movement_state == 1:  # Movement detected
                            detected_activity = 1  # LATRA Activity ID 1 (Movement/Logging)
                            record["activity"] = "1 - Movement/Logging (I/O 240 Movement ON)"
                            print(f"🚗 MOVEMENT DETECTED via I/O 240: Movement ON (State: {movement_state}) -> LATRA Activity 1")
                        elif movement_state == 0:  # Movement stopped
                            detected_activity = 1  # LATRA Activity ID 1 (Movement/Logging)
                            record["activity"] = "1 - Movement/Logging (I/O 240 Movement OFF)"
                            print(f"🛑 MOVEMENT DETECTED via I/O 240: Movement OFF (State: {movement_state}) -> LATRA Activity 1")
                   
                    # Tertiary: Check I/O element 239 (Ignition) if no Event ID or Movement
                    elif 239 in io_elements:
                        ignition_state = io_elements[239]
                        if ignition_state == 1:  # Ignition ON
                            detected_activity = 2  # LATRA Activity ID 2 (Engine ON)
                            record["activity"] = "2 - Engine ON (I/O 239 Ignition ON)"
                            print(f"🔑 IGNITION DETECTED via I/O 239: Ignition ON (State: {ignition_state}) -> LATRA Activity 2")
                        elif ignition_state == 0:  # Ignition OFF
                            detected_activity = 3  # LATRA Activity ID 3 (Engine OFF)
                            record["activity"] = "3 - Engine OFF (I/O 239 Ignition OFF)"
                            print(f"🔑 IGNITION DETECTED via I/O 239: Ignition OFF (State: {ignition_state}) -> LATRA Activity 3")
                   
                    # COMPREHENSIVE I/O ELEMENT DETECTION - Check all I/O elements for activities
                    if not detected_activity:
                        # Check for speeding (Speed field or Event ID 255)
                        speed_value = record.get("speed", 0)
                        try:
                            speed_int = int(speed_value) if isinstance(speed_value, str) else speed_value
                            if speed_int > 80:  # Configurable speed limit
                                detected_activity = 4  # LATRA Activity ID 4 (Speeding)
                                record["activity"] = f"4 - Speeding ({speed_value} km/h)"
                                print(f"🏎️ SPEEDING DETECTED: {speed_value} km/h -> LATRA Activity 4")
                        except (ValueError, TypeError):
                            print(f"DEBUG: Invalid speed value: {speed_value}, skipping speeding check")
                       
                        # ENHANCED I/O ELEMENT MAPPING - Use the comprehensive ACTIVITY_CODES mapping
                        if not detected_activity:
                            # Sort I/O elements by priority (critical events first)
                            priority_io_elements = [
                                # Critical safety events (highest priority)
                                (252, "9", "Unplug (Battery Unplugged) -> Internal Battery Low"),
                                (246, "33", "Towing -> Vehicle Theft"),
                                (247, "12", "Crash Detection -> Accident"),
                                (253, "5", "Green Driving Event (harsh braking) -> Hash Braking"),
                                (254, "7", "Green Driving Value (harsh acceleration) -> Hash Acceleration"),
                                (255, "4", "Over Speeding -> Speeding"),
                                (8, "8", "Panic Button -> Panic Button (Driver)"),
                                (318, "26", "GNSS Jamming -> GPS Signal Lost"),
                               
                                # Driver identification events (high priority for iButton scanning)
                                (78, "24", "iButton -> Ibutton Scan (Regular)"),
                                (245, "24", "Driver ID -> Ibutton Scan (Regular)"),
                                (403, "24", "Driver 1 ID -> Ibutton Scan (Regular)"),
                                (404, "24", "Driver 2 ID -> Ibutton Scan (Regular)"),
                                (405, "24", "Driver 3 ID -> Ibutton Scan (Regular)"),
                                (406, "24", "Driver 4 ID -> Ibutton Scan (Regular)"),
                                (407, "24", "Driver 5 ID -> Ibutton Scan (Regular)"),
                                (408, "17", "Unknown Driver -> Invalid Scan"),
                                (409, "17", "Driving without Card -> Invalid Scan"),
                                (207, "24", "RFID Tag -> Ibutton Scan (Regular)"),
                                (264, "24", "Barcode ID -> Ibutton Scan (Regular)"),
                                (100, "24", "Magnetic Card ID -> Ibutton Scan (Regular)"),
                               
                                # Power management events
                                (67, "9", "Battery Voltage -> Internal Battery Low"),
                                (66, "10", "External Voltage -> External Power Disconnected"),
                                (65, "10", "Power Input 2 -> External Power Disconnected"),
                                (113, "9", "Battery Level -> Internal Battery Low"),
                                (114, "10", "LVCAN Power -> External Power Disconnected"),
                               
                                # Trip and driving events
                                (250, "18", "Trip Start/Stop -> Engine Start/Stop"),
                                (251, "11", "Idling -> Excessive Idle"),
                               
                                # Temperature monitoring
                                (72, "37", "Dallas Temperature 1 -> High Temperature Alert"),
                                (73, "37", "Dallas Temperature 2 -> High Temperature Alert"),
                                (74, "37", "Dallas Temperature 3 -> High Temperature Alert"),
                                (75, "37", "Dallas Temperature 4 -> High Temperature Alert"),
                                (32, "37", "OBD Coolant Temperature -> High Temperature Alert"),
                               
                                # Fuel monitoring
                                (201, "16", "Fuel Level 1 -> Fuel data report"),
                                (202, "16", "Fuel Level 2 -> Fuel data report"),
                                (203, "16", "Fuel Used 1 -> Fuel data report"),
                                (204, "16", "Fuel Used 2 -> Fuel data report"),
                                (211, "36", "Fuel Level Warning -> Low Fuel Alert"),
                                (84, "36", "CAN Fuel Level -> Low Fuel Alert"),
                                (89, "36", "CAN Fuel Level % -> Low Fuel Alert"),
                               
                                # Geofence events (sample - full list too long for inline)
                                (155, "20", "Geofence Zone 01 -> Enter Boundary"),
                                (156, "21", "Geofence Zone 01 Exit -> Leave Boundary"),
                                (157, "20", "Geofence Zone 02 -> Enter Boundary"),
                                (158, "21", "Geofence Zone 02 Exit -> Leave Boundary"),
                               
                                # Digital I/O
                                (1, "39", "Digital Input 1 -> Door Open/Close"),
                                (2, "39", "Digital Input 2 -> Door Open/Close"),
                                (3, "39", "Digital Input 3 -> Door Open/Close"),
                                (381, "14", "Ground Sense -> Device Tempering"),
                               
                                # Environmental sensors
                                (10800, "37", "EYE Temperature 1 -> High Temperature Alert"),
                                (10820, "9", "EYE Low Battery 1 -> Internal Battery Low"),
                                (10500, "37", "WSN Temperature 1 -> High Temperature Alert"),
                                (10510, "9", "WSN Battery Level 1 -> Internal Battery Low"),
                            ]
                           
                            # Check each I/O element present against the priority list
                            for io_id in io_elements:
                                if io_id in ACTIVITY_CODES:
                                    latra_activity = ACTIVITY_CODES[io_id]
                                    if isinstance(latra_activity, str) and latra_activity.isdigit():
                                        io_value = io_elements[io_id]
                                        detected_activity = int(latra_activity)
                                       
                                        # Special handling for specific I/O elements
                                        activity_description = self.get_io_activity_description(io_id, io_value, detected_activity)
                                        record["activity"] = f"{detected_activity} - {activity_description}"
                                        print(f"🔌 I/O ELEMENT {io_id} DETECTED: Value={io_value} -> LATRA Activity {detected_activity} ({activity_description})")
                                        break  # Take first match (priority order)
                       
                        # Check for low internal battery (I/O 67 - Battery Voltage)
                        if not detected_activity and 67 in io_elements:
                            battery_voltage = io_elements[67]  # Already parsed by sorting_hat with 0.01 multiplier
                            try:
                                # battery_voltage is already in volts (parsed by sorting_hat)
                                voltage = float(battery_voltage)
                                   
                                print(f"🔋 BATTERY VOLTAGE CHECK: Parsed={voltage:.2f}V")
                                   
                                # Battery low check - for backup battery, anything below 3.5V is concerning
                                if voltage > 0 and voltage < 3.5:  # Less than 3.5V for backup battery
                                    detected_activity = 9  # LATRA Activity ID 9 (Internal Battery Low)
                                    record["activity"] = f"9 - Internal Battery Low ({voltage:.2f}V)"
                                    print(f"🔋 LOW BATTERY DETECTED: {voltage:.2f}V -> LATRA Activity 9")
                                elif voltage == 0:
                                    # Zero voltage is definitely an issue
                                    detected_activity = 9  # LATRA Activity ID 9 (Internal Battery Low)
                                    record["activity"] = f"9 - Internal Battery Low (0V - No Reading)"
                                    print(f"🔋 ZERO BATTERY VOLTAGE -> LATRA Activity 9")
                                else:
                                    print(f"🔋 BATTERY VOLTAGE NORMAL: {voltage:.2f}V (above 3.5V threshold)")
                                   
                            except (ValueError, TypeError) as e:
                                print(f"DEBUG: Error parsing battery voltage {battery_voltage}: {e}")
                                # Still report as battery event if I/O 67 is present
                                detected_activity = 9
                                record["activity"] = f"9 - Internal Battery Low (Parse Error: {battery_voltage})"
                                print(f"🔋 BATTERY PARSE ERROR -> LATRA Activity 9")
                       
                        # Check for external power disconnection (I/O 66 - External Voltage)
                        if not detected_activity and 66 in io_elements:
                            ext_voltage = io_elements[66]  # Already parsed by sorting_hat with 0.01 multiplier
                            try:
                                # ext_voltage is already in volts (parsed by sorting_hat)
                                voltage = float(ext_voltage)
                                current_speed = record.get("speed", 0)
                                   
                                print(f"🔌 EXTERNAL VOLTAGE CHECK: Parsed={voltage:.2f}V, Speed={current_speed} km/h")
                                   
                                # External power disconnection check
                                if voltage == 0 or (voltage > 0 and voltage < 9.0):  # Less than 9V or 0V
                                    # Device Tampering Logic: External power disconnect at speed ≥20 km/h = Device Tampering
                                    if current_speed >= 20:
                                        detected_activity = 14  # LATRA Activity ID 14 (Device Tampering)
                                        record["activity"] = f"14 - Device Tampering (External power disconnect at {current_speed} km/h, {voltage:.2f}V)"
                                        print(f"⚠️ DEVICE TAMPERING: External power disconnect at {current_speed} km/h ({voltage:.2f}V) -> LATRA Activity 14")
                                    else:
                                        detected_activity = 10  # LATRA Activity ID 10 (External Power Disconnected)
                                        record["activity"] = f"10 - External Power Disconnected ({voltage:.2f}V at {current_speed} km/h)"
                                        print(f"🔌 EXTERNAL POWER DISCONNECTED: {voltage:.2f}V at {current_speed} km/h -> LATRA Activity 10")
                                else:
                                    print(f"🔌 EXTERNAL VOLTAGE NORMAL: {voltage:.2f}V (above 9V threshold)")
                                   
                            except (ValueError, TypeError) as e:
                                print(f"DEBUG: Error parsing external voltage {ext_voltage}: {e}")
                                current_speed = record.get("speed", 0)
                                # Still report as power disconnect/tampering event if I/O 66 is present
                                if current_speed >= 20:
                                    detected_activity = 14
                                    record["activity"] = f"14 - Device Tampering (Parse Error at {current_speed} km/h: {ext_voltage})"
                                    print(f"⚠️ DEVICE TAMPERING PARSE ERROR at {current_speed} km/h -> LATRA Activity 14")
                                else:
                                    detected_activity = 10
                                    record["activity"] = f"10 - External Power Disconnected (Parse Error: {ext_voltage})"
                                    print(f"🔌 EXTERNAL POWER PARSE ERROR -> LATRA Activity 10")
                       
                        # Check for external power status (I/O 252 - External Power Connection Status) - Like PHP EVENT_EXTERNAL_POWER = 252
                        if not detected_activity and 252 in io_elements:
                            ext_power_status = io_elements[252]
                            current_speed = record.get("speed", 0)
                            print(f"🔌 EXTERNAL POWER STATUS CHECK: I/O 252={ext_power_status}, Speed={current_speed} km/h")
                            
                            # I/O 252: 1 = disconnected, 0 = connected
                            if ext_power_status == 1:  # External power disconnected
                                # Device Tampering Logic: External power disconnect at speed ≥20 km/h = Device Tampering
                                if current_speed >= 20:
                                    detected_activity = 14  # LATRA Activity ID 14 (Device Tampering)
                                    record["activity"] = f"14 - Device Tampering (External power status disconnect at {current_speed} km/h)"
                                    print(f"⚠️ DEVICE TAMPERING: External power status disconnect at {current_speed} km/h -> LATRA Activity 14")
                                else:
                                    detected_activity = 10  # LATRA Activity ID 10 (External Power Disconnected)
                                    record["activity"] = f"10 - External Power Disconnected (Status disconnect at {current_speed} km/h)"
                                    print(f"🔌 EXTERNAL POWER STATUS DISCONNECTED: At {current_speed} km/h -> LATRA Activity 10")
                            elif ext_power_status == 0:
                                print(f"🔌 EXTERNAL POWER STATUS CONNECTED: I/O 252=0 (normal)")
                       
                        # Check for trip events (I/O 250 - Trip)
                        if not detected_activity and 250 in io_elements:
                            trip_state = io_elements[250]
                            if trip_state == 1:  # Trip start
                                detected_activity = 18  # LATRA Activity ID 18 (Engine Start)
                                record["activity"] = "18 - Engine Start (Trip Start)"
                                print(f"🚗 TRIP START DETECTED (I/O 250=1) -> LATRA Activity 18")
                            elif trip_state == 0:  # Trip stop
                                detected_activity = 19  # LATRA Activity ID 19 (Engine Stop)
                                record["activity"] = "19 - Engine Stop (Trip Stop)"
                                print(f"🛑 TRIP STOP DETECTED (I/O 250=0) -> LATRA Activity 19")
                        
                        # Check for ignition/journey events (I/O 239 - Ignition/Journey) - COMPREHENSIVE CHECK
                        if not detected_activity and 239 in io_elements:
                            ignition_state = io_elements[239]
                            print(f"🔍 COMPREHENSIVE I/O 239 CHECK: Journey/Ignition state = {ignition_state}")
                            if ignition_state == 1:  # Journey/Ignition ON
                                detected_activity = 2  # LATRA Activity ID 2 (Engine ON)
                                record["activity"] = "2 - Engine ON (I/O 239 Journey/Ignition ON)"
                                print(f"🔑 JOURNEY/IGNITION ON DETECTED (I/O 239=1) -> LATRA Activity 2")
                            elif ignition_state == 0:  # Journey/Ignition OFF
                                detected_activity = 3  # LATRA Activity ID 3 (Engine OFF)
                                record["activity"] = "3 - Engine OFF (I/O 239 Journey/Ignition OFF)"
                                print(f"🔑 JOURNEY/IGNITION OFF DETECTED (I/O 239=0) -> LATRA Activity 3")
                            else:
                                print(f"🔍 I/O 239 has unexpected value: {ignition_state}, treating as status change")
                                # For any other value, treat as journey status change
                                detected_activity = 1  # Default to movement/logging
                                record["activity"] = f"1 - Movement/Logging (I/O 239 Journey Status: {ignition_state})"
                                print(f"🔄 JOURNEY STATUS CHANGE (I/O 239={ignition_state}) -> LATRA Activity 1")
                       
                        # Check for driver identification (I/O 78 - iButton or I/O 245 - Driver ID)
                        if not detected_activity and (78 in io_elements or 245 in io_elements):
                            # Check I/O 78 (iButton) first
                            if 78 in io_elements:
                                ibutton_id = io_elements[78]
                                
                                # Check if the iButton ID is valid (not an error pattern)
                                is_valid_ibutton = False
                                if ibutton_id is not None:
                                    # Convert to string for checking
                                    ibutton_str = str(ibutton_id).replace("0x", "").replace("0X", "").upper().strip()
                                    
                                    # Check for invalid patterns
                                    invalid_patterns = [
                                        "",                    # Empty
                                        "0",                   # Just zero
                                        "00000000",            # 4-byte zeros
                                        "0000000000000000",    # 8-byte zeros  
                                        "FFFFFFFFFFFFFFFF",    # All F's (device error indicator)
                                        "FFFFFFFF",            # 4-byte F's
                                    ]
                                    
                                    is_valid_ibutton = ibutton_str not in invalid_patterns and len(ibutton_str) > 0
                                
                                if is_valid_ibutton:
                                    detected_activity = 24  # LATRA Activity ID 24 (Ibutton Scan Regular)
                                    record["activity"] = f"24 - Ibutton Scan (Regular) - iButton ID: {ibutton_id}"
                                    print(f"👤 VALID IBUTTON SCANNED (I/O 78): {ibutton_id} -> LATRA Activity 24")
                                else:
                                    detected_activity = 17  # LATRA Activity ID 17 (Invalid Scan)
                                    record["activity"] = f"17 - Invalid Scan (Invalid iButton pattern: {ibutton_id})"
                                    print(f"❌ INVALID IBUTTON SCAN (I/O 78): {ibutton_id} -> LATRA Activity 17")
                           
                            # Check I/O 245 (Driver ID) if no I/O 78 or if I/O 78 was invalid
                            elif 245 in io_elements:
                                driver_id = io_elements[245]
                                
                                # Check if the driver ID is valid (not an error pattern)
                                is_valid_driver_id = False
                                if driver_id is not None:
                                    # Convert to string for checking
                                    driver_str = str(driver_id).replace("0x", "").replace("0X", "").upper().strip()
                                    
                                    # Check for invalid patterns
                                    invalid_patterns = [
                                        "",                    # Empty
                                        "0",                   # Just zero
                                        "00000000",            # 4-byte zeros
                                        "0000000000000000",    # 8-byte zeros  
                                        "FFFFFFFFFFFFFFFF",    # All F's (device error indicator)
                                        "FFFFFFFF",            # 4-byte F's
                                    ]
                                    
                                    is_valid_driver_id = driver_str not in invalid_patterns and len(driver_str) > 0
                                
                                if is_valid_driver_id:
                                    detected_activity = 24  # LATRA Activity ID 24 (Ibutton Scan Regular)
                                    record["activity"] = f"24 - Ibutton Scan (Regular) - Driver ID: {driver_id}"
                                    print(f"👤 VALID DRIVER ID SCANNED (I/O 245): {driver_id} -> LATRA Activity 24")
                                else:
                                    detected_activity = 17  # LATRA Activity ID 17 (Invalid Scan)
                                    record["activity"] = f"17 - Invalid Scan (Invalid driver ID pattern: {driver_id})"
                                    print(f"❌ INVALID DRIVER ID SCAN (I/O 245): {driver_id} -> LATRA Activity 17")
                       
                        # Check for harsh driving events (I/O 253 - Green Driving Events)
                        if not detected_activity and 253 in io_elements:
                            green_driving_value = io_elements[253]
                            print(f"🚗 GREEN DRIVING EVENT DETECTED: I/O 253 = {green_driving_value}")
                            
                            if green_driving_value == 1:
                                detected_activity = 7  # LATRA Activity ID 7 (Harsh Acceleration)
                                record["activity"] = f"7 - Hash Acceleration (I/O 253: {green_driving_value})"
                                print(f"⚡ HARSH ACCELERATION DETECTED: I/O 253 = {green_driving_value} -> LATRA Activity 7")
                            elif green_driving_value == 2:
                                detected_activity = 5  # LATRA Activity ID 5 (Harsh Braking)
                                record["activity"] = f"5 - Hash Braking (I/O 253: {green_driving_value})"
                                print(f"🛑 HARSH BRAKING DETECTED: I/O 253 = {green_driving_value} -> LATRA Activity 5")
                            elif green_driving_value == 3:
                                detected_activity = 6  # LATRA Activity ID 6 (Harsh Turning)
                                record["activity"] = f"6 - Hash Turning (I/O 253: {green_driving_value})"
                                print(f"↪️ HARSH TURNING DETECTED: I/O 253 = {green_driving_value} -> LATRA Activity 6")
                            else:
                                print(f"DEBUG: I/O 253 present but unknown value: {green_driving_value}")
                       
                        # Check for panic button (I/O 2 - Digital Input 2 for Driver Panic)
                        if not detected_activity and 2 in io_elements:
                            panic_state = io_elements[2]
                            if panic_state == 1:
                                detected_activity = 8  # LATRA Activity ID 8 (Panic Button Driver)
                                record["activity"] = "8 - Panic Button (Driver) via Digital Input 2"
                                print(f"🆘 DRIVER PANIC BUTTON DETECTED (I/O 2=1) -> LATRA Activity 8")
                       
                        # Check for panic button (I/O 200 - can be panic/emergency)
                        if not detected_activity and 200 in io_elements:
                            panic_state = io_elements[200]
                            if panic_state == 1:
                                detected_activity = 8  # LATRA Activity ID 8 (Panic Button Driver)
                                record["activity"] = "8 - Panic Button (Driver)"
                                print(f"🆘 PANIC BUTTON DETECTED (I/O 200=1) -> LATRA Activity 8")
                       
                        # Check for jamming (I/O elements or specific conditions)
                        if not detected_activity:
                            # GPS Signal quality check
                            gps_signal = record.get("satellites", 0)
                            if gps_signal == 0 and (record.get("latitude", 0) == 0 and record.get("longitude", 0) == 0):
                                detected_activity = 26  # LATRA Activity ID 26 (GPS Signal Lost)
                                record["activity"] = "26 - GPS Signal Lost"
                                print(f"📡 GPS SIGNAL LOST DETECTED -> LATRA Activity 26")
                       
                        # Default fallback - if we have ANY GPS data or I/O elements, use Movement/Logging
                        if not detected_activity:
                            # More inclusive fallback - ANY record should generate an activity
                            if (record.get("latitude", 0) != 0 or record.get("longitude", 0) != 0 or
                                len(io_elements) > 0 or record.get("speed", 0) > 0):
                                detected_activity = 1  # LATRA Activity ID 1 (Movement/Logging Default)
                                record["activity"] = "1 - Movement/Logging (Default Data)"
                                print(f"📊 DEFAULT ACTIVITY for data record -> LATRA Activity 1 (Movement/Logging)")
                           
                            # Even if no GPS or I/O data, still send as basic logging event
                            elif not detected_activity:
                                detected_activity = 15  # LATRA Activity ID 15 (Black Box Data Logging)
                                record["activity"] = "15 - Black Box Data Logging"
                                print(f"📋 BLACK BOX LOGGING (minimal data) -> LATRA Activity 15")
                   
                    # Log final activity detection result
                    if detected_activity:
                        latra_activity_name = ""
                        if detected_activity <= 50:  # Standard LATRA activities
                            latra_activity_name = {
                                1: "Movement/Logging (Default)", 2: "Engine ON", 3: "Engine OFF",
                                4: "Speeding", 5: "Hash Braking", 6: "Hash Turning", 7: "Hash Acceleration",
                                8: "Panic Button (Driver)", 9: "Internal Battery Low", 10: "External Power Disconnected",
                                11: "Excessive Idle", 12: "Accident", 13: "Panic Button (Passenger)",
                                14: "Device Tempering", 15: "Black Box Data Logging", 16: "Fuel data report",
                                17: "Invalid Scan", 18: "Engine Start", 19: "Engine Stop",
                                20: "Enter Boundary", 21: "Leave Boundary", 22: "Enter Checkpoint",
                                23: "Leave Checkpoint", 24: "Ibutton Scan (Regular)"
                            }.get(detected_activity, f"Activity {detected_activity}")
                       
                        print(f"✅ FINAL LATRA ACTIVITY ID: {detected_activity} - {latra_activity_name}")
                        print(f"📊 ACTIVITY SOURCE BREAKDOWN:")
                        print(f"   - Event ID: {event_id} (0x{event_id:02X})")
                        print(f"   - I/O 240 (Movement): {io_elements.get(240, 'N/A')}")
                        print(f"   - I/O 239 (Ignition): {io_elements.get(239, 'N/A')}")
                        print(f"   - Speed: {record.get('speed', 0)} km/h")
                        print(f"   - GPS Valid: {record.get('latitude', 0) != 0 or record.get('longitude', 0) != 0}")
                        print(f"🚀 RECORD WILL BE SENT TO LATRA with Activity ID {detected_activity}")
                    else:
                        print(f"❌ NO ACTIVITY DETECTED:")
                        print(f"   - Event ID: {event_id} (0x{event_id:02X})")
                        print(f"   - I/O 240 (Movement): {io_elements.get(240, 'N/A')}")
                        print(f"   - I/O 239 (Ignition): {io_elements.get(239, 'N/A')}")
                        print(f"   - Available I/O Elements: {list(io_elements.keys())}")
                        print(f"⚠️ RECORD WILL BE SKIPPED FOR LATRA TRANSMISSION")
                   
                    # Store the LATRA activity ID for later use - ENSURE ALWAYS SET
                    if detected_activity is None:
                        # Ultimate failsafe - ALWAYS assign an activity ID
                        detected_activity = 1  # Default to Movement/Logging
                        record["activity"] = "1 - Movement/Logging (Ultimate Failsafe)"
                        print(f"🔄 ULTIMATE FAILSAFE: Assigning Activity ID 1 (Movement/Logging)")
                   
                    record["latra_activity_id"] = detected_activity
                   
                    # GUARANTEE: Every record will now have a LATRA activity ID
                    print(f"🎯 GUARANTEED ACTIVITY ID: {detected_activity} for transmission to LATRA")

                    result["records"].append(record)

                except Exception as e:
                    result["parse_errors"].append(f"Error parsing record {record_num}: {str(e)}")
                    continue

        except Exception as e:
            result["parse_errors"].append(f"Fatal parsing error: {str(e)}")

        # Final summary of all parsed records
        print(f"\n🏁 PARSING COMPLETE SUMMARY:")
        print(f"   📊 Total Records Parsed: {len(result['records'])}")
        for i, record in enumerate(result['records']):
            activity_id = record.get('latra_activity_id', 'None')
            activity_desc = record.get('activity', 'No activity')
            event_id = record.get('event_id', 0)
            print(f"   📄 Record {i+1}: Activity ID {activity_id} - {activity_desc} (Event ID: {event_id})")
       
        if result.get("parse_errors"):
            print(f"   ❌ Parse Errors: {len(result['parse_errors'])}")
            for error in result["parse_errors"]:
                print(f"      - {error}")
       
        print(f"🎯 ALL RECORDS WILL BE SENT TO LATRA (No filtering by activity)\n")

        return result

    def coordinate_formater(self, hex_coordinate):
        """Convert hex coordinate to decimal degrees"""
        try:
            if not hex_coordinate or hex_coordinate == "00000000":
                print(f"DEBUG: Empty or zero coordinate hex: {hex_coordinate}")
                return 0.0
               
            coordinate = self.safe_hex_to_int(hex_coordinate)
            print(f"DEBUG: Raw coordinate int: {coordinate}")
           
            if coordinate == 0:
                print(f"DEBUG: Zero coordinate detected")
                return 0.0
               
            if coordinate & (1 << 31):
                new_int = coordinate - 2 ** 32
                dec_coordinate = new_int / 1e7
                print(f"DEBUG: Negative coordinate - Raw: {coordinate}, Converted: {new_int}, Final: {dec_coordinate}")
            else:
                dec_coordinate = coordinate / 10000000
                print(f"DEBUG: Positive coordinate - Raw: {coordinate}, Final: {dec_coordinate}")
            return dec_coordinate
        except Exception as e:
            print(f"DEBUG: Coordinate parsing error: {e} for hex: {hex_coordinate}")
            return 0.0

    def time_stamper_for_json(self):
        """Generate timestamp string for JSON output"""
        current_server_time = datetime.datetime.now()
        timestamp_utc = datetime.datetime.utcnow()
        return f"{current_server_time.strftime('%H:%M:%S %d-%m-%Y')} (local) / {timestamp_utc.strftime('%H:%M:%S %d-%m-%Y')} (utc)"

    def device_time_stamper(self, timestamp):
        """Convert device timestamp to readable format"""
        try:
            timestamp_ms = self.safe_hex_to_int(timestamp) / 1000
            timestamp_utc = datetime.datetime.utcfromtimestamp(timestamp_ms)
            utc_offset = datetime.datetime.fromtimestamp(timestamp_ms) - datetime.datetime.utcfromtimestamp(timestamp_ms)
            timestamp_local = timestamp_utc + utc_offset
            formatted_timestamp_local = timestamp_local.strftime("%H:%M:%S %d-%m-%Y")
            formatted_timestamp_utc = timestamp_utc.strftime("%H:%M:%S %d-%m-%Y")
            return f"{formatted_timestamp_local} (local) / {formatted_timestamp_utc} (utc)"
        except Exception:
            return "INVALID_TIMESTAMP"

    def record_delay_counter(self, timestamp):
        """Calculate delay between device timestamp and server time"""
        try:
            timestamp_ms = self.safe_hex_to_int(timestamp) / 1000
            current_server_time = datetime.datetime.now().timestamp()
            return f"{int(current_server_time - timestamp_ms)} seconds"
        except Exception:
            return "INVALID_DELAY"

    def get_io_activity_description(self, io_id, io_value, latra_activity_id):
        """Generate detailed activity description for I/O elements"""
       
        # Special handling for specific I/O elements
        if io_id == 250:  # Trip Start/Stop
            if io_value == 1:
                return "Engine Start (Trip Start)"
            elif io_value == 0:
                return "Engine Stop (Trip Stop)"
            else:
                return f"Trip Event (Value: {io_value})"
               
        elif io_id == 239:  # Ignition
            if io_value == 1:
                return "Engine ON (Ignition)"
            elif io_value == 0:
                return "Engine OFF (Ignition)"
            else:
                return f"Ignition Event (Value: {io_value})"
               
        elif io_id == 240:  # Movement
            if io_value == 1:
                return "Movement/Logging (Movement ON)"
            elif io_value == 0:
                return "Movement/Logging (Movement STOP)"
            else:
                return f"Movement Event (Value: {io_value})"
               
        elif io_id == 253:  # Green Driving Events (Harsh Driving)
            if io_value == 1:
                return "Hash Acceleration (Green Driving)"
            elif io_value == 2:
                return "Hash Braking (Green Driving)"
            elif io_value == 3:
                return "Hash Turning (Green Driving)"
            else:
                return f"Green Driving Event (Value: {io_value})"
               
        elif io_id in [67, 113]:  # Battery voltage/level
            return f"Internal Battery Low (Battery: {io_value})"
           
        elif io_id in [66, 65, 114]:  # External power
            return f"External Power Disconnected (Voltage: {io_value})"
           
        elif io_id in [72, 73, 74, 75, 32, 39]:  # Temperature sensors
            return f"High Temperature Alert (Temp: {io_value})"
           
        elif io_id in [201, 202, 203, 204, 207, 208, 209, 210, 212, 213, 214, 215]:  # Fuel data
            return f"Fuel data report (Fuel: {io_value})"
           
        elif io_id in [211, 84, 89]:  # Low fuel
            return f"Low Fuel Alert (Fuel Level: {io_value})"
           
        elif io_id in [78, 403, 404, 405, 406, 407]:  # Driver ID
            return f"Ibutton Scan (Regular) (Driver ID: {io_value})"
           
        elif io_id in [408, 409]:  # Invalid driver
            return f"Invalid Scan (Driver Issue: {io_value})"
           
        elif io_id in range(155, 232):  # Geofence zones
            zone_num = ((io_id - 155) // 2) + 1
            if io_id % 2 == 1:  # Odd = Enter
                return f"Enter Boundary (Zone {zone_num}: {io_value})"
            else:  # Even = Exit
                return f"Leave Boundary (Zone {zone_num}: {io_value})"
               
        elif io_id == 2:  # Digital Input 2 - Driver Panic Button
            return f"Panic Button (Driver) (Input {io_id}: {io_value})"
               
        elif io_id in [1, 3, 379]:  # Other digital inputs
            return f"Door Open/Close (Input {io_id}: {io_value})"
           
        elif io_id in [179, 180, 380]:  # Digital outputs
            return f"Door Open/Close (Output {io_id}: {io_value})"
           
        elif io_id == 381:  # Ground sense
            return f"Device Tempering (Ground Sense: {io_value})"
           
        elif io_id in [252]:  # Battery unplug
            return f"Internal Battery Low (Battery Unplugged: {io_value})"
           
        elif io_id == 246:  # Towing
            return f"Vehicle Theft (Towing Detected: {io_value})"
           
        elif io_id == 247:  # Crash
            return f"Accident (Crash Detection: {io_value})"
           
        elif io_id == 255:  # Over speeding
            return f"Speeding (Over Speed Event: {io_value})"
           
        elif io_id in [253, 17, 18, 19]:  # Accelerometer
            if io_id == 253 or io_id == 19:
                return f"Hash Braking (Z-Axis: {io_value})"
            elif io_id == 17:
                return f"Hash Acceleration (X-Axis: {io_value})"
            elif io_id == 18:
                return f"Hash Turning (Y-Axis: {io_value})"
               
        elif io_id in [318, 249]:  # Jamming
            return f"GPS Signal Lost (Jamming: {io_value})"
           
        elif io_id == 251:  # Idling
            return f"Excessive Idle (Idling: {io_value})"
           
        elif io_id >= 10800 and io_id <= 10833:  # EYE sensors
            if io_id <= 10805:
                return f"High Temperature Alert (EYE Temp {io_id-10799}: {io_value})"
            elif io_id >= 10820 and io_id <= 10825:
                return f"Internal Battery Low (EYE Battery {io_id-10819}: {io_value})"
            elif io_id >= 10830:
                return f"Movement/Logging (EYE Movement {io_id-10829}: {io_value})"
            else:
                return f"EYE Sensor Event (ID {io_id}: {io_value})"
               
        elif io_id >= 10500 and io_id <= 10523:  # WSN sensors
            if io_id <= 10505:
                return f"High Temperature Alert (WSN Temp {io_id-10499}: {io_value})"
            elif io_id >= 10510 and io_id <= 10515:
                return f"Internal Battery Low (WSN Battery {io_id-10509}: {io_value})"
            elif io_id >= 10520:
                return f"Door Open/Close (WSN Door {io_id-10519}: {io_value})"
            else:
                return f"WSN Sensor Event (ID {io_id}: {io_value})"
       
        # OBD-II parameters
        elif io_id >= 30 and io_id <= 57:
            if io_id in [30, 31, 40, 42, 43, 47, 49]:
                return f"Black Box Data Logging (OBD {io_id}: {io_value})"
            elif io_id in [32, 39, 45]:
                return f"High Temperature Alert (OBD Temp {io_id}: {io_value})"
            elif io_id in [34, 35, 36, 41, 50, 52, 53]:
                return f"Fuel data report (OBD Fuel {io_id}: {io_value})"
            elif io_id in [33, 44, 51, 54, 55]:
                return f"Maintenance Alert (OBD {io_id}: {io_value})"
            elif io_id == 46:
                return f"Internal Battery Low (OBD Voltage: {io_value})"
            else:
                return f"OBD Parameter (ID {io_id}: {io_value})"
       
        # CAN Bus parameters
        elif io_id >= 80 and io_id <= 100:
            if io_id in [80, 86, 87, 88, 91, 95, 96, 97, 99, 100]:
                return f"Black Box Data Logging (CAN {io_id}: {io_value})"
            elif io_id in [82, 98]:
                return f"High Temperature Alert (CAN Temp {io_id}: {io_value})"
            elif io_id == 83:
                return f"Fuel data report (CAN Fuel Consumed: {io_value})"
            elif io_id in [84, 89]:
                return f"Low Fuel Alert (CAN Fuel Level: {io_value})"
            elif io_id == 85:
                return f"Movement/Logging (CAN Distance: {io_value})"
            elif io_id == 90:
                return f"Speeding (CAN Wheel Speed: {io_value})"
            elif io_id in [92, 93]:
                return f"Excessive Idle (CAN {io_id}: {io_value})"
            elif io_id == 94:
                return f"Maintenance Alert (CAN Service Distance: {io_value})"
            else:
                return f"CAN Parameter (ID {io_id}: {io_value})"
       
        # Generic descriptions based on LATRA activity ID
        latra_activities = {
            1: "Movement/Logging", 2: "Engine ON", 3: "Engine OFF",
            4: "Speeding", 5: "Hash Braking", 6: "Hash Turning", 7: "Hash Acceleration",
            8: "Panic Button (Driver)", 9: "Internal Battery Low", 10: "External Power Disconnected",
            11: "Excessive Idle", 12: "Accident", 13: "Panic Button (Passenger)",
            14: "Device Tempering", 15: "Black Box Data Logging", 16: "Fuel data report",
            17: "Invalid Scan", 18: "Engine Start", 19: "Engine Stop",
            20: "Enter Boundary", 21: "Leave Boundary", 22: "Enter Checkpoint",
            23: "Leave Checkpoint", 24: "Ibutton Scan (Regular)", 25: "Reserved",
            26: "GPS Signal Lost", 27: "GPS Signal Restored", 28: "Reserved",
            29: "Reserved", 30: "Reserved", 31: "Driver Identification",
            32: "Reserved", 33: "Vehicle Theft", 34: "Maintenance Alert",
            35: "Reserved", 36: "Low Fuel Alert", 37: "High Temperature Alert",
            38: "Reserved", 39: "Door Open/Close", 40: "Reserved"
        }
       
        activity_name = latra_activities.get(latra_activity_id, f"Activity {latra_activity_id}")
        return f"{activity_name} (I/O {io_id}: {io_value})"

    def display_activity_specific_data(self, activity_code, record):
        """Display specific information based on activity code"""
        io_elements = record.get("io_elements", {})
       
        if activity_code == 3:  # Engine OFF
            print("\nENGINE OFF EVENT DETAILS:")
            print(f"Event Time: {record.get('timestamp', 'N/A')}")
            print(f"Location: {record.get('latitude', 'N/A')}, {record.get('longitude', 'N/A')}")
            print(f"Speed at shutdown: {record.get('speed', 'N/A')} km/h")
            print(f"Distance travelled: {io_elements.get(239, 'N/A')} km")
            print(f"Trip duration: {io_elements.get(80, 'N/A')} minutes")
            print(f"Average speed: {io_elements.get(241, 'N/A')} km/h")
            print(f"Max speed: {io_elements.get(242, 'N/A')} km/h")
            print(f"GPS Satellites: {record.get('satellites', 'N/A')}")
            print(f"Engine Hours: {io_elements.get(80, 'N/A')}")
            print(f"Fuel Level: {io_elements.get(16, 'N/A')}%")
            print(f"Battery Voltage: {io_elements.get(66, 'N/A')}V")
       
        elif activity_code == 2:  # Engine ON
            print("\nENGINE ON EVENT DETAILS:")
            print(f"Idle Time: {io_elements.get(11, 'N/A')} seconds")
            print(f"Driver ID: {io_elements.get(245, 'N/A')}")
       
        elif activity_code in (9, 10):  # Battery/Power events
            print("\nPOWER EVENT DETAILS:")
            print(f"External Power Voltage: {io_elements.get(67, 'N/A')}V")
            print(f"Internal Battery Voltage: {io_elements.get(66, 'N/A')}V")
       
        elif activity_code in (17, 24):  # Driver identification events
            print("\nDRIVER IDENTIFICATION DETAILS:")
            driver_id = io_elements.get(245, 'N/A')
            if isinstance(driver_id, str) and driver_id.startswith('0x'):
                driver_id = driver_id[2:]
            print(f"Driver ID (16-digit hex): {driver_id}")
       
        elif activity_code == 16:  # Fuel data report
            print("\nFUEL DATA REPORT DETAILS:")
            print(f"Data Valid Flag: {io_elements.get(250, 'N/A')} (0=valid)")
            print(f"Signal Sensitivity: {io_elements.get(251, 'N/A')}/99")
            print(f"Software Status: {io_elements.get(252, 'N/A')} (0=normal)")
           
            hw_fault_code = io_elements.get(253, 0)
            hw_fault_desc = HARDWARE_FAULT_CODES.get(hw_fault_code, "Unknown fault")
            print(f"Hardware Fault: {hw_fault_code} - {hw_fault_desc}")
           
            print(f"Fuel Level (smoothed): {io_elements.get(16, 'N/A')} mm")
            print(f"Real-time Fuel Level: {io_elements.get(254, 'N/A')} mm")
           
            temp_raw = io_elements.get(255, 0)
            temp_celsius = float(temp_raw) / 10 if isinstance(temp_raw, (int, float)) else 'N/A'
            print(f"Tank Temperature: {temp_celsius}°C")
           
            print(f"Fuel Tank Compartment: {io_elements.get(256, 1)}")
       
        print("END OF ACTIVITY DETAILS\n")

    def parse_driver_id(self, hex_value):
        """Parse driver ID/iButton hex values - properly handle invalid scans"""
        try:
            print(f"🔍 PARSE_DRIVER_ID CALLED with: '{hex_value}' (type: {type(hex_value)})")
            
            if hex_value is None:
                print(f"DEBUG: None iButton hex value, returning empty string")
                return ""
            
            # Convert to string and handle different input types
            if isinstance(hex_value, (int, float)):
                # If it's a number, convert to hex string - KEEP ZEROS!
                clean_hex = f"{int(hex_value):X}".upper()
                print(f"DEBUG: Converted number {hex_value} to hex: {clean_hex}")
            else:
                # Handle string input
                str_value = str(hex_value).strip()
                if not str_value:
                    print(f"DEBUG: Empty string value, returning empty")
                    return ""
                
                # Remove 0x prefix if present and convert to uppercase
                clean_hex = str_value.replace("0x", "").replace("0X", "").upper().strip()
            
            # Debug logging
            print(f"DEBUG: Parsing iButton - Raw: '{hex_value}' -> Clean: '{clean_hex}'")
            
            # Check if it's empty after cleaning
            if not clean_hex:
                print(f"DEBUG: Empty after cleaning, returning empty")
                return ""
            
            # Validate hex characters
            if not all(c in '0123456789ABCDEF' for c in clean_hex):
                print(f"DEBUG: Invalid hex characters in iButton value: '{clean_hex}', returning as-is")
                return str(hex_value)  # Return original value if not valid hex
            
            # Check for invalid scan patterns - these indicate device couldn't read iButton properly
            invalid_patterns = [
                "FFFFFFFFFFFFFFFF",  # All F's - common invalid scan indicator
                "0000000000000000",  # All zeros - empty/null value
            ]
            
            # If we have an exact match for invalid patterns, return empty string
            if clean_hex in invalid_patterns:
                print(f"DEBUG: ⚠️ Invalid iButton scan pattern detected: '{clean_hex}' - returning empty string")
                return ""
            
            # Pad to 16 characters (8 bytes) if needed
            if len(clean_hex) < 16:
                clean_hex = clean_hex.zfill(16)
                print(f"DEBUG: Padded iButton value to 16 chars: '{clean_hex}'")
            elif len(clean_hex) > 16:
                # Take the last 16 characters if too long
                clean_hex = clean_hex[-16:]
                print(f"DEBUG: Truncated iButton value to 16 chars: '{clean_hex}'")
            
            # Send valid iButton ID
            print(f"DEBUG: ✅ Sending valid iButton ID: '{clean_hex}'")
            return clean_hex
            
        except Exception as e:
            print(f"DEBUG: Error parsing iButton hex '{hex_value}': {e}, returning original value")
            return str(hex_value) if hex_value is not None else ""

    def sorting_hat(self, key, value):
        """Parse I/O element based on its ID"""
        parse_functions = {
            240: lambda x: self.safe_hex_to_int(x),
            239: lambda x: self.safe_hex_to_int(x),
            80: lambda x: self.safe_hex_to_int(x),
            241: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.1')),
            242: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.1')),
            11: lambda x: self.safe_hex_to_int(x),
            245: lambda x: self.parse_driver_id(x),  # Use dedicated parser for driver ID
            78: lambda x: self.parse_driver_id(x),   # iButton ID
            403: lambda x: self.parse_driver_id(x),  # Driver 1 ID  
            404: lambda x: self.parse_driver_id(x),  # Driver 2 ID
            405: lambda x: self.parse_driver_id(x),  # Driver 3 ID
            406: lambda x: self.parse_driver_id(x),  # Driver 4 ID
            407: lambda x: self.parse_driver_id(x),  # Driver 5 ID
            207: lambda x: self.parse_driver_id(x),  # RFID Tag
            264: lambda x: self.parse_driver_id(x),  # Barcode ID
            100: lambda x: self.parse_driver_id(x),  # Magnetic Card ID
            66: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.01')),
            67: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.01')),
            16: lambda x: self.safe_hex_to_int(x),
            250: lambda x: self.safe_hex_to_int(x),
            251: lambda x: self.safe_hex_to_int(x),
            252: lambda x: self.safe_hex_to_int(x),
            253: lambda x: self.safe_hex_to_int(x),
            254: lambda x: self.safe_hex_to_int(x),
            255: lambda x: self.safe_hex_to_int(x),
            256: lambda x: self.safe_hex_to_int(x),
            21: lambda x: self.safe_hex_to_int(x),
            200: lambda x: self.safe_hex_to_int(x),
            69: lambda x: self.safe_hex_to_int(x),
            181: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.1')),
            182: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.1')),
            24: lambda x: self.safe_hex_to_int(x),
            205: lambda x: self.safe_hex_to_int(x),
            206: lambda x: self.safe_hex_to_int(x),
            68: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.001')),
            299: lambda x: self.safe_hex_to_int(x),
            1: lambda x: self.safe_hex_to_int(x),
            9: lambda x: self.safe_hex_to_int(x),
            179: lambda x: self.safe_hex_to_int(x),
            12: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.001')),
            13: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.01')),
            17: lambda x: struct.unpack(">i", bytes.fromhex(x.zfill(8)))[0] if x else 0,
            18: lambda x: struct.unpack(">i", bytes.fromhex(x.zfill(8)))[0] if x else 0,
            19: lambda x: struct.unpack(">i", bytes.fromhex(x.zfill(8)))[0] if x else 0,
            10: lambda x: self.safe_hex_to_int(x),
            2: lambda x: self.safe_hex_to_int(x),
            3: lambda x: self.safe_hex_to_int(x),
            6: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.001')),
            180: lambda x: self.safe_hex_to_int(x),
            199: lambda x: self.safe_hex_to_int(x),  # Trip Odometer (meters)
            80: lambda x: self.safe_hex_to_int(x),   # Trip duration (seconds)
            241: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.1')),  # Average speed
            242: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.1')),  # Max speed
        }

        try:
            if key in parse_functions:
                return parse_functions[key](value)
            return f"0x{value}"
        except Exception:
            return f"0x{value}"

    def get_addon_info_for_activity(self, activity_id, io_elements):
        """Generate addon_info based on activity ID"""
        addon_info = {}
       
        if activity_id == 2:  # Engine ON / Trip Start
            if 11 in io_elements:  # Idle time
                addon_info["idleTime"] = str(io_elements[11])
           
            if 245 in io_elements:  # Driver identification
                driver_id = io_elements[245]
                # Convert to 16-digit hex string if needed
                if isinstance(driver_id, str) and driver_id.startswith('0x'):
                    driver_id = driver_id[2:].upper().zfill(16)
                elif isinstance(driver_id, int):
                    driver_id = f"{driver_id:016X}"
                else:
                    driver_id = str(driver_id).upper().zfill(16)
                addon_info["v_driver_identification_no"] = driver_id
               
        elif activity_id == 3:  # Engine OFF / Trip End / Journey Stop
            # Add comprehensive data for journey stop reporting - EXACTLY LIKE PHP VERSION
            print(f"DEBUG: Generating addon_info for Engine OFF (Journey Stop) - Activity ID 3")
            print(f"DEBUG: Available I/O elements: {list(io_elements.keys())}")
            
            # PRIMARY TRIP DATA - Matching PHP getTripSummary() function
            
            # Trip distance - I/O 199 (Trip Odometer) - CONVERT TO KM like PHP
            if 199 in io_elements:  
                trip_distance_meters = io_elements[199]
                trip_distance_km = trip_distance_meters / 1000 if trip_distance_meters else 0  # Convert to km like PHP
                addon_info["distance_travelled"] = str(trip_distance_km)
                print(f"DEBUG: Trip distance from I/O 199: {trip_distance_meters} m = {trip_distance_km} km")
            
            # Trip duration - Calculate like PHP (in minutes, not seconds)
            if 80 in io_elements:  
                duration_seconds = io_elements[80]
                duration_minutes = round(duration_seconds / 60) if duration_seconds else 1  # Convert to minutes like PHP
                duration_minutes = max(1, duration_minutes)  # Minimum 1 minute like PHP
                addon_info["trip_duration"] = str(duration_minutes)
                print(f"DEBUG: Trip duration from I/O 80: {duration_seconds} seconds = {duration_minutes} minutes")
            
            # Average speed during trip - Use device calculated average if available
            avg_speed_found = False
            for speed_io in [241, 17, 18]:  # Check different possible average speed I/Os
                if speed_io in io_elements and not avg_speed_found:  
                    speed_val = io_elements[speed_io]
                    # Validate that this looks like a reasonable speed (not an operator code)
                    if isinstance(speed_val, (int, float)) and 0 <= speed_val <= 200:  # Reasonable speed range
                        addon_info["avgSpeed"] = str(speed_val)
                        print(f"DEBUG: Average speed from I/O {speed_io}: {speed_val} km/h")
                        avg_speed_found = True
           
            # Max speed during trip - Use device calculated max speed if available
            max_speed_found = False
            for speed_io in [242, 19]:  # Check different possible max speed I/Os
                if speed_io in io_elements and not max_speed_found:  
                    speed_val = io_elements[speed_io]
                    # Validate that this looks like a reasonable speed (not some other value)
                    if isinstance(speed_val, (int, float)) and 0 <= speed_val <= 300:  # Reasonable max speed range
                        addon_info["maxSpeed"] = str(speed_val)
                        print(f"DEBUG: Max speed from I/O {speed_io}: {speed_val} km/h")
                        max_speed_found = True
            
            # VOLTAGE DATA - Matching PHP getVoltages() function
            
            # External power voltage - I/O 66 - Like PHP $externalVoltageId = 66
            if 66 in io_elements:  
                ext_voltage = io_elements[66]
                addon_info["ext_power_voltage"] = str(ext_voltage) if ext_voltage else "0"
                print(f"DEBUG: External power voltage from I/O 66: {ext_voltage} V")
            
            # Battery voltage - I/O 67 - Like PHP $batteryVoltageId = 67  
            if 67 in io_elements:  
                battery_voltage = io_elements[67]
                addon_info["int_battery_voltage"] = str(battery_voltage) if battery_voltage else "0"
                print(f"DEBUG: Internal battery voltage from I/O 67: {battery_voltage} V")
            
            # External power connection status - I/O 252 - Like PHP EVENT_EXTERNAL_POWER = 252
            if 252 in io_elements:  
                ext_power_status = io_elements[252]
                addon_info["ext_power_status"] = str(ext_power_status)
                print(f"DEBUG: External power status from I/O 252: {ext_power_status} (1=disconnected)")
            
            # Battery level - I/O 113 - Like PHP EVENT_BATTERY_LOW = 113
            if 113 in io_elements:  
                battery_level = io_elements[113]
                addon_info["battery_level"] = str(battery_level)
                print(f"DEBUG: Battery level from I/O 113: {battery_level}")
            
            # Fuel level - I/O 9 - Like PHP EVENT_FUEL = 9
            if 9 in io_elements and "analog_input_1" not in addon_info:  # Prioritize fuel over generic analog
                fuel_level = io_elements[9]
                addon_info["fuel_level"] = str(fuel_level)
                print(f"DEBUG: Fuel level from I/O 9: {fuel_level}")
            elif 9 in io_elements:  # If already used as analog, still capture as fuel reference
                addon_info["fuel_level_alt"] = str(io_elements[9])
                print(f"DEBUG: Fuel level (alt) from I/O 9: {io_elements[9]}")
            
            # DRIVER IDENTIFICATION - Like PHP iButton collection
            
            # Driver iButton - I/O 78 - Like PHP $ibuttonId = self::EVENT_IBUTTON (78)
            driver_found = False
            for driver_io in [78, 245, 403, 404, 405, 406, 407]:  # Priority to I/O 78 like PHP
                if driver_io in io_elements and not driver_found:
                    driver_id = io_elements[driver_io]
                    if driver_id and str(driver_id).strip() not in ["", "0", "FFFFFFFFFFFFFFFF", "0000000000000000"]:
                        # Format like PHP: pad to 16 chars if needed
                        if isinstance(driver_id, str) and len(driver_id) < 16:
                            driver_id = driver_id.zfill(16)  # Pad with zeros like PHP
                        addon_info["v_driver_identification_no"] = str(driver_id)
                        print(f"DEBUG: Driver ID at journey stop from I/O {driver_io}: {driver_id}")
                        driver_found = True
                        break
            
            # CONFIRMATION/STATUS DATA - Additional context
            
            # Journey status - I/O 239 (for confirmation that ignition is OFF)
            if 239 in io_elements:  
                addon_info["journey_status"] = str(io_elements[239])
                print(f"DEBUG: Journey status from I/O 239: {io_elements[239]} (0=Stop, 1=Start)")
            
            # Movement status - I/O 240 (for confirmation that movement stopped)
            if 240 in io_elements:  
                addon_info["movement_status"] = str(io_elements[240])
                print(f"DEBUG: Movement status from I/O 240: {io_elements[240]} (0=Off, 1=On)")
            
            # Total odometer - I/O 16 (Total Odometer) - Additional tracking
            if 16 in io_elements and "distance_travelled" not in addon_info:  # Only if not used for trip distance
                addon_info["total_odometer"] = str(io_elements[16])
                print(f"DEBUG: Total odometer from I/O 16: {io_elements[16]}")
            
            # ENGINE AND OPERATIONAL DATA
            
            # Engine hours/runtime - I/O 15 (Engine runtime) 
            if 15 in io_elements:  
                addon_info["engine_hours"] = str(io_elements[15])
                print(f"DEBUG: Engine hours from I/O 15: {io_elements[15]}")
                
            # Idle time during trip - I/O 11 (Total idle time) - Important for trip summary
            if 11 in io_elements:  
                addon_info["idleTime"] = str(io_elements[11])  # Use same key name as PHP
                print(f"DEBUG: Idle time from I/O 11: {io_elements[11]} seconds")
            
            # COMMUNICATION QUALITY DATA
            
            # GSM signal quality - I/O 21
            if 21 in io_elements:  
                addon_info["gsm_signal"] = str(io_elements[21])
                print(f"DEBUG: GSM signal from I/O 21: {io_elements[21]}")
            
            if 205 in io_elements:  # GSM cell ID - Like PHP $cellId
                addon_info["cell_id"] = str(io_elements[205])
                print(f"DEBUG: GSM cell ID from I/O 205: {io_elements[205]}")
            
            if 206 in io_elements:  # GSM area code - Like PHP $lac
                addon_info["area_code"] = str(io_elements[206])
                print(f"DEBUG: GSM area code from I/O 206: {io_elements[206]}")
            
            # GPS/GNSS quality indicators - Like PHP HDOP
            if 182 in io_elements:  # HDOP (GPS quality) 
                addon_info["hdop"] = str(io_elements[182])
                print(f"DEBUG: HDOP from I/O 182: {io_elements[182]}")
            
            if 69 in io_elements:  # GNSS status
                addon_info["gnss_status"] = str(io_elements[69])
                print(f"DEBUG: GNSS status from I/O 69: {io_elements[69]}")
            
            # VEHICLE HARDWARE STATUS
            
            # Digital inputs status (doors, ignition accessories) - Like PHP digital outputs
            for digital_io in [1, 2, 3, 4]:  # Common digital inputs
                if digital_io in io_elements:
                    addon_info[f"digital_input_{digital_io}"] = str(io_elements[digital_io])
                    print(f"DEBUG: Digital input {digital_io} from I/O {digital_io}: {io_elements[digital_io]}")
            
            # Digital outputs status - Like PHP EVENT_DIGITAL_OUTPUT_2 = 180
            for output_io in [179, 180, 181, 182]:  # Common digital outputs, including 180 from PHP
                if output_io in io_elements:
                    addon_info[f"digital_output_{output_io}"] = str(io_elements[output_io])
                    print(f"DEBUG: Digital output {output_io} from I/O {output_io}: {io_elements[output_io]}")
            
            # Temperature sensors - Multiple temperature I/O elements
            temp_sensors = {72: "temp_1", 73: "temp_2", 74: "temp_3", 75: "temp_4"}
            for temp_io, temp_name in temp_sensors.items():
                if temp_io in io_elements:
                    addon_info[temp_name] = str(io_elements[temp_io])
                    print(f"DEBUG: Temperature sensor {temp_name} from I/O {temp_io}: {io_elements[temp_io]} °C")
            
            # Additional vehicle metrics
            if 24 in io_elements:  # Speed source/status
                addon_info["speed_source"] = str(io_elements[24])
                print(f"DEBUG: Speed source from I/O 24: {io_elements[24]}")
            
            # Analog inputs - Additional sensor data
            if 9 in io_elements:  # Analog input 1 (could be additional data)
                addon_info["analog_input_1"] = str(io_elements[9])
                print(f"DEBUG: Analog input 1 from I/O 9: {io_elements[9]}")
            
            if 10 in io_elements:  # Analog input 2  
                addon_info["analog_input_2"] = str(io_elements[10])
                print(f"DEBUG: Analog input 2 from I/O 10: {io_elements[10]}")
            
            print(f"DEBUG: COMPREHENSIVE ENGINE OFF addon_info (PHP-style): {addon_info}")
            print(f"DEBUG: Total I/O elements captured: {len([k for k in addon_info.keys() if not k.startswith('DEBUG')])}")
               
        elif activity_id == 19:  # Engine Stop / Trip Stop (similar to Activity 3 but via I/O 250)
            print(f"DEBUG: Generating addon_info for Engine Stop (Trip Stop) - Activity ID 19")
            print(f"DEBUG: Available I/O elements: {list(io_elements.keys())}")
            
            # Trip distance - I/O 199 (Trip Odometer)
            if 199 in io_elements:  
                addon_info["distance_travelled"] = str(io_elements[199])
                print(f"DEBUG: Trip distance from I/O 199: {io_elements[199]} m")
            
            # Total odometer - I/O 16 (Total Odometer) 
            if 16 in io_elements:
                addon_info["total_odometer"] = str(io_elements[16])
                print(f"DEBUG: Total odometer from I/O 16: {io_elements[16]}")
            
            # Trip duration - I/O 80 (Trip duration in seconds)
            if 80 in io_elements:  
                addon_info["trip_duration"] = str(io_elements[80])
                print(f"DEBUG: Trip duration from I/O 80: {io_elements[80]} seconds")
           
            # Average and max speeds (with validation)
            avg_speed_found = False
            for speed_io in [241, 17, 18]:
                if speed_io in io_elements and not avg_speed_found:  
                    speed_val = io_elements[speed_io]
                    if isinstance(speed_val, (int, float)) and 0 <= speed_val <= 200:
                        addon_info["avgSpeed"] = str(speed_val)
                        print(f"DEBUG: Average speed from I/O {speed_io}: {speed_val} km/h")
                        avg_speed_found = True
            
            max_speed_found = False
            for speed_io in [242, 19]:
                if speed_io in io_elements and not max_speed_found:  
                    speed_val = io_elements[speed_io]
                    if isinstance(speed_val, (int, float)) and 0 <= speed_val <= 300:
                        addon_info["maxSpeed"] = str(speed_val)
                        print(f"DEBUG: Max speed from I/O {speed_io}: {speed_val} km/h")
                        max_speed_found = True
            
            # Trip status - I/O 250 (for confirmation)
            if 250 in io_elements:  
                addon_info["trip_status"] = str(io_elements[250])
                print(f"DEBUG: Trip status from I/O 250: {io_elements[250]} (0=Stop, 1=Start)")
            
            # Add all the same comprehensive I/O data as Activity 3 (Engine OFF)
            # Battery voltage - I/O 67
            if 67 in io_elements:  
                addon_info["battery_voltage"] = str(io_elements[67])
                print(f"DEBUG: Battery voltage from I/O 67: {io_elements[67]} V")
            
            # External power voltage - I/O 66
            if 66 in io_elements:  
                addon_info["ext_power_voltage"] = str(io_elements[66])
                print(f"DEBUG: External power voltage from I/O 66: {io_elements[66]} V")
            
            # Journey status - I/O 239 (for confirmation)
            if 239 in io_elements:  
                addon_info["journey_status"] = str(io_elements[239])
                print(f"DEBUG: Journey status from I/O 239: {io_elements[239]} (0=Stop, 1=Start)")
            
            # Movement status - I/O 240 (for confirmation)
            if 240 in io_elements:  
                addon_info["movement_status"] = str(io_elements[240])
                print(f"DEBUG: Movement status from I/O 240: {io_elements[240]} (0=Off, 1=On)")
            
            # GSM signal quality - I/O 21
            if 21 in io_elements:  
                addon_info["gsm_signal"] = str(io_elements[21])
                print(f"DEBUG: GSM signal from I/O 21: {io_elements[21]}")
            
            # Engine hours/runtime - I/O 15 (Engine runtime) 
            if 15 in io_elements:  
                addon_info["engine_hours"] = str(io_elements[15])
                print(f"DEBUG: Engine hours from I/O 15: {io_elements[15]}")
                
            # Idle time during trip - I/O 11 (Total idle time)
            if 11 in io_elements:  
                addon_info["idle_time"] = str(io_elements[11])
                print(f"DEBUG: Idle time from I/O 11: {io_elements[11]} seconds")
            
            # Digital inputs status (doors, ignition accessories)
            for digital_io in [1, 2, 3, 4]:  # Common digital inputs
                if digital_io in io_elements:
                    addon_info[f"digital_input_{digital_io}"] = str(io_elements[digital_io])
                    print(f"DEBUG: Digital input {digital_io} from I/O {digital_io}: {io_elements[digital_io]}")
            
            # Digital outputs status 
            for output_io in [179, 180, 181, 182]:  # Common digital outputs
                if output_io in io_elements:
                    addon_info[f"digital_output_{output_io}"] = str(io_elements[output_io])
                    print(f"DEBUG: Digital output {output_io} from I/O {output_io}: {io_elements[output_io]}")
            
            # Temperature sensors
            temp_sensors = {72: "temp_1", 73: "temp_2", 74: "temp_3", 75: "temp_4"}
            for temp_io, temp_name in temp_sensors.items():
                if temp_io in io_elements:
                    addon_info[temp_name] = str(io_elements[temp_io])
                    print(f"DEBUG: Temperature sensor {temp_name} from I/O {temp_io}: {io_elements[temp_io]} °C")
            
            # GPS/GNSS quality indicators
            if 69 in io_elements:  # GNSS status
                addon_info["gnss_status"] = str(io_elements[69])
                print(f"DEBUG: GNSS status from I/O 69: {io_elements[69]}")
            
            if 182 in io_elements:  # HDOP (GPS quality)
                addon_info["hdop"] = str(io_elements[182])
                print(f"DEBUG: HDOP from I/O 182: {io_elements[182]}")
            
            # Driver identification at trip end
            driver_found = False
            for driver_io in [78, 245, 403, 404, 405, 406, 407]:
                if driver_io in io_elements and not driver_found:
                    driver_id = io_elements[driver_io]
                    if driver_id and str(driver_id).strip() not in ["", "0", "FFFFFFFFFFFFFFFF", "0000000000000000"]:
                        addon_info["driver_at_stop"] = str(driver_id)
                        print(f"DEBUG: Driver at trip stop from I/O {driver_io}: {driver_id}")
                        driver_found = True
                
            print(f"DEBUG: Enhanced addon_info for Trip Stop: {addon_info}")
               
        elif activity_id in [9, 10]:  # Power status events
            if 67 in io_elements:  # Internal battery voltage (backup battery)
                addon_info["int_battery_voltage"] = str(io_elements[67])
           
            if 66 in io_elements:  # External power voltage (main vehicle power)
                addon_info["ext_power_voltage"] = str(io_elements[66])
               
        elif activity_id == 8:  # Panic Button (Driver) events
            print(f"DEBUG: Generating addon_info for Panic Button (Driver) - Activity ID 8")
            print(f"DEBUG: Available I/O elements: {list(io_elements.keys())}")
            
            # Panic button source information
            if 2 in io_elements:  # Digital Input 2 (main panic button)
                addon_info["panic_source"] = "Digital Input 2"
                addon_info["panic_state"] = str(io_elements[2])
                print(f"DEBUG: Panic button from I/O 2: {io_elements[2]}")
            elif 200 in io_elements:  # Alternative panic button I/O
                addon_info["panic_source"] = "I/O Element 200"
                addon_info["panic_state"] = str(io_elements[200])
                print(f"DEBUG: Panic button from I/O 200: {io_elements[200]}")
            
            # Location information for emergency response
            if 21 in io_elements:  # GSM signal quality
                addon_info["gsm_signal"] = str(io_elements[21])
                print(f"DEBUG: GSM signal during panic: {io_elements[21]}")
            
            # Battery status during emergency
            if 67 in io_elements:  # Internal battery voltage
                addon_info["battery_voltage"] = str(io_elements[67])
                print(f"DEBUG: Battery voltage during panic: {io_elements[67]} V")
            
            print(f"DEBUG: Final addon_info for Panic Button: {addon_info}")
               
        elif activity_id in [5, 6, 7]:  # Harsh Driving Events (Braking, Turning, Acceleration)
            print(f"DEBUG: Generating addon_info for Harsh Driving Event - Activity ID {activity_id}")
            print(f"DEBUG: Available I/O elements: {list(io_elements.keys())}")
            
            # Harsh driving type from I/O 253 (Green Driving)
            if 253 in io_elements:
                green_driving_value = io_elements[253]
                driving_type_map = {1: "Harsh Acceleration", 2: "Harsh Braking", 3: "Harsh Turning"}
                driving_type = driving_type_map.get(green_driving_value, f"Unknown ({green_driving_value})")
                addon_info["driving_event_type"] = driving_type
                addon_info["green_driving_value"] = str(green_driving_value)
                print(f"DEBUG: Green driving event from I/O 253: {driving_type} (value: {green_driving_value})")
            
            # Speed during harsh driving event
            # Note: Speed is typically in the main record, but we can check for speed-related I/O elements too
            speed_ios = [181, 182, 241, 242]  # Various speed-related I/O elements
            for speed_io in speed_ios:
                if speed_io in io_elements:
                    addon_info[f"speed_io_{speed_io}"] = str(io_elements[speed_io])
                    print(f"DEBUG: Speed data from I/O {speed_io}: {io_elements[speed_io]}")
            
            # Accelerometer data if available
            accel_ios = [17, 18, 19]  # X, Y, Z axis accelerometer
            for accel_io in accel_ios:
                if accel_io in io_elements:
                    axis_name = {17: "X-axis", 18: "Y-axis", 19: "Z-axis"}[accel_io]
                    addon_info[f"accelerometer_{axis_name.lower()}"] = str(io_elements[accel_io])
                    print(f"DEBUG: Accelerometer {axis_name} from I/O {accel_io}: {io_elements[accel_io]}")
            
            # GSM signal quality during event
            if 21 in io_elements:
                addon_info["gsm_signal"] = str(io_elements[21])
                print(f"DEBUG: GSM signal during harsh driving: {io_elements[21]}")
            
            print(f"DEBUG: Final addon_info for Harsh Driving Event: {addon_info}")
               
        elif activity_id in [17, 24]:  # Invalid Scan and Regular Ibutton Scan
            # Check multiple possible I/O elements for driver ID
            driver_id = None
            raw_driver_value = None
            
            print(f"DEBUG: Processing iButton scan event (Activity {activity_id})")
            print(f"DEBUG: Available I/O elements: {list(io_elements.keys())}")
            
            # Priority order: I/O 245 (Driver ID), I/O 78 (iButton), then others
            for io_id in [245, 78, 403, 404, 405, 406, 407, 207, 264, 100]:
                if io_id in io_elements:
                    potential_driver_id = io_elements[io_id]
                    raw_driver_value = potential_driver_id  # Store the raw value
                    print(f"DEBUG: Found driver ID in I/O {io_id}: '{potential_driver_id}' (type: {type(potential_driver_id)})")
                    
                    # Use ANY value found - don't reject zeros or any other values
                    if potential_driver_id is not None:
                        driver_id = str(potential_driver_id)
                        print(f"DEBUG: Using driver ID: '{driver_id}' from I/O {io_id}")
                        break
                    else:
                        print(f"DEBUG: Null driver ID from I/O {io_id}")
                        
            # Process the driver ID based on activity type and content
            if driver_id is not None:
                # Check if the raw value indicates an invalid scan
                is_invalid_scan = False
                if isinstance(raw_driver_value, str):
                    clean_raw = raw_driver_value.replace("0x", "").replace("0X", "").upper().strip()
                    is_invalid_scan = clean_raw in ["FFFFFFFFFFFFFFFF", "0000000000000000"]
                elif isinstance(raw_driver_value, int):
                    # Check for patterns like -1 (0xFFFFFFFFFFFFFFFF) or 0
                    is_invalid_scan = (raw_driver_value == -1 or 
                                     raw_driver_value == 0 or 
                                     hex(raw_driver_value).upper().replace("0X", "").replace("-", "F") == "FFFFFFFFFFFFFFFF")
                
                if activity_id == 17:  # Invalid Scan
                    # For invalid scans, we can send the error indicator or empty
                    if is_invalid_scan:
                        addon_info["v_driver_identification_no"] = ""  # Empty for invalid
                        print(f"DEBUG: Invalid scan (Activity 17) with invalid pattern - sending empty string")
                    else:
                        # Unexpected: got valid-looking ID on invalid scan event
                        addon_info["v_driver_identification_no"] = driver_id
                        print(f"DEBUG: Invalid scan (Activity 17) but got valid-looking ID: '{driver_id}'")
                        
                elif activity_id == 24:  # Regular iButton Scan
                    if is_invalid_scan:
                        # Device couldn't read the iButton properly - send empty
                        addon_info["v_driver_identification_no"] = ""
                        print(f"DEBUG: Regular scan (Activity 24) failed to read iButton - sending empty string")
                    else:
                        # Valid scan with actual iButton data
                        addon_info["v_driver_identification_no"] = driver_id
                        print(f"DEBUG: Regular scan (Activity 24) with valid iButton ID: '{driver_id}'")
                        
                print(f"DEBUG: Final driver ID for activity {activity_id}: '{addon_info.get('v_driver_identification_no', '')}'")
            else:
                # No driver ID found in any I/O element
                addon_info["v_driver_identification_no"] = ""
                print(f"DEBUG: No driver ID found for activity {activity_id}, sending empty string")
       
        return addon_info if addon_info else None

    def get_fuel_info_for_activity(self, activity_id, io_elements):
        """Generate fuel_info based on activity ID"""
        if activity_id != 16:  # Only for fuel data report
            return None
           
        fuel_info = {}
       
        if 250 in io_elements:  # Data valid flag
            fuel_info["validFlag"] = str(io_elements[250])
       
        if 251 in io_elements:  # Signal sensitivity
            fuel_info["signalLevel"] = str(io_elements[251])
       
        if 252 in io_elements:  # Software status
            fuel_info["softStatus"] = str(io_elements[252])
       
        if 253 in io_elements:  # Hardware fault code
            fuel_info["hardFault"] = str(io_elements[253])
       
        if 16 in io_elements:  # Fuel level (smoothed)
            fuel_info["fuelLevel"] = str(io_elements[16])
       
        if 254 in io_elements:  # Real-time fuel level
            fuel_info["rtFuelLevel"] = str(io_elements[254])
       
        if 255 in io_elements:  # Tank temperature (already multiplied by 10)
            fuel_info["tankTemp"] = str(io_elements[255])
       
        if 256 in io_elements:  # Fuel tank compartment
            fuel_info["channel"] = str(io_elements[256])
        else:
            fuel_info["channel"] = "1"  # Default value
       
        return fuel_info if fuel_info else None

    def generate_dynamic_mgs_id(self):
        """Generate dynamic MGS_ID with incrementing counter and timestamp"""
        import random
       
        # Increment counter and reset if it gets too high
        self.mgs_id_counter += 1
        if self.mgs_id_counter > 99999:
            self.mgs_id_counter = 10000
       
        # Add some randomness based on current time
        timestamp_part = int(time.time()) % 10000  # Last 4 digits of timestamp
        random_part = random.randint(100, 999)  # 3-digit random number
       
        # Combine counter with timestamp and random parts
        dynamic_id = f"{self.mgs_id_counter}{timestamp_part % 100}{random_part % 100}"
       
        return dynamic_id[:8]  # Ensure it's not too long

    def send_to_latra(self, vehicle, data):
        """Send data to LATRA API with retry logic and activity-specific addon_info"""
        max_retries = 3
        retry_delay = 1  # seconds
       
        for attempt in range(max_retries):
            try:
                # Prepare payload for each record
                items = []
                for record in data['records']:
                    try:
                        # Parse timestamp from the format "HH:MM:SS DD-MM-YYYY (local) / HH:MM:SS DD-MM-YYYY (utc)"
                        timestamp_str = record["timestamp"].split(" (")[0]
                        try:
                            timestamp = int(datetime.datetime.strptime(
                                timestamp_str,
                                "%H:%M:%S %d-%m-%Y"
                            ).timestamp() * 1000)
                           
                            # Validate timestamp (should be reasonable)
                            current_time = int(time.time() * 1000)
                            if timestamp <= 0 or timestamp > current_time + (24 * 60 * 60 * 1000):  # Not in future by more than 1 day
                                print(f"Warning: Invalid timestamp {timestamp}, using current time")
                                timestamp = current_time
                               
                        except Exception as e:
                            print(f"Error parsing timestamp {timestamp_str}: {e}, using current time")
                            timestamp = int(time.time() * 1000)
                       
                        # Extract activity ID from stored LATRA activity ID (already mapped)
                        io_elements = record.get("io_elements", {})
                        event_id = record.get("event_id", 0)
                       
                        # Use the pre-calculated LATRA activity ID from parsing
                        activity_id = record.get("latra_activity_id")
                        activity_source = "none"
                       
                        # Fallback logic if latra_activity_id is not set
                        if activity_id is None:
                            # Primary: Use Event ID field and map to LATRA activity
                            if event_id and event_id != 0:
                                latra_mapping = ACTIVITY_CODES.get(event_id)
                                if latra_mapping and isinstance(latra_mapping, str) and latra_mapping.isdigit():
                                    activity_id = int(latra_mapping)
                                else:
                                    activity_id = event_id  # Use Event ID directly if no mapping
                                activity_source = "Event ID"
                                print(f"DEBUG: Fallback - Using Event ID as activity: {activity_id}")
                           
                            # Secondary: Use I/O 240 (Movement) -> LATRA Activity 1
                            elif 240 in io_elements:
                                activity_id = 1  # LATRA Movement/Logging activity
                                activity_source = "I/O 240 (Movement)"
                                movement_state = io_elements[240]
                                print(f"DEBUG: Fallback - Using I/O 240 as activity: {activity_id}, state: {movement_state}")
                           
                            # Tertiary: Use I/O 239 (Ignition) -> LATRA Activity 2/3
                            elif 239 in io_elements:
                                ignition_state = io_elements[239]
                                activity_id = 2 if ignition_state == 1 else 3  # Engine ON/OFF
                                activity_source = "I/O 239 (Ignition)"
                                print(f"DEBUG: Fallback - Using I/O 239 as activity: {activity_id}, state: {ignition_state}")
                           
                            # Final fallback: Use default movement activity for any GPS record
                            else:
                                activity_id = 1  # Default LATRA Movement/Logging activity
                                activity_source = "Default fallback"
                                print(f"DEBUG: Final fallback - Using default activity: {activity_id}")
                        else:
                            activity_source = "Pre-calculated LATRA mapping"
                       
                        # Ensure we always have an activity ID (should never be None now)
                        if activity_id is None:
                            activity_id = 1  # Ultimate fallback to Movement/Logging
                            print(f"DEBUG: Ultimate fallback - Using activity ID: {activity_id}")
                       
                        # Special debugging for iButton events
                        if activity_id in [17, 24]:
                            print(f"\n🔑 IBUTTON EVENT DETECTED!")
                            print(f"   Activity ID: {activity_id} ({'Invalid Scan' if activity_id == 17 else 'Regular iButton Scan'})")
                            print(f"   Activity Source: {activity_source}")
                            print(f"   Available I/O Elements: {list(io_elements.keys())}")
                            
                            # Check all possible driver ID sources
                            for io_id in [245, 78, 403, 404, 405, 406, 407, 207, 264, 100]:
                                if io_id in io_elements:
                                    raw_value = io_elements[io_id]
                                    print(f"   📱 I/O {io_id}: '{raw_value}' (type: {type(raw_value)})")
                       
                        print(f"DEBUG: Final LATRA Activity ID for transmission: {activity_id} (source: {activity_source})")
                       
                        # Generate dynamic MGS_ID for this record
                        dynamic_mgs_id = self.generate_dynamic_mgs_id()
                       
                        # Get speed value
                        speed_value = record.get("speed", 0)
                       
                        print(f"🎯 LATRA TRANSMISSION DETAILS:")
                        print(f"   📍 Activity ID: {activity_id} (Source: {activity_source})")
                        print(f"   🚗 Speed: {speed_value} km/h")
                        print(f"   📱 IMEI: {vehicle.imei.imei_number}")
                        print(f"   🚙 Vehicle: {getattr(vehicle, 'name', 'Unknown')}")
                        print(f"   🌐 GPS: Will be determined after coordinate validation")
                        print(f"   ⏰ Timestamp: {timestamp}")
                        if event_id and event_id != 0:
                            event_name = ACTIVITY_CODES.get(event_id, f"Event {event_id}")
                            print(f"   🔢 Event ID: {event_id} (0x{event_id:02X}) - {event_name}")
                        if io_elements:
                            print(f"   🔌 I/O Elements: {len(io_elements)} elements")
                            for io_id, io_value in list(io_elements.items())[:5]:  # Show first 5
                                print(f"      - I/O {io_id}: {io_value}")
                            if len(io_elements) > 5:
                                print(f"      ... and {len(io_elements) - 5} more I/O elements")
                        print(f"   🚀 STATUS: PREPARING FOR LATRA TRANSMISSION ✅")
                       
                        # Build base item with proper validation
                        latitude = record.get("latitude", 0)
                        longitude = record.get("longitude", 0)
                       
                        print(f"🔍 COORDINATE DEBUG:")
                        print(f"   Raw latitude: {latitude} (type: {type(latitude)})")
                        print(f"   Raw longitude: {longitude} (type: {type(longitude)})")
                        print(f"   Activity ID: {activity_id}")
                        print(f"   Record data: {record.get('latitude')}, {record.get('longitude')}")
                       
                        # Define activities that don't require valid GPS coordinates or can use fallback
                        non_gps_activities = [2, 3, 8, 9, 10, 14, 15, 16, 17, 18, 19, 24, 26, 31, 34]  # Engine events, Panic, Battery, Power, Device events, etc.
                       
                        # More inclusive coordinate validation
                        coordinates_valid = False
                       
                        # Check if coordinates are in valid range
                        if (-90.0 <= latitude <= 90.0) and (-180.0 <= longitude <= 180.0):
                            if latitude != 0.0 or longitude != 0.0:
                                coordinates_valid = True
                                print(f"✅ VALID GPS COORDINATES: ({latitude:.6f}, {longitude:.6f})")
                            else:
                                # (0,0) coordinates - acceptable for some activities
                                if activity_id in non_gps_activities:
                                    # Use Nairobi as fallback for non-GPS activities
                                    latitude = -1.286389
                                    longitude = 36.817223
                                    coordinates_valid = True
                                    print(f"🌍 NON-GPS ACTIVITY: Using Nairobi coordinates ({latitude:.6f}, {longitude:.6f})")
                                else:
                                    # For GPS-dependent activities, use fallback coordinates but mark as valid
                                    latitude = -1.286389
                                    longitude = 36.817223
                                    coordinates_valid = True
                                    print(f"⚠️ GPS ACTIVITY WITH (0,0): Using Nairobi fallback ({latitude:.6f}, {longitude:.6f})")
                        else:
                            # Invalid coordinates - still allow for non-GPS activities
                            if activity_id in non_gps_activities:
                                latitude = -1.286389
                                longitude = 36.817223
                                coordinates_valid = True
                                print(f"🔧 INVALID GPS FOR NON-GPS ACTIVITY: Using Nairobi coordinates ({latitude:.6f}, {longitude:.6f})")
                            else:
                                print(f"❌ INVALID COORDINATES FOR GPS ACTIVITY: ({latitude},{longitude}) - WILL STILL SEND WITH FALLBACK")
                                latitude = -1.286389
                                longitude = 36.817223
                                coordinates_valid = True
                       
                        # ALWAYS try to send to LATRA - let LATRA decide if coordinates are acceptable
                        if not coordinates_valid:
                            latitude = -1.286389
                            longitude = 36.817223
                            print(f"� FINAL FALLBACK: Using Nairobi coordinates ({latitude:.6f}, {longitude:.6f})")
                       
                        # Special debugging for Journey Stop events (Activity 3)
                        if activity_id == 3:
                            print(f"\n🛑 JOURNEY STOP EVENT DEBUG:")
                            print(f"   📍 Raw Coordinates: lat={latitude}, lon={longitude}")
                            print(f"   🌐 Coordinate Valid: {coordinates_valid}")
                            print(f"   🔌 Available I/O Elements: {list(io_elements.keys())}")
                            print(f"   📊 Key I/O Values:")
                            for key in [239, 240, 16, 199, 80, 21, 66, 67]:
                                if key in io_elements:
                                    print(f"      I/O {key}: {io_elements[key]}")
                            print(f"   🚀 Will send to LATRA: YES (Activity 3 is in non_gps_activities)")
                       
                        print(f"📍 FINAL COORDINATES TO SEND: ({latitude:.6f}, {longitude:.6f})")
                       
                       
                        # Extract additional LATRA required fields from I/O elements - ONLY REAL DATA
                        io_elements = record.get("io_elements", {})
                       
                        # Satellite Count - Only from parsed GPS data
                        satellite_count = record.get("satellites", 0)
                        # NO DEFAULT from I/O elements
                       
                        # HDOP (Horizontal Dilution of Precision) - Only from actual I/O
                        hdop_value = "0"  # Default to 0 (unknown) instead of fake value
                        if 182 in io_elements:  # GPS HDOP
                            hdop_value = f"{io_elements[182] / 10:.1f}"
                        # NO ESTIMATION from other I/O elements
                       
                        # GPS Mode (2D/3D) - Only from actual I/O
                        gps_mode = "0"  # Default to 0 (unknown) instead of fake 3D
                        if 181 in io_elements:  # GPS Fix Type
                            fix_type = io_elements[181]
                            gps_mode = "2" if fix_type == 2 else "3"
                        elif satellite_count >= 4:
                            gps_mode = "3"  # Only if we have enough satellites
                        elif satellite_count > 0:
                            gps_mode = "2"  # 2D if some satellites
                       
                        # RSSI (Received Signal Strength Indication) - From I/O 21 like PHP
                        rssi_value = "0"  # Default to 0 (unknown)
                        if 21 in io_elements:  # GSM Signal Strength
                            signal_raw = io_elements[21]
                            try:
                                # Apply PHP logic: $rssi = $rssv ? $rssv * 6 : 0;
                                signal_int = int(signal_raw)
                                if signal_int > 0:
                                    rssi_value = str(signal_int * 6)  # Multiply by 6 like PHP
                                    print(f"DEBUG: RSSI calculation: {signal_int} * 6 = {rssi_value}")
                                else:
                                    rssi_value = "0"
                            except (ValueError, TypeError):
                                rssi_value = "0"
                        # NO ESTIMATION from other sources
                       
                        # LAC (Location Area Code) - From I/O 206 (GSM Area Code) like PHP
                        lac_value = "0"  # Default to 0 (unknown)
                        if 206 in io_elements:  # GSM Area Code - CORRECT I/O for LAC
                            lac_raw = io_elements[206]
                            try:
                                # Validate LAC range (should be 1-65534, if > 65536 set to 0 like PHP)
                                lac_int = int(lac_raw)
                                if lac_int > 0 and lac_int <= 65534:
                                    lac_value = str(lac_int)
                                else:
                                    lac_value = "0"
                                    print(f"DEBUG: LAC {lac_int} out of range, setting to 0 like PHP logic")
                            except (ValueError, TypeError):
                                lac_value = "0"
                        # NO EXTRACTION from other operator codes
                       
                        # Cell ID - From I/O 205 (GSM Cell ID) like PHP
                        cell_id_value = "0"  # Default to 0 (unknown)
                        if 205 in io_elements:  # GSM Cell ID - CORRECT I/O for Cell ID
                            cell_id_raw = io_elements[205]
                            try:
                                cell_id_int = int(cell_id_raw)
                                if cell_id_int > 0:
                                    cell_id_value = str(cell_id_int)
                            except (ValueError, TypeError):
                                cell_id_value = "0"
                        # NO FALLBACK to other I/O elements
                       
                        # MCC (Mobile Country Code) - Use Tanzania code like PHP
                        mcc_value = "640"  # Tanzania MCC like PHP hardcoded value "640"
                        # In PHP: "MCC" => "640", //tanzania
                        
                        # Alternative: Extract from GSM Operator Code if available
                        if 14 in io_elements:  # GSM Operator Code
                            operator_code = io_elements[14]
                            try:
                                # Ensure operator_code is an integer for comparison
                                operator_code_int = int(operator_code) if isinstance(operator_code, str) else operator_code
                                if operator_code_int > 100000:
                                    extracted_mcc = str(operator_code_int)[:3]
                                    # Use extracted MCC if it looks valid, otherwise keep Tanzania default
                                    if extracted_mcc in ["640", "639", "641"]:  # Valid Tanzania/East Africa MCCs
                                        mcc_value = extracted_mcc
                                        print(f"DEBUG: Using extracted MCC: {extracted_mcc}")
                                    else:
                                        print(f"DEBUG: Non-Tanzania MCC {extracted_mcc}, keeping default 640")
                            except (ValueError, TypeError):
                                print(f"DEBUG: Invalid operator code: {operator_code}, using Tanzania MCC 640")
                       
                        print(f"📊 LATRA GSM/NETWORK FIELDS - CORRECTED I/O MAPPINGS:")
                        print(f"   🛰️ Satellite Count: {satellite_count} (Source: {'GPS data' if satellite_count > 0 else 'NOT AVAILABLE'})")
                        print(f"   📡 HDOP: {hdop_value} (Source: {'I/O 182' if 182 in io_elements else 'NOT AVAILABLE'})")
                        print(f"   🌐 GPS Mode: {gps_mode} (Source: {'I/O 181' if 181 in io_elements else 'satellite count' if satellite_count > 0 else 'NOT AVAILABLE'})")
                        print(f"   📶 RSSI: {rssi_value} (Source: {'I/O 21 × 6' if 21 in io_elements else 'NOT AVAILABLE'}) - PHP Logic Applied")
                        print(f"   🏢 LAC: {lac_value} (Source: {'I/O 206' if 206 in io_elements else 'NOT AVAILABLE'}) - CORRECTED MAPPING")
                        print(f"   📱 Cell ID: {cell_id_value} (Source: {'I/O 205' if 205 in io_elements else 'NOT AVAILABLE'}) - CORRECTED MAPPING")
                        print(f"   🌍 MCC: {mcc_value} (Source: {'Tanzania (640)' if mcc_value == '640' else 'I/O 14'}) - PHP Default Applied")
                        print(f"   📋 Available Network I/O Elements: {[io for io in [21, 205, 206, 14, 182, 181] if io in io_elements]}")
                        if not any(io in io_elements for io in [21, 205, 206]):
                            print(f"   ⚠️ WARNING: No GSM network data (I/O 21, 205, 206) available - will send zeros to LATRA")

                        item = {
                            "latitude": str(f"{latitude:.6f}"),
                            "longitude": str(f"{longitude:.6f}"),
                            "altitude": str(int(record.get("altitude", 0))),
                            "timestamp": str(timestamp),
                            "horizontal_speed": str(int(speed_value)),
                            "vertical_speed": str(0),
                            "bearing": str(int(record.get("angle", 0))),
                            "satellite_count": str(int(satellite_count)),
                            "HDOP": str(hdop_value),
                            "d2d3": str(gps_mode),
                            "RSSI": str(rssi_value),
                            "LAC": str(lac_value),
                            "Cell_ID": str(cell_id_value),
                            "MGS_ID": str(dynamic_mgs_id),
                            "MCC": str(mcc_value),
                            "activity_id": str(activity_id)  # Send activity_id as string without modification
                        }
                       
                        # Add addon_info based on activity ID
                        addon_info = self.get_addon_info_for_activity(activity_id, io_elements)
                        if addon_info:
                            item["addon_info"] = addon_info
                            print(f"📋 ADDON_INFO ADDED: {addon_info}")
                       
                        # Add fuel_info for activity 16
                        fuel_info = self.get_fuel_info_for_activity(activity_id, io_elements)
                        if fuel_info:
                            item["fuel_info"] = fuel_info
                            print(f"⛽ FUEL_INFO ADDED: {fuel_info}")
                       
                        # Print complete item data before adding to items list
                        print(f"\n🎯 COMPLETE LATRA ITEM DATA:")
                        print(f"{'='*60}")
                        for key, value in item.items():
                            print(f"   {key}: {value}")
                        print(f"{'='*60}")
                       
                        items.append(item)
                       
                    except Exception as e:
                        print(f"Error preparing record for LATRA: {e}")
                        continue

                # Only send if we have valid items with GPS data
                if not items:
                    print("❌ NO VALID GPS RECORDS TO SEND TO LATRA")
                    print("📍 All records were filtered out during validation")
                    print("🔍 Common reasons:")
                    print("   - Coordinates were exactly (0.0, 0.0) indicating no GPS fix")
                    print("   - Coordinates were outside valid ranges (-90 to 90 lat, -180 to 180 lon)")
                    print("   - Parsing errors occurred during record processing")
                    print("🚫 Check GPS device connection and satellite reception")
                    return False, {"error": "No valid GPS data to send - all records filtered out"}

                payload = {
                    "vehicle_reg_no": getattr(vehicle, 'registration_number', vehicle.imei.imei_number[-6:]),
                    "type": "poi",
                    "imei": vehicle.imei.imei_number,
                    "items": items
                }

                headers = {
                    "Authorization": f"Basic {settings.LATRA_API_TOKEN}",
                    "Content-Type": "application/json"
                }

                # Comprehensive payload logging
                print(f"\n🚀 FINAL LATRA PAYLOAD - SENDING TO API:")
                print(f"{'='*80}")
                print(f"📡 API URL: {settings.LATRA_API_URL}")
                print(f"🚙 Vehicle Registration: {payload['vehicle_reg_no']}")
                print(f"📱 IMEI: {payload['imei']}")
                print(f"📊 Type: {payload['type']}")
                print(f"📦 Total Items: {len(payload['items'])}")
                print(f"{'='*80}")
               
                # Print each item in detail
                for idx, item in enumerate(payload['items'], 1):
                    print(f"\n📍 ITEM {idx} DATA:")
                    print(f"   🌍 Location: ({item['latitude']}, {item['longitude']})")
                    print(f"   🏔️  Altitude: {item['altitude']} m")
                    print(f"   ⏰ Timestamp: {item['timestamp']}")
                    print(f"   🚗 Speed (H/V): {item['horizontal_speed']}/{item['vertical_speed']} km/h")
                    print(f"   🧭 Bearing: {item['bearing']}°")
                    print(f"   🛰️  Satellites: {item['satellite_count']}")
                    print(f"   📡 HDOP: {item['HDOP']}")
                    print(f"   🌐 GPS Mode: {item['d2d3']}D")
                    print(f"   📶 RSSI: {item['RSSI']}")
                    print(f"   🏢 LAC: {item['LAC']}")
                    print(f"   📱 Cell ID: {item['Cell_ID']}")
                    print(f"   🆔 MGS ID: {item['MGS_ID']}")
                    print(f"   🌍 MCC: {item['MCC']}")
                    print(f"   🎯 Activity ID: {item['activity_id']}")
                   
                    if 'addon_info' in item:
                        print(f"   📋 Addon Info:")
                        for key, value in item['addon_info'].items():
                            print(f"      - {key}: {value}")
                   
                    if 'fuel_info' in item:
                        print(f"   ⛽ Fuel Info:")
                        for key, value in item['fuel_info'].items():
                            print(f"      - {key}: {value}")
               
                print(f"\n{'='*80}")
                print(f"🚀 SENDING COMPLETE PAYLOAD TO LATRA...")
                print(f"{'='*80}")

                # Also print the raw JSON payload
                print(f"\n📄 RAW JSON PAYLOAD:")
                print(json.dumps(payload, indent=2, ensure_ascii=False))

                response = requests.post(
                    settings.LATRA_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
               
                # Better error handling
                if response.status_code != 200:
                    error_msg = f"LATRA API returned status {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg += f": {error_data}"
                        print(f"LATRA Error Response: {error_data}")
                    except:
                        error_msg += f": {response.text}"
                        print(f"LATRA Error Text: {response.text}")
                    return False, {"error": error_msg}
               
                response_data = response.json()
                print(f"\n✅ LATRA API SUCCESS RESPONSE:")
                print(f"{'='*50}")
                print(f"📊 Status Code: {response.status_code}")
                print(f"📨 Response Data: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                print(f"⏱️  Response Time: {response.elapsed.total_seconds():.2f} seconds")
                print(f"📦 Items Sent: {len(items)}")
                print(f"{'='*50}")
                return True, response_data
               
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    return False, {"error": str(e)}
                time.sleep(retry_delay * (attempt + 1))
            except Exception as e:
                return False, {"error": str(e)}
       
        return False, {"error": "Max retries exceeded"}

if __name__ == "__main__":
    listener = GPSListener()
   
    # Start GPS listener for real data only
    print("="*60)
    print("GPS LISTENER - WAITING FOR REAL DEVICE CONNECTIONS")
    print("="*60)
    print("🔧 Listening on port 2000 for GPS device connections...")
    print("📡 Only real GPS data from devices will be processed")
    print("🚫 No simulation or test data will be generated")
    print("="*60)
   
    listener.start_listener()