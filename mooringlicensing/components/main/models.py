from __future__ import unicode_literals
import pytz
import os

# from ledger.settings_base import TIME_ZONE
from django.db import models
# from django.utils.encoding import python_2_unicode_compatible
from django.core.exceptions import ValidationError
# from ledger.accounts.models import EmailUser, RevisionedMixin
from datetime import datetime
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete, pre_delete
from mooringlicensing import settings


class UserSystemSettings(models.Model):
    # user = models.OneToOneField(EmailUser, related_name='system_settings')
    user = models.IntegerField(unique=True)  # EmailUserRO

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name_plural = "User System Settings"


# @python_2_unicode_compatible
class UserAction(models.Model):
    # who = models.ForeignKey(EmailUser, null=False, blank=False)
    who = models.IntegerField()  # EmailUserRO
    when = models.DateTimeField(null=False, blank=False, auto_now_add=True)
    what = models.TextField(blank=False)

    def __str__(self):
        return "{what} ({who} at {when})".format(
            what=self.what,
            who=self.who,
            when=self.when
        )

    class Meta:
        abstract = True
        app_label = 'mooringlicensing'


class CommunicationsLogEntry(models.Model):
    TYPE_CHOICES = [
        ('email', 'Email'),
        ('phone', 'Phone Call'),
        ('mail', 'Mail'),
        ('person', 'In Person'),
        ('onhold', 'On Hold'),
        ('onhold_remove', 'Remove On Hold'),
        ('with_qaofficer', 'With QA Officer'),
        ('with_qaofficer_completed', 'QA Officer Completed'),
        ('referral_complete','Referral Completed'),
    ]
    DEFAULT_TYPE = TYPE_CHOICES[0][0]

    to = models.TextField(blank=True, verbose_name="To")
    fromm = models.CharField(max_length=200, blank=True, verbose_name="From")
    cc = models.TextField(blank=True, verbose_name="cc")

    type = models.CharField(max_length=35, choices=TYPE_CHOICES, default=DEFAULT_TYPE)
    reference = models.CharField(max_length=100, blank=True)
    subject = models.CharField(max_length=200, blank=True, verbose_name="Subject / Description")
    text = models.TextField(blank=True)

    # customer = models.ForeignKey(EmailUser, null=True, related_name='+')
    customer = models.IntegerField(null=True)  # EmailUserRO
    # staff = models.ForeignKey(EmailUser, null=True, related_name='+')
    staff = models.IntegerField()  # EmailUserRO

    created = models.DateTimeField(auto_now_add=True, null=False, blank=False)

    class Meta:
        app_label = 'mooringlicensing'


# @python_2_unicode_compatible
class Document(models.Model):
    name = models.CharField(max_length=255, blank=True,
                            verbose_name='name', help_text='')
    description = models.TextField(blank=True,
                                   verbose_name='description', help_text='')
    uploaded_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'mooringlicensing'
        abstract = True

    @property
    def path(self):
        #comment above line to fix the error "The '_file' attribute has no file associated with it." when adding comms log entry.
        if self._file:
            return self._file.path
        else:
            return ''

    @property
    def filename(self):
        return os.path.basename(self.path)

    def __str__(self):
        return self.name or self.filename


class ApplicationType(models.Model):
    code = models.CharField(max_length=30, blank=True, null=True, unique=True)
    description = models.CharField(max_length=200, blank=True, null=True)
    fee_by_fee_constructor = models.BooleanField(default=True)

    def __str__(self):
        return '{}'.format(self.description)

    def get_oracle_code_by_date(self, target_date=datetime.now(pytz.timezone(settings.TIME_ZONE)).date()):
        try:
            oracle_code_item = self.oracle_code_items.filter(date_of_enforcement__lte=target_date).order_by('-date_of_enforcement').first()
            return oracle_code_item.value
        except:
            raise ValueError('Oracle code not found for the application: {} at the date: {}'.format(self, target_date))

    def get_enforcement_date_by_date(self, target_date=datetime.now(pytz.timezone(settings.TIME_ZONE)).date()):
        try:
            oracle_code_item = self.oracle_code_items.filter(date_of_enforcement__lte=target_date).order_by('-date_of_enforcement').first()
            return oracle_code_item.date_of_enforcement
        except:
            raise ValueError('Oracle code not found for the application: {} at the date: {}'.format(self, target_date))

    @staticmethod
    def get_current_oracle_code_by_application(code):
        application_type = ApplicationType.objects.get(code=code)
        return application_type.get_oracle_code_by_date()

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = 'Oracle code'


