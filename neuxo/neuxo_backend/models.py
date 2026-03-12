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
    website = models.URLField(max_length=1000, blank=True, null=True)
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
    note_of_user = models.TextField(blank=True, null=True)
    is_finding_company = models.CharField(max_length=200, blank=True, null=True)
    is_crawl = models.CharField(max_length=50, blank=True, null=True)
    is_blacklist = models.BooleanField(default=False, null=True)

    lst_email_contact = models.JSONField(default=list, blank=True, null=True)
    user_reach_out = models.TextField(blank=True, null=True)
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


class LinkedinJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=1000)
    category = models.ForeignKey(
        LinkedinCategory, on_delete=models.CASCADE, blank=True, null=True
    )
    location = models.ForeignKey(
        LinkedinLocation, on_delete=models.CASCADE, blank=True, null=True
    )
    company = models.ForeignKey(
        LinkedinCompany, on_delete=models.CASCADE, blank=True, null=True
    )
    linkedin_url = models.URLField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    label = models.ForeignKey(
        LinkedinJobLabels, on_delete=models.CASCADE, blank=True, null=True
    )
    short_description = models.TextField(blank=True, null=True)

    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    status = models.TextField(blank=True, null=True, default="active")
    last_check = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Linkedin_Jobs"
        indexes = [
            models.Index(fields=["created_at"], name="job_created_at_idx"),
            models.Index(
                fields=["company", "last_check"], name="job_company_lastcheck_idx"
            ),
            models.Index(fields=["linkedin_url"], name="job_linkedin_url_idx"),
        ]


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


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file_name = models.CharField(max_length=255)
    path_file = models.TextField(blank=False, null=False)
    size = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Documents"


class MailAppAccount(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "ACTIVE"),
        ("INACTIVE", "INACTIVE"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, blank=True, null=False)
    email = models.TextField(max_length=300, blank=True, null=True)
    password_app = models.TextField(max_length=300, blank=True, null=True)
    status = models.CharField(default="ACTIVE", choices=STATUS_CHOICES, max_length=100)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "User_Mail_Account"


class Notification(models.Model):
    TYPE_CHOICES = [
        ("SUB_DOMAIN", "SUB_DOMAIN"),
        ("LINKEDIN", "LINKEDIN"),
        ("TWITTER", "TWITTER"),
        ("EVENT", "EVENT"),
        ("HIRING", "HIRING"),
        ("NEWS", "NEWS"),
        ("FUNDING", "FUNDING"),
        ("JOB_CHANGE", "JOB_CHANGE"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.TextField(blank=True, null=False, choices=TYPE_CHOICES)
    reference_id = models.TextField(blank=True, null=False)
    title = models.TextField(blank=True, null=True)
    post_url = models.TextField(blank=True, null=True)
    time_post = models.DateTimeField(default=timezone.now)
    company = models.ForeignKey(
        LinkedinCompany, on_delete=models.CASCADE, blank=True, null=True
    )
    guest_id = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    is_send = models.BooleanField(default=False)

    class Meta:
        db_table = "Notification"


# --------------------------------Funding ---------------------------------------
class CompanyFunding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    round = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateTimeField(default=timezone.now)
    amount = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=500, blank=True, null=True)

    website = models.URLField(max_length=200, blank=True, null=True)
    project_url = models.URLField(max_length=200, blank=True, null=True)
    linkedin_url = models.URLField(max_length=200, blank=True, null=True)
    linkedin_uid = models.CharField(max_length=100, blank=True, null=True)

    company = models.ForeignKey(
        LinkedinCompany, on_delete=models.CASCADE, blank=True, null=True
    )
    logo_url = models.URLField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Funding"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["updated_at"]),
        ]


# -----------------Clutch io-----------------


class ClutchReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        LinkedinCompany, on_delete=models.CASCADE, blank=True, null=True
    )
    reviewer_name = models.CharField(max_length=255, blank=True, null=True)
    reviewer_role = models.CharField(max_length=255, blank=True, null=True)
    reviewer_company = models.CharField(max_length=255, blank=True, null=True)
    industry = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    client_size = models.CharField(max_length=255, blank=True, null=True)
    services = models.CharField(max_length=255, blank=True, null=True)
    project_size = models.CharField(max_length=255, blank=True, null=True)
    project_length = models.CharField(max_length=255, blank=True, null=True)
    project_description = models.TextField(blank=True, null=True)
    background = models.TextField(blank=True, null=True)
    website_url = models.URLField(max_length=1000, blank=True, null=True)
    linkedin_url = models.URLField(max_length=200, blank=True, null=True)
    description_company_outsource = models.TextField(blank=True, null=True)
    services_company_outsource = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Clutch_Review"
        indexes = [
            models.Index(fields=["company"]),
            models.Index(fields=["updated_at"]),
        ]


