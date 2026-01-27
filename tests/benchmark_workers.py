#!/usr/bin/env python3
"""
Benchmark script to test multi-process worker performance.
Compares single-process vs multi-process proxy throughput.
"""
import subprocess
import time
import sys
import os
import signal
import asyncio
import aiohttp

# Test configuration
PROXY_PORT = 19090
NUM_REQUESTS = 100
CONCURRENT_REQUESTS = 20
TEST_URL = 'http://httpbin.org/get'

async def make_request(session, proxy_url):
    """Make a single request through the proxy."""
    start = time.perf_counter()
    try:
        async with session.get(TEST_URL, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            await resp.read()
            return time.perf_counter() - start, True
    except Exception as e:
        return time.perf_counter() - start, False

async def benchmark_proxy(proxy_url, num_requests, concurrent):
    """Benchmark the proxy with concurrent requests."""
    connector = aiohttp.TCPConnector(limit=concurrent)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Warm up
        await make_request(session, proxy_url)

        # Run benchmark
        start = time.perf_counter()
        tasks = [make_request(session, proxy_url) for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start

        successful = sum(1 for _, ok in results if ok)
        times = [t for t, ok in results if ok]

        return {
            'total_time': total_time,
            'successful': successful,
            'failed': num_requests - successful,
            'avg_latency': sum(times) / len(times) if times else 0,
            'min_latency': min(times) if times else 0,
            'max_latency': max(times) if times else 0,
            'requests_per_sec': successful / total_time if total_time > 0 else 0
        }

def start_proxy(workers=1):
    """Start the proxy server."""
    cmd = [sys.executable, '-m', 'pproxy', '-l', f'http+socks5://:{PROXY_PORT}']
    if workers > 1:
        cmd.extend(['--workers', str(workers)])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    time.sleep(3)  # Wait for proxy to start
    return proc

def stop_proxy(proc):
    """Stop the proxy server."""
    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        # Kill any child processes
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except:
            pass

def print_results(name, results):
    """Print benchmark results."""
    print(f"\n{name}:")
    print(f"  Total time: {results['total_time']:.2f}s")
    print(f"  Successful: {results['successful']}/{results['successful'] + results['failed']}")
    print(f"  Requests/sec: {results['requests_per_sec']:.2f}")
    print(f"  Avg latency: {results['avg_latency']*1000:.2f}ms")
    print(f"  Min latency: {results['min_latency']*1000:.2f}ms")
    print(f"  Max latency: {results['max_latency']*1000:.2f}ms")

async def main():
    print("=" * 60)
    print("Multi-Process Worker Benchmark")
    print("=" * 60)
    print(f"Requests: {NUM_REQUESTS}")
    print(f"Concurrent: {CONCURRENT_REQUESTS}")
    print(f"Test URL: {TEST_URL}")

    proxy_url = f'http://localhost:{PROXY_PORT}'
    results_all = {}

    # Test with 1 worker
    print("\n--- Testing with 1 worker ---")
    proc = start_proxy(workers=1)
    try:
        results_all['1 worker'] = await benchmark_proxy(proxy_url, NUM_REQUESTS, CONCURRENT_REQUESTS)
        print_results("1 Worker", results_all['1 worker'])
    finally:
        stop_proxy(proc)

    time.sleep(2)

    # Test with 2 workers
    print("\n--- Testing with 2 workers ---")
    proc = start_proxy(workers=2)
    try:
        results_all['2 workers'] = await benchmark_proxy(proxy_url, NUM_REQUESTS, CONCURRENT_REQUESTS)
        print_results("2 Workers", results_all['2 workers'])
    finally:
        stop_proxy(proc)

    time.sleep(2)

    # Test with 4 workers
    print("\n--- Testing with 4 workers ---")
    proc = start_proxy(workers=4)
    try:
        results_all['4 workers'] = await benchmark_proxy(proxy_url, NUM_REQUESTS, CONCURRENT_REQUESTS)
        print_results("4 Workers", results_all['4 workers'])
    finally:
        stop_proxy(proc)

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    baseline = results_all['1 worker']['requests_per_sec']
    for name, results in results_all.items():
        speedup = results['requests_per_sec'] / baseline if baseline > 0 else 0
        print(f"{name}: {results['requests_per_sec']:.2f} req/s ({speedup:.2f}x)")

if __name__ == '__main__':
    try:
        import aiohttp
    except ImportError:
        print("Please install aiohttp: pip install aiohttp")
        sys.exit(1)

    asyncio.run(main())