class GlobalSettings(models.Model):
    KEY_DCV_PERMIT_TEMPLATE_FILE = 'dcv_permit_template_file'
    KEY_DCV_ADMISSION_TEMPLATE_FILE = 'dcv_admission_template_file'
    KEY_WLA_TEMPLATE_FILE = 'wla_template_file'
    KEY_AAP_TEMPLATE_FILE = 'aap_template_file'
    KEY_AUP_TEMPLATE_FILE = 'aup_template_file'
    KEY_ML_TEMPLATE_FILE = 'ml_template_file'
    KEY_ML_AU_LIST_TEMPLATE_FILE = 'ml_au_list_template_file'
    KEY_MINIMUM_VESSEL_LENGTH = 'minimum_vessel_length'
    KEY_MINUMUM_MOORING_VESSEL_LENGTH = 'minimum_mooring_vessel_length'
    KEY_MINUMUM_STICKER_NUMBER_FOR_DCV_PERMIT = 'min_sticker_number_for_dcv_permit'

    keys_for_file = (
        KEY_DCV_PERMIT_TEMPLATE_FILE,
        KEY_DCV_ADMISSION_TEMPLATE_FILE,
        KEY_WLA_TEMPLATE_FILE,
        KEY_AAP_TEMPLATE_FILE,
        KEY_AUP_TEMPLATE_FILE,
        KEY_ML_TEMPLATE_FILE,
        KEY_ML_AU_LIST_TEMPLATE_FILE,
    )
    keys = (
        (KEY_DCV_PERMIT_TEMPLATE_FILE, 'DcvPermit template file'),
        (KEY_DCV_ADMISSION_TEMPLATE_FILE, 'DcvAdmission template file'),
        (KEY_WLA_TEMPLATE_FILE, 'Waiting List Allocation template file'),
        (KEY_AAP_TEMPLATE_FILE, 'Annual Admission Permit template file'),
        (KEY_AUP_TEMPLATE_FILE, 'Authorised User Permit template file'),
        (KEY_ML_TEMPLATE_FILE, 'Mooring Licence template file'),
        (KEY_ML_AU_LIST_TEMPLATE_FILE, 'Mooring Licence Authorised User Summary template file'),
        (KEY_MINIMUM_VESSEL_LENGTH, 'Minimum vessel length'),
        (KEY_MINUMUM_MOORING_VESSEL_LENGTH, 'Minimum mooring vessel length'),
        (KEY_MINUMUM_STICKER_NUMBER_FOR_DCV_PERMIT, 'Minimun sticker number for DCV Permit')
    )
    template_folder = 'mooringlicensing/management/templates'
    default_values = {
        KEY_DCV_PERMIT_TEMPLATE_FILE: os.path.join(settings.BASE_DIR, template_folder, 'Attachment Template - DCVP.docx'),
        KEY_DCV_ADMISSION_TEMPLATE_FILE: os.path.join(settings.BASE_DIR, template_folder, 'Attachment Template - DCVA.docx'),
        KEY_WLA_TEMPLATE_FILE: os.path.join(settings.BASE_DIR, template_folder, 'Attachment Template - WLA.docx'),
        KEY_AAP_TEMPLATE_FILE: os.path.join(settings.BASE_DIR, template_folder, 'Attachment Template - AAP.docx'),
        KEY_AUP_TEMPLATE_FILE: os.path.join(settings.BASE_DIR, template_folder, 'Attachment Template - AUP.docx'),
        KEY_ML_TEMPLATE_FILE: os.path.join(settings.BASE_DIR, template_folder, 'Attachment Template - ML.docx'),
        KEY_ML_AU_LIST_TEMPLATE_FILE: os.path.join(settings.BASE_DIR, template_folder, 'Attachment Template - ML - AU Summary.docx'),
        KEY_MINIMUM_VESSEL_LENGTH: 3.75,
        KEY_MINUMUM_MOORING_VESSEL_LENGTH: 6.50,
        KEY_MINUMUM_STICKER_NUMBER_FOR_DCV_PERMIT: 200000,
    }

    key = models.CharField(max_length=255, choices=keys, blank=False, null=False,)
    value = models.CharField(max_length=255)
    _file = models.FileField(upload_to='approval_permit_template', null=True, blank=True)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name_plural = "Global Settings"


