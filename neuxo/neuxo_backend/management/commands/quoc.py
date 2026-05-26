from django.core.management.base import BaseCommand
from tqdm import tqdm
from neuxo_backend.models import GuestList, LinkedinCompany


class Command(BaseCommand):
    help = "This is a placeholder command."

    def handle(self, *args, **options):
        guests = (
            GuestList.objects.filter(company__isnull=True)
            .exclude(website__isnull=True)
            .exclude(website="")
        )
        matched = 0
        skipped = 0

        for guest in tqdm(guests.iterator(), total=guests.count()):
            raw_website = (guest.website or "").strip().lower()
            if not raw_website:
                skipped += 1
                continue

            candidates = {raw_website.rstrip("/")}
            if not raw_website.startswith("http://") and not raw_website.startswith(
                "https://"
            ):
                candidates.add(f"https://{raw_website}".rstrip("/"))
                candidates.add(f"http://{raw_website}".rstrip("/"))

            company = LinkedinCompany.objects.filter(
                website__in=list(candidates)
            ).first()
            if company:
                guest.company = company
                guest.check_company = True
                guest.save(update_fields=["company", "check_company", "updated_at"])
                matched += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f"Matched companies: {matched}. Skipped: {skipped}.")
        )
