from django.core.management.base import BaseCommand
from vehicles.models import DeviceImei, Vehicle
from data_reported.models import ReportedData
import json
from datetime import datetime, timedelta
import random


class Command(BaseCommand):
    help = 'Create sample data for testing the frontend'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating sample data...'))
        
        # Create sample IMEI devices
        imei_numbers = [
            '123456789012345',
            '234567890123456', 
            '345678901234567',
            '456789012345678',
            '567890123456789',
            '678901234567890',
            '789012345678901',
            '890123456789012'
        ]
        
        devices = []
        for imei in imei_numbers:
            device, created = DeviceImei.objects.get_or_create(
                imei_number=imei
            )
            devices.append(device)
            if created:
                self.stdout.write(f'Created device: {imei}')
        
        # Create sample vehicles (assign only some devices)
        vehicle_data = [
            ('T123ABC', devices[0]),
            ('T456DEF', devices[1]),
            ('T789GHI', devices[2]),
            ('T012JKL', devices[3]),
            ('T345MNO', devices[4]),
        ]
        
        vehicles = []
        for reg_num, device in vehicle_data:
            vehicle, created = Vehicle.objects.get_or_create(
                registration_number=reg_num,
                defaults={'imei': device}
            )
            vehicles.append(vehicle)
            if created:
                self.stdout.write(f'Created vehicle: {reg_num}')
        
        # Create sample reported data
        for i in range(20):
            vehicle = random.choice(vehicles)
            
            # Create sample processed data
            sample_data = {
                "device_imei": vehicle.imei.imei_number,
                "server_time": datetime.now().strftime("%H:%M:%S %d-%m-%Y"),
                "records": [
                    {
                        "record_number": 1,
                        "imei": vehicle.imei.imei_number,
                        "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 1440))).strftime("%H:%M:%S %d-%m-%Y (local) / %H:%M:%S %d-%m-%Y (utc)"),
                        "latitude": -6.7924 + random.uniform(-0.01, 0.01),  # Dar es Salaam area
                        "longitude": 39.2083 + random.uniform(-0.01, 0.01),
                        "altitude": random.randint(0, 100),
                        "angle": random.randint(0, 359),
                        "satellites": random.randint(4, 12),
                        "speed": random.randint(0, 120),
                        "io_elements": {
                            240: random.randint(1, 24),  # Activity code
                            239: random.randint(1, 500),  # Distance
                            241: random.uniform(20, 80),   # Average speed
                            242: random.uniform(40, 120),  # Max speed
                        }
                    }
                ],
                "parse_errors": []
            }
            
            # Sample LATRA response
            latra_response = {
                "status": "success" if random.choice([True, False, True]) else "error",
                "message": "Data received successfully" if random.choice([True, False, True]) else "Error processing data",
                "timestamp": datetime.now().isoformat()
            }
            
            success = latra_response["status"] == "success"
            
            ReportedData.objects.create(
                vehicle=vehicle,
                raw_data={"hex": f"sample_hex_data_{i}"},
                processed_data=sample_data,
                latra_response=latra_response,
                is_success=success
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created:\n'
                f'- {len(devices)} IMEI devices\n'
                f'- {len(vehicles)} vehicles\n'
                f'- {len(devices) - len(vehicles)} unassigned devices\n'
                f'- 20 reported data entries'
            )
        )
