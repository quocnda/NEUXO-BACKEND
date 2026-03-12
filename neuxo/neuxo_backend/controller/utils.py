from __future__ import annotations

from typing import Literal

from neuxo_backend.models import ShowingField
from neuxo_backend.controller import COMPANY_SIZE_ORDER
from functools import reduce
import operator
from django.db.models import (
    Case,
    F,
    Q,
    Value,
    When,
    IntegerField,
)
from django.db.models.functions import Replace


def getParams(request):
    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 100))
    if page < 1:
        page = 1
    if limit < 1 or limit > 200:
        limit = 10
    if start_date and len(start_date) == 10:
        start_date = start_date + " 00:00:00"
    if end_date and len(end_date) == 10:
        end_date = end_date + " 23:59:59"

    return start_date, end_date, page, limit


def getShowingColumns(userId=None):
    if userId is None:
        is_showing_columns = (
            ShowingField.objects.filter(user_id=None).values().order_by("order_by")
        )
    else:
        is_showing_columns = (
            ShowingField.objects.filter(user_id=userId).values().order_by("order_by")
        )

    name_order = [
        "company",
        "link",
        "label",
        "category",
        "trigger",
        "trigger_time",
        "company_size",
        "followers",
        "headquarters",
        "country",
        "industry",
        "action",
    ]

    showing_columns = []
    for column in is_showing_columns:
        if column["name_columns"] not in name_order:
            continue
        if column["is_show"] == "YES":
            dict_col_value = {"name": column["name_columns"], "is_show": True}
        else:
            dict_col_value = {"name": column["name_columns"], "is_show": False}

        if column["can_arrange"] == "YES":
            dict_col_value["can_arrange"] = True
        else:
            dict_col_value["can_arrange"] = False
        showing_columns.append(dict_col_value)
    return showing_columns


def apply_custom_sort(
    queryset, field_expr, order_map, sort_desc=False, alias="sort_order"
):
    normalized = Replace(F(field_expr), Value(","), Value(""))

    whens = [
        When(normalized=label.replace(",", ""), then=Value(rank))
        for label, rank in order_map.items()
    ]
    return queryset.annotate(
        normalized=normalized,
        **{alias: Case(*whens, default=Value(999), output_field=IntegerField())},
    ).order_by(f"-{alias}" if sort_desc else alias)


def getFilterDataQuery(request=None, companies=None, table=None, sort_field_map=None):
    # companies = MasterCompanies.objects.all()
    # Get filter parameters from request
    sortByVal = request.GET.get("sortByVal", None)
    orderByVal = request.GET.get("orderByVal", "DESC")
    event_parents = request.GET.get("event_parent", None)
    search_locations = request.GET.get("country", None)
    company_size = request.GET.get("company_size", None)
    followers = request.GET.get("followers", None)
    trigger = request.GET.get("trigger", None)
    country = request.GET.get("country", None)
    industry = request.GET.get("industry", None)
    organization = request.GET.get("organization_type", None)
    assignee = request.GET.get("assignee", None)
    category = request.GET.get("category", None)
    company_email = request.GET.get("company_email", None)

    # Set default sort field based on table type
    if not sortByVal:
        sortByVal = {
            "matching": "created_at",
            "events": "start_date",
            "funding": "date",
            "email": "last_sent_date",
        }.get(table, "created_at")

    # Determine sort direction
    if sort_field_map:
        sort_field = sort_field_map.get(sortByVal, "created_at")
    else:
        sort_field = sortByVal
    revert = orderByVal.upper() == "DESC"
    # Apply sorting
    if sort_field == "company__size":
        companies = apply_custom_sort(
            companies, "company__size", COMPANY_SIZE_ORDER, sort_desc=revert
        )
    elif sort_field == "size":
        companies = apply_custom_sort(
            companies, "size", COMPANY_SIZE_ORDER, sort_desc=revert
        )
    else:
        companies = companies.order_by(f"-{sort_field}" if revert else sort_field)

    # Apply filters
    if assignee:
        assignees = assignee.split(",")
        companies = companies.filter(company__assignee__name__in=assignees)

    if event_parents and event_parents.strip() != "null":
        event_parents = event_parents.split(",")
        companies = companies.filter(event_parent__in=event_parents)

    if search_locations and search_locations.strip() != "null":
        search_locations = search_locations.split(",")
        companies = companies.filter(company__country__in=search_locations)

    if company_size:
        company_sizes = company_size.split(",")
        companies = companies.filter(company__size__in=company_sizes)

    if country:
        countries = country.split(",")
        companies = companies.filter(company__country__in=countries)

    if category:
        categories = category.split(",")
        companies = companies.filter(company__category__in=categories)

    if industry:
        industries = industry.split(",")
        companies = companies.filter(company__industry__in=industries)

    if organization:
        organizations = organization.split(",")
        companies = companies.filter(company__organization_type__in=organizations)

    if followers:
        lst_followers = followers.split(",")
        follower_conditions = []

        for follower in lst_followers:
            if follower == "1000001+":
                follower_conditions.append(Q(company__followers__gte=1000001))
            else:
                follower_range = list(map(int, follower.split("-")))
                follower_conditions.append(
                    (
                        Q(company__followers__gte=int(follower_range[0]))
                        & Q(company__followers__lte=int(follower_range[1]))
                    )
                )

        follower_filters = reduce(operator.or_, follower_conditions)

        companies = companies.filter(follower_filters)

    if trigger:
        triggers = set(trigger.split(","))
        companies = companies.filter(
            reduce(operator.and_, [Q(trigger__contains=trig) for trig in triggers])
        )

    if company_email:
        
        company_email = company_email.split(",")
        print('Company email filter:', company_email)
        if len(company_email) == 1:
            company_email = company_email[0]
            if company_email == 'false':
                companies = companies.filter(
                    Q(company__lst_email_contact=[])
                    | Q(company__lst_email_contact__contains=["waiting"])
                )
            elif company_email == 'true':
                companies = companies.filter(
                    ~Q(company__lst_email_contact=[])
                    & ~Q(company__lst_email_contact__contains=["waiting"])
                )

    return companies


