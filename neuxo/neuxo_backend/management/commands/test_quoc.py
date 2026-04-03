from django.core.management.base import BaseCommand
from neuxo_backend.crawler.Subdomain import Subdomains

class Command(BaseCommand):
    help = "This is a placeholder command."

    def handle(self, *args, **options):
        self.stdout.write("Placeholder command executed successfully.")
        Subdomains().getSubdomainsByLinkCompany('https://aspecta.ai')