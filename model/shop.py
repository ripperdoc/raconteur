from raconteur import db
from model.misc import list_to_choices
from flask.ext.babel import lazy_gettext as _
from datetime import datetime
from user import User
from slugify import slugify
from misc import Choices
from world import ImageAsset

ProductTypes = Choices(
  book=_('Book'),
  item=_('Item'),
  digital=_('Digital'),
  shipping=_('Shipping fee'))

ProductStatus = Choices(
  pre_order = _('Pre-order'),
  available = _('Available'),
  out_of_stock = _('Out of stock'),
  hidden = _('Hidden'))

class Product(db.Document):
  slug = db.StringField(unique=True, max_length=62) # URL-friendly name
  title = db.StringField(max_length=60, required=True, verbose_name=_('Title'))
  description = db.StringField(max_length=500, verbose_name=_('Description'))
  publisher = db.StringField(max_length=60, required=True, verbose_name=_('Publisher'))
  family = db.StringField(max_length=60, verbose_name=_('Family'))
  created = db.DateTimeField(default=datetime.utcnow, verbose_name=_('Created'))
  type = db.StringField(choices=ProductTypes.to_tuples(), required=True, verbose_name=_('Type'))
  price = db.FloatField(min_value=0, required=True, verbose_name=_('Price'))
  status = db.StringField(choices=ProductStatus.to_tuples(), default=ProductStatus.hidden, verbose_name=_('Status'))
  feature_image = db.ReferenceField(ImageAsset)

  # Executes before saving
  def clean(self):
    self.slug = slugify(self.title)

  def __unicode__(self):
    return u'%s %s %s' % (self.title, _('by'), self.publisher)


class OrderLine(db.EmbeddedDocument):
  quantity = db.IntField(min_value=1, default=1, verbose_name=_('Quantity'))
  product = db.ReferenceField(Product, required=True, verbose_name=_('Product'))
  price = db.FloatField(min_value=0, required=True, verbose_name=_('Price'))
  comment = db.StringField(max_length=256, verbose_name=_('Comment'))
  
class Address(db.EmbeddedDocument):
  street = db.StringField(max_length=60, required=True, verbose_name=_('Street'))
  zipcode = db.StringField(max_length=8, required=True, verbose_name=_('Zipcode'))
  city = db.StringField(max_length=60, required=True, verbose_name=_('City'))
  country = db.StringField(max_length=60, required=True, verbose_name=_('Country'))

OrderStatus = Choices(
  cart = _('Cart'),
  ordered = _('Ordered'),
  paid = _('Paid'),
  shipped = _('Shipped'),
  error = _('Error'))

class Order(db.Document):
  user = db.ReferenceField(User, verbose_name=_('User'))
  session = db.StringField(verbose_name=_('Session ID'))
  email = db.EmailField(max_length=60, required=True, verbose_name=_('Email'))
  order_lines = db.ListField(db.EmbeddedDocumentField(OrderLine))
  total_items = db.IntField(min_value=0, default=0) # Total number of items
  total_price = db.FloatField(min_value=0, default=0.0) # Total price of order
  created = db.DateTimeField(default=datetime.utcnow, verbose_name=_('Created'))
  updated = db.DateTimeField(default=datetime.utcnow, verbose_name=_('Updated'))
  status = db.StringField(choices=OrderStatus.to_tuples(), default=OrderStatus.cart, verbose_name=_('Status'))
  shipping_address = db.EmbeddedDocumentField(Address)
  
  def __unicode__(self):
    max_prod, max_price = None, 0
    for ol in self.order_lines:
      if ol.price > max_price:
        max_prod, max_price = ol.product, ol.price
    if max_prod:
      s = u'%s %s%s' % (
        _('Order for'), 
        max_prod.title, 
        ' '+_('and more') if len(self.order_lines)>1 else '')
    else:
      s = _('Empty order')
    return s

  # Executes before saving
  def clean(self):
    num, sum =0, 0.0
    for ol in self.order_lines:
      num += ol.quantity
      sum += ol.quantity * ol.price
    self.total_items = num
    self.total_price = sum
