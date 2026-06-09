import asyncio
import json
import uuid
import redis.asyncio as redis
from app.config import get_settings
from app.logging import get_logger
from app.agent.schemas import AgentEvent

log = get_logger(__name__)
_redis_pool = None

def get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = redis.ConnectionPool.from_url(f"redis://{settings.redis_host}:{settings.redis_port}", decode_responses=True)
    return redis.Redis(connection_pool=_redis_pool)

async def enqueue(identifier: str) -> str:
    r = get_redis()
    job_id = str(uuid.uuid4())
    await r.lpush("job_queue", json.dumps({"job_id": job_id, "identifier": identifier}))
    return job_id

async def subscribe(job_id: str):
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(f"job_events:{job_id}")
    try:
        # Yield past events so the UI instantly catches up
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
                
                # Intercept the memory publish and reroute to Redis!
                def _redis_publish(event: AgentEvent):
                    ev_dict = event.model_dump()
                    ev_str = json.dumps(ev_dict)
                    async def push():
                        r2 = get_redis()
                        await r2.rpush(f"job_history:{job_id}", ev_str)
                        await r2.publish(f"job_events:{job_id}", ev_str)
                    asyncio.create_task(push())
                
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
