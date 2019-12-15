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
    pass


@admin.register(IndexGoodsBanner)
class IndexGoodsBannerAdmin(BaseModuleAdmin):
    pass


@admin.register(IndexPromotionBanner)
class IndexPromotionBannerAdmin(BaseModuleAdmin):
    pass


@admin.register(IndexTypeGoodsBanner)
class IndexTypeGoodsBannerAdmin(BaseModuleAdmin):
    pass


@admin.register(GoodsSKU)
class GoodsSKUAdmin(BaseModuleAdmin):
    pass


@admin.register(GoodsSPU)
class GoodsSPUAdmin(BaseModuleAdmin):
    pass


@admin.register(GoodsImage)
class GoodsImageAdmin(BaseModuleAdmin):
    pass


