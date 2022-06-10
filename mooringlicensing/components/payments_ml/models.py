import datetime
import logging
from decimal import Decimal
from math import ceil

import pytz
from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Min
from ledger.accounts.models import RevisionedMixin, EmailUser
from ledger.payments.invoice.models import Invoice
from ledger.settings_base import TIME_ZONE

from mooringlicensing import settings
from mooringlicensing.components.main.models import ApplicationType, VesselSizeCategoryGroup, VesselSizeCategory
from mooringlicensing.components.proposals.models import ProposalType, AnnualAdmissionApplication, \
    AuthorisedUserApplication, VesselDetails, WaitingListApplication
from smart_selects.db_fields import ChainedForeignKey

logger = logging.getLogger('mooringlicensing')


class Payment(models.Model):
    send_invoice = models.BooleanField(default=False)
    confirmation_sent = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    expiry_time = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    class Meta:
        app_label = 'mooringlicensing'
        abstract = True

    @property
    def paid(self):
        payment_status = self.__check_payment_status()
        if payment_status == 'paid' or payment_status == 'over_paid':
            return True
        return False

    @property
    def unpaid(self):
        payment_status = self.__check_payment_status()
        if payment_status == 'unpaid':
            return True
        return False

    @property
    def amount_paid(self):
        return self.__check_payment_amount()

    def __check_payment_amount(self):
        amount = Decimal('0.0')
        if self.active_invoice:
            return self.active_invoice.payment_amount
        return amount

    def __check_invoice_payment_status(self):
        invoices = []
        payment_amount = Decimal('0.0')
        invoice_amount = Decimal('0.0')
        references = self.invoices.all().values('invoice_reference')
        for r in references:
            try:
                invoices.append(Invoice.objects.get(reference=r.get("invoice_reference")))
            except Invoice.DoesNotExist:
                pass
        for i in invoices:
            if not i.voided:
                payment_amount += i.payment_amount
                invoice_amount += i.amount

        if invoice_amount == payment_amount:
            return 'paid'
        if payment_amount > invoice_amount:
            return 'over_paid'
        return "unpaid"

    def __check_payment_status(self):
        amount = Decimal('0.0')
        invoice = Invoice.objects.filter(reference=self.invoice_reference)
        if invoice:
            invoice = invoice.first()
            return invoice.payment_status
        else:
            return '---'
            # raise Exception('No invoice found for the ApplicationFee: {}'.format(self))


class DcvAdmissionFee(Payment):
    PAYMENT_TYPE_INTERNET = 0
    PAYMENT_TYPE_RECEPTION = 1
    PAYMENT_TYPE_BLACK = 2
    PAYMENT_TYPE_TEMPORARY = 3
    PAYMENT_TYPE_CHOICES = (
        (PAYMENT_TYPE_INTERNET, 'Internet booking'),
        (PAYMENT_TYPE_RECEPTION, 'Reception booking'),
        (PAYMENT_TYPE_BLACK, 'Black booking'),
        (PAYMENT_TYPE_TEMPORARY, 'Temporary reservation'),
    )

    dcv_admission = models.ForeignKey('DcvAdmission', on_delete=models.PROTECT, blank=True, null=True, related_name='dcv_admission_fees')
    payment_type = models.SmallIntegerField(choices=PAYMENT_TYPE_CHOICES, default=0)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    created_by = models.ForeignKey(EmailUser, on_delete=models.PROTECT, blank=True, null=True, related_name='created_by_dcv_admission_fee')
    invoice_reference = models.CharField(max_length=50, null=True, blank=True, default='')
    fee_items = models.ManyToManyField('FeeItem', related_name='dcv_admission_fees')

    def __str__(self):
        return 'DcvAdmission {} : Invoice {}'.format(self.dcv_admission, self.invoice_reference)

    class Meta:
        app_label = 'mooringlicensing'


