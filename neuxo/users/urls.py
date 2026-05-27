from django.urls import path

from users.services import userServices

urlpatterns = [
    path("sign_in", userServices.signIn, name="sign_in"),
    path("sign_up", userServices.signUp, name="user_info"),
    path("sign_out", userServices.signOut, name="log_out"),
    path("user_infor", userServices.userInfo, name="refresh_token_user"),
    path(
        "refresh_token_user", userServices.refreshTokenUser, name="refresh_token_user"
    ),
    path("change_password", userServices.changePassword, name="change_password"),
    path(
        "set_password", userServices.setPassword, name="set_password"
    ),  # used for accounts without password
    path("sign_in_google", userServices.signInGoogle, name="sign_in_google"),
    path("sign_up_google", userServices.signUpGoogle, name="sign_up_google"),
    path("update_profile", userServices.updateProfile, name="update_profile"),
    # Admin
    path("admin/crete", userServices.createUser, name="user_info"),
    path("admin/list", userServices.getListUser, name="list_user"),
    path("admin/delete/<str:id>", userServices.deleteUser, name="delete_user"),
    path("admin/update/<str:id>", userServices.updateUser, name="update_user"),
]
