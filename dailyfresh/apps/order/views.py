import json
import os
import time
from datetime import datetime

from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.domain.AlipayTradeAppPayModel import AlipayTradeAppPayModel
from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel
from alipay.aop.api.domain.SettleDetailInfo import SettleDetailInfo
from alipay.aop.api.domain.SettleInfo import SettleInfo
from alipay.aop.api.domain.SubMerchant import SubMerchant
from alipay.aop.api.request.AlipayTradeAppPayRequest import AlipayTradeAppPayRequest
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest
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
from dailyfresh import settings
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
                    print(sku.stock)
                    print(sku.sales)

                    # 使用乐观锁:使用乐观锁就是可以同时进行查询在在数据更新时进行判断,条件满足,订单成功,否则订单失败
                    # 相当于sql语句 update df_goods_sku set stock=new_stock,
                    #  sales=new_sales where id=sku_id and stock=origin_stock
                    # 返回值是受影响的行数        todo:要放在创建数据库后面防止重复尝试添加数据库数据
                    res = GoodsSKU.objects.filter(id=sku.id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                    print(sku.stock)
                    print(sku.sales)
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


# ajax post
# 前端传递的参数:订单id(order_id)
# /order/pay
class OrderPayHandle(View):
    """订单支付"""

    def post(self, request):
        """订单支付"""
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 1, "error_message": "请先登录"})
        # 接收参数
        order_id = request.POST.get("order_id")
        # 校验参数
        if not order_id:
            return JsonResponse({"res": 2, "error_message": "无效订单id"})
        ordertext = OrderInfo.objects.get(order_id=order_id)
        print(order_id, user)
        print(ordertext.order_id, ordertext.user,ordertext.pay_method,ordertext.order_status)
        try:
            # 判断订单id是否是传入的订单id,用户是否为当前登录的用户,支付方法是否为3(支付宝支付),商品状态是否是未支付
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user, pay_method=3,
                                          order_status=1)
        except:
            # 如果上述条件有一个不满足就终止订单
            return JsonResponse({"res": 3, "error_message": "订单错误"})

        # 业务处理:使用python sdk调用支付宝接口
        # 初始化
        def ali_pay():
            # 为阿里支付实例化一个对象
            alipay_config = AlipayClientConfig(sandbox_debug=True)
            # 初始化各种配置信息
            # 阿里提供的服务接口
            alipay_config.server_url = "https://openapi.alipaydev.com/gateway.do"
            # 申请沙箱环境的app_id
            alipay_config.app_id = "2016101500689662"

            # 商户的私钥
            with open(os.path.join(settings.BASE_DIR, "apps/order/app_private_key.txt")) as f:
                alipay_config.app_private_key = f.read()

            # 阿里的公钥
            with open(os.path.join(settings.BASE_DIR, "apps/order/alipay_public_key.txt")) as f:
                alipay_config.alipay_public_key = f.read()

            # 实例化一个支付对象并返回
            alipay_client = DefaultAlipayClient(alipay_client_config=alipay_config)
            return alipay_client

        # 对照接口文档，构造请求对象
        # 创建阿里支付的实例化对象
        client = ali_pay()
        # 为API生成一个模板对象初始化参数时使用
        model = AlipayTradePagePayModel()
        # 订单号
        model.out_trade_no = order_id
        # 需要支付的金额
        model.total_amount = str(order.total_price)
        # 商品的标题
        model.subject = "天天生鲜%s" % order_id
        # 商品的详细内容
        model.body = "支付宝测试"
        # 销售产品码,与支付宝签约商品的名称
        model.product_code = "FAST_INSTANT_TRADE_PAY"
        # 实例化一个请求对象
        request = AlipayTradePagePayRequest(biz_model=model)
        # 向阿里发出支付请求
        response = client.page_execute(request, http_method="GET")
        return JsonResponse({"res": 0, "response": response})


