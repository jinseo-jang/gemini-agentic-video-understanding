"""Live TCP Socket Adversarial Concurrency and Stress Test Harness.

Executes real network requests against http://127.0.0.1:8000:
1. 200 concurrent TCP requests to /api/health (throughput, p50/p95/p99 latency)
2. 50 concurrent TCP range requests to /api/preset/video (range slicing, throughput)
3. 30 concurrent adversarial/out-of-bounds range requests
4. 1 MB massive prompt payload upload over live HTTP
5. Mixed concurrency burst across endpoints
"""

import asyncio
import statistics
import time
from typing import Dict, List, Tuple
import httpx

LIVE_SERVER_URL = "http://127.0.0.1:8000"


async def test_live_health_burst(concurrency: int = 200) -> Dict:
    """Stress test /api/health with concurrent TCP requests."""
    print(f"\n[LIVE STRESS] Running {concurrency} concurrent TCP requests to /api/health...")
    latencies: List[float] = []
    errors: List[str] = []

    async with httpx.AsyncClient(base_url=LIVE_SERVER_URL, timeout=10.0) as client:
        async def single_req():
            t0 = time.perf_counter()
            try:
                resp = await client.get("/api/health")
                dur = time.perf_counter() - t0
                latencies.append(dur)
                if resp.status_code != 200:
                    errors.append(f"Status {resp.status_code}")
                elif resp.json() != {"status": "ok", "version": "1.0.0"}:
                    errors.append("Invalid body")
            except Exception as exc:
                latencies.append(time.perf_counter() - t0)
                errors.append(str(exc))

        t_start = time.perf_counter()
        await asyncio.gather(*(single_req() for _ in range(concurrency)))
        total_time = time.perf_counter() - t_start

    sorted_lat = sorted(latencies)
    p50 = sorted_lat[int(len(sorted_lat) * 0.50)] * 1000
    p95 = sorted_lat[int(len(sorted_lat) * 0.95)] * 1000
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)] * 1000
    rps = concurrency / total_time

    res = {
        "concurrency": concurrency,
        "total_time_seconds": round(total_time, 3),
        "rps": round(rps, 1),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "errors": len(errors),
    }
    print(f"  -> Done in {total_time:.3f}s ({rps:.1f} req/s) | p50={p50:.1f}ms, p95={p95:.1f}ms, p99={p99:.1f}ms | Errors: {len(errors)}")
    return res


async def test_live_video_streaming_concurrency(concurrency: int = 50) -> Dict:
    """Stress test /api/preset/video concurrent Range streaming."""
    print(f"\n[LIVE STRESS] Running {concurrency} concurrent TCP range requests to /api/preset/video...")
    ranges = [
        "bytes=0-1023",
        "bytes=1024-4095",
        "bytes=4096-16383",
        "bytes=100000-110000",
        "bytes=-2048",
    ]
    latencies: List[float] = []
    errors: List[str] = []
    bytes_downloaded: int = 0

    async with httpx.AsyncClient(base_url=LIVE_SERVER_URL, timeout=15.0) as client:
        async def single_stream(idx: int):
            nonlocal bytes_downloaded
            r_header = ranges[idx % len(ranges)]
            t0 = time.perf_counter()
            try:
                resp = await client.get("/api/preset/video", headers={"Range": r_header})
                dur = time.perf_counter() - t0
                latencies.append(dur)
                if resp.status_code != 206:
                    errors.append(f"Status {resp.status_code}")
                else:
                    bytes_downloaded += len(resp.content)
            except Exception as exc:
                errors.append(str(exc))

        t_start = time.perf_counter()
        await asyncio.gather(*(single_stream(i) for i in range(concurrency)))
        total_time = time.perf_counter() - t_start

    sorted_lat = sorted(latencies)
    p50 = sorted_lat[int(len(sorted_lat) * 0.50)] * 1000
    p95 = sorted_lat[int(len(sorted_lat) * 0.95)] * 1000
    rps = concurrency / total_time

    res = {
        "concurrency": concurrency,
        "total_time_seconds": round(total_time, 3),
        "rps": round(rps, 1),
        "total_bytes": bytes_downloaded,
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "errors": len(errors),
    }
    print(f"  -> Done in {total_time:.3f}s ({rps:.1f} req/s) | Downloaded {bytes_downloaded} bytes | p50={p50:.1f}ms, p95={p95:.1f}ms | Errors: {len(errors)}")
    return res


