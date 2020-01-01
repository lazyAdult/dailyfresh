# 使用celery
from celery import Celery
from django.core.mail import EmailMultiAlternatives
from django.template import loader, RequestContext

from dailyfresh import settings


# 重置文件
import os
# 导入django
import django
#
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")

# django初始化
# django.setup()

# 导入的模型类文件一定要在初始化方法下部,不然就会报错
from apps.goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner


# 创建一个Celery类的实例对象
# 第一个参数按照规范一般传入文件的路径 celery通过borker自动连接worker


app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/1')
# app = Celery('celery_tasks.tasks', broker='redis://192.168.1.16:6379/1')


# 定义任务函数
@app.task       # 使用task函数进行装饰
def send_mails(email, sender_mes, username, token):
    # 邮件主题
    subject = "天天生鲜欢迎您%s" % sender_mes
    to = [email]
    sender = sender_mes
    text_content = "%s 欢迎访问天天生鲜官网" % username
    html_content = """<p>{}欢迎访问天天生鲜官网</p><p><a href="http://127.0.0.1:8000/user/active/{}">请点击确认完成注册</a></p>
                    <p>此链接有效时间为一个小时</p>""".format(username, token)
    msg = EmailMultiAlternatives(subject, text_content, sender, to)
    # 设置如果html文本发送失败使用文档
    msg.attach_alternative(html_content, 'text/html')
    msg.send()


# 创建一个任务来生成静态页面
@app.task
def generate_static_index_html():
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

    # 加载静态文件
    # 因为不要验证用户是否登录需要从新创建一个模板文件来生成静态首页
    temp = loader.get_template("static_index.html")
    # 定义模板上下文   我们这里不要是使用request
    # context = RequestContext(request, context)
    # 直接传入context进行模板渲染生成静态文件,返回模板对象
    static_index_html = temp.render(context)

    # 生成首页对应的静态文件
    # 设置生成静态文件路径
    static_path = os.path.join(settings.BASE_DIR, "static/index.html")
    with open(static_path, "w") as f:
        f.write(static_index_html)
