from astra import models, fields
from astra.fields import ModelField
from astra.models import List, ForeignKey, Set

from extension.validators import DictValidatorMixin, OwnerDateTimeValidatorMixin, \
    BaseCollectionTypeValidatorMixin


class OwnerList(BaseCollectionTypeValidatorMixin, List):
    _write_operation = ('linsert', 'lpop', 'lpush',
                        'lpushx', 'lset', 'rpop',
                        'rpoplpush', 'rpush', 'rpushx',)

    # https://www.zhihu.com/question/44015086
    def __getitem__(self, item):
        res = super().__getitem__(item)
        if res is None:
            raise StopIteration
        return res

    def _remove(self):
        for inner_item in self:
            if isinstance(inner_item, models.Model):
                inner_item.remove()
        super()._remove()


class OwnerSet(BaseCollectionTypeValidatorMixin, Set):
    _write_operation = ('sadd', 'smove', 'srem',)

    def _remove(self):
        for inner_item in self.smembers():
            if isinstance(inner_item, models.Model):
                inner_item.remove()
        super()._remove()


class OwnerForeignKey(ForeignKey):
    def _remove(self):
        # _obtain:  get ForeignKey  model class instance
        foreign_model_instance = self._obtain()  # get the model object corresponding to the foreign key
        if foreign_model_instance:  # null indicates that there is no foreign key association
            self._obtain().remove()
        super()._remove()


# class OwnerIntegerList(List):
#     # https://www.zhihu.com/question/44015086
#     def __getitem__(self, item):
#         res = super().__getitem__(item)
#         if res is None:
#             raise StopIteration
#         try:
#             return int(res)
#         except ValueError:
#             raise ValueError('Invalid type of field %s: %s. Expected is int' %
#                              (self._name, type(res).__name__))


class N0CacheMixin:
    def _load_hash(self: ModelField):
        self._model._astra_hash_loaded = True
        self._model._astra_hash = \
            self._model._astra_get_db().hgetall(
                self._get_key_name(True))
        if not self._model._astra_hash:
            self._model._astra_hash = {}
            self._model._astra_hash_exist = False
        else:
            self._model._astra_hash_exist = True


# N0CacheMixin 必须的放置到前面,根据继承原则才会执行它
class OwnerBooleanHash(N0CacheMixin, models.BooleanHash):
    pass


class DictField(DictValidatorMixin, fields.BaseField):
    _directly_redis_helpers = (
        'setex', 'setnx', 'expire', 'ttl')  # 该框架使用redis自带方法默认没有对输入参数做类型检验 example：setnx（str）而不是dict 因为不走validator


class OwnerDateTimeField(OwnerDateTimeValidatorMixin, fields.BaseField):
    _directly_redis_helpers = ('setex', 'setnx', 'expire', 'ttl',)
