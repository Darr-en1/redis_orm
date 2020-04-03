# redis orm 使用说明

## delete field
```python
# 删除单个field
model_instance._astra_fields[field_name]._remove()
# 删除model instance 删除 field
model_instance.remove()
```


#### BaseField 
包括 CharField...以及 ForeignKey

BaseField并不推荐直接删除field,可以通过重新赋值的方式改变field的value

针对BaseField  _remove()会将redis 中的key 删除

针对 OwnerForeignKey，不但会删除redis 中的key，
倘若 to 指定的是一个Model type,会一并将Model instance 删除

#### BaseCollection
包括 List,Set,SortedSet

删除方法还可以是: `model_instance.field_name = None`,
BaseCollection并不具备直接赋值，所以在重新赋值过程中，这种方式至关重要

针对 OwnerList,OwnerSet,会一并删除关联关系

#### BaseHash

**不允许**删除单个field,因为BaseHash 内部数据结构事hash,因此存在多个hash_field公用一个 redis key,
删除操作会直接删除其他field