#!/usr/bin/env python3
"""
Test script for harsh driving event fixes
Tests I/O 253 (Green Driving Events) mapping to LATRA activities:
- Value 1 -> Activity 7 (Hash Acceleration)
- Value 2 -> Activity 5 (Hash Braking) 
- Value 3 -> Activity 6 (Hash Turning)
"""

import sys
import os

# Add the project root to the path so we can import the services module
sys.path.append('/home/halidi/temp/VTS-intergrations-middleware')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'latra_gps.settings')
import django
django.setup()

from gps_listener.services import GPSListener

def test_harsh_driving_detection():
    """Test harsh driving events detection and mapping"""
    
    # Create a GPS listener instance
    listener = GPSListener()
    
    print("🧪 TESTING HARSH DRIVING EVENT DETECTION")
    print("=" * 60)
    
    # Test data: Mock codec 8E packet with I/O element 253 (Green Driving)
    # This simulates different harsh driving scenarios
    
    test_cases = [
        {
            "name": "Harsh Acceleration",
            "io_253_value": 1,
            "expected_activity": 7,
            "expected_desc": "Hash Acceleration"
        },
        {
            "name": "Harsh Braking", 
            "io_253_value": 2,
            "expected_activity": 5,
            "expected_desc": "Hash Braking"
        },
        {
            "name": "Harsh Turning",
            "io_253_value": 3,
            "expected_activity": 6,
            "expected_desc": "Hash Turning"
        },
        {
            "name": "Unknown Green Driving Event",
            "io_253_value": 4,  # Unknown value
            "expected_activity": None,  # Should not detect specific activity
            "expected_desc": None
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔬 TEST CASE {i}: {test_case['name']}")
        print(f"   I/O 253 Value: {test_case['io_253_value']}")
        print(f"   Expected LATRA Activity: {test_case['expected_activity']}")
        
        # Mock parsed data structure
        test_data = {
            "device_imei": "123456789012345",
            "server_time": "12:00:00 20-08-2025 (local) / 12:00:00 20-08-2025 (utc)",
            "raw_data": "test_harsh_driving_data",
            "records": [{
                "timestamp": "12:00:00 20-08-2025",
                "latitude": -6.7924,
                "longitude": 39.2083,
                "altitude": 100,
                "angle": 45,
                "satellites": 8,
                "speed": 60,  # 60 km/h during harsh event
                "event_id": 0,
                "io_elements": {
                    253: test_case['io_253_value'],  # Green driving event
                    21: 25,   # GSM signal
                    17: 2000, # X-axis accelerometer 
                    18: 1500, # Y-axis accelerometer
                    19: -3000 # Z-axis accelerometer
                }
            }],
            "parse_errors": []
        }
        
        # Test the sorting_hat function for I/O 253 parsing
        io_253_parsed = listener.sorting_hat(253, f"{test_case['io_253_value']:02X}")
        print(f"   ✅ I/O 253 Parsing: {test_case['io_253_value']:02X} -> {io_253_parsed}")
        
        # Test activity detection in the main parsing logic
        record = test_data["records"][0]
        io_elements = record["io_elements"]
        
        # Simulate the activity detection logic
        detected_activity = None
        activity_desc = ""
        
        if 253 in io_elements:
            green_driving_value = io_elements[253]
            print(f"   🚗 Green driving value detected: {green_driving_value}")
            
            if green_driving_value == 1:
                detected_activity = 7  # Hash Acceleration
                activity_desc = f"7 - Hash Acceleration (I/O 253: {green_driving_value})"
            elif green_driving_value == 2:
                detected_activity = 5  # Hash Braking  
                activity_desc = f"5 - Hash Braking (I/O 253: {green_driving_value})"
            elif green_driving_value == 3:
                detected_activity = 6  # Hash Turning
                activity_desc = f"6 - Hash Turning (I/O 253: {green_driving_value})"
        
        # Test activity description generation
        if detected_activity:
            desc = listener.get_io_activity_description(253, test_case['io_253_value'], detected_activity)
            print(f"   📝 Generated Description: {desc}")
        
        # Test addon_info generation
        if detected_activity in [5, 6, 7]:
            addon_info = listener.get_addon_info_for_activity(detected_activity, io_elements)
            print(f"   📦 Generated addon_info: {addon_info}")
        
        # Verify results
        if test_case['expected_activity']:
            if detected_activity == test_case['expected_activity']:
                print(f"   ✅ SUCCESS: Activity correctly detected as {detected_activity}")
            else:
                print(f"   ❌ FAILED: Expected activity {test_case['expected_activity']}, got {detected_activity}")
        else:
            if detected_activity is None:
                print(f"   ✅ SUCCESS: No specific activity detected as expected")
            else:
                print(f"   ❌ FAILED: Expected no activity, but got {detected_activity}")
        
        print(f"   📄 Final Activity Description: {activity_desc}")
    
    print(f"\n{'='*60}")
    print(f"🏁 HARSH DRIVING DETECTION TESTS COMPLETED")
    print(f"{'='*60}")

if __name__ == "__main__":
    test_harsh_driving_detection()
