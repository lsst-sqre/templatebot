from setuptools import setup, find_packages
from pathlib import Path

package_name = 'templatebot'
description = (
    'Templatebot is an api.lsst.codes microservice for creating new projects '
    'and files from templates.'
)
author = 'Association of Universities for Research in Astronomy'
author_email = 'sqre-admin@lists.lsst.org'
license = 'MIT'
url = 'https://github.com/lsst-sqre/templatebot'
pypi_classifiers = [
    'Development Status :: 4 - Beta',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3.7'
]
keywords = ['lsst', 'slack']
readme = Path(__file__).parent / 'README.rst'

# Core dependencies
install_requires = [
    'aiodns==1.1.1',
    'aiohttp==3.5.0',
    'cchardet==2.1.4',
    'structlog==18.2.0',
    'colorama==0.4.1',  # used by structlog
    'click',
    'fastavro==0.21.16',
    'kafkit==0.2.0b3',
    'aiokafka==0.6.0',
    'templatekit==0.4.1',
    'confluent-kafka==0.11.6',
    'GitPython==3.1.3',
    'cachetools==3.1.0',
    'gidgethub==3.1.0',
]

# Test dependencies
tests_require = [
    'pytest==5.4.3',
    'pytest-flake8==1.0.6',
    'aiohttp-devtools==0.11',
]
tests_require += install_requires

# Sphinx documentation dependencies
docs_require = [
    'documenteer[pipelines]>=0.5.0,<0.6.0',
]

# Optional dependencies (like for dev)
extras_require = {
    # For development environments
    'dev': tests_require + docs_require
}

# Setup-time dependencies
setup_requires = [
    'pytest-runner>=4.2.0,<5.0.0',
    'setuptools_scm',
]

setup(
    name=package_name,
    description=description,
    long_description=readme.read_text(),
    author=author,
    author_email=author_email,
    url=url,
    license=license,
    classifiers=pypi_classifiers,
    keywords=keywords,
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=install_requires,
    tests_require=tests_require,
    setup_requires=setup_requires,
    extras_require=extras_require,
    entry_points={
        'console_scripts': [
            'templatebot = templatebot.cli:main'
        ]
    },
    use_scm_version=True,
    include_package_data=True
)
