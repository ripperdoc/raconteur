"""
  fablr.resource
  ~~~~~~~~~~~~~~~~

  An internal library for generating REST-like URL routes and request
  handling functionality for most of Fablr's models. This provides
  DRYness of code and simplified addition of new models.

  :copyright: (c) 2014 by Helmgast AB
"""

import inspect
import logging
import pprint
import re
import sys

from flask import request, render_template, flash, redirect, url_for, abort, g, current_app
from flask.ext.babel import lazy_gettext as _
from flask.ext.classy import FlaskView
from flask.ext.mongoengine import Pagination
from flask.ext.mongoengine.wtf import model_form
from flask.ext.mongoengine.wtf.fields import ModelSelectField, NoneStringField
from flask.ext.mongoengine.wtf.models import ModelForm
from flask.ext.mongoengine.wtf.orm import ModelConverter, converts
from flask import Response
from flask.json import jsonify
from flask.views import View
from mongoengine.errors import DoesNotExist, ValidationError, NotUniqueError
from werkzeug.exceptions import HTTPException
from wtforms import Form as OrigForm
from wtforms import fields as f, validators as v, widgets
from wtforms.compat import iteritems
from wtforms.widgets import html5

from fablr.model.misc import METHODS
from fablr.model.world import EMBEDDED_TYPES, Article

logger = current_app.logger if current_app else logging.getLogger(__name__)

objid_matcher = re.compile(r'^[0-9a-fA-F]{24}$')


def generate_flash(action, name, model_identifiers, dest=''):
    # s = u'%s %s%s %s%s' % (action, name, 's' if len(model_identifiers) > 1
    #   else '', ', '.join(model_identifiers), u' to %s' % dest if dest else '')
    s = u'%s %s %s' % (_(u'Successfully'), action, name)
    flash(s, 'success')
    return s


mime_types = {
    'html': 'text/html',
    'json': 'application/json',
    'csv': 'text/csv'
}

# import collections
#
# def flatten(d, parent_key='', sep='__'):
#     items = []
#     for k, v in d.items():
#         if v: # we ignore empty values, we don't want to use them
#             new_key = parent_key + sep + k if parent_key else k
#             if isinstance(v, collections.MutableMapping):
#                 items.extend(flatten(v, new_key, sep=sep).items())
#             else:
#                 items.append((new_key, v))
#     return dict(items)


# class BaseArgs(OrigForm):
#     debug = f.BooleanField() # if debug config is on, use this to show extra debug output
#     as_user = f.StringField() # if user is admin, show page as viewed by given username
#     # out = {modal, fragment, html}
#
# # Parse args
# class EditArgs(BaseArgs):
#     # method={PUT, PATCH, DELETE} to use instead of POST from a browser
#     method = f.StringField(validators=[v.AnyOf(['PUT', 'PATCH', 'DELETE'])])
#
#     # next={url} next URL to redirect to after completed POST, PUT, PATCH, DELETE, must be an URL within this website
#     next = f.StringField(validators=v.Regexp(r'^[/?].+')) # match relative urls only for time being
#
# # For GET item
# class GetArgs(BaseArgs):
#     # action={PUT, PATCH, DELETE} intended next action, e.g. to serve a form
#     action = f.StringField(validators=[v.AnyOf(['PUT', 'patch', 'DELETE'])])
#
#     # view={card, table}, type of view of a list, also view={markdown} on articles
#     view = f.StringField(validators=[v.AnyOf(['markdown'])])
#
#     # set prefill fields based on model form
#
#
# # For GET list
# class ListArgs(BaseArgs):
#     # page={1+, default 1}, which page we want to load in a list
#     page = f.IntegerField(validators=[v.NumberRange(1)], default=1)
#
#     # per_page={1+, default 20}, how many items per page of a list
#     per_page = f.IntegerField(validators=[v.NumberRange(-1)], default=20) # -1 means no limit
#
#     # order_by={key}, order a list by given key.
#       If prefixed with - or +, interpret as descending and ascending. Ascending default.
#     # order_by = StringField() # improve to support multiple order_by fields
#
#     # {key}={value}, interpret as a filter for LIST/INDEX views. Only existing, and allowed, fields.
#     # {key} can in turn have the form key__operator or key__subkey, key__subkey__operator
#     # e.g. title__lte or author__name__exists
#     # valid suffixes:
#     # ne, lt, lte, gt, in, nin, mod, all, size, exists, exact, iexact, contains,
#     # icontains, istartswith, endswith, iendswith, match
#     # not__ before all above
#
#     # view={card, table}, type of view of a list, also view={markdown} on articles
#     view = f.StringField(v.AnyOf(['card', 'table']), default='table')
#
#     # q=, free text search this list
#     q = f.StringField()

# def model_args(baseform, model_class, field_names=None):
#     """Builds a form to parse args for a specific model class"""
#     arg_fields = OrderedDict()
#     if field_names:
#         ordering_choices = [u''] # allow empty choice, reduces validation errors
#         for name in field_names:
#             ordering_choices.extend(['+'+name,'-'+name, name])
#         arg_fields['order_by'] = f.StringField(validators=[v.AnyOf(ordering_choices)])
#         key_form = model_form(
#             model_class,
#             base_class=OrigForm,
#             only=field_names,
#             converter=RacModelConverter()
#             )
#         for name in field_names:
#             # Remove all defaults from the model, as they wont be useful for
#             # filtering or prefilling
#             getattr(key_form, name).kwargs.pop('default')
#         arg_fields['queryargs'] = f.FormField(key_form, separator='__')
#     return type(model_class.__name__ + 'Args', (baseform,), arg_fields)

