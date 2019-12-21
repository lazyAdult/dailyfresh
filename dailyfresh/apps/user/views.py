import re

from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator

from apps.order.models import OrderInfo, OrderGoods
from utils.mixin import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render, redirect

# Create your views here.
from django.urls import reverse
from django.views import View
from django_redis import get_redis_connection
from itsdangerous import SignatureExpired

from apps.goods.models import GoodsSKU
from celery_tasks import tasks
from apps.user.diy_views import HidenMessage
from apps.user.models import User, Address
from dailyfresh import settings


class RegisterHandle(View):
    """设置注册类处理注册"""
    def get(self, request):
        """get请求方式"""
        return render(request, 'register.html')

    def post(self, request):
        """post请求方式"""
        username = request.POST.get('user_name')
        password1 = request.POST.get('pwd')
        password2 = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 两次密码是否一致
        if password1 != password2:
            error_message = "两次密码不一致"
            return render(request, 'register.html', locals())
        # 验证是否条件都为True
        if not all([username, password1, email]):
            error_message = "注册信息不完整"
            return render(request, 'register.html', locals())
        # 校验邮箱
        if not re.match(r'^[a-z0-9][\w\\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            error_message = "邮箱信息格式不正确"
            return render(request, 'register.html', locals())
        if allow != 'on':
            error_message = "对不起,请阅读用户协议并勾选"
            return render(request, 'register.html', locals())
        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as e:
            # 用户不存在
            user = None
        else:
            # 用户名已存在
            error_message = "用户名已存在"
            return render(request, 'register.html', locals())
        # 调用django本身对于用户的处理方法 进行业务处理,用户注册并保存到数据库
        user = User.objects.create_user(username, email, password2)
        # 对于Django注册以后会将用户自动激活,将用户激活状态设置为0表示未激活
        user.is_active = 0
        user.save()

        # 发送邮件并提示用户进行激活包含激活的连接:http://127.0.0.1/user/active/(用户id)
        # 激活连接中包含用户的敏感信息使用第三方加密进行发送加密信息itdangerous

        # 加密用户的身份信息,并生成token
        token = HidenMessage(settings.SECRET_KEY, 3600, id=user.id)
        token = token.make_secret()
        token = token.decode()
        # 发送邮件
        # send_mails(email, settings.EMAIL_HOST_USER, username, token)
        # 因为我们在celery里面使用的send_mail方法是一个阻塞函数我们可以通过缓存,提高用户体验
        # 使用它的delay方法就可以实现
        tasks.send_mails.delay(email, settings.EMAIL_HOST_USER, username, token)
        # 返回应答跳转到登录页面
        return redirect(reverse("user:login"))


def comfire_mail(request, code):
    code = HidenMessage(settings.SECRET_KEY, 3600, code=code)
    try:
        code = code.load_secret()
        user_id = code['confirm']
        # 根据id获取用户信息
        global user
        user = User.objects.get(id=user_id)
        if user.is_active == 1:
            return HttpResponse("用户已激活")
        else:
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 跳转到登录页面
            return redirect(reverse("user:login"))
    except SignatureExpired as e:
        # itsdangerous自带的过期错误,需要导入
        # 激活连接已过期
        user.delete()
        return HttpResponse("激活连接已过期")


class LoginHandle(View):

    def post(self, request):
        username = request.POST.get("username")
        password = request.POST.get("pwd")

        if not all([username, password]):
            error_message = "输入的信息不完整"
            return render(request, 'login.html', locals())
        # 业务处理:登录验证(使用django自带的authenticate方法 配合login()函数进行记录session)
        # 需要在setting设置AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.AllowAllUsersModelBackend']不然一直提示为None
        user = authenticate(username=username, password=password)

        if user is not None:
            # 用户名密码正确
            if user.is_active:
                # 查看用户是否已激活
                # 记录用户状态
                # 如果你已经认证了一个用户可以使用login()函数把它附带到当前会话当中,login()使用Django的session
                # 框架来将用户的ID保存到session中
                login(request, user)

                # 记录用户登录状态 当用户登录以后添加islogin字段在session中
                request.session["is_login"] = True
                # flush()方法是比较安全的一种做法,而且一次性将session中的所有内容全部清空,确保不留后患.但也有不好的地方,那就是如果你在session中
                # 删除数据库中sessionid对应的值
                # request.session.clear()
                # 删除session中指定的键及值,在存储中只删除某个键及对应的某个值
                # del request.session['键']
                # 设置会话超时时间,如果没有指定过期时间则两个星期后过期
                # 如果value是一个整数,会话的session_id cookie将在value秒没有活动后过期
                # 如果value为0,那么用户会话的session_id cookie将在用户的浏览器关闭以后过期
                # 如果value为None,那么会话的session_id cookie两周之后过期
                # request.session.set_expiry(value)
                # 夹带了一点私货,也会一并删除,这一点一定要注意
                request.session.set_expiry(0)
                # 使用post提交的时候默认提交到浏览器显示的地址页面
                # 使用django自带的login_required在验证用户没有登录的情况下跳转到登录页面并且把用户访问的页面当做参数传入
                # 我们可以设置来返回到用户登录前的页面用户验证在url哪里需要在settings设置LOGIN_URL = "/user/login"
                # login_required()的方法的url显示127.0.0.1:8000/user/login/?next=/order/ 登录以后就会跳转到127.0.0.1:8000/user/order/ 页面
                # 获取next的值,如果没有使用默认的reverse('goods:index')生成首页路径
                next_url = request.GET.get('next', reverse('goods:index'))

                # 跳转到首页
                response = redirect(next_url)

                # 判断用户是否需要记住用户名
                remember = request.POST.get('remember')
                # checkbox点击时的值是on
                if remember == "on":
                    # 设置cookie记住用户名('键',值,过期时间)response可以使HttpResponse和JsonResponse的对象
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    # 如果用户再次登录时不需要记住就将cookie删除
                    response.delete_cookie('username')
                return response
            else:
                error_message = "账户未激活"
                return render(request, 'login.html', locals())
        else:
            error_message = "用户名或密码错误"
            return render(request, 'login.html', locals())

    def get(self, request):
        # 查看用户登录状态,如果用户的session中包含islogin字段转到首页
        if request.session.has_key('is_login'):
            return redirect(reverse('goods:index'))
        # 因为是get请求所以在get方式里面设置
        if "username" in request.COOKIES:
            username = request.COOKIES["username"]
        else:
            username = ""
        return render(request, 'login.html', locals())


# 用户退出
class LogoutHandle(View):

    def get(self, request):
        # django为我们封装了一个注销登录的方法而且在注销登录的同时会将session的数据清除
        # 如果没有登录也不会报错
        logout(request)
        return redirect(reverse('goods:index'))


# 对于多继承首先在自己中查找再去第一个类中查找,直到查找第一个没有,因为在第一个中调用类方法就会去第二个查找
class UserInfoView(LoginRequiredMixin, View):
    """用户中心-信息页
    继承自LoginRequiredMixin这个调用login_required()方法的类就可以在路径里面直接写
    UserOrderView.as_view()不需要再次使用login_required()的方法
    """

    def get(self, request):
        """显示用户信息信息"""
        # 传入一个值来控制前端页面的active显示
        # 对于用户是否登录django有一个验证方法 django使用会话和中间件来拦截request对象到认证系统中
        # 他们在每个请求上提供request.user属性,表示当前的用户,如果当前用户没有登入,该属性设置成AnonymousUser的一个实例,否则它将是User的实例
        # 除了你给模板文件传递的模板变量之外,Django框架会把request.user也传给模板文件
        # 验证是否登录
        # request.user.is_authenticated()
        # 这个user要放到前面不然在用户提交的错误的时候没有address传入到前端页面
        # 用户在验证成功登录以后request自动包含user
        # 设置一个参数来定位用户点击页面传入到前端页面
        page = "user"
        user = request.user
        # try:
        #     # 验证用户是否已经有默认收货地址
        #     address = Address.objects.get(user=user, is_default=True)
        #
        # except Address.DoesNotExist:
        #     # 没有默认收货地址
        #     address = None
        # 在Address类里面封装了一个方法get_default_address
        address = Address.objects.get_default_address(user)

        # 获取用户浏览记录 正常的python与redis交互
        # from redis import StrictRedis
        # sr = StrictRedis(host="127.0.0.1:6379", port=6379, db=2)
        # sr.get()
        # 使用django-redis为我们封装好了一个方法返回StrictRedis对象
        # 在setting中我们使用缓存定义了SESSION_CACHE_ALIAS = "default",django就会自动帮我们链接到default定义的数据库中
        con = get_redis_connection('default')
        # 定义一个键值
        history_key = "history_%s" % user.id
        # 获取用户浏览的前5个商品的记录我们将浏览记录使用redis的list格式保存,如果美誉返回False
        sku_ids = con.lrange(history_key, 0, 4)
        # 定义一个列表记录用户的浏览记录,因为直接返回数据库的记录是按照id的循序返回的
        goods_li = []

        # 从数据库根据用户的sku_ids来查找对应的数据
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)

        # context = {
        #     'address': address,
        #     'goods_li': goods_li,
        # }
        return render(request, 'user_center_info.html', locals())


