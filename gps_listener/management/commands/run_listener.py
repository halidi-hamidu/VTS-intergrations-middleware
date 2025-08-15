from django.core.management.base import BaseCommand
from gps_listener.services import GPSListener

class Command(BaseCommand):
    help = 'Starts the GPS listener service'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting GPS listener service...'))
        listener = GPSListener()
        listener.start_listener()
