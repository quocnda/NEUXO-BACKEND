from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from neuxo_backend.controller.watchlist_controller import (
    add_company_to_watchlist,
    add_guest_available_mention,
    add_new_guest_mention,
    check_had_create_manual_watchlist,
    check_had_other_watchlist,
    create_completion_history,
    delete_completions,
    edit_note_for_company,
    edit_subject_completions,
    get_all_completions,
    get_all_contact_for_company,
    get_all_guest_mention_for_company,
    get_all_mention,
    get_all_mentioned_company_per_user,
    get_all_notify_for_user,
    get_detail_info_for_company,
    get_list_icp,
    get_mention_per_people,
    get_watchlist_by_user_team,
    get_watchlist_data,
    getParamsVer2,
    new_notify_today,
    pin_watchlist_company,
    remove_company_from_watchlist,
    remove_guest_mention_for_company,
    save_history_gen,
    save_icp_for_company,
    seen_all_mention,
    update_company,
    update_contact,
)
from users.models import Users
from users.utils.utils import requireLogin, requireRoles


# OpenAPI parameters
PARAMETERS = [
    OpenApiParameter(
        name="start_date",
        required=False,
        type=str,
        examples=[OpenApiExample("2024-1-1 00:00:00", value="2024-1-1 00:00:00")],
    ),
    OpenApiParameter(
        name="end_date",
        required=False,
        type=str,
        examples=[OpenApiExample("2024-12-31 00:00:00", value="2024-12-31 00:00:00")],
    ),
    OpenApiParameter(
        name="page",
        required=False,
        type=int,
        examples=[OpenApiExample("1", value="1")],
    ),
    OpenApiParameter(
        name="limit",
        required=False,
        type=int,
        examples=[OpenApiExample("10", value="10")],
    ),
]

PARAMETERS_WATCHLIST = [
    OpenApiParameter(
        name="search_key", description="find keyword", required=False, type=str
    ),
    OpenApiParameter(
        name="start_date",
        required=False,
        type=str,
        examples=[OpenApiExample("2024-1-1 00:00:00", value="2024-1-1 00:00:00")],
    ),
    OpenApiParameter(
        name="end_date",
        required=False,
        type=str,
        examples=[OpenApiExample("2024-12-31 00:00:00", value="2024-12-31 00:00:00")],
    ),
    OpenApiParameter(
        name="page",
        required=False,
        type=int,
        examples=[OpenApiExample("1", value="1")],
    ),
    OpenApiParameter(
        name="limit",
        required=False,
        type=int,
        examples=[OpenApiExample("10", value="10")],
    ),
    OpenApiParameter(name="icp_id", required=False, type=str),
    OpenApiParameter(
        name="company_size", description="company_size", required=False, type=str
    ),
    OpenApiParameter(
        name="followers", description="followers", required=False, type=str
    ),
    OpenApiParameter(name="country", description="country", required=False, type=str),
]


# ---------------------------------------- addCompanyToWatchList ---------------------------------------- #


