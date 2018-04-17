import pkg_resources


def newrequest_streams():
    script = pkg_resources.resource_stream('productionsystem', 'webapp/resources/static/newrequest.js')
    style = pkg_resources.resource_stream('productionsystem', 'webapp/resources/static/newrequest.css')
    form = pkg_resources.resource_stream('productionsystem', 'webapp/resources/static/newrequest_form.html')
    return script, style, form
