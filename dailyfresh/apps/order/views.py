from datetime import datetime

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect

# Create your views here.
from django.urls import reverse
from django.views import View
from django_redis import get_redis_connection

from apps.goods.models import GoodsSKU
from apps.order.models import OrderInfo, OrderGoods
from apps.user.models import Address
from utils.mixin import LoginRequiredMixin


class OrderPlaceHandle(LoginRequiredMixin, View):

    def post(self, request):
        # 获取用户
        user = request.user
        # 获取订单页面传入的商品id
        sku_ids = request.POST.getlist("sku_ids")
        # 校验参数
        if not sku_ids:
            return redirect(reverse("cart:info"))
        # 连接redis数据库
        conn = get_redis_connection("default")
        # 拼接查询关键字
        cart_key = "cart_%d" % user.id
        # 定义商品列表
        skus = []
        # 定义总价格和总数量
        total_count = 0
        total_price = 0
        # 获取单个商品id
        for sku_id in sku_ids:
            # 从数据库中获取商品
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取用户所需商品的数量
            count = conn.hget(cart_key, sku_id)
            # 计算商品小计
            amount = sku.price * int(count)
            # 动态给sku增加属性
            sku.amount = amount
            sku.count = int(count)
            # 将商品追加到商品列表
            skus.append(sku)
            # 计算总价格和总数量
            total_count += int(count)
            total_price += amount

        # 运费:实际开发的时候属于一个子系统
        transit_price = 10  # 这里将运费写死
        # 实付款
        total_pay = total_price + transit_price

        # 获取收件地址
        addrs = Address.objects.filter(user_id=user.id)
        # 拼接字符串用于传递购买商品的id方便在前端传到订单后台 使用,分割
        sku_ids = ",".join(sku_ids)
        # 组织上下文
        context = {
            "skus": skus,
            "total_count": total_count,
            "total_price": total_price,
            "transit_price": transit_price,
            "total_pay": total_pay,
            "addrs": addrs, "sku_ids": sku_ids,
        }

        return render(request, "place_order.html", context)

    def get(self, request):
        # todo:判断用户是否有未支付订单
        user = request.user
        # 连接redis数据库
        conn = get_redis_connection("default")
        # 拼接键值
        cart_key = "cart_%d" % user.id
        # 取出用户购物车数据
        cart_field = conn.hkeys(cart_key)
        if not cart_field:
            return redirect(reverse("user:order"))
        return render(request, "place_order.html")


# 用户使用ajax传入了参数:商品id,收件地址,支付方式
# mysql事务:一组sql操作,要么都成功,要么都失败
# 高并发:秒杀
# 支付宝支付
# 使用悲观锁
class OrderCommitHandle1(View):
    """创建订单"""

    # 开启事务防止在库存不足的情况下继续执行数据库操作
    @transaction.atomic
    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 0, "error_message": "请登录"})
        # 获取用户传入数据
        sku_ids = request.POST.get("sku_ids")

        addr_id = request.POST.get("addr_id")
        pay_method = request.POST.get("pay_method")
        # 判断用户传入数据是否合法
        if not all([sku_ids, addr_id, pay_method]):
            return JsonResponse({"res": 1, "error_message": "信息输入不完整"})
        # 判断支付方式,先在order的model中定义查询的键值
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({"res": 2, "error_message": "请选择支付方式"})
        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({"res": 3, "error_message": "请选择支付方式"})
        # Todo:创建订单核心业务
        # 组织参数  先在缺少订单id,运费,总数目,总数量
        # 订单id 订单生成时间+用户id
        order_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(user.id)
        # 创建运费
        transit_price = 10
        # 创建总价格
        total_price = 0
        # 创建总件数
        total_count = 0

        # 创建保存点,如果下面的某处存储失败,进行回滚,如果没有再进行保存
        Savepoint = transaction.savepoint()
        try:
            # todo 生成一个订单,向df_order_info表中添加一条数据
            order = OrderInfo.objects.create(order_id=order_id, user=user,
                                             address=addr, pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)
            # 拼接查询key
            cart_kry = "cart_%d" % user.id
            # 连接数据库
            conn = get_redis_connection("default")
            # todo 一定要了解一个用户只有一个订单信息,但是每件商品都要对应一个数据表
            # 用户的订单中几件商品就要向df_order_goods中添加几条对应的数据
            # 遍历所有的商品id
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                # 校验商品是否存在
                try:
                    # 正常查找
                    # sku = GoodsSKU.objects.get(id=sku_id)
                    # 处理并发时开起悲观锁,谁先拿到就会阻塞,等到数据更新结束以后才会解锁  解决订单并发
                    # 悲观锁,相当于 select * from df_goods_sku where id=sku_id for update;
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)

                except GoodsSKU.DoesNotExist:
                    # 如果订单不存在进行回滚
                    transaction.rollback(Savepoint)
                    return JsonResponse({"res": 4, "error_message": "商品不存在"})
                # 获取订单中商品数量
                count = conn.hget(cart_kry, sku_id)

                # 判断库存是否满足订单需求
                if int(count) > sku.stock:
                    # 如果库存不足进行回滚数据
                    transaction.rollback(Savepoint)
                    return JsonResponse({"res": 5, "error_message": "库存不足"})
                # todo :向df_order_goods表中添加一条记录
                OrderGoods.objects.create(order=order, sku=sku, count=count,
                                          price=sku.price,)
                # todo: 更新商品的存库和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()

                # todo:累加计算订单商品的总数量和总价格
                # 获取商品中商品价格的小计
                amount = sku.price * int(count)
                total_price += amount
                total_count += int(count)

            # 更新订单中信息报中的总价格和总数量
            order.total_count = total_count
            order.total_price = total_price
            # 保存修改
            order.save()
        except:
            # 订单失败回滚事务
            transaction.rollback(Savepoint)
            return JsonResponse({"res": 6, "error_message": "订单失败"})

        # 数据成功保存
        transaction.savepoint_commit(Savepoint)
        # Todo:删除购物车中的购买过的商品 使用 *[1, 2]就会解包
        conn.hdel(cart_kry, *sku_ids)

        return JsonResponse({"res": 7, "message": "创建成功"})


