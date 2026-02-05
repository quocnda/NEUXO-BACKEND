from django.db import models
from django.utils import timezone


class Users(models.Model):
    ROLE_CHOICES = [
        ("Admin", "Admin"),
        ("User", "User"),
    ]
    ACCOUNT_STATUS = [
        ("NEW", "NEW"),
        ("VERIFIED", "VERIFIED"),
        ("VERIFY_FAILED", "VERIFY_FAILED"),
    ]
    id = models.AutoField(primary_key=True)
    user_name = models.CharField(max_length=256, null=True)
    first_name = models.CharField(max_length=256, null=True)
    last_name = models.CharField(max_length=256, null=True)
    phone_number = models.CharField(max_length=64, null=True)
    pwd_sha256 = models.CharField(max_length=64, null=True)
    email = models.CharField(max_length=128, null=True)
    avatar = models.ForeignKey(
        "neuxo_backend.Document", on_delete=models.CASCADE, blank=True, null=True
    )
    account_status = models.CharField(
        max_length=128, null=False, default="NEW", choices=ACCOUNT_STATUS
    )
    role = models.CharField(
        max_length=128, null=False, default="User", choices=ROLE_CHOICES
    )
    location = models.CharField(max_length=256, null=True)
    linkedin_cookie = models.TextField(null=True)
    group = models.CharField(max_length=256, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "Users"


class UserWatchList(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, null=False)
    company = models.ForeignKey(
        "neuxo_backend.LinkedinCompany",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )
    target_guest = models.JSONField(max_length=256, null=True)
    note = models.TextField(null=True, blank=True)
    time_PIN = models.DateTimeField(null=True, default=None)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "User_WatchList"
