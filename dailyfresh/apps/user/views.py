import re

from django.contrib.auth import authenticate, login
from django.http import HttpResponse
from django.shortcuts import render, redirect

# Create your views here.
from django.urls import reverse
from django.views import View
from itsdangerous import SignatureExpired
from celery_tasks import tasks
from apps.user.diy_views import HidenMessage
from apps.user.models import User
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
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
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
        return render(request, 'login.html')


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

                # 跳转到首页
                response = redirect(reverse('goods:index'))

                # 判断用户是否需要记住用户名
                remember = request.POST.get('remember')
                # checkbox点击时的值是on
                if remember == "on":
                    # 设置cookie记住用户名('键',值,过期时间)
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    # 如果用户再次登录时不需要记住就将cookie删除
                    response.delete_cookie('username')
                return response
            else:
                error_message = "账户未激活"
        else:
            error_message = "用户名或密码错误"
        return render(request, 'login.html', locals())

    def get(self, request):
        # 因为是get请求所以在get方式里面设置
        if "username" in request.COOKIES:
            username = request.COOKIES["username"]
        else:
            username = ""
        return render(request, 'login.html', locals())
