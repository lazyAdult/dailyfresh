from django.core.files.storage import Storage
# 导入django的存储类
from fdfs_client.client import Fdfs_client

from dailyfresh import settings


class FfdsStorage(Storage):
    """fast dfs文件存储类"""

    def __init__(self, client_conf=None, base_url=None):
        """重写init方法方便调用配置"""
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf

        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url = base_url

    def _open(self, name, mode='rb'):
        """打开文件时使用"""
        pass

    def _save(self, name, content):
        """保存文件时使用"""
        # name:你选择上传文件时使用的名字
        # content:包含你上传文件时内容的file对象

        # 创建一个Fdfs_client对象
        client = Fdfs_client(self.client_conf)

        # 上传到fast dfs系统中
        res = client.upload_by_buffer(content.read())

        # 返回一个字典
        # dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }

        # 判断上传是否成功
        if res.get("Status") != "Upload successed.":

            # 失败返回提示
            raise Exception("上传文件到fast dfs失败")

        # 上传成功返回Remote file_id标识返回在fast dfs的存储标识
        file_name = res.get("Remote file_id")
        return file_name

    # 判断文件名是否存在 使用exists()方法如果提供的名称的文件在文件系统中已经存在,则返回True,否则这个名称就可以用于新文件,返回Fales
    def exists(self, name):
        return False

    def url(self, name):
        """

        :param name: 被访问文件的内容
        :return:
        """
        # 返回URl:通过它可以反问道name所引用的文件,对于不支持URl访问的存储系统,抛出NotImplementedError异常
        return self.base_url + name
