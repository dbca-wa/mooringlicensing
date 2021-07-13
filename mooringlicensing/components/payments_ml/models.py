import datetime
import logging
from decimal import Decimal

import pytz
from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Min
from ledger.accounts.models import RevisionedMixin, EmailUser
from ledger.payments.invoice.models import Invoice
from ledger.settings_base import TIME_ZONE

from mooringlicensing.components.main.models import ApplicationType, VesselSizeCategoryGroup, VesselSizeCategory
# from mooringlicensing.components.proposals.models import Proposal, ProposalType

logger = logging.getLogger('__name__')


class Payment(RevisionedMixin):
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
        invoices = []
        amount = Decimal('0.0')
        references = self.invoices.all().values('invoice_reference')
        for r in references:
            try:
                invoices.append(Invoice.objects.get(reference=r.get("invoice_reference")))
            except Invoice.DoesNotExist:
                pass
        for i in invoices:
            if not i.voided:
                amount += i.payment_amount

        if amount == 0:
            return 'unpaid'
        elif self.cost_total < amount:
            return 'over_paid'
        elif self.cost_total > amount:
            return 'partially_paid'
        return "paid"


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
    # fee_constructor = models.ForeignKey('FeeConstructor', on_delete=models.PROTECT, blank=True, null=True, related_name='dcv_admission_fees')
    # fee_item = models.ForeignKey('FeeItem', on_delete=models.PROTECT, blank=True, null=True,)
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
    # fee_constructor = models.ForeignKey('FeeConstructor', on_delete=models.PROTECT, blank=True, null=True, related_name='dcv_permit_fees')
    # fee_item = models.ForeignKey('FeeItem', on_delete=models.PROTECT, blank=True, null=True,)
    fee_items = models.ManyToManyField('FeeItem', related_name='dcv_permit_fees')

    def __str__(self):
        return 'DcvPermit {} : Invoice {}'.format(self.dcv_permit, self.invoice_reference)

    class Meta:
        app_label = 'mooringlicensing'


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
    # fee_constructor = models.ForeignKey('FeeConstructor', on_delete=models.PROTECT, blank=True, null=True, related_name='application_fees')
    # fee_item = models.ForeignKey('FeeItem', on_delete=models.PROTECT, blank=True, null=True,)
    fee_items = models.ManyToManyField('FeeItem', related_name='application_fees')

    def __str__(self):
        return 'Application {} : Invoice {}'.format(self.proposal, self.invoice_reference)

    @property
    def fee_constructor(self):
        # TODO: this is not always correct...???
        if self.fee_items:
            return self.fee_items.first().fee_constructor
        return None

    class Meta:
        app_label = 'mooringlicensing'


class FeeSeason(RevisionedMixin):
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        if self.start_date:
            # return '{} ({} - {})'.format(self.name, self.start_date, self.end_date)
            return self.name
        else:
            return '{} (No periods found)'.format(self.name)

        # num_item = self.fee_periods.count()
        # num_str = '{} period'.format(num_item) if num_item == 1 else '{} periods'.format(num_item)
        #
        # if self.start_date:
        #     return '{} [{} to {}] ({})'.format(self.name, self.start_date, self.end_date, num_str)
        # else:
        #     return '{} (No periods found)'.format(self.name)

    def get_first_period(self):
        first_period = self.fee_periods.order_by('start_date').first()
        return first_period

    # def save(self, **kwargs):
    #     if not self.is_editable:
    #         raise ValidationError('Season cannot be changed once used for payment calculation')
    #     else:
    #         super(FeeSeason, self).save(**kwargs)

    @property
    def is_editable(self):
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
        end_date = self.start_date + relativedelta(years=1) - relativedelta(days=1)
        return end_date

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = 'season'


class FeePeriod(RevisionedMixin):
    fee_season = models.ForeignKey(FeeSeason, null=True, blank=True, related_name='fee_periods')
    name = models.CharField(max_length=50, null=True, blank=True, default='')
    start_date = models.DateField(null=True, blank=True)
    # end_date = (next fee_period - 1day) or fee_season.end_date, which is start_date + 1year

    def __str__(self):
        return '{} (start: {})'.format(self.name, self.start_date)

    @property
    def is_editable(self):
        if self.fee_season:
            return self.fee_season.is_editable
        return True

    # def save(self, **kwargs):
    #     if not self.is_editable:
    #         raise ValidationError('Period cannot be changed once used for payment calculation')
    #     else:
    #         super(FeePeriod, self).save(**kwargs)

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ['start_date']


class FeeConstructor(RevisionedMixin):
    application_type = models.ForeignKey(ApplicationType, null=False, blank=False)
    fee_season = models.ForeignKey(FeeSeason, null=False, blank=False, related_name='fee_constructors')
    vessel_size_category_group = models.ForeignKey(VesselSizeCategoryGroup, null=False, blank=False, related_name='fee_constructors')
    incur_gst = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return 'ApplicationType: {}, Season: {}, VesselSizeCategoryGroup: {}'.format(self.application_type.description, self.fee_season, self.vessel_size_category_group)

    def get_fee_item(self, vessel_length, proposal_type=None, target_date=datetime.datetime.now(pytz.timezone(TIME_ZONE)).date(), age_group=None, admission_type=None):
        fee_period = self.fee_season.fee_periods.filter(start_date__lte=target_date).order_by('start_date').last()
        vessel_size_category = self.vessel_size_category_group.vessel_size_categories.filter(start_size__lte=vessel_length).order_by('start_size').last()
        fee_item = self.get_fee_item_for_adjustment(vessel_size_category, fee_period, proposal_type=proposal_type, age_group=age_group, admission_type=admission_type)

        return fee_item

    def get_fee_item_for_adjustment(self, vessel_size_category, fee_period, proposal_type=None, age_group=None, admission_type=None):
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
        # return self.application_fees.count() + self.dcv_permit_fees.count()
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
        logger = logging.getLogger('payment_checkout')

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
        logger = logging.getLogger('payment_checkout')

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
    def get_current_fee_constructor_by_application_type_and_date(cls, application_type, target_date=datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()):
        logger = logging.getLogger('payment_checkout')

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

    class Meta:
        app_label = 'mooringlicensing'


class FeeItem(RevisionedMixin):
    fee_constructor = models.ForeignKey(FeeConstructor, null=True, blank=True)
    fee_period = models.ForeignKey(FeePeriod, null=True, blank=True)
    vessel_size_category = models.ForeignKey(VesselSizeCategory, null=True, blank=True)
    proposal_type = models.ForeignKey('ProposalType', null=True, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', help_text='$')
    # For DcvAdmission
    age_group = models.ForeignKey('AgeGroup', null=True, blank=True)
    admission_type = models.ForeignKey('AdmissionType', null=True, blank=True)

    def __str__(self):
        return '${}: ApplicationType: {}, Period: {}, VesselSizeCategory: {}'.format(self.amount, self.fee_constructor.application_type, self.fee_period, self.vessel_size_category)

    @property
    def is_editable(self):
        if self.fee_constructor:
            return self.fee_constructor.is_editable
        return True

    class Meta:
        app_label = 'mooringlicensing'


