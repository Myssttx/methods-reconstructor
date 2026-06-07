import asyncio

import pytest

from app.agent.runner import AgentRunner


@pytest.mark.asyncio
async def test_runner_stream_fans_out_to_multiple_subscribers():
    runner = AgentRunner(job_id="fanout-test", identifier="fixture:paper_a")

    async def next_event():
        async for event in runner.stream():
            return event
        return None

    first = asyncio.create_task(next_event())
    second = asyncio.create_task(next_event())
    await asyncio.sleep(0)

    await runner._emit("status", {"message": "shared"})

    first_event, second_event = await asyncio.gather(first, second)
    assert first_event is not None and first_event.data["message"] == "shared"
    assert second_event is not None and second_event.data["message"] == "shared"
