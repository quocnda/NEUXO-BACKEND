import os
from types import SimpleNamespace

import requests
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_405_METHOD_NOT_ALLOWED,
)
from unidecode import unidecode

from neuxo_backend.models import Document, MailAppAccount, ShowingField
from users.models import Users
from users.serializers import (
    SignIn400ResponseSerializer,
    SignIn401ResponseSerializer,
    SignIn500ResponseSerializer,
    SignInResponseSerializer,
    SignInSerializer,
    changePasswordResponseSerializer,
    changePasswordSerializer,
    refreshTokenUserResponseSerializer,
    userInfoResponseSerializer,
    userLogoutResponseSerializer,
)

# from user.utils.redis_utils import addingTokenToRefresh, deleteTokenToRefresh
from users.utils.utils import (
    checkPassword,
    encodeToSha256,
    generateBearerToken,
    generateBearerTokenWithTime,
    requireLogin,
    requireRoles,
    requireTokenRefresh,
    showingfield_data,
    validatePassword,
)

REFRESH_TOKEN_TTL_MINUTES = int(os.getenv("REFRESH_TOKEN_TTL_MINUTES"))


@extend_schema(
    request=SignInSerializer,
    responses={
        200: SignInResponseSerializer,
        400: SignIn400ResponseSerializer,
        401: SignIn401ResponseSerializer,
        500: SignIn500ResponseSerializer,
    },
    auth=None,
    operation_id="signIn",
    tags=["User"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
def signIn(request):
    if request.method == "POST":
        try:
            print("Ready for sign in")
            serializer = SignInSerializer(data=request.data)
            if not serializer.is_valid():
                return JsonResponse(serializer.errors, status=HTTP_400_BAD_REQUEST)
            print("Serializer is valid")
            username = serializer.validated_data.get("username")
            password = serializer.validated_data.get("password")

            checkPassValidate = validatePassword(password)
            if checkPassValidate is not None:
                return JsonResponse(
                    {"message": checkPassValidate}, status=HTTP_400_BAD_REQUEST
                )

            myUser = Users.objects.filter(
                Q(user_name=username) | Q(email=username)
            ).first()
            if not myUser:
                return JsonResponse(
                    {"message": "User Name or Password is incorrect"},
                    status=HTTP_401_UNAUTHORIZED,
                )

            if not checkPassword(myUser.pwd_sha256, password):
                return JsonResponse(
                    {"message": "User Name or password is incorrect"},
                    status=HTTP_400_BAD_REQUEST,
                )

            permissions = None
            token = generateBearerToken(myUser.id, myUser.user_name, permissions)
            refresh_token = generateBearerTokenWithTime(
                {"userId": myUser.id, "type": "REFRESH_TOKEN"},
                REFRESH_TOKEN_TTL_MINUTES,
            )
            # addingTokenToRefresh(myUser, token, refresh_token)

            dataOutput = {
                "id": myUser.id,
                "email": myUser.email,
                "user_name": myUser.user_name,
                "role": myUser.role,
            }
            data = {
                "message": "Sign-in successfully",
                "data": {
                    "access_token": token,
                    "refresh_token": refresh_token,
                    "permissions": permissions,
                    "user": dataOutput,
                },
            }
            return JsonResponse(data, status=HTTP_200_OK)
        except Exception:
            import traceback

            traceback.print_exc()
            return JsonResponse(
                {"message": "Sign-in unsuccessfully."}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only POST requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "first_name": {
                    "type": "string",
                },
                "last_name": {
                    "type": "string",
                },
                "password": {
                    "type": "string",
                },
                "phone_number": {
                    "type": "string",
                },
                "email": {
                    "type": "string",
                },
                "role": {"type": "string", "enum": ["Admin", "User"]},
            },
            "required": ["first_name", "last_name", "password", "email", "role"],
        }
    },
    responses=None,
    auth=None,
    operation_id="createUser",
    tags=["Admin"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
@requireRoles(["Admin", "Super_Admin"])
def createUser(request):
    if request.method == "POST":
        try:
            first_name = request.data.get("first_name", None)
            last_name = request.data.get("last_name", None)
            password = request.data.get("password")
            phone_number = request.data.get("phone_number", None)
            email = request.data.get("email")
            role = request.data.get("role")
            if not first_name or not last_name or not password or not email or not role:
                return JsonResponse(
                    {"message": "Please fill in all fields"},
                    status=HTTP_400_BAD_REQUEST,
                )

            if role not in ["Admin", "User"]:
                return JsonResponse(
                    {"message": "Role is invalid"}, status=HTTP_400_BAD_REQUEST
                )

            checkPassValidate = validatePassword(password)
            if checkPassValidate is not None:
                return JsonResponse(
                    {"message": checkPassValidate}, status=HTTP_400_BAD_REQUEST
                )
            username = unidecode(f"{first_name}{last_name}")
            myUser = Users.objects.filter(user_name=username).first()
            if myUser:
                return JsonResponse(
                    {"message": "User Name is already exist"},
                    status=HTTP_400_BAD_REQUEST,
                )
            myUser = Users.objects.filter(email=email).first()
            if myUser:
                return JsonResponse(
                    {"message": "Email is already exist"}, status=HTTP_400_BAD_REQUEST
                )

            pwd_sha256 = encodeToSha256(password)
            with transaction.atomic():
                myUser = Users(
                    first_name=first_name,
                    last_name=last_name,
                    user_name=username,
                    pwd_sha256=pwd_sha256,
                    email=email,
                    role=role,
                    account_status="VERIFIED",
                    phone_number=phone_number,
                )

                myUser.save()
                data_insert = showingfield_data(myUser.id)
                ShowingField.objects.bulk_create(
                    [ShowingField(**item) for item in data_insert]
                )

            return JsonResponse({"message": "Create successfully"}, status=HTTP_200_OK)
        except Exception:
            return JsonResponse(
                {"message": "Create unsuccessfully."}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only POST requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request=None,
    responses={HTTP_200_OK: userLogoutResponseSerializer},
    auth=None,
    operation_id="userLogout",
    tags=["User"],
    operation=None,
)
@api_view(["POST"])
@csrf_exempt
@requireLogin
def signOut(request):
    if request.method == "POST":
        # try:
        userPayload = SimpleNamespace(**request.user)
        userId = userPayload.id
        user_info = Users.objects.filter(id=userId).first()
        if user_info is None:
            return JsonResponse(
                {"message": "User does not exist on the system."},
                status=HTTP_400_BAD_REQUEST,
            )
        # deleteTokenToRefresh(user_info)
        return JsonResponse(
            {"message": "Log-out successfully."},
            status=HTTP_200_OK,
        )
    # except:
    #     return JsonResponse({"message": "Log-out unsuccessfully."}, status=HTTP_400_BAD_REQUEST)
    return JsonResponse(
        {"message": "Invalid request method. Only POST requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request=None,
    responses={HTTP_200_OK: refreshTokenUserResponseSerializer},
    auth=None,
    operation_id="refreshTokenUser",
    tags=["User"],
    operation=None,
)
@api_view(["GET"])
@csrf_exempt
@requireTokenRefresh
def refreshTokenUser(request):
    if request.method == "GET":
        try:
            userPayload = SimpleNamespace(**request.user)
            userId = userPayload.id
            user_info = Users.objects.filter(id=userId).first()

            if user_info is None:
                return JsonResponse(
                    {"message": "User does not exist on the system."},
                    status=HTTP_400_BAD_REQUEST,
                )

            permissions = None

            token = generateBearerToken(user_info.id, user_info.user_name, permissions)
            return JsonResponse(
                {
                    "message": "Refresh successfully.",
                    "data": {
                        "access_token": token,
                        "refresh_token": request.headers.get("Authorization"),
                        "permissions": permissions,
                    },
                },
                status=HTTP_200_OK,
            )
        except Exception:
            return JsonResponse(
                {"message": "Refresh unsuccessfully."}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only POST requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request=None,
    responses={200: userInfoResponseSerializer},
    auth=None,
    operation_id="userInfo",
    tags=["User"],
    operation=None,
)
@api_view(["GET"])
@csrf_exempt
@requireLogin
def userInfo(request):
    if request.method == "GET":
        try:
            userInfo = request.user
            temp = SimpleNamespace(**userInfo)
            permissions = str(temp.permission)
            usernameCheck = (
                Users.objects.filter(id=temp.id)
                .values(
                    "id",
                    "email",
                    "user_name",
                    "first_name",
                    "last_name",
                    "phone_number",
                    "location",
                    "pwd_sha256",
                    "role",
                )
                .first()
            )
            has_mail_app_pass = False
            user_mail_infor = MailAppAccount.objects.filter(user__id=temp.id).first()
            if user_mail_infor:
                email_infor = {"email": user_mail_infor.email}
                has_mail_app_pass = True
            else:
                email_infor = {"email": usernameCheck["email"]}
            if usernameCheck is None:
                return JsonResponse(
                    {"message": "Username not found"}, status=HTTP_400_BAD_REQUEST
                )

            dataOutput = {
                "id": usernameCheck["id"],
                "email": usernameCheck["email"],
                "user_name": usernameCheck["user_name"],
                "permissions": permissions,
                "first_name": usernameCheck["first_name"],
                "role": usernameCheck["role"],
                "last_name": usernameCheck["last_name"],
                "phone_number": usernameCheck["phone_number"],
                "location": usernameCheck["location"],
                "has_password": True if usernameCheck["pwd_sha256"] else False,
                "has_mail_app_pass": has_mail_app_pass,
                "avatar": None,
                "email_tracker": email_infor,
            }
            return JsonResponse(
                {"message": "Get user information successfully", "data": dataOutput},
                status=HTTP_200_OK,
            )
        except Exception:
            import traceback

            traceback.print_exc()
            return JsonResponse(
                {"message": "Get user information Unsuccessfully"},
                status=HTTP_400_BAD_REQUEST,
            )
    return JsonResponse(
        {"message": "Invalid request method. Only POST requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request=None,
    responses={HTTP_200_OK},
    auth=None,
    operation_id="GET_list_user",
    tags=["Admin"],
    operation=None,
)
@api_view(["GET"])
@csrf_exempt
@requireLogin
@requireRoles(["Admin", "Super_Admin"])
def getListUser(request):
    if request.method == "GET":
        try:
            list_user = Users.objects.all().values(
                "id", "user_name", "role", "email", "created_at"
            )
            data = list(list_user)
            return JsonResponse(
                {"message": "Get list user successfully", "data": data},
                status=HTTP_200_OK,
            )
        except Exception:
            return JsonResponse(
                {"message": "Get list user Unsuccessfully"}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only GET requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request=changePasswordSerializer,
    responses={200: changePasswordResponseSerializer},
    auth=None,
    operation_id="POST_changePassword",
    tags=["User"],
    operation=None,
)
@api_view(["POST"])
@csrf_exempt
@requireLogin
def changePassword(request):
    if request.method == "POST":
        try:
            user_info = request.user
            user_id = user_info.get("id", None)

            serializer = changePasswordSerializer(data=request.data)
            if not serializer.is_valid():
                return JsonResponse(serializer.errors, status=HTTP_400_BAD_REQUEST)

            newPassword = serializer.validated_data.get("newPassword")
            oldPassword = serializer.validated_data.get("oldPassword")

            myUser = Users.objects.filter(id=user_id).first()

            old_pwd_sha256 = encodeToSha256(oldPassword)

            if old_pwd_sha256 != myUser.pwd_sha256:
                return JsonResponse(
                    {"message": "Old password is incorrect"},
                    status=HTTP_400_BAD_REQUEST,
                )

            checkPassValidate = validatePassword(newPassword)
            if checkPassValidate is not None:
                return JsonResponse(
                    {"message": checkPassValidate}, status=HTTP_400_BAD_REQUEST
                )
            new_pwd_sha256 = encodeToSha256(newPassword)
            myUser.pwd_sha256 = new_pwd_sha256
            myUser.save()

            permissions = None
            token = generateBearerToken(myUser.id, myUser.user_name, permissions)
            refresh_token = generateBearerTokenWithTime(
                {"userId": myUser.id, "type": "REFRESH_TOKEN"},
                REFRESH_TOKEN_TTL_MINUTES,
            )
            # addingTokenToRefresh(myUser, token, refresh_token)

            dataOutput = {
                "id": myUser.id,
                "email": myUser.email,
                "user_name": myUser.user_name,
            }
            data = {
                "message": "Change password successfully",
                "data": {
                    "access_token": token,
                    "refresh_token": refresh_token,
                    "permissions": permissions,
                    "user": dataOutput,
                },
            }
            return JsonResponse(data, status=HTTP_200_OK)
        except Exception:
            return JsonResponse(
                {"message": "Change password unsuccessfully."},
                status=HTTP_400_BAD_REQUEST,
            )
    return JsonResponse(
        {"message": "Invalid request method. Only POST requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "new_password": {
                    "type": "string",
                },
            },
            "required": ["new_password"],
        },
    },
    responses={HTTP_200_OK},
    auth=None,
    operation_id="POST_setPassword",
    tags=["User"],
    operation=None,
)
@api_view(["POST"])
@csrf_exempt
@requireLogin
def setPassword(request):
    if request.method == "POST":
        try:
            user_info = request.user
            user_id = user_info.get("id", None)

            newPassword = request.data.get("new_password")

            myUser = Users.objects.filter(id=user_id).first()

            if myUser is None:
                return JsonResponse(
                    {"message": "User not found"}, status=HTTP_400_BAD_REQUEST
                )

            if myUser.pwd_sha256:
                return JsonResponse(
                    {"message": "Password already set"}, status=HTTP_400_BAD_REQUEST
                )

            checkPassValidate = validatePassword(newPassword)

            if checkPassValidate is not None:
                return JsonResponse(
                    {"message": checkPassValidate}, status=HTTP_400_BAD_REQUEST
                )
            new_pwd_sha256 = encodeToSha256(newPassword)
            myUser.pwd_sha256 = new_pwd_sha256
            myUser.save()

            permissions = None
            token = generateBearerToken(myUser.id, myUser.user_name, permissions)
            refresh_token = generateBearerTokenWithTime(
                {"userId": myUser.id, "type": "REFRESH_TOKEN"},
                REFRESH_TOKEN_TTL_MINUTES,
            )
            # addingTokenToRefresh(myUser, token, refresh_token)

            dataOutput = {
                "id": myUser.id,
                "email": myUser.email,
                "user_name": myUser.user_name,
            }
            data = {
                "message": "Set password successfully",
                "data": {
                    "access_token": token,
                    "refresh_token": refresh_token,
                    "permissions": permissions,
                    "user": dataOutput,
                },
            }
            return JsonResponse(data, status=HTTP_200_OK)
        except Exception:
            return JsonResponse(
                {"message": "Set password unsuccessfully."}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only POST requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request=None,
    responses={HTTP_200_OK},
    auth=None,
    operation_id="DELETE_deleteUser",
    tags=["Admin"],
    operation=None,
)
@api_view(["DELETE"])
@csrf_exempt
@requireLogin
@requireRoles(["Admin", "Super_Admin"])
def deleteUser(request, id):
    if request.method == "DELETE":
        try:
            user_info = request.user
            user_id = user_info.get("id", None)
            user_role = user_info.get("role", None)
            if user_id == id:
                return JsonResponse(
                    {"message": "can not delete yourself"}, status=HTTP_400_BAD_REQUEST
                )
            user = Users.objects.filter(id=id).first()
            if user is None:
                return JsonResponse(
                    {"message": "User not found"}, status=HTTP_400_BAD_REQUEST
                )

            if user_role == "Super_Admin":
                user.delete()
                return JsonResponse(
                    {"message": "Delete user successfully"}, status=HTTP_200_OK
                )

            if user_role == "Admin":
                if user.role != "User":
                    return JsonResponse(
                        {"message": "You don't have permission"},
                        status=HTTP_400_BAD_REQUEST,
                    )
                user.delete()
                return JsonResponse(
                    {"message": "Delete user successfully"}, status=HTTP_200_OK
                )
            return JsonResponse(
                {"message": "Delete user unsuccessfully"}, status=HTTP_400_BAD_REQUEST
            )
        except Exception:
            return JsonResponse(
                {"message": "Delete user unsuccessfully"}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only DELETE requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                },
                "password": {
                    "type": "string",
                },
                "email": {
                    "type": "string",
                },
                "role": {"type": "string", "enum": ["Admin", "User"]},
            },
            "required": ["username", "password", "email", "role"],
        },
    },
    responses={HTTP_200_OK},
    auth=None,
    operation_id="PUT_updateUser",
    tags=["Admin"],
    operation=None,
)
@api_view(["PUT"])
@csrf_exempt
@requireLogin
@requireRoles(["Admin", "Super_Admin"])
def updateUser(request, id):
    if request.method == "PUT":
        try:
            user_info = request.user
            user_id = user_info.get("id", None)

            username = request.data.get("username", None)
            password = request.data.get("password", None)
            email = request.data.get("email", None)
            role = request.data.get("role", None)

            if user_id == id:
                return JsonResponse(
                    {"message": "can not update yourself"}, status=HTTP_400_BAD_REQUEST
                )
            info_user = Users.objects.filter(id=id).first()
            if info_user is None:
                return JsonResponse(
                    {"message": "User not found"}, status=HTTP_400_BAD_REQUEST
                )

            info_user.user_name = username if username else info_user.user_name
            info_user.email = email if email else info_user.email

            if password:
                checkPassValidate = validatePassword(password)
                if checkPassValidate is not None:
                    return JsonResponse(
                        {"message": checkPassValidate}, status=HTTP_400_BAD_REQUEST
                    )

                new_pwd_sha256 = encodeToSha256(password)
                info_user.pwd_sha256 = new_pwd_sha256

            if role:
                if role not in ["Admin", "User"]:
                    return JsonResponse(
                        {"message": "Role is invalid"}, status=HTTP_400_BAD_REQUEST
                    )
                info_user.role = role

            info_user.save()

            return JsonResponse(
                {"message": "Update user successfully"}, status=HTTP_200_OK
            )

        except Exception:
            return JsonResponse(
                {"message": "Update user unsuccessfully"}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only PUT requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "string",
                },
            },
            "required": ["token_id"],
        }
    },
    responses=None,
    auth=None,
    operation_id="signUpWithGoogle",
    tags=["User"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
def signUpGoogle(request):
    if request.method == "POST":
        try:
            token_id = request.data.get("token_id")

            if not token_id:
                return JsonResponse(
                    {"message": "Token id is required"}, status=HTTP_400_BAD_REQUEST
                )
            url = "https://www.googleapis.com/oauth2/v1/tokeninfo"
            params = {"access_token": token_id}
            response = requests.get(url, params=params).json()

            if response["email"] is None:
                return JsonResponse(
                    {"message": "User created successfully."},
                    status=HTTP_400_BAD_REQUEST,
                )
            userCheck = Users.objects.filter(email=response["email"]).first()

            permissions = None
            if userCheck is None:
                with transaction.atomic():
                    new_user = Users.objects.create(
                        email=response["email"], role="User", account_status="VERIFIED"
                    )
                    data_insert = showingfield_data(new_user.id)
                    ShowingField.objects.bulk_create(
                        [ShowingField(**item) for item in data_insert]
                    )

                token = generateBearerToken(
                    new_user.id, new_user.user_name, permissions
                )
                refresh_token = generateBearerTokenWithTime(
                    {"userId": new_user.id, "type": "REFRESH_TOKEN"},
                    REFRESH_TOKEN_TTL_MINUTES,
                )
                # addingTokenToRefresh(new_user, token, refresh_token)
                dataOutput = {
                    "id": new_user.id,
                    "email": new_user.email,
                    "user_name": new_user.user_name,
                    "role": new_user.role,
                }
                return JsonResponse(
                    {
                        "message": "User created successfully.",
                        "data": {
                            "access_token": token,
                            "refresh_token": refresh_token,
                            "permissions": permissions,
                            "user": dataOutput,
                        },
                    },
                    status=HTTP_201_CREATED,
                )
            else:
                token = generateBearerToken(
                    userCheck.id, userCheck.user_name, permissions
                )
                refresh_token = generateBearerTokenWithTime(
                    {"userId": userCheck.id, "type": "REFRESH_TOKEN"},
                    REFRESH_TOKEN_TTL_MINUTES,
                )
                # addingTokenToRefresh(userCheck, token, refresh_token)
                dataOutput = {
                    "id": userCheck.id,
                    "email": userCheck.email,
                    "user_name": userCheck.user_name,
                    "role": userCheck.role,
                }
                return JsonResponse(
                    {
                        "message": "User are already exist.",
                        "data": {
                            "access_token": token,
                            "refresh_token": refresh_token,
                            "permissions": permissions,
                            "user": dataOutput,
                        },
                    },
                    status=HTTP_200_OK,
                )

        except Exception as e:
            print(e)
            import traceback

            traceback.print_exc()
            return JsonResponse(
                {"message": "Sign-up unsuccessfully."}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only POST requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "first_name": {
                    "type": "string",
                },
                "last_name": {
                    "type": "string",
                },
                "phone_number": {
                    "type": "string",
                },
                "location": {
                    "type": "string",
                },
                "avatar": {
                    "type": "object",
                    "properties": {
                        "file_name": {
                            "type": "string",
                        },
                        "file_path": {
                            "type": "string",
                        },
                    },
                },
            },
            "required": ["first_name", "last_name", "phone_number", "location"],
        },
    },
    responses={HTTP_200_OK},
    auth=None,
    operation_id="PUT_updateUser",
    tags=["User"],
    operation=None,
)
@api_view(["PUT"])
@csrf_exempt
@requireLogin
def updateProfile(request):
    if request.method == "PUT":
        try:
            user_info = request.user
            user_id = user_info.get("id", None)

            first_name = request.data.get("first_name", None)
            last_name = request.data.get("last_name", None)
            phone_number = request.data.get("phone_number", None)
            location = request.data.get("location", None)
            avatar = request.data.get("avatar", None)

            user = Users.objects.filter(id=user_id).first()
            if user is None:
                return JsonResponse(
                    {"message": "User not found"}, status=HTTP_400_BAD_REQUEST
                )

            if avatar and avatar.get("file_path"):
                checkExitDocument = Document.objects.filter(
                    path_file=avatar.get("file_path"), file_name=avatar.get("file_name")
                ).first()

                if checkExitDocument is None:
                    avatar_file = Document.objects.create(
                        file_name=avatar.get("file_name"),
                        path_file=avatar.get("file_path"),
                    )
                    user.avatar = avatar_file
                else:
                    user.avatar = checkExitDocument
            else:
                user.avatar = None

            username = (
                unidecode(f"{first_name}{last_name}")
                if (first_name and last_name)
                else None
            )
            user.first_name = first_name if first_name else user.first_name
            user.last_name = last_name if last_name else user.last_name
            user.phone_number = phone_number if phone_number else user.phone_number
            user.location = location if location else user.location
            if user.user_name is None:
                user.user_name = username if username else user.user_name

            user.save()

            return JsonResponse(
                {"message": "Update user successfully"}, status=HTTP_200_OK
            )

        except Exception as e:
            print(e)
            return JsonResponse(
                {"message": "Update user unsuccessfully"}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only PUT requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "string",
                },
            },
            "required": ["token_id"],
        }
    },
    responses=None,
    auth=None,
    operation_id="signUpWithGoogle",
    tags=["User"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
def signInGoogle(request):
    if request.method == "POST":
        try:
            token_id = request.data.get("token_id")

            if not token_id:
                return JsonResponse(
                    {"message": "Token id is required"}, status=HTTP_400_BAD_REQUEST
                )
            url = "https://www.googleapis.com/oauth2/v1/tokeninfo"
            params = {"access_token": token_id}
            response = requests.get(url, params=params).json()

            if response["email"] is None:
                return JsonResponse(
                    {"message": "User created successfully."},
                    status=HTTP_400_BAD_REQUEST,
                )
            userCheck = Users.objects.filter(email=response["email"]).first()

            permissions = None
            if userCheck is None:
                return JsonResponse(
                    {"message": "User not found"}, status=HTTP_400_BAD_REQUEST
                )

            else:
                token = generateBearerToken(
                    userCheck.id, userCheck.user_name, permissions
                )
                refresh_token = generateBearerTokenWithTime(
                    {"userId": userCheck.id, "type": "REFRESH_TOKEN"},
                    REFRESH_TOKEN_TTL_MINUTES,
                )
                # addingTokenToRefresh(userCheck, token, refresh_token)
                dataOutput = {
                    "id": userCheck.id,
                    "email": userCheck.email,
                    "user_name": userCheck.user_name,
                    "role": userCheck.role,
                }
                return JsonResponse(
                    {
                        "message": "Sign in successful.",
                        "data": {
                            "access_token": token,
                            "refresh_token": refresh_token,
                            "permissions": permissions,
                            "user": dataOutput,
                        },
                    },
                    status=HTTP_200_OK,
                )

        except Exception as e:
            print(e)
            return JsonResponse(
                {"message": "Sign-in unsuccessfully."}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only POST requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                },
                "username": {"type": "string"},
                "password": {
                    "type": "string",
                },
            },
            "required": ["email", "password"],
        }
    },
    responses=None,
    auth=None,
    operation_id="signUp",
    tags=["User"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
def signUp(request):
    if request.method == "POST":
        try:
            email = request.data.get("email")
            username = request.data.get("username", None)
            password = request.data.get("password")

            if not password or not email:
                return JsonResponse(
                    {"message": "Please fill email and password."},
                    status=HTTP_400_BAD_REQUEST,
                )

            checkExitUser = Users.objects.filter(email=email).first()
            if checkExitUser:
                return JsonResponse(
                    {"message": "Email is already exist"}, status=HTTP_400_BAD_REQUEST
                )

            checkPassValidate = validatePassword(password)
            if checkPassValidate is not None:
                return JsonResponse(
                    {"message": checkPassValidate}, status=HTTP_400_BAD_REQUEST
                )

            pwd_sha256 = encodeToSha256(password)
            with transaction.atomic():
                newUser = Users.objects.create(
                    username=username if username else email.split("@")[0],
                    email=email,
                    pwd_sha256=pwd_sha256,
                    role="User",
                    account_status="NEW",
                )
                data_insert = showingfield_data(newUser.id)
                ShowingField.objects.bulk_create(
                    [ShowingField(**item) for item in data_insert]
                )

            return JsonResponse({"message": "Sign-up successfully"}, status=HTTP_200_OK)
        except Exception:
            import traceback

            traceback.print_exc()
            return JsonResponse(
                {"message": "Sign-up unsuccessfully."}, status=HTTP_400_BAD_REQUEST
            )
    return JsonResponse(
        {"message": "Invalid request method. Only POST requests are allowed."},
        status=HTTP_405_METHOD_NOT_ALLOWED,
    )
