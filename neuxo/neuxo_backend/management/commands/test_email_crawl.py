from __future__ import annotations

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from neuxo_backend.models import MailAppAccount
from neuxo_backend.tasks import (
    INBOX_FOLDER,
    crawl_mail_account_task,
    enqueue_mail_account_crawl,
    _message_cache_key,
)


class Command(BaseCommand):
    help = "Test crawl email history for a saved mail account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="Email address of the saved mail account to crawl.",
        )
        parser.add_argument(
            "--account-id",
            type=str,
            help="UUID of the MailAppAccount to crawl.",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            dest="run_async",
            help="Queue the crawl through Celery instead of running immediately.",
        )
        parser.add_argument(
            "--reset-cursor",
            action="store_true",
            help="Clear Redis crawl cursors before starting, useful to recrawl from the newest messages again.",
        )

    def handle(self, *args, **options):
        email = options.get("email")
        account_id = options.get("account_id")
        run_async = options.get("run_async", False)
        reset_cursor = options.get("reset_cursor", False)

        if not email and not account_id:
            raise CommandError("Provide either --email or --account-id.")

        query = MailAppAccount.objects.filter(status="ACTIVE")
        if account_id:
            account = query.filter(id=account_id).first()
        else:
            account = query.filter(email=(email or "").strip().lower()).first()

        if not account:
            raise CommandError("Active mail account not found.")

        if reset_cursor:
            sent_candidates = ['"[Gmail]/Sent Mail"', '"[Google Mail]/Sent Mail"', "Sent"]
            for folder_name in [INBOX_FOLDER, *sent_candidates]:
                cache.delete(_message_cache_key(str(account.id), folder_name))
            self.stdout.write(
                self.style.WARNING(
                    f"Reset crawl cursors for account {account.email} ({account.id})."
                )
            )

        if run_async:
            result = enqueue_mail_account_crawl.delay(str(account.id))
            self.stdout.write(
                self.style.SUCCESS(
                    f"Queued crawl for {account.email} ({account.id}), task_id={result.id}"
                )
            )
            return

        result = crawl_mail_account_task.run(str(account.id))
        self.stdout.write(self.style.SUCCESS(f"Crawl result: {result}"))
