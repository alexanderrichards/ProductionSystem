"""Setuptools Module."""
from setuptools import setup, find_packages

setup(
    name="productionsystem",
    version="0.1",
    packages=find_packages(),
    install_requires=['CherryPy',
                      'daemonize',
                      'enum34',
                      'requests',
                      'SQLAlchemy',
                      'rpyc',
                      'suds'
                      ],
    extras_require={
        'dev': ["pep257", "pep8", "pylint", "Sphinx", "sphinxcontrib-httpdomain", "mock", "pytest", "coverage", "pytest-cov", "pytest-pylint", "pytest-pep8", "pytest-pep257"],
    },
    setup_requires=["pytest-runner"],
    tests_require=["mock", "pytest", 'coverage', 'pytest-cov', 'pytest-pylint', 'pytest-pep8', 'pytest-pep257'],
    test_suit="tests",
    entry_points={
        'dbmodels': ['parametricjobs = productionsystem.sql.models.ParametricJobs:ParametricJobs',
                     'requests = productionsystem.sql.models.Requests:Requests'],
        'webapp.services': ['htmlpageserver = productionsystem.webapp.services.HTMLPageServer:HTMLPageServer'],
        'daemons': ['webapp = productionsystem.webapp.WebApp:WebApp']
    },
    scripts=['productionsystem/webapp-daemon.py',
             'productionsystem/monitoring-daemon.py',
             'productionsystem/dirac-daemon.py'],
    # metadata for upload to PyPI
    author="Alexander Richards",
    author_email="a.richards@imperial.ac.uk",
    description="Production System",
    license="MIT",
    keywords="production",
    url="https://github.com/alexanderrichards/ProductionSystem"
)
