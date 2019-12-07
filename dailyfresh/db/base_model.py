from django.db import models


# 对于所有的模型类都共有的字段我们抽出来创建一个基类让所有的类都继承简化代码
class BaseModel(models.Model):
    """模型抽象基类"""
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    is_delete = models.BooleanField(default=False, verbose_name="删除标记")

    class Meta:
        # 表示这是一个抽象模型类
        abstract = True


