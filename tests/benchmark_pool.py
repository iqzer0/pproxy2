#!/usr/bin/env python3
"""
Benchmark script to test connection pooling effectiveness.
Tests direct TCP connection time with and without pooling.
"""
import asyncio
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pproxy.server import CONNECTION_POOL

# Target for testing - httpbin.org or a local server
TEST_HOST = 'httpbin.org'
TEST_PORT = 80
NUM_CONNECTIONS = 50

async def benchmark_no_pool():
    """Benchmark creating fresh connections each time."""
    times = []
    for i in range(NUM_CONNECTIONS):
        start = time.perf_counter()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(TEST_HOST, TEST_PORT),
                timeout=10
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        except Exception as e:
            print(f"  Connection {i+1} failed: {e}")
    return times

async def benchmark_with_pool():
    """Benchmark with connection pooling - return connections to pool."""
    times = []
    for i in range(NUM_CONNECTIONS):
        start = time.perf_counter()
        try:
            # Try pool first
            pooled = await CONNECTION_POOL.get(TEST_HOST, TEST_PORT)
            if pooled:
                reader, writer = pooled
                elapsed = time.perf_counter() - start
                times.append(elapsed)
                # Return to pool for next iteration
                await CONNECTION_POOL.put(TEST_HOST, TEST_PORT, reader, writer)
            else:
                # Create new connection
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(TEST_HOST, TEST_PORT),
                    timeout=10
                )
                elapsed = time.perf_counter() - start
                times.append(elapsed)
                # Return to pool for next iteration
                await CONNECTION_POOL.put(TEST_HOST, TEST_PORT, reader, writer)
        except Exception as e:
            print(f"  Connection {i+1} failed: {e}")

    # Cleanup - close all pooled connections
    stats = CONNECTION_POOL.stats()
    return times

async def benchmark_sequential_reuse():
    """Benchmark simulating sequential requests reusing same connection."""
    times = []
    reader, writer = None, None

    for i in range(NUM_CONNECTIONS):
        start = time.perf_counter()
        try:
            # Try pool first
            pooled = await CONNECTION_POOL.get(TEST_HOST, TEST_PORT)
            if pooled:
                reader, writer = pooled
            else:
                # Create new connection
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(TEST_HOST, TEST_PORT),
                    timeout=10
                )
            elapsed = time.perf_counter() - start
            times.append(elapsed)

            # Simulate a quick HTTP request
            writer.write(b'HEAD / HTTP/1.1\r\nHost: ' + TEST_HOST.encode() + b'\r\nConnection: keep-alive\r\n\r\n')
            await writer.drain()
            response = await asyncio.wait_for(reader.read(1024), timeout=5)

            # Return to pool (if connection still good)
            if not writer.is_closing() and not reader.at_eof():
                await CONNECTION_POOL.put(TEST_HOST, TEST_PORT, reader, writer)
            else:
                writer.close()
        except Exception as e:
            print(f"  Request {i+1} failed: {e}")
            if writer:
                try:
                    writer.close()
                except:
                    pass

    return times

def print_stats(name, times):
    if not times:
        print(f"{name}: No successful connections")
        return
    avg = sum(times) / len(times)
    min_t = min(times)
    max_t = max(times)
    # Count how many were from pool (very fast, < 1ms)
    pool_hits = sum(1 for t in times if t < 0.001)
    print(f"{name}:")
    print(f"  Connections: {len(times)}")
    print(f"  Avg time: {avg*1000:.2f}ms")
    print(f"  Min time: {min_t*1000:.2f}ms")
    print(f"  Max time: {max_t*1000:.2f}ms")
    print(f"  Pool hits (< 1ms): {pool_hits}")
    print(f"  Total time: {sum(times)*1000:.2f}ms")
    print()

async def main():
    print(f"Connection Pool Benchmark")
    print(f"Target: {TEST_HOST}:{TEST_PORT}")
    print(f"Connections per test: {NUM_CONNECTIONS}")
    print("=" * 50)
    print()

    # Test 1: No pooling (baseline)
    print("Test 1: Fresh connections (no pooling)...")
    times_no_pool = await benchmark_no_pool()
    print_stats("No Pool", times_no_pool)

    # Small delay between tests
    await asyncio.sleep(1)

    # Test 2: With pooling (return to pool after each)
    print("Test 2: With connection pooling...")
    times_with_pool = await benchmark_with_pool()
    print_stats("With Pool", times_with_pool)

    # Print pool stats
    stats = CONNECTION_POOL.stats()
    print("Pool Statistics:")
    print(f"  Hits: {stats['hits']}")
    print(f"  Misses: {stats['misses']}")
    print(f"  Created: {stats['created']}")
    print(f"  Reused: {stats['reused']}")
    print()

    # Small delay between tests
    await asyncio.sleep(1)

    # Test 3: Sequential HTTP requests with keep-alive
    print("Test 3: Sequential HTTP requests with keep-alive...")
    times_sequential = await benchmark_sequential_reuse()
    print_stats("Sequential Reuse", times_sequential)

    # Final pool stats
    stats = CONNECTION_POOL.stats()
    print("Final Pool Statistics:")
    print(f"  Hits: {stats['hits']}")
    print(f"  Misses: {stats['misses']}")
    print(f"  Created: {stats['created']}")
    print(f"  Reused: {stats['reused']}")
    print()

    # Summary
    if times_no_pool and times_with_pool:
        no_pool_total = sum(times_no_pool)
        with_pool_total = sum(times_with_pool)
        speedup = no_pool_total / with_pool_total if with_pool_total > 0 else 0
        print(f"Pool speedup: {speedup:.2f}x")

    if times_no_pool and times_sequential:
        no_pool_total = sum(times_no_pool)
        sequential_total = sum(times_sequential)
        speedup = no_pool_total / sequential_total if sequential_total > 0 else 0
        print(f"Sequential reuse speedup: {speedup:.2f}x")

if __name__ == '__main__':
    asyncio.run(main())
