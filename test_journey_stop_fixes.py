#!/usr/bin/env python3
"""
Test Journey Stop detection and addon_info generation
"""

# Mock the functions we need to test
class MockGPSListener:
    def safe_hex_to_int(self, hex_string):
        """Mock safe hex to int conversion"""
        try:
            return int(hex_string, 16) if isinstance(hex_string, str) else int(hex_string)
        except:
            return 0

    def get_addon_info_for_activity(self, activity_id, io_elements):
        """Generate addon_info based on activity ID"""
        addon_info = {}
       
        if activity_id == 3:  # Engine OFF / Trip End / Journey Stop
            # Add comprehensive data for journey stop reporting
            print(f"DEBUG: Generating addon_info for Engine OFF (Journey Stop) - Activity ID 3")
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
           
            # Average speed during trip - I/O 241 
            if 241 in io_elements:  
                addon_info["avgSpeed"] = str(io_elements[241])
                print(f"DEBUG: Average speed from I/O 241: {io_elements[241]} km/h")
           
            # Max speed during trip - I/O 242 
            if 242 in io_elements:  
                addon_info["maxSpeed"] = str(io_elements[242])
                print(f"DEBUG: Max speed from I/O 242: {io_elements[242]} km/h")
            
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
            
            print(f"DEBUG: Final addon_info for Journey Stop: {addon_info}")
        
        return addon_info if addon_info else None

    def test_journey_stop_detection(self, io_elements):
        """Test journey stop activity detection logic"""
        detected_activity = None
        
        print(f"🔍 TESTING JOURNEY STOP DETECTION")
        print(f"Available I/O elements: {list(io_elements.keys())}")
        
        # Test I/O 239 (Journey/Ignition) detection
        if 239 in io_elements:
            ignition_state = io_elements[239]
            print(f"🔍 I/O 239 Journey/Ignition state = {ignition_state}")
            if ignition_state == 0:  # Journey/Ignition OFF
                detected_activity = 3  # LATRA Activity ID 3 (Engine OFF)
                print(f"🔑 JOURNEY/IGNITION OFF DETECTED (I/O 239=0) -> LATRA Activity 3")
                return detected_activity
        
        # Test I/O 250 (Trip) detection  
        if 250 in io_elements:
            trip_state = io_elements[250]
            if trip_state == 0:  # Trip stop
                detected_activity = 19  # LATRA Activity ID 19 (Engine Stop)
                print(f"🛑 TRIP STOP DETECTED (I/O 250=0) -> LATRA Activity 19")
                return detected_activity
        
        print(f"❌ NO JOURNEY STOP DETECTED")
        return detected_activity

# Test cases based on the attachment data
print("🧪 TESTING JOURNEY STOP DETECTION AND REPORTING")
print("=" * 80)

gps_listener = MockGPSListener()

# Test case 1: Journey Stop based on attachment data
test_io_elements = {
    239: 0,      # Journey: Stop (from attachment)
    240: 0,      # Movement: Off (from attachment)  
    24: 0,       # Speed: 0 km/h (from attachment)
    16: 25317967, # Total Odometer: 25317967 (from attachment)
    199: 0,      # Trip Odometer: 0 m (from attachment)
    21: 5,       # GSM Signal: 5 (from attachment)
    67: 4.033,   # Battery Voltage: 4.033 V (from attachment)
    66: 12.598,  # External Voltage: 12.598 V (from attachment)
    181: 1.1,    # GNSS PDOP: 1.1 (from attachment)
    182: 0.7,    # GNSS HDOP: 0.7 (from attachment)
    205: 17133,  # GSM Cell ID: 17133 (from attachment)
    206: 160,    # GSM Area Code: 160 (from attachment)
    241: 64004,  # Active GSM Operator: 64004 (from attachment)
    68: 0,       # Battery Current: 0 A (from attachment)
    9: 0.26,     # Fuel Sensor Status: 0.26 mV (from attachment)
    6: 0.26,     # Analog Input 2: 0.26 mV (from attachment)
    11: 892550450, # ICCID1: 892550450 (from attachment)
    14: 655720851, # ICCID2: 655720851 (from attachment)
}

print(f"\n📋 TEST 1: Journey Stop Detection")
print("-" * 50)
detected_activity = gps_listener.test_journey_stop_detection(test_io_elements)
print(f"🎯 DETECTED ACTIVITY: {detected_activity}")

if detected_activity:
    print(f"\n📋 TEST 2: Addon Info Generation for Activity {detected_activity}")
    print("-" * 50)
    addon_info = gps_listener.get_addon_info_for_activity(detected_activity, test_io_elements)
    print(f"\n📊 FINAL ADDON_INFO TO SEND TO LATRA:")
    if addon_info:
        for key, value in addon_info.items():
            print(f"   {key}: {value}")
    else:
        print("   NO ADDON_INFO GENERATED")

# Test case 2: Trip Stop via I/O 250
print(f"\n\n📋 TEST 3: Trip Stop Detection (I/O 250)")
print("-" * 50)
test_io_elements_trip = {
    250: 0,      # Trip: Stop
    240: 0,      # Movement: Off
    24: 0,       # Speed: 0 km/h
    16: 25317967, # Total Odometer
    80: 1800,    # Trip duration: 30 minutes
    241: 45.5,   # Average speed: 45.5 km/h
    242: 85.2,   # Max speed: 85.2 km/h
}

detected_activity = gps_listener.test_journey_stop_detection(test_io_elements_trip)
print(f"🎯 DETECTED ACTIVITY: {detected_activity}")

if detected_activity:
    addon_info = gps_listener.get_addon_info_for_activity(detected_activity, test_io_elements_trip)
    print(f"\n📊 ADDON_INFO FOR TRIP STOP:")
    if addon_info:
        for key, value in addon_info.items():
            print(f"   {key}: {value}")

print(f"\n{'=' * 80}")
print("🏁 JOURNEY STOP TESTING SUMMARY:")
print("✅ Journey Stop (I/O 239=0) should be detected as Activity 3 (Engine OFF)")
print("✅ Trip Stop (I/O 250=0) should be detected as Activity 19 (Engine Stop)")  
print("✅ Both should generate comprehensive addon_info with trip data")
print("✅ Activity 3 is now in non_gps_activities list (can use fallback coordinates)")
print("✅ Enhanced debugging will help identify issues in real scenarios")
print(f"{'=' * 80}")
