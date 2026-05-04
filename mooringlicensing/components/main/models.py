from __future__ import unicode_literals
import pytz
import os

from django.db import models
from django.core.exceptions import ValidationError
from datetime import datetime
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from mooringlicensing import settings
from django.apps import apps
from mooringlicensing.ledger_api_utils import retrieve_email_userro
from django.core.files.storage import FileSystemStorage
from django.core.cache import cache
from django.core.files.base import ContentFile
from dirtyfields import DirtyFieldsMixin
from django.utils import timezone
from django.utils.html import strip_tags

import uuid

private_storage = FileSystemStorage(  # We want to store files in secure place (outside of the media folder)
    location=settings.PRIVATE_MEDIA_STORAGE_LOCATION,
    base_url=settings.PRIVATE_MEDIA_BASE_URL,
)

class SanitiseMixin(models.Model):
    """
    Sanitise models fields
    """

    def save(self, **kwargs):
        from mooringlicensing.components.main.utils import sanitise_fields
        #sanitise
        exclude = kwargs.pop("exclude_sanitise", []) #fields that should not be subject to full tag removal
        error_on_change = kwargs.pop("error_on_sanitise", []) #fields that should not be modified through tag removal (and should throw and error if they are)
        self = sanitise_fields(self, exclude, error_on_change)
        super(SanitiseMixin, self).save(**kwargs)

    class Meta:
        abstract = True

class SanitiseFileMixin(SanitiseMixin, DirtyFieldsMixin):
    """
    Sanitise file extensions and names
    """
    def auto_generate_file_name(self, extension):
        return "{}_{}_{}.{}".format(self._meta.model_name,uuid.uuid4(),int(datetime.now().timestamp()*100000), extension)

    def save(self, **kwargs):
        from mooringlicensing.components.main.utils import check_file

        path_to_file = kwargs.pop("path_to_file",None)
        file_content = kwargs.pop("file_content",None)
        storage = kwargs.pop("storage",None)

        if not path_to_file:
            try:
                #we specify an empty string here so we can substitute our own (NOTE: may be worth changing how this works to just return the path)
                path_to_file = self._meta.get_field('_file').upload_to(self,'')
            except Exception as e:
                print(e)
                path_to_file = None

        if not storage:
            storage = self._meta.get_field('_file').storage

        if not file_content:
            file_content = self._file

        file_content_exists = True
        try:
            if path_to_file and file_content and storage:
                content_test = file_content.size
        except Exception as e:
            print(e)
            file_content_exists = False

        #if file content does not exist, it does not need to be sanitised
        if not file_content_exists:
            super(SanitiseMixin, self).save(**kwargs)
            return

        if path_to_file and file_content and storage:
            #check file extension
            check_file(file_content, self._meta.model_name)

            #check file size
            if file_content.size > settings.FILE_SIZE_LIMIT_BYTES:
                raise ValidationError(format("File size too large: Max {}MB",settings.FILE_SIZE_LIMIT_BYTES/1000000))

            #auto-gen file name
            _, extension = os.path.splitext(str(file_content))
            generated_file_name = self.auto_generate_file_name(extension.replace(".",""))
            read = file_content.read()
            if bool(read):
                self._file = storage.save('{}/{}'.format(path_to_file,generated_file_name), ContentFile(read))
        elif '_file' in self.get_dirty_fields() and self.get_dirty_fields()['_file']:
            raise ValidationError("Cannot change file")

        #proceed with general sanitisation and save
        super(SanitiseMixin, self).save(**kwargs)
    
    class Meta:
        abstract = True


class Notice(SanitiseMixin):

    NOTICE_TYPE_CHOICES = (
        (0, 'Red Warning'),
        (1, 'Orange Warning'),
        (2, 'Blue Warning') ,
        (3, 'Green Warning')   
        )
    
    #NOTE: formatting not ideal but we need to be able to search this field
    PAGE_CHOICES = (
        ('External Dashboard','External Dashboard'),
        ('Application Page','Application Page'),
        ('Compliance Page','Compliance Page'),
    )

    notice_type = models.IntegerField(choices=NOTICE_TYPE_CHOICES,default=0)
    message = models.TextField(null=True, blank=True, default='')
    order = models.IntegerField(default=1)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(default=timezone.now)
    page = models.TextField(null=True, blank=True, default='External Dashboard', choices=PAGE_CHOICES)

    def __str__(self):
           return '{}'.format(strip_tags(self.message).replace('&nbsp;', ' '))
    
    def save(self, *args, **kwargs):
        cache.delete('utils_cache.get_notices()')
        self.full_clean()
        super(Notice, self).save(*args, **kwargs)

