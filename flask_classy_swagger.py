import inspect
import re
from collections import defaultdict


from flask import jsonify

from undecorated import undecorated


SWAGGER_VERSION = '2.0'
SWAGGER_PATH = '/swagger.json'
IGNORED_RULES = ['/static', SWAGGER_PATH]


def schema(title, version, base_path=None):
    schema = {"swagger": SWAGGER_VERSION,
              "paths": {},
              "tags": [],
              "info": {
                  "title": title,
                  "version": version}}
    if base_path is not None:
        schema['basePath'] = base_path
    return schema


def http_verb(rule):
    # trying to get over rule.methods like: set(['HEAD', 'OPTIONS', 'GET'])
    for m in rule.methods:
        if m in ['GET', 'POST', 'PUT', 'DELETE']:
            return m.lower()


def is_ignored(rule):
    # TODO app.static_url_path
    for ignored in IGNORED_RULES:
        if rule.rule.startswith(ignored):
            return True
    else:
        return False


def get_path(rule):
    # swagger spec is very clear about wanting paths to start with a slash
    assert rule.rule.startswith('/')

    if rule.rule == '/':
        return '/'

    # try to strip the end of the path which are usually parameters
    reversed = rule.rule[::-1]
    return re.sub(r'(>\w+\</)', '', reversed)[::-1].rstrip('/')


def get_tag(rule):
    return rule.endpoint.split(":")[0]


def get_docs(function):
    """Return (summary, description) tuple from the passed in function"""
    try:
        summary, description = re.match(
            r"""
            (.+?$) # first (summary) line, non-greedy MULTILINE $
            \n?    # maybe a newline
            \s*    # maybe indentation to the beginning of the next line
            (.*)   # maybe multiple other lines DOTALL
            """,
            function.func_doc.strip(),
            re.MULTILINE | re.DOTALL | re.VERBOSE
        ).groups()
    except (AttributeError, TypeError):
        return '', ''

    # swagger ignores single newlines, but if it sees two consecutive
    # newline characters (a blank line) the swagger UI break out of the
    # "Implementation Notes" paragraph. AFAICS this is not in the
    # swagger spec?
    description = re.sub(r'\n\n+', '\n', description)
    return summary, description


def get_flask_classy_class(method):
    if method is None:
        return None
    return method.im_class


def get_tag_description(func):
    klass = get_flask_classy_class(func)
    if klass:
        return klass.__doc__ or ''


def get_parameters(method):
    if method is None:
        return []

    argspec = inspect.getargspec(method)
    if argspec.defaults is None:
        optional = []
        required = [
            {'name': p, 'required': True}
            for p in argspec.args
        ]
    else:
        optional = [
            {'name': p, 'required': False}
            # go from back to front because of the way getargspec returns
            # args and defaults
            for p, d in zip(argspec.args[::-1], argspec.defaults[::-1])[::-1]
        ]
        required = [
            {'name': p, 'required': True}
            for p in argspec.args[:-len(argspec.defaults)]
        ]

    if required and required[0]['name'] == 'self':  # assert this?
        required.pop(0)

    return required + optional


def get_api_method(app, rule):
    """Return the original Flask-Classy method as the user first wrote it

    This means without any decorators applied.

    :app: a Flask app object
    :rule: a werkzeug.routing.Rule object

    """
    return undecorated(app.view_functions[rule.endpoint])


def generate_everything(app, title, version, base_path=None):
    """Build the whole swagger JSON tree for this app"""
    paths = defaultdict(dict)
    tags = dict()
    for rule in app.url_map.iter_rules():
        if is_ignored(rule):
            continue

        path = get_path(rule)

        method = get_api_method(app, rule)
        summary, description = get_docs(method)
        parameters = get_parameters(method)

        tag = get_tag(rule)
        if tag not in tags:
            tags[tag] = get_tag_description(method)

        path_item_object = {
            "summary": summary,
            "description": description,
            "tags": [tag],
            "parameters": parameters
        }
        path_item_name = http_verb(rule)
        paths[path][path_item_name] = path_item_object

    docs = schema(title, version, base_path)
    docs['paths'] = paths
    docs['tags'] = [{'name': k, 'description': v}
                    for k, v in tags.items()]
    return docs


def swaggerify(
        app, title, version, swagger_path=SWAGGER_PATH, base_path=None):
    @app.route(swagger_path)
    def swagger():
        docs = generate_everything(app, title, version, base_path)
        return jsonify(docs)
