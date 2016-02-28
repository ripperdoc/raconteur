"""
  controller.shop
  ~~~~~~~~~~~~~~~~

  This is the controller and Flask blueprint for a basic webshopg. It will
  setup the URL routes based on Resource and provide a checkout flow. It
  also hosts important return URLs for the payment processor.

  :copyright: (c) 2014 by Helmgast AB
"""
import logging
from itertools import izip

import stripe
from flask import render_template, Blueprint, current_app, g, request, url_for
from flask.ext.babel import lazy_gettext as _
from flask.ext.mongoengine.wtf import model_form
from wtforms.fields import FormField, FieldList, HiddenField
from wtforms.utils import unset_value

from fablr.controller.mailer import send_mail
from fablr.controller.resource import (ResourceHandler, ResourceRoutingStrategy, ResourceAccessPolicy,
                                       RacModelConverter, RacBaseForm, ResourceError, generate_flash)
from fablr.model.shop import Product, Order, OrderLine, OrderStatus, Address

logger = current_app.logger if current_app else logging.getLogger(__name__)

shop_app = Blueprint('shop', __name__, template_folder='../templates/shop')

stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

product_access = ResourceAccessPolicy({
    'view': 'user',
    '_default': 'admin'
})

product_strategy = ResourceRoutingStrategy(
    Product,
    'products',
    'slug',
    short_url=False,
    form_class=model_form(Product,
                          base_class=RacBaseForm,
                          exclude=['slug'],
                          converter=RacModelConverter()),
    access_policy=product_access)


class ProductHandler(ResourceHandler):
    def list(self, r):
        if not (g.user and g.user.admin):
            filter = r.get('filter', {})
            filter.update({'status__ne': 'hidden'})
            print filter
            r['filter'] = filter
        return super(ProductHandler, self).list(r)


ProductHandler.register_urls(shop_app, product_strategy)

order_access = ResourceAccessPolicy({
    'my_orders': 'user',
    'view': 'private',
    'list': 'admin',
    'edit': 'admin',
    'form_edit': 'admin',
    '_default': 'admin'
})

order_strategy = ResourceRoutingStrategy(Order, 'orders', form_class=model_form(
    Order, base_class=RacBaseForm, only=['order_lines', 'shipping_address',
                                         'shipping_mobile'], converter=RacModelConverter()), access_policy=order_access)


# This injects the "cart_items" into templates in shop_app
@shop_app.context_processor
def inject_cart():
    cart_order = Order.objects(user=g.user, status=OrderStatus.cart).only('total_items').first()
    return dict(cart_items=cart_order.total_items if cart_order else 0)


# Order states and form
# cart.
# Only one order per user can be in this state at the same time.
# Product quantities and comments can be changed, new orderlines can be added or removed.
# Address will not be editable
# ordered
# Order has been confirmed and sent for payment. Quantities can no longer be changed.
# paid
# Order has been confirmed paid. Address and comments can be changed, but with warning (as it may be too late for shipment)
# shipped
# Order has been shipped and is impossible to edit.
# error
# an error needing manual review. includes requests for refund, etc.

CartOrderLineForm = model_form(OrderLine, only=['quantity', 'comment'], base_class=RacBaseForm,
                               converter=RacModelConverter())
# Orderlines that only include comments, to allow for editing comments but not the order lines as such
LimitedOrderLineForm = model_form(OrderLine, only=['comment'], base_class=RacBaseForm, converter=RacModelConverter())
ShippingForm = model_form(Address, base_class=RacBaseForm, converter=RacModelConverter())


class FixedFieldList(FieldList):
    # TODO
    # Below is a very hacky approach to handle updating the order_list. When we send in a form
    # with a deleted row, it never appears in formdata. For example, we have a order_list of 2 items,
    # when the first is deleted only the second is submitted. Below code uses the indices of the
    # field ids, e.g. order_lines-0 and order_lines-1 to identify what was removed, and then
    # process and populate the right item from the OrderList field of the model.
    # This should be fixed by wtforms!

    def process(self, formdata, data=unset_value):
        print 'FieldList process formdata %s, data %s' % (formdata, data)
        self.entries = []
        if data is unset_value or not data:
            try:
                data = self.default()
            except TypeError:
                data = self.default

        self.object_data = data

        if formdata:
            indices = sorted(set(self._extract_indices(self.name, formdata)))
            if self.max_entries:
                indices = indices[:self.max_entries]

            for index in indices:
                try:
                    obj_data = data[index]
                    print "Got obj_data %s" % obj_data
                except LookupError:
                    obj_data = unset_value
                self._add_entry(formdata, obj_data, index=index)
        else:
            for obj_data in data:
                self._add_entry(formdata, obj_data)

        while len(self.entries) < self.min_entries:
            self._add_entry(formdata)

    def populate_obj(self, obj, name):
        old_values = getattr(obj, name, [])

        candidates = []
        indices = [e.id.rsplit('-', 1)[1] for e in self.entries]
        for i in indices:
            candidates.append(old_values[int(i)])

        _fake = type(str('_fake'), (object,), {})
        output = []
        for field, data in izip(self.entries, candidates):
            fake_obj = _fake()
            fake_obj.data = data
            field.populate_obj(fake_obj, 'data')
            output.append(fake_obj.data)

        setattr(obj, name, output)


