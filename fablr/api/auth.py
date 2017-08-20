"""
    fablr.auth
    ~~~~~~~~~~~~~~~~

   Authentication module that provides login and logout features on top of
   User model, uses Auth0.com as authentication backend.

    :copyright: (c) 2016 by Helmgast AB
"""

from builtins import str
import functools
import json
from datetime import datetime

import requests
from flask import Blueprint, request, session, flash
from flask import abort
from flask import current_app
from flask import logging
from flask import redirect, url_for, g
from flask import render_template
from flask_babel import lazy_gettext as _
from mongoengine import MultipleObjectsReturned, DoesNotExist, Q

from fablr.model.misc import safe_next_url, set_lang_options
from fablr.model.user import User, UserStatus
from fablr.model.world import Publisher

logger = current_app.logger if current_app else logging.getLogger(__name__)

auth_app = Blueprint('auth', __name__, template_folder='../templates/auth')


# single signon
# set cookie on fablr.co (also works for dev.fablr.co, helmgast.fablr.co, etc
# set cookie on custom domains (helmgast.se, kultdivinitylost.com)
#  method 1 - redirect to them in turn
#  method 2 - embed image requests to a script endpoint
#  method 3 - use AJAX with correct CORS headers on server
# For any of above methods, we need to verify that the request two set the custom domain
# cookies are related to the signon that was just completed, e.g. it needs to be authenticated
# When we visit first custom domain, it wont receive the secure cookie already set on .fablr.co,
# so it needs to be provided in an URL arg. But that URL arg has to be temporary, unguessable and only work
# once, to avoid security holes. CSRF tokens may be one way.
# with this setup there is no subdomain for assets that will not receive cookies

# https://helmgast.eu.auth0.com/authorize?client_id=JAwGB3WgQFDHqQCjRNo0Ij3MPbIEGB1N&response_type=code&redirect_uri=http://*.fablr.co/auth/callback
# https://helmgast.eu.auth0.com/login?client=JAwGB3WgQFDHqQCjRNo0Ij3MPbIEGB1N

# Attach hooks at blueprint init time, instead of at import time
@auth_app.record_once
def on_load(state):
    state.app.before_request(load_user)
    state.app.template_context_processors[None].append(get_context_user)
    state.app.login_required = login_required
    state.app.admin_required = admin_required


def add_auth(user, user_info, next_url):
    if not user.auth_keys:
        user.auth_keys = []

    ak = "{email}|{sub}".format(email=user_info['email'], sub=user_info['sub'])
    # Go through user profile change if we have a new auth method
    new_auth = ak not in user.auth_keys

    if new_auth:
        next_url = url_for('social.UsersView:get', intent='patch', id=user.identifier(), next=next_url)

        user.auth_keys.append(ak)

        # Only delete old info when we have confirmed it using a new login
        migrated = False
        if user.password:
            user.password = None
            migrated = True
        if user.google_auth and user.google_auth.emails and user_info['email'] in user.google_auth.emails:
            user.google_auth = None
            migrated = True
        if user.facebook_auth and user.facebook_auth.emails and user_info['email'] in user.facebook_auth.emails:
            user.facebook_auth = None
            migrated = True
        if migrated:
            flash(_("Your user have been migrated to the new login system, contact us if something doesn't look ok"),
                  'info')
        else:
            # We have migrated before but are now adding an additional auth method
            flash(_("We added %(provider)s authentication using %(email)s to your user, and updated your profile data",
                    provider=user_info['sub'].split('|')[0], email=user_info['email']), 'info')

        if not user.realname:
            user.realname = user_info.get('name', None)
        if not user.username:
            user.username = user_info.get('nickname', None)
        if not user.images:
            picture_url = user_info.get('picture_large', None) or user_info.get('picture', None)
            if picture_url and 'gravatar.com' not in picture_url:
                from fablr.model.asset import FileAsset
                img = FileAsset(owner=user, access_type='hidden', tags=['user'],
                                source_file_url=picture_url)
                try:
                    img.save()
                    user.images = [img]
                except Exception as e:
                    logger.warning(
                        u"Unable to load profile image at sign-in for user {user}: {reason}"
                        .format(user=user, reason=e))
    elif user.status == 'invited':
        # Keep sending to user profile if we are still invited
        next_url = url_for('social.UsersView:get', intent='patch', id=user.identifier(), next=next_url)
        flash(_('Save your profile before you can use your new user!'), 'info')
    else:
        flash(_('You are logged in as %(user)s with %(email)s', user=user, email=user_info['email']), 'success')

    return next_url


