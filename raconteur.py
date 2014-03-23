"""
  raconteur.raconteur
  ~~~~~~~~~~~~~~~~

  Main raconteur application class, that initializes the Flask application,
  it's blueprints, plugins and template filters.

  :copyright: (c) 2014 by Raconteur
"""

import logging
import os
from re import compile
from flask import Flask, Markup, render_template, request, redirect, url_for, flash, g, make_response, current_app

from auth import Auth

# from admin import Admin

from flask.json import JSONEncoder
from flask.ext.mongoengine import MongoEngine, Pagination
from flask.ext.mongoengine.wtf import model_form
from flaskext.markdown import Markdown
from flask_wtf.csrf import CsrfProtect
# Babel
from flask.ext.babel import Babel
from flask.ext.babel import lazy_gettext as _
from mongoengine import Document, QuerySet
from markdown.extensions import Extension
from markdown.inlinepatterns import ImagePattern, IMAGE_LINK_RE
from markdown.util import etree

the_app = None
db = None
auth = None

app_states = {
  # Private = Everything locked down, no access to database (due to maintenance)
  "private": False,
  # Protected = Site is fully visible. Resources are shown on a case-by-case (depending on default access allowance). Admin is allowed to log in.
  "protected": False,
  # Public = Everyone is allowed to log in and create new accounts
  "public": True
}

app_features = {
  "tools": True,
  "join": False
}

def is_private():
  return app_states["private"]


def is_protected():
  return app_states["protected"]


def is_public():
  return app_states["public"]

def is_allowed_access(user):
  if is_private():
    return False
  elif is_protected():
    return user.admin if user else False
  else:
    return True

class MongoJSONEncoder(JSONEncoder):
  def default(self, o):
    if isinstance(o, Document) or isinstance(o, QuerySet):
      return o.to_json()
    elif isinstance(o, Pagination):
      return {'page':o.page, 'per_page':o.per_page, 'total':o.total}
    return JSONEncoder.default(self, o)

class NewImagePattern(ImagePattern):
  def handleMatch(self, m):
    el = super(NewImagePattern, self).handleMatch(m)
    alt = el.get('alt')
    src = el.get('src')
    parts = alt.rsplit('|',1)
    el.set('alt',parts[0])
    if len(parts)==2:
      el.set('class', parts[1])
      if parts[1] in ['gallery', 'thumb']:
        el.set('src', src.replace('/asset/','/asset/thumbs/'))
    a_el = etree.Element('a')
    a_el.set('class', 'imagelink')
    a_el.append(el)
    a_el.set('href', src)
    return a_el

class AutolinkedImage(Extension):
  def extendMarkdown(self, md, md_globals):
    # Insert instance of 'mypattern' before 'references' pattern
    md.inlinePatterns["image_link"] = NewImagePattern(IMAGE_LINK_RE, md)

default_options = {
  'MONGODB_SETTINGS': {'DB':'raconteurdb'},
  'SECRET_KEY':'raconteur',
  'LANGUAGES': {
    'en': 'English',
    'sv': 'Swedish'
  }
}

def create_app(**kwargs):
  the_app = Flask('raconteur')  # Creates new flask instance
  logger = logging.getLogger(__name__)
  logger.info("App created: %s", the_app)
  the_app.config.update(default_options)  # default, dummy settings
  the_app.config.update(kwargs)  # default, dummy settings
  if 'RACONTEUR_CONFIG_FILE' in os.environ:
    the_app.config.from_envvar('RACONTEUR_CONFIG_FILE', silent=True)  # db-settings and secrets, should not be shown in code
  if 'RACONTEUR_INIT_MODE' in os.environ:
    the_app.config['INIT_MODE'] = os.environ.get('RACONTEUR_INIT_MODE')
  the_app.config['PROPAGATE_EXCEPTIONS'] = the_app.debug
  the_app.json_encoder = MongoJSONEncoder
  db = MongoEngine(the_app)  # Initiate the MongoEngine DB layer
  # we can't import models before db is created, as the model classes are built on runtime knowledge of db

  from model.user import User
  auth = Auth(the_app, db, user_model=User)

  md = Markdown(the_app, extensions=['attr_list'])
  md.register_extension(AutolinkedImage)
  csrf = CsrfProtect(the_app)
  babel = Babel(the_app)

  from controller.world import world_app as world
  from controller.social import social
  from controller.generator import generator
  from controller.campaign import campaign_app as campaign
  from resource import ResourceError, ResourceHandler, ResourceAccessStrategy, RacModelConverter
  from model.world import ImageAsset

  the_app.register_blueprint(world, url_prefix='/world')
  if app_features["tools"]:
    the_app.register_blueprint(generator, url_prefix='/generator')
  the_app.register_blueprint(social, url_prefix='/social')
  the_app.register_blueprint(campaign, url_prefix='/campaign')

  init_mode = the_app.config.get('INIT_MODE', None)
  if init_mode:
    if init_mode=='reset':
      setup_models()
    elif init_mode=='lang':
      setup_language()
    elif init_mode=='test':
      run_tests()
    # Clear the init mode flag to avoid running twice accidentaly
    del os.environ['INIT_MODE']

