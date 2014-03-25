from distutils.core import setup
from shutil import copy
from dvasya import VERSION

try:
    copy("scripts/manage.py", "scripts/dvasya-manage")
except OSError:
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
    install_requires=['aiohttp']
)
