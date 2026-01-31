from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "This is a placeholder command."

    def handle(self, *args, **options):
        self.stdout.write("Placeholder command executed successfully.")