def run_the_app(debug):
  logger.info("Running local instance")
  the_app.run(debug=True)

def setup_models():
  logger.info("Resetting data models")
  db.connection.drop_database(the_app.config['MONGODB_SETTINGS']['DB'])
  from test_data import model_setup
  model_setup.setup_models()
  # This hack sets a unique index on the md5 of image files to prevent us from 
  # uploading duplicate images
  # db.connection[the_app.config['MONGODB_SETTINGS']['DB']]['images.files'].ensure_index(
 #        'md5', unique=True, background=True)

def validate_model():
  is_ok = True
  pkgs = ['model.campaign', 'model.misc', 'model.user', 'model.world']  # Look for model classes in these packages
  for doc in db.Document._subclasses:  # Ugly way of finding all document type
    if doc != 'Document':  # Ignore base type (since we don't own it)
      for pkg in pkgs:
        try:
          cls = getattr(__import__(pkg, fromlist=[doc]), doc)  # Do add-hoc import/lookup of type, simillar to from 'pkg' import 'doc'
          try:
            cls.objects()  # Check all objects of type
          except TypeError:
            logger.error("Failed to instantiate %s", cls)
            is_ok = False
        except AttributeError:
          pass  # Ignore errors from getattr
        except ImportError:
          pass  # Ignore errors from __import__
  logger.info("Model has been validated" if is_ok else "Model has errors, aborting startup")
  return is_ok

def setup_language():
  os.system("pybabel compile -d translations/");

def run_tests():
  logger.info("Running unit tests")
  from tests import app_test
  app_test.run_tests()


@current_app.before_request
def load_user():
  g.feature = app_features

###
### Basic views (URL handlers)
###
@current_app.route('/')
def homepage():
  return render_template('homepage.html')


@auth.admin_required
@current_app.route('/admin/', methods=['GET', 'POST'])
def admin():
  if request.method == 'GET':
    return render_template('admin.html', states=app_states, features=app_features)
  elif request.method == 'POST':
    self.app_states = request.form['states']
    self.app_features = request.form['features']


JoinForm = model_form(User)

# Page to sign up, takes both GET and POST so that it can save the form
@current_app.route('/join/', methods=['GET', 'POST'])
def join():
  if not app_features["join"]:
    raise ResourceError(403)
  if request.method == 'POST' and request.form['username']:
    # Read username from the form that was posted in the POST request
    try:
      User.objects().get(username=request.form['username'])
      flash(_('That username is already taken'))
    except User.DoesNotExist:
      user = User(
          username=request.form['username'],
          email=request.form['email'],
      )
      user.set_password(request.form['password'])
      user.save()

      auth.login_user(user)
      return redirect(url_for('homepage'))
  join_form = JoinForm()
  return render_template('join.html', join_form=join_form)

# This should be a lower memory way of doing this
# try:
#     file = FS.get(ObjectId(oid))
#     return Response(file, mimetype=file.content_type, direct_passthrough=True)
# except NoFile:
#     abort(404)
# or this
# https://github.com/RedBeard0531/python-gridfs-server/blob/master/gridfs_server.py
@current_app.route('/asset/<slug>')
def asset(slug):
  asset = ImageAsset.objects(slug=slug).first_or_404()
  response = make_response(asset.image.read())
  response.mimetype = asset.mime_type
  return response

@current_app.route('/asset/thumbs/<slug>')
def asset_thumb(slug):
  asset = ImageAsset.objects(slug=slug).first_or_404()
  response = make_response(asset.image.thumbnail.read())
  response.mimetype = asset.mime_type
  return response

imageasset_strategy = ResourceAccessStrategy(ImageAsset, 'images', form_class=
  model_form(ImageAsset, exclude=['image','mime_type', 'slug'], converter=RacModelConverter()))
class ImageAssetHandler(ResourceHandler):
  def new(self, r):
    '''Override new() to do some custom file pre-handling'''
    self.strategy.check_operation_any(r['op'])
    form = self.form_class(request.form, obj=None)
    # del form.slug # remove slug so it wont throw errors here
    if not form.validate():
      r['form'] = form
      raise ResourceError(400, r)
    file = request.files['imagefile']
    item = ImageAsset(creator=g.user)
    if file:
      item.make_from_file(file)
    elif request.form.has_key('source_image_url'):
      item.make_from_url(request.form['source_image_url'])
    else:
      abort(403)
    form.populate_obj(item)
    item.save()
    r['item'] = item
    r['next'] = url_for('asset', slug=item.slug)
    return r

ImageAssetHandler.register_urls(the_app, imageasset_strategy)


# @current_app.template_filter('dictreplace')
# def dictreplace(s, d):
#   if d and len(d) > 0:
#     parts = s.split("__")
#     # Looking for variables __key__ in s.
#     # Splitting on __ makes every 2nd part a key, starting with index 1 (not 0)
#     for i in range(1, len(parts), 2):
#       parts[i] = d[parts[i]]  # Replace with dict content
#     return ''.join(parts)
#   return s


# i18n
@babel.localeselector
def get_locale():
  return "sv"  # request.accept_languages.best_match(LANGUAGES.keys()) # Add 'sv' here instead to force swedish translation.
