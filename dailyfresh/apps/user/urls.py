from django.urls import path, include, re_path

from apps.user import views
from apps.user.views import RegisterHandle, LoginHandle, UserInfoView, UserOrderView, AddressView, LogoutHandle

urlpatterns = [
    path("register/", RegisterHandle.as_view(), name="register"),     # 注册
    re_path(r"^active/(?P<code>.*)$", views.comfire_mail, name="active"),   # 激活用户

    path('login/', LoginHandle.as_view(), name="login"),    # 登录
    path('logout/', LogoutHandle.as_view(), name="logout"),     # 注销登录

    # # 调用django自带的用户状态验证默认的是跳转到account/login,我们需要在settings里面设置LOGIN_URL = "/user/login"
    # path('', login_required(UserInfoView.as_view()), name="user"),      # 用户信息-信息页
    # path('info/', login_required(UserOrderView.as_view()), name="order"),   # 用户订单页面
    # path('address/', login_required(AddressView.as_view()), name="address"),      # 用户地址页面
    # 使用LoginRequiredMixin在mixin中定义的方法就可以直接写
    path('', UserInfoView.as_view(), name="user"),      # 用户信息-信息页
    path('info/', UserOrderView.as_view(), name="order"),   # 用户订单页面
    path('address/', AddressView.as_view(), name="address"),      # 用户地址页面

]
