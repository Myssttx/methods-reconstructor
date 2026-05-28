"""Elasticsearch client factory.

Supports two deployment modes:
  - Elastic Cloud:  set ELASTIC_CLOUD_ID + ELASTIC_API_KEY
  - Self-hosted:    set ELASTIC_URL (default: http://localhost:9200)

Both paths return an `elasticsearch.AsyncElasticsearch` instance. The
project pins client 8.15.1 to match the server image in docker-compose.
"""

from functools import lru_cache

from elasticsearch import AsyncElasticsearch

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)


@lru_cache
def get_es() -> AsyncElasticsearch:
    settings = get_settings()

    if settings.elastic_cloud_id and settings.elastic_api_key:
        log.info("elastic.connect", mode="cloud")
        return AsyncElasticsearch(
            cloud_id=settings.elastic_cloud_id,
            api_key=settings.elastic_api_key,
            request_timeout=30,
        )

    log.info("elastic.connect", mode="self_hosted", url=settings.elastic_url)
    return AsyncElasticsearch(
        hosts=[settings.elastic_url],
        request_timeout=30,
    )


async def close_es() -> None:
    es = get_es()
    await es.close()
