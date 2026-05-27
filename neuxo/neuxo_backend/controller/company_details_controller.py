from __future__ import annotations

from itertools import chain

from django.utils import timezone

from neuxo_backend.models import (
    CompanyFunding,
    EventsList,
    GuestList,
    LinkedinCompany,
    LinkedinJob,
    LinkedinPersonalEmail,
    MasterCompanies,
    PersonalEmail,
    PersonalExperience,
)
from users.models import Users, UserWatchList


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def getTriggerDataByCompanyId(company_id: str) -> dict:
    """Return structured trigger data (funding, hiring, events, contacts) for a company."""
    company = LinkedinCompany.objects.filter(id=company_id).first()
    if not company:
        return {}

    all_data: dict = {
        "company_information": {
            "assignee": company.assignee or "",
            "name": company.name,
            "linkedin_url": company.linkedin_url,
            "website": company.website,
            "link_twitter": company.link_twitter,
            "size": company.size,
            "industry": company.industry,
            "organization_type": company.organization_type,
            "headquarters": company.headquarters,
            "followers": company.followers,
            "category": [company.category] if company.category else [],
            "short_description": company.description,
            "label": company.labels,
            "country": company.country,
            "avatar_linkedin_url": company.avatar_url,
            "is_blacklist": company.is_blacklist,
        },
        "funding": [],
        "hiring": [],
        "event": [],
        "news": [],
        "contacts": [],
    }

    # Funding
    funding_data = CompanyFunding.objects.filter(
        linkedin_url=company.linkedin_url
    ).values("name", "date", "amount", "category", "project_url")
    funding_seen: set = set()
    for item in funding_data:
        item["date"] = item["date"].strftime("%Y-%m-%d") if item["date"] else ""
        key = (
            item["name"],
            item["date"],
            item["amount"],
            item["category"],
            item["project_url"],
        )
        if key not in funding_seen:
            funding_seen.add(key)
            all_data["funding"].append(item)

    # Hiring
    hiring_data = (
        LinkedinJob.objects.filter(company=company)
        .exclude(status="removed")
        .values("title", "category__name", "linkedin_url", "label__name", "created_at")
        .order_by("-created_at")
    )
    hiring_seen: set = set()
    for item in hiring_data:
        item["created_at"] = (
            item["created_at"].strftime("%Y-%m-%d") if item["created_at"] else ""
        )
        hiring_key = (item["title"], item["linkedin_url"])
        if hiring_key not in hiring_seen:
            hiring_seen.add(hiring_key)
            all_data["hiring"].append(item)

    # Events
    event_ids = GuestList.objects.filter(company=company).values_list(
        "event__id", flat=True
    )
    event_data = (
        EventsList.objects.filter(id__in=event_ids)
        .values("name", "event_url", "start_date")
        .order_by("-start_date")
    )
    event_seen: set = set()
    for item in event_data:
        item["event_url"] = (
            "https://lu.ma/" + item["event_url"] if item["event_url"] else ""
        )
        item["start_date"] = (
            item["start_date"].strftime("%Y-%m-%d") if item["start_date"] else ""
        )
        event_key = (item["name"], item["event_url"], item["start_date"])
        if event_key not in event_seen:
            event_seen.add(event_key)
            all_data["event"].append(item)

    # Contacts
    contacts = LinkedinPersonalEmail.objects.filter(company__id=company_id).values(
        "id",
        "first_name",
        "last_name",
        "linkedin_url",
        "role",
        "twitter_url",
        "created_at",
        "avatar_linkedin_url",
    )
    for item in contacts:
        item["created_at"] = (
            item["created_at"].strftime("%Y-%m-%d") if item["created_at"] else ""
        )
        first = item["first_name"] or ""
        last = item["last_name"] or ""
        item["first_name"] = first
        item["last_name"] = last
        item["name"] = (first + " " + last).strip() if first != last else last
        item["twitter_url"] = item["twitter_url"] or ""
        all_data["contacts"].append(item)

    return all_data


def getCompanyDetailById(user_id, company_id: str) -> dict | None:
    """Return full company detail including watchlist meta."""
    all_data = getTriggerDataByCompanyId(company_id)
    if not all_data:
        return None

    user_watchlist = UserWatchList.objects.filter(
        user_id=user_id, company_id=company_id
    ).first()
    note_watchlist = user_watchlist.note if user_watchlist else None
    count_watchlist = UserWatchList.objects.filter(company_id=company_id).count()
    info = all_data["company_information"]

    return {
        "assignee": info["assignee"],
        "name": info["name"],
        "linkedin_url": info["linkedin_url"],
        "twitter_url": info["link_twitter"],
        "website": info["website"],
        "size": info["size"],
        "industry": info["industry"],
        "organization_type": info["organization_type"],
        "headquarters": info["headquarters"],
        "followers": info["followers"],
        "category": info["category"],
        "short_description": info["short_description"],
        "label": info["label"],
        "country": info["country"],
        "avatar_url": info["avatar_linkedin_url"],
        "is_blacklist": info["is_blacklist"],
        "note_watchlist": note_watchlist,
        "watchlist": user_watchlist is not None,
        "is_in_watchlist": count_watchlist,
        "funding": all_data["funding"],
        "hiring": all_data["hiring"],
        "event": all_data["event"],
        "news": all_data["news"],
        "contacts": all_data["contacts"],
    }


