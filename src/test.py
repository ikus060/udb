import cherrypy


@cherrypy.popargs('id')
class Person:
    @cherrypy.expose
    def index(self, id=None):
        if id:
            return 'FOO'
        return 'BAR'

    @cherrypy.expose('data.json')
    @cherrypy.tools.json_out()
    def data_json(self, id=None, **kwargs):
        if id:
            return {'a': 'foo'}
        return {'a': 'bar'}


class Root:
    person = Person()

    @cherrypy.expose
    def index(self, id=None):
        return 'index'


cherrypy.quickstart(root=Root())
