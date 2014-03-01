"""
    raconteur.auth
    ~~~~~~~~~~~~~~~~

   Authentication module that provides login and logout features on top of 
   User model. Adapted from flask-peewee.

    :copyright: (c) 2014 by Raconteur
"""

import functools
import os
import random

from flask import Blueprint, render_template, abort, request, session, flash, redirect, url_for, g
from flask_wtf import Form
from wtforms import TextField, PasswordField, validators
from hashlib import sha1

current_dir = os.path.dirname(__file__)

# Provides

# borrowing these methods, slightly modified, from django.contrib.auth
def get_hexdigest(salt, raw_password):
    return sha1(salt + raw_password).hexdigest()

def make_password(raw_password):
    salt = get_hexdigest(str(random.random()), str(random.random()))[:5]
    hsh = get_hexdigest(salt, raw_password)
    return '%s$%s' % (salt, hsh)

def check_password(raw_password, enc_password):
    salt, hsh = enc_password.split('$', 1)
    return hsh == get_hexdigest(salt, raw_password)

def get_next():
    if not request.query_string:
        return request.path
    return '%s?%s' % (request.path, request.query_string)

class LoginForm(Form):
    username = TextField('Username', validators=[validators.Required()])
    password = PasswordField('Password', validators=[validators.Required()])


class BaseUser(object):
    def set_password(self, password):
        self.password = make_password(password)

    def check_password(self, password):
        return check_password(password, self.password)


class Auth(object):
    def __init__(self, app, db, user_model=None, prefix='/accounts', name='auth',
                 clear_session=False, default_next_url='/'):
        self.app = app
        self.db = db

        self.User = user_model or self.get_user_model()

        self.blueprint = self.get_blueprint(name)
        self.url_prefix = prefix

        self.clear_session = clear_session
        self.default_next_url = default_next_url

        self.setup()

    def get_context_user(self):
        return {'user': self.get_logged_in_user()}

    def get_user_model(self):
        class User(self.db.Model, BaseUser):
            username = CharField(unique=True)
            password = CharField()
            email = CharField(unique=True)
            active = BooleanField()
            admin = BooleanField(default=False)

            def __unicode__(self):
                return self.username

        return User

    def get_blueprint(self, blueprint_name):
        return Blueprint(
            blueprint_name,
            __name__,
            static_folder=os.path.join(current_dir, 'static'),
            template_folder=os.path.join(current_dir, 'templates'),
        )

    def get_urls(self):
        return (
            ('/logout/', self.logout),
            ('/login/', self.login),
        )

    def get_login_form(self):
        return LoginForm

    def test_user(self, test_fn):
        def decorator(fn):
            @functools.wraps(fn)
            def inner(*args, **kwargs):
                user = self.get_logged_in_user()
                
                if not user or not test_fn(user):
                    login_url = url_for('%s.login' % self.blueprint.name, next=get_next())
                    return redirect(login_url)
                return fn(*args, **kwargs)
            return inner
        return decorator

    def login_required(self, func):
        return self.test_user(lambda u: True)(func)
    
    def admin_required(self, func):
        return self.test_user(lambda u: u.admin)(func)

    def authenticate(self, username, password):
        active = self.User.objects(active=True)
        try:
            user = active(username=username).get()
        except self.User.DoesNotExist:
            return False
        else:
            if not user.check_password(password):
                return False

        return user

    def login_user(self, user):
        session['logged_in'] = True
        session['user_pk'] = str(user.id)
        session.permanent = True
        g.user = user
        flash('You are logged in as %s' % user.username, 'success')

    def logout_user(self, user):
        if self.clear_session:
            session.clear()
        else:
            session.pop('logged_in', None)
        g.user = None
        flash('You are now logged out', 'success')

    def get_logged_in_user(self):
        if session.get('logged_in'):
            if getattr(g, 'user', None):
                return g.user

            try:
                return self.User.objects(
                    active=True, id=session.get('user_pk')
                ).get()
            except self.User.DoesNotExist:
                session.pop('logged_in', None)
                pass

    def login(self):
        error = None
        Form = self.get_login_form()

        if request.method == 'POST':
            form = Form(request.form)
            if form.validate():
                authenticated_user = self.authenticate(
                    form.username.data,
                    form.password.data,
                )
                if authenticated_user:
                    self.login_user(authenticated_user)
                    return redirect(
                        request.args.get('next') or \
                        self.default_next_url
                    )
                else:
                    flash('Incorrect username or password', 'warning')
        else:
            form = Form()

        return render_template('includes/login.html', error=error, form=form)

    def logout(self):
        self.logout_user(self.get_logged_in_user())
        return redirect(
            request.args.get('next') or \
            self.default_next_url
        )

    def configure_routes(self):
        for url, callback in self.get_urls():
            self.blueprint.route(url, methods=['GET', 'POST'])(callback)

    def register_blueprint(self, **kwargs):
        self.app.register_blueprint(self.blueprint, url_prefix=self.url_prefix, **kwargs)

    def load_user(self):
        g.user = self.get_logged_in_user()

    def register_handlers(self):
        self.app.before_request(self.load_user)

    def register_context_processors(self):
        self.app.template_context_processors[None].append(self.get_context_user)

    def setup(self):
        self.configure_routes()
        self.register_blueprint()
        self.register_handlers()
        self.register_context_processors()
