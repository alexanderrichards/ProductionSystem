"""SQL Models."""
from __future__ import absolute_import
import pkg_resources
from productionsystem.config import ConfigSystem
from .Users import Users
from .Services import Services
# from DiracJobs import DiracJobs

# pylint: disable=no-member
DiracJobs = ConfigSystem.get_instance().entry_point_map['dbmodels']['diracjobs'].load()
ParametricJobs = ConfigSystem.get_instance().entry_point_map['dbmodels']['parametricjobs'].load()
Requests = ConfigSystem.get_instance().entry_point_map['dbmodels']['requests'].load()
# ParametricJobs = pkg_resources.load_entry_point(getConfig('Plugins').get('parametricjobs',
#                                                                          'productionsystem'),
#                                                 'dbmodels', 'parametricjobs')
# Requests = pkg_resources.load_entry_point(getConfig('Plugins').get('requests',
#                                                                    'productionsystem'),
#                                           'dbmodels', 'requests')
# ParametricJobs.diracjobs = DiracJobs.unsafe_construct()
# Requests.parametricjobs = ParametricJobs.unsafe_construct()