@auth_app.route('/callback', subdomain='<pub_host>')
def callback():
    # Note: This callback applies both to login and signup, there is no difference.

    support_email = current_app.config['MAIL_DEFAULT_SENDER']
    code = request.args.get('code', None)
    if not code:
        abort(401)

    token_url = "https://{domain}/oauth/token".format(domain=current_app.config['AUTH0_DOMAIN'])

    token_payload = {
        'client_id': current_app.config['AUTH0_CLIENT_ID'],
        'client_secret': current_app.config['AUTH0_CLIENT_SECRET'],
        'redirect_uri': url_for('auth.callback', pub_host=g.pub_host, _external=True, _scheme=request.scheme),
        'code': code,
        'grant_type': 'authorization_code'
    }
    # Verify the token
    token_info = requests.post(token_url, data=json.dumps(token_payload),
                               headers={'content-type': 'application/json'}).json()
    # Fetch user info
    user_url = "https://{domain}/userinfo?access_token={access_token}" \
        .format(domain=current_app.config['AUTH0_DOMAIN'], access_token=token_info['access_token'])

    user_info = requests.get(user_url).json()

    # Make sure next is a relative URL
    next_url = safe_next_url(default_url='/')

    if not user_info or 'email' not in user_info or 'sub' not in user_info:
        logger.error(u"Unknown user denied login due to missing from backend {info}".format(info=user_info))
        logout_user()
        flash(_('Error logging in, contact %(email)s for support', email=support_email), 'danger')
        return redirect(next_url)  # RETURN IN ERROR

    if not user_info.get('email_verified', False):
        logger.warning(u"{user} denied login due to lacking verification".format(user=user_info))
        logout_user()
        flash(_('Check your email inbox for verification link before you can login'), 'warning')
        return redirect(next_url)  # RETURN IN ERROR

    session_user = get_logged_in_user(require_active=False)

    # Find user that matches the provided auth email
    try:
        auth_user = User.objects(auth_keys__startswith=user_info['email'] + '|').get()
        if auth_user.status == 'deleted':
            flash(_('This user is deleted and cannot be used. Contact %(email)s for support.', email=support_email),
                  'error')
            logger.error(u'{user} tried to login but the user is deleted'.format(user=user_info['email']))
            return redirect(next_url)  # RETURN IN ERROR
    except MultipleObjectsReturned:
        logger.error(u"Multiple users found with same email {email}, shouldn't happen".format(email=user_info['email']))
        logout_user()
        flash(_('Multiple users with same email, contact %(email)s for support', email=support_email), 'danger')
        return redirect(next_url)  # RETURN IN ERROR
    except DoesNotExist:
        # TODO while we are migrating, also match just email field
        auth_user = User.objects(Q(email=user_info['email']) |
                                 Q(facebook_auth__emails=user_info['email']) |
                                 Q(google_auth__emails=user_info['email'])).first()  # Returns None if not found

    if session_user:
        # Someone already logged in, means they are trying to add more auths to current account
        user = session_user
        if auth_user and session_user != auth_user:
            # We have two different users that might be trying to merge
            if session_user.status == 'invited' and auth_user.status == 'active':
                # Move over auths from old user before we delete it
                for ak in session_user.auth_keys:
                    auth_user.auth_keys.append(ak)
                logout_user()
                session_user.delete()
                user = auth_user
            else:
                logger.error(u"User tried to add auth {auth} while logged in as {user}, cannot merge".format(
                    auth=auth_user, user=session_user))
                logout_user()
                flash(_('Cannot add this auth to logged in user %(user)s, contact %(email)s for support',
                        user=session_user.email, email=support_email), 'danger')
                return redirect(next_url)  # RETURN IN ERROR
        else:
            # Will add new auth to session user, or just login
            next_url = add_auth(session_user, user_info, next_url)

    elif auth_user:
        # Will add new auth to auth user, or just login
        next_url = add_auth(auth_user, user_info, next_url)
        user = auth_user
    else:
        # We have neither user from session or from login. Create a new user!
        user = User(email=user_info['email'])
        user.save()  # So that we are guaranteed to have a user id for add_auth()
        logger.info(u"New user {user} created using {identities}".format(
            user=user_info['email'],
            identities=user_info['identities']))
        flash(_('Your new user have been created.'), 'info')
        next_url = add_auth(user, user_info, next_url)

    user.last_login = datetime.utcnow()
    user.logged_in = True
    # user.status = 'active'
    user.save()

    login_user(user)
    return redirect(next_url)


