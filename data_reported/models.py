from django.db import models
from vehicles.models import Vehicle

class ReportedData(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='reported_data')
    raw_data = models.JSONField()
    processed_data = models.JSONField()
    latra_response = models.JSONField()
    is_success = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vehicle.registration_number} - {self.created_at}"