# -----------------People ------------------
class LinkedinPersonalEmail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=100)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    linkedin_url = models.URLField(max_length=200, blank=True, null=True)
    twitter_url = models.URLField(max_length=200, blank=True, null=True)
    avatar_linkedin_url = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=200, blank=True, null=True)
    company = models.ForeignKey(
        LinkedinCompany, on_delete=models.CASCADE, blank=True, null=True
    )
    twitter_summary = models.TextField(blank=True, null=True)

    note = models.TextField(blank=True, null=True)
    is_update = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    urn = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "Linkedin_Peoples"


class PersonalExperience(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    linkedin_company_id = models.TextField(blank=True, null=True, max_length=50)
    linkedin_company_url = models.TextField(blank=True, null=True)
    linkedin_company_logo = models.TextField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)
    company_name = models.TextField(blank=True, null=True)
    time_period = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    personal = models.ForeignKey(
        LinkedinPersonalEmail, on_delete=models.CASCADE, blank=False, null=False
    )

    class Meta:
        db_table = "Linkedin_Personal_Experience"


class PersonalEmail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=100, unique=False)
    personal = models.ForeignKey(
        LinkedinPersonalEmail, on_delete=models.CASCADE, blank=False, null=False
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "Personal_Email"


# ----------------------------------- ICP -----------------------------------#


class ListICP(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    icp_name = models.TextField(blank=True, null=True)
    icp_description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "List_ICP"


# ----------------------------------- Mentions -----------------------------------#


class Mentions(models.Model):
    TYPE_CHOICES = [
        ("SUB_DOMAIN", "SUB_DOMAIN"),
        ("LINKEDIN", "LINKEDIN"),
        ("TWITTER", "TWITTER"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        LinkedinCompany, on_delete=models.CASCADE, blank=False, null=False
    )
    note = models.TextField(blank=True, null=True)
    type = models.TextField(blank=True, null=False, choices=TYPE_CHOICES)
    guest_id = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Mentions"


class MentionsSubDomain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_domain = models.TextField(blank=True, null=True)
    ip = models.TextField(blank=True, null=True)
    mentions = models.ForeignKey(
        Mentions, on_delete=models.CASCADE, blank=False, null=False
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Mentions_SubDomain"


class MentionsLinkedin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    linkedin_post_url = models.TextField(blank=True, null=True)
    linkedin_repost_url = models.TextField(blank=True, null=True)
    description_repost = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    mentions = models.ForeignKey(
        Mentions, on_delete=models.CASCADE, blank=False, null=False
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Mentions_Linkedin"


class MentionsTwitter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    twitter_post_url = models.TextField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    mentions = models.ForeignKey(
        Mentions, on_delete=models.CASCADE, blank=False, null=False
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "Mentions_Twitter"


# ----------------------------------- User Notification -----------------------------------#


class UserNotification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, blank=True, null=True)
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, blank=True, null=True
    )
    is_read = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "User_Notification"


# ----------------------------------- News -----------------------------------#


class NewsInformation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_company = models.TextField(blank=True, null=True)
    company = models.ForeignKey(
        LinkedinCompany, on_delete=models.CASCADE, blank=True, null=True
    )
    link_news = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    category = models.TextField(blank=True, null=True)
    time_post = models.DateTimeField(default=timezone.now)
    title = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "News"


# ----------------------------------- History Gen AI -----------------------------------#


class HistoryGenAI(models.Model):
    ROLE = [
        ("user", "user"),
        ("assistant", "assistant"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.TextField(blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    completion_id = models.TextField(blank=True, null=True)
    summarize_content = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    order_number = models.IntegerField(default=0)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, blank=False, default=1)
    company_id = models.TextField(blank=True, null=True)
    person_contact_id = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "History_Gen_AI"
