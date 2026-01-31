import hashlib
import os
import re
from datetime import datetime, timedelta
from functools import wraps

import jwt
from django.http import JsonResponse
from dotenv import load_dotenv
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED

from user.models import Users
from user.serializers import UserSerializers

load_dotenv()
TOKEN_TTL_MINUTES = int(os.getenv("TOKEN_TTL_MINUTES", "60"))


def encodeToSha256(password):
    return hashlib.sha256(password.encode()).hexdigest()


def checkPassword(hashed_password, password):
    return hashlib.sha256(password.encode()).hexdigest() == hashed_password


def generateBearerToken(user_id, user_name, permissions: str = ""):
    exp = datetime.now() + timedelta(minutes=TOKEN_TTL_MINUTES)
    user_id_str = str(user_id)
    user_name_str = str(user_name) if user_name else ""

    token_payload = {
        "id": user_id_str,
        "user_name": user_name_str,
        "permissions": permissions,
        "type": "ACCESS_TOKEN",
        "exp": int(exp.timestamp()),  # Convert exp to a Unix timestamp
    }
    access_token = jwt.encode(
        token_payload, os.getenv("SECRET_KEY", "secret"), algorithm="HS256"
    )
    return str(access_token)


def generateBearerTokenWithTime(dataInput, ttlTime):
    exp = datetime.utcnow() + timedelta(minutes=ttlTime)
    dataInput["exp"] = int(exp.timestamp())
    access_token = jwt.encode(
        dataInput, os.getenv("SECRET_KEY", "secret"), algorithm="HS256"
    )
    return str(access_token)


def validateToken(token):
    try:
        payload = jwt.decode(
            token, os.getenv("SECRET_KEY", "secret"), algorithms=["HS256"]
        )
        return payload
    except jwt.exceptions.ExpiredSignatureError:
        raise Exception("Token expire time")


def validate_email(email):
    if not email:
        return False

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def handleError(error):
    return JsonResponse(
        {
            "success": False,
            "error": str(error),
        },
        status=HTTP_400_BAD_REQUEST,
    )


def handleSuccess(message, data, status):
    return JsonResponse({"message": message, "data": data}, status=status)


def requireLogin(view_func):
    def wrapper(request, *args, **kwargs):
        bearerToken = request.headers.get("Authorization")
        if not bearerToken or bearerToken is None:
            return handleError("No token provided")
        token = bearerToken[7:]

        try:
            payload = validateToken(token)
            temp = Users.objects.get(pk=payload["id"])
            permission = payload["permissions"]
            serializer = UserSerializers(temp)
            request.user = dict(serializer.data)
            request.user["permission"] = permission

            if payload["type"] != "ACCESS_TOKEN":
                return JsonResponse(
                    {"success": False, "error": str("Invalid token")},
                    status=HTTP_401_UNAUTHORIZED,
                )
        except jwt.exceptions.InvalidTokenError:
            return JsonResponse(
                {"success": False, "error": str("Invalid token")},
                status=HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            return JsonResponse(
                {"success": False, "error": str("Token expire time")},
                status=HTTP_401_UNAUTHORIZED,
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def requireRoles(required_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user_role = request.user.get("role", None)
            if user_role in required_roles:
                return view_func(request, *args, **kwargs)
            return JsonResponse(
                {"message": "Access denied. You do not have the required role."},
                status=403,
            )

        return _wrapped_view

    return decorator


def requireTokenRefresh(view_func):
    def wrapper(request, *args, **kwargs):
        bearerToken = request.headers.get("Authorization")
        if not bearerToken or bearerToken is None:
            return handleError("No token provided")
        token = bearerToken[7:]

        try:
            payload = validateToken(token)
            temp = Users.objects.get(pk=payload["userId"])
            serializer = UserSerializers(temp)
            request.user = dict(serializer.data)
            if payload["type"] != "REFRESH_TOKEN":
                return JsonResponse(
                    {"success": False, "error": str("Invalid token")},
                    status=HTTP_401_UNAUTHORIZED,
                )
        except jwt.exceptions.InvalidTokenError:
            return JsonResponse(
                {"success": False, "error": str("Invalid token")},
                status=HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            return JsonResponse(
                {"success": False, "error": str("Token expire time")},
                status=HTTP_401_UNAUTHORIZED,
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def validatePassword(password):
    if not password:
        return "Please provide a password"

    if len(password) < 8:
        return "Password must contain at least 8 characters"

    if not any(char.isupper() for char in password):
        return "Password must have at least ONE uppercase character"

    if not any(char.isdigit() for char in password):
        return "Password must have at least ONE number"

    if not re.search("[~`!@#\$%\^&\*\(\)_\+\{\[\}\]\|\\:;\"'<,>\.?/]", password):
        return "Password must have at least ONE special character"


def validateEmail(email):
    if (
        not re.match("[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email)
        or len(email) > 100
    ):
        return "Please use a valid email address"


def showingfield_data(user_id):
    data = [
        {
            "name_columns": "organization_type",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 12,
            "user_id": user_id,
        },
        {
            "name_columns": "guests",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "company",
            "is_show": "YES",
            "can_arrange": "YES",
            "order_by": 1,
            "user_id": user_id,
        },
        {
            "name_columns": "link",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 2,
            "user_id": user_id,
        },
        {
            "name_columns": "event__name",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "industry",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 13,
            "user_id": user_id,
        },
        {
            "name_columns": "label",
            "is_show": "YES",
            "can_arrange": "YES",
            "order_by": 3,
            "user_id": user_id,
        },
        {
            "name_columns": "score",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 14,
            "user_id": user_id,
        },
        {
            "name_columns": "event_url",
            "is_show": "NO",
            "can_arrange": "NO",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "linkedin_url",
            "is_show": "NO",
            "can_arrange": "NO",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "twitter_url",
            "is_show": "NO",
            "can_arrange": "NO",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "headquarters",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 9,
            "user_id": user_id,
        },
        {
            "name_columns": "trigger",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 4,
            "user_id": user_id,
        },
        {
            "name_columns": "website",
            "is_show": "NO",
            "can_arrange": "NO",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "country",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 10,
            "user_id": user_id,
        },
        {
            "name_columns": "date",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "contacts",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 6,
            "user_id": user_id,
        },
        {
            "name_columns": "email",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "company__name",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "company__country",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "start_date",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "job_title",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "note",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "funding_amount",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "trigger_time",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": 5,
            "user_id": user_id,
        },
        {
            "name_columns": "round",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "followers",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 8,
            "user_id": user_id,
        },
        {
            "name_columns": "assignee",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 15,
            "user_id": user_id,
        },
        {
            "name_columns": "name",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "action",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 16,
            "user_id": user_id,
        },
        {
            "name_columns": "project_url",
            "is_show": "NO",
            "can_arrange": "NO",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "company_size",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 7,
            "user_id": user_id,
        },
        {
            "name_columns": "short_description",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 11,
            "user_id": user_id,
        },
        {
            "name_columns": "event_parent",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "created_at",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "companies",
            "is_show": "NO",
            "can_arrange": "NO",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "location",
            "is_show": "NO",
            "can_arrange": "YES",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "note_of_user",
            "is_show": "NO",
            "can_arrange": "NO",
            "order_by": None,
            "user_id": user_id,
        },
        {
            "name_columns": "category",
            "is_show": "YES",
            "can_arrange": "NO",
            "order_by": 17,
            "user_id": user_id,
        },
    ]
    return data