class CartForm(RacBaseForm):
    order_lines = FixedFieldList(FormField(CartOrderLineForm))
    shipping_address = FormField(ShippingForm)
    stripe_token = HiddenField()


class PostCartForm(RacBaseForm):
    order_lines = FixedFieldList(FormField(LimitedOrderLineForm))
    shipping_address = FormField(ShippingForm)


class OrderHandler(ResourceHandler):
    # We have to tailor our own edit because the form needs to be conditionally
    # modified
    def edit(self, r):
        order = r['item']
        auth = self.strategy.authorize(r['op'], order)
        r['auth'] = auth
        if not auth:
            raise ResourceError(auth.error_code, r=r, message=auth.message)
        r['template'] = self.strategy.item_template()
        if order.status == 'cart':
            Formclass = CartForm
        else:
            Formclass = PostCartForm
        form = Formclass(request.form, obj=order)
        # logger.warning('Form %s validates to %s' % (request.form, form.validate()))
        if not form.validate():
            r['form'] = form
            raise ResourceError(400, r=r)
        if not isinstance(form, RacBaseForm):
            raise ValueError("Edit op requires a form that supports populate_obj(obj, fields_to_populate)")
        # We now have a validated form. Let's save the order first, then attempt to purchase it.
        # This is very important, as the save() will re-calculate key values for this order
        # print "Populating object %s with form keys %s, data %s" % (order, request.form.keys(), form.data)
        print "Got order_lines %s extracted as indices %s" % (
            request.form.keys(),
            list(form.order_lines._extract_indices(form.order_lines.name, request.form))
        )
        # raise Exception()
        form.populate_obj(order)
        order.save()

        # In case slug has changed, query the new value before redirecting!
        r['next'] = url_for('.order_form_edit', order=order.id)

        if form.stripe_token.data:  # We have token data, so this is a purchase
            try:
                charge = stripe.Charge.create(
                    source=form.stripe_token.data,
                    amount=int(order.total_price * 100),  # Stripe takes input in "cents" or similar
                    currency=order.currency,
                    description=unicode(order),
                    metadata={'order_id': order.id}
                )
                if charge['status'] == 'succeeded':
                    order.status = OrderStatus.paid
                    order.charge_id = charge['id']
                    order.save()
                    send_mail([g.user.email], _('Thank you for your order!'), 'order', user=g.user, order=order)
                    logger.info("User %s purchased %s", g.user, order)
                    generate_flash("Purchased", "order", order)
                    return r
            except stripe.error.CardError as e:
                raise ResourceError(500, message="Could not complete purchase: %s" % e.message, r=r)

        logger.info("Edit on %s/%s", self.strategy.resource_name, order.id)
        generate_flash("Edited", self.strategy.resource_name, order)
        return r

    def my_orders(self, r):
        filter = r.get('filter', {})
        filter.update({'user': g.user})
        r['filter'] = filter
        return super(OrderHandler, self).list(r)

    # Endpoint will be 'order_cart' as it's attached to OrderHandler
    @ResourceHandler.methods(['GET', 'POST'])
    def cart(self, r):
        r['template'] = 'shop/order_item.html'

        if g.user:
            cart_order = Order.objects(user=g.user, status=OrderStatus.cart).first()
            if not cart_order:
                cart_order = Order(user=g.user, email=g.user.email).save()
            r['item'] = cart_order
            r['order'] = cart_order
            r['url_args'] = {'order': cart_order.id}
            r['stripe_key'] = current_app.config['STRIPE_PUBLIC_KEY']
        else:
            raise ResourceError(401, _('Need to log in to use shopping cart'))
        if request.method == 'GET':
            self.form_class = CartForm
            r = self.form_edit(r)

        elif request.method == 'POST':
            if 'product' in request.form:
                slug = request.form.get('product')
                p = Product.objects(slug=slug).first()
                if p:
                    found = False
                    for ol in cart_order.order_lines:
                        if ol.product == p:
                            ol.quantity += 1
                            found = True
                    if not found:  # create new orderline with this product
                        newol = OrderLine(product=p, price=p.price)
                        cart_order.order_lines.append(newol)
                    cart_order.save()
                    r['item'] = cart_order.total_items
                else:
                    raise ResourceError(400, r, 'No product with slug %s exists' % slug)
            else:
                raise ResourceError(400, r, 'Not supported')

        return r


OrderHandler.register_urls(shop_app, order_strategy)


@shop_app.route('/')
def index():
    product_families = Product.objects().distinct('family')
    return render_template('shop/_page.html', product_families=product_families)


# POST cart - add products, create order if needed
# GET cart - current order, displayed differently depending on current state

# my orders
@current_app.template_filter('currency')
def currency(value):
    return ("{:.0f}" if float(value).is_integer() else "{:.2f}").format(value)