common_args = frozenset(['page', 'per_page', 'debug', 'as_user', 'view', 'q', 'action', 'method', 'next', 'order_by'])

re_operators = re.compile(
    r'__(ne|lt|lte|gt|in|nin|mod|all|size|exists|exact|iexact|contains|'
    'icontains|istartswith|endswith|iendswith|match|not__ne|not__lt|not__lte|'
    'not__gt|not__in|not__nin|not__mod|not__all|not__size|not__exists|'
    'not__exact|not__iexact|not__contains|not__icontains|not__istartswith|'
    'not__endswith|not__iendswith)$')
re_next = re.compile(r'^[/?].+')
re_order_by = re.compile(r'^[+-]')


def prefillable_fields_parser(fields=None):
    fields = frozenset(fields or [])
    return dict(ItemResponse.arg_parser, **{
        'fields': fields
    })


def filterable_fields_parser(fields=None):
    fields = frozenset(fields or [])
    return dict(ListResponse.arg_parser, **{
        'order_by': lambda x: x.lower() if re_order_by.sub('', x.lower()) in fields else None,
        'fields': fields
    })


action_strings = {
    'post': 'posted',
    'put': 'put',
    'patch': 'patched',
    'delete': 'deleted'
}
action_strings_translated = {
    'post': _('posted'),
    'put': _('put'),
    'delete': _('deleted'),
    'patch': _('patched'),
}


def change_endpoint(new_method, current_endpoint=None):
    current_endpoint = (current_endpoint or request.endpoint).rsplit(':', 1)[0] + ':'
    return current_endpoint + new_method


class ResourceResponse(Response):
    arg_parser = {
        # none should remain for subsequent requests
        'debug': lambda x: x.lower() == 'true',
        'as_user': lambda x: x,
        'render': lambda x: x if x in ['json', 'html'] else None
    }

    def __init__(self, resource_view, queries, formats=None, theme=None, extra_args=None):
        # Can be set from Model
        assert resource_view
        self.resource_view = resource_view

        self.resource_queries = []
        assert queries and isinstance(queries, list)
        for q in queries:
            assert isinstance(q, tuple)
            assert isinstance(q[0], basestring)
            setattr(self, q[0], q[1])
            self.resource_queries.append(q[0])  # remember names in order

        self.access = resource_view.access_policy
        self.model = resource_view.model

        # To be set from from route
        self.theme = theme
        self.formats = formats or frozenset(['html','json'])
        self.args = self.parse_args(self.arg_parser, extra_args or {})
        super(ResourceResponse, self).__init__()  # init a blank flask Response

    def auth_or_abort(self):
        instance = getattr(self, 'instance', None)
        auth = self.access.authorize(self.method, instance=instance)
        if not auth:
            raise ResourceError(auth.error_code, r={'TBD': 'TBD'}, message=auth.message)
        else:
            # if there's an intent, we also need to check that it's allowed
            intent = self.args.get('intent', None)
            if intent:
                auth = self.access.authorize(intent, instance=instance)
            self.auth = auth

    def set_theme(self, theme_template):
        self.theme = current_app.jinja_env.get_or_select_template([theme_template, '_page.html'])

    def render(self):
        if self.args['render']:
            best_type = mime_types[self.args['render']]
        else:
            best_type = request.accept_mimetypes.best_match([mime_types[m] for m in self.formats])
        if best_type == 'text/html':
            template_args = vars(self)  # All local and inherited variables
            self.set_data(render_template(self.template, **template_args))
            return self
        elif best_type == 'application/json':
            # TODO this will create a new response, which is a bit of waste
            return jsonify({k: getattr(self, k) for k in self.json_fields})
        else:  # csv
            abort(406)  # Not acceptable content available

    @staticmethod
    def parse_args(arg_parser, extra_args):
        """Parses request args through a form that sets defaults or removes invalid entries
        """
        args = {k: '' for k, v in arg_parser.iteritems()}  # Make copy of arg_parser for args
        # TODO to_dict flattens the request dict, meaning we cannot take multiple
        # values for same URL param (e.g. key=val1&key=val2)
        req_args = dict(request.args.to_dict(), **extra_args)
        # Iterate over arg_parser keys, so that we are guaranteed to have all default keys present
        for k in arg_parser:
            if k is not 'fields':
                args[k] = arg_parser[k](req_args.get(k, ''))
            else:
                args['fields'] = {}
                fields = arg_parser[k]
                for q, w in req_args.iteritems():
                    if q not in arg_parser:
                        new_k = re_operators.sub('', q)  # remove mongo operators from filter key
                        if new_k in fields:
                            args['fields'][q] = w
        # print args, arg_parser
        return args


class ListResponse(ResourceResponse):
    """index, listing of resources"""

    json_fields = frozenset(['query', 'pagination'])
    arg_parser = dict(ResourceResponse.arg_parser, **{
        'page': lambda x: int(x) if x.isdigit() and int(x) > 1 else 1,
        'per_page': lambda x: int(x) if x.lstrip('-').isdigit() and int(x) >= -1 else 20,
        'view': lambda x: x.lower() if x.lower() in ['card', 'table', 'list'] else None,
    })
    method = 'list'

    def __init__(self, resource_view, queries, formats=None, theme=None, extra_args=None):
        list_arg_parser = getattr(resource_view, 'list_arg_parser', None)
        if list_arg_parser:
            self.arg_parser = list_arg_parser
        super(ListResponse, self).__init__(resource_view, queries, formats, theme, extra_args)
        self.template = resource_view.list_template

    @property  # For convenience
    def query(self):
        return getattr(self, self.resource_queries[0])  # first queried item is the query

    @query.setter
    def query(self, x):
        setattr(self, self.resource_queries[0], x)

    def prepare_query(self, paginate=True):  # also filter by authorization, paginate
        """Prepares an original query based on request args provided, such as
        ordering, filtering, pagination etc """
        if self.args['order_by']:
            self.query = self.query.order_by(self.args['order_by'])
        if self.args['fields']:
            self.query = self.query.filter(**self.args['fields'])

        # TODO implement search, use textindex and do ".search_text()"

        # TODO max query size 10000 implied here
        per_page = self.args['per_page'] if paginate and self.args['per_page'] > 0 else 10000
        self.pagination = self.query.paginate(page=self.args['page'], per_page=per_page)
        self.query = self.pagination.items  # set default query as the paginated one