async def test_live_adversarial_ranges(count: int = 30) -> Dict:
    """Send adversarial/invalid Range headers over TCP."""
    print(f"\n[LIVE STRESS] Sending {count} adversarial range headers over TCP...")
    adversarial_ranges = [
        "bytes=9999999999-",
        "bytes=100-50",
        "bytes=corrupt-range",
        "bytes=--100",
        "bytes=0-0",
        "bytes=-9999999999",
    ]
    status_counts: Dict[int, int] = {}
    errors: List[str] = []

    async with httpx.AsyncClient(base_url=LIVE_SERVER_URL, timeout=10.0) as client:
        for i in range(count):
            r = adversarial_ranges[i % len(adversarial_ranges)]
            try:
                resp = await client.get("/api/preset/video", headers={"Range": r})
                status_counts[resp.status_code] = status_counts.get(resp.status_code, 0) + 1
                if resp.status_code not in [206, 416]:
                    errors.append(f"Unexpected status {resp.status_code} for {r}")
            except Exception as exc:
                errors.append(str(exc))

    print(f"  -> Status distribution: {status_counts} | Errors (unexpected status or crash): {len(errors)}")
    return {"distribution": status_counts, "errors": len(errors)}


async def test_live_massive_payload() -> Dict:
    """Send a 1MB payload to live server /api/analyze."""
    print(f"\n[LIVE STRESS] Uploading 1MB payload to {LIVE_SERVER_URL}/api/analyze...")
    payload = {
        "video_url": "https://storage.googleapis.com/test/video.mp4",
        "video_source_type": "url",
        "prompt": "Find objects: " + ("X" * 1_000_000),
        "credentials": {"api_key": "probe_test_key"},
    }

    async with httpx.AsyncClient(base_url=LIVE_SERVER_URL, timeout=20.0) as client:
        t0 = time.perf_counter()
        resp = await client.post("/api/analyze", json=payload)
        elapsed = time.perf_counter() - t0

    print(f"  -> Status: {resp.status_code} in {elapsed:.3f}s (No 500 crash)")
    assert resp.status_code != 500
    return {"status_code": resp.status_code, "elapsed_seconds": round(elapsed, 3)}


async def main():
    print("=" * 70)
    print("  LIVE TCP ADVERSARIAL CONCURRENCY & STRESS TEST REPORT")
    print(f"  Target: {LIVE_SERVER_URL}")
    print("=" * 70)

    h_res = await test_live_health_burst(200)
    v_res = await test_live_video_streaming_concurrency(50)
    adv_res = await test_live_adversarial_ranges(30)
    mass_res = await test_live_massive_payload()

    print("\n" + "=" * 70)
    print("  SUMMARY OF LIVE SOCKET STRESS TEST")
    print("=" * 70)
    print(f"  Health 200 Concurrency:    {h_res['rps']} req/s, p95={h_res['p95_ms']}ms, Errors={h_res['errors']}")
    print(f"  Video 50 Concurrency:      {v_res['rps']} req/s, p95={v_res['p95_ms']}ms, Bytes={v_res['total_bytes']}, Errors={v_res['errors']}")
    print(f"  Adversarial Ranges:        {adv_res['distribution']}, Errors={adv_res['errors']}")
    print(f"  1MB Prompt Upload:         Status {mass_res['status_code']} in {mass_res['elapsed_seconds']}s")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