# @python_2_unicode_compatible
class SystemMaintenance(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    def duration(self):
        """ Duration of system maintenance (in mins) """
        return int( (self.end_date - self.start_date).total_seconds()/60.) if self.end_date and self.start_date else ''
    duration.short_description = 'Duration (mins)'

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name_plural = "System maintenance"

    def __str__(self):
        return 'System Maintenance: {} ({}) - starting {}, ending {}'.format(self.name, self.description, self.start_date, self.end_date)


class TemporaryDocumentCollection(models.Model):

    class Meta:
        app_label = 'mooringlicensing'


class TemporaryDocument(Document):
    temp_document_collection = models.ForeignKey(
        TemporaryDocumentCollection,
        related_name='documents',
        on_delete=models.CASCADE,
    )
    _file = models.FileField(max_length=255)

    class Meta:
        app_label = 'mooringlicensing'


def update_electoral_roll_doc_filename(instance, filename):
    return '{}/emailusers/{}/documents/{}'.format(settings.MEDIA_APP_DIR, instance.emailuser.id,filename)


class RevisionedMixin(models.Model):
    """
    A model tracked by reversion through the save method.
    """

    def save(self, **kwargs):
        from reversion import revisions

        if kwargs.pop("no_revision", False):
            super(RevisionedMixin, self).save(**kwargs)
        else:
            with revisions.create_revision():
                if "version_user" in kwargs:
                    revisions.set_user(kwargs.pop("version_user", None))
                if "version_comment" in kwargs:
                    revisions.set_comment(kwargs.pop("version_comment", ""))
                super(RevisionedMixin, self).save(**kwargs)

    @property
    def created_date(self):
        from reversion.models import Version

        # return revisions.get_for_object(self).last().revision.date_created
        return Version.objects.get_for_object(self).last().revision.date_created

    @property
    def modified_date(self):
        from reversion.models import Version

        # return revisions.get_for_object(self).first().revision.date_created
        return Version.objects.get_for_object(self).first().revision.date_created

    class Meta:
        abstract = True

class VesselSizeCategoryGroup(RevisionedMixin):
    name = models.CharField(max_length=100, null=False, blank=False)

    def get_one_smaller_category(self, vessel_size_category):
        smaller_categories = self.vessel_size_categories.filter(start_size__lt=vessel_size_category.start_size, null_vessel=False).order_by('-start_size')
        if smaller_categories:
            return smaller_categories.first()
        else:
            # Probably the vessel_size_category passed as a parameter is the smallest vessel size category in this group
            return None

    def get_one_larger_category(self, vessel_size_category):
        larger_categories = self.vessel_size_categories.filter(start_size__gt=vessel_size_category.start_size, null_vessel=False).order_by('start_size')
        if larger_categories:
            return larger_categories.first()
        else:
            # Probably the vessel_size_category passed as a parameter is the largest vessel size category in this group
            return None

    def __str__(self):
        num_item = self.vessel_size_categories.count()
        return '{} ({} category)'.format(self.name, num_item) if num_item == 1 else '{} ({} categories)'.format(self.name, num_item)

    class Meta:
        verbose_name_plural = "Vessel Size Category Group"
        app_label = 'mooringlicensing'

    def save(self, **kwargs):
        if not self.is_editable:
            raise ValidationError('VesselSizeCategoryGroup cannot be changed once used for payment calculation')
        else:
            super(VesselSizeCategoryGroup, self).save(**kwargs)


    @property
    def is_editable(self):
        for fee_constructor in self.fee_constructors.all():
            if not fee_constructor.is_editable:
                # This object has been used in the fee_constructor for payments at least once
                return False
        return True


class VesselSizeCategory(RevisionedMixin):
    name = models.CharField(max_length=100)
    start_size = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', help_text='unit [m]')
    include_start_size = models.BooleanField(default=True)  # When true, 'start_size' is included.
    vessel_size_category_group = models.ForeignKey(VesselSizeCategoryGroup, null=True, blank=True, related_name='vessel_size_categories', on_delete=models.SET_NULL)
    null_vessel = models.BooleanField(default=False)

    def get_one_smaller_category(self):
        smaller_category = self.vessel_size_category_group.get_one_smaller_category(self)
        return smaller_category

    def __str__(self):
        if self.null_vessel:
            return self.name
        else:
            if self.include_start_size:
                return '{} (>={}m)'.format(self.name, self.start_size)
            else:
                return '{} (>{}m)'.format(self.name, self.start_size)

    class Meta:
        verbose_name_plural = "Vessel Size Categories"
        app_label = 'mooringlicensing'

    def save(self, **kwargs):
        if not self.is_editable:
            raise ValidationError('VesselSizeCategory cannot be changed once used for payment calculation')
        else:
            super(VesselSizeCategory, self).save(**kwargs)

    @property
    def is_editable(self):
        if self.vessel_size_category_group:
            return self.vessel_size_category_group.is_editable
        return True


@receiver(post_save, sender=VesselSizeCategory)
def _post_save_vsc(sender, instance, **kwargs):
    print('VesselSizeCategory post save()')
    print(instance.vessel_size_category_group)

    for fee_constructor in instance.vessel_size_category_group.fee_constructors.all():
        if fee_constructor.is_editable:
            fee_constructor.reconstruct_fees()


@receiver(post_delete, sender=VesselSizeCategory)
def _post_delete_vsc(sender, instance, **kwargs):
    print('VesselSizeCategory post delete()')
    print(instance.vessel_size_category_group)

    for fee_constructor in instance.vessel_size_category_group.fee_constructors.all():
        if fee_constructor.is_editable:
            fee_constructor.reconstruct_fees()


class NumberOfDaysType(RevisionedMixin):
    code = models.CharField(max_length=100, blank=True, null=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, verbose_name='description', help_text='')

    def __str__(self):
        return self.name

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = 'Number of days Settings'
        verbose_name_plural = 'Number of days Settings'

    def get_setting_by_date(self, target_date=datetime.now(pytz.timezone(settings.TIME_ZONE)).date()):
        return NumberOfDaysSetting.get_setting_by_date(self, target_date)

    def get_number_of_days_currently_applied(self):
        setting = self.get_setting_by_date(target_date=datetime.now(pytz.timezone(settings.TIME_ZONE)).date())
        if setting:
            return setting.number_of_days
        else:
            return '---'

    get_number_of_days_currently_applied.short_description = 'Number currently applied'  # Displayed at the admin page
    number_by_date = property(get_number_of_days_currently_applied)


class NumberOfDaysSetting(RevisionedMixin):
    number_of_days = models.PositiveSmallIntegerField(blank=True, null=True)
    date_of_enforcement = models.DateField(blank=True, null=True)
    number_of_days_type = models.ForeignKey(NumberOfDaysType, blank=True, null=True, related_name='settings', on_delete=models.CASCADE)

    def __str__(self):
        return '{} ({})'.format(self.number_of_days, self.number_of_days_type.name)

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ['-date_of_enforcement',]

    @staticmethod
    def get_setting_by_date(number_of_days_type, target_date=datetime.now(pytz.timezone(settings.TIME_ZONE)).date()):
        """
        Return an setting object which is enabled at the target_date
        """
        setting = NumberOfDaysSetting.objects.filter(
            number_of_days_type=number_of_days_type,
            date_of_enforcement__lte=target_date,
        ).order_by('date_of_enforcement').last()
        return setting


import reversion
reversion.register(UserSystemSettings, follow=[])
reversion.register(CommunicationsLogEntry, follow=[])
reversion.register(ApplicationType, follow=['proposalstandardrequirement_set', 'feeseason_set', 'feeconstructor_set', 'oracle_code_items'])
reversion.register(GlobalSettings, follow=[])
reversion.register(SystemMaintenance, follow=[])
reversion.register(TemporaryDocumentCollection, follow=['documents'])
reversion.register(TemporaryDocument, follow=[])
reversion.register(VesselSizeCategoryGroup, follow=['vessel_size_categories', 'fee_constructors'])
reversion.register(VesselSizeCategory, follow=['feeitem_set'])
reversion.register(NumberOfDaysType, follow=['settings'])
reversion.register(NumberOfDaysSetting, follow=[])

