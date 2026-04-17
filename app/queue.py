from redis import Redis
from rq import Queue

from app.config import settings


def get_redis_connection() -> Redis:
    return Redis.from_url(settings.redis_url)


def get_queue() -> Queue:
    return Queue("submissions", connection=get_redis_connection())