class UserOrderView(LoginRequiredMixin, View):
    """用户中心-订单页"""

    def get(self, request, page_num):
        """显示用户订单信息信息"""
        # 获取用户订单
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by("-create_time")

        # 遍历订单获取商品信息
        for order in orders:
            order_skus = OrderGoods.objects.filter(order=order.order_id).order_by("-create_time")

            # 遍历订单商品获取商品信息
            for order_sku in order_skus:
                # 计算商品小计
                amount = order_sku.price * order_sku.count
                # 动态给订单商品添加小计
                order_sku.amount = amount
            # 动态给订单增加属性,保存订单商品信息
            order.order_skus = order_skus
            # todo: 动态的给order属性添加一个商品订单状态
            order.order_status_name = OrderInfo.ORDER_STATUS_ENUM[order.order_status]
        # 获取分页参数:可迭代对象,分页数
        paginator = Paginator(orders, 2)

        # 校验页码
        try:
            page_num = int(page_num)
        except Exception as e:
            page_num = 1
        # 判断分页是否大于总页数
        if page_num > paginator.num_pages:
            page_num = 1

        # 获取page页的Page对象
        skus_page = paginator.page(page_num)

        # todo: 获取页码控制
        # 自定义页码的控制,页面上最多显示5页
        num_pages = paginator.num_pages
        # 1.总页数小于5页,页面上显示所有页码
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        # 2.如果当前页是前3页显示前5页
        elif page_num <= 3:
            pages = range(1, 6)
        # 3.如果当前页面是后3页显示后5页
        elif num_pages - page_num <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            # 正常情况下
            pages = range(page_num - 2, page_num + 3)
        page = "order"

        # 组织参数
        context = {
            "orders": orders,
            "page": page,
            "skus_page": skus_page,
            "pages": pages,
        }
        return render(request, "user_center_order.html", context)