class DcvPermitFee(Payment):
    PAYMENT_TYPE_INTERNET = 0
    PAYMENT_TYPE_RECEPTION = 1
    PAYMENT_TYPE_BLACK = 2
    PAYMENT_TYPE_TEMPORARY = 3
    PAYMENT_TYPE_CHOICES = (
        (PAYMENT_TYPE_INTERNET, 'Internet booking'),
        (PAYMENT_TYPE_RECEPTION, 'Reception booking'),
        (PAYMENT_TYPE_BLACK, 'Black booking'),
        (PAYMENT_TYPE_TEMPORARY, 'Temporary reservation'),
    )

    dcv_permit = models.ForeignKey('DcvPermit', on_delete=models.PROTECT, blank=True, null=True, related_name='dcv_permit_fees')
    payment_type = models.SmallIntegerField(choices=PAYMENT_TYPE_CHOICES, default=0)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    created_by = models.ForeignKey(EmailUser, on_delete=models.PROTECT, blank=True, null=True, related_name='created_by_dcv_permit_fee')
    invoice_reference = models.CharField(max_length=50, null=True, blank=True, default='')
    fee_items = models.ManyToManyField('FeeItem', related_name='dcv_permit_fees')

    def __str__(self):
        return 'DcvPermit {} : Invoice {}'.format(self.dcv_permit, self.invoice_reference)

    class Meta:
        app_label = 'mooringlicensing'


class StickerActionFee(Payment):
    PAYMENT_TYPE_INTERNET = 0
    PAYMENT_TYPE_RECEPTION = 1
    PAYMENT_TYPE_BLACK = 2
    PAYMENT_TYPE_TEMPORARY = 3
    PAYMENT_TYPE_CHOICES = (
        (PAYMENT_TYPE_INTERNET, 'Internet booking'),
        (PAYMENT_TYPE_RECEPTION, 'Reception booking'),
        (PAYMENT_TYPE_BLACK, 'Black booking'),
        (PAYMENT_TYPE_TEMPORARY, 'Temporary reservation'),
    )

    payment_type = models.SmallIntegerField(choices=PAYMENT_TYPE_CHOICES, default=0)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    created_by = models.ForeignKey(EmailUser,on_delete=models.PROTECT, blank=True, null=True,)
    invoice_reference = models.CharField(max_length=50, null=True, blank=True, default='')

    def __str__(self):
        stickers = []
        for sticker_action_detail in self.sticker_action_details.all():
            stickers. append(sticker_action_detail.sticker.number)
        return 'Sticker(s): [{}] : Invoice {}'.format(','.join(stickers), self.invoice_reference)

    class Meta:
        app_label = 'mooringlicensing'


class FeeItemApplicationFee(models.Model):
    fee_item = models.ForeignKey('FeeItem',)
    application_fee = models.ForeignKey('ApplicationFee',)
    vessel_details = models.ForeignKey(VesselDetails, null=True, blank=True)
    amount_to_be_paid = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, default=None)
    amount_paid = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, default=None)

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def application_type(self):
        return self.fee_item.application_type


class ApplicationFee(Payment):
    PAYMENT_TYPE_INTERNET = 0
    PAYMENT_TYPE_RECEPTION = 1
    PAYMENT_TYPE_BLACK = 2
    PAYMENT_TYPE_TEMPORARY = 3
    PAYMENT_TYPE_CHOICES = (
        (PAYMENT_TYPE_INTERNET, 'Internet booking'),
        (PAYMENT_TYPE_RECEPTION, 'Reception booking'),
        (PAYMENT_TYPE_BLACK, 'Black booking'),
        (PAYMENT_TYPE_TEMPORARY, 'Temporary reservation'),
    )

    proposal = models.ForeignKey('Proposal', on_delete=models.PROTECT, blank=True, null=True, related_name='application_fees')
    payment_type = models.SmallIntegerField(choices=PAYMENT_TYPE_CHOICES, default=0)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    created_by = models.ForeignKey(EmailUser,on_delete=models.PROTECT, blank=True, null=True,related_name='created_by_application_fee')
    invoice_reference = models.CharField(max_length=50, null=True, blank=True, default='')
    fee_items = models.ManyToManyField('FeeItem', related_name='application_fees', through='FeeItemApplicationFee')
    system_invoice = models.BooleanField(default=False)

    def __str__(self):
        return 'Application {} : Invoice {}'.format(self.proposal, self.invoice_reference)

    @property
    def fee_constructor(self):
        # TODO: this is not always correct...???
        if self.fee_items.count():
            return self.fee_items.first().fee_constructor
        return None

    class Meta:
        app_label = 'mooringlicensing'


