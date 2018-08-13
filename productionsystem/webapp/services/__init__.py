import pkg_resources
from productionsystem.config import getConfig
from CVMFSListing import CVMFSDirectoryListing

HTMLPageServer = pkg_resources.load_entry_point(getConfig('Plugins').get('htmlpageserver', 'productionsystem'), 'webapp.services', 'htmlpageserver')