class AddressView(LoginRequiredMixin, View):
    """用户中心-地址页"""

    def post(self, request):
        """添加收货地址"""
        # 获取用户输入
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        # 这个user要放到前面不然在用户提交的错误的时候没有address传入到前端页面
        # 用户在验证成功登录以后request自动包含user
        # 设置一个参数来定位用户点击页面传入到前端页面
        page = "address"
        user = request.user
        # try:
        #     # 验证用户是否已经有默认收货地址
        #     address = Address.objects.get(user=user, is_default=True)
        #
        # except Address.DoesNotExist:
        #     # 没有默认收货地址
        #     address = None
        # 在Address类里面封装了一个方法get_default_address
        address = Address.objects.get_default_address(user)
        # 验证用户是否合法
        if not all([receiver, addr, phone]):
            error_message = "信息填写不正确"
            return render(request, 'user_center_site.html', locals())

        # 如果匹配不到就会返回None,相当于None == None,如果有值就是False
        if not re.match(r"^1[3-9][0-9]{9}$", phone):
            error_message = "电话号码输入错误"
            return render(request, 'user_center_site.html', locals())

        if address:
            is_default = False
        else:
            is_default = True
        # 保存用户对于地址的输入
        Address.objects.create(user=user, receiver=receiver,
                               addr=addr, zip_code=zip_code,
                               phone=phone, is_default=is_default)

        return redirect(reverse("user:address"))

    def get(self, request):
        """显示用户地址信息信息"""
        page = "address"
        # 用户在验证成功登录以后request自动包含user
        user = request.user
        # try:
        #     # 验证用户是否已经有默认收货地址
        #     address = Address.objects.get(user=user, is_default=True)
        #
        # except Address.DoesNotExist:
        #     # 没有默认收货地址
        #     address = None
        address = Address.objects.get_default_address(user)
        return render(request, 'user_center_site.html', locals())
