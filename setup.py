import sys
from distutils.core import setup
from shutil import copy
from dvasya import VERSION

install_requires=['aiohttp>=0.12.0,<0.13']


PY_VER = sys.version_info

if PY_VER >= (3, 4):
    pass
elif PY_VER >= (3, 3):
    install_requires.append('asyncio')
else:
    raise RuntimeError("dvasya doesn't suppport Python earllier than 3.3")
try:
    copy("scripts/manage.py", "scripts/dvasya-manage")
except (OSError, IOError):
    pass


setup(
    name='dvasya',
    version=VERSION,
    packages=['dvasya', 'dvasya.contrib'],
    scripts=['scripts/dvasya-manage'],
    url='',
    license='Beer Licence',
    author='tumbler',
    author_email='zimbler@gmail.com',
    description='Django Views for AsyncIO APIs',
    install_requires=install_requires
)
