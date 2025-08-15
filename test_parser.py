#!/usr/bin/env python3
"""
Standalone GPS data parser test
"""
import struct
import decimal

def safe_hex_to_int(hex_str, default=0):
    """Safely convert hex string to integer with error handling"""
    try:
        return int(hex_str, 16) if hex_str else default
    except ValueError:
        return default

def coordinate_formater(hex_coordinate):
    """Convert hex coordinate to decimal degrees"""
    try:
        if not hex_coordinate or hex_coordinate == "00000000":
            print(f"DEBUG: Empty or zero coordinate hex: {hex_coordinate}")
            return 0.0
            
        coordinate = safe_hex_to_int(hex_coordinate)
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

def codec_8e_checker(codec8_packet):
    """Check if packet is valid Codec8/8E format"""
    try:
        if len(codec8_packet) < 18:
            return False
        
        codec_type = codec8_packet[16:18]
        return codec_type.upper() in ["8E", "08"]
    except Exception:
        return False

def parse_gps_data(hex_data):
    """Parse the GPS data"""
    print(f"Hex data length: {len(hex_data)} characters")
    print(f"First 20 chars: {hex_data[:20]}")
    
    # Check codec type
    if len(hex_data) < 18:
        print("Data too short")
        return None
        
    codec_type = hex_data[16:18]
    print(f"Codec type: {codec_type}")
    
    is_valid = codec_8e_checker(hex_data)
    print(f"Is valid codec: {is_valid}")
    
    if not is_valid:
        return None
        
    # Get codec type (8 or 8E)
    data_step = 4 if codec_type.upper() == "8E" else 2
    print(f"Data step: {data_step}")
    
    # Number of records
    number_of_records = safe_hex_to_int(hex_data[18:20])
    print(f"Number of records: {number_of_records}")
    
    # Start parsing records
    avl_data_start = hex_data[20:]
    data_field_position = 0
    
    print(f"AVL data start length: {len(avl_data_start)}")
    
    for record_num in range(number_of_records):
        print(f"\n=== PARSING RECORD {record_num + 1} ===")
        
        # Timestamp (8 bytes)
        timestamp = avl_data_start[data_field_position:data_field_position+16]
        print(f"Timestamp hex: {timestamp}")
        data_field_position += 16
        
        # Priority (1 byte)
        priority = avl_data_start[data_field_position:data_field_position+2]
        print(f"Priority hex: {priority}")
        data_field_position += 2
        
        # Longitude (4 bytes)
        longitude_hex = avl_data_start[data_field_position:data_field_position+8]
        longitude = coordinate_formater(longitude_hex)
        print(f"Longitude - Hex: {longitude_hex}, Parsed: {longitude}")
        data_field_position += 8
        
        # Latitude (4 bytes)
        latitude_hex = avl_data_start[data_field_position:data_field_position+8]
        latitude = coordinate_formater(latitude_hex)
        print(f"Latitude - Hex: {latitude_hex}, Parsed: {latitude}")
        data_field_position += 8
        
        # Altitude (2 bytes)
        altitude_hex = avl_data_start[data_field_position:data_field_position+4]
        altitude = safe_hex_to_int(altitude_hex)
        print(f"Altitude - Hex: {altitude_hex}, Parsed: {altitude}")
        data_field_position += 4
        
        # Angle (2 bytes)
        angle_hex = avl_data_start[data_field_position:data_field_position+4]
        angle = safe_hex_to_int(angle_hex)
        print(f"Angle - Hex: {angle_hex}, Parsed: {angle}")
        data_field_position += 4
        
        # Satellites (1 byte)
        satellites_hex = avl_data_start[data_field_position:data_field_position+2]
        satellites = safe_hex_to_int(satellites_hex)
        print(f"Satellites - Hex: {satellites_hex}, Parsed: {satellites}")
        data_field_position += 2
        
        # Speed (2 bytes)
        speed_hex = avl_data_start[data_field_position:data_field_position+4]
        speed = safe_hex_to_int(speed_hex)
        print(f"Speed - Hex: {speed_hex}, Parsed: {speed} km/h")
        data_field_position += 4
        
        # Event IO ID
        event_io_hex = avl_data_start[data_field_position:data_field_position+data_step]
        event_id = safe_hex_to_int(event_io_hex)
        print(f"Event ID - Hex: {event_io_hex}, Parsed: {event_id}")
        data_field_position += data_step
        
        print(f"\nFINAL PARSED VALUES:")
        print(f"  Coordinates: ({latitude}, {longitude})")
        print(f"  Speed: {speed} km/h")
        print(f"  Satellites: {satellites}")
        print(f"  Event ID: {event_id}")
        print(f"  Altitude: {altitude}m")
        print(f"  Bearing: {angle}°")
        
        # Check coordinate validation
        print(f"\nCOORDINATE VALIDATION:")
        print(f"  Both zero check: {latitude == 0.0 and longitude == 0.0}")
        print(f"  Range check lat: {-90.0 <= latitude <= 90.0}")
        print(f"  Range check lon: {-180.0 <= longitude <= 180.0}")
        
        if latitude == 0.0 and longitude == 0.0:
            print("  ❌ Would be SKIPPED - both coordinates are 0.0")
        elif not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            print(f"  ❌ Would be SKIPPED - coordinates out of range")
        else:
            print("  ✅ Would be SENT to LATRA")
        
        return {
            'latitude': latitude,
            'longitude': longitude,
            'speed': speed,
            'satellites': satellites,
            'event_id': event_id,
            'altitude': altitude,
            'angle': angle
        }

if __name__ == "__main__":
    # Test with the provided hex data
    hex_data = "0000000000000076080100000198af1f6ca80016d2955efc8c266001ac00ad100031001a0bef01f0011505c80045010101b30002000300b40071640ab5000bb6000742313d180031cd4e22ce00d8430ff544000009010406010403f10000fa04c700060d7c10016d1477020b00000002140063f40e00000000271581f70100001a6b"
    
    print("Testing GPS data parsing...")
    print("=" * 60)
    
    result = parse_gps_data(hex_data)
    
    if result:
        print("\n" + "=" * 60)
        print("SUCCESS: Data parsed successfully!")
        print(f"Final result: {result}")
    else:
        print("\nFAILED: Could not parse data")