@auth_app.route('/sso', subdomain='<pub_host>')
def sso():
    next_url = safe_next_url()
    callback_url = url_for('auth.callback', pub_host=g.pub_host, next=next_url, _external=True, _scheme=request.scheme)
    auth0_url = 'https://{domain}/authorize?client_id={client_id}&response_type=code&redirect_uri={callback}'.format(
        domain=current_app.config['AUTH0_DOMAIN'],
        client_id=current_app.config['AUTH0_CLIENT_ID'],
        callback=callback_url)
    return redirect(auth0_url)


@auth_app.route('/logout', subdomain='<pub_host>')
def logout():
    # Clears logged in flag to effectively log out from all domains, even if session is only cleared in current domain.
    publisher = Publisher.objects(slug=g.pub_host).first()
    set_lang_options(publisher)

    logout_user()
    flash(_('You are now logged out'), 'success')
    auth0_url = 'https://{domain}/v2/logout?returnTo={home}'.format(
        domain=current_app.config['AUTH0_DOMAIN'],
        home=url_for('world.ArticlesView:publisher_home', _external=True, _scheme=request.scheme))

    return redirect(auth0_url)


@auth_app.route('/login', subdomain='<pub_host>')
def login():
    publisher = Publisher.objects(slug=g.pub_host).first()
    set_lang_options(publisher)
    return render_template('auth/login.html')


@auth_app.route('/join')
def join():
    # TODO redirect to the Auth0 screen?
    abort(404)


def get_context_user():
    return {'user': get_logged_in_user()}


def load_user():
    g.user = get_logged_in_user()


# TODO update or depcrecate
def check_user(test_fn):
    def decorator(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            user = get_logged_in_user()
            if not user:
                return redirect(url_for('auth.login'))

            if not test_fn(user):
                return redirect(url_for('auth.login'))

            return fn(*args, **kwargs)

        return inner

    return decorator


def login_required(func):
    return check_user(lambda u: True)(func)


def admin_required(func):
    return check_user(lambda u: u.admin)(func)


def login_user(user):
    # cart_id = session.get('cid', None)
    session['uid'] = str(user.id)  # The user ID to save for longer
    # if cart_id:
    #     session['cid'] = cart_id  # A cart id from the shop that could come from before we login
    session.permanent = True  # Default 30 days
    g.user = user


def logout_user():
    session.clear()
    if getattr(g, 'user', None):
        g.user.logged_in = False
        g.user.save()
        g.user = None


def get_logged_in_user(require_active=True):
    u = getattr(g, 'user', None)  # See if we already fetched it in this request
    if not u:
        uid = session.get('uid', None)
        if uid:
            try:
                u = User.objects(id=uid).first()
                if u:
                    if not u.logged_in or (require_active and u.status != UserStatus.active):
                        logger.warn("User {user} forced out: logged_in={logged_in}, u.status={status}, require_active={active}".
                                    format(user=u, logged_in=u.logged_in, status=u.status, active=require_active))
                        # We are logged out or user has become other than active
                        return None

                    if "as_user" in request.args and u and u.admin:
                        as_user = request.args['as_user']
                        if as_user == 'none':
                            return None  # Simulate no logged in user
                        u2 = User.objects(email=as_user).first()
                        if u2:
                            logger.debug("User %s masquerading as %s" % (u, u2))
                            return u2
                else:
                    logger.warn("No user in database with uid {uid}".format(uid=uid))
            except Exception as e:
                logger.error(e)
                logout_user()
    return u  # Might be None if all failed above