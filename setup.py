from setuptools import setup

setup(name='Raconteur', version='0.3',
      description='OpenShift Python-2.7 Community Cartridge based application',
      author='Martin Frojd', author_email='ripperdoc@gmail.com',
      url='http://www.python.org/sigs/distutils-sig/',

      #  Uncomment one or more lines below in the install_requires section
      #  for the specific client drivers/modules your application needs.
      install_requires=['greenlet', 'gevent', 'Jinja2 <= 2.6', 'Flask', 'psycopg2', 'flask-peewee', 'wtf-peewee >= 0.2.2'
                        #  'MySQL-python',
                        #  'pymongo',
                        #  'psycopg2',
      ],
     )