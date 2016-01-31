import sys
from distutils.core import setup
from shutil import copy
from dvasya import VERSION

SCRIPTS = "manage", "gunicorn"

install_requires=['aiohttp>=0.17.2,<0.21']


PY_VER = sys.version_info

if PY_VER >= (3, 4):
    pass
elif PY_VER >= (3, 3):
    install_requires.append('asyncio')
else:
    raise RuntimeError("dvasya doesn't suppport Python earllier than 3.3")
try:
    for script in SCRIPTS:
        copy("scripts/%s.py" % script, "scripts/dvasya-%s" % script)
except (OSError, IOError):
    pass


setup(
    name='dvasya',
    version=VERSION,
    packages=['dvasya', 'dvasya.contrib'],
    scripts=["scripts/dvasya-%s" % s for s in SCRIPTS],
    url='',
    license='Beer Licence',
    author='tumbler',
    author_email='zimbler@gmail.com',
    description='Django Views for AsyncIO APIs',
    install_requires=install_requires
)