class FeeSeason(models.Model):
    application_type = models.ForeignKey(ApplicationType, null=True, blank=True, limit_choices_to={'fee_by_fee_constructor': True})
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        if self.start_date:
            return self.name
        else:
            return '{} (No periods found)'.format(self.name)

    def get_first_period(self):
        first_period = self.fee_periods.order_by('start_date').first()
        return first_period

    @property
    def is_editable(self):
        temp = self.fee_constructors
        temp = self.fee_constructors.all()
        for fee_constructor in self.fee_constructors.all():
            if not fee_constructor.is_editable:
                # This season has been used in the fee_constructor for payments at least once
                return False
        return True

    @property
    def start_date(self):
        first_period = self.get_first_period()
        return first_period.start_date if first_period else None

    @property
    def end_date(self):
        end_date = None
        if self.start_date:
            end_date = self.start_date + relativedelta(years=1) - relativedelta(days=1)
        return end_date

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = 'season'


class FeePeriod(models.Model):
    fee_season = models.ForeignKey(FeeSeason, null=True, blank=True, related_name='fee_periods')
    name = models.CharField(max_length=50, null=True, blank=True, default='')
    start_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return '{} (start: {})'.format(self.name, self.start_date)

    @property
    def is_editable(self):
        if self.fee_season:
            return self.fee_season.is_editable
        return True

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ['start_date']


