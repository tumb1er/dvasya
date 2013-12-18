from distutils.core import setup
import os
import shutil

if not os.path.exists('scripts'):
    os.makedirs('scripts')
shutil.copyfile('scripts/manage.py', 'scripts/dvasya-manage')
from dvasya import VERSION

setup(
    name='dvasya',
    version=VERSION,
    packages=['dvasya'],
    scripts=['scripts/dvasya-manage'],
    url='',
    license='Beer Licence',
    author='tumbler',
    author_email='zimbler@gmail.com',
    description='Django Views for AsyncIO APIs',
    install_requires=['aiohttp']
)
