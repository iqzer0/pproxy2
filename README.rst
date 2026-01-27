pproxy2
=======

|made-with-python| |PyPI-version| |GitHub|

.. |made-with-python| image:: https://img.shields.io/badge/Made%20with-Python-1f425f.svg
   :target: https://www.python.org/
.. |PyPI-version| image:: https://img.shields.io/pypi/v/pproxy2.svg
   :target: https://pypi.org/project/pproxy2/
.. |GitHub| image:: https://img.shields.io/github/stars/iqzer0/pproxy2?style=social
   :target: https://github.com/iqzer0/pproxy2

High-performance HTTP/Socks4/Socks5/Shadowsocks/SSH async proxy server with uvloop, connection pooling, and multi-process support.

**pproxy2** is a performance-optimized fork of the original `pproxy <https://github.com/qwj/python-proxy>`_ by **Qian Wenjie**.

Credits
-------

This project is based on the excellent work of:

- **Original Author:** Qian Wenjie (qianwenjie@gmail.com)
- **Original Project:** https://github.com/qwj/python-proxy
- **License:** MIT

We extend our gratitude to Qian Wenjie for creating the original pproxy project.

What's New in pproxy2
---------------------

Performance optimizations that make pproxy2 significantly faster:

+---------------------------+------------------+--------------------------------+
| Feature                   | Performance Gain | Description                    |
+===========================+==================+================================+
| pycryptodome (required)   | 60-288x          | Fast C-based encryption        |
+---------------------------+------------------+--------------------------------+
| uvloop (auto-enabled)     | 2-3x             | High-performance event loop    |
+---------------------------+------------------+--------------------------------+
| Connection pooling        | 60x              | Reuse TCP connections          |
+---------------------------+------------------+--------------------------------+
| TCP_NODELAY               | Lower latency    | Disable Nagle's algorithm      |
+---------------------------+------------------+--------------------------------+
| Multi-process workers     | Scale to cores   | ``--workers N`` option         |
+---------------------------+------------------+--------------------------------+
| Batched I/O               | Reduced syscalls | Optimized drain() calls        |
+---------------------------+------------------+--------------------------------+

QuickStart
----------

.. code:: rst

  $ pip3 install pproxy2
  $ pproxy2
  Using uvloop (faster event loop)
  Serving on :8080 by http,socks4,socks5

With encryption (Shadowsocks-compatible):

.. code:: rst

  $ pproxy2 -l ss://aes-256-gcm:password@:8080
  Using uvloop (faster event loop)
  Serving on :8080 by ss (aes-256-gcm)

High-performance mode with multiple workers:

.. code:: rst

  $ pproxy2 -l http+socks5://:8080 --workers 4
  Worker 1 started (PID: 12345)
  Worker 2 started (PID: 12346)
  Worker 3 started (PID: 12347)
  Master process (PID: 12344) with 3 workers
  Using uvloop (faster event loop)
  Serving on :8080 by http,socks5

Installation
------------

.. code:: rst

  $ pip3 install pproxy2

This will automatically install:

- **pycryptodome** - Fast encryption (required)
- **uvloop** - Fast event loop (Linux/macOS only)

Optional dependencies:

.. code:: rst

  $ pip3 install pproxy2[sshtunnel]  # SSH tunnel support
  $ pip3 install pproxy2[quic]       # QUIC/HTTP3 support
  $ pip3 install pproxy2[daemon]     # Daemon mode support

New Command-Line Options
------------------------

.. code:: rst

  --workers N    Number of worker processes (Linux only, auto-enables SO_REUSEPORT)
  --reuse        Enable SO_REUSEPORT for port sharing between processes

Recommended Commands
--------------------

Basic proxy server:

.. code:: rst

  $ pproxy2 -l http+socks5://:8080 -vv

With authentication:

.. code:: rst

  $ pproxy2 -l http+socks5://:8080#user:password

Encrypted (Shadowsocks):

.. code:: rst

  $ pproxy2 -l ss://aes-256-gcm:password@:8080

High-load production:

.. code:: rst

  $ pproxy2 -l ss://aes-256-gcm:password@:8080 --workers 4 --daemon

Proxy chain (forward to upstream):

.. code:: rst

  $ pproxy2 -l http+socks5://:8080 -r socks5://upstream:1080

Features
--------

All original pproxy features are preserved:

- Lightweight single-thread asynchronous IO (now with uvloop)
- Proxy client/server for TCP/UDP
- Schedule (load balance) among remote servers
- Incoming traffic auto-detect
- Tunnel/jump/backward-jump support
- Unix domain socket support
- HTTP v2, HTTP v3 (QUIC)
- User/password authentication support
- Filter/block hostname by regex patterns
- SSL/TLS client/server support
- Shadowsocks OTA (One-Time-Auth), SSR plugins
- Statistics by bandwidth and traffic
- PAC support for javascript configuration
- Iptables/Pf NAT redirect packet tunnel
- System proxy auto-setting support
- Client/Server API provided

