"""
Deep test harness: submits multiple arXiv papers to the live API and
collects scores + event logs for each.
"""
import asyncio
import json
import time
import httpx

PAPERS = [
    # scRNA-seq cancer genomics (review, no explicit methods header)
    ("arxiv:2005.01549", "Single-cell cancer genomics review"),
    # Concrete methods paper: CRISPR cancer screen
    ("arxiv:2206.12179", "Pancreatic cancer CRISPR screen"),
    # Breast cancer multi-omics
    ("arxiv:2303.05228", "Breast cancer multi-omics"),
]

BASE = "http://localhost:8000"
TIMEOUT = 600


from app.config import get_settings

async def run_paper(identifier: str, label: str) -> dict:
    t0 = time.time()
    result = {
        "label": label,
        "identifier": identifier,
        "events": [],
        "score": None,
        "n_claims": None,
        "n_gaps": None,
        "protocol_id": None,
        "error": None,
        "elapsed_s": None,
    }
    settings = get_settings()
    headers = {}
    if settings.api_key:
        headers["X-API-Key"] = settings.api_key
    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=TIMEOUT) as client:
        try:
            r = await client.post("/api/reconstructions", json={"identifier": identifier})
            r.raise_for_status()
            job = r.json()
            job_id = job["job_id"]
            result["job_id"] = job_id

            stream_url = job["stream_url"]
            if settings.api_key:
                stream_url += f"?api_key={settings.api_key}"

            async with client.stream("GET", stream_url) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        ev = json.loads(line[5:].strip())
                        result["events"].append(ev)
                        t = ev.get("type")
                        d = ev.get("data", {})
                        if t == "decompose":
                            result["n_claims"] = d.get("n_claims")
                        if t == "assemble":
                            result["score"] = d.get("score")
                            result["n_gaps"] = d.get("n_gaps")
                            result["protocol_id"] = d.get("protocol_id")
                        if t in {"complete", "error"}:
                            if t == "error":
                                result["error"] = d.get("message")
                            break
                    except Exception:
                        pass
        except Exception as e:
            result["error"] = str(e)
    result["elapsed_s"] = round(time.time() - t0, 1)
    return result


async def main():
    print(f"Running {len(PAPERS)} papers concurrently against {BASE}...\n")
    tasks = [run_paper(ident, label) for ident, label in PAPERS]
    results = await asyncio.gather(*tasks)

    print("\n" + "=" * 70)
    print("DEEP TEST RESULTS")
    print("=" * 70)
    for r in results:
        print(f"\nPaper : {r['label']}")
        print(f"ID    : {r['identifier']}")
        print(f"Time  : {r['elapsed_s']}s")
        print(f"Claims: {r['n_claims']}")
        print(f"Score : {r['score']}")
        print(f"Gaps  : {r['n_gaps']}")
        if r.get("error"):
            print(f"ERROR : {r['error']}")
        print(f"Events: {[e.get('type') for e in r['events']]}")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
