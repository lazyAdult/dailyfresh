from django.urls import path, include, re_path

from apps.goods import views
from apps.goods.views import IndexHandle, DetailHandle

urlpatterns = [
    # 为了区分是否是第一次访问页面我们添加index路径
    path("index/", IndexHandle.as_view(), name="index"),
    re_path(r"detail/(?P<goods_id>\d+)$", DetailHandle.as_view(), name="detail")
]