class FeeConstructor(models.Model):
    application_type = models.ForeignKey(ApplicationType, null=False, blank=False, limit_choices_to={'fee_by_fee_constructor': True})
    fee_season = ChainedForeignKey(FeeSeason,
                                   chained_field='application_type',
                                   chained_model_field='application_type',
                                   show_all=False,
                                   auto_choose=True,
                                   sort=True,
                                   null=True,
                                   blank=True,
                                   related_name='fee_constructors')
    vessel_size_category_group = models.ForeignKey(VesselSizeCategoryGroup, null=False, blank=False, related_name='fee_constructors')
    incur_gst = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return 'ApplicationType: {}, Season: {}, VesselSizeCategoryGroup: {}'.format(self.application_type.description, self.fee_season, self.vessel_size_category_group)

    def get_fee_item(self, vessel_length, proposal_type=None, target_date=datetime.datetime.now(pytz.timezone(TIME_ZONE)).date(), age_group=None, admission_type=None, accept_null_vessel=False):
        fee_period = self.fee_season.fee_periods.filter(start_date__lte=target_date).order_by('start_date').last()
        if accept_null_vessel:
            vessel_size_category = self.vessel_size_category_group.vessel_size_categories.filter(null_vessel=True)
            if vessel_size_category.count() == 1:
                vessel_size_category = vessel_size_category[0]
            else:
                raise ValueError('Null vessel size category not found under the vessel size category group: {}'.format(self.vessel_size_category_group))
        else:
            vessel_size_category = self.vessel_size_category_group.vessel_size_categories.filter(start_size__lte=vessel_length, null_vessel=False).order_by('start_size').last()
        fee_item = self.get_fee_item_for_adjustment(vessel_size_category, fee_period, proposal_type=proposal_type, age_group=age_group, admission_type=admission_type)

        return fee_item

    def get_fee_item_for_adjustment(self, vessel_size_category, fee_period, proposal_type=None, age_group=None, admission_type=None):
        logger.info('Getting fee_item for the fee_constructor: {}, fee_period: {}, vessel_size_category: {}, proposal_type: {}, age_group: {}, admission_type: {}'.format(
            self, fee_period, vessel_size_category, proposal_type, age_group, admission_type,
        ))

        fee_item = FeeItem.objects.filter(
            fee_constructor=self,
            fee_period=fee_period,
            vessel_size_category=vessel_size_category,
            proposal_type=proposal_type,
            age_group=age_group,
            admission_type=admission_type,
        )

        if fee_item:
            return fee_item[0]
        else:
            # Fees are probably not configured yet...
            return None

    @property
    def is_editable(self):
        return True if not self.num_of_times_used_for_payment else False

    @property
    def start_date(self):
        if self.fee_season:
            return self.fee_season.start_date
        return None

    @property
    def end_date(self):
        if self.fee_season:
            return self.fee_season.end_date
        return None

    @property
    def num_of_times_used_for_payment(self):
        application_fees = ApplicationFee.objects.filter(fee_items__in=self.feeitem_set.all())
        return application_fees.count()

    def validate_unique(self, exclude=None):
        # Conditional unique together validation
        # unique_together in the Meta cannot handle conditional unique_together
        if self.enabled:
            if FeeConstructor.objects.exclude(id=self.id).filter(enabled=True, application_type=self.application_type, fee_season=self.fee_season).exists():
                # An application type cannot have the same fee_season multiple times.
                # Which means a vessel_size_category_group can be determined by the application_type and the fee_season
                raise ValidationError('Enabled Fee constructor with this Application type and Fee season already exists.')
        super(FeeConstructor, self).validate_unique(exclude)

    @classmethod
    def get_current_and_future_fee_constructors_by_application_type_and_date(cls, application_type, target_date=datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()):
        logger = logging.getLogger('mooringlicensing')

        # Select a fee_constructor object which has been started most recently for the application_type
        try:
            fee_constructors = []
            current_fee_constructor = cls.objects.filter(application_type=application_type,) \
                .annotate(s_date=Min("fee_season__fee_periods__start_date")) \
                .filter(s_date__lte=target_date, enabled=True).order_by('s_date').last()

            if current_fee_constructor:
                if target_date <= current_fee_constructor.fee_season.end_date:
                    fee_constructors.append(current_fee_constructor)

            future_fee_constructors = cls.objects.filter(application_type=application_type,) \
                .annotate(s_date=Min("fee_season__fee_periods__start_date")) \
                .filter(s_date__gte=target_date, enabled=True).order_by('s_date')

            fee_constructors.extend(list(future_fee_constructors))

            return fee_constructors

        except Exception as e:
            logger.error('Error determining the fee: {}'.format(e))
            raise

    @classmethod
    def get_fee_constructor_by_application_type_and_season(cls, application_type, fee_season):
        logger = logging.getLogger('mooringlicensing')

        try:
            fee_constructor_qs = cls.objects.filter(application_type=application_type, fee_season=fee_season, enabled=True)

            # Validation
            if not fee_constructor_qs:
                raise Exception('No fees are configured for the application type: {} and season: {}'.format(application_type, fee_season))
            elif fee_constructor_qs.count() > 1:
                # more than one fee constructors found
                raise Exception('Too many fees are configured for the application type: {} and season: {}'.format(application_type, fee_season))
            else:
                fee_constructor = fee_constructor_qs.first()
                return fee_constructor

        except Exception as e:
            logger.error('Error determining the fee: {}'.format(e))
            raise

    @classmethod
    def get_fee_constructor_by_application_type_and_date(cls, application_type, target_date=datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()):
        logger = logging.getLogger('mooringlicensing')

        # Select a fee_constructor object which has been started most recently for the application_type
        try:
            fee_constructor = None
            fee_constructor_qs = cls.objects.filter(application_type=application_type,)\
                .annotate(s_date=Min("fee_season__fee_periods__start_date"))\
                .filter(s_date__lte=target_date, enabled=True).order_by('s_date')

            # Validation
            if not fee_constructor_qs:
                raise Exception('No fees are configured for the application type: {} on the date: {}'.format(application_type, target_date))
            else:
                # One or more fee constructors found
                fee_constructor = fee_constructor_qs.last()

            if target_date <= fee_constructor.fee_season.end_date:
                # fee_constructor object selected above has not ended yet
                return fee_constructor
            else:
                # fee_constructor object selected above has already ended
                raise Exception('No fees are configured for the application type: {} on the date: {}'.format(application_type, target_date))
        except Exception as e:
            logger.error('Error determining the fee: {}'.format(e))
            raise

    def reconstruct_fees(self):
        # When fee_constructor object is created/updated, all the fee_items are recreated unless
        proposal_types = ProposalType.objects.all()
        valid_fee_item_ids = []  # We want to keep these fee items under this fee constructor object.

        try:
            for fee_period in self.fee_season.fee_periods.all():
                for vessel_size_category in self.vessel_size_category_group.vessel_size_categories.all():
                    if self.application_type.code == settings.APPLICATION_TYPE_DCV_PERMIT['code']:
                        # For DcvPermit, no proposal type for-loop
                        fee_item, created = FeeItem.objects.get_or_create(fee_constructor=self,
                                                                          fee_period=fee_period,
                                                                          vessel_size_category=vessel_size_category,
                                                                          proposal_type=None)
                        valid_fee_item_ids.append(fee_item.id)
                        if created:
                            logger.info(
                                'FeeItem created: {} - {}'.format(fee_period.name,
                                                                  vessel_size_category.name))

                    elif self.application_type.code == settings.APPLICATION_TYPE_DCV_ADMISSION['code']:
                        # For DcvAdmission, no proposal type for-loop
                        from mooringlicensing.components.approvals.models import AgeGroup
                        for age_gruop in AgeGroup.objects.all():
                            from mooringlicensing.components.approvals.models import AdmissionType
                            for admission_type in AdmissionType.objects.all():
                                fee_item, created = FeeItem.objects.get_or_create(fee_constructor=self,
                                                                                  fee_period=fee_period,
                                                                                  vessel_size_category=vessel_size_category,
                                                                                  age_group=age_gruop,
                                                                                  admission_type=admission_type,
                                                                                  proposal_type=None)
                                valid_fee_item_ids.append(fee_item.id)
                                if created:
                                    logger.info(
                                        'FeeItem created: {} - {} - {} - {}'.format(fee_period.name,
                                                                                    vessel_size_category.name,
                                                                                    age_gruop,
                                                                                    admission_type))
                    else:
                        for proposal_type in proposal_types:
                            if vessel_size_category.null_vessel and \
                                    ((self.application_type.code in (WaitingListApplication.code, AnnualAdmissionApplication.code) and proposal_type.code == settings.PROPOSAL_TYPE_RENEWAL) or
                                     proposal_type.code in [settings.PROPOSAL_TYPE_NEW, settings.PROPOSAL_TYPE_AMENDMENT,]):
                                # When WLA/AAA and renewal application
                                # When new/amendment application
                                # No fee_items created
                                continue
                            else:
                                fee_item, created = FeeItem.objects.get_or_create(fee_constructor=self,
                                                                                  fee_period=fee_period,
                                                                                  vessel_size_category=vessel_size_category,
                                                                                  proposal_type=proposal_type)
                                valid_fee_item_ids.append(fee_item.id)
                                if created:
                                    logger.info('FeeItem created: {} - {} - {}'.format(fee_period.name,
                                                                                       vessel_size_category.name,
                                                                                       proposal_type.description))

            # Delete unused onl fee_items
            if self.num_of_times_used_for_payment == 0:
                unneeded_fee_items = FeeItem.objects.filter(fee_constructor=self).exclude(id__in=valid_fee_item_ids)
                if unneeded_fee_items:
                    unneeded_fee_item_ids = [item.id for item in unneeded_fee_items]
                    unneeded_fee_items.delete()
                    logger.info('FeeItem deleted: FeeItem ids: {}'.format(unneeded_fee_item_ids))
        except Exception as e:
            print(e)

    class Meta:
        app_label = 'mooringlicensing'


