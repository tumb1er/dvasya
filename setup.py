from distutils.core import setup

from dvasya import VERSION

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
