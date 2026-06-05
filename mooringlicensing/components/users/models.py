from __future__ import unicode_literals

from django.db import models

from mooringlicensing import settings
from django.core.files.storage import FileSystemStorage
from mooringlicensing.components.main.models import CommunicationsLogEntry, Document

private_storage = FileSystemStorage(  # We want to store files in secure place (outside of the media folder)
    location=settings.PRIVATE_MEDIA_STORAGE_LOCATION,
    base_url=settings.PRIVATE_MEDIA_BASE_URL,
)

class EmailUserLogEntry(CommunicationsLogEntry):
    email_user_id = models.IntegerField(null=True, blank=True)

    def __init__(self, *args, **kwargs):
        if 'customer' in kwargs and not isinstance(kwargs.get('customer', 0), int):
            kwargs['customer'] = kwargs['customer'].id
        #if 'staff' in kwargs and not isinstance(kwargs.get('staff', 0), int):
        #    kwargs['staff'] = kwargs['staff'].id
        if 'email_user_id' in kwargs and not isinstance(kwargs.get('email_user_id', 0), int):
            kwargs['email_user_id'] = kwargs['email_user_id'].id
        super(EmailUserLogEntry, self).__init__(*args, **kwargs)

    def save(self, **kwargs):
        # save the request id if the reference not provided
        if not self.reference:
            self.reference = self.email_user_id

        super(EmailUserLogEntry, self).save(**kwargs)

    class Meta:
        app_label = 'mooringlicensing'


def update_emailuser_comms_log_filename(instance, filename):
    return '{}/emailusers/{}/communications/{}/{}'.format(settings.MEDIA_APP_DIR, instance.log_entry.email_user_id, instance.id, filename)


class EmailUserLogDocument(Document):
    log_entry = models.ForeignKey('EmailUserLogEntry',related_name='documents', on_delete=models.CASCADE)
    _file = models.FileField(storage=private_storage,upload_to=update_emailuser_comms_log_filename, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'
