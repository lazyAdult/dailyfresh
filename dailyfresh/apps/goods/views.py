from django.core.cache import cache
from django.shortcuts import render, redirect

# Create your views here.
from django.urls import reverse
from django.views import View
from django_redis import get_redis_connection

from apps.goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from apps.order.models import OrderGoods


class IndexHandle(View):

    def get(self, request):
        """首页"""
        # 获取是否存在缓存,如果没有返回None 这里使用context就是保存的下面content的数据所以这里使用context没有影响
        context = cache.get('index_page_data')
        if context is None:
            # 获取商品种类信息
            types = GoodsType.objects.all()
            # 获取首页轮播图信息
            goods_banners = IndexGoodsBanner.objects.all().order_by("index")
            # 获取首页促销活动信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by("index")
            # 获取首页分类商品展示信息
            for type in types:
                image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by("index")
                title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by("index")

                # 动态的给对象增加属性, 分别保存首页分类商品的图片展示信息和文字展示信息
                type.image_banners = image_banners
                type.title_banners = title_banners

            context = {
                'types': types,
                'goods_banners': goods_banners,
                'promotion_banners': promotion_banners,
                'type_goods_banners': promotion_banners,
            }
            # 设置缓存django已经封装好了缓存方法我们直接代用api调用
            # 参数为key value timeout 设置为一个小时方便多人开发时清除缓存
            cache.set("index_page_data", context, 3600)
        # 获取用户购物车商品的数目
        user = request.user
        # 初始化购物车
        cart_count = 0
        # 验证用户是否登录
        if user.is_authenticated:
            # 连接到redis数据库
            conn = get_redis_connection("default")
            # 设置hash键值
            cart_key = "cart_%d" % user.id
            # 查询redis数据库
            cart_count = conn.hlen(cart_key)
        context.update(cart_count=cart_count)
        # context = {
        #     'types': types,
        #     'goods_banners': goods_banners,
        #     'promotion_banners': promotion_banners,
        #     'type_goods_banners': promotion_banners,
        #     'cart_count': cart_count
        # }

        return render(request, 'index.html', context)


class DetailHandle(View):
    """商品详情类"""

    def get(self, request, goods_id):

        # 获取商品id
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse("goods:index"))
        # 获取商品分类信息
        types = GoodsType.objects.all()
        # 获取商品评论信息      使用exclude可以过滤信息参数里面的信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment="")
        # 获取新品信息 [:2]取两个值
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by("-create_time")[:2]
        # 获取同一个SPU的其他规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods_spu=sku.goods_spu).exclude(id=goods_id)
        # 获取购物车
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            conn = get_redis_connection("default")
            cart_key = "key_%d" % user.id
            cart_count = conn.hlen(cart_key)

            # 添加用户浏览记录
            conn = get_redis_connection("default")
            # 拼接key
            history_key = "history_%d" % user.id
            # 先将列表中的goods_id移除  0代表全部移除
            conn.lrem(history_key, 0, goods_id)
            # 把浏览的goods_id插入到列表中 lpush表示从左侧插入保证用户看到最新的浏览记录
            conn.lpush(history_key, goods_id)
            # 只保存用户的5条浏览记录 ltrim对列表进行切片
            conn.ltrim(history_key, 0, 4)

        context = {
            'sku': sku, 'types': types,
            'sku_order': sku_orders,
            'new_skus': new_skus,
            'cart_cont': cart_count,
            "same_spu_skus": same_spu_skus
        }

        return render(request, 'detail.html', context)