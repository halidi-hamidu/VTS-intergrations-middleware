from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Initialize the application'

    def handle(self, *args, **options):
        # Run migrations
        call_command('migrate')
        
        # Create superuser if not exists
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin'
            )
            self.stdout.write(self.style.SUCCESS('Superuser created'))
        
        # Collect static files
        call_command('collectstatic', '--noinput')
        
        self.stdout.write(self.style.SUCCESS('Application initialized successfully'))
