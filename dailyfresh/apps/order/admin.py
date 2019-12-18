from django.contrib import admin

# Register your models here.
from apps.order.models import OrderInfo, OrderGoods


@admin.register(OrderInfo)
class OrderInfoAdmin(admin.ModelAdmin):
    list_display = ["order_id", "user", "address", "pay_method", "total_count",
                    "total_price", "transit_price", "order_status", "trade_no"]


@admin.register(OrderGoods)
class OrderGoodsAdmin(admin.ModelAdmin):
    list_display = ["order", "sku", "count", "price", "comment"]