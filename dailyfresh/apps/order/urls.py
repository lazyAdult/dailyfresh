from django.urls import path, include, re_path

from apps.order.views import OrderPlaceHandle, OrderCommitHandle, OrderPayHandle, OrderCheckedHandle, OrderCommentHandle

urlpatterns = [
    path("place/", OrderPlaceHandle.as_view(), name="place"),   # 订单页面
    path("commit/", OrderCommitHandle.as_view(), name="commit"),   # 创建订单
    path("pay/", OrderPayHandle.as_view(), name="pay"),     # 向用户跳转到支付页面
    path("checked/", OrderCheckedHandle.as_view(), name="checked"),     # 查看支付情况
    re_path(r"^comment/(?P<order_id>\d+)$", OrderCommentHandle.as_view(), name="comment"),     # 订单商品评论页面
]
