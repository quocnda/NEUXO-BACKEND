from __future__ import annotations
from neuxo_backend.controller import INDUSTRIES_REJECT
from neuxo_backend.controller.utils import (
    getFilterDataQuery,
    getParams,
    getShowingColumns,
)
from neuxo_backend.models import MasterCompanies, ShowingField
from django.db import models
from django.db.models import Q
from users.models import UserWatchList


def getDataCompany(request):
    search_key = request.GET.get("search_key", None)
    companies = MasterCompanies.objects.all().order_by(("-company__created_at"))
    print("Total LEN COMPANIES:", companies.count())
    companies = (
        companies.exclude(company__industry__in=INDUSTRIES_REJECT)
        .exclude(company__country="Vietnam")
        .select_related("company")
    )
    print("Initial LEN COMPANIES:", companies.count())
    print("Search key:", search_key)
    if search_key:
        companies = companies.filter(Q(company__name__icontains=search_key))
    print("LEN COMPANIES after search key:", companies.count())
    count_trigger = request.GET.get("count_trigger", None)
    userId = request.user.get("id", None)

    start_date, end_date, page, limit = getParams(request)

    showing_columns = getShowingColumns(userId)

    if start_date and end_date:
        companies = companies.filter(updated_at__range=[start_date, end_date])
    print("LEN COMPANIES:", companies.count())
    lst_data = []
    user_watchlist = UserWatchList.objects.filter(user_id=userId).values_list(
        "company_id", flat=True
    )
    sort_field_map = {
        "company": "company__name",
        "followers": "company__followers",
        "industry": "company__industry",
        "assignee": "company__assignee__name",
        "country": "company__country",
        "category": "company__category",
        "updated_at": "updated_at",
        "created_at": "company__created_at",
        "funding": "funding_amount",
        "trigger": "trigger",
        "trigger_time": "trigger_time",
        "company_size": "company__size",
        "headquarters": "company__headquarters",
    }
    companies = getFilterDataQuery(
        request, companies, table="matching", sort_field_map=sort_field_map
    )
    companies = companies.values(
        "company__id",
        "company__name",
        "company__linkedin_url",
        "company__website",
        "company__link_twitter",
        "company__labels",
        "company__size",
        "company__category",
        "company__followers",
        "company__headquarters",
        "company__country",
        "company__organization_type",
        "company__industry",
        "company__note_of_user",
        "company__short_description",
        # "company__is_crawl",
        "company__avatar_url",
        # "company__updated_at",
        "company__lst_email_contact",
        "company__user_reach_out",
        "trigger",
        # "company__created_at",
        "updated_at",
        "trigger_time",
        "funding_amount",
        "contact",
        # "score",
    )

    # Get total count before pagination
    total_count = companies.count()

    if page and limit:
        offset = (page - 1) * limit
        companies = companies[offset : offset + limit]
    for company in companies:
        labels = (
            ", ".join(company["company__labels"]) if company["company__labels"] else ""
        )
        is_in_user_watchlist = company["company__id"] in user_watchlist

        dict_company = {
            "company_id": company["company__id"],
            "company": company["company__name"],
            "external": {
                "linkedin": company["company__linkedin_url"],
                "website": company["company__website"],
                "email": "email" if company["contact"] else "",
                "twitter": company["company__link_twitter"],
            },
            "label": labels,
            "trigger": company["trigger"],
            "trigger_time": company["trigger_time"].strftime("%Y-%m-%d"),
            "updated_at": company["updated_at"].strftime("%Y-%m-%d"),
            "funding_amount": float(company["funding_amount"]),
            "contacts": company["contact"],
            "company_size": company["company__size"],
            "category": company["company__category"],
            "followers": company["company__followers"],
            "headquarters": company["company__headquarters"],
            "country": company["company__country"],
            "organization_type": company["company__organization_type"],
            "industry": company["company__industry"],
            "note": company["company__note_of_user"],
            "avatar_url": company["company__avatar_url"],
            "short_description": company["company__short_description"],
            "watchlist": is_in_user_watchlist,
            "lst_email": company["company__lst_email_contact"]
            if company["company__lst_email_contact"]
            else [],
            "status_mail": company["company__user_reach_out"]
            if company["company__user_reach_out"]
            else "Send mail",
        }
        lst_data.append(dict_company)
    sortByVal = request.GET.get("sortByVal", None)
    orderByVal = request.GET.get("orderByVal", "DESC")
    if sortByVal == "label":
        lst_data = sorted(
            lst_data,
            key=lambda x: x["label"].lower(),
            reverse=True if orderByVal.upper() == "DESC" else False,
        )
    # companies = getLastFilterData(request, lst_data, table="matching")
    companies = lst_data
    if count_trigger:
        if int(count_trigger) > 4:
            count_trigger = 4
        else:
            count_trigger = int(count_trigger)
        companies = [
            item for item in companies if len(item["trigger"]) == count_trigger
        ]
        # Update total count after applying count_trigger filter
        total_count = len(companies)

    company_ids = [company["company_id"] for company in companies]
    watchlist_counts = {}
    if company_ids:
        watchlist_counts = dict(
            UserWatchList.objects.filter(company_id__in=company_ids)
            .values("company_id")
            .annotate(count=models.Count("id"))
            .values_list("company_id", "count")
        )

    for company in companies:
        company["is_in_watchlist"] = watchlist_counts.get(company["company_id"], 0)

    paginator = {
        "page": page,
        "limit": limit,
        "total_page": (total_count + limit - 1) // limit,
        "total_item": total_count,
    }

    return paginator, companies, showing_columns


def updateShowingColumnsData(userId, name_columns_and_status: list[dict]):
    count = 0
    for column in name_columns_and_status:
        count += 1
        is_show = "YES" if column.get("is_show") else "NO"
        ShowingField.objects.filter(name_columns=column["name"], user_id=userId).update(
            is_show=is_show, order_by=count
        )
    return getShowingColumns(userId)
