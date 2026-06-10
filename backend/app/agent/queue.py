import asyncio
import json
import uuid

import redis.asyncio as redis

from app.agent.schemas import AgentEvent
from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)
_redis_pool = None

JOB_HISTORY_TTL = 86400  # 24 hours


def get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        password = settings.redis_password or None
        auth = f":{password}@" if password else ""
        _redis_pool = redis.ConnectionPool.from_url(
            f"redis://{auth}{settings.redis_host}:{settings.redis_port}",
            decode_responses=True,
        )
    return redis.Redis(connection_pool=_redis_pool)


async def enqueue(identifier: str) -> str:
    r = get_redis()
    job_id = str(uuid.uuid4())
    await r.lpush("job_queue", json.dumps({"job_id": job_id, "identifier": identifier}))
    return job_id


async def subscribe(job_id: str):
    r = get_redis()
    pubsub = r.pubsub()
    # M-1 fix: subscribe BEFORE reading history so no events are dropped in the gap.
    await pubsub.subscribe(f"job_events:{job_id}")
    try:
        past_events = await r.lrange(f"job_history:{job_id}", 0, -1)
        for ev_str in past_events:
            yield json.loads(ev_str)

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                yield data
                if data.get("type") in {"complete", "error"}:
                    break
    finally:
        await pubsub.unsubscribe(f"job_events:{job_id}")
        await pubsub.close()


async def worker_loop():
    from app.agent.runner import AgentRunner
    from app.search.indexes import ensure_indexes

    r = get_redis()
    await ensure_indexes()
    _bg_tasks: set[asyncio.Task] = set()
    log.info("queue.worker_started", msg="Waiting for jobs on Redis queue")
    while True:
        try:
            result = await r.brpop("job_queue", timeout=1)
            if result:
                _, data_str = result
                data = json.loads(data_str)
                job_id = data["job_id"]
                identifier = data["identifier"]
                log.info("queue.job_started", job_id=job_id)
                runner = AgentRunner(job_id, identifier)

                def _redis_publish(event: AgentEvent):
                    ev_dict = event.model_dump()
                    ev_str = json.dumps(ev_dict)

                    async def push(jid=job_id, estr=ev_str):  # noqa: B023
                        r2 = get_redis()
                        # H-1 fix: always refresh TTL so history expires after 24h.
                        pipe = r2.pipeline()
                        pipe.rpush(f"job_history:{jid}", estr)
                        pipe.expire(f"job_history:{jid}", JOB_HISTORY_TTL)
                        pipe.publish(f"job_events:{jid}", estr)
                        await pipe.execute()

                    t = asyncio.create_task(push())
                    _bg_tasks.add(t)
                    t.add_done_callback(_bg_tasks.discard)

                runner._publish = _redis_publish
                await runner.run()
                log.info("queue.job_finished", job_id=job_id)
        except Exception as e:
            log.exception("queue.worker_error", error=str(e))
            await asyncio.sleep(1)


if __name__ == "__main__":
    from app.logging import configure_logging

    configure_logging()
    asyncio.run(worker_loop())
