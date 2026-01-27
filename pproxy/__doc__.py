__title__       = "pproxy2"
__license__     = "MIT"
__description__ = "High-performance async proxy server with uvloop, connection pooling, and multi-process support."
__keywords__    = "proxy socks http shadowsocks shadowsocksr ssr redirect pf tunnel cipher ssl udp performance uvloop"
__author__      = "iqzer0"
__email__       = "aaish@parallel.solutions"
__url__         = "https://github.com/iqzer0/pproxy2"

# Original project credits
__original_author__ = "Qian Wenjie"
__original_email__  = "qianwenjie@gmail.com"
__original_url__    = "https://github.com/qwj/python-proxy"

try:
    from setuptools_scm import get_version
    __version__ = get_version()
except Exception:
    try:
        from pkg_resources import get_distribution
        __version__ = get_distribution('pproxy2').version
    except Exception:
        __version__ = '2.2.0'

__all__ = ['__version__', '__description__', '__url__', '__original_author__', '__original_url__']
