#!/usr/bin/env python3
import binascii
import struct
import datetime
import sys
import json

def decode_teltonika_packet(hex_string):
    """
    Decode a Teltonika protocol hex string into structured data
    """
    # Remove any spaces or non-hex characters
    hex_string = ''.join(c for c in hex_string if c.lower() in '0123456789abcdef')
    
    # Convert hex string to bytes
    try:
        data = binascii.unhexlify(hex_string)
    except binascii.Error as e:
        return {"error": f"Invalid hex string: {e}"}
    
    result = {
        "raw_hex": hex_string
    }
    
    # Try to parse based on Teltonika protocol structure
    try:
        # First 4 bytes are usually preamble (zeros)
        # Next 4 bytes may be data field length or IMEI
        result["header"] = data[0:8].hex()
        
        # Check codec ID - determines the structure
        if len(data) <= 8:
            return {"error": "Data too short", "raw_hex": hex_string}
        
        codec_id = data[8]
        result["codec_id"] = codec_id
        
        # Check if it's Teltonika codec 8 (binary data) format
        if codec_id == 8:
            # CODEC 8 structure
            pos = 9
            
            # Number of data records
            if len(data) <= pos:
                return {"error": "Data too short for records count", "raw_hex": hex_string}
            
            num_records = data[pos]
            pos += 1
            result["number_of_records"] = num_records
            
            # Process each record
            records = []
            
            for record_idx in range(num_records):
                record = {}
                
                # Parse timestamp (Unix timestamp)
                if len(data) <= pos + 8:
                    result["error"] = "Data too short for timestamp"
                    break
                
                try:
                    timestamp = int.from_bytes(data[pos:pos+8], byteorder='big')
                    record["timestamp"] = timestamp
                    record["datetime"] = datetime.datetime.fromtimestamp(timestamp).isoformat()
                except (ValueError, OSError, OverflowError) as e:
                    # Handle invalid timestamps
                    timestamp_bytes = data[pos:pos+8].hex()
                    record["timestamp_hex"] = timestamp_bytes
                    record["timestamp_error"] = str(e)
                pos += 8
                
                # Priority
                if len(data) <= pos:
                    result["error"] = "Data too short for priority"
                    break
                    
                priority = data[pos]
                pos += 1
                record["priority"] = priority
                
                # Longitude, Latitude, Altitude, Angle, Satellites, Speed
                if len(data) <= pos + 15:
                    result["error"] = "Data too short for GPS data"
                    break
                
                try:
                    longitude = struct.unpack('>i', data[pos:pos+4])[0] / 10000000.0
                    pos += 4
                    latitude = struct.unpack('>i', data[pos:pos+4])[0] / 10000000.0
                    pos += 4
                    altitude = struct.unpack('>h', data[pos:pos+2])[0]
                    pos += 2
                    angle = struct.unpack('>h', data[pos:pos+2])[0]
                    pos += 2
                    satellites = data[pos]
                    pos += 1
                    speed = struct.unpack('>h', data[pos:pos+2])[0]
                    pos += 2
                    
                    record["longitude"] = longitude
                    record["latitude"] = latitude
                    record["altitude"] = altitude
                    record["angle"] = angle
                    record["satellites"] = satellites
                    record["speed"] = speed
                except Exception as e:
                    record["gps_error"] = str(e)
                
                # IO Elements section
                if len(data) <= pos:
                    result["error"] = "Data too short for IO elements count"
                    break
                    
                io_elements_count = data[pos]
                pos += 1
                record["io_elements_count"] = io_elements_count
                
                # Parse IO elements
                io_elements = {}
                
                # Try to parse each IO element section (1-byte, 2-byte, 4-byte, 8-byte)
                try:
                    # 1-byte IO elements
                    if len(data) <= pos:
                        break
                    n1 = data[pos]
                    pos += 1
                    for i in range(n1):
                        if len(data) <= pos + 1:
                            break
                        io_id = data[pos]
                        pos += 1
                        io_value = data[pos]
                        pos += 1
                        io_elements[str(io_id)] = io_value
                    
                    # 2-byte IO elements
                    if len(data) <= pos:
                        break
                    n2 = data[pos]
                    pos += 1
                    for i in range(n2):
                        if len(data) <= pos + 2:
                            break
                        io_id = data[pos]
                        pos += 1
                        io_value = int.from_bytes(data[pos:pos+2], byteorder='big')
                        pos += 2
                        io_elements[str(io_id)] = io_value
                    
                    # 4-byte IO elements
                    if len(data) <= pos:
                        break
                    n4 = data[pos]
                    pos += 1
                    for i in range(n4):
                        if len(data) <= pos + 4:
                            break
                        io_id = data[pos]
                        pos += 1
                        io_value = int.from_bytes(data[pos:pos+4], byteorder='big')
                        pos += 4
                        io_elements[str(io_id)] = io_value
                    
                    # 8-byte IO elements
                    if len(data) <= pos:
                        break
                    n8 = data[pos]
                    pos += 1
                    for i in range(n8):
                        if len(data) <= pos + 8:
                            break
                        io_id = data[pos]
                        pos += 1
                        io_value = int.from_bytes(data[pos:pos+8], byteorder='big')
                        pos += 8
                        io_elements[str(io_id)] = io_value
                    
                except Exception as e:
                    record["io_elements_error"] = str(e)
                
                record["io_elements"] = io_elements
                records.append(record)
            
            result["records"] = records
            
            # Activity analysis based on IO elements from first record
            if records and "io_elements" in records[0]:
                result["activity_analysis"] = analyze_activity(records[0]["io_elements"])
        else:
            result["note"] = f"Codec {codec_id} parsing not fully implemented"
            
    except Exception as e:
        result["parsing_error"] = str(e)
        result["raw_hex"] = hex_string
    
    return result