@extend_schema(
    parameters=[],
    request={
        "application/json": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Company id"}},
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_AddCompanyToWatchList",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def addCompanyToWatchList(request: HttpRequest) -> JsonResponse:
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    data = request.data
    companyId = data.get("id")
    user_id = request.user.get("id", None)

    if not companyId:
        return JsonResponse(
            {"message": "Company ids are required"}, status=HTTP_400_BAD_REQUEST
        )

    success, message = add_company_to_watchlist(user_id, companyId)
    if not success:
        return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


# ---------------------------------------- removeCompanyFromWatchList ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "string",
                },
            },
            "required": ["ids"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_RemoveCompanyFromWatchList",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def removeCompanyFromWatchList(request: HttpRequest) -> JsonResponse:
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    user_id = request.user.get("id", None)
    lst_id = request.data.get("ids", None)

    success, message = remove_company_from_watchlist(user_id, lst_id)
    if not success:
        return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


# ---------------------------------------- getWatchList ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS + PARAMETERS_WATCHLIST,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetWatchList",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getWatchList(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    paginator, data = get_watchlist_data(request)

    return JsonResponse(
        {
            "message": "Success",
            "pagination": paginator,
            "data": data,
        },
        status=HTTP_200_OK,
    )


# ---------------------------------------- getWatchListForAdmin ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS_WATCHLIST,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetWatchListForAdmin",
    tags=["Admin seen watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
@requireRoles(["Admin", "Super_Admin"])
def getWatchListForAdmin(request, id):
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    paginator, data = get_watchlist_data(request)

    return JsonResponse(
        {
            "message": "Success",
            "pagination": paginator,
            "data": data,
        },
        status=HTTP_200_OK,
    )


# ---------------------------------------- getAllWatchlistOfMemberForAdmin ---------------------------------------- #


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="search_key", description="find keyword", required=False, type=str
        ),
        OpenApiParameter(
            name="list_icp", description="list_icp", required=False, type=str
        ),
        OpenApiParameter(
            name="list_user_id", description="list_user_id", required=False, type=str
        ),
        OpenApiParameter(
            name="page",
            description="Page",
            required=False,
            type=int,
            examples=[OpenApiExample("1", value="1")],
        ),
        OpenApiParameter(
            name="limit",
            description="Page Size",
            required=False,
            type=int,
            examples=[OpenApiExample("10", value="10")],
        ),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetAllWatchlistOfMember",
    tags=["Admin seen watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
@requireRoles(["Admin", "Super_Admin"])
def getAllWatchlistOfMemberForAdmin(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    admin_id = request.user.get("id", None)
    search_key = request.GET.get("search_key", None)
    list_icp = request.GET.get("list_icp", None)
    listUserId = request.GET.get("list_user_id", None)
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 50))

    if listUserId:
        listUserId = listUserId.split(",")
        listUserId = [uuid_str.replace("-", "") for uuid_str in listUserId]
    else:
        listUserId = (
            Users.objects.filter(group="Var-meta")
            .exclude(id=admin_id)
            .values_list("id", flat=True)
        )

    if list_icp:
        list_icp = list_icp.split(",")

    data = get_watchlist_by_user_team(list_icp, search_key, listUserId)

    if len(data) == 0:
        return JsonResponse(
            {
                "message": "Success",
                "pagination": {
                    "page": 1,
                    "total_page": 1,
                    "total_item": 0,
                },
                "data": [],
            },
            status=HTTP_200_OK,
        )
    response_data = list(data)[page * limit - limit : page * limit]

    return JsonResponse(
        {
            "message": "Success",
            "pagination": {
                "page": page,
                "total_page": len(list(data)) // limit + 1,
                "total_item": len(list(data)),
            },
            "data": response_data,
        },
        status=HTTP_200_OK,
    )


# ---------------------------------------- Guest Management ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "linkedin_url": {"type": "string"},
                "twitter_url": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["linkedin_url"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="POST_AddGuestMentionForCompany",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def addNewGuestMentionForCompany(request, id):
    if request.method != "POST":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    userId = request.user.get("id", None)
    linkedin_url = request.data.get("linkedin_url", None)
    twitter_url = request.data.get("twitter_url", None)
    email = request.data.get("email", None)

    if not linkedin_url:
        return JsonResponse(
            {"message": "LinkedIn URL is required"}, status=HTTP_400_BAD_REQUEST
        )

    success, message, guest_id = add_new_guest_mention(
        userId, id, linkedin_url, twitter_url, email
    )

    if not success:
        return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": message}, status=HTTP_200_OK)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {"guest_id": {"type": "string"}},
            "required": ["guest_id"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="POST_addGuestAvailableMention",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def addGuestAvailableMention(request, id):
    if request.method != "POST":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    userId = request.user.get("id", None)
    guest_id = request.data.get("guest_id", None)

    if not guest_id:
        return JsonResponse(
            {"message": "Guest ID is required"}, status=HTTP_400_BAD_REQUEST
        )

    success, message = add_guest_available_mention(userId, id, guest_id)

    if not success:
        return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


@extend_schema(
    parameters=None,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetAllGuestMentionForCompany",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllGuestMentionForCompany(request, id):
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    userId = request.user.get("id", None)
    data = get_all_guest_mention_for_company(userId, id)

    return JsonResponse({"message": "Success", "data": list(data)}, status=HTTP_200_OK)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {"guest_id": {"type": "string"}},
            "required": ["guest_id"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_removeGuestMentionForCompany",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def removeGuestMentionForCompany(request, id):
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    user_id = request.user.get("id", None)
    guest_id = request.data.get("guest_id", None)

    if not id:
        return JsonResponse(
            {"message": "Company ids are required"}, status=HTTP_400_BAD_REQUEST
        )

    if not guest_id:
        return JsonResponse(
            {"message": "Guest ids are required"}, status=HTTP_400_BAD_REQUEST
        )

    success, message = remove_guest_mention_for_company(user_id, id, guest_id)

    if not success:
        return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


# ---------------------------------------- Mentions ---------------------------------------- #


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="offset",
            description="offset",
            required=False,
            type=int,
            examples=[OpenApiExample("0", value="0")],
        ),
        OpenApiParameter(
            name="limit",
            description="record Size",
            required=False,
            type=int,
            examples=[OpenApiExample("10", value="10")],
        ),
        OpenApiParameter(
            name="filter",
            description="filter",
            required=False,
            type=str,
            examples=[
                OpenApiExample(
                    "filter", value="NEWS,HIRING,EVENT,LINKEDIN,TWITTER,SUB_DOMAIN"
                )
            ],
        ),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetAllMentionedCompanyPerUser",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllMentionedCompanyPerUser(request, id):
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    userId = request.user.get("id", None)
    filter_type = request.GET.get("filter", None)
    offset = int(request.GET.get("offset", 0))
    limit = int(request.GET.get("limit", 10))

    pagination, data = get_all_mentioned_company_per_user(
        userId, id, filter_type, offset, limit
    )

    return JsonResponse(
        {
            "message": "Success",
            "pagination": pagination,
            "data": list(data),
        },
        status=HTTP_200_OK,
    )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="offset",
            description="offset",
            required=False,
            type=int,
            examples=[OpenApiExample("0", value="0")],
        ),
        OpenApiParameter(
            name="limit",
            description="record Size",
            required=False,
            type=int,
            examples=[OpenApiExample("10", value="10")],
        ),
        OpenApiParameter(
            name="filter",
            description="filter",
            required=False,
            type=str,
            examples=[
                OpenApiExample(
                    "filter", value="NEWS,HIRING,EVENT,LINKEDIN,TWITTER,SUB_DOMAIN"
                )
            ],
        ),
        OpenApiParameter(
            name="user_id",
            description="user_id",
            required=True,
            type=str,
            examples=[OpenApiExample("user_id", value="user_id")],
        ),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getAllMentionedCompanyPerAdmin",
    tags=["Admin seen watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
@requireRoles(["Admin", "Super_Admin"])
def getAllMentionedCompanyPerAdmin(request, id):
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    filter_type = request.GET.get("filter", None)
    user_id = request.GET.get("user_id", None)
    offset = int(request.GET.get("offset", 0))
    limit = int(request.GET.get("limit", 10))

    pagination, data = get_all_mentioned_company_per_user(
        user_id, id, filter_type, offset, limit
    )

    return JsonResponse(
        {
            "message": "Success",
            "pagination": pagination,
            "data": list(data),
        },
        status=HTTP_200_OK,
    )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="offset",
            description="offset",
            required=False,
            type=int,
            examples=[OpenApiExample("0", value="0")],
        ),
        OpenApiParameter(
            name="limit",
            description="record Size",
            required=False,
            type=int,
            examples=[OpenApiExample("10", value="10")],
        ),
        OpenApiParameter(
            name="range_time",
            description="range_time",
            required=False,
            type=str,
            examples=[OpenApiExample("filter", value="SEVEN_DAYS")],
        ),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetMentionPerPeople",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getMentionPerPeople(request, id):
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    userId = request.user.get("id", None)
    offset = int(request.GET.get("offset", 0))
    limit = int(request.GET.get("limit", 10))
    range_time = request.GET.get("range_time", None)

    pagination, data = get_mention_per_people(userId, id, offset, limit, range_time)

    return JsonResponse(
        {
            "message": "Success",
            "pagination": pagination,
            "data": list(data),
        },
        status=HTTP_200_OK,
    )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="offset",
            description="offset",
            required=False,
            type=int,
            examples=[OpenApiExample("0", value="0")],
        ),
        OpenApiParameter(
            name="limit",
            description="record Size",
            required=False,
            type=int,
            examples=[OpenApiExample("10", value="10")],
        ),
        OpenApiParameter(
            name="user_id", description="user_id", required=False, type=str
        ),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getMentionPerPeoplePerAdmin",
    tags=["Admin seen watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
@requireRoles(["Admin", "Super_Admin"])
def getMentionPerPeoplePerAdmin(request, id):
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    offset = int(request.GET.get("offset", 0))
    limit = int(request.GET.get("limit", 10))
    user_id = request.GET.get("user_id", None)

    pagination, data = get_mention_per_people(user_id, id, offset, limit, "SEVEN_DAYS")

    return JsonResponse(
        {
            "message": "Success",
            "pagination": pagination,
            "data": list(data),
        },
        status=HTTP_200_OK,
    )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="offset",
            description="offset",
            required=False,
            type=int,
            examples=[OpenApiExample("0", value="0")],
        ),
        OpenApiParameter(
            name="limit",
            description="record Size",
            required=False,
            type=int,
            examples=[OpenApiExample("10", value="10")],
        ),
        OpenApiParameter(
            name="filter",
            description="filter",
            required=False,
            type=str,
            examples=[
                OpenApiExample(
                    "filter", value="NEWS,HIRING,EVENT,LINKEDIN,TWITTER,SUB_DOMAIN"
                )
            ],
        ),
        OpenApiParameter(
            name="type",
            description="type",
            required=False,
            type=str,
            examples=[OpenApiExample("type", value="contact")],
        ),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetAllMention",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllMention(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    userId = request.user.get("id", None)
    filter_type = request.GET.get("filter", None)
    offset = int(request.GET.get("offset", 0))
    limit = int(request.GET.get("limit", 10))
    mention_type = request.GET.get("type", None)

    pagination, data = get_all_mention(userId, filter_type, offset, limit, mention_type)

    return JsonResponse(
        {
            "message": "Success",
            "pagination": pagination,
            "data": list(data),
        },
        status=HTTP_200_OK,
    )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "example": "contact"},
                "filter": {
                    "type": "string",
                    "example": "NEWS,HIRING,EVENT,LINKEDIN,TWITTER,SUB_DOMAIN",
                },
            },
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="POST_SeenAllMention",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def seenAllMention(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    userId = request.user.get("id", None)
    mention_type = request.data.get("type", None)
    filter_type = request.data.get("filter", None)

    seen_all_mention(userId, mention_type, filter_type)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


# ---------------------------------------- Contacts ---------------------------------------- #


@extend_schema(
    parameters=None,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetAllContactForCompany",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllContactForCompany(request, id):
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    userId = request.user.get("id", None)
    data = get_all_contact_for_company(userId, id)

    return JsonResponse({"message": "Success", "data": list(data)}, status=HTTP_200_OK)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="user_id", description="user_id", required=False, type=str
        )
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getAllContactForCompanyPerAdmin",
    tags=["Admin seen watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
@requireRoles(["Admin", "Super_Admin"])
def getAllContactForCompanyPerAdmin(request, id):
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    user_id = request.GET.get("user_id", None)
    data = get_all_contact_for_company(user_id, id)

    return JsonResponse({"message": "Success", "data": list(data)}, status=HTTP_200_OK)


# ---------------------------------------- Note and ICP ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company_id": {"type": "string"},
                    "note": {"type": "string"},
                },
            },
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_editNoteForCompany",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def editNoteForCompany(request: HttpRequest) -> JsonResponse:
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    user_id = request.user.get("id", None)
    data = request.data

    if data == {}:
        return JsonResponse({"message": "Data is empty"}, status=HTTP_400_BAD_REQUEST)
    if len(data) == 0:
        return JsonResponse({"message": "Data is empty"}, status=HTTP_400_BAD_REQUEST)
    if "company_id" not in data[0]:
        return JsonResponse(
            {"message": "Company_id is required"}, status=HTTP_400_BAD_REQUEST
        )
    if "note" not in data[0]:
        return JsonResponse(
            {"message": "Note is required"}, status=HTTP_400_BAD_REQUEST
        )

    edit_note_for_company(user_id, data)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


