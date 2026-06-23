import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Creates the initial SAGE YAADGA administrator from environment variables.'

    def handle(self, *args, **options):
        username = os.getenv('SAGE_ADMIN_USERNAME')
        password = os.getenv('SAGE_ADMIN_PASSWORD')
        email = os.getenv('SAGE_ADMIN_EMAIL', '')

        if not username or not password:
            self.stdout.write('Initial administrator not configured.')
            return

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
                'role': user_model.Role.ADMINISTRATOR,
            },
        )

        if not created:
            self.stdout.write('Initial administrator already exists.')
            return

        user.set_password(password)
        user.save(update_fields=['password'])
        self.stdout.write('Initial administrator created.')
