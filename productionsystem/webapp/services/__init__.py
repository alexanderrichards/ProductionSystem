"""Services sub-package."""
# import pkg_resources
from productionsystem.config import ConfigSystem
from CVMFSListing import CVMFSDirectoryListing
from GitListing import GitDirectoryListing, GitTagListing, GitSchema

# pylint: disable=no-member
HTMLPageServer = ConfigSystem.get_instance()\
                             .entry_point_map['webapp.services']['htmlpageserver']\
                             .load()
# HTMLPageServer = pkg_resources.load_entry_point(getConfig('Plugins')\
#                                                  .get('htmlpageserver', 'productionsystem'),
#                                       'webapp.services', 'htmlpageserver')
