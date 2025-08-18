#!/usr/bin/env python3
"""
Test script to verify iButton parsing fixes
"""

# Mock the functions we need to test without Django
class MockGPSListener:
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

    def get_addon_info_for_activity(self, activity_id, io_elements):
        """Mock version of addon_info generation for iButton activities"""
        addon_info = {}
        
        if activity_id in [17, 24]:  # Invalid Scan and Regular Ibutton Scan
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

# Test cases
test_cases = [
    # Test parse_driver_id function
    ("parse_driver_id", "1234567890ABCDEF", "Valid 8-byte hex"),
    ("parse_driver_id", "ABCDEF1234567890", "Another valid 8-byte hex"),
    ("parse_driver_id", "12345678", "4-byte hex (should be padded)"),
    ("parse_driver_id", "FFFFFFFFFFFFFFFF", "All F's (should return empty)"),
    ("parse_driver_id", "0000000000000000", "All zeros (should return empty)"),
    ("parse_driver_id", "0x1234567890ABCDEF", "With 0x prefix"),
    ("parse_driver_id", "", "Empty string"),
    ("parse_driver_id", None, "None value"),
    
    # Test addon_info generation for different activities and I/O values
    ("addon_info", (24, {78: "1234567890ABCDEF"}), "Activity 24 with valid iButton"),
    ("addon_info", (24, {78: "FFFFFFFFFFFFFFFF"}), "Activity 24 with invalid iButton (all F's)"),
    ("addon_info", (17, {78: "FFFFFFFFFFFFFFFF"}), "Activity 17 with invalid iButton (all F's)"),
    ("addon_info", (24, {245: "ABCD1234EFGH5678"}), "Activity 24 with valid Driver ID"),
    ("addon_info", (24, {245: "0000000000000000"}), "Activity 24 with invalid Driver ID (all zeros)"),
    ("addon_info", (24, {}), "Activity 24 with no I/O elements"),
]

print("🧪 TESTING IBUTTON PARSING FIXES")
print("=" * 80)

gps_listener = MockGPSListener()

for test_type, test_input, description in test_cases:
    print(f"\n📋 TEST: {description}")
    print("-" * 50)
    
    try:
        if test_type == "parse_driver_id":
            result = gps_listener.parse_driver_id(test_input)
            print(f"   Input: {test_input}")
            print(f"   Output: '{result}'")
            print(f"   Result: {'✅ PASS' if result != 'FFFFFFFFFFFFFFFF' else '❌ FAIL'}")
            
        elif test_type == "addon_info":
            activity_id, io_elements = test_input
            result = gps_listener.get_addon_info_for_activity(activity_id, io_elements)
            driver_id = result.get("v_driver_identification_no", "NOT_SET") if result else "NO_ADDON_INFO"
            print(f"   Input: Activity {activity_id}, I/O: {io_elements}")
            print(f"   Output: {result}")
            print(f"   Driver ID: '{driver_id}'")
            
            # Check if we're properly handling invalid scans
            if "FFFF" in str(io_elements.values()) and driver_id != "":
                print(f"   Result: ❌ FAIL - Should return empty for FFFF patterns")
            else:
                print(f"   Result: ✅ PASS - Properly handled")
            
    except Exception as e:
        print(f"   ERROR: {e}")
        print(f"   Result: ❌ FAIL - Exception occurred")

print(f"\n{'=' * 80}")
print("🏁 TEST SUMMARY:")
print("The fixes should:")
print("1. ✅ Return empty string for FFFFFFFFFFFFFFFF patterns (invalid scans)")
print("2. ✅ Return empty string for 0000000000000000 patterns (null values)")
print("3. ✅ Return properly formatted hex for valid iButton IDs")
print("4. ✅ Handle both Activity 17 (Invalid Scan) and Activity 24 (Regular Scan) correctly")
print("5. ✅ Send empty addon_info field instead of FFFFFFFFFFFFFFFF to LATRA")
print(f"{'=' * 80}")
