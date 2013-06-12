
from flask import Flask, Markup, render_template, request, redirect, url_for, flash
from datetime import datetime
from flask_peewee.auth import Auth
from flask_peewee.db import Database
from peewee import Model
from re import compile
from flaskext.markdown import Markdown
import os

try:
  import simplejson as json
except ImportError:
  import json

class LocalConfiguration(object): # basic configuration if running locally, uses Sqlite
    DATABASE = {
    #     'name': 'example.db',
    #     'engine': 'peewee.SqliteDatabase',
    #     'check_same_thread': False,
#        'user': 'admin',
#        'password': 'xzUqQfsuJlhN',
#        'host':os.environ['OPENSHIFT_POSTGRESQL_DB_HOST'],
#        'port':os.environ['OPENSHIFT_POSTGRESQL_DB_PORT'],
        'name': 'martin',
        'engine': 'peewee.PostgresqlDatabase',
        'threadlocals': True,
        #'check_same_thread': False,
    }
    SECRET_KEY = 'shhhh'

class RaconteurDB(Database):
  def get_model_class(self):
    class BaseModel(Model):
        class Meta:
            database = self.database
        # def __unicode__(self): # plan to override string representations, gave up TODO
        #     print "__str__ called"
        #     return str(self)
    return BaseModel

the_app = None
db = None
auth = None
admin = None

if the_app == None:
  from app import is_debug, is_deploy
  # is_deploy = True
  # os.environ['OPENSHIFT_POSTGRESQL_DB_HOST']='127.0.0.1'
  # os.environ['OPENSHIFT_POSTGRESQL_DB_PORT']='8080'
  the_app = Flask('raconteur') # Creates new flask instance
  print "App created"
  print the_app
  if is_deploy:
    from deploy import DeployConfiguration
    the_app.config.from_object(DeployConfiguration)
  else:
    the_app.config.from_object(LocalConfiguration)
  the_app.config['DEBUG'] = is_debug
  the_app.config['PROPAGATE_EXCEPTIONS'] = is_debug
  db = RaconteurDB(the_app) # Initiate the peewee DB layer
  # we can't import models before db is created, as the model classes are built on runtime knowledge of db
  
  import model_setup
  from models import User
  from admin import create_admin
  from api import create_api

  auth = Auth(the_app, db, user_model=User)

  Markdown(the_app)

  admin = create_admin(the_app, auth)
  api = create_api(the_app, auth)

  from world import world_app as world
  from social import social
  from generator import generator
  from campaign import campaign

  the_app.register_blueprint(world, url_prefix='/world')
  the_app.register_blueprint(generator, url_prefix='/generator')
  the_app.register_blueprint(social, url_prefix='/social')
  the_app.register_blueprint(campaign, url_prefix='/campaign')
  #print the_app.url_map
  
def setup_models():
  model_setup.setup_models()

###
### Basic views (URL handlers)
###
@the_app.route('/')
def homepage():
  return render_template('homepage.html')
    #if auth.get_logged_in_user():
    #    return private_timeline()
    #else:
    #    return public_timeline()

# Page to sign up, takes both GET and POST so that it can save the form
@the_app.route('/join/', methods=['GET', 'POST'])
def join():
    if request.method == 'POST' and request.form['username']:
        # Read username from the form that was posted in the POST request
        try:
            user = User.get(username=request.form['username'])
            flash('That username is already taken')
        except User.DoesNotExist:
            user = User(
                username=request.form['username'],
                email=request.form['email'],
                join_date=datetime.datetime.now()
            )
            user.set_password(request.form['password'])
            user.save()
            
            auth.login_user(user)
            return redirect(url_for('homepage'))

    return render_template('join.html')

###
### Template filters
###
@the_app.template_filter('is_following')
def is_following(from_user, to_user):
    return from_user.is_following(to_user)
    
wikify_re = compile(r'\b(([A-Z]+[a-z]+){2,})\b')

@the_app.template_filter('wikify')
def wikify(s):
    return Markup(wikify_re.sub(r'<a href="/world/\1/">\1</a>', s))

@the_app.template_filter('dictreplace')
def dictreplace(s, d):
    #print "Replacing %s with %s" % (s,d)
    if d and len(d) > 0:
        parts = s.split("__")
        # Looking for variables __key__ in s.
        # Splitting on __ makes every 2nd part a key, starting with index 1 (not 0)
        for i in range(1,len(parts),2):
            parts[i] = d[parts[i]] # Replace with dict content
        return ''.join(parts)
    return s