# 引入haystack模块中的indexes函数
from haystack import indexes
# 引入需要建立索引的模型类
from apps.goods.models import GoodsSKU


# 指定对于 具体类 下的 具体属性 建立索引
# 通常索引类名格式: 模型类名 + Index
class GoodsSKUIndex(indexes.SearchIndex, indexes.Indexable):
    """索引类, 继承与indexes的SearchIndex和Indexable类"""

    # 定义text值
    # 其中,索引字段 use_template=True指定根据表中的那些字段建立索引文件的说明放在一个文件中
    text = indexes.CharField(document=True, use_template=True)

    # 获取模型类
    def get_model(self):
        # 返回模型类
        return GoodsSKU

    # 获得所需要建立索引的数据
    def index_queryset(self, using=None):
        return self.get_model().objects.all()  # 查询该模型类下所有数据
