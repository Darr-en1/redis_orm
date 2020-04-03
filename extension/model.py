import importlib

from astra import models, fields

# hash 对象会从缓冲中读取数据,所以得不到最新更新数据
from extension.execption import InstanceExistError, InstanceNotExistError
from extension.filter import obj_filter_by_field, field_key_without_pk_filter
from setting import redis_client

DIRECTLY_REDIS_HELPERS_SPLIT = "__"


def gen_primary_value(key):
    return redis_client.incr(key)


class CheckMeta(type):
    def __new__(cls, name, bases, namespace, **kwargs):
        if "model" in namespace and type(namespace["model"]) != str:
            raise TypeError('model type should be string')
        return type.__new__(cls, name, bases, namespace, **kwargs)


class BaseModel(models.Model, metaclass=CheckMeta):
    parent_pk = models.CharField()

    load = "__all__"

    def __init__(self, pk=None, **kwargs):
        if pk is None:
            pk = gen_primary_value(self.__class__.__name__)

        super().__init__(pk, **kwargs)
        if hasattr(self, "parent_pk") and getattr(self, "parent_pk"):
            self._check_parent()

    def _check_parent(self):
        if self.parent_pk is not None:
            elements = self.model.split('.', )
            imp_class = elements.pop()
            imp_module = '.'.join(elements)
            ip_module = importlib.import_module(imp_module)
            ip_module_cls = getattr(ip_module, imp_class)
            self.parent = ip_module_cls(pk=self.parent_pk)

    def get_db(self):
        return redis_client

    def __getattribute__(self, key):
        # When someone request _astra_fields, then start lazy loading...
        if key == '_astra_fields' and not self._astra_fields_loaded:
            self._astra_load_fields()

        # Keys + some internal methods
        if key.startswith('_astra_') or key == '__class__':
            return object.__getattribute__(self, key)

        if key in self._astra_fields:
            field = self._astra_fields[key]
            return field._obtain()

        # If key is not in the fields, we're attempt call helper
        # Ex. "user.login__strlen" call redis "strlen" method on "login" field
        key_elements = key.split(DIRECTLY_REDIS_HELPERS_SPLIT, )
        method_name = key_elements.pop()
        field_name = DIRECTLY_REDIS_HELPERS_SPLIT.join(key_elements)
        if field_name in self._astra_fields:
            field = self._astra_fields[field_name]
            return field._helper(method_name)

        # Otherwise, default behavior:
        return object.__getattribute__(self, key)

    def hash_exist(self):
        """
        用于判断是否有hash对象
        :return:
        """

        return True if super().hash_exist() == 1 else False

    def exist(self):
        """
        用于判断对象是否存在
        :return:
        """
        check_hash_field = False

        for field in self._astra_fields.values():

            if isinstance(field, fields.BaseHash):
                if not check_hash_field:

                    check_hash_field = True

                    hash_key = f"{self._astra_prefix}::{self.__class__.__name__.lower()}::hash::{self.pk}"

                    if self._astra_get_db().exists(hash_key):
                        return True

            elif self._astra_get_db().exists(field._get_key_name()):
                return True
        return False

    @classmethod
    def _get_pk_list(cls) -> list:
        pk_set = set()

        hash_load = False  # 确保hash field 只加载一次

        for arg in dir(cls):

            val = getattr(cls, arg)
            if isinstance(val, fields.ModelField):
                if isinstance(val, fields.BaseHash):
                    if not hash_load:
                        for filter_fields in redis_client.keys(
                                obj_filter_by_field.format(cls=cls.__name__.lower(), field=val._field_type_name)):
                            pk_set.add(filter_fields.split("::")[-1])

                        hash_load = True
                else:
                    for filter_fields in redis_client.keys(
                            field_key_without_pk_filter.format(cls=cls.__name__.lower(),
                                                               field_type=val._field_type_name,
                                                               field_name=arg)):
                        pk_set.add(filter_fields.split("::")[-2])

        return list(pk_set)

    @classmethod
    def all(cls, **kwargs):
        instance_list = [cls(pk=pk) for pk in cls._get_pk_list()]

        # def parse(val):
        #     return True if val == "true" else False if val == "false" else val

        filter_instance_list = []
        for instance in instance_list:
            comparison = True  # 参数值都正确则写入filter_instance_list
            for k, v in kwargs.items():
                result = getattr(instance, k)
                if isinstance(result, fields.BaseCollection):
                    raise TypeError("filter key cannot be an fields.BaseCollection type")
                if str(result) != v:
                    comparison = False
                    break
            if comparison:
                filter_instance_list.append(instance)
        return filter_instance_list

    def json(self):
        result = {}
        for field_name in [*self._astra_fields.keys(), "pk"]:
            if isinstance(self.load, tuple):
                if field_name not in self.load:
                    continue
            val = getattr(self, field_name)
            if isinstance(val, BaseModel):
                result[field_name] = val.json()

            elif isinstance(val, models.List):
                result[field_name] = [v.json() if isinstance(v, BaseModel) else v for v in val]

            elif isinstance(val, models.Set):
                result[field_name] = [v.json() if isinstance(v, BaseModel) else v for v in val.smembers()]

            elif isinstance(val, models.SortedSet):
                pass
            else:
                if val:
                    result[field_name] = val
        return result

    @classmethod
    def create(cls, **kwargs):
        pk = kwargs.pop("pk", None)
        if pk is None:
            pk = gen_primary_value(cls.__name__)
        if cls(pk=pk).exist():
            raise InstanceExistError()
        return cls(pk, **kwargs)

    @classmethod
    def update(cls, **kwargs):
        pk = kwargs.pop("pk")
        if not cls(pk=pk).exist():
            raise InstanceNotExistError()
        return cls(pk, **kwargs)
