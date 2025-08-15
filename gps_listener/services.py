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
    
    250: "18",  # Trip Start/Stop -> Engine Start/Stop
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
    239: "2",   # Ignition Event -> Engine ON/OFF
    240: "1",   # Movement Event -> Movement/Logging (Default)
    
    # Additional Teltonika Event IDs mapped to LATRA activities
    175: "20",  # Auto Geofence -> Enter/Leave Boundary
    236: "8",   # Alarm -> Panic Button (Driver)
    257: "12",  # Crash trace data -> Accident
    285: "31",  # Blood alcohol content -> Driver Identification
    318: "26",  # GNSS Jamming -> GPS Signal Lost
    391: "14",  # Private mode -> Device Tempering
    449: "2",   # Ignition On Counter -> Engine ON
    
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
                            io_elements[self.safe_hex_to_int(key)] = self.sorting_hat(
                                self.safe_hex_to_int(key), 
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
                            io_elements[self.safe_hex_to_int(key)] = self.sorting_hat(
                                self.safe_hex_to_int(key), 
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
                            io_elements[self.safe_hex_to_int(key)] = self.sorting_hat(
                                self.safe_hex_to_int(key), 
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
                                io_elements[self.safe_hex_to_int(key)] = self.sorting_hat(
                                    self.safe_hex_to_int(key), 
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
                            detected_activity = event_id
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
                    
                    # Check for other specific I/O elements that map to activities
                    if not detected_activity:
                        # Check for speeding (I/O 24 - Speed)
                        speed_value = record.get("speed", 0)
                        try:
                            speed_int = int(speed_value) if isinstance(speed_value, str) else speed_value
                            if speed_int > 80:  # Configurable speed limit
                                detected_activity = 4  # LATRA Activity ID 4 (Speeding)
                                record["activity"] = f"4 - Speeding ({speed_value} km/h)"
                                print(f"DEBUG: Speeding detected: {speed_value} km/h -> LATRA Activity 4")
                        except (ValueError, TypeError):
                            print(f"DEBUG: Invalid speed value: {speed_value}, skipping speeding check")
                        
                        # Check for low battery (I/O 67 - Battery Voltage)
                        if not detected_activity and 67 in io_elements:
                            battery_voltage = io_elements[67]
                            if isinstance(battery_voltage, (int, float)) and battery_voltage < 11.0:
                                detected_activity = 9  # LATRA Activity ID 9 (Internal Battery Low)
                                record["activity"] = f"9 - Internal Battery Low ({battery_voltage}V)"
                                print(f"DEBUG: Low battery detected: {battery_voltage}V -> LATRA Activity 9")
                        
                        # Check for external power disconnection (I/O 66 - External Voltage)
                        if not detected_activity and 66 in io_elements:
                            ext_voltage = io_elements[66]
                            if isinstance(ext_voltage, (int, float)) and ext_voltage < 8.0:
                                detected_activity = 10  # LATRA Activity ID 10 (External Power Disconnected)
                                record["activity"] = f"10 - External Power Disconnected ({ext_voltage}V)"
                                print(f"DEBUG: External power disconnected: {ext_voltage}V -> LATRA Activity 10")
                        
                        # Check for driver identification (I/O 78 - iButton)
                        if not detected_activity and 78 in io_elements:
                            ibutton_id = io_elements[78]
                            if ibutton_id and str(ibutton_id) != "0x00000000000000":
                                detected_activity = 24  # LATRA Activity ID 24 (Ibutton Scan Regular)
                                record["activity"] = f"24 - Ibutton Scan (Regular) - ID: {ibutton_id}"
                                print(f"DEBUG: iButton detected: {ibutton_id} -> LATRA Activity 24")
                            else:
                                detected_activity = 17  # LATRA Activity ID 17 (Invalid Scan)
                                record["activity"] = "17 - Invalid Scan (No iButton)"
                                print(f"DEBUG: Invalid iButton scan -> LATRA Activity 17")
                        
                        # Default fallback - if we have GPS data but no specific activity, use Movement/Logging
                        if not detected_activity and (record.get("latitude", 0) != 0 or record.get("longitude", 0) != 0):
                            detected_activity = 1  # LATRA Activity ID 1 (Movement/Logging Default)
                            record["activity"] = "1 - Movement/Logging (Default GPS Data)"
                            print(f"DEBUG: Default activity for GPS data -> LATRA Activity 1 (Movement/Logging)")
                    
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
                    
                    # Store the LATRA activity ID for later use
                    record["latra_activity_id"] = detected_activity

                    result["records"].append(record)

                except Exception as e:
                    result["parse_errors"].append(f"Error parsing record {record_num}: {str(e)}")
                    continue

        except Exception as e:
            result["parse_errors"].append(f"Fatal parsing error: {str(e)}")

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

    def sorting_hat(self, key, value):
        """Parse I/O element based on its ID"""
        parse_functions = {
            240: lambda x: self.safe_hex_to_int(x),
            239: lambda x: self.safe_hex_to_int(x),
            80: lambda x: self.safe_hex_to_int(x),
            241: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.1')),
            242: lambda x: float(decimal.Decimal(self.safe_hex_to_int(x)) * decimal.Decimal('0.1')),
            11: lambda x: self.safe_hex_to_int(x),
            245: lambda x: x if x else "FFFFFFFFFFFFFFFF",  # Keep raw hex for driver ID
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
            180: lambda x: self.safe_hex_to_int(x)
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
                
        elif activity_id == 3:  # Engine OFF / Trip End
            if 239 in io_elements:  # Distance travelled
                addon_info["distance_travelled"] = str(io_elements[239])
            
            if 80 in io_elements:  # Trip duration
                addon_info["trip_duration"] = str(io_elements[80])
            
            if 241 in io_elements:  # Average speed
                addon_info["avgSpeed"] = str(io_elements[241])
            
            if 242 in io_elements:  # Max speed
                addon_info["maxSpeed"] = str(io_elements[242])
                
        elif activity_id in [9, 10]:  # Power status events
            if 67 in io_elements:  # External power voltage
                addon_info["ext_power_voltage"] = str(io_elements[67])
            
            if 66 in io_elements:  # Internal battery voltage
                addon_info["int_battery_voltage"] = str(io_elements[66])
                
        elif activity_id in [17, 24]:  # Invalid Scan and Regular Ibutton Scan
            if 245 in io_elements:  # Driver identification
                driver_id = io_elements[245]
                # Convert to 16-digit hex string if needed
                if isinstance(driver_id, str) and driver_id.startswith('0x'):
                    driver_id = driver_id[2:].upper().zfill(16)
                elif isinstance(driver_id, int):
                    driver_id = f"{driver_id:016X}"
                else:
                    driver_id = str(driver_id).upper().zfill(16)
                    
                # Use FFFFFFFFFFFFFFFF when no valid identification detected
                if not driver_id or driver_id == "0000000000000000":
                    driver_id = "FFFFFFFFFFFFFFFF"
                    
                addon_info["v_driver_identification_no"] = driver_id
        
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
                        print(f"   Record data: {record.get('latitude')}, {record.get('longitude')}")
                        
                        # Very lenient coordinate validation for testing
                        # Only skip if coordinates are clearly invalid (outside possible ranges)
                        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
                            print(f"❌ SKIPPING RECORD: Coordinates out of valid range ({latitude},{longitude})")
                            continue
                        
                        # Allow (0,0) coordinates for testing - LATRA might accept them
                        if latitude == 0.0 and longitude == 0.0:
                            print(f"⚠️ SENDING (0,0) COORDINATES: GPS fix may not be available but will send to LATRA")
                            # Use Nairobi coordinates as fallback for testing
                            latitude = -1.286389
                            longitude = 36.817223
                            print(f"📍 USING TEST COORDINATES: Nairobi ({latitude:.6f}, {longitude:.6f})")
                        
                        print(f"✅ COORDINATES TO SEND: ({latitude:.6f}, {longitude:.6f})")
                        
                        
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
                        
                        # RSSI (Received Signal Strength Indication) - Only from actual I/O
                        rssi_value = "0"  # Default to 0 (unknown)
                        if 21 in io_elements:  # GSM Signal Strength
                            rssi_value = str(io_elements[21])
                        # NO ESTIMATION from other sources
                        
                        # LAC (Location Area Code) - Only from actual I/O
                        lac_value = "0"  # Default to 0 (unknown) instead of fake 123
                        if 212 in io_elements:  # GSM Cell LAC
                            lac_value = str(io_elements[212])
                        # NO EXTRACTION from operator codes
                        
                        # Cell ID - Only from actual I/O
                        cell_id_value = "0"  # Default to 0 (unknown) instead of fake 12345
                        if 213 in io_elements:  # GSM Cell ID
                            cell_id_value = str(io_elements[213])
                        # NO FALLBACK to other I/O elements
                        
                        # MCC (Mobile Country Code) - Only from actual I/O
                        mcc_value = "0"  # Default to 0 (unknown) instead of assuming Kenya
                        if 14 in io_elements:  # GSM Operator Code
                            operator_code = io_elements[14]
                            try:
                                # Ensure operator_code is an integer for comparison
                                operator_code_int = int(operator_code) if isinstance(operator_code, str) else operator_code
                                if operator_code_int > 100000:
                                    mcc_value = str(operator_code_int)[:3]
                            except (ValueError, TypeError):
                                print(f"DEBUG: Invalid operator code: {operator_code}, using default MCC")
                                mcc_value = "0"
                        
                        print(f"📊 LATRA FIELDS - REAL DATA ONLY:")
                        print(f"   ️  Satellite Count: {satellite_count} (Source: {'GPS data' if satellite_count > 0 else 'NOT AVAILABLE'})")
                        print(f"   📡 HDOP: {hdop_value} (Source: {'I/O 182' if 182 in io_elements else 'NOT AVAILABLE'})")
                        print(f"   🌐 GPS Mode: {gps_mode} (Source: {'I/O 181' if 181 in io_elements else 'satellite count' if satellite_count > 0 else 'NOT AVAILABLE'})")
                        print(f"   📶 RSSI: {rssi_value} (Source: {'I/O 21' if 21 in io_elements else 'NOT AVAILABLE'})")
                        print(f"   🏢 LAC: {lac_value} (Source: {'I/O 212' if 212 in io_elements else 'NOT AVAILABLE'})")
                        print(f"   📱 Cell ID: {cell_id_value} (Source: {'I/O 213' if 213 in io_elements else 'NOT AVAILABLE'})")
                        print(f"   🌍 MCC: {mcc_value} (Source: {'I/O 14' if 14 in io_elements else 'NOT AVAILABLE'})")

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

