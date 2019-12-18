from django.urls import path, include

from apps.order.views import OrderPlaceHandle, OrderCommitHandle

urlpatterns = [
    path("place/", OrderPlaceHandle.as_view(), name="place"),   # 订单页面
    path("commit/", OrderCommitHandle.as_view(), name="commit")     # 创建订单
]