def getShowingColumnsCustom(
    source: Literal["Event", "Guests", "Job", "Funding", "Blacklist"],
    request,
):
    user_info = request.user
    userId = user_info.get("id", None)

    if source is None:
        return False

    name_order_map = {
        "Event": [
            "name",
            "event_url",
            "start_date",
            "companies",
            "guests",
            "event_parent",
            "location",
            "country",
        ],
        "Guests": [
            "name",
            "link",
            "event__name",
            "company__name",
            "company__country",
            "category",
            "email",
            "created_at",
        ],
        "Job": [
            "job_title",
            "category",
            "company",
            "location",
            "linkedin_url",
            "created_at",
            "label",
        ],
        "Funding": [
            "name",
            "link",
            "round",
            "funding_amount",
            "date",
            "category",
            "created_at",
        ],
        "Blacklist": [
            "name",
            "link",
            "industry",
            "headquarters",
            "category",
            "labels",
            "size",
            "organization_type",
            "short_description",
            "note_of_user",
            "created_at",
            "trigger_time",
        ],
    }

    name_order = name_order_map.get(source)
    if name_order is None:
        return False

    if userId is None:
        is_showing_columns = ShowingField.objects.filter(user_id=None).values()
    else:
        is_showing_columns = ShowingField.objects.filter(user_id=userId).values()

    showing_columns = []
    for column in is_showing_columns:
        if column["name_columns"] not in name_order:
            continue
        dict_col_value = {
            "name": column["name_columns"],
            "is_show": True,
            "can_arrange": column["can_arrange"] == "YES",
        }
        showing_columns.append(dict_col_value)

    order_index = {key: idx for idx, key in enumerate(name_order)}
    return sorted(
        showing_columns, key=lambda d: order_index.get(d["name"], float("inf"))
    )


def getFilterDataQueryForBlacklist(request, queryset, sort_field_map=None):
    """
    Apply sort + filter for queries directly on LinkedinCompany (e.g. Blacklist).
    Unlike getFilterDataQuery which assumes MasterCompanies with company__ prefix,
    this function filters on direct LinkedinCompany fields.
    """
    sortByVal = request.GET.get("sortByVal", None)
    orderByVal = request.GET.get("orderByVal", "DESC")
    country = request.GET.get("country", None)
    company_size = request.GET.get("company_size", None)
    followers = request.GET.get("followers", None)
    industry = request.GET.get("industry", None)
    organization = request.GET.get("organization_type", None)
    category = request.GET.get("category", None)

    if not sortByVal:
        sortByVal = "created_at"

    if sort_field_map:
        sort_field = sort_field_map.get(sortByVal, "created_at")
    else:
        sort_field = sortByVal

    revert = orderByVal.upper() == "DESC"

    if sort_field == "size":
        queryset = apply_custom_sort(
            queryset, "size", COMPANY_SIZE_ORDER, sort_desc=revert
        )
    else:
        queryset = queryset.order_by(f"-{sort_field}" if revert else sort_field)

    if country:
        queryset = queryset.filter(country__in=country.split(","))

    if company_size:
        queryset = queryset.filter(size__in=company_size.split(","))

    if industry:
        queryset = queryset.filter(industry__in=industry.split(","))

    if organization:
        queryset = queryset.filter(organization_type__in=organization.split(","))

    if category:
        queryset = queryset.filter(category__in=category.split(","))

    if followers:
        lst_followers = followers.split(",")
        follower_conditions = []
        for follower in lst_followers:
            if follower == "1000001+":
                follower_conditions.append(Q(followers__gte=1000001))
            else:
                follower_range = list(map(int, follower.split("-")))
                follower_conditions.append(
                    Q(followers__gte=follower_range[0])
                    & Q(followers__lte=follower_range[1])
                )
        queryset = queryset.filter(reduce(operator.or_, follower_conditions))

    return queryset