class FeeItemStickerReplacement(models.Model):
    amount = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', help_text='unit [$AU/Sticker]')
    date_of_enforcement = models.DateField(blank=True, null=True)
    enabled = models.BooleanField(default=True)
    incur_gst = models.BooleanField(default=True)

    @staticmethod
    def get_fee_item_by_date(target_date=datetime.datetime.now(pytz.timezone(settings.TIME_ZONE)).date()):
        try:
            fee_item = FeeItemStickerReplacement.objects.filter(date_of_enforcement__lte=target_date, enabled=True).order_by('-date_of_enforcement').first()
            return fee_item
        except Exception as e:
            raise ValueError('Sticker replacement fee not found for the date: {}'.format(target_date))

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = 'Fee (sticker replacement)'
        verbose_name_plural = 'Fee (sticker replacement)'


class FeeItem(models.Model):
    fee_constructor = models.ForeignKey(FeeConstructor, null=True, blank=True)
    fee_period = models.ForeignKey(FeePeriod, null=True, blank=True)
    vessel_size_category = models.ForeignKey(VesselSizeCategory, null=True, blank=True)
    proposal_type = models.ForeignKey('ProposalType', null=True, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', help_text='$')
    incremental_amount = models.BooleanField(default=False, help_text='When ticked, The amount will be the increase in the rate per meter')  # When False, the 'amount' value is the price for this item.  When True, the 'amount' is the price per meter.
    # For DcvAdmission
    age_group = models.ForeignKey('AgeGroup', null=True, blank=True)
    admission_type = models.ForeignKey('AdmissionType', null=True, blank=True)

    def __str__(self):
        return '${}: {}, {}, {}, {}'.format(self.amount, self.fee_constructor.application_type, self.fee_period, self.vessel_size_category, self.proposal_type)

    @property
    def application_type(self):
        return self.fee_constructor.application_type

    def get_corresponding_fee_item(self, proposal_type):
        fee_item = self.fee_constructor.feeitem_set.filter(
            fee_period=self.fee_period,
            vessel_size_category=self.vessel_size_category,
            proposal_type=proposal_type,
        )
        if fee_item.count():
            fee_item = fee_item.first()
            return fee_item
        else:
            raise Exception('FeeItem for fee_period: {}, vessel_size_category: {}, proposal_type: {} not found.'.format(self.fee_period, self.vessel_size_category, self.proposal_type))

    def get_absolute_amount(self, vessel_size=None):
        if not self.incremental_amount or not vessel_size:
            return self.amount
        else:
            # This self.amount is the incremental amount.  Therefore the absolute amount must be calculated based on the fee_item of one smaller vessel size category
            vessel_size = float(vessel_size)
            smaller_vessel_size_category = self.vessel_size_category.get_one_smaller_category()
            if smaller_vessel_size_category:
                smaller_fee_item = self.fee_constructor.feeitem_set.filter(fee_period=self.fee_period, proposal_type=self.proposal_type, vessel_size_category=smaller_vessel_size_category)
                if smaller_fee_item.count() == 1:
                    smaller_fee_item = smaller_fee_item.first()
                    diff = vessel_size - float(self.vessel_size_category.start_size)
                    number_of_increment = ceil(diff)
                    if diff.is_integer() and self.vessel_size_category.include_start_size:
                        # In this case, 'vessel_size' is at the first step of this fee_item object.
                        number_of_increment += 1
                    absolute_amount = smaller_fee_item.get_absolute_amount(self.vessel_size_category.start_size) + number_of_increment * self.amount
                    return absolute_amount
                else:
                    # Should not reach here
                    raise Exception('FeeItem object not found in the FeeConstructor: {} for {}, {} and {}'.format(self.fee_constructor, self.fee_period, self.proposal_type, smaller_vessel_size_category))
            else:
                # This fee_item is for the smallest vessel size category and also incremental
                number_of_increment = ceil(vessel_size - float(self.vessel_size_category.start_size))
                absolute_amount = self.amount * number_of_increment
                return absolute_amount

    @property
    def is_editable(self):
        if self.fee_constructor:
            return self.fee_constructor.is_editable
        return True

    class Meta:
        app_label = 'mooringlicensing'


class OracleCodeItem(models.Model):
    application_type = models.ForeignKey(ApplicationType, blank=True, null=True, related_name='oracle_code_items')
    value = models.CharField(max_length=50, null=True, blank=True, default='T1 EXEMPT')
    date_of_enforcement = models.DateField(blank=True, null=True)

    class Meta:
        app_label = 'mooringlicensing'


import reversion
#reversion.register(DcvAdmissionFee, follow=[])
#reversion.register(DcvPermitFee, follow=[])
#reversion.register(StickerActionFee, follow=['sticker_action_details'])
#reversion.register(FeeItemApplicationFee, follow=['fee_item', 'application_fee', 'vessel_details'])
#reversion.register(ApplicationFee, follow=['feeitemapplicationfee_set'])
#reversion.register(ApplicationFee)
#reversion.register(FeeSeason, follow=['fee_periods', 'fee_constructors', 'dcvadmissionarrival_set', 'dcv_permits', 'sticker_set'])
#reversion.register(FeePeriod, follow=['feeitem_set'])
#reversion.register(FeeConstructor, follow=['feeitem_set', 'dcv_admission_arrivals', 'sticker_set'])
#reversion.register(FeeItemStickerReplacement, follow=[])
#reversion.register(FeeItem, follow=['dcv_admission_fees', 'dcv_permit_fees', 'feeitemapplicationfee_set', 'application_fees'])
#reversion.register(FeeItem, follow=['dcv_admission_fees', 'dcv_permit_fees', 'application_fees'])
#reversion.register(OracleCodeItem, follow=[])

