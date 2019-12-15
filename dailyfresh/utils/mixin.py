# 对于一些公共的方法封装到一个包里面
from django.contrib.auth.decorators import login_required


class LoginRequiredMixin(object):
    # 因为在验证路径时要使用as_view方法,所以使用as_view方法按照View类中as_view 和view
    @classmethod
    def as_view(cls, **initkwargs):
        # 调用父类的方法as_view
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)