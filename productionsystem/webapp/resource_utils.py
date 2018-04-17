import pkg_resources
from productionsystem.config import getConfig


def newrequest_streams():
    plugin = getConfig('Core').get('plugin', 'productionsystem')
    script = pkg_resources.resource_stream(plugin, 'webapp/resources/static/newrequest.js')
    style = pkg_resources.resource_stream(plugin, 'webapp/resources/static/newrequest.css')
    form = pkg_resources.resource_stream(plugin, 'webapp/resources/static/newrequest_form.html')
    return script, style, form
