"""SQL Models."""
import pkg_resources
from Users import Users
from Services import Services

ParametricJobs = pkg_resources.load_entry_point('productionsystem', 'dbmodels', 'parametricjobs')
Requests = pkg_resources.load_entry_point('productionsystem', 'dbmodels', 'requests')