def getContactsWithDetails(company_id: str) -> list[dict]:
    """Return contacts for a company with their experiences and emails."""
    all_data = getTriggerDataByCompanyId(company_id)
    contacts = all_data.get("contacts", [])
    print(f"Contacts for company {company_id}: {contacts}")  # Debug log
    result = []
    for item in contacts:
        experiences = list(
            PersonalExperience.objects.filter(personal_id=item["id"])
            .values(
                "id",
                "linkedin_company_url",
                "linkedin_company_logo",
                "title",
                "company_name",
                "time_period",
                "created_at",
            )
            .order_by("-created_at")
        )
        emails = list(
            PersonalEmail.objects.filter(personal_id=item["id"])
            .values("id", "email")
            .order_by("-created_at")
        )
        item["experiences"] = experiences
        item["emails"] = emails
        result.append(item)
    return result


def addTwitterUrl(company_id: str, url_twitter: str):
    """Update twitter URL for a company. Returns the updated company or raises."""
    company = LinkedinCompany.objects.filter(id=company_id).first()
    if not company:
        return None
    company.link_twitter = url_twitter
    company.save()
    return company


def addContactForCompany(company_id: str, linkedin_url: str, twitter_url: str | None):
    """Create or update a contact for a company by linkedin URL."""
    company = LinkedinCompany.objects.filter(id=company_id).first()
    if not company:
        return None, "Company not found"

    linkedin_url = linkedin_url.strip("/")
    contact, created = LinkedinPersonalEmail.objects.update_or_create(
        linkedin_url=linkedin_url,
        defaults={
            "linkedin_url": linkedin_url,
            "twitter_url": twitter_url,
            "company_id": company_id,
            "updated_at": timezone.now(),
        },
    )
    return contact, None


def addEmailToContact(contact_id: str, email: str):
    """Add a new email to a contact and sync to company's lst_email_contact."""
    contact = LinkedinPersonalEmail.objects.filter(id=contact_id).first()
    if not contact:
        return "Contact not found"

    if PersonalEmail.objects.filter(email=email, personal=contact).exists():
        return "Email already exists"

    PersonalEmail.objects.create(email=email, personal=contact)

    company = contact.company
    if not company:
        return "Company not found"

    lst = company.lst_email_contact or []
    lst.append(email)
    company.lst_email_contact = list(set(lst))
    company.save()
    return None


def removeEmailFromContact(email_id: str):
    """Delete a PersonalEmail by id."""
    email_obj = PersonalEmail.objects.filter(id=email_id).first()
    if not email_obj:
        return "Email not found"
    email_obj.delete()
    return None


def updateEmailForContact(contact_id: str, email_id: str, new_email: str):
    """Update an email entry and re-sync the company's email list."""
    contact = LinkedinPersonalEmail.objects.filter(id=contact_id).first()
    if not contact:
        return "Contact not found"

    if PersonalEmail.objects.filter(email=new_email, personal=contact).exists():
        return "Email already exists"

    email_obj = PersonalEmail.objects.filter(id=email_id).first()
    if not email_obj:
        return "Email not found"

    email_obj.email = new_email
    email_obj.save()
    contact.email = new_email
    contact.save()

    company = contact.company
    if not company:
        return "Company not found"

    data_individual = LinkedinPersonalEmail.objects.filter(company=company)
    invalid_emails = {"#VALUE!", "", None, "Email unavailable", "waiting"}
    direct_emails = [
        e
        for e in data_individual.values_list("email", flat=True)
        if e not in invalid_emails
    ]
    personal_ids = list(data_individual.values_list("id", flat=True))
    related_emails = PersonalEmail.objects.filter(
        personal_id__in=personal_ids
    ).values_list("email", flat=True)
    lst_email = list(set(chain(direct_emails, related_emails)))
    company.lst_email_contact = lst_email
    company.save()

    master = MasterCompanies.objects.filter(company=company).first()
    if master:
        master.lst_email_contact = lst_email
        master.save()

    return None


def deleteContact(user_id: int, contact_id: str):
    """Delete a contact. Only Admins can perform this action."""
    user = Users.objects.filter(id=user_id).first()
    if not user:
        return "User not found"
    if user.role == "User":
        return "Permission denied"

    contact = LinkedinPersonalEmail.objects.filter(id=contact_id).first()
    if not contact:
        return "Contact not found"

    PersonalExperience.objects.filter(personal__id=contact_id).delete()
    PersonalEmail.objects.filter(personal__id=contact_id).delete()
    contact.delete()
    return None