def analyze_activity(io_elements):
    """
    Analyze IO elements to determine device activity
    """
    activity = {}
    
    # Common IO element IDs and their meanings - specific to Teltonika devices
    io_meanings = {
        # Digital Inputs
        "1": "Digital Input 1",
        "2": "Digital Input 2",
        "3": "Digital Input 3",
        "4": "Digital Input 4",
        
        # Analog Inputs
        "9": "Analog Input 1",
        "10": "Analog Input 2",
        "11": "ICCID",
        
        # Fuel Data
        "12": "Fuel Used GPS",
        "13": "Fuel Rate GPS",
        "16": "Total Odometer",
        
        # Accelerometer
        "17": "Accelerometer X",
        "18": "Accelerometer Y",
        "19": "Accelerometer Z",
        
        # Device Status
        "20": "BLE Battery 1",
        "21": "GSM Signal",
        "24": "Speed",
        "25": "BLE Temperature 1",
        "66": "External Voltage",
        "67": "Battery Voltage",
        "68": "Battery Current",
        "69": "GNSS Status",
        "80": "Data Mode",
        
        # Commands and Outputs
        "181": "GPRS Command",
        "182": "Digital Output 1",
        "183": "Digital Output 2",
        
        # Vehicle Data
        "239": "Trip Odometer",
        "240": "LATRA Activity",  # Specific to LATRA/Tanzanian implementation
        "241": "Speed from CAN",
        "242": "Fuel Level (percentage)",
        "243": "Engine RPM",
        "246": "Engine Temperature",
        
        # LATRA Specific (Tanzanian implementation)
        "179": "Movement Event",
        "180": "Engine On/Off Event",
        "181": "Speeding Event",
        "240": "Activity Code"
    }
    
    # LATRA Activity codes
    latra_activities = {
        "1": "Movement/Logging",
        "2": "Engine ON",
        "3": "Engine OFF",
        "4": "Speeding",
        "5": "Hash Braking",
        "6": "Hash Turning",
        "7": "Hash Acceleration",
        "8": "Panic Button (Driver)",
        "9": "Internal Battery Low",
        "10": "External Power Disconnected",
        "11": "Excessive Idle",
        "12": "Accident",
        "13": "Panic Button (Passenger)",
        "14": "Device Tempering",
        "15": "Black Box Data Logging",
        "16": "Fuel data report"
    }
    
    # Check for specific activities based on IO elements
    for io_id, value in io_elements.items():
        if io_id in io_meanings:
            activity[io_meanings[io_id]] = value
        else:
            activity[f"IO {io_id}"] = value
    
    # Check for LATRA activity code
    if "240" in io_elements:
        activity_code = str(io_elements["240"])
        if activity_code in latra_activities:
            activity["Activity Type"] = latra_activities[activity_code]
        else:
            activity["Activity Type"] = f"Unknown Activity ({activity_code})"
    
    # Determine vehicle status based on speed
    if "24" in io_elements and io_elements["24"] > 0:
        activity["Vehicle Status"] = "Moving"
    else:
        activity["Vehicle Status"] = "Stationary"
    
    # Check engine status
    if "2" in io_elements:  # Digital Input often used for ignition
        if io_elements["2"] == 1:
            activity["Engine Status"] = "Running"
        else:
            activity["Engine Status"] = "Off"
    
    return activity

