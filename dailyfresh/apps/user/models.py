from django.contrib.auth.models import AbstractUser
from django.db import models
from db.base_model import BaseModel


# Create your models here.
# 多重继承AbstractUser是Django自带的用户模块
class User(AbstractUser, BaseModel):
    """用户模型类"""

    class Meta:
        db_table = 'df_user'
        verbose_name = "用户"
        verbose_name_plural = verbose_name

class AddressManager(models.Manager):
    """地址模型管理类"""
    # 1.改变原有查询集结果从新定义方法 def all(self):
    # 2.封装方法:用户操作模型类对应的数据表(增删改查)

    def get_default_address(self, user):
        """获取默认收货地址对象"""
        # self.model:获取self所在的模型类,即使模型类变化也没有关系
        # 调用的时候为Address.objects.get_default_address 所以在这里直接使用self,因为objects就是models.Manages实例对象
        try:
            # 验证用户是否已经有默认收货地址
            address = self.get(user=user, is_default=True)

        # 使用self.model.DoesNotExist来创建错误
        except self.model.DoesNotExist:
            # 没有默认收货地址
            address = None

        return address


class Address(BaseModel):
    """地址模型类"""
    user = models.ForeignKey('User', on_delete=models.CASCADE, verbose_name="所属账户")
    receiver = models.CharField(max_length=20, verbose_name="收件人")
    addr = models.CharField(max_length=256, verbose_name="收件地址")
    zip_code = models.CharField(max_length=6, null=True, verbose_name="邮政编码")
    phone = models.CharField(max_length=11, verbose_name="联系电话")
    is_default = models.BooleanField(default=False, verbose_name="是否默认")

    # 自定义一个模型类管理对象
    objects = AddressManager()
    class Meta:
        db_table = 'df_address'
        verbose_name = "地址"
        verbose_name_plural = verbose_name
