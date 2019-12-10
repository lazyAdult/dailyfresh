from django.core.mail import EmailMultiAlternatives
from itsdangerous import TimedJSONWebSignatureSerializer as Secret

# def make_secret(key, id, time):
#     """自定义方法加密信息"""
#     # 激活连接中需要包含用户的信息
#     secret = Secret(key, time)
#     info = {'comfire': id}
#     token = secret.dumps(info)      # 返回一个bytes类型
#     token.decode()      # 解码默认是utf-8
#     return token


# def send_mails(email, sender_mes, username, token):
#     # 邮件主题
#     subject = "天天生鲜欢迎您%s" % sender_mes
#     to = [email]
#     sender = sender_mes
#     text_content = "%s 欢迎访问天天生鲜官网" % username
#     html_content = """<p>{}欢迎访问天天生鲜官网</p><p><a href="http://127.0.0.1:8000/user/active/{}">请点击确认完成注册</a></p>
#                     <p>此链接有效时间为一个小时</p>""".format(username, token)
#     msg = EmailMultiAlternatives(subject, text_content, sender, to)
#     # 设置如果html文本发送失败使用文档
#     msg.attach_alternative(html_content, 'text/html')
#     msg.send()


class HidenMessage(object):
    """加/解密类"""

    def __init__(self, key, time, id=None, code=None):
        self.id = id
        self.code = code
        self.secret = Secret(key, time)

    def make_secret(self):
        """加密方法"""
        # 激活连接中需要包含用户的信息
        info = {'confirm': self.id}
        token = self.secret.dumps(info)  # 返回一个bytes类型
        # token.decode()  # 解码默认是utf8
        return token

    def load_secret(self):
        """解密方法"""
        code = self.secret.loads(self.code)
        return code