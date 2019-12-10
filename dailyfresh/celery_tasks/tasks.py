# 使用celery
from celery import Celery
from django.core.mail import EmailMultiAlternatives

# 重置文件
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")

application = get_wsgi_application()

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