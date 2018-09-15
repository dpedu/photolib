#!/usr/bin/env python3

from setuptools import setup


__version__ = "0.0.0"


setup(name='photoapp',
      version=__version__,
      description='Photo library application',
      url='',
      author='dpedu',
      author_email='dave@davepedu.com',
      packages=['photoapp'],
      install_requires=[],
      entry_points={
          "console_scripts": [
              "photoappd = photoapp.daemon:main",
              "photoimport = photoapp.ingest:main",
              "photovalidate = photoapp.validate:main",
              "photoinfo = photoapp.image:main",
              "photooffset = photoapp.dateoffset:main",
          ]
      },
      include_package_data=True,
      package_data={'photoapp': ['../templates/*.html',
                                 '../styles/dist/*']},
      zip_safe=False)
