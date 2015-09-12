import json

from flask import Flask

from flask_classy_swagger import schema, swaggerify


TITLE = 'MyTestAPI'
VERSION = '0.9'
BASIC_SCHEMA = {
    'info': {
        'title': TITLE,
        'version': VERSION},
    'swagger': '2.0',
    'paths': {}}


class TestSchema(object):
    def test_required_params(self):
        assert schema(TITLE, VERSION) == BASIC_SCHEMA

    def test_base_path(self):
        assert (
            schema(TITLE, VERSION, base_path='/myswagger') ==
            dict(BASIC_SCHEMA, **{'basePath': '/myswagger'}))


class TestSwaggerify(object):
    def test_basic(self):
        app = Flask('test')
        swaggerify(app, '/my-swagger-path', TITLE, VERSION)
        client = app.test_client()

        response = client.get('/my-swagger-path')
        assert json.loads(response.data) == BASIC_SCHEMA