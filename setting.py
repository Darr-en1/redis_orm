from redis import StrictRedis, ConnectionPool

from extension.local import REDIS_URL

DEFAULT_DATE_TIME_FORMAT = "%Y_%m_%d_%H_%M_%S"
redis_client = StrictRedis(connection_pool=ConnectionPool.from_url(REDIS_URL, decode_responses=True))
