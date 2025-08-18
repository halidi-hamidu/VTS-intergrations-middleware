#!/usr/bin/env python3
"""
Test script to debug iButton parsing issues
"""

import sys
import os
import django

# Add the project directory to Python path
sys.path.append('/home/halidy/Desktop/for ochu to add ui to the middleware/VTS-intergrations-middleware')

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'latra_gps.settings')

# Setup Django
django.setup()

from gps_listener.services import GPSListener

# Create an instance of GPSListener
gps_listener = GPSListener()

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
]

print("🔧 TESTING IBUTTON PARSING")
print("=" * 50)

for i, test_value in enumerate(test_values, 1):
    print(f"\nTest {i}: Input = '{test_value}'")
    try:
        result = gps_listener.parse_driver_id(test_value)
        print(f"         Output = '{result}'")
    except Exception as e:
        print(f"         ERROR = {e}")

print("\n" + "=" * 50)
print("🔧 TESTING SORTING_HAT FOR I/O 245")
print("=" * 50)

for i, test_value in enumerate(test_values, 1):
    print(f"\nTest {i}: Input = '{test_value}'")
    try:
        result = gps_listener.sorting_hat(245, test_value)
        print(f"         Output = '{result}'")
    except Exception as e:
        print(f"         ERROR = {e}")

print("\nTest completed!")