# ajax post
# 前端传递的参数:订单id(order_id)
# /order/pay
class OrderCheckedHandle(View):
    """订单支付结果查询"""

    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 1, "error_message": "请先登录"})
        # 接收参数
        order_id = request.POST.get("order_id")
        # 校验参数
        if not order_id:
            return JsonResponse({"res": 2, "error_message": "无效订单id"})
        try:
            # 判断订单id是否是传入的订单id,用户是否为当前登录的用户,支付方法是否为3(支付宝支付),商品状态是否是未支付
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user, pay_method=3,
                                          order_status=1)
        except:
            # 如果上述条件有一个不满足就终止订单
            return JsonResponse({"res": 3, "error_message": "订单错误"})

        # 业务处理:使用python sdk调用支付宝接口
        # 初始化
        def ali_pay():
            # 为阿里支付实例化一个对象
            alipay_config = AlipayClientConfig(sandbox_debug=True)
            # 初始化各种配置信息
            # 阿里提供的服务接口
            alipay_config.server_url = "https://openapi.alipaydev.com/gateway.do"
            # 申请沙箱环境的app_id
            alipay_config.app_id = "2016101500689662"

            # 商户的私钥
            with open(os.path.join(settings.BASE_DIR, "apps/order/app_private_key.txt")) as f:
                alipay_config.app_private_key = f.read()

            # 阿里的公钥
            with open(os.path.join(settings.BASE_DIR, "apps/order/alipay_public_key.txt")) as f:
                alipay_config.alipay_public_key = f.read()

            # 实例化一个支付对象并返回
            alipay_client = DefaultAlipayClient(alipay_client_config=alipay_config)
            return alipay_client

        # 创建一个实例化对象
        client = ali_pay()
        # 初始化各种配置信息
        # 完成接口调用
        model = AlipayTradeQueryModel()
        # 获取订单号
        model.out_trade_no = order_id
        # 组织参数 实例化一个请求对象
        request = AlipayTradeQueryRequest(biz_model=model)

        # response返回一个字典
        # {"code": "10000", "msg": "Success",
        #  "buyer_logon_id": "lbt***@sandbox.com",
        # "buyer_pay_amount": "0.00",
        #  "buyer_user_id": "2088102179931812",
        #  "buyer_user_type": "PRIVATE",
        #  "invoice_amount": "0.00",
        #  "out_trade_no": "201912182026581",
        # "point_amount": "0.00",
        #  "receipt_amount": "0.00",
        #  "send_pay_date": "2019-12-19 12:11:52",
        # "total_amount": "33.60",
        # "trade_no": "2019121922001431811000137543",
        # "trade_status": "TRADE_SUCCESS"}

        while True:
            # 返回应答
            response = client.execute(request)
            # 将字符串转换为字典
            response = json.loads(response)
            # 获取当前支付提示码
            code = response.get("code")
            # 获取当前支付状态
            trade_status = response.get("trade_status")
            # 判断支付情况
            if code == "10000" and trade_status == "TRADE_SUCCESS":
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get("trade_no")
                # 更新订单状态
                order.order_status = 4
                order.trade_no = trade_no
                order.save()
                # 返回结果
                return JsonResponse({"res": 0, "message": "支付成功"})
            # 业务处理时可能一时请求业务处理失败,需要进行重复验证在等待状态是正在交易等待卖家付款
            elif code == "10000" or code == "40004":
                # 这时需要跳过需要进一步的验证处理
                import time
                # 让程序休息5秒,同时也能缓解进程压力
                time.sleep(5)
                continue
            else:
                return JsonResponse({"res": 4, "error_message": "支付失败"})


# 商品评论页面
class OrderCommentHandle(LoginRequiredMixin, View):
    """订单商品评论页面"""

    def get(self, request, order_id):
        # 获取当前用户
        user = request.user
        # 判断是否为空
        if not order_id:
            return redirect(reverse("user:order", args=str(1)))
        # 判断订单是否存在
        try:
            order = OrderInfo.objects.get(user=user,
                                  order_id=order_id)
        except OrderInfo.DoesNotExist:
            # 遍历订单获取当前订单的所有商品信息
            return redirect(reverse("user:order", args=str(1)))
        # 动态给订单对象添加属性
        order.status_name = OrderInfo.ORDER_STATUS_ENUM[order.order_status]
        # 查询订单商品的信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)
        # 查询订单中的所有商品
        for order_sku in order_skus:
            # 计算商品的小计
            amount = order_sku.count * order_sku.price
            # 动态给商品添加小计
            order_sku.amount = amount

        # 动态给order_sku增加属性order_skus
        order.order_skus = order_skus

        return render(request, "goods_order_comment.html", {"order": order})

        # else:
        #     return redirect(reverse("user:order", args=str(1)))

    # 提交评论
    def post(self, request, order_id):
        # 获取提交请求
        user = request.user
        # 判断是否传入order_id参数
        if not order_id:
            return redirect(reverse("user:order", args=str(1)))
        # 判断获取的订单id和参数传入的订单id是否相同
        post_order_id = request.POST.get("order_id")
        # 判断路径参数是否与订单id相同
        if order_id != post_order_id:
            return redirect(reverse("user:order", args=str(1)))
        try:
            # 获取订单对象
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order", args=str(1)))
        # 获取订单商品数
        total_count = request.POST.get("total_count")
        total_count = int(total_count)
        # 遍历订单数 取出对应的值
        for i in range(1, total_count+1):
            # 根据前端获取的商品id
            sku_id = request.POST.get("sku_%d" % i)
            # 尝试获取商品信息
            try:
                order_goods = OrderGoods.objects.get(id=sku_id, order=order)
            except OrderGoods.DoesNotExist:
                # 如果没有匹配成功跳过
                continue
            # 获取评论内容
            goods_comment = request.POST.get("comment_%d" % i)
            print(goods_comment)
            # 将内容赋值给数据库对应的键
            order_goods.comment = goods_comment
            # 保存内容到数据库
            order_goods.save()
        # 修改订单状态 修改为已完成
        order.order_status = 5
        # 保存到数据库
        order.save()
        return redirect(reverse("user:order", args=str(1)))
