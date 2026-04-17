from redis import Redis
from rq import Connection, Worker

from app.bootstrap import init_db, init_storage, seed_example_problem
from app.config import settings
from app.db import SessionLocal


def main() -> None:
    init_storage()
    init_db()
    with SessionLocal() as db:
        seed_example_problem(db)

    redis = Redis.from_url(settings.redis_url)
    with Connection(redis):
        worker = Worker(["submissions"])
        worker.work()


if __name__ == "__main__":
    main()
