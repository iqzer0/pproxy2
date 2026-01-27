import time, sys, asyncio, functools
from collections import deque

b2s = lambda i: f'{i/2**30:.1f}G' if i>=2**30 else f'{i/2**20:.1f}M' if i>=2**20 else f'{i/1024:.1f}K'

def all_stat_other(stats):
    cmd = sys.stdin.readline()
    all_stat(stats)

def all_stat(stats):
    if len(stats) <= 1:
        print('no traffic')
        return
    print('='*70)
    hstat = {}
    for remote_ip, v in stats.items():
        if remote_ip == 0: continue
        stat = [0]*6
        for host_name, v2 in v.items():
            for h in (stat, hstat.setdefault(host_name, [0]*6)):
                for i in range(6):
                    h[i] += v2[i]
        stat = [b2s(i) for i in stat[:4]] + stat[4:]
        print(remote_ip, '\tDIRECT: {5} ({1},{3})  PROXY: {4} ({0},{2})'.format(*stat))
    print(' '*3+'-'*64)
    hstat = sorted(hstat.items(), key=lambda x: sum(x[1]), reverse=True)[:15]
    hlen = max(map(lambda x: len(x[0]), hstat)) if hstat else 0
    for host_name, stat in hstat:
        stat, conn = (b2s(stat[0]+stat[1]), b2s(stat[2]+stat[3])), stat[4]+stat[5]
        print(host_name.ljust(hlen+5), '{0} / {1}'.format(*stat), '/ {}'.format(conn) if conn else '')
    print('='*70)

async def realtime_stat(stats):
    history = deque(maxlen=10)  # Use deque with maxlen for O(1) automatic eviction
    history.append((stats[:4], time.perf_counter()))
    while True:
        await asyncio.sleep(1)
        history.append((stats[:4], time.perf_counter()))
        i0, t0, i1, t1 = history[0][0], history[0][1], history[-1][0], history[-1][1]
        stat = [b2s((i1[i]-i0[i])/(t1-t0))+'/s' for i in range(4)] + stats[4:]
        sys.stdout.write('DIRECT: {5} ({1},{3})   PROXY: {4} ({0},{2})\x1b[0K\r'.format(*stat))
        sys.stdout.flush()

def setup(loop, args):
    def verbose(s):
        if args.v >= 2:
            sys.stdout.write('\x1b[32m'+time.strftime('%Y-%m-%d %H:%M:%S')+'\x1b[m ')
            sys.stdout.write(s+'\x1b[0K\n')
        else:
            sys.stdout.write(s+'\n')
        sys.stdout.flush()
    args.verbose = verbose
    args.stats = {0: [0]*6}
    # Cache for modstat results to avoid repeated dict lookups and lambda creation
    _modstat_cache = {}
    def modstat(user, remote_ip, host_name, stats=args.stats):
        # Create cache key - use bytes(user) for stable key (id() can be reused after GC)
        cache_key = (bytes(user) if isinstance(user, (bytes, bytearray)) else user, remote_ip, host_name)
        cached = _modstat_cache.get(cache_key)
        if cached is not None:
            return cached

        u = user.decode().split(':')[0]+':' if isinstance(user, (bytes,bytearray)) else ''
        # Avoid repeated host_name.split('.') call
        parts = host_name.split('.')
        if parts[-1].isalpha():
            suffix_len = 3 if host_name.endswith('.com.cn') else 2
            host_name_2 = '.'.join(parts[-suffix_len:])
        else:
            host_name_2 = host_name
        tostat = (stats[0], stats.setdefault(u+remote_ip, {}).setdefault(host_name_2, [0]*6))

        # Pre-create stat update functions for each index
        def make_stat_fn(idx, st=tostat):
            def stat_fn(s):
                st[0][idx] += s
                st[1][idx] += s
            return stat_fn
        stat_fns = {i: make_stat_fn(i) for i in range(6)}
        result = lambda i, fns=stat_fns: fns.get(i, lambda s: None)

        # Cache with size limit to prevent unbounded growth
        if len(_modstat_cache) < 10000:
            _modstat_cache[cache_key] = result
        return result
    args.modstat = modstat
    def win_readline(handler):
        while True:
            line = sys.stdin.readline()
            handler()
    if args.v >= 2:
        asyncio.ensure_future(realtime_stat(args.stats[0]))
        if sys.platform != 'win32':
            try:
                loop.add_reader(sys.stdin, functools.partial(all_stat_other, args.stats))
            except (PermissionError, OSError):
                pass  # Ignore if stdin is not a real file descriptor
        else:
            loop.run_in_executor(None, win_readline, functools.partial(all_stat, args.stats))

