from django.urls import path, include

from apps.cart.views import CartHandle, CartInfoHandle, CartUpdateHandle, CartDeleteHandle

urlpatterns = [
    path('add/', CartHandle.as_view(), name="add"),     # 增加购物车商品
    path('info/', CartInfoHandle.as_view(), name="info"),   # 获取购物车商品信息
    path("update/", CartUpdateHandle.as_view(), name="update"),     # 更新购物车数据
    path("delete/", CartDeleteHandle.as_view(), name="delete")      # 删除购物车数据
]
