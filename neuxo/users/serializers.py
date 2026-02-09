from rest_framework import serializers

from users.models import Users


class UserSerializers(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = "__all__"


class UsersSerializers(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = "__all__"


class UserGetSerializers(serializers.ModelSerializer):
    role_id = serializers.SerializerMethodField()

    class Meta:
        model = Users
        fields = [
            "id",
            "user_name",
            "email",
            "created_utc",
            "updated_utc",
            "status_code",
            "last_login",
        ]


class SignInSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)


class forgotPasswordUserSerializer(serializers.Serializer):
    email = serializers.CharField(required=True)


class changePasswordSerializer(serializers.Serializer):
    newPassword = serializers.CharField(required=True)
    oldPassword = serializers.CharField(required=True)


class updateProfileSerializer(serializers.Serializer):
    userName = serializers.CharField(required=True)


class SignInResponseDataSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    permissions = serializers.ListField()


class SignInResponseSerializer(serializers.Serializer):
    message = serializers.CharField(default="Sign-in successfully")
    data = SignInResponseDataSerializer()


class SignIn400ResponseSerializer(serializers.Serializer):
    error = serializers.CharField(default="Invalid request")


class SignIn401ResponseSerializer(serializers.Serializer):
    error = serializers.CharField(default="User Name or Password is incorrect")


class SignIn500ResponseSerializer(serializers.Serializer):
    message = serializers.CharField(default="Your account has been deactivated.")


class userInfoResponseDataSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.CharField()
    user_name = serializers.CharField()
    permissions = serializers.ListField()


class userInfoResponseSerializer(serializers.Serializer):
    message = serializers.CharField(default="successfully")
    data = userInfoResponseDataSerializer()


class forgotPasswordUserResponseSerializer(serializers.Serializer):
    message = serializers.CharField(default="Forgot Password successfully.")


class changePasswordResponseSerializer(serializers.Serializer):
    message = serializers.CharField(default="Change password successfully.")


class updateProfileResponseSerializer(serializers.Serializer):
    message = serializers.CharField(default="Update profile successfully.")


class userLogoutResponseSerializer(serializers.Serializer):
    message = serializers.CharField(default="Log-out successfully.")


class refreshTokenUserResponseSerializer(serializers.Serializer):
    message = serializers.CharField(default="Refresh successfully")
    data = SignInResponseDataSerializer()
