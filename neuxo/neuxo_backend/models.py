from django.db import models  # noqa: F401
import uuid
from django.utils import timezone

from users.models import Users


# ----------------------------------- Main Functions -----------------------------------#


class LinkedinCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "DEFAULT_Linkedin_Category"


class LinkedinJobLabels(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        LinkedinCategory, on_delete=models.CASCADE, blank=True, null=True
    )
    is_pick_gen_ai = models.BooleanField(default=True)

    class Meta:
        db_table = "DEFAULT_Linkedin_JobLabels"


class LinkedinLocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "DEFAULT_Linkedin_Location"


class LinkedinExcludeKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=100)

    class Meta:
        db_table = "DEFAULT_Linkedin_ExcludeKey"


class LinkedinExcludeCompany(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.CharField(max_length=100)

    class Meta:
        db_table = "DEFAULT_Linkedin_ExcludeCompany"


# ---------------------- Company Models ----------------------#
class LinkedinCompany(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    avatar_url = models.URLField(max_length=1000, blank=True, null=True)
    linkedin_url = models.URLField(max_length=500, blank=True, null=True)
    linkedin_uid = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(max_length=200, blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, null=True)
    link_twitter = models.CharField(max_length=100, blank=True, null=True)

    linkedin_funding_amt = models.CharField(max_length=100, blank=True, null=True)
    linkedin_lasted_funding_date = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    industry = models.CharField(max_length=256, blank=True, null=True)
    organization_type = models.CharField(max_length=500, blank=True, null=True)
    headquarters = models.CharField(max_length=500, blank=True, null=True)
    followers = models.PositiveIntegerField(blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    short_description = models.TextField(blank=True, null=True)
    labels = models.JSONField(default=list, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)

    note = models.TextField(blank=True, null=True)
    is_finding_company = models.CharField(max_length=200, blank=True, null=True)
    is_crawl = models.CharField(max_length=50, blank=True, null=True)
    is_blacklist = models.BooleanField(default=False, null=True)

    organization_revune_apollo = models.CharField(
        max_length=255, blank=True, null=True, default=""
    )

    # Add missing fields referenced in indexes
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    assignee = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "Linkedin_Companies"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["industry"]),
            models.Index(fields=["country"]),
            models.Index(fields=["category"]),
            models.Index(fields=["is_blacklist"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
            models.Index(fields=["assignee"]),
        ]

        ordering = ["-created_at"]

    @classmethod
    def get_paginated_data(cls, page=1, page_size=10, filters=None, order_by=None):
        """
        Get paginated data with optimized queries
        """
        queryset = cls.objects.all()

        if filters:
            queryset = queryset.filter(**filters)
        if order_by:
            queryset = queryset.order_by(*order_by)
        queryset = queryset.select_related("assignee")

        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size

        paginated_data = queryset[start:end]

        return {
            "data": paginated_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }


class MasterCompanies(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        LinkedinCompany, on_delete=models.CASCADE, blank=True, null=True
    )

    trigger = models.JSONField(default=list, blank=True, null=True)
    contact = models.BooleanField(default=False)
    funding_amount = models.TextField(blank=True, null=True)
    score = models.FloatField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    trigger_time = models.DateTimeField(default=timezone.now)

    lst_email_contact = models.JSONField(default=list, blank=True, null=True)
    user_reach_out = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "Companies_Master"


class ShowingField(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_columns = models.CharField(max_length=100)
    is_show = models.TextField(blank=True, null=True)
    can_arrange = models.TextField(default="NO", blank=True, null=True)
    order_by = models.IntegerField(default=0, null=True, blank=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        db_table = "User_Dashboard_ShowingField"


# ----------------------------------- Event  -----------------------------------#


class MainEvents(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    api_id = models.CharField(max_length=100, blank=True, null=True)

    name = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    event_url = models.URLField(max_length=500, blank=True, null=True)
    cover_image_url = models.URLField(max_length=500, blank=True, null=True)
    avatar_image_url = models.URLField(max_length=500, blank=True, null=True)
    geo_city = models.CharField(max_length=100, blank=True, null=True)
    geo_country = models.CharField(max_length=100, blank=True, null=True)
    geo_region = models.CharField(max_length=100, blank=True, null=True)

    instagram_url = models.URLField(max_length=200, blank=True, null=True)
    linkedin_url = models.URLField(max_length=200, blank=True, null=True)
    twitter_url = models.URLField(max_length=200, blank=True, null=True)
    website = models.URLField(max_length=200, blank=True, null=True)
    youtube_url = models.URLField(max_length=200, blank=True, null=True)
    verified_at = models.DateTimeField(default=timezone.now, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Events_MainEvents"


class EventsList(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=500)
    # description = models.TextField(blank=True, null=True)
    event_url = models.URLField(max_length=200, blank=True, null=True)
    start_date = models.DateTimeField(default=timezone.now)
    ticket_key = models.CharField(max_length=100, blank=True, null=True)
    api_id = models.CharField(max_length=100, blank=True, null=True)

    location = models.CharField(max_length=1000, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    event_parent = models.CharField(max_length=100, blank=True, null=True)
    event_parent_path = models.URLField(max_length=200, blank=True, null=True)

    note = models.TextField(blank=True, null=True)
    number_of_company = models.IntegerField(blank=True, null=True)
    number_of_guest = models.IntegerField(blank=True, null=True)
    account = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    main_event = models.ForeignKey(
        MainEvents, on_delete=models.CASCADE, blank=True, null=True
    )

    event_image = models.TextField(blank=True, null=True)
    approval_status = models.CharField(max_length=100, blank=True, null=True)
    guest_count = models.IntegerField(blank=True, null=True)
    start_at = models.DateTimeField(default=timezone.now)
    end_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Events_List"


class GuestList(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=500)
    linkedin_url = models.URLField(max_length=200, blank=True, null=True)
    twitter_url = models.URLField(max_length=200, blank=True, null=True)
    website = models.URLField(max_length=200, blank=True, null=True)

    company = models.ForeignKey(
        LinkedinCompany, on_delete=models.CASCADE, blank=True, null=True
    )
    event = models.ForeignKey(
        EventsList, on_delete=models.CASCADE, blank=True, null=True
    )

    email = models.EmailField(max_length=100)
    role = models.CharField(max_length=300, blank=True, null=True)
    check_company = models.BooleanField(default=False)

    email_status_emailinfor = models.CharField(max_length=100, blank=True, null=True)
    send_by_emailinfor = models.CharField(max_length=100, blank=True, null=True)
    last_activity_emailinfor = models.DateTimeField(default=timezone.now, null=True)
    error_emailinfor = models.TextField(blank=True, null=True)
    last_reply_emailinfor = models.DateTimeField(default=timezone.now, null=True)
    note = models.TextField(blank=True, null=True)
    email_input_from_user = models.BooleanField(default=False)

    time_zone = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Events_GuestList"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["company"]),
            models.Index(fields=["email_status_emailinfor"]),
        ]
