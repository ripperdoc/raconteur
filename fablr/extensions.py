# import mongoengine.connection
# mongoengine.connection.old_get_connection = mongoengine.connection.get_connection

# def new_get_connection(alias='default', reconnect=False):
#   conn = mongoengine.connection.old_get_connection(alias, reconnect)
#   conn =
#   return False

# mongoengine.connection.get_connection = new_get_connection

import sys
import urllib

from datetime import datetime

from babel import Locale
from bson.objectid import ObjectId
from flask import abort
from flask_mongoengine import Pagination, MongoEngine, DynamicDocument
from flask.json import JSONEncoder, load
from flask_debugtoolbar import DebugToolbarExtension
from markdown.treeprocessors import Treeprocessor
from mongoengine import Document, QuerySet, ConnectionError
from pymongo.errors import ConnectionFailure
from speaklater import _LazyString
from werkzeug.routing import Rule
from werkzeug.urls import url_decode
import time

toolbar = DebugToolbarExtension()


# class MyMongoEngine(MongoEngine):
# def

# def get_db(alias='default', reconnect=False):
#   global _dbs
#   if reconnect:
#     disconnect(alias)

#   if alias not in _dbs:
#     conn = get_connection(alias)
#     conn_settings = _connection_settings[alias]
#     db = conn[conn_settings['name']]
#     # Authenticate if necessary
#     if conn_settings['username'] and conn_settings['password']:
#       db.authenticate(conn_settings['username'], conn_settings['password'],
#         source=conn_settings['auth_source'])
#     _dbs[alias] = db
#   print "Using get_db"
#   return _dbs[alias]


class MethodRewriteMiddleware(object):
    """Rewrites POST with ending url /patch /put /delete into a proper PUT, PATCH, DELETE.
    Also removes the ending part of the url within flask, while user will see same URL"""

    applied_methods = ['PUT', 'PATCH', 'DELETE']

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if environ['REQUEST_METHOD'] == 'POST':
            args = url_decode(environ['QUERY_STRING'])
            method = args.get('method', '').upper()
            if method and method in self.applied_methods:
                method = method.encode('ascii', 'replace')
                environ['REQUEST_METHOD'] = method
        return self.app(environ, start_response)

import re

class FablrRule(Rule):
    """Sorts rules starting with a variable, e.g. /<xyx>, last"""
    allow_domains = False
    default_host = None
    re_sortkey = re.compile(r'[^\/<]')

    def bind(self, map, rebind=False):
        # if self.subdomain:  # Convert subdomain to full host rule
            # self.host = self.subdomain + '.' + self.default_host
            # Treat subdomains as full domain, as Flask-Classy only supports setting subdomain currently
        thehost = self.subdomain or None

        if thehost and not self.allow_domains:
            self.rule = "/_" + thehost + "/" + self.rule.lstrip("/")
            self.subdomain = ''  # Hack, parent bind will check if None, '' will be read as having one
            self.host = ''
        else:
            self.host = thehost or self.default_host
        # Will transform rule to string of / and <, to ensure we sort by path with non-variables before variables
        # That means that /worlds/ab will come before /<pub>/ab
        self.matchorder = FablrRule.re_sortkey.sub('', self.rule)
        super(FablrRule, self).bind(map, rebind)

    def match_compare_key(self):
        tup = (self.matchorder,) + super(FablrRule, self).match_compare_key()
        return tup


def db_config_string(app):
    # Clean to remove password
    return re.sub(r':([^/]+?)@', ':<REMOVED_PASSWORD>@', app.config['MONGODB_HOST'])


def is_db_empty(db):
    print db.collection_names(False)


db = MongoEngine()
# TODO this is a hack to turn of schema validation, as it reacts when database contains fields
# not in model, which can happen if we have a database that is used for branches with both new and old schema
# db.Document = DynamicDocument

# db.Document._meta['auto_create_index'] = False


def start_db(app):
    # while True:
    dbstring = db_config_string(app)
    # db_config = {
    #     'MONGODB_SETTINGS': {
    #         'host': app.config['MONGODB_HOST'],
    #         'connectTimeoutMS': 1000,
    #         'serverSelectionTimeoutMS': 1000
    #     }
    # }
    db.init_app(app)
    # try:
    with app.app_context():
        num_collections = len(db.connection.get_default_database().collection_names(False))
        if not app.debug and num_collections == 0:
            print >> sys.stderr, "Database %s is empty, run python manage.py db_setup" % dbstring
    # except ConnectionFailure as e:
    #     print >> sys.stderr, "Database connection failure %s: %s" % (e.__class__, e)
    #     exit(1)

        # break
        # except None:
        #     print >> sys.stderr, "Cannot connect to database: %s [waiting 20s]" % dbstring
        #     time.sleep(20)


class MongoJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Document) or isinstance(o, QuerySet):
            return o.to_mongo()
        elif isinstance(o, ObjectId) or isinstance(o, QuerySet):
            return str(o)
        elif isinstance(o, Pagination):
            return {'page': o.page, 'per_page': o.per_page, 'pages': o.pages, 'total': o.total}
        if isinstance(o, _LazyString):  # i18n Babel uses lazy strings, need to be treated as string here
            return unicode(o)
        return JSONEncoder.default(self, o)


from flask_babel import Babel


babel = Babel()
configured_locales = set()

from flask import g, request, current_app, session


def pick_locale():
    """
    Called by Flask Babel on each request to determine which locale to use, subsequently cached during request.

    - There are two types of available locales - the content and the interface.
    - No content locale means it can be assumed that there is no content to localize (only interface)
    - Content locales need to be set in g object before any translation happens, or you need to call refresh() on Babel to
      run this function again
    - User locale preference is either a single choice from URL or cookie, otherwise from HTTP request lang.
    - Never allow mismatch of interface and content locale.
    - If not match can be made, return 404 if the locale was specified in URL, otherwise fallback to default locale
    (consider always making locale part of URL to have no ambiguity)

    :return:
    """

    content_locales = g.get('content_locales', None)
    if not isinstance(content_locales, set):
        content_locales = None
    g.available_locales = {k: Locale.parse(k).language_name.capitalize() for k in
                           (configured_locales & content_locales if content_locales else configured_locales)}

    if 'locale' in request.args:
        preferred_locale = request.args['locale']
        if preferred_locale not in g.available_locales:
            # Hard abort as URL specified an unavailable locale
            abort(404, u"Unsupported locale %s for this resource (supports %s)" % (preferred_locale, g.available_locales))
        else:
            session['locale'] = preferred_locale
    elif 'locale' in session:
        preferred_locale = session.get('locale')
    else:
        preferred_locale = request.accept_languages.best_match(g.available_locales.keys())
    if preferred_locale not in g.available_locales:
        preferred_locale = current_app.config.get('BABEL_DEFAULT_LOCALE', 'en')

    # print "Got lang %s, available_locale %s" % (preferred_locale, g.available_locales)
    return preferred_locale


from flask_wtf.csrf import CsrfProtect

csrf = CsrfProtect()


# Inspired by flask webpack but without any cruft
def init_assets(app):
    try:
        with app.open_resource(app.config.get('WEBPACK_MANIFEST_PATH'), 'r') as stats_json:
            stats = load(stats_json)
            app.assets = stats['assets']
    except IOError as io:
        raise RuntimeError(
            "Asset management requires 'WEBPACK_MANIFEST_PATH' to be set and "
            "it must point to a valid json file. It was %s. %s" % (app.config.get('WEBPACK_MANIFEST_PATH'), io))


from markdown.extensions import Extension
from markdown.inlinepatterns import ImagePattern, IMAGE_LINK_RE
from markdown.util import etree
import re


class GalleryList(Treeprocessor):
    def run(self, root):
        for ul in root.findall('ul'):
            if len(ul) and ul[0].text:
                h_text = ul[0].text.strip()
                if h_text in ['gallery-center', 'gallery-wide', 'gallery-side']:
                    ul.set('class', 'gallery %s' % h_text)
                    ul[0].set('class', 'hide')
                    for li in list(ul)[1:]:
                        li.set('class', 'gallery-item')
                        a_el = etree.Element('a')
                        a_el.set('href', '#')
                        a_el.set('class', 'zoomable')
                        a_el.extend(list(li))  # list(li) enumerates all children of li
                        for e in li:
                            # Image to set its aspect once loaded, we dont know width/height here
                            e.set('onload', 'set_aspect(this)')
                            li.remove(e)
                        li.append(a_el)
                        # imgs = list(ul.iterfind('.//img'))
                        # txts = list(ul.itertext())[1:]  # Skip first as it is the current node, e.g. ul
                        # # if there are same amount of images as text items, and the text is zero, we have only images in the list
                        # # however, they may be nested in other tags, e.g. a
                        # if ''.join(txts).strip() == '':  # All text nodes empty in the list


class AutolinkedImage(Extension):
    def extendMarkdown(self, md, md_globals):
        md.treeprocessors['gallery'] = GalleryList()


from jinja2 import Undefined


class SilentUndefined(Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        print 'JINJA2: something was undefined!'  # TODO, should print correct log error
        return None


def currentyear(nada):
    return datetime.utcnow().strftime('%Y')


def dict_without(value, *args):
    return {k: value[k] for k in value.keys() if k not in args}


def dict_with(value, **kwargs):
    z = value.copy()
    z.update(kwargs)
    return z
