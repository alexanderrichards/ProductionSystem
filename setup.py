"""Setuptools Module."""
from setuptools import setup, find_packages

setup(
    name="productionsystem",
    version="0.1",
    packages=find_packages(),
    install_requires=['CherryPy',
                      'jinja2',
                      'daemonize',
                      'enum34',
                      'requests',
                      'SQLAlchemy',
                      'pymysql',
#                      'mysql-python',
                      'rpyc',
                      'suds',
                      'gitpython',
                      'psutil',
                      'mock'
                      ],
    extras_require={
        'doc': ['Sphinx', 'sphinxcontrib-httpdomain'],
        'dev': ["pep257",
                "pep8",
                "pylint",
                "Sphinx",
                "sphinxcontrib-httpdomain",
                "pytest",
                "coverage",
                "pytest-cov",
                "pytest-pylint",
                "pytest-pep8",
                "pytest-pep257"],
    },
    setup_requires=["pytest-runner"],
    tests_require=["pytest", 'coverage', 'pytest-cov', 'pytest-pylint', 'pytest-pep8', 'pytest-pep257'],
    test_suit="tests",
    entry_points={
        'dbmodels': ['parametricjobs = productionsystem.sql.models.ParametricJobs:ParametricJobs',
                     'requests = productionsystem.sql.models.Requests:Requests'],
        'monitoring': ['daemon = productionsystem.monitoring.MonitoringDaemon:MonitoringDaemon'],
        'webapp.services': ['htmlpageserver = productionsystem.webapp.services.HTMLService:HTMLPageServer'],
        'webapp': [
#            'jinja2_loader = None',  # This can be filled out by plugins to load their templates
            'daemon = productionsystem.webapp.WebApp:WebApp'
        ]
    },
    scripts=['scripts/webapp-daemon.py',
             'scripts/monitoring-daemon.py',
             'scripts/dirac-daemon.py',
             'scripts/userdb-update.py',
             'scripts/service-status.sh',
             'scripts/stop-services.sh'],
    package_data={'productionsystem': ['webapp/static_resources/*', 'webapp/templates/*']},
    # metadata for upload to PyPI
    author="Alexander Richards",
    author_email="a.richards@imperial.ac.uk",
    description="Production System",
    license="MIT",
    keywords="production",
    url="https://github.com/alexanderrichards/ProductionSystem"
)
