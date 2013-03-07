# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" Setup file.
"""
import os
from setuptools import setup, find_packages

PROJECT = 'simplepush_ws'

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.md')) as f:
    README = f.read()


setup(name=PROJECT,
      version=0.001,
      description=PROJECT,
      long_description=README,
      classifiers=[
          "Programming Language :: Python",
          "Framework :: Tornado",
          "Topic :: Internet :: WWW/HTTP",
          "Topic :: Internet :: WWW/HTTP :: WSGI :: Application"
      ],
      keywords="web services",
      author='jr conlin',
      author_email='jrconlin@mozilla.com',
      url='',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
)