class UserAction(SanitiseMixin):
    who = models.IntegerField(null=True, blank=True)
    when = models.DateTimeField(null=False, blank=False, auto_now_add=True)
    what = models.TextField(blank=False)

    def __str__(self):
        return "{what} ({who} at {when})".format(
            what=self.what,
            who=self.who,
            when=self.when
        )
    @property
    def who_obj(self):
        return retrieve_email_userro(self.who)

    class Meta:
        abstract = True
        app_label = 'mooringlicensing'


class CommunicationsLogEntry(SanitiseMixin):
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

    customer = models.IntegerField(null=True)
    staff = models.IntegerField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True, null=False, blank=False)

    class Meta:
        app_label = 'mooringlicensing'


class FileExtensionWhitelist(models.Model):

    name = models.CharField(
        max_length=16,
        help_text="The file extension without the dot, e.g. jpg, pdf, docx, etc",
    )
    model = models.CharField(max_length=255, default="all")

    class Meta:
        app_label = "mooringlicensing"
        unique_together = ("name", "model")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._meta.get_field("model").choices = (
            (
                "all",
                "all",
            ),
        ) + tuple(
            map(
                lambda m: (m, m),
                filter(
                    lambda m: Document
                    in apps.get_app_config("mooringlicensing").models[m].__bases__,
                    apps.get_app_config("mooringlicensing").models,
                ),
            )
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(settings.CACHE_KEY_FILE_EXTENSION_WHITELIST)


class Document(SanitiseFileMixin):
    name = models.CharField(max_length=255, blank=True, verbose_name='name', help_text='')
    description = models.TextField(blank=True, verbose_name='description', help_text='')
    uploaded_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'mooringlicensing'
        abstract = True

    @property
    def path(self):
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
    KEY_EXTERNAL_DASHBOARD_SECTIONS_LIST = 'external_dashboard_sections_list'
    KEY_NUMBER_OF_MOORINGS_TO_RETURN_FOR_LOOKUP = 'number_of_moorings_to_return_for_lookup'
    KEY_FEE_AMOUNT_OF_SWAP_MOORINGS = 'fee_amount_of_swap_moorings'
    KEY_SWAP_MOORINGS_INCLUDES_GST = 'swap_moorings_includes_gst'
    KEY_STAT_DEC_FORM = 'stat_dec_form'

    keys_for_file = (
        KEY_DCV_PERMIT_TEMPLATE_FILE,
        KEY_DCV_ADMISSION_TEMPLATE_FILE,
        KEY_WLA_TEMPLATE_FILE,
        KEY_AAP_TEMPLATE_FILE,
        KEY_AUP_TEMPLATE_FILE,
        KEY_ML_TEMPLATE_FILE,
        KEY_ML_AU_LIST_TEMPLATE_FILE,
        KEY_STAT_DEC_FORM
    )
    keys = (
        (KEY_DCV_PERMIT_TEMPLATE_FILE, 'DcvPermit template file'),
        (KEY_DCV_ADMISSION_TEMPLATE_FILE, 'DcvAdmission template file'),
        (KEY_WLA_TEMPLATE_FILE, 'Waiting List Allocation template file'),
        (KEY_AAP_TEMPLATE_FILE, 'Annual Admission Permit template file'),
        (KEY_AUP_TEMPLATE_FILE, 'Authorised User Permit template file'),
        (KEY_ML_TEMPLATE_FILE, 'Mooring Site Licence template file'),
        (KEY_ML_AU_LIST_TEMPLATE_FILE, 'Mooring Site Licence Authorised User Summary template file'),
        (KEY_MINIMUM_VESSEL_LENGTH, 'Minimum vessel length'),
        (KEY_MINUMUM_MOORING_VESSEL_LENGTH, 'Minimum mooring vessel length'),
        (KEY_EXTERNAL_DASHBOARD_SECTIONS_LIST, 'External dashboard sections list'),
        (KEY_NUMBER_OF_MOORINGS_TO_RETURN_FOR_LOOKUP, 'Number of moorings to return for lookup'),
        (KEY_FEE_AMOUNT_OF_SWAP_MOORINGS, 'Fee amount of swap moorings'),
        (KEY_SWAP_MOORINGS_INCLUDES_GST, 'Fee for swap moorings includes gst'),
        (KEY_STAT_DEC_FORM, 'Statutory declaration form')
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
        KEY_MINIMUM_VESSEL_LENGTH: 3.76,
        KEY_MINUMUM_MOORING_VESSEL_LENGTH: 6.40,
        KEY_EXTERNAL_DASHBOARD_SECTIONS_LIST: 'LicencesAndPermitsTable, ApplicationsTable, CompliancesTable, WaitingListTable, AuthorisedUserApplicationsTable',
        KEY_NUMBER_OF_MOORINGS_TO_RETURN_FOR_LOOKUP: 10,
        KEY_FEE_AMOUNT_OF_SWAP_MOORINGS: 317.00,
        KEY_SWAP_MOORINGS_INCLUDES_GST: True,
        KEY_STAT_DEC_FORM: os.path.join(settings.BASE_DIR, template_folder, 'Statutory Declaration Form.docx'),
    }

    key = models.CharField(max_length=255, choices=keys, blank=False, null=False,)
    value = models.CharField(max_length=255)
    _file = models.FileField(upload_to='approval_permit_template', null=True, blank=True, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name_plural = "Global Settings"


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


def update_electoral_roll_doc_filename(instance, filename):
    return '{}/emailusers/{}/documents/{}'.format(settings.MEDIA_APP_DIR, instance.emailuser.id,filename)


class RevisionedMixin(SanitiseMixin):
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
        return Version.objects.get_for_object(self).last().revision.date_created

    @property
    def modified_date(self):
        from reversion.models import Version
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
        if self.pk and not self.is_editable:
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

    def get_max_allowed_length(self):
        one_larger_category = self.get_one_larger_category()
        if one_larger_category:
            max_allowed_length = one_larger_category.start_size
            if one_larger_category.include_start_size:
                include_max_allowed_length = False
            else:
                include_max_allowed_length = True
        else:
            max_allowed_length = 999999
            include_max_allowed_length = True

        return max_allowed_length, include_max_allowed_length

    def get_one_larger_category(self):
        larger_category = self.vessel_size_category_group.get_one_larger_category(self)
        return larger_category

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
        if self.pk and not self.is_editable:
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
    for fee_constructor in instance.vessel_size_category_group.fee_constructors.all():
        if fee_constructor.is_editable:
            fee_constructor.reconstruct_fees()


@receiver(post_delete, sender=VesselSizeCategory)
def _post_delete_vsc(sender, instance, **kwargs):
    for fee_constructor in instance.vessel_size_category_group.fee_constructors.all():
        if fee_constructor.is_editable:
            fee_constructor.reconstruct_fees()


class NumberOfDaysType(SanitiseMixin):
    code = models.CharField(max_length=100, blank=True, null=True, unique=True)
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

class JobQueue(models.Model):
    STATUS = (
       (0, 'Pending'),
       (1, 'Running'),
       (2, 'Completed'),
       (3, 'Failed'),
    )

    job_cmd = models.CharField(max_length=1000, null=True, blank=True)
    system_id = models.CharField(max_length=4, null=True, blank=True)
    status = models.SmallIntegerField(choices=STATUS, default=0) 
    parameters_json = models.JSONField(null=True, blank=True)
    processed_dt = models.DateTimeField(default=None,null=True, blank=True )
    user = models.IntegerField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.job_cmd   

import reversion
reversion.register(CommunicationsLogEntry, follow=[])
reversion.register(GlobalSettings, follow=[])
reversion.register(SystemMaintenance, follow=[])
reversion.register(VesselSizeCategoryGroup, follow=['vessel_size_categories', 'fee_constructors'])
reversion.register(VesselSizeCategory, follow=['feeitem_set'])
reversion.register(NumberOfDaysSetting, follow=[])