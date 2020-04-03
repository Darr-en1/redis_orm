import datetime as dt
import json
from types import MethodType

from astra import fields

from setting import DEFAULT_DATE_TIME_FORMAT


class DictValidatorMixin(object):
    def _validate(self, value):
        if not isinstance(value, dict):
            raise ValueError('Invalid type of field %s: %s.' %
                             (self._name, type(value).__name__))
        return json.dumps(value)

    def _convert(self, value):
        if value is None:
            return {}
        try:
            return json.loads(value)
        except ValueError:
            return {}


class OwnerDateTimeValidatorMixin:
    def _validate(self, value):
        if not isinstance(value, dt.datetime) and not \
                isinstance(value, dt.date):
            raise ValueError('Invalid type of field %s: %s. Expected '
                             'is datetime.datetime or datetime.date' %
                             (self._name, type(value).__name__))

        return value.strftime(DEFAULT_DATE_TIME_FORMAT)

    def _convert(self, value):
        if value is None or not isinstance(value, str):
            return None
        try:
            return dt.datetime.strptime(value, DEFAULT_DATE_TIME_FORMAT)
        except ValueError:
            return None


class BaseCollectionTypeValidatorMixin:
    def __getattr__(self, item):
        if item not in self._allowed_redis_methods:
            return super().__getattribute__(item)

        original_command = getattr(self._model._astra_get_db(), item)
        current_key = self._get_key_name()

        def _method_wrapper(*args, **kwargs):
            from astra import models

            # Scan passed args and convert to pk if passed models
            new_args = [current_key]
            new_kwargs = dict()
            for v in args:
                if item in self._write_operation:
                    # 确保写入的内容 和to 的 内容类型一致
                    # _to 如果是<class 'method'> 说明to没有被指定t,默认str
                    if type(self._to) != MethodType:
                        if isinstance(v, fields.ModelField):  # 存在一些指令需要多个field 组合 如：list 中的 rpoplpush set 中的smove 等
                            v = v._get_key_name()
                        elif self._to != v.__class__:
                            raise TypeError(
                                f"expect {self._to} but enter {v.__class__}")
                    elif not isinstance(v, str):
                        raise TypeError("The default write type is str")

                new_args.append(v.pk if isinstance(v, models.Model) else v)
            for k, v in kwargs.items():
                new_kwargs[k] = v.pk if isinstance(v, models.Model) else v

            # Call original method on the database
            answer = original_command(*new_args, **new_kwargs)

            # Wrap to model
            if item in self._single_object_answered_redis_methods:
                return None if not answer else self._to(answer)

            if item in self._list_answered_redis_methods:
                wrapper_answer = []
                for pk in answer:
                    if not pk:
                        wrapper_answer.append(None)
                    else:
                        if isinstance(pk, tuple) and len(pk) > 0:
                            wrapper_answer.append((self._to(pk[0]), pk[1]))
                        else:
                            wrapper_answer.append(self._to(pk))

                return wrapper_answer
            return answer  # Direct answer

        return _method_wrapper
