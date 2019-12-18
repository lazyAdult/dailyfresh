from django.http import JsonResponse
from django.shortcuts import render, redirect

# Create your views here.
from django.urls import reverse
from django.views import View
from django_redis import get_redis_connection

from apps.goods.models import GoodsSKU
from utils.mixin import LoginRequiredMixin


# 添加商品到购物车:
# 1>请求方式,采用ajax,post
# 如果涉及到数据的修改(新增,更新,删除),采用post
# 如果只涉及到数据的获取,采用get
# 传递参数:商品id 商品数量


class CartHandle(View):

    def post(self, request):
        sku_id = request.POST.get("sku_id")
        count = request.POST.get("count")
        user = request.user
        # 因为ajax发起的请求都在后端,在浏览器中看到效果所以我们要做出用户是否登录判断
        if not user.is_authenticated:
            return JsonResponse({'res': 0, "error_message": "你还没有登录"})
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, "error_message": "数据输入不完整"})
        # 校验商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({'res': 2, "error_message": "商品数目出错"})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({"res": 3, "error_message": "商品不存在"})

        # 业务处理添加购物车记录
        # 连接redis数据库
        conn = get_redis_connection("default")
        # 创建查询key
        cart_key = "cart_%d" % user.id
        # 获取数据库对应id的值
        # 尝试获取sku_id的值-->hget(key, 属性)
        cart_count = conn.hget(cart_key, sku_id)
        # 累加购物车中商品的数目并判断是否这个用户已经添加过购物车此商品
        if cart_count:
            count += int(cart_count)
        # 判断库存
        if count > sku.stock:
            return JsonResponse({"res": 4, "error_message": "库存不足"})

        # 更新设置用户在数据库中对应商品的数量hset()方法如果已经存在更改属性的值,没有的话添加
        conn.hset(cart_key, sku_id, count)
        # 计算用户购物车商品的总条目数
        total_count = conn.hlen(cart_key)
        # 返回应答
        return JsonResponse({"res": 5, "total_count": total_count, "message": "添加成功"})


# 购物车模块
class CartInfoHandle(LoginRequiredMixin, View):

    def get(self, request):
        """获取对应购物车信息"""
        user = request.user
        # 连接数据库
        conn = get_redis_connection("default")
        # 拼接key
        cart_key = "cart_%d" % user.id
        # 查询对应用户购物车信息
        cart_dict = conn.hgetall(cart_key)
        # 保存用户购物车数据
        skus = []
        # 保存用户购物车中商品的总条目和总价格
        total_price = 0
        total_count = 0
        # 遍历用户字典取出用户信息
        for sku_id, count in cart_dict.items():
            # 通过商品id获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 添加到skus列表中
            skus.append(sku)
            # 计算商品小计
            amount = sku.price * int(count)
            # 动态给sku对象那增加amount属性
            sku.amount = amount
            # 动态给sku对象增加count属性
            sku.count = int(count)

            # 累加计算总价格和总条目
            total_count += int(count)
            total_price += amount

        # 组织上下文
        context = {
            "total_price": total_price,
            "total_count": total_count,
            "skus": skus
        }

        return render(request, 'cart.html', context)


# 更新购物车记录
# 采用ajax post请求
# 前端需要传递的参数:商品id(sku_id) 更新商品的数量
class CartUpdateHandle(View):
    """购物车记录更新"""
    def post(self, request):

        # 因为ajax发起的请求都在后端,在浏览器中看到效果所以我们要做出用户是否登录判断
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, "error_message": "你还没有登录"})
        sku_id = request.POST.get("sku_id")
        count = request.POST.get("count")
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, "error_message": "数据输入不完整"})
        # 校验商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({'res': 2, "error_message": "商品数目出错"})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({"res": 3, "error_message": "商品不存在"})

        # 业务处理更新购物车记录
        # 连接redis数据库
        conn = get_redis_connection("default")
        # 创建查询key
        cart_key = "cart_%d" % user.id
        # 判断库存
        if count > sku.stock:
            return JsonResponse({"res": 4, "error_message": "库存不足"})

        # 更新设置用户在数据库中对应商品的数量hset()方法如果已经存在更改属性的值,没有的话添加
        conn.hset(cart_key, sku_id, count)

        # 保存用户购物车中商品的总条目
        total_count = 0
        # 遍历用户字典取出用户信息计算购物车中商品的总件数{"1": 5, "2": 3}
        vals = conn.hvals(cart_key)
        # 计算总件数
        for val in vals:
            total_count += int(val)
        # 返回应答
        return JsonResponse({"res": 5, "total_count": total_count, "message": "修改成功"})


# 删除购物车数据
# 采用ajax post请求
# 前端需要传入的参数:商品的id(sku_id)
class CartDeleteHandle(View):
    """删除数据类"""

    def post(self, request):
        # 判断是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 0, "error_message": "请先登录"})

        # 接收参数
        sku_id = request.POST.get("sku_id")

        # 查看是否有参数
        if not sku_id:
            return JsonResponse({"res": 1, "error_message": "无效参数"})

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({"res": 2, "error_message": "没有这个商品"})

        # 连接数据库
        conn = get_redis_connection("default")
        # 拼接删除键
        cart_key = "cart_%d" % user.id
        # 删除对应的数据
        conn.hdel(cart_key, sku_id)

        # 获取所有件数
        vals = conn.hvals(cart_key)
        # 设置总件数
        total_count = 0
        # 遍历所有值并相加
        for val in vals:
            total_count += int(val)
        # 返回应答
        return JsonResponse({"res": 3, "total_count": total_count, "message": "成功删除"})