# 使用乐观锁
class OrderCommitHandle(View):
    """创建订单"""

    # 开启事务防止在库存不足的情况下继续执行数据库操作
    @transaction.atomic
    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 0, "error_message": "请登录"})
        # 获取用户传入数据
        sku_ids = request.POST.get("sku_ids")

        addr_id = request.POST.get("addr_id")
        pay_method = request.POST.get("pay_method")
        # 判断用户传入数据是否合法
        if not all([sku_ids, addr_id, pay_method]):
            return JsonResponse({"res": 1, "error_message": "信息输入不完整"})
        # 判断支付方式,先在order的model中定义查询的键值
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({"res": 2, "error_message": "请选择支付方式"})
        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({"res": 3, "error_message": "请选择支付方式"})
        # Todo:创建订单核心业务
        # 组织参数  先在缺少订单id,运费,总数目,总数量
        # 订单id 订单生成时间+用户id
        order_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(user.id)
        # 创建运费
        transit_price = 10
        # 创建总价格
        total_price = 0
        # 创建总件数
        total_count = 0

        # 创建保存点,如果下面的某处存储失败,进行回滚,如果没有再进行保存
        Savepoint = transaction.savepoint()
        try:
            # todo 生成一个订单,向df_order_info表中添加一条数据
            order = OrderInfo.objects.create(order_id=order_id, user=user,
                                             address=addr, pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)
            # 拼接查询key
            cart_kry = "cart_%d" % user.id
            # 连接数据库
            conn = get_redis_connection("default")
            # todo 一定要了解一个用户只有一个订单信息,但是每件商品都要对应一个数据表
            # 用户的订单中几件商品就要向df_order_goods中添加几条对应的数据
            # 遍历所有的商品id
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                for i in range(3):
                    # 校验商品是否存在
                    try:
                        # 正常查找
                        sku = GoodsSKU.objects.get(id=sku_id)

                    except GoodsSKU.DoesNotExist:
                        # 如果订单不存在进行回滚
                        transaction.savepoint_rollback(Savepoint)
                        return JsonResponse({"res": 4, "error_message": "商品不存在"})
                    # 获取订单中商品数量
                    count = conn.hget(cart_kry, sku_id)

                    # 判断库存是否满足订单需求
                    if int(count) > sku.stock:
                        # 如果库存不足进行回滚数据
                        transaction.savepoint_rollback(Savepoint)
                        return JsonResponse({"res": 5, "error_message": "库存不足"})

                    # 更新商品销量和库存
                    origin_stock = sku.stock
                    new_stock = origin_stock - int(count)
                    new_sales = sku.stock + int(count)


                    # 使用乐观锁:使用乐观锁就是可以同时进行查询在在数据更新时进行判断,条件满足,订单成功,否则订单失败
                    # 相当于sql语句 update df_goods_sku set stock=new_stock, sales=new_sales where id=sku_id and stock=origin_stock
                    # 返回值是受影响的行数
                    res = GoodsSKU.objects.filter(id=sku.id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        # 回滚数据
                        # 尝试3次来验证是否可以下单
                        if i == 2:
                            transaction.savepoint_rollback(Savepoint)
                            return JsonResponse({"res": 6, "error_message": "秒杀失败"})
                        continue

                    # todo :向df_order_goods表中添加一条记录
                    OrderGoods.objects.create(order=order, sku=sku, count=count,
                                              price=sku.price, )
                    # todo: 更新商品的存库和销量
                    # sku.stock -= int(count)
                    # sku.sales += int(count)
                    # sku.save()

                    # todo:累加计算订单商品的总数量和总价格
                    # 获取商品中商品价格的小计
                    amount = sku.price * int(count)
                    total_price += amount
                    total_count += int(count)

                    # 下单成功跳出循环
                    break

            # 更新订单中信息报中的总价格和总数量
            order.total_count = total_count
            order.total_price = total_price
            # 保存修改
            order.save()
        except:
            # 订单失败回滚事务
            transaction.savepoint_rollback(Savepoint)
            return JsonResponse({"res": 7, "error_message": "订单失败"})

        # 数据成功保存
        transaction.savepoint_commit(Savepoint)
        # Todo:删除购物车中的购买过的商品 使用 *[1, 2]就会解包
        conn.hdel(cart_kry, *sku_ids)

        return JsonResponse({"res": 8, "message": "创建成功"})
