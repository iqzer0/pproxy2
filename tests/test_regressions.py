#!/usr/bin/env python3
"""
Regression tests for bugs found in the 2.3.x performance work.

Run directly:   python3 tests/test_regressions.py
(Exits non-zero if any assertion fails. No third-party deps required, though the
 cipher tests need pycryptodome, which the proxy already depends on.)

Covered:
  #1  rc4 / zero-IV cipher crash on the 2nd packet          (cipher.py IV sentinel)
  #2  keep-alive proxy duplicated response bytes            (HTTPResponseTracker)
  #3  chunked-response desync on split boundaries           (HTTPResponseTracker)
  #4  pooling a connection with a response still in flight  (http_keepalive_proxy)
  #5  AEAD nonce wrap at 4096 instead of 2**96              (AEADCipher.nonce)
  #6  request stall when \\r\\n\\r\\n splits across reads     (forward_to_remote)
"""
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pproxy import proto, server            # noqa: E402
from pproxy.cipher import get_cipher         # noqa: E402

HResp = proto.HTTPResponseTracker
FAILURES = []


def check(name, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    print(f'  [{status}] {name}' + (f' -- {detail}' if detail and not cond else ''))
    if not cond:
        FAILURES.append(name)


def split_feed(wire, parts):
    """Feed `wire` to a fresh tracker cut at the given number of random points,
    returning (total_completions, tracker)."""
    cuts = sorted(random.sample(range(1, len(wire)), min(parts, len(wire) - 1)))
    pieces = [wire[a:b] for a, b in zip([0] + cuts, cuts + [len(wire)])]
    t = HResp()
    completions = 0
    for p in pieces:
        if t.feed(p):
            completions += 1
    return completions, t


# ---------------------------------------------------------------------------
# #2 / #3 : HTTPResponseTracker framing is correct across arbitrary splits
# ---------------------------------------------------------------------------
def test_tracker_content_length():
    print('#2 tracker: Content-Length responses across split reads')
    body = b'hello world' * 10
    wire = b'HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n' % len(body) + body

    # whole
    t = HResp()
    check('single-shot completes once', t.feed(wire) and t.responses_completed == 1)
    check('single-shot at clean boundary', t.at_boundary())
    check('single-shot reusable (keep-alive)', t.can_reuse())

    # the exact #2 scenario: header block split mid-way
    t = HResp()
    c1 = t.feed(b'HTTP/1.1 200 OK\r\nContent-')
    c2 = t.feed(b'Length: 5\r\n\r\nhello')
    check('header split: no premature completion', c1 is False)
    check('header split: completes after body', c2 is True and t.responses_completed == 1)

    # fuzz random split points
    ok = True
    for _ in range(500):
        comp, t = split_feed(wire, random.randint(1, 6))
        if comp != 1 or t.responses_completed != 1 or not t.at_boundary():
            ok = False
            break
    check('fuzz: exactly one completion at the boundary (500 trials)', ok)


def test_tracker_chunked():
    print('#3 tracker: chunked responses across split reads')

    def build_chunked(nchunks, keep_alive=True):
        hdr = b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n'
        hdr += (b'\r\n' if keep_alive else b'Connection: close\r\n\r\n')
        body = b''
        for _ in range(nchunks):
            size = random.randint(1, 400)
            data = bytes(random.choice(b'ay\r\n0123\x00\xff') for _ in range(size))
            body += b'%x\r\n%s\r\n' % (size, data)
        body += b'0\r\n\r\n'
        return hdr + body

    ok = True
    detail = ''
    for trial in range(500):
        wire = build_chunked(random.randint(1, 4))
        comp, t = split_feed(wire, random.randint(1, 8))
        if comp != 1 or t.responses_completed != 1 or not t.at_boundary():
            ok = False
            detail = f'trial {trial}: completions={comp} done={t.responses_completed} boundary={t.at_boundary()}'
            break
    check('fuzz: chunked completes exactly once at the end (500 trials)', ok, detail)

    # trailing CRLF of a chunk split across reads
    hdr = b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'
    t = HResp()
    t.feed(hdr)
    t.feed(b'5\r\nhello\r')          # split right on the trailing CRLF
    done = t.feed(b'\n0\r\n\r\n')
    check('chunk trailing-CRLF split: completes correctly', done and t.responses_completed == 1)

    # chunk-size line split across reads
    t = HResp()
    t.feed(hdr)
    t.feed(b'1')                      # partial hex size
    t.feed(b'A3\r\n')                 # rest of the size line -> 0x1A3
    done = t.feed(b'x' * 0x1A3 + b'\r\n0\r\n\r\n')
    check('chunk-size line split: completes correctly', done and t.responses_completed == 1)


def test_tracker_multi_and_close():
    print('tracker: multiple responses and read-until-close')
    body = b'abc'
    one = b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\n' + body
    comp, t = split_feed(one + one, random.randint(1, 10))
    check('two pipelined responses -> two completions', t.responses_completed == 2)

    # Connection: close, no length -> body until EOF, never poolable
    t = HResp()
    t.feed(b'HTTP/1.0 200 OK\r\n\r\n' + b'streaming body with no length')
    check('read-until-close: not a clean boundary', not t.at_boundary())
    check('read-until-close: not reusable', not t.can_reuse())


# ---------------------------------------------------------------------------
# test harness fakes for the async proxy path (#4, #6)
# ---------------------------------------------------------------------------
class FakeWriter:
    def __init__(self):
        self.data = bytearray()
        self.closed = False
    def write(self, d):
        self.data.extend(d)
    async def drain(self):
        pass
    def is_closing(self):
        return self.closed
    def close(self):
        self.closed = True


class ScriptedReader:
    """Yields the given chunks in order; None means 'block' (response in flight);
    then reports EOF."""
    def __init__(self, chunks, on_pop=None):
        self._chunks = list(chunks)
        self._eof = False
        self._on_pop = on_pop
    def at_eof(self):
        return self._eof
    async def read(self, n=-1):
        while self._chunks:
            c = self._chunks.pop(0)
            if self._on_pop:
                self._on_pop(c)
            if c is None:
                await asyncio.sleep(3600)   # will be cancelled
                continue
            return c
        self._eof = True
        return b''


def _modstat(_i):
    return lambda *a, **k: None


async def _run_keepalive(client_chunks, remote_chunks, on_remote_pop=None):
    host, port = 'test-host', 12345
    server.CONNECTION_POOL._pools.pop((host, port), None)
    client_reader = ScriptedReader(client_chunks)
    remote_reader = ScriptedReader(remote_chunks, on_pop=on_remote_pop)
    client_writer, remote_writer = FakeWriter(), FakeWriter()
    await asyncio.wait_for(server.http_keepalive_proxy(
        client_reader, client_writer, remote_reader, remote_writer,
        host, port, proto.HTTP(None), _modstat, lambda d: None), timeout=5)
    pooled = server.CONNECTION_POOL._pools.get((host, port))
    return remote_writer, client_writer, bool(pooled)


def test_pool_poisoning():
    print('#4 keep-alive: never pool a connection with a response in flight')
    reqA = b'GET /a HTTP/1.1\r\nHost: x\r\n\r\n'
    reqB = b'GET /b HTTP/1.1\r\nHost: x\r\n\r\n'
    respA = b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok'

    # client sends A and B, then disconnects; only A is answered -> must NOT pool
    remote_w, _client_w, pooled = asyncio.run(
        _run_keepalive([reqA, reqB], [respA, None]))
    check('B in flight after client close -> connection not pooled', not pooled)
    check('both requests were forwarded to remote',
          b'GET /a ' in bytes(remote_w.data) and b'GET /b ' in bytes(remote_w.data))

    # clean case: one request answered, remote stays open (idle) -> should pool.
    # deliver respA, then keep remote open (block); client disconnects only after
    # respA has been fed to the tracker (synchronised via an event) so the check is
    # deterministic rather than timing-dependent.
    ev = {}
    async def clean():
        host, port = 'test-host', 12345
        server.CONNECTION_POOL._pools.pop((host, port), None)
        ev['e'] = asyncio.Event()
        def on_pop(c):
            if c is not None:      # respA just handed to forward_from_remote
                ev['e'].set()
        class ClientR(ScriptedReader):
            async def read(self, n=-1):
                if self._chunks:
                    return self._chunks.pop(0)
                await ev['e'].wait()   # wait until respA has been fed to the tracker
                self._eof = True
                return b''
        client_reader = ClientR([reqA])
        remote_reader = ScriptedReader([respA, None], on_pop=on_pop)
        cw, rw = FakeWriter(), FakeWriter()
        await asyncio.wait_for(server.http_keepalive_proxy(
            client_reader, cw, remote_reader, rw,
            host, port, proto.HTTP(None), _modstat, lambda d: None), timeout=5)
        return server.CONNECTION_POOL._pools.get((host, port))
    pooled_clean = asyncio.run(clean())
    check('clean request/response + idle remote -> connection pooled', bool(pooled_clean))


def test_split_terminator_no_stall():
    print(r'#6 keep-alive: request with \r\n\r\n split across reads is not stalled')
    # terminator split: first read ends with '...\r\n\r', the '\n' arrives next
    part1 = b'GET /path HTTP/1.1\r\nHost: example.com\r\n\r'
    part2 = b'\n'
    # remote immediately EOF so the coroutine returns quickly
    remote_w, _client_w, _pooled = asyncio.run(
        _run_keepalive([part1, part2], []))
    got = bytes(remote_w.data)
    check('split-terminator request forwarded (no hang)', b'GET /path HTTP/1.1' in got)
    check('full header block reassembled', b'Host: example.com\r\n\r\n' in got)


# ---------------------------------------------------------------------------
# #1 / #5 : cipher fixes
# ---------------------------------------------------------------------------
def test_rc4_no_crash():
    print('#1 rc4: no crash on 2nd packet + correct round-trip')

    # Drive the encrypt writer and decrypt reader directly through prepare_ciphers.
    async def run2():
        enc = get_cipher('rc4:password')[1]
        sr = asyncio.StreamReader()
        out = bytearray()
        class W:
            def write(self, d):
                out.extend(d)
            def get_extra_info(self, k):
                return None
        w = W()
        _, _ = await server.prepare_ciphers(enc, sr, w, server_side=False)
        msgs = [b'hello', b'world', b'again!']
        for m in msgs:
            w.write(m)              # encrypt path (w.write was patched)
        stream = bytes(out)

        dec = get_cipher('rc4:password')[1]
        dr = asyncio.StreamReader()
        class W2:
            def write(self, d):
                pass
            def get_extra_info(self, k):
                return None
        await server.prepare_ciphers(dec, dr, W2(), server_side=False)
        decfn = dr.decrypts[0]
        got = bytearray()
        for i in range(0, len(stream), 3):   # tiny fragments -> exercise 2nd+ packets
            got += decfn(stream[i:i + 3])
        return bytes(got), b''.join(msgs)

    got, expected = asyncio.run(run2())
    check('rc4 fragmented round-trip matches plaintext (no crash)', got == expected)


def test_nonce_full_width():
    print('#5 AEAD: nonce counter spans the full 96 bits')
    _, apply = get_cipher('aes-256-gcm:pw')
    cipher = apply.cipher
    inst = cipher(b'k' * cipher.KEY_LENGTH, ota=False).setup_iv(b'i' * cipher.IV_LENGTH)
    seen = set()
    for _ in range(6000):
        seen.add(inst.nonce)
    check('6000 nonces are all unique (old code repeated at 4096)', len(seen) == 6000)


def main():
    random.seed(1234)
    tests = [
        test_tracker_content_length,
        test_tracker_chunked,
        test_tracker_multi_and_close,
        test_pool_poisoning,
        test_split_terminator_no_stall,
        test_rc4_no_crash,
        test_nonce_full_width,
    ]
    for t in tests:
        t()
    print()
    if FAILURES:
        print(f'FAILED ({len(FAILURES)}): ' + ', '.join(FAILURES))
        sys.exit(1)
    print('All regression tests passed.')


if __name__ == '__main__':
    main()
