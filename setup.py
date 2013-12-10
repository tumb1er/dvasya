from distutils.core import setup
import os
import shutil

if not os.path.exists('scripts'):
    os.makedirs('scripts')
shutil.copyfile('scripts/manage.py', 'scripts/dvasya-manage')

setup(
    name='dvasya',
    version='0.0.1',
    packages=['dvasya'],
    scripts=['scripts/dvasrv'],
    url='',
    license='Beer Licence',
    author='tumbler',
    author_email='zimbler@gmail.com',
    description='Django Views for AsyncIO APIs',
    install_requires=['aiohttp']
)