@extend_schema(
    parameters=None,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getListICP",
    tags=["ICP"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getListICP(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    list_icp = get_list_icp()

    return JsonResponse({"message": "Success", "data": list_icp}, status=HTTP_200_OK)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "icp_id": {"type": "string"},
            },
            "required": ["company_id", "icp_id"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_saveICP",
    tags=["ICP"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def saveICP(request: HttpRequest) -> JsonResponse:
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    user_id = request.user.get("id", None)
    data = request.data

    if data == {}:
        return JsonResponse({"message": "Data is empty"}, status=HTTP_400_BAD_REQUEST)

    company_id = data.get("company_id", None)
    icp_id = data.get("icp_id", None)

    if not company_id or not icp_id:
        return JsonResponse(
            {"message": "Company_id and ICP_id are required"},
            status=HTTP_400_BAD_REQUEST,
        )

    success, message = save_icp_for_company(user_id, company_id, icp_id)

    if not success:
        return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


# ---------------------------------------- PIN Watchlist ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {"company_id": {"type": "string"}},
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_PINWatchlist",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def PINWatchlist(request: HttpRequest) -> JsonResponse:
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    user_id = request.user.get("id", None)
    data = request.data

    if data == {}:
        return JsonResponse({"message": "Data is empty"}, status=HTTP_400_BAD_REQUEST)

    company_id = data.get("company_id", None)

    if not company_id:
        return JsonResponse(
            {"message": "Company_id are required"}, status=HTTP_400_BAD_REQUEST
        )

    success, message = pin_watchlist_company(user_id, company_id)

    if not success:
        return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": message}, status=HTTP_200_OK)


# ---------------------------------------- Company/Contact Updates ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "twitter_url": {"type": "string"},
                "website": {"type": "string"},
                "country": {"type": "string"},
            },
            "required": ["twitter_url", "website"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_updateCompany",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def updateCompany(request, id):
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    data = request.data
    twitter_url = data.get("twitter_url", None)
    website = data.get("website", None)
    country = data.get("country", None)

    success, message = update_company(id, twitter_url, website, country)

    if not success:
        return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "twitter_url": {"type": "string"},
                "linkedin_url": {"type": "string"},
            },
            "required": ["twitter_url", "linkedin_url"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_updateContact",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def updateContact(request, id):
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    data = request.data
    linkedin_url = data.get("linkedin_url", None)
    twitter_url = data.get("twitter_url", None)

    success, message = update_contact(id, linkedin_url, twitter_url)

    if not success:
        return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


# ---------------------------------------- Notifications ---------------------------------------- #


@extend_schema(
    parameters=None,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_newNotifyToday",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def newNotifyToday(request, id):
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    data = new_notify_today(id)

    return JsonResponse({"message": "Success", "data": data}, status=HTTP_200_OK)


@extend_schema(
    parameters=None,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getAllNotifyForUser",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllNotifyForUser(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    userId = request.user.get("id", None)
    new_notify = get_all_notify_for_user(userId)

    return JsonResponse(
        {"message": "Success", "new_notify": new_notify}, status=HTTP_200_OK
    )


# ---------------------------------------- Detail Info ---------------------------------------- #


@extend_schema(
    parameters=None,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getDetailInfoForCompany",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getDetailInfoForCompany(request, id):
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    contact_data = get_detail_info_for_company(id)

    if not contact_data:
        return JsonResponse(
            {"message": "Company not found"}, status=HTTP_400_BAD_REQUEST
        )

    return JsonResponse(
        {"message": "Success", "data": contact_data}, status=HTTP_200_OK
    )


# ---------------------------------------- Validation ---------------------------------------- #


@api_view(["POST"])
@requireLogin
def checkHadOtherWatchlist(request: HttpRequest) -> JsonResponse:
    try:
        if request.method != "POST":
            return JsonResponse(
                {"message": "Invalid request method"},
                status=HTTP_405_METHOD_NOT_ALLOWED,
            )

        current_user = request.user
        watchlist_info = request.data.get("watchlist_info")

        if not watchlist_info:
            return JsonResponse(
                {"message": "Watchlist info is required"}, status=HTTP_400_BAD_REQUEST
            )

        data = check_had_other_watchlist(current_user.get("id"), watchlist_info)

        return JsonResponse({"message": "Success", "data": data}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse(
            {"message": "An error occurred", "error": str(e)},
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@requireLogin
def checkHadCreateManualWatchlist(request: HttpRequest) -> JsonResponse:
    try:
        if request.method != "POST":
            return JsonResponse(
                {"message": "Invalid request method"},
                status=HTTP_405_METHOD_NOT_ALLOWED,
            )

        current_user = request.user
        current_user_id = current_user.get("id")
        company_linkedin = request.data.get("company_linkedin")

        if not company_linkedin:
            return JsonResponse(
                {"message": "company_linkedin info is required"},
                status=HTTP_400_BAD_REQUEST,
            )

        data = check_had_create_manual_watchlist(current_user_id, company_linkedin)

        if "error" in data:
            return JsonResponse({"message": data["error"]}, status=HTTP_400_BAD_REQUEST)

        return JsonResponse({"message": "Success", "data": data}, status=HTTP_200_OK)
    except Exception as e:
        print("[watchlist] check_had_create_manual_watchlist error:", str(e))
        return JsonResponse(
            {"message": "An error occurred", "error": str(e)},
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ---------------------------------------- AI Completions History ---------------------------------------- #


@extend_schema(
    parameters=None,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getIDCompletionsCompany",
    tags=["Watchlist"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getIDCompletionsForCompany(request: HttpRequest, id) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    user_id = request.user.get("id", None)
    history_id = create_completion_history(user_id, "company_id", id)

    if not history_id:
        return JsonResponse({"message": "User not found"}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": "Success", "data": history_id}, status=HTTP_200_OK)


@extend_schema(
    parameters=None,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getIDCompletionsContacts",
    tags=["Watchlist"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getIDCompletionsForContacts(request: HttpRequest, id) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    user_id = request.user.get("id", None)
    history_id = create_completion_history(user_id, "person_contact_id", id)

    if not history_id:
        return JsonResponse({"message": "User not found"}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": "Success", "data": history_id}, status=HTTP_200_OK)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "example": "gpt-4o",
                    "description": "AI model used",
                },
                "completion_id": {"type": "string"},
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {
                                "type": "string",
                                "example": "user",
                                "description": "Message role",
                            },
                            "content": {
                                "type": "string",
                                "example": "NEWS (in chronological order): ...",
                                "description": "Message content",
                            },
                        },
                    },
                },
            },
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="POST_saveHistoryGen",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def saveHistoryGen(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    user_id = request.user.get("id", None)
    data = request.data
    completion_id = data.get("completion_id", None)

    if not completion_id:
        return JsonResponse(
            {"message": "completion_id is required"}, status=HTTP_400_BAD_REQUEST
        )

    messages = data.get("messages", None)

    success = save_history_gen(user_id, completion_id, messages)

    if not success:
        return JsonResponse({"message": "User not found"}, status=HTTP_400_BAD_REQUEST)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getAllCompletionsForContact",
    tags=["Watchlist"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllCompletionsForContact(request: HttpRequest, id) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    user_id = request.user.get("id", None)
    _, _, page, limit = getParamsVer2(request)

    pagination, data = get_all_completions(user_id, "person_contact_id", id, page, limit)

    return JsonResponse(
        {
            "message": "Success",
            "pagination": pagination,
            "data": data,
        },
        status=HTTP_200_OK,
        safe=False,
    )


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getAllCompletionsForCompany",
    tags=["Watchlist"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllCompletionsForCompany(request: HttpRequest, id) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    user_id = request.user.get("id", None)
    _, _, page, limit = getParamsVer2(request)

    pagination, data = get_all_completions(user_id, "company_id", id, page, limit)

    return JsonResponse(
        {
            "message": "Success",
            "pagination": pagination,
            "data": data,
        },
        status=HTTP_200_OK,
        safe=False,
    )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "completion_id": {"type": "string"},
                "subject": {"type": "string"},
            },
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="POST_editSubjectCompletions",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def editSubjectCompletions(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    data = request.data
    completion_id = data.get("completion_id", None)
    subject = data.get("subject", None)

    edit_subject_completions(completion_id, subject)

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {"completion_id": {"type": "string"}},
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_deleteCompletions",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def deleteCompletions(request: HttpRequest) -> JsonResponse:
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    data = request.data
    completion_id = data.get("completion_id", None)

    success = delete_completions(completion_id)

    if not success:
        return JsonResponse(
            {"message": "Completion not found"}, status=HTTP_400_BAD_REQUEST
        )

    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)