def print_readable_report(decoded_data):
    """
    Print a human-readable report of the decoded data
    """
    print("\n===== TELTONIKA GPS PACKET ANALYSIS =====\n")
    
    if "error" in decoded_data:
        print(f"ERROR: {decoded_data['error']}")
        return
    
    print(f"DEVICE DATA:")
    print(f"  Codec: {decoded_data.get('codec_id')}")
    print(f"  Records: {decoded_data.get('number_of_records')}")
    
    if "records" in decoded_data and decoded_data["records"]:
        record = decoded_data["records"][0]  # Take first record
        
        print(f"\nTIMESTAMP:")
        print(f"  Time: {record.get('datetime', 'N/A')}")
        print(f"  Unix: {record.get('timestamp', 'N/A')}")
        
        print(f"\nLOCATION DATA:")
        print(f"  Latitude:   {record.get('latitude', 'N/A')} °")
        print(f"  Longitude:  {record.get('longitude', 'N/A')} °")
        print(f"  Altitude:   {record.get('altitude', 'N/A')} m")
        print(f"  Speed:      {record.get('speed', 'N/A')} km/h")
        print(f"  Direction:  {record.get('angle', 'N/A')} °")
        print(f"  Satellites: {record.get('satellites', 'N/A')}")
        
        print(f"\nIO ELEMENTS:")
        print(f"  Total Elements: {record.get('io_elements_count', 'N/A')}")
        
        for io_id, value in record.get("io_elements", {}).items():
            print(f"  IO {io_id}: {value}")
    
    if "activity_analysis" in decoded_data:
        activity = decoded_data["activity_analysis"]
        print(f"\nACTIVITY ANALYSIS:")
        
        # Print important activity data first
        important_keys = ["Activity Type", "Vehicle Status", "Engine Status"]
        for key in important_keys:
            if key in activity:
                print(f"  {key}: {activity[key]}")
        
        # Print remaining activity data
        for key, value in activity.items():
            if key not in important_keys:
                print(f"  {key}: {value}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Read from command line argument
        hex_string = sys.argv[1]
    else:
        # Example hex string
        hex_string = "0000000000000076080100000198b8bc06b80015ddb6b6fdfdb7090588012d140000001a0bef01f0001505c80045010101b30002000300b40071640ab5000bb60006426eb5180000cd8235ce00854310084400000900ae0600ae03f10000fa04c7009a35db1001e2b9db020b00000002140063f40e000000002715829c010000d188"
    
    # You can also pass the hex string directly
    # hex_string = "{'hex': '0000000000000076080100000198b8bc06b80015ddb6b6fdfdb7090588012d140000001a0bef01f0001505c80045010101b30002000300b40071640ab5000bb60006426eb5180000cd8235ce00854310084400000900ae0600ae03f10000fa04c7009a35db1001e2b9db020b00000002140063f40e000000002715829c010000d188'}"
    
    # Remove any extra characters like quotes, curly braces, or 'hex:' text
    hex_string = hex_string.replace("'", "").replace('"', "").replace("{", "").replace("}", "")
    if "hex:" in hex_string or "hex=" in hex_string:
        hex_string = hex_string.split(":", 1)[1] if ":" in hex_string else hex_string.split("=", 1)[1]
    hex_string = hex_string.strip()
    
    decoded = decode_teltonika_packet(hex_string)
    print_readable_report(decoded)
    print("\nFull decoded data structure:")
    print(json.dumps(decoded, indent=2))
