from django.contrib import admin
from django.core.cache import cache

from apps.goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner,GoodsImage,GoodsSKU,GoodsSPU
# Register your models here.

# 定义一个类在后台管理员进行修改首页显示时自动生成静态页面
from celery_tasks.tasks import generate_static_index_html


class BaseModuleAdmin(admin.ModelAdmin):
    """抽象一个父类来继承"""
    def save_model(self, request, obj, form, change):
        # 调用父类方法 修改后生成静态页面
        super().save_model(request, obj, form, change)
        generate_static_index_html.delay()

        # 当后台管理员更新数据时,清除缓存
        cache.delete("index_page_data")

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        generate_static_index_html.delay()

        # 当后台管理员更新数据时,清除缓存
        cache.delete("index_page_date")


@admin.register(GoodsType)
class GoodsTypeAdmin(BaseModuleAdmin):
    list_display = ["id", "name", "logo", "image"]


@admin.register(IndexGoodsBanner)
class IndexGoodsBannerAdmin(BaseModuleAdmin):
    list_display = ["id", "sku", "image", "index"]


@admin.register(IndexPromotionBanner)
class IndexPromotionBannerAdmin(BaseModuleAdmin):
    list_display = ["id", "url", "name", "image", "index"]


@admin.register(IndexTypeGoodsBanner)
class IndexTypeGoodsBannerAdmin(BaseModuleAdmin):
    list_display = ["id", "type", "sku", "display_type", "index"]


@admin.register(GoodsSKU)
class GoodsSKUAdmin(BaseModuleAdmin):
    list_display = ["id", "type", "goods_spu", "name", "desc", "price", "unite", "image", "stock", "sales", "status"]


@admin.register(GoodsSPU)
class GoodsSPUAdmin(BaseModuleAdmin):
    list_display = ["id", "name", "detail"]


@admin.register(GoodsImage)
class GoodsImageAdmin(BaseModuleAdmin):
    list_display = ["id", "sku", "image"]


