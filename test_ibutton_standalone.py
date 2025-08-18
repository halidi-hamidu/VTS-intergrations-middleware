#!/usr/bin/env python3
"""
Standalone test script to debug iButton parsing without Django dependencies
"""

import decimal
import struct

class TestGPSListener:
    def safe_hex_to_int(self, hex_str):
        """Safely convert hex string to int"""
        try:
            return int(hex_str, 16) if hex_str else 0
        except (ValueError, TypeError):
            return 0

    def parse_driver_id(self, hex_value):
        """Properly parse driver ID/iButton hex values"""
        try:
            if not hex_value:
                print(f"DEBUG: Empty iButton hex value, returning FFFFFFFFFFFFFFFF")
                return "FFFFFFFFFFFFFFFF"
            
            # Convert to string and handle different input types
            if isinstance(hex_value, (int, float)):
                # If it's a number, convert to hex string
                clean_hex = f"{int(hex_value):X}".upper()
                print(f"DEBUG: Converted number {hex_value} to hex: {clean_hex}")
            else:
                # Remove 0x prefix if present and convert to uppercase
                clean_hex = str(hex_value).replace("0x", "").replace("0X", "").upper().strip()
            
            # Debug logging
            print(f"DEBUG: Parsing iButton - Raw: '{hex_value}' -> Clean: '{clean_hex}'")
            
            # Check if it's empty after cleaning
            if not clean_hex:
                print(f"DEBUG: Empty after cleaning, returning FFFFFFFFFFFFFFFF")
                return "FFFFFFFFFFFFFFFF"
            
            # Validate hex characters
            if not all(c in '0123456789ABCDEF' for c in clean_hex):
                print(f"DEBUG: Invalid hex characters in iButton value: '{clean_hex}', returning FFFFFFFFFFFFFFFF")
                return "FFFFFFFFFFFFFFFF"
            
            # Pad to 16 characters (8 bytes) if needed
            if len(clean_hex) < 16:
                clean_hex = clean_hex.zfill(16)
                print(f"DEBUG: Padded iButton value to 16 chars: '{clean_hex}'")
            elif len(clean_hex) > 16:
                # Take the last 16 characters if too long
                clean_hex = clean_hex[-16:]
                print(f"DEBUG: Truncated iButton value to 16 chars: '{clean_hex}'")
            
            # Check for obvious invalid values (all zeros)
            if clean_hex == "0000000000000000":
                print(f"DEBUG: All zeros detected, returning FFFFFFFFFFFFFFFF")
                return "FFFFFFFFFFFFFFFF"
            
            # Return the cleaned hex value - DON'T reject all F's as they might be valid
            print(f"DEBUG: Valid iButton ID found: '{clean_hex}'")
            return clean_hex
            
        except Exception as e:
            print(f"DEBUG: Error parsing iButton hex '{hex_value}': {e}, returning FFFFFFFFFFFFFFFF")
            return "FFFFFFFFFFFFFFFF"

    def sorting_hat(self, key, value):
        """Parse I/O element based on its ID - simplified version"""
        if key == 245:  # Driver ID
            return self.parse_driver_id(value)
        elif key == 78:  # iButton ID
            return self.parse_driver_id(value)
        else:
            return value

# Test various hex values that might come from iButton scans
test_values = [
    "1234567890ABCDEF",  # Valid 8-byte hex
    "ABCDEF1234567890",  # Another valid 8-byte hex
    "12345678",          # 4-byte hex (should be padded)
    "1234",              # 2-byte hex (should be padded)
    "12",                # 1-byte hex (should be padded)
    "00000000",          # All zeros (should be treated as invalid)
    "FFFFFFFFFFFFFFFF",  # All F's (should be kept as is)
    "",                  # Empty (should default to FFFFFFFFFFFFFFFF)
    "0x1234567890ABCDEF", # With 0x prefix
    "abcdef1234567890",  # Lowercase (should be converted to uppercase)
    305419896,           # Integer input
    0,                   # Zero integer
]

# Create test instance
gps_listener = TestGPSListener()

print("🔧 TESTING IBUTTON PARSING")
print("=" * 70)

for i, test_value in enumerate(test_values, 1):
    print(f"\nTest {i}: Input = '{test_value}' (type: {type(test_value).__name__})")
    try:
        result = gps_listener.parse_driver_id(test_value)
        print(f"         Output = '{result}'")
        print(f"         Status = {'✅ SUCCESS' if result != 'FFFFFFFFFFFFFFFF' else '❌ DEFAULTED'}")
    except Exception as e:
        print(f"         ERROR = {e}")

print("\n" + "=" * 70)
print("Test completed!")
