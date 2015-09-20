"""
    model.asset
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2014 by Helmgast AB
"""
import mimetypes
import re
from mongoengine import ValidationError

from slugify import slugify

from fablr.app import db
from flask.ext.babel import gettext, lazy_gettext as _
from misc import Choices
from flask import request


FileAccessType = Choices(
    # Accessed by anyone
    public=_('Public use'),
    # Access given through some product
    product=_('Product required'),
    # Access given through some product, also user specific
    user=_('User unique and product required'))

allowed_mimetypes = [
    'application/pdf',
    'application/rtf',
    'application/zip',
    'application/x-compressed-zip',
    'image/jpeg',
    'image/png',
    'text/html',
    'text/plain']


class FileAsset(db.Document):
    slug = db.StringField(max_length=62)
    title = db.StringField(max_length=60, required=True, verbose_name=_('Title'))
    description = db.StringField(max_length=500, verbose_name=_('Description'))
    # Internal filename
    source_filename = db.StringField(max_length=60, verbose_name=_('Filename'))
    # Alternative filename when downloaded
    attachment_filename = db.StringField(max_length=60, verbose_name=_('Filename when downloading'))
    # Actual file
    file_data = db.FileField(verbose_name=_('File data'))
    # How the file might be accessed
    access_type = db.StringField(choices=FileAccessType.to_tuples(), required=True, verbose_name=_('Access type'))

    def clean(self):
        self.slug = slugify(self.title)
        request_file_data = request.files['file_data']
        if request_file_data is not None and request_file_data.content_length > 0:
            if request_file_data.mimetype not in allowed_mimetypes:
                raise ValidationError(
                    gettext('Files of type %(mimetype)s is not allowed.', mimetype=request_file_data.mimetype))
            # File is present, save to GridFS
            self.file_data.replace(request_file_data, content_type=request_file_data.mimetype)
            self.source_filename = request_file_data.filename
            if not self.attachment_filename:
                self.attachment_filename = self.source_filename

    def get_user_attachment_filename(self, user):
        filename = self.attachment_filename if self.attachment_filename is not None else self.source_filename
        if user is not None and self.access_type == FileAccessType.user:
            return filename % re.sub(r'@|\.', '_', user.email).lower()
        else:
            return filename

    def is_public(self):
        return self.access_type == FileAccessType.public

    def file_data_exists(self):
        return self.file_data.grid_id is not None

    def get_mimetype(self):
        return mimetypes.guess_type(self.source_filename)[0]

    def access_type_name(self):
        return FileAccessType[self.access_type]

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        return u'%s%s' % (self.title, ' [%s]' % self.access_type)