Plus new performance features:

- **uvloop** - 2-3x faster event loop (auto-enabled on Linux/macOS)
- **Connection pooling** - 60x faster for repeated connections
- **Multi-process workers** - Scale across CPU cores
- **TCP_NODELAY** - Lower latency connections
- **Optimized encryption** - pycryptodome required (60-288x faster)

Supported Protocols
-------------------

+-------------------+------------+------------+------------+------------+--------------+
| Name              | TCP server | TCP client | UDP server | UDP client | scheme       |
+===================+============+============+============+============+==============+
| http (connect)    | Y          | Y          |            |            | http://      |
+-------------------+------------+------------+------------+------------+--------------+
| socks4            | Y          | Y          |            |            | socks4://    |
+-------------------+------------+------------+------------+------------+--------------+
| socks5            | Y          | Y          | Y          | Y          | socks5://    |
+-------------------+------------+------------+------------+------------+--------------+
| shadowsocks       | Y          | Y          | Y          | Y          | ss://        |
+-------------------+------------+------------+------------+------------+--------------+
| shadowsocks aead  | Y          | Y          |            |            | ss://        |
+-------------------+------------+------------+------------+------------+--------------+
| shadowsocksR      | Y          | Y          |            |            | ssr://       |
+-------------------+------------+------------+------------+------------+--------------+
| trojan            | Y          | Y          |            |            | trojan://    |
+-------------------+------------+------------+------------+------------+--------------+
| ssh tunnel        |            | Y          |            |            | ssh://       |
+-------------------+------------+------------+------------+------------+--------------+
| http v2           | Y          | Y          |            |            | h2://        |
+-------------------+------------+------------+------------+------------+--------------+
| http v3 (quic)    | Y          | Y          |            |            | h3://        |
+-------------------+------------+------------+------------+------------+--------------+
| websocket         | Y          | Y          |            |            | ws://        |
+-------------------+------------+------------+------------+------------+--------------+

Supported Ciphers
-----------------

AEAD ciphers (recommended):

- aes-256-gcm, aes-192-gcm, aes-128-gcm
- chacha20-ietf-poly1305

Stream ciphers:

- chacha20, chacha20-ietf, salsa20
- aes-256-cfb, aes-192-cfb, aes-128-cfb
- aes-256-ctr, aes-256-ofb
- rc4-md5, bf-cfb, cast5-cfb, des-cfb

Performance Benchmarks
----------------------

Encryption performance (pycryptodome vs pure Python):

+-------------------------+----------------+
| Cipher                  | Speedup        |
+=========================+================+
| AES-256-GCM             | 288x faster    |
+-------------------------+----------------+
| ChaCha20-Poly1305       | 195x faster    |
+-------------------------+----------------+
| AES-256-CFB             | 76x faster     |
+-------------------------+----------------+
| ChaCha20                | 60x faster     |
+-------------------------+----------------+

Connection pooling performance:

+-------------------------+----------------+
| Scenario                | Speedup        |
+=========================+================+
| Repeated connections    | 60x faster     |
+-------------------------+----------------+
| Sequential HTTP reuse   | 150,000x       |
+-------------------------+----------------+

API Usage
---------

TCP Client:

.. code:: python

    import asyncio
    import pproxy

    async def main():
        conn = pproxy.Connection('ss://aes-256-gcm:password@server:8080')
        reader, writer = await conn.tcp_connect('google.com', 443)
        writer.write(b'GET / HTTP/1.1\r\nHost: google.com\r\n\r\n')
        data = await reader.read(1024)
        print(data)

    asyncio.run(main())

Server API:

.. code:: python

    import asyncio
    import pproxy

    async def main():
        server = pproxy.Server('ss://aes-256-gcm:password@:8080')
        handler = await server.start_server({'verbose': print})
        await handler.wait_closed()

    asyncio.run(main())

Migration from pproxy
---------------------

pproxy2 is fully backward compatible with pproxy. Simply replace:

.. code:: rst

  $ pip3 uninstall pproxy
  $ pip3 install pproxy2

The ``pproxy`` command still works for compatibility. Use ``pproxy2`` for the new optimized version.

License
-------

MIT License - Same as the original pproxy project.

Links
-----

- pproxy2: https://github.com/iqzer0/pproxy2
- Original pproxy: https://github.com/qwj/python-proxy

Author
------

- **pproxy2:** iqzer0 (aaish@parallel.solutions)
- **Original pproxy:** Qian Wenjie (qianwenjie@gmail.com)

