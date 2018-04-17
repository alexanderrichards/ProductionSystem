"""SQL Models."""
import pkg_resources
from productionsystem.config import getConfig
from Users import Users
from Services import Services

ParametricJobs = pkg_resources.load_entry_point(getConfig('Core').get('plugin', 'productionsystem'), 'dbmodels', 'parametricjobs')
Requests = pkg_resources.load_entry_point(getConfig('Core').get('plugin', 'productionsystem'), 'dbmodels', 'requests')