class ItemResponse(ResourceResponse):
    """both for getting and editing items of resources"""

    json_fields = frozenset(['instance'])
    arg_parser = dict(ResourceResponse.arg_parser, **{
        'view': lambda x: x.lower() if x.lower() in 'markdown' else None,
        'intent': lambda x: x if x.upper() in METHODS else None,
        'next': lambda x: x if re_next.match(x) else None
    })

    def __init__(self, resource_view, queries, method='get', formats=None, theme=None, extra_args=None,
                 extra_form_args=None):
        item_arg_parser = getattr(resource_view, 'item_arg_parser', None)
        if item_arg_parser:
            self.arg_parser = item_arg_parser
        super(ItemResponse, self).__init__(resource_view, queries, formats, theme, extra_args)

        self.template = resource_view.item_template
        self.method = method

        if (self.method != 'get') or self.args['intent']:
            form_args = extra_form_args or {}
            if self.args['intent']:
                # we want to serve a form, pre-filled with field values and parent queries
                form_args.update({k: getattr(self, k) for k in self.resource_queries[1:]})
                form_args.update(self.args['fields'])
                if self.args['intent'] == 'post':
                    new_args = dict(request.view_args)
                    new_args.pop('id')
                    self.action_url = url_for(change_endpoint('post'), **new_args)
                else:
                    self.action_url = url_for(request.endpoint, method=self.args['intent'], **request.view_args)
            self.form = self.resource_view.form_class(formdata=request.form, obj=self.instance, **form_args)

    def validate(self):
        return self.form.validate()

    def commit(self, new_instance=None, next_url=None):
        next_url = next_url or self.args['next']
        new_args = dict(request.view_args)
        new_args.pop('id', None)
        if self.method == 'delete':
            self.instance.delete()
            if not next_url:
                next_url = url_for(change_endpoint('index'), **new_args)
        else:
            instance = new_instance or self.instance
            instance.save()
            self.instance = instance  # only save back to response if successful in case we have a post
            if not next_url:
                next_url = url_for(change_endpoint('get'), id=self.instance.slug, **new_args)
        log_event(self.method, self.instance)
        self.next = next_url

    @property  # For convenience
    def instance(self):
        return getattr(self, self.resource_queries[0])  # first queried item is the instance

    @instance.setter
    def instance(self, x):
        setattr(self, self.resource_queries[0], x)

    @property
    def form(self):
        return getattr(self, self.resource_queries[0] + "_form", None)  # first queried item is the instance

    @form.setter
    def form(self, x):
        setattr(self, self.resource_queries[0] + "_form", x)


def log_event(action, instance=None, message='', user=None):
    # <datetime> <user> <action> <object> <message>
    # martin patch article(helmgast)
    user = user or g.user
    if user:
        user.log(action, instance, message)
    else:
        user = "System"
    logger.info("%s %s %s", user, action_strings[action], " (%s)" % message if message else "")
    generate_flash(action_strings_translated[action], 'item', instance)


def parse_out_arg(out_param):
    if out_param == 'json':
        return out_param
    elif out_param in ['page', 'modal', 'fragment']:
        return '_%s.html' % out_param  # to use as template path
        # used in Jinja
    else:
        return None  # Same as page, but set as None in order to not override template given inheritance


class ResourceView(FlaskView):
    def after_request(self, name, response):
        """Makes sure all ResourceResponse objects are rendered before sending onwards"""
        if isinstance(response, ResourceResponse):
            return response.render()
        else:
            return response

    @classmethod
    def register_with_access(cls, app, domain):
        current_app.access_policy[domain] = cls.access_policy
        return cls.register(app)

        # def register(): # overload register method to register access policies automatically


class RacBaseForm(ModelForm):
    # TODO if fields_to_populate are set to use form keys, a deleted field may mean
    # no form key is left in the submitted form, ignoring that delete
    def populate_obj(self, obj, fields_to_populate=None):
        if fields_to_populate:
            # FormFields in form args will have '-' do denote it's subfields. We
            # only want the first part, or it won't match the field names
            new_fields_to_populate = set([fld.split('-', 1)[0] for fld in fields_to_populate])
            print "In populate, fields_to_populate before \n%s\nand after\n%s\n" % (
                fields_to_populate, new_fields_to_populate)
            newfields = [(name, fld) for (name, fld) in iteritems(self._fields) if name in new_fields_to_populate]
        else:
            newfields = iteritems(self._fields)
        for name, field in newfields:
            if isinstance(field, f.FormField) and getattr(obj, name, None) is None and field._obj is None:
                field._obj = field.model_class()  # new instance created
            if isinstance(field, f.FileField) and field.data == '':
                # Don't try to write empty FileField
                continue
            field.populate_obj(obj, name)


