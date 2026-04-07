
from __future__ import annotations
from typing import Any, ClassVar, Literal

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from neuxo_backend.models import (
    Mentions,
    MentionsLinkedin,
    Notification,
)
from .BaseLinkedin import BaseLinkedin


ActorName = Literal[
    "LINKEDIN_GET_LEADS",
    "LINKEDIN_GET_PROFILE_PERSON",
    "LINKEDIN_GET_POST",
    "LINKEDIN_GET_JOB",
]
class LinkedinPostService(BaseLinkedin):
    ACTOR_NAME: ClassVar[ActorName] = "LINKEDIN_GET_POST"
    DEFAULT_RUN_INPUT: ClassVar[dict[str, Any]] = {
        "deepScrape": False,
        "limitPerSource": 10,
        "rawData": False,
        "urls": [],
    }

    def run_get_posts_by_urls(self, urls: list[str]) -> list[dict[str, Any]]:
        normalized_urls = [normalized_url for url in urls if (normalized_url := self._normalize_url(url))]
        run_input = self._default_run_input()
        run_input["urls"] = normalized_urls
        return self.run_actor(actor_name="LINKEDIN_GET_POST", run_input=run_input)

    def upsert_linkedin_post_mention(self, post: dict[str, Any]) -> MentionsLinkedin | None:
        company, person = self._resolve_company_and_person_for_post(post)
        if company is None:
            return None
        guest_id = str(person.id) if person is not None else None

        post_url = self._normalize_url(str(post.get("url") or ""))
        if not post_url:
            return None

        posted_at = parse_datetime(str(post.get("postedAtISO") or ""))
        if posted_at is None:
            posted_at = timezone.now()

        existing_query = MentionsLinkedin.objects.filter(mentions__company=company, linkedin_post_url=post_url)
        if guest_id is None:
            existing_query = existing_query.filter(Q(mentions__guest_id__isnull=True) | Q(mentions__guest_id=""))
        else:
            existing_query = existing_query.filter(mentions__guest_id=guest_id)
        existing = existing_query.select_related("mentions").first()

        title = self._safe_str(post.get("authorName")) or self._safe_str(self._dict_get(post, ["author", "name"]))

        defaults: dict[str, Any] = {
            "linkedin_post_url": post_url,
            "linkedin_repost_url": self._safe_str(post.get("inputUrl")),
            "description_repost": self._safe_str(post.get("activityDescription")),
            "note": self._safe_str(post.get("timeSincePosted")),
            "title": title,
            "description": self._safe_str(post.get("text")),
            "post_urn": self._safe_str(post.get("urn")),
            "share_urn": self._safe_str(post.get("shareUrn")),
            "post_type": self._safe_str(post.get("type"), 50),
            "input_url": self._safe_str(post.get("inputUrl")),
            "author_name": title,
            "author_type": self._safe_str(post.get("authorType"), 50),
            "author_profile_url": self._safe_str(post.get("authorProfileUrl")),
            "author_urn": self._safe_str(post.get("authorUrn")),
            "author_followers_count": self._safe_str(post.get("authorFollowersCount"), 100),
            "posted_at_iso": posted_at,
            "posted_at_timestamp": post.get("postedAtTimestamp"),
            "time_since_posted": self._safe_str(post.get("timeSincePosted"), 50),
            "num_likes": post.get("numLikes"),
            "num_comments": post.get("numComments"),
            "num_shares": post.get("numShares"),
            "images": post.get("images") or [],
            "attributes": post.get("attributes") or [],
            "raw_data": post,
            "updated_at": posted_at,
        }

        if existing is not None:
            mentions = existing.mentions
            mentions.guest_id = guest_id
            mentions.company = company
            mentions.updated_at = posted_at
            mentions.save(update_fields=["guest_id", "company", "updated_at"])

            for field, value in defaults.items():
                setattr(existing, field, value)
            existing.save(update_fields=list(defaults.keys()))
            linkedin_mention = existing
        else:
            mentions = Mentions.objects.create(
                company=company,
                guest_id=guest_id,
                type="LINKEDIN",
                note="LinkedIn post",
                updated_at=posted_at,
            )
            linkedin_mention = MentionsLinkedin.objects.create(mentions=mentions, **defaults)

        notification, created = Notification.objects.get_or_create(
            reference_id=str(linkedin_mention.id),
            type="LINKEDIN",
            company=company,
            defaults={"title": title, "post_url": linkedin_mention.linkedin_post_url, "time_post": posted_at},
        )
        if not created:
            notification.title = title
            notification.post_url = linkedin_mention.linkedin_post_url
            notification.time_post = posted_at
            notification.guest_id = guest_id
            notification.company = company
            notification.save(update_fields=["title", "post_url", "time_post", "guest_id", "company"])
        else:
            notification.guest_id = guest_id
            notification.save(update_fields=["guest_id"])

        return linkedin_mention

    def run_get_posts_and_upsert_mentions_by_urls(self, urls: list[str]) -> list[MentionsLinkedin]:
        posts = self.run_get_posts_by_urls(urls)
        created_mentions: list[MentionsLinkedin] = []
        for post in posts:
            mention = self.upsert_linkedin_post_mention(post)
            if mention is not None:
                created_mentions.append(mention)
        return created_mentions
