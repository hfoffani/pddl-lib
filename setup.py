#!/usr/bin/python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages  # Always prefer setuptools over distutils
from setuptools.command.build_py import build_py
from codecs import open  # To use a consistent encoding
from os import path
import subprocess
import sys
import urllib.request
import os

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    keep=False
    l = []
    for line in f:
        if not keep and "###" in line:
            keep = True
            continue
        if "###" in line:
            keep = False
            break
        if keep:
            l.append(line)
    long_description = "".join(l)


class BuildPyCommand(build_py):
    """Custom build command to compile ANTLR grammar before building."""

    def run(self):
        # ANTLR configuration - use 4.13.2 for Java 8 compatibility
        antlr_version = '4.13.2'
        antlr_jar = f'antlr-{antlr_version}-complete.jar'
        antlr_url = f'https://www.antlr.org/download/{antlr_jar}'
        antlr_jar_path = os.path.abspath(antlr_jar)

        # Download ANTLR JAR if not present
        if not os.path.exists(antlr_jar_path):
            print(f'Downloading ANTLR {antlr_version}...')
            try:
                urllib.request.urlretrieve(antlr_url, antlr_jar_path)
                print(f'Downloaded {antlr_jar}')
            except Exception as e:
                print(f'Warning: Could not download ANTLR JAR: {e}')
                print('Assuming parser files are already generated...')

        # Compile ANTLR grammar to Python
        grammar_file = 'pddl.g4'
        if os.path.exists(grammar_file):
            print('Compiling ANTLR grammar to Python...')

            # Check if Java is available
            try:
                subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print('Warning: Java not found. Skipping ANTLR compilation.')
                print('Parser files must be pre-generated or ANTLR compilation will fail.')
                build_py.run(self)
                return

            # Only compile if JAR exists
            if not os.path.exists(antlr_jar_path):
                raise Exception('ANTLR JAR not found. Cannot compile grammar.')

            try:
                os.makedirs('pddlpy', exist_ok=True)
                subprocess.check_call([
                    'java', '-jar', antlr_jar_path,
                    '-Dlanguage=Python3',
                    '-o', 'pddlpy',
                    grammar_file
                ])
                print('ANTLR grammar compiled successfully')
            except subprocess.CalledProcessError as e:
                print(f'Warning: ANTLR compilation failed: {e}')
                print('If parser files are pre-generated, build will continue...')

        # Continue with standard build
        build_py.run(self)


setup(
    name='pddlpy',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.4.4',

    description='Python PDDL parser',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/hfoffani/pddl-lib',

    # Author details
    author='Hernan Foffani',
    author_email='hfoffani@gmail.com',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
    ],

    # What does your project relate to?
    keywords='pddl planning parser',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=['pddlpy'],

    # List run-time dependencies here.  These will be installed by pip when your
    # project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'antlr4-python3-runtime==4.9.3',
    ],

    # List additional groups of dependencies here (e.g. development dependencies).
    # You can install these using the following syntax, for example:
    # $ pip install -e .[dev,test]
    extras_require = {
    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    # include_package_data=True,
    # package_data={
    #     'examples': ['examples-pddl/domain-01.pddl'],
    # },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages.
    # see http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    # data_files=[('my_data', ['data/data_file'])],
    data_files=[
        ('examples',[
            'examples-pddl/domain-01.pddl',
            'examples-pddl/domain-02.pddl',
            'examples-pddl/domain-03.pddl',
            'examples-pddl/domain-04.pddl',
            'examples-pddl/domain-05.pddl',
            'examples-pddl/domain-06.pddl',
            'examples-pddl/problem-01.pddl',
            'examples-pddl/problem-02.pddl',
            'examples-pddl/problem-03.pddl',
            'examples-pddl/problem-04.pddl',
            'examples-pddl/problem-05.pddl',
            'examples-pddl/problem-06.pddl',
        ]),
    ],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        # 'console_scripts': [
        #     'sample=sample:main',
        # ],
    },

    # Custom build command to compile ANTLR grammar
    cmdclass={
        'build_py': BuildPyCommand,
    },
)

