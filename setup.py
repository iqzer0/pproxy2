from setuptools import setup
import os, re

def read(*names, **kwargs):
    with open(os.path.join(os.path.dirname(__file__), *names), encoding='utf8') as fp:
        return fp.read()

def find_value(name):
    data_file = read('pproxy', '__doc__.py')
    data_match = re.search(r"^__%s__ += ['\"]([^'\"]*)['\"]" % name, data_file, re.M)
    if data_match:
        return data_match.group(1)
    raise RuntimeError(f"Unable to find '{name}' string.")

setup(
    name                = find_value('title'),
    version             = '2.0.0',
    description         = find_value('description'),
    long_description    = read('README.rst'),
    long_description_content_type = 'text/x-rst',
    url                 = find_value('url'),
    author              = find_value('author'),
    author_email        = find_value('email'),
    license             = find_value('license'),
    python_requires     = '>=3.8',
    keywords            = find_value('keywords'),
    packages            = ['pproxy'],
    classifiers         = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: System :: Networking',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    extras_require      = {
        'sshtunnel': [
            'asyncssh >= 2.5.0',
        ],
        'quic': [
            'aioquic >= 0.9.7',
        ],
        'daemon': [
            'python-daemon >= 2.2.3',
        ],
    },
    install_requires    = [
        'pycryptodome >= 3.7.2',
        'uvloop >= 0.13.0; sys_platform != "win32"',  # uvloop only works on Unix
    ],
    entry_points        = {
        'console_scripts': [
            'pproxy2 = pproxy.server:main',
            'pproxy = pproxy.server:main',  # Keep backward compatibility
        ],
    },
)
