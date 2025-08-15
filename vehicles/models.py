from django.db import models


class DeviceImei(models.Model):
    imei_number = models.CharField(max_length=15, unique=True)  # IMEI is always 15 digits
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.imei_number

class Vehicle(models.Model):
    registration_number = models.CharField(max_length=20, unique=True)
    imei = models.OneToOneField(DeviceImei, on_delete=models.CASCADE, related_name='vehicle')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.registration_number} (IMEI: {self.imei.imei_number})"
