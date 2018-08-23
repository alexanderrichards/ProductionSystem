"""SQL Models."""
import pkg_resources
from productionsystem.config import getConfig
from Users import Users
from Services import Services
from DiracJobs import DiracJobs

ParametricJobs = pkg_resources.load_entry_point(getConfig('Plugins').get('parametricjobs', 'productionsystem'), 'dbmodels', 'parametricjobs')
Requests = pkg_resources.load_entry_point(getConfig('Plugins').get('requests', 'productionsystem'), 'dbmodels', 'requests')
#ParametricJobs.diracjobs = DiracJobs.unsafe_construct()
#Requests.parametricjobs = ParametricJobs.unsafe_construct()
