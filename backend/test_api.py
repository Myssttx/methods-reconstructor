import asyncio
import httpx
import json

from app.config import get_settings

async def test_api():
    print("Testing API and Worker End-to-End...")
    settings = get_settings()
    headers = {}
    if settings.api_key:
        headers["X-API-Key"] = settings.api_key
    async with httpx.AsyncClient(base_url="http://localhost:8000", headers=headers, timeout=600.0) as client:
        print("Submitting arxiv:2111.08202...")
        r = await client.post("/api/reconstructions", json={"identifier": "arxiv:2111.08202"})
        r.raise_for_status()
        data = r.json()
        job_id = data["job_id"]
        print(f"Success! Job Enqueued with ID: {job_id}")
        
        # If API_KEY is set, make sure to append it to the stream URL as query param since EventSource/stream client might require it
        stream_url = data['stream_url']
        if settings.api_key:
            stream_url += f"?api_key={settings.api_key}"
        print(f"Connecting to stream: {stream_url}")
        
        async with client.stream("GET", stream_url) as response:
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    try:
                        event = json.loads(data_str)
                        print(f"[{event.get('type')}] {event.get('data')}")
                        if event.get('type') in {"complete", "error"}:
                            break
                    except Exception as e:
                        print(f"Error parsing: {data_str}")

if __name__ == "__main__":
    asyncio.run(test_api())
