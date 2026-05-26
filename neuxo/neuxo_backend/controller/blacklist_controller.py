from __future__ import annotations

from typing import Any

from django.db.models import OuterRef, Subquery
from django.http import HttpRequest

from neuxo_backend.controller.utils import (
    getFilterDataQueryForBlacklist,
    getParams,
    getShowingColumnsCustom,
)
from neuxo_backend.dto.blacklist_dto import (
    BlacklistCompanyItem,
    BlacklistExternal,
    BlacklistPagination,
)
from neuxo_backend.models import LinkedinCompany, MasterCompanies


def getBlacklistData(
    request: HttpRequest,
) -> tuple[BlacklistPagination, list[BlacklistCompanyItem], list[Any]]:
    start_date, end_date, page, limit = getParams(request)

    sort_field_map = {
        "company": "name",
        "followers": "followers",
        "industry": "industry",
        "country": "country",
        "category": "category",
        "company_size": "size",
        "headquarters": "headquarters",
        "label": "labels",
        "trigger": "trigger",
        "trigger_time": "trigger_time",
        "updated_at": "updated_at",
        "created_at": "created_at",
    }

    trigger_subquery = MasterCompanies.objects.filter(company_id=OuterRef("id")).values(
        "trigger"
    )[:1]

    trigger_time_subquery = MasterCompanies.objects.filter(
        company_id=OuterRef("id")
    ).values("trigger_time")[:1]

    main_data = LinkedinCompany.objects.filter(is_blacklist=True).annotate(
        trigger=Subquery(trigger_subquery),
        trigger_time=Subquery(trigger_time_subquery),
    )

    main_data = getFilterDataQueryForBlacklist(
        request, main_data, sort_field_map=sort_field_map
    )
    main_data = main_data.values(
        "id",
        "name",
        "website",
        "industry",
        "linkedin_url",
        "headquarters",
        "category",
        "labels",
        "size",
        "organization_type",
        "short_description",
        "note_of_user",
        "created_at",
        "updated_at",
        "link_twitter",
        "followers",
        "linkedin_funding_amt",
        "country",
        "trigger",
        "trigger_time",
    )

    total_count = main_data.count()
    offset = (page - 1) * limit
    paginated = list(main_data[offset : offset + limit])

    for data in paginated:
        data["external"] = BlacklistExternal(
            linkedin=data.get("linkedin_url"),
            website=data.get("website"),
            twitter=data.get("link_twitter"),
        )
        data["label"] = ", ".join(data["labels"]) if data["labels"] else ""
        data["company_size"] = data["size"]
        data["company_id"] = data["id"]
        data["company"] = data["name"]
        data["funding_amount"] = data["linkedin_funding_amt"]
        if data.get("created_at"):
            data["created_at"] = data["created_at"].strftime("%Y-%m-%d")
        else:
            data["created_at"] = None
        if data.get("updated_at"):
            data["updated_at"] = data["updated_at"].strftime("%Y-%m-%d")
        else:
            data["updated_at"] = None

        master = MasterCompanies.objects.filter(company_id=data["id"]).first()
        if master:
            data["trigger"] = master.trigger if master.trigger else []
            if master.trigger_time:
                data["trigger_time"] = master.trigger_time.strftime("%d %b, %Y")
            else:
                data["trigger_time"] = None
        else:
            data["trigger"] = []
            data["trigger_time"] = None

    paginator = {
        "page": page,
        "limit": limit,
        "total_page": (total_count + limit - 1) // limit,
        "total_item": total_count,
    }

    showing_columns = getShowingColumnsCustom("Blacklist", request)

    normalized_pagination = BlacklistPagination.model_validate(paginator)
    normalized_items = [BlacklistCompanyItem.model_validate(item) for item in paginated]

    return normalized_pagination, normalized_items, showing_columns


def addToBlacklist(ids: list[str]) -> list[str]:
    not_found = []
    for company_id in ids:
        company = LinkedinCompany.objects.filter(id=company_id).first()
        if not company:
            not_found.append(company_id)
            continue
        company.is_blacklist = True
        company.save()
    return not_found


def removeFromBlacklist(ids: list[str]) -> list[str]:
    not_found = []
    for company_id in ids:
        company = LinkedinCompany.objects.filter(id=company_id).first()
        if not company:
            not_found.append(company_id)
            continue
        company.is_blacklist = False
        company.save()
    return not_found
