#!/usr/bin/env python

import os
from setuptools import setup
from buster import _version


setup(name="buster",
      version=_version.__version__,
      description="Static site generator for Ghost and Github",
      long_description=open("README.md").read(),
      author="Akshit Khurana",
      author_email="axitkhurana@gmail.com",
      url="https://github.com/axitkhurana/buster",
      license="MIT",
      packages=["buster"],
      entry_points={"console_scripts": ["buster = buster.buster:main"]},
      install_requires=['GitPython==0.3.2.RC1', 'async==0.6.1', 'gitdb==0.5.4', 'smmap==0.8.2', 'lxml>=3.4.1', 'beautifulsoup4>=4.3.2', 'html5lib', 'argparse']
    )
