from redis import Redis
from rq import Worker, Queue

from app.config import settings

def main() -> None:
    redis_conn = Redis.from_url(settings.redis_url)

    queue = Queue("submissions", connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)

    worker.work()


if __name__ == "__main__":
    main()
