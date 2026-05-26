from __future__ import annotations

from typing import Any, ClassVar, Literal

from django.db.models import Q
from django.utils import timezone

from neuxo_backend.models import (
    LinkedinCompany,
    Mentions,
    MentionsTwitter,
    Notification,
)
from .BaseLinkedin import BaseLinkedin


ActorName = Literal["TWITTER_GET_POST",]


class TwitterService(BaseLinkedin):
    ACTOR_NAME: ClassVar[ActorName] = "TWITTER_GET_POST"
    DEFAULT_RUN_INPUT: ClassVar[dict[str, Any]] = {
        "profileUrls": [],
        "resultsLimit": 30,
    }

    def run_get_posts_by_profile_urls(
        self, profile_urls: list[str]
    ) -> list[dict[str, Any]]:
        normalized_urls = [
            normalized_url
            for url in profile_urls
            if (normalized_url := self._normalize_url(url))
        ]
        run_input = self._default_run_input()
        run_input["profileUrls"] = normalized_urls
        return self.run_actor(actor_name="TWITTER_GET_POST", run_input=run_input)

    @staticmethod
    def _get_twitter_handle(value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip().strip("/")
        if not normalized:
            return None

        for host in ("twitter.com/", "x.com/"):
            if host in normalized:
                normalized = normalized.split(host, 1)[1]
                break

        normalized = normalized.lstrip("@")
        handle = normalized.split("/", 1)[0].strip()
        return handle or None

    def _find_company_by_twitter_url(
        self, twitter_url: str | None
    ) -> LinkedinCompany | None:
        normalized = self._normalize_url(twitter_url)
        handle = self._get_twitter_handle(twitter_url)

        candidates: list[str] = []
        if normalized:
            candidates.append(normalized)
            candidates.append(f"{normalized}/")
            if "twitter.com/" in normalized:
                candidates.append(normalized.replace("twitter.com/", "x.com/"))
            elif "x.com/" in normalized:
                candidates.append(normalized.replace("x.com/", "twitter.com/"))

        if handle:
            candidates.append(handle)
            candidates.append(f"@{handle}")
            candidates.append(f"https://x.com/{handle}")
            candidates.append(f"https://twitter.com/{handle}")

        unique_candidates = list(dict.fromkeys(candidates))
        if not unique_candidates:
            return None

        query = Q()
        for candidate in unique_candidates:
            query |= Q(link_twitter=candidate)
        return LinkedinCompany.objects.filter(query).first()

    @staticmethod
    def _parse_posted_at(value: Any) -> timezone.datetime:
        if value is None:
            return timezone.now()
        try:
            timestamp = int(value)
        except (TypeError, ValueError):
            return timezone.now()

        seconds = timestamp / 1000 if timestamp > 10**11 else timestamp
        return timezone.datetime.fromtimestamp(seconds, tz=timezone.utc)

    def upsert_twitter_post_mention(
        self, post: dict[str, Any]
    ) -> MentionsTwitter | None:
        profile_url = self._normalize_url(str(post.get("profileUrl") or ""))
        company = self._find_company_by_twitter_url(profile_url)
        if company is None:
            author_screen_name = self._get_twitter_handle(
                str(self._dict_get(post, ["author", "screenName"]) or "")
            )
            if author_screen_name:
                company = self._find_company_by_twitter_url(author_screen_name)
        if company is None:
            return None

        post_url = self._normalize_url(str(post.get("postUrl") or ""))
        if not post_url:
            return None

        posted_at = self._parse_posted_at(post.get("timestamp"))

        existing = (
            MentionsTwitter.objects.filter(
                mentions__company=company, twitter_post_url=post_url
            )
            .select_related("mentions")
            .first()
        )

        author = post.get("author") or {}
        title = self._safe_str(author.get("name")) or self._safe_str(
            author.get("screenName")
        )
        defaults: dict[str, Any] = {
            "twitter_post_url": post_url,
            "title": title,
            "description": self._safe_str(post.get("postText")),
            "updated_at": posted_at,
        }

        if existing is not None:
            mentions = existing.mentions
            mentions.company = company
            mentions.updated_at = posted_at
            mentions.save(update_fields=["company", "updated_at"])

            for field, value in defaults.items():
                setattr(existing, field, value)
            existing.save(update_fields=list(defaults.keys()))
            twitter_mention = existing
        else:
            mentions = Mentions.objects.create(
                company=company,
                type="TWITTER",
                note="Twitter post",
                updated_at=posted_at,
            )
            twitter_mention = MentionsTwitter.objects.create(
                mentions=mentions, **defaults
            )

        notification, created = Notification.objects.get_or_create(
            reference_id=str(twitter_mention.id),
            type="TWITTER",
            company=company,
            defaults={
                "title": title,
                "post_url": twitter_mention.twitter_post_url,
                "time_post": posted_at,
            },
        )
        if not created:
            notification.title = title
            notification.post_url = twitter_mention.twitter_post_url
            notification.time_post = posted_at
            notification.company = company
            notification.save(
                update_fields=["title", "post_url", "time_post", "company"]
            )

        return twitter_mention

    def run_get_posts_and_upsert_mentions_by_profile_urls(
        self, profile_urls: list[str]
    ) -> list[MentionsTwitter]:
        posts = self.run_get_posts_by_profile_urls(profile_urls)
        created_mentions: list[MentionsTwitter] = []
        for post in posts:
            mention = self.upsert_twitter_post_mention(post)
            if mention is not None:
                created_mentions.append(mention)
        return created_mentions