class ArticleBaseForm(RacBaseForm):
    def process(self, formdata=None, obj=None, **kwargs):
        super(ArticleBaseForm, self).process(formdata, obj, **kwargs)
        # remove all *article fields that don't match new type
        typedata = Article.type_data_name(self.data.get('type', 'default'))
        for embedded_type in EMBEDDED_TYPES:
            if embedded_type != typedata:
                del self._fields[embedded_type]

    def populate_obj(self, obj, fields_to_populate=None):
        if not type(obj) is Article:
            raise TypeError('ArticleBaseForm can only handle Article models')
        if 'type' in self.data:
            new_type = self.data['type']
            # Tell the Article we have changed type
            obj.change_type(new_type)
        super(ArticleBaseForm, self).populate_obj(obj)


class MultiCheckboxField(f.SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class RacModelSelectField(ModelSelectField):
    # TODO quick fix to change queryset.get(id=...) to queryset.get(pk=...)
    # have been fixed in 0.8 when released
    # This is required to accept custom primary keys
    # https://github.com/MongoEngine/flask-mongoengine/issues/82
    def process_formdata(self, valuelist):
        print valuelist
        if valuelist:
            if valuelist[0] == '__None':
                self.data = None
            else:
                if self.queryset is None:
                    self.data = None
                    return
                try:
                    # clone() because of https://github.com/MongoEngine/mongoengine/issues/56
                    obj = self.queryset.get(pk=valuelist[0])
                    self.data = obj
                except DoesNotExist:
                    self.data = None


class RacModelConverter(ModelConverter):
    @converts('EmbeddedDocumentField')
    def conv_EmbeddedDocument(self, model, field, kwargs):
        kwargs = {
            'validators': [],
            'filters': [],
            'default': field.default or field.document_type_obj,
            # Important. This separator makes the form also able to double as parser
            # for filter args to mongoengine, of type 'author__name'.
            'separator': '__'
        }
        # The only difference to normal ModelConverter is that we use the original,
        # insecure WTForms form base class instead of the CSRF enabled one from
        # flask-wtf. This is because we are in a FormField, and it doesn't require
        # additional CSRFs.

        form_class = model_form(field.document_type_obj, converter=RacModelConverter(),
                                base_class=OrigForm, field_args={})
        return f.FormField(form_class, **kwargs)

    @converts('ReferenceField')
    def conv_Reference(self, model, field, kwargs):
        kwargs['allow_blank'] = not field.required
        return RacModelSelectField(model=field.document_type, **kwargs)

    @converts('URLField')
    def conv_URL(self, model, field, kwargs):
        kwargs['validators'].append(v.URL())
        self._string_common(model, field, kwargs)
        kwargs.setdefault('widget', html5.URLInput())  # Set if not set from before
        return NoneStringField(**kwargs)

    @converts('EmailField')
    def conv_Email(self, model, field, kwargs):
        kwargs['validators'].append(v.Email())
        self._string_common(model, field, kwargs)
        kwargs.setdefault('widget', html5.EmailInput())  # Set if not set from before
        return NoneStringField(**kwargs)

    @converts('IntField')
    def conv_Int(self, model, field, kwargs):
        self._number_common(model, field, kwargs)
        kwargs.setdefault('widget', html5.NumberInput(step='1'))  # Set if not set from before
        return f.IntegerField(**kwargs)

    # Temporarily not used. datetime HTML5 inputs are in unclear support and cant handle seconds
    # @converts('DateTimeField')
    # def conv_DateTime(self, model, field, kwargs):
    #   kwargs.setdefault('widget', html5.DateTimeInput()) # Set if not set from before
    #   return f.DateTimeField(**kwargs)

    @converts('FileField')
    def conv_File(self, model, field, kwargs):
        # TODO add validators
        #     FileRequired(),
        #       FileAllowed(['jpg', 'png'], 'Images only!')
        return f.FileField(**kwargs)

    @converts('StringField')
    def conv_String(self, model, field, kwargs):
        if field.regex:
            kwargs['validators'].append(v.Regexp(regex=field.regex))
        self._string_common(model, field, kwargs)
        if 'password' in kwargs:
            if kwargs.pop('password'):
                return f.PasswordField(**kwargs)
        if field.max_length and field.max_length < 100:  # changed from original code
            return f.StringField(**kwargs)
        return f.TextAreaField(**kwargs)


class Authorization:
    def __init__(self, is_authorized, message='', privileged=False, only_fields=None, error_code=403):
        self.is_authorized = is_authorized
        self.message = message
        self.error_code = error_code
        self.privileged = privileged
        # Privileged means that this authorization would not apply to the public
        # or a normal user. E.g. a user can only edit their own profile (privilege),
        # or an admin can see other people's orders
        self.only_fields = only_fields

    def __repr__(self):
        return "%s%s" % (
            "Authorized" if self.is_authorized else "UNAUTHORIZED", ": %s" % self.message if self.message else "")

    def is_privileged(self):
        return self.privileged

    def __nonzero__(self):
        return self.is_authorized


# Checks if user is logged in and authorized
class ResourceAccessPolicy(object):
    model_class = None
    levels = ['public', 'user', 'private', 'admin']
    translate = {'post': 'new', 'patch': 'edit', 'put': 'edit', 'index': 'list', 'delete': 'edit'}

    def __init__(self, ops_levels=None, get_owner_func=None):
        if not ops_levels:
            self.ops_levels = {
                'view': 'public',
                'list': 'public',
                '_default': 'admin'
            }
        else:
            self.ops_levels = ops_levels
        if not get_owner_func:
            self.get_owner_func = lambda x: getattr(x, 'user', None)
        else:
            self.get_owner_func = get_owner_func

    def authorize(self, op, instance=None):
        if op in self.translate:  # TODO temporary translation between old and new op words, e.g. patch vs edit
            op = self.translate[op]
        if op not in self.ops_levels:
            level = self.ops_levels['_default']
        else:
            level = self.ops_levels[op]
        msg = '%s requires a logged in user' % op
        if level == 'public':
            return Authorization(True, '%s is a publicly allowed operation' % op)
        elif level == 'user':
            if g.user:
                return Authorization(True, msg)
            else:
                return Authorization(False, msg, error_code=401)  # Denoted that the user should log in first
        elif level == 'private':
            if not instance:
                return Authorization(False, 'Error: Cannot apply private access without an instance')
            instance_owner = self.get_owner_func(instance)

            if g.user and g.user.admin:
                return Authorization(True, '%s have access to do private operation %s on instance %s' % (
                    unicode(instance_owner), op, instance), privileged=True)

            if not instance_owner:
                return Authorization(False, 'Error: Cannot identify user which instance %s belongs to' % instance)
            elif not g.user:
                return Authorization(False, msg, error_code=401)  # Denotes that the user should log in first
            elif not g.user == instance_owner:
                return Authorization(False, '%s is a private operation which requires the owner to be logged in' % op)
            else:
                return Authorization(True, '%s have access to do private operation %s on instance %s' % (
                    unicode(instance_owner), op, instance), privileged=True)
        elif level == 'admin':
            if not g.user:
                return Authorization(False, msg, error_code=401)  # Denotes that the user should log in first
            elif not g.user.admin:
                return Authorization(False, 'Need to be logged in with admin access')
            elif g.user:
                return Authorization(True, '%s is an admin' % unicode(g.user), privileged=True)
        return Authorization(False, 'This is catch all denied authorization, should not be here')

    def auth_or_abort(self, response, instance=None):
        # if 'args' not in response or 'intent' not in response['args']:
        #     raise KeyError('Expects an intent arg, even if empty. Make sure to parse_args before auth')
        action = response['action']  # choose intent before action
        # print "Auth for %s, intent %s action %s" % (action, response['args']['intent'], response['action'])
        auth = self.authorize(action, instance)
        if not auth:
            raise ResourceError(auth.error_code, r={'TBD': 'TBD'}, message=auth.message)
        else:
            response['auth'] = auth
            return response


class ResourceRoutingStrategy:
    def __init__(self, model_class, plural_name, id_field='id', form_class=None,
                 parent_strategy=None, parent_reference_field=None, short_url=False,
                 list_filters=None, use_subdomain=False, access_policy=None, post_edit_action='view'):
        if use_subdomain and parent_strategy:
            raise ValueError("A subdomain-identified resource cannot have parents")
        self.form_class = form_class if form_class else model_form(model_class, base_class=RacBaseForm,
                                                                   converter=RacModelConverter())
        self.model_class = model_class
        self.resource_name = model_class.__name__.lower().split('.')[-1]  # class name, ignoring package name
        self.plural_name = plural_name
        self.parent = parent_strategy
        self.id_field = id_field
        self.use_subdomain = use_subdomain
        self.subdomain_part = None
        if self.use_subdomain:
            self.subdomain_part = '<' + self.resource_name + '>'
        elif self.parent:
            p = self
            while p.parent and not p.use_subdomain:
                p = p.parent
            if p:
                self.subdomain_part = p.subdomain_part
        self.short_url = short_url
        self.post_edit_action = post_edit_action
        self.fieldnames = [n for n in self.form_class.__dict__.keys() if
                           (not n.startswith('_') and n is not 'model_class')]
        self.default_list_filters = list_filters
        # The field name pointing to a parent resource for this resource, e.g. article.world
        self.parent_reference_field = self.parent.resource_name if \
            (self.parent and not parent_reference_field) else None
        self.access = access_policy if access_policy else ResourceAccessPolicy()
        self.access.model_class = self.model_class

    def get_url_path(self, part, op=None):
        parent_url = ('/' if (self.parent is None) else self.parent.url_item(None))
        op_val = op if op else ''
        # print "For %s we add %s %s %s" % (self.resource_name, parent_url, part, op_val)
        url = parent_url + part + ('/' if part else '') + op_val
        return url

    def url_list(self, op=None):
        return self.get_url_path(self.plural_name, op)

    def url_item(self, op=None):
        if self.use_subdomain:
            return self.get_url_path('', op)
        elif self.short_url:
            return self.get_url_path('<' + self.resource_name + '>', op)
        else:
            return self.get_url_path(self.plural_name + '/<' + self.resource_name + '>', op)

    def item_template(self):
        return '%s_item.html' % self.resource_name

    def list_template(self):
        return '%s_list.html' % self.resource_name

    def query_item(self, **kwargs):
        item_id = kwargs[self.resource_name]
        if objid_matcher.match(item_id):
            return self.model_class.objects.get(id=item_id)
        else:
            return self.model_class.objects.get(**{self.id_field: item_id})

    def create_item(self):
        return self.model_class()

    def query_list(self, args):
        qr = self.model_class.objects()
        filters = {}
        for key in args.keys():
            if key == 'order_by':
                qr = qr.order_by(*args.getlist('order_by'))
            elif key == 'q':
                qr = qr  # TODO search
            else:
                fieldname = key.split('__')[0]
                # print fieldname, (fieldname in self.model_class.__dict__)
                # TODO replace second and-part with dict per model-class that describes what is filterable
                if fieldname[0] != '_' and fieldname in self.model_class.__dict__:
                    filters[key] = args.get(key)
        # print filters
        if self.default_list_filters:
            qr = self.default_list_filters(qr)
        if filters:
            qr = qr.filter(**filters)
        # TODO very little safety in above as all filters are allowed
        return qr

    def query_parents(self, **kwargs):
        if not self.parent:
            return {}
        # Silently pop arg, if existing, relating to current resource
        kwargs.pop(self.resource_name, None)
        grandparents = self.parent.query_parents(**kwargs)
        grandparents[self.parent.resource_name] = self.parent.query_item(**kwargs)
        # print "all parents %s" % grandparents
        return grandparents

    def all_view_args(self, item):
        view_args = {self.resource_name: getattr(item, self.id_field)}
        if self.parent:
            view_args.update(self.parent.all_view_args(getattr(item, self.parent_reference_field)))
        return view_args

    def endpoint_name(self, suffix):
        return self.resource_name + '_' + suffix

    def endpoint_post_edit(self):
        return self.endpoint_name(self.post_edit_action)

    def authorize(self, op, instance=None):
        return self.access.authorize(op, instance)


class ResourceError(Exception):
    default_messages = {
        400: u"%s" % _("Bad request or invalid input"),
        401: u"%s" % _("Unathorized access, please login"),
        403: u"%s" % _("Forbidden, this is not an allowed operation"),
        404: u"%s" % _("Resource not found"),
        500: u"%s" % _("Internal server error")
    }

    def __init__(self, status_code, message=None, r=None, field_errors=None, template=None, template_vars=None):
        message = message if message else self.default_messages.get(status_code, _('Unknown error'))
        self.r = r
        if r:
            form = r.get('form', None)
            self.field_errors = form.errors if form else None
            self.template = r.get('template', None)
            self.template_vars = r
        if status_code == 400 and field_errors:
            message += u", invalid fields: \n%s" % pprint.pformat(field_errors)
        self.message = message
        self.status_code = status_code

        if field_errors:
            self.field_errors = field_errors
        if template:
            self.template = template
        if template_vars:
            self.template_vars = template_vars

        logger.warning(u"%d: %s%s", self.status_code, self.message,
                       u"\n%s\nin resource: \n%s\nwith formdata:\n%s" %
                       (request.url, pprint.pformat(self.r).decode('utf-8'), pprint.pformat(dict(request.form))))
        Exception.__init__(self, "%i: %s" % (status_code, message))


class ResourceHandler(View):
    allowed_ops = ['view', 'form_new', 'form_edit', 'list', 'new', 'replace', 'edit', 'delete']
    ignored_methods = ['as_view', 'dispatch_request', 'register_urls', 'return_json', 'methods']
    get_post_pairs = {'edit': 'form_edit', 'new': 'form_new', 'replace': 'form_edit', 'delete': 'edit'}

    def __init__(self, strategy):
        self.logger = current_app.logger
        self.form_class = strategy.form_class
        self.strategy = strategy

    @classmethod
    def methods(cls, resource_methods):
        def real_decorator(func):
            func.resource_methods = resource_methods
            return func

        return real_decorator

    @classmethod
    def register_urls(cls, app, st, sub=False):
        # We try to parse out any custom methods added to this handler class, which we will use as separate endpoints
        custom_ops = []
        if cls != ResourceHandler:  # If it is vanilla ResourceHandler, we know there won't be any new methods
            for name, m in inspect.getmembers(cls, predicate=inspect.ismethod):
                #   print "%s: Looking at method %s, not_private %s not_ignored %s not_in_allowed %s" % (app.name, name,
                #     (not name.startswith("_")), (not name in cls.ignored_methods), (not name in cls.allowed_ops))

                if (not name.startswith("_")) and (name not in cls.ignored_methods) and (name not in cls.allowed_ops):
                    app.add_url_rule(st.get_url_path(name),
                                     subdomain=st.parent.subdomain_part if st.parent else None,
                                     methods=m.resource_methods if hasattr(m, 'resource_methods') else ['GET'],
                                     view_func=cls.as_view(st.endpoint_name(name), st))
                    custom_ops.append(name)
            cls.allowed_ops.extend(custom_ops)
        # Uncomment to see all resources created
        # logger.debug("Creating resource %s with url pattern %s and custom ops %s, ignoring %s", cls, st.url_item(),
        # [st.get_url_path(o) for o in custom_ops], cls.ignored_methods)

        app.add_url_rule(st.url_item(), subdomain=st.subdomain_part, methods=['GET'],
                         view_func=cls.as_view(st.endpoint_name('view'), st))
        app.add_url_rule(st.url_list('new'), subdomain=st.parent.subdomain_part if st.parent else None, methods=['GET'],
                         view_func=cls.as_view(st.endpoint_name('form_new'), st))
        app.add_url_rule(st.url_item('edit'), subdomain=st.subdomain_part, methods=['GET'],
                         view_func=cls.as_view(st.endpoint_name('form_edit'), st))
        app.add_url_rule(st.url_list(), subdomain=st.parent.subdomain_part if st.parent else None, methods=['GET'],
                         view_func=cls.as_view(st.endpoint_name('list'), st))
        app.add_url_rule(st.url_list(), subdomain=st.parent.subdomain_part if st.parent else None, methods=['POST'],
                         view_func=cls.as_view(st.endpoint_name('new'), st))
        app.add_url_rule(st.url_item(), subdomain=st.subdomain_part, methods=['PUT'],
                         view_func=cls.as_view(st.endpoint_name('replace'), st))
        app.add_url_rule(st.url_item(), subdomain=st.subdomain_part, methods=['PATCH'],
                         view_func=cls.as_view(st.endpoint_name('edit'), st))
        app.add_url_rule(st.url_item(), subdomain=st.subdomain_part, methods=['DELETE'],
                         view_func=cls.as_view(st.endpoint_name('delete'), st))

        if current_app:
            current_app.access_policy[st.resource_name] = st.access

            # print "in register url %s" % app.app
            # /<resource>/[_,view,edit] -> GET:fablr.co/helmgast/, GET:fablr.co/helmgast/view, GET|POST:fablr.co/helmgast/edit
            # /resource/[list,new] -> GET:/world/list, GET:/world/new
            # <resource>.host/[_,view,edit] -> -> GET:helmgast.fablr.co, GET:helmgast.fablr.co/view, GET|POST:helmgast.fablr.co/edit

            # [GET]<world>.<host>/[_,edit]          -> world_view, world_form_edit
            # [GET]<host>/world/[worlds,new]      -> world_list, world_form_new
            # [GET]<world>.<host>/<article>   -> article_view
            # [GET]<world>.<host>/articles

    def dispatch_request(self, *args, **kwargs):
        # If op is given by argument, we use that, otherwise we take it from endpoint
        # The reason is that endpoints are not unique, e.g. for a given URL there may be many endpoints
        # TODO unsafe to let us call a custom methods based on request args!
        r = self._parse_url(**kwargs)
        print "Dispatch: got request.url = %s and endpoint %s and method %s, now r=%s" % (
            request.url, request.endpoint, request.method, r)
        try:
            if r['op'] not in self.__class__.allowed_ops:
                raise ResourceError(400, r=r, message="Attempted op %s is not allowed for this handler" % r['op'])
            r = self._query_url_components(r, **kwargs)
            r = getattr(self, r['op'])(r)  # picks the right method from the class and calls it!
        except ResourceError as err:
            if 'debug' in request.args and current_app.debug:
                raise  # send onward if we are debugging
            if err.status_code == 400:  # bad request
                if r['op'] in self.get_post_pairs:
                    # we were posting a form
                    r['op'] = self.get_post_pairs[r['op']]  # change the effective op
                    r['template'] = self.strategy.item_template()
                    r[self.strategy.resource_name + '_form'] = r['form']

                # if json, return json instead of render
                if r['out'] == 'json':
                    return self.return_json(r, err)
                elif 'template' in r:
                    flash(err.message, 'warning')
                    return render_template(r['template'], **r), 400
                else:
                    return err.message, 400

            elif err.status_code == 401:  # unauthorized
                if r['out'] == 'json':
                    return self.return_json(r, err)
                else:
                    flash(err.message, 'warning')
                    # if fragment/json, just return 401
                    return redirect(url_for('auth.login', next=request.path))

            elif err.status_code == 403:  # forbidden
                # change the effective op
                # r['op'] = self.get_post_pairs[r['op']] if r['op'] in self.get_post_pairs else r['op']
                # r['template'] = self.strategy.item_template()
                if r['out'] == 'json':
                    return self.return_json(r, err)
                # elif 'template' in r:
                #   flash(err.message,'warning')
                #   return render_template(r['template'], **r), 403
                else:
                    return err.message, 403

            elif err.status_code == 404:
                abort(404)  # TODO, nicer 404 page?

            elif r['out'] == 'json':
                return self.return_json(r, err)
            else:
                raise  # Send the error onward, will be picked up by debugger if in debug mode
        except DoesNotExist:
            abort(404)
        except ValidationError as valErr:
            #   logger.exception("Validation error")
            res_err = ResourceError(400, message=valErr.message, r=r, field_errors=valErr.errors)
            if r['out'] == 'json':
                return self.return_json(r, res_err)
            else:
                # Send the error onward, will be picked up by debugger if in debug mode
                # 3rd args is the current traceback, as we have created a new exception
                raise res_err, None, sys.exc_info()[2]
        except NotUniqueError as err:
            res_err = ResourceError(400, r=r, message=err.message)
            if r['out'] == 'json':
                return self.return_json(r, res_err)
            else:
                # Send the error onward, will be picked up by debugger if in debug mode
                # 3rd args is the current traceback, as we have created a new exception
                raise res_err, None, sys.exc_info()[2]
        except Exception as err:
            if not isinstance(err, HTTPException):
                # Ignore HTTP errors, as they happen for any normal abort(404) etc call
                logger.exception(u"%s: resource: %s" % (err, pprint.pformat(r).decode('utf-8')))
                if r['out'] == 'json':
                    return self.return_json(r, err, 500)
                else:
                    raise
            else:
                raise  # Let it be handled as usual

        # no error, render output
        if r['out'] == 'json':
            return self.return_json(r)
        elif 'next' in r:
            return redirect(r['next'])
        elif 'response' in r:
            return r['response']  # op function may have rendered the answer itself
        else:
            # if json, return json instead of render
            return render_template(r['template'], **r)

    def return_json(self, r, err=None, status_code=0):
        if err:
            logger.exception(err)
            return jsonify({'error': err.__class__.__name__, 'message': err.message,
                            'status_code': status_code}), status_code or err.status_code
        else:
            d = {k: v for k, v in r.iteritems() if k in ['item', 'list', 'op', 'parents', 'next', 'pagination']}
            return jsonify(d)

    def _parse_url(self, **kwargs):
        r = {'url_args': kwargs}
        op = request.args.get('op', request.endpoint.split('.')[-1].split('_', 1)[-1]).lower()
        if op in ['form_edit', 'form_new', 'list']:
            # TODO faster, more pythonic way of getting intersection of fieldnames and args
            vals = {}
            for arg in request.args:
                if arg in self.strategy.fieldnames:
                    val = request.args.get(arg).strip()
                    if val:
                        vals[arg] = val
            r['filter' if op is 'list' else 'prefill'] = vals
        r['op'] = op
        r['out'] = parse_out_arg(request.args.get('out', None))  # defaults to None, meaning _page.html
        r['model'] = self.strategy.model_class
        r['parent_template'] = r['out']  # TODO, we only need one of out and parent_template
        if 'next' in request.args:
            r['next'] = request.args['next']
        return r

    def _query_url_components(self, r, **kwargs):
        if self.strategy.resource_name in kwargs:
            r['item'] = self.strategy.query_item(**kwargs)
            r[self.strategy.resource_name] = r['item']
        r['parents'] = self.strategy.query_parents(**kwargs)
        r.update(r['parents'])
        # print "url comps %s, r %s" % (kwargs, r)
        return r

    def view(self, r):
        item = r['item']
        auth = self.strategy.authorize(r['op'], item)
        r['auth'] = auth
        if not auth:
            raise ResourceError(auth.error_code, r=r, message=auth.message)

        r['template'] = self.strategy.item_template()
        return r

    def form_edit(self, r):
        item = r['item']

        auth = self.strategy.authorize(r['op'], item)
        r['auth'] = auth
        if not auth:
            raise ResourceError(auth.error_code, r=r, message=auth.message)

        form = self.form_class(obj=item, **r.get('prefill', {}))
        form.action_url = url_for('.' + self.strategy.endpoint_name('edit'), METHOD='PATCH', **r['url_args'])
        r[self.strategy.resource_name + '_form'] = form
        r['op'] = 'edit'  # form_edit is not used in templates...
        r['template'] = self.strategy.item_template()
        return r

    def form_new(self, r):
        auth = self.strategy.authorize(r['op'])
        r['auth'] = auth
        if not auth:
            raise ResourceError(auth.error_code, r=r, message=auth.message)
        if 'parents' in r:
            r.setdefault('prefill', {}).update(
                {k: v for k, v in r['parents'].iteritems()})
        form = self.form_class(request.args, obj=None, **r.get('prefill', {}))
        form.action_url = url_for('.' + self.strategy.endpoint_name('new'),
                                  **r['url_args'])  # Method will be POST by default
        r[self.strategy.resource_name + '_form'] = form
        r['op'] = 'new'  # form_new is not used in templates...
        r['template'] = self.strategy.item_template()
        return r

    def list(self, r):
        auth = self.strategy.authorize(r['op'])
        r['auth'] = auth
        if not auth:
            raise ResourceError(auth.error_code, r=r, message=auth.message)

        listquery = self.strategy.query_list(request.args).filter(**r.get('filter', {}))
        if r.get('parents'):
            # TODO if the name of the parent resource is different than the reference field name
            # it will not work
            listquery = listquery.filter(**r['parents'])
        page = request.args.get('page', 1)
        per_page = request.args.get('per_page', 20)
        if per_page == 'all':
            r['list'] = listquery
            r[self.strategy.plural_name] = listquery
        else:
            r['pagination'] = listquery.paginate(page=int(page), per_page=int(per_page))
            r['list'] = r['pagination'].items
            r[self.strategy.plural_name] = r['list']
        r['url_for_args'] = request.view_args
        r['url_for_args'].update(request.args.to_dict())
        r['template'] = self.strategy.list_template()
        return r

    def new(self, r):
        auth = self.strategy.authorize(r['op'])
        r['auth'] = auth
        if not auth:
            raise ResourceError(auth.error_code, r=r, message=auth.message)

        r['template'] = self.strategy.item_template()
        form = self.form_class(request.form, obj=None)
        if not form.validate():
            r['form'] = form
            raise ResourceError(400, r=r)
        item = self.strategy.create_item()
        form.populate_obj(item)
        item.save()
        r['item'] = item
        if 'next' not in r:
            r['next'] = url_for('.' + self.strategy.endpoint_post_edit(), **self.strategy.all_view_args(item))
        return r

    def edit(self, r):
        item = r['item']
        auth = self.strategy.authorize(r['op'], item)
        r['auth'] = auth
        if not auth:
            raise ResourceError(auth.error_code, r=r, message=auth.message)

        r['template'] = self.strategy.item_template()
        form = self.form_class(request.form, obj=item)
        logger.warning('Form %s validates to %s' % (request.form, form.validate()))
        if not form.validate():
            r['form'] = form
            raise ResourceError(400, r=r)
        if not isinstance(form, RacBaseForm):
            raise ValueError("Edit op requires a form that supports populate_obj(obj, fields_to_populate)")
        form.populate_obj(item, request.form.keys())
        print r
        item.save()
        # In case slug has changed, query the new value before redirecting!
        if 'next' not in r:
            r['next'] = url_for('.' + self.strategy.endpoint_post_edit(), **self.strategy.all_view_args(item))
        logger.info("Edit on %s/%s", self.strategy.resource_name, item[self.strategy.id_field])
        generate_flash(_("edited"), self.strategy.resource_name, item)
        return r

    def replace(self, r):
        item = r['item']
        auth = self.strategy.authorize(r['op'], item)
        r['auth'] = auth
        if not auth:
            raise ResourceError(auth.error_code, r=r, message=auth.message)

        form = self.form_class(request.form, obj=item)
        if not form.validate():
            r['form'] = form
            raise ResourceError(400, r=r)
        form.populate_obj(item)
        item.save()
        if 'next' not in r:
            # In case slug has changed, query the new value before redirecting!
            r['next'] = url_for('.' + self.strategy.endpoint_post_edit(), **self.strategy.all_view_args(item))
        return r

    def delete(self, r):
        item = r['item']
        auth = self.strategy.authorize(r['op'], item)
        r['auth'] = auth
        if not auth:
            raise ResourceError(auth.error_code, r=r, message=auth.message)

        if 'next' not in r:
            r['next'] = url_for('.' + self.strategy.endpoint_name('list'), **self.strategy.all_view_args(item))
        logger.info("Delete on %s with id %s", self.strategy.resource_name, item.id)
        item.delete()
        return r
