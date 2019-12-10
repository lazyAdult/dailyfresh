from django.urls import path, include, re_path

from apps.user import views
from apps.user.views import RegisterHandle, LoginHandle

urlpatterns = [
    path("register/", RegisterHandle.as_view(), name="register"),     # 注册
    re_path(r"^active/(?P<code>.*)$", views.comfire_mail, name="active"),
    path('login/', LoginHandle.as_view(), name="login")
]
