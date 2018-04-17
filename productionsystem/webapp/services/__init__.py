import pkg_resources
from productionsystem.config import getConfig

HTMLPageServer = pkg_resources.load_entry_point(getConfig('Core').get('plugin', 'productionsystem'), 'webapp.services', 'htmlpageserver')
