from __future__ import unicode_literals

import json
import datetime
from _pydecimal import Decimal

import pytz
import uuid
from ledger.settings_base import TIME_ZONE
from ledger.payments.pdf import create_invoice_pdf_bytes
from django.db import models, transaction
from django.dispatch import receiver
from django.db.models.signals import pre_delete
from django.utils.encoding import python_2_unicode_compatible
from django.core.exceptions import ValidationError, ObjectDoesNotExist, ImproperlyConfigured
from django.contrib.postgres.fields.jsonb import JSONField
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import Group
from django.utils import timezone
from django.conf import settings
from django.core.urlresolvers import reverse
from ledger.accounts.models import EmailUser, RevisionedMixin
from mooringlicensing import exceptions
from mooringlicensing.components.organisations.models import Organisation
from mooringlicensing.components.main.models import (
    CommunicationsLogEntry,
    UserAction,
    Document, ApplicationType, NumberOfDaysType, NumberOfDaysSetting,
)
from mooringlicensing.components.main.decorators import (
        basic_exception_handler, 
        timeit, 
        query_debugger
        )
from ledger.checkout.utils import createCustomBasket
from ledger.payments.invoice.models import Invoice
from ledger.payments.invoice.utils import CreateInvoiceBasket

from mooringlicensing.components.proposals.email import (
    send_application_approved_or_declined_email,
    send_amendment_email_notification,
    send_confirmation_email_upon_submit,
    send_approver_approve_decline_email_notification,
    send_proposal_approver_sendback_email_notification, send_endorsement_of_authorised_user_application_email,
    send_documents_upload_for_mooring_licence_application_email,
    send_other_documents_submitted_notification_email, send_notification_email_upon_submit_to_assessor,
    send_aua_approved_or_declined_email_new_renewal, send_mla_approved_or_declined_email_new_renewal,
    send_au_summary_to_ml_holder,
)
from mooringlicensing.ordered_model import OrderedModel
import copy
import subprocess
from django.db.models import Q, Max
from reversion.models import Version
from dirtyfields import DirtyFieldsMixin
from rest_framework import serializers

import logging

from mooringlicensing.settings import PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL, PAYMENT_SYSTEM_ID, \
    PAYMENT_SYSTEM_PREFIX, PROPOSAL_TYPE_NEW, CODE_DAYS_FOR_ENDORSER_AUA

logger = logging.getLogger(__name__)
logger_for_payment = logging.getLogger('mooringlicensing')


def update_proposal_doc_filename(instance, filename):
    return '{}/proposals/{}/documents/{}'.format(settings.MEDIA_APP_DIR, instance.proposal.id,filename)

def update_onhold_doc_filename(instance, filename):
    return '{}/proposals/{}/on_hold/{}'.format(settings.MEDIA_APP_DIR, instance.proposal.id,filename)

def update_proposal_required_doc_filename(instance, filename):
    return '{}/proposals/{}/required_documents/{}'.format(settings.MEDIA_APP_DIR, instance.proposal.id,filename)

def update_requirement_doc_filename(instance, filename):
    return '{}/proposals/{}/requirement_documents/{}'.format(settings.MEDIA_APP_DIR, instance.requirement.proposal.id,filename)

def update_proposal_comms_log_filename(instance, filename):
    return '{}/proposals/{}/communications/{}/{}'.format(settings.MEDIA_APP_DIR, instance.log_entry.proposal.id, instance.log_entry.id, filename)

def update_vessel_comms_log_filename(instance, filename):
    return '{}/vessels/{}/communications/{}/{}'.format(settings.MEDIA_APP_DIR, instance.log_entry.vessel.id, instance.log_entry.id, filename)

def update_mooring_comms_log_filename(instance, filename):
    return '{}/moorings/{}/communications/{}/{}'.format(settings.MEDIA_APP_DIR, instance.log_entry.mooring.id, instance.log_entry.id, filename)


class ProposalDocument(Document):
    proposal = models.ForeignKey('Proposal',related_name='documents')
    _file = models.FileField(upload_to=update_proposal_doc_filename, max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Document"


class RequirementDocument(Document):
    requirement = models.ForeignKey('ProposalRequirement',related_name='requirement_documents')
    _file = models.FileField(upload_to=update_requirement_doc_filename, max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    visible = models.BooleanField(default=True) # to prevent deletion on file system, hidden and still be available in history

    def delete(self):
        if self.can_delete:
            return super(RequirementDocument, self).delete()


VESSEL_TYPES = (
        ('yacht', 'Yacht'),
        ('cabin_cruiser', 'Cabin Cruiser'),
        ('tender', 'Tender'),
        ('other', 'Other'),
        )
INSURANCE_CHOICES = (
    ("five_million", "$5 million Third Party Liability insurance cover - required for vessels of length less than 6.4 metres"),
    ("ten_million", "$10 million Third Party Liability insurance cover - required for vessels of length 6.4 metres or greater"),
    ("over_ten", "over $10 million"),
)
MOORING_AUTH_PREFERENCES = (
        ('site_licensee', 'By a mooring site licensee for their mooring'),
        ('ria', 'By Rottnest Island Authority for a mooring allocated by the Authority'),
        )


class ProposalType(RevisionedMixin):
    code = models.CharField(max_length=30, blank=True, null=True)
    description = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        # return 'id: {} code: {}'.format(self.id, self.code)
        return self.description

    class Meta:
        app_label = 'mooringlicensing'


class Proposal(DirtyFieldsMixin, RevisionedMixin):
#class Proposal(DirtyFieldsMixin, models.Model):
    APPLICANT_TYPE_ORGANISATION = 'ORG'
    APPLICANT_TYPE_PROXY = 'PRX'
    APPLICANT_TYPE_SUBMITTER = 'SUB'

    CUSTOMER_STATUS_DRAFT = 'draft'
    CUSTOMER_STATUS_WITH_ASSESSOR = 'with_assessor'
    CUSTOMER_STATUS_AWAITING_ENDORSEMENT = 'awaiting_endorsement'
    CUSTOMER_STATUS_AWAITING_DOCUMENTS = 'awaiting_documents'
    CUSTOMER_STATUS_PRINTING_STICKER = 'printing_sticker'
    CUSTOMER_STATUS_APPROVED = 'approved'
    CUSTOMER_STATUS_DECLINED = 'declined'
    CUSTOMER_STATUS_DISCARDED = 'discarded'
    CUSTOMER_STATUS_AWAITING_PAYMENT = 'awaiting_payment'
    CUSTOMER_STATUS_EXPIRED = 'expired'
    CUSTOMER_STATUS_CHOICES = (
        (CUSTOMER_STATUS_DRAFT, 'Draft'),
        (CUSTOMER_STATUS_WITH_ASSESSOR, 'Under Review'),
        (CUSTOMER_STATUS_AWAITING_ENDORSEMENT, 'Awaiting Endorsement'),
        (CUSTOMER_STATUS_AWAITING_DOCUMENTS, 'Awaiting Documents'),
        (CUSTOMER_STATUS_PRINTING_STICKER, 'Printing Sticker'),
        (CUSTOMER_STATUS_APPROVED, 'Approved'),
        (CUSTOMER_STATUS_DECLINED, 'Declined'),
        (CUSTOMER_STATUS_DISCARDED, 'Discarded'),
        (CUSTOMER_STATUS_AWAITING_PAYMENT, 'Awaiting Payment'),
        (CUSTOMER_STATUS_EXPIRED, 'Expired'),
        )

    # List of statuses from above that allow a customer to edit an application.
    CUSTOMER_EDITABLE_STATE = [
        #'temp',
        CUSTOMER_STATUS_DRAFT,
        # CUSTOMER_STATUS_AMENDMENT_REQUIRED,
    ]

    # List of statuses from above that allow a customer to view an application (read-only)
    CUSTOMER_VIEWABLE_STATE = [
        CUSTOMER_STATUS_WITH_ASSESSOR,
        CUSTOMER_STATUS_WITH_ASSESSOR,
        # 'id_required',
        # 'returns_required',
        CUSTOMER_STATUS_AWAITING_PAYMENT,
        CUSTOMER_STATUS_PRINTING_STICKER,
        CUSTOMER_STATUS_AWAITING_ENDORSEMENT,
        CUSTOMER_STATUS_AWAITING_DOCUMENTS,
        CUSTOMER_STATUS_APPROVED,
        CUSTOMER_STATUS_DECLINED,
        CUSTOMER_STATUS_EXPIRED,
    ]

    PROCESSING_STATUS_DRAFT = 'draft'
    PROCESSING_STATUS_WITH_ASSESSOR = 'with_assessor'
    PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS = 'with_assessor_requirements'
    PROCESSING_STATUS_WITH_APPROVER = 'with_approver'
    PROCESSING_STATUS_PRINTING_STICKER = 'printing_sticker'
    PROCESSING_STATUS_AWAITING_ENDORSEMENT = 'awaiting_endorsement'
    PROCESSING_STATUS_AWAITING_DOCUMENTS = 'awaiting_documents'
    PROCESSING_STATUS_APPROVED = 'approved'
    PROCESSING_STATUS_DECLINED = 'declined'
    PROCESSING_STATUS_DISCARDED = 'discarded'
    PROCESSING_STATUS_AWAITING_PAYMENT = 'awaiting_payment'
    PROCESSING_STATUS_EXPIRED = 'expired'

    PROCESSING_STATUS_CHOICES = (
        (PROCESSING_STATUS_DRAFT, 'Draft'),
        (PROCESSING_STATUS_WITH_ASSESSOR, 'With Assessor'),
        (PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS, 'With Assessor (Requirements)'),
        (PROCESSING_STATUS_WITH_APPROVER, 'With Approver'),
        (PROCESSING_STATUS_PRINTING_STICKER, 'Printing Sticker'),
        (PROCESSING_STATUS_AWAITING_ENDORSEMENT, 'Awaiting Endorsement'),
        (PROCESSING_STATUS_AWAITING_DOCUMENTS, 'Awaiting Documents'),
        (PROCESSING_STATUS_APPROVED, 'Approved'),
        (PROCESSING_STATUS_DECLINED, 'Declined'),
        (PROCESSING_STATUS_DISCARDED, 'Discarded'),
        (PROCESSING_STATUS_AWAITING_PAYMENT, 'Awaiting Payment'),
        (PROCESSING_STATUS_EXPIRED, 'Expired'),
    )

    proposal_type = models.ForeignKey(ProposalType, blank=True, null=True)

#data = JSONField(blank=True, null=True)
    assessor_data = JSONField(blank=True, null=True)
    comment_data = JSONField(blank=True, null=True)
    #schema = JSONField(blank=False, null=False)
    proposed_issuance_approval = JSONField(blank=True, null=True)

    customer_status = models.CharField('Customer Status', max_length=40, choices=CUSTOMER_STATUS_CHOICES,
                                       default=CUSTOMER_STATUS_CHOICES[0][0])
    org_applicant = models.ForeignKey(
        Organisation,
        blank=True,
        null=True,
        related_name='org_applications') # not currently used in ML
    lodgement_number = models.CharField(max_length=9, blank=True, default='')
    lodgement_sequence = models.IntegerField(blank=True, default=0)
    lodgement_date = models.DateTimeField(blank=True, null=True)

    proxy_applicant = models.ForeignKey(EmailUser, blank=True, null=True, related_name='mooringlicensing_proxy') # not currently used by ML
    submitter = models.ForeignKey(EmailUser, blank=True, null=True, related_name='mooringlicensing_proposals')

    assigned_officer = models.ForeignKey(EmailUser, blank=True, null=True, related_name='mooringlicensing_proposals_assigned', on_delete=models.SET_NULL)
    assigned_approver = models.ForeignKey(EmailUser, blank=True, null=True, related_name='mooringlicensing_proposals_approvals', on_delete=models.SET_NULL)
    processing_status = models.CharField('Processing Status', max_length=40, choices=PROCESSING_STATUS_CHOICES,
                                         default=PROCESSING_STATUS_CHOICES[0][0])
    prev_processing_status = models.CharField(max_length=40, blank=True, null=True)

    approval = models.ForeignKey('mooringlicensing.Approval',null=True,blank=True)
    previous_application = models.ForeignKey('self', on_delete=models.PROTECT, blank=True, null=True, related_name="succeeding_proposals")

    proposed_decline_status = models.BooleanField(default=False)
    title = models.CharField(max_length=255,null=True,blank=True)
    approval_level = models.CharField('Activity matrix approval level', max_length=255,null=True,blank=True)
    approval_level_document = models.ForeignKey(ProposalDocument, blank=True, null=True, related_name='approval_level_document')
    approval_comment = models.TextField(blank=True)
    #If the proposal is created as part of migration of approvals
    migrated=models.BooleanField(default=False)
    #application_type = models.ForeignKey(ApplicationType)

    #fee_invoice_reference = models.CharField(max_length=50, null=True, blank=True, default='')
    #vessel_details_many = models.ManyToManyField('VesselDetails', related_name="proposal_vessel_details_many")
    vessel_details = models.ForeignKey('VesselDetails', blank=True, null=True)
    vessel_ownership = models.ForeignKey('VesselOwnership', blank=True, null=True)
    # draft proposal status VesselDetails records - goes to VesselDetails master record after submit
    rego_no = models.CharField(max_length=200, blank=True, null=True)
    vessel_id = models.IntegerField(null=True,blank=True)
    vessel_type = models.CharField(max_length=20, choices=VESSEL_TYPES, blank=True)
    vessel_name = models.CharField(max_length=400, blank=True)
    #vessel_overall_length = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # exists in MB as 'size'
    vessel_length = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # does not exist in MB
    vessel_draft = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_beam = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_weight = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # tonnage
    berth_mooring = models.CharField(max_length=200, blank=True)
    ## Name as shown on DoT registration papers
    dot_name = models.CharField(max_length=200, blank=True, null=True)
    #org_name = models.CharField(max_length=200, blank=True, null=True)
    percentage = models.IntegerField(null=True, blank=True)
    individual_owner = models.NullBooleanField()
    company_ownership_percentage = models.IntegerField(null=True, blank=True)
    company_ownership_name = models.CharField(max_length=200, blank=True, null=True)
    # only for draft status proposals, otherwise retrieve from within vessel_ownership
    #company_ownership = models.ForeignKey('CompanyOwnership', blank=True, null=True)
    ## Insurance component field
    insurance_choice = models.CharField(max_length=20, choices=INSURANCE_CHOICES, blank=True)
    ## WLA
    preferred_bay = models.ForeignKey('MooringBay', null=True, blank=True, on_delete=models.SET_NULL)
    ## Electoral Roll component field
    silent_elector = models.NullBooleanField() # if False, user is on electoral roll
    ## Mooring Authorisation fields mooring_suthorisation_preferences, bay_preferences_numbered, site_licensee_email and mooring
    # AUA
    mooring_authorisation_preference = models.CharField(max_length=20, choices=MOORING_AUTH_PREFERENCES, blank=True)
    bay_preferences_numbered = ArrayField(
            models.IntegerField(null=True, blank=True),
            blank=True,null=True,
            )
    site_licensee_email = models.CharField(max_length=200, blank=True, null=True)
    mooring = models.ForeignKey('Mooring', null=True, blank=True, on_delete=models.SET_NULL)
    endorser_reminder_sent = models.BooleanField(default=False)
    ## MLA
    allocated_mooring = models.ForeignKey('Mooring', null=True, blank=True, on_delete=models.SET_NULL, related_name="ria_generated_proposal")
    waiting_list_allocation = models.ForeignKey('mooringlicensing.Approval',null=True,blank=True, related_name="ria_generated_proposal")
    date_invited = models.DateField(blank=True, null=True)  # The date RIA has invited the WLAllocation holder.  This application is expired in a configurable number of days after the invitation without submit.
    invitee_reminder_sent = models.BooleanField(default=False)
    temporary_document_collection_id = models.IntegerField(blank=True, null=True)
    # AUA amendment
    keep_existing_mooring = models.BooleanField(default=False)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application"
        verbose_name_plural = "Applications"

    def __str__(self):
        return str(self.lodgement_number)

    @staticmethod
    def get_corresponding_amendment_fee_item(accept_null_vessel, fee_constructor, fee_item, target_date, vessel_length):
        proposal_type_amendment = ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT)
        if fee_item.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
            # This application is 'Amendment' application.  fee_item is already for 'Amendment'
            fee_item_amendment_calculation = fee_item
        else:
            # We want to store the fee_item considered to be paid in order to calculate the amount for the amendment application
            fee_item_amendment_calculation = fee_constructor.get_fee_item(vessel_length, proposal_type_amendment,
                                                                          target_date,
                                                                          accept_null_vessel=accept_null_vessel)
        return fee_item_amendment_calculation

    def get_fee_items_paid(self, fee_season, vessel_details=None):
        from mooringlicensing.components.payments_ml.models import FeeItemApplicationFee

        fee_items = []

        queries = Q()
        queries &= Q(application_fee__in=self.application_fees.all())
        queries &= Q(fee_item__fee_period__fee_season=fee_season)
        if vessel_details:
            # AA component for ML, we mind the vessel
            queries &= Q(vessel_details__vessel=vessel_details.vessel)

        fee_item_application_fees = FeeItemApplicationFee.objects.filter(queries)

        for fee_item_application_fee in fee_item_application_fees:
            fee_items.append(fee_item_application_fee.fee_item)

        return fee_items

    @property
    def fee_period(self):
        fee_items = self.get_fee_items_paid()
        if len(fee_items):
            fee_item = fee_items[0]
            return fee_item.fee_period

    @property
    def vessel_removed(self):
        # for AUP, AAP manage_stickers
        #from mooringlicensing.components.approvals.models import AuthorisedUserPermit, AnnualAdmissionPermit
        if type(self.child_obj) not in [AuthorisedUserApplication, AnnualAdmissionApplication]:
            raise ValidationError("Only for AUP, AAA")
        removed = False
        if self.previous_application and self.previous_application.vessel_ownership and not self.vessel_ownership:
            removed = True
        return removed

    @property
    def vessel_swapped(self):
        # for AUP, AAP manage_stickers
        #from mooringlicensing.components.approvals.models import AuthorisedUserPermit, AnnualAdmissionPermit
        if type(self.child_obj) not in [AuthorisedUserApplication, AnnualAdmissionApplication]:
            raise ValidationError("Only for AUP, AAA")
        changed = False
        if (self.vessel_ownership and self.previous_application and self.previous_application.vessel_ownership and
                self.vessel_ownership.vessel.rego_no != self.previous_application.vessel_ownership.vessel.rego_no):
            changed = True
        return changed

    @property
    def vessel_amend_new(self):
        # only for amendment
        # for AUP, AAP manage_stickers
        #from mooringlicensing.components.approvals.models import AuthorisedUserPermit, AnnualAdmissionPermit
        if type(self.child_obj) not in [AuthorisedUserApplication, AnnualAdmissionApplication]:
            raise ValidationError("Only for AUP, AAA")
        new = False
        if (self.proposal_type is not ProposalType.objects.get(code='new') and self.vessel_ownership and
                self.previous_application and not self.previous_application.vessel_ownership):
            new = True
        return new

    def does_have_valid_associations(self):
        # Check if this application has valid associations with other applications and approvals
        return self.child_obj.does_have_valid_associations()

    @property
    def final_status(self):
        final_status = False
        if self.processing_status in ([Proposal.PROCESSING_STATUS_PRINTING_STICKER, Proposal.PROCESSING_STATUS_APPROVED]):
            final_status = True
        return final_status

    def endorse_approved(self, request):
        self.customer_status = Proposal.CUSTOMER_STATUS_WITH_ASSESSOR
        self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR

        # TODO: Action Log
        # self.approval.log_user_action(ApprovalUserAction.ACTION_AMEND_APPROVAL.format(self.approval.id),request)

        self.save()

    def endorse_declined(self, request):
        self.customer_status = Proposal.CUSTOMER_STATUS_DECLINED
        self.processing_status = Proposal.PROCESSING_STATUS_DECLINED

        # TODO: Action Log
        # self.approval.log_user_action(ApprovalUserAction.ACTION_AMEND_APPROVAL.format(self.approval.id),request)

        self.save()

    def save(self, *args, **kwargs):
        super(Proposal, self).save(*args,**kwargs)
        if type(self) == Proposal:
            self.child_obj.refresh_from_db()

    @property
    def fee_constructor(self):
        if self.application_fees.count() < 1:
            return None
        elif self.application_fees.count() == 1:
            application_fee = self.application_fees.first()
            return application_fee.fee_constructor
        else:
            msg = 'Proposal: {} has {} ApplicationFees.  There should be 0 or 1.'.format(self, self.application_fees.count())
            logger.error(msg)
            raise ValidationError(msg)

    @property
    def invoice(self):
        if self.application_fees.count() < 1:
            return None
        elif self.application_fees.count() == 1:
            application_fee = self.application_fees.first()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            return invoice
        else:
            msg = 'Proposal: {} has {} ApplicationFees.  There should be 0 or 1.'.format(self, self.application_fees.count())
            logger.error(msg)
            raise ValidationError(msg)

    @property
    def start_date(self):
        if self.migrated:
            return datetime.datetime(2020,9,1).date()

        if self.application_fees.count() < 1:
            return None
        elif self.application_fees.count() == 1:
            application_fee = self.application_fees.first()
            if application_fee.fee_constructor:
                return application_fee.fee_constructor.start_date
            else:
                return None
        else:
            msg = 'Proposal: {} has {} ApplicationFees.  There should be 0 or 1.'.format(self, self.application_fees.count())
            logger.error(msg)
            raise ValidationError(msg)

    @property
    def end_date(self):
        if self.migrated:
            return datetime.datetime(2021,11,30).date()

        if self.application_fees.count() < 1:
            return None
        elif self.application_fees.count() == 1:
            application_fee = self.application_fees.first()
            if application_fee.fee_constructor:
                return application_fee.fee_constructor.end_date
            else:
                return None
        else:
            logger.error('Proposal: {} has {} ApplicationFees.  There should be 0 or 1.'.format(self, self.application_fees.count()))
            raise ValidationError('Proposal: {} has {} ApplicationFees.  There should be 0 or 1.'.format(self, self.application_fees.count()))

    @property
    def editable_vessel_details(self):
        editable = True
        #if self.vessel_details:
        #    if self.vessel_details.status == 'draft' and (
        #            self.vessel_details.blocking_proposal != self or
        #            not self.vessel_details.blocking_proposal):
        #        editable = False
        return editable

    @property
    def fee_paid(self):
        if (self.invoice and self.invoice.payment_status in ['paid', 'over_paid']) or self.proposal_type==PROPOSAL_TYPE_AMENDMENT:
            return True
        return False

    @property
    def fee_amount(self):
        return self.invoice.amount if self.fee_paid else None

    @property
    def reversion_ids(self):
        current_revision_id = Version.objects.get_for_object(self).first().revision_id
        versions = Version.objects.get_for_object(self).select_related("revision__user").filter(Q(revision__comment__icontains='status') | Q(revision_id=current_revision_id))
        version_ids = [[i.id,i.revision.date_created] for i in versions]
        return [dict(cur_version_id=version_ids[0][0], prev_version_id=version_ids[i+1][0], created=version_ids[i][1]) for i in range(len(version_ids)-1)]

    @property
    def applicant(self):
        if self.org_applicant:
            return self.org_applicant.organisation.name
        elif self.proxy_applicant:
            return "{} {}".format(
                self.proxy_applicant.first_name,
                self.proxy_applicant.last_name)
        else:
            return "{} {}".format(
                self.submitter.first_name,
                self.submitter.last_name)

    @property
    def applicant_email(self):
        if self.org_applicant and hasattr(self.org_applicant.organisation, 'email') and self.org_applicant.organisation.email:
            return self.org_applicant.organisation.email
        elif self.proxy_applicant:
            return self.proxy_applicant.email
        else:
            return self.submitter.email

    @property
    def applicant_details(self):
        if self.org_applicant:
            return '{} \n{}'.format(
                self.org_applicant.organisation.name,
                self.org_applicant.address)
        elif self.proxy_applicant:
            return "{} {}\n{}".format(
                self.proxy_applicant.first_name,
                self.proxy_applicant.last_name,
                self.proxy_applicant.addresses.all().first())
        else:
            return "{} {}\n{}".format(
                self.submitter.first_name,
                self.submitter.last_name,
                self.submitter.addresses.all().first())

    @property
    def applicant_address(self):
        if self.org_applicant:
            return self.org_applicant.address
        elif self.proxy_applicant:
            #return self.proxy_applicant.addresses.all().first()
            return self.proxy_applicant.residential_address
        else:
            #return self.submitter.addresses.all().first()
            return self.submitter.residential_address

    @property
    def applicant_id(self):
        if self.org_applicant:
            return self.org_applicant.id
        elif self.proxy_applicant:
            return self.proxy_applicant.id
        else:
            return self.submitter.id

    @property
    def applicant_type(self):
        if self.org_applicant:
            return self.APPLICANT_TYPE_ORGANISATION
        elif self.proxy_applicant:
            return self.APPLICANT_TYPE_PROXY
        else:
            return self.APPLICANT_TYPE_SUBMITTER

    @property
    def applicant_field(self):
        if self.org_applicant:
            return 'org_applicant'
        elif self.proxy_applicant:
            return 'proxy_applicant'
        else:
            return 'submitter'

    @property
    def get_history(self):
        """ Return the prev proposal versions """
        l = []
        p = copy.deepcopy(self)
        while (p.previous_application):
            l.append( dict(id=p.previous_application.id, modified=p.previous_application.modified_date) )
            p = p.previous_application
        return l

    @property
    def is_assigned(self):
        return self.assigned_officer is not None

    @property
    def can_user_edit(self):
        """
        :return: True if the application is in one of the editable status.
        """
        return self.customer_status in self.CUSTOMER_EDITABLE_STATE

    @property
    def can_user_view(self):
        """
        :return: True if the application is in one of the approved status.
        """
        return self.customer_status in self.CUSTOMER_VIEWABLE_STATE

    @property
    def assessor_assessment(self):
        # qs=self.assessment.filter(referral_assessment=False, referral_group=None)
        qs = self.assessment.all()  # <== Is this correct???
        if qs:
            return qs[0]
        else:
            return None

    @property
    def permit(self):
        return self.approval.licence_document._file.url if self.approval else None

    @property
    def allowed_assessors(self):
        # TODO: check this logic
        if self.processing_status == 'with_approver':
            #group = self.__approver_group()
            group = self.__approver_group()
        else:
            group = self.__assessor_group()
            #group = self.__assessor_group()
        return group.user_set.all() if group else []

    def allowed_assessors_user(self, request):
        if self.processing_status == 'with_approver':
            group = self.__approver_group()
        else:
            group = self.__assessor_group()
        return True if group and group.user_set.filter(id=request.user.id).values_list('id', flat=True) else False

    #@property
    #def compliance_assessors(self):
    #    group = self.__assessor_group()
    #    return group.members.all() if group else []

    @property
    def can_officer_process(self):
        """ :return: True if the application is in one of the processable status for Assessor role."""
        officer_view_state = [
            Proposal.PROCESSING_STATUS_DRAFT,
            Proposal.PROCESSING_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_DECLINED,
            # Proposal.PROCESSING_STATUS_TEMP,
            Proposal.PROCESSING_STATUS_DISCARDED,
            # 'with_referral',
            # 'with_qa_officer',
            Proposal.PROCESSING_STATUS_AWAITING_PAYMENT,
            # 'partially_approved',
            # 'partially_declined',
            # 'with_district_assessor',
            Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT,
            Proposal.PROCESSING_STATUS_AWAITING_DOCUMENTS,
            Proposal.PROCESSING_STATUS_PRINTING_STICKER,
        ]
        return False if self.processing_status in officer_view_state else True

    @property
    def amendment_requests(self):
        qs =AmendmentRequest.objects.filter(proposal=self)
        return qs

    #Check if there is an pending amendment request exist for the proposal
    @property
    def pending_amendment_request(self):
        qs =AmendmentRequest.objects.filter(proposal = self, status = "requested")
        if qs:
            return True
        return False

    @property
    def is_amendment_proposal(self):
        if self.proposal_type==PROPOSAL_TYPE_AMENDMENT:
            return True
        return False

    def __assessor_group(self):
        return self.child_obj.assessor_group
        #return ProposalAssessorGroup.objects.first()

    def __approver_group(self):
        return self.child_obj.approver_group
        #return ProposalApproverGroup.objects.first()

    def __check_proposal_filled_out(self):
        if not self.data:
            raise exceptions.ProposalNotComplete()
        missing_fields = []
        required_fields = {
        }
        for k,v in required_fields.items():
            val = getattr(self,k)
            if not val:
                missing_fields.append(v)
        return missing_fields

    @property
    def assessor_recipients(self):
        return self.child_obj.assessor_recipients
        #recipients = ProposalAssessorGroup.objects.first().members_email  # We expect there is only one assessor group
        #return recipients


    @property
    def approver_recipients(self):
        return self.child_obj.approver_recipients
        #recipients = ProposalApproverGroup.objects.first().members_email  # We expect there is only one assessor group
        #return recipients
    #    recipients = []
    #    try:
    #        recipients = ProposalApproverGroup.objects.get(region=self.region).members_email
    #    except:
    #        recipients = ProposalApproverGroup.objects.get(default=True).members_email
    #    return recipients

    #Check if the user is member of assessor group for the Proposal
    def is_assessor(self, user):
        return self.child_obj.is_assessor(user)
        #return self.__assessor_group() in user.proposalassessorgroup_set.all()
        #return

    #Check if the user is member of assessor group for the Proposal
    def is_approver(self, user):
        return self.child_obj.is_approver(user)
        #return self.__approver_group() in user.proposalapprovergroup_set.all()

    def can_assess(self, user):
        #if self.processing_status == 'on_hold' or self.processing_status == 'with_assessor' or self.processing_status == 'with_referral' or self.processing_status == 'with_assessor_requirements':
        # if self.processing_status in ['on_hold', 'with_qa_officer', 'with_assessor', 'with_referral', 'with_assessor_requirements']:
        if self.processing_status in [Proposal.PROCESSING_STATUS_WITH_ASSESSOR, Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS]:
            #return self.__assessor_group() in user.proposalassessorgroup_set.all()
            return self.child_obj.is_assessor(user)
        elif self.processing_status in [Proposal.PROCESSING_STATUS_WITH_APPROVER, Proposal.PROCESSING_STATUS_AWAITING_PAYMENT, Proposal.PROCESSING_STATUS_PRINTING_STICKER]:
            #return self.__approver_group() in user.proposalapprovergroup_set.all()
            return self.child_obj.is_approver(user)
        else:
            return False

    #def assessor_comments_view(self, user):
    #    if self.processing_status == 'with_assessor' or self.processing_status == 'with_referral' or self.processing_status == 'with_assessor_requirements' or self.processing_status == 'with_approver':
    #        try:
    #            referral = Referral.objects.get(proposal=self,referral=user)
    #        except:
    #            referral = None
    #        if referral:
    #            return True
    #        elif self.__assessor_group() in user.proposalassessorgroup_set.all():
    #            return True
    #        elif self.__approver_group() in user.proposalapprovergroup_set.all():
    #            return True
    #        else:
    #            return False
    #    else:
    #        return False

    def has_assessor_mode(self,user):
        status_without_assessor = ['with_approver','approved','awaiting_payment','declined','draft']
        if self.processing_status in status_without_assessor:
            return False
        else:
            if self.assigned_officer:
                if self.assigned_officer == user:
                    return self.child_obj.is_assessor(user)
                    #return self.__assessor_group() in user.proposalassessorgroup_set.all()
                else:
                    return False
            else:
                #return self.__assessor_group() in user.proposalassessorgroup_set.all()
                return self.child_obj.is_assessor(user)

    #def log_user_action(self, action, request):
     #   return ProposalUserAction.log_action(self, action, request.user)

    def log_user_action(self, action, request=None):
        if request:
            return ProposalUserAction.log_action(self, action, request.user)
        else:
            return ProposalUserAction.log_action(self, action)

    @property
    def is_submitted(self):
        return True if self.lodgement_date else False

    def update(self,request,viewset):
        from mooringlicensing.components.proposals.utils import save_proponent_data
        with transaction.atomic():
            if self.can_user_edit:
                # Save the data first
                save_proponent_data(self,request,viewset)
                self.save()
            else:
                raise ValidationError('You can\'t edit this proposal at this moment')

    def assign_officer(self, request, officer):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if not self.can_assess(officer):
                    raise ValidationError('The selected person is not authorised to be assigned to this proposal')
                if self.processing_status == 'with_approver':
                    if officer != self.assigned_approver:
                        self.assigned_approver = officer
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_ASSIGN_TO_APPROVER.format(self.id,'{}({})'.format(officer.get_full_name(),officer.email)),request)
                        # Create a log entry for the organisation
                        applicant_field=getattr(self, self.applicant_field)
                        applicant_field.log_user_action(ProposalUserAction.ACTION_ASSIGN_TO_APPROVER.format(self.id,'{}({})'.format(officer.get_full_name(),officer.email)),request)
                else:
                    if officer != self.assigned_officer:
                        self.assigned_officer = officer
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_ASSIGN_TO_ASSESSOR.format(self.id,'{}({})'.format(officer.get_full_name(),officer.email)),request)
                        # Create a log entry for the organisation
                        applicant_field=getattr(self, self.applicant_field)
                        applicant_field.log_user_action(ProposalUserAction.ACTION_ASSIGN_TO_ASSESSOR.format(self.id,'{}({})'.format(officer.get_full_name(),officer.email)),request)
            except:
                raise

    def assing_approval_level_document(self, request):
        with transaction.atomic():
            try:
                approval_level_document = request.data['approval_level_document']
                if approval_level_document != 'null':
                    try:
                        document = self.documents.get(input_name=str(approval_level_document))
                    except ProposalDocument.DoesNotExist:
                        document = self.documents.get_or_create(input_name=str(approval_level_document), name=str(approval_level_document))[0]
                    document.name = str(approval_level_document)
                    # commenting out below tow lines - we want to retain all past attachments - reversion can use them
                    #if document._file and os.path.isfile(document._file.path):
                    #    os.remove(document._file.path)
                    document._file = approval_level_document
                    document.save()
                    d=ProposalDocument.objects.get(id=document.id)
                    self.approval_level_document = d
                    comment = 'Approval Level Document Added: {}'.format(document.name)
                else:
                    self.approval_level_document = None
                    comment = 'Approval Level Document Deleted: {}'.format(request.data['approval_level_document_name'])
                #self.save()
                self.save(version_comment=comment) # to allow revision to be added to reversion history
                self.log_user_action(ProposalUserAction.ACTION_APPROVAL_LEVEL_DOCUMENT.format(self.id),request)
                # Create a log entry for the organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_APPROVAL_LEVEL_DOCUMENT.format(self.id),request)
                return self
            except:
                raise

    def unassign(self,request):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status == 'with_approver':
                    if self.assigned_approver:
                        self.assigned_approver = None
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_UNASSIGN_APPROVER.format(self.id),request)
                        # Create a log entry for the organisation
                        applicant_field=getattr(self, self.applicant_field)
                        applicant_field.log_user_action(ProposalUserAction.ACTION_UNASSIGN_APPROVER.format(self.id),request)
                else:
                    if self.assigned_officer:
                        self.assigned_officer = None
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_UNASSIGN_ASSESSOR.format(self.id),request)
                        # Create a log entry for the organisation
                        applicant_field=getattr(self, self.applicant_field)
                        applicant_field.log_user_action(ProposalUserAction.ACTION_UNASSIGN_ASSESSOR.format(self.id),request)
            except:
                raise

    def add_default_requirements(self):
        # Add default standard requirements to Proposal
        due_date = None
        # if self.application_type.name == ApplicationType.TCLASS:
        #     due_date = self.other_details.nominated_start_date
        # elif self.application_type.name == ApplicationType.FILMING:
        #     due_date = self.filming_activity.commencement_date
        # elif self.application_type.name == ApplicationType.EVENT:
        #     due_date = self.event_activity.commencement_date
        default_requirements = ProposalStandardRequirement.objects.filter(application_type=self.application_type, default=True, obsolete=False)
        if default_requirements:
            for req in default_requirements:
                r, created = ProposalRequirement.objects.get_or_create(proposal=self, standard_requirement=req, due_date=due_date)

    def move_to_status(self, request, status, approver_comment):
        if not status:
            raise serializers.ValidationError('Status is required')
        if status not in [Proposal.PROCESSING_STATUS_WITH_ASSESSOR, Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS, Proposal.PROCESSING_STATUS_WITH_APPROVER]:
            raise serializers.ValidationError('The status provided is not allowed')
        if not self.can_assess(request.user):
            raise exceptions.ProposalNotAuthorized()
        # if self.processing_status == Proposal.PROCESSING_STATUS_WITH_REFERRAL or self.can_user_edit:
        #     raise ValidationError('You cannot change the current status at this time')

        if self.processing_status != status:
            if self.processing_status == Proposal.PROCESSING_STATUS_WITH_APPROVER:
                self.approver_comment = ''
                if approver_comment:
                    self.approver_comment = approver_comment
                    self.save()
                    send_proposal_approver_sendback_email_notification(request, self)
            self.processing_status = status
            self.save()
            if status == self.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS:
                self.add_default_requirements()

            # Create a log entry for the proposal
            if self.processing_status == self.PROCESSING_STATUS_WITH_ASSESSOR:
                self.log_user_action(ProposalUserAction.ACTION_BACK_TO_PROCESSING.format(self.id), request)
            elif self.processing_status == self.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS:
                self.log_user_action(ProposalUserAction.ACTION_ENTER_REQUIREMENTS.format(self.id), request)

    def reissue_approval(self,request,status):
        with transaction.atomic():
            if not self.processing_status=='approved' :
                raise ValidationError('You cannot change the current status at this time')
            elif self.approval and self.approval.can_reissue and self.is_approver(request.user):
                self.processing_status = status
                self.proposed_issuance_approval = {}
                self.save()
                self.approval.reissued=True
                self.approval.save()
                # Create a log entry for the proposal
                self.log_user_action(ProposalUserAction.ACTION_REISSUE_APPROVAL.format(self.lodgement_number), request)
                #self.approval.log_user_action(ApprovalUserAction.ACTION_REISSUE_APPROVAL.format(self.approval.lodgement_number), request)
                #else:
                    #raise ValidationError('Cannot reissue Approval')
            else:
                raise ValidationError('Cannot reissue Approval')

    def proposed_decline(self,request,details):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status != Proposal.PROCESSING_STATUS_WITH_ASSESSOR:
                    raise ValidationError('You cannot propose to decline if it is not with assessor')

                reason = details.get('reason', '')
                ProposalDeclinedDetails.objects.update_or_create(
                    proposal=self,
                    defaults={
                        'officer': request.user,
                        'reason': reason,
                        'cc_email': details.get('cc_email', None)
                    }
                )
                self.proposed_decline_status = True
                approver_comment = ''
                self.move_to_status(request, Proposal.PROCESSING_STATUS_WITH_APPROVER, approver_comment)
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_PROPOSED_DECLINE.format(self.id), request)
                # Log entry for organisation
                applicant_field = getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_PROPOSED_DECLINE.format(self.id), request)

                send_approver_approve_decline_email_notification(request, self)
            except:
                raise

    def final_decline(self, request, details):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()

                if self.application_type.code in (WaitingListApplication.code, AnnualAdmissionApplication.code):
                    if self.processing_status not in (Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS, Proposal.PROCESSING_STATUS_WITH_ASSESSOR):
                        # For WLA or AAA, assessor can final decline
                        raise ValidationError('You cannot decline if it is not with approver')
                else:
                    if self.processing_status != Proposal.PROCESSING_STATUS_WITH_APPROVER:
                        # For AuA or MLA, approver can final decline
                        raise ValidationError('You cannot decline if it is not with approver')

                proposal_decline, success = ProposalDeclinedDetails.objects.update_or_create(
                    proposal=self,
                    defaults={
                        'officer': request.user,
                        'reason': details.get('reason', ''),
                        'cc_email': details.get('cc_email',None)
                    }
                )
                self.proposed_decline_status = True
                self.processing_status = Proposal.PROCESSING_STATUS_DECLINED
                self.customer_status = Proposal.CUSTOMER_STATUS_DECLINED
                self.save()
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_DECLINE.format(self.id),request)
                # Log entry for organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_DECLINE.format(self.id),request)
                # update WLA internal_status
                ## ML
                #from mooringlicensing.components.approvals.models import MooringLicence
                if type(self.child_obj) == MooringLicenceApplication and self.waiting_list_allocation:
                    self.waiting_list_allocation.internal_status = 'waiting'
                    current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
                    self.waiting_list_allocation.wla_queue_date = current_datetime
                    self.waiting_list_allocation.save()
                    self.waiting_list_allocation.set_wla_order()
                #if self.application_type.code == MooringLicence.code and self.waiting_list_allocation:
                #    self.waiting_list_allocation.internal_status = 'waiting'
                #    self.waiting_list_allocation.save()
                # send_proposal_decline_email_notification(self,request, proposal_decline)
                send_application_approved_or_declined_email(self, 'declined', request)
            except:
                raise

    def on_hold(self,request):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if not (self.processing_status == 'with_assessor' or self.processing_status == 'with_referral'):
                    raise ValidationError('You cannot put on hold if it is not with assessor or with referral')

                self.prev_processing_status = self.processing_status
                self.processing_status = self.PROCESSING_STATUS_ONHOLD
                self.save()
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_PUT_ONHOLD.format(self.id),request)
                # Log entry for organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_PUT_ONHOLD.format(self.id),request)

                #send_approver_decline_email_notification(reason, request, self)
            except:
                raise

    def on_hold_remove(self,request):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status != 'on_hold':
                    raise ValidationError('You cannot remove on hold if it is not currently on hold')

                self.processing_status = self.prev_processing_status
                self.prev_processing_status = self.PROCESSING_STATUS_ONHOLD
                self.save()
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_REMOVE_ONHOLD.format(self.id),request)
                # Log entry for organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_REMOVE_ONHOLD.format(self.id),request)

                #send_approver_decline_email_notification(reason, request, self)
            except:
                raise

    # def proposed_approval(self,request,details):
    #     with transaction.atomic():
    #         try:
    #             if not self.can_assess(request.user):
    #                 raise exceptions.ProposalNotAuthorized()
    #             if self.processing_status != 'with_assessor_requirements':
    #                 raise ValidationError('You cannot propose for approval if it is not with assessor for requirements')
    #             self.proposed_issuance_approval = {
    #                 'start_date' : details.get('start_date').strftime('%d/%m/%Y'),
    #                 'expiry_date' : details.get('expiry_date').strftime('%d/%m/%Y'),
    #                 'details': details.get('details'),
    #                 'cc_email':details.get('cc_email')
    #             }
    #             self.proposed_decline_status = False
    #             approver_comment = ''
    #             self.move_to_status(request,'with_approver', approver_comment)
    #             self.assigned_officer = None
    #             self.save()
    #             # Log proposal action
    #             self.log_user_action(ProposalUserAction.ACTION_PROPOSED_APPROVAL.format(self.id),request)
    #             # Log entry for organisation
    #             applicant_field=getattr(self, self.applicant_field)
    #             applicant_field.log_user_action(ProposalUserAction.ACTION_PROPOSED_APPROVAL.format(self.id),request)
    #
    #             send_approver_approve_email_notification(request, self)
    #         except:
    #             raise

    def proposed_approval(self, request, details):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status != Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS:
                    raise ValidationError('You cannot propose for approval if it is not with assessor for requirements')

                current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
                current_date = current_datetime.date()

                ria_mooring_name = ''
                mooring_id = details.get('mooring_id')
                if mooring_id:
                    ria_mooring_name = Mooring.objects.get(id=mooring_id).name
                self.proposed_issuance_approval = {
                    'current_date': current_date.strftime('%d/%m/%Y'),  # start_date and expiry_date are determined when making payment or approved???
                    # 'start_date': current_date.strftime('%d/%m/%Y'),
                    # 'expiry_date': self.end_date.strftime('%d/%m/%Y'),
                    ## mooring_bay_id and mooring_id req for AUA
                    'mooring_bay_id': details.get('mooring_bay_id'),
                    'mooring_id': mooring_id,
                    'ria_mooring_name': ria_mooring_name,
                    'details': details.get('details'),
                    'cc_email': details.get('cc_email'),
                    'mooring_on_approval': details.get('mooring_on_approval'),
                    'vessel_ownership': details.get('vessel_ownership'),
                }
                self.proposed_decline_status = False
                approver_comment = ''
                self.move_to_status(request, Proposal.PROCESSING_STATUS_WITH_APPROVER, approver_comment)
                self.assigned_officer = None
                self.save()
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_PROPOSED_APPROVAL.format(self.id), request)
                # Log entry for organisation
                applicant_field = getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_PROPOSED_APPROVAL.format(self.id), request)

                send_approver_approve_decline_email_notification(request, self)
                return self

            except:
                raise

    def preview_approval(self,request,details):
        from mooringlicensing.components.approvals.models import PreviewTempApproval
        with transaction.atomic():
            try:
                if self.processing_status != 'with_approver':
                    raise ValidationError('Licence preview only available when processing status is with_approver. Current status {}'.format(self.processing_status))
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                #if not self.applicant.organisation.postal_address:
                if not self.applicant_address:
                    raise ValidationError('The applicant needs to have set their postal address before approving this proposal.')

                lodgement_number = self.previous_application.approval.lodgement_number if self.proposal_type in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT] else None # renewals/amendments keep same licence number
                preview_approval = PreviewTempApproval.objects.create(
                    current_proposal = self,
                    issue_date = timezone.now(),
                    expiry_date = datetime.datetime.strptime(details.get('due_date'), '%d/%m/%Y').date(),
                    start_date = datetime.datetime.strptime(details.get('start_date'), '%d/%m/%Y').date(),
                    submitter = self.submitter,
                    #org_applicant = self.applicant if isinstance(self.applicant, Organisation) else None,
                    #proxy_applicant = self.applicant if isinstance(self.applicant, EmailUser) else None,
                    org_applicant = self.org_applicant,
                    proxy_applicant = self.proxy_applicant,
                    lodgement_number = lodgement_number
                )

                # Generate the preview document - get the value of the BytesIO buffer
                licence_buffer = preview_approval.generate_doc(request.user, preview=True)

                # clean temp preview licence object
                transaction.set_rollback(True)

                return licence_buffer
            except:
                raise

    def final_approval_for_WLA_AAA(self, request, details=None, auto_approve=False):
        with transaction.atomic():
            try:
                current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
                self.proposed_decline_status = False

                # Validation & update proposed_issuance_approval
                if (self.processing_status == Proposal.PROCESSING_STATUS_AWAITING_PAYMENT and self.fee_paid) or self.proposal_type == PROPOSAL_TYPE_AMENDMENT:
                    # for 'Awaiting Payment' approval. External/Internal user fires this method after full payment via Make/Record Payment
                    pass
                else:
                    if not auto_approve and not self.can_assess(request.user):
                        raise exceptions.ProposalNotAuthorized()
                    if not auto_approve and self.processing_status not in (Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS, Proposal.PROCESSING_STATUS_WITH_ASSESSOR):
                        raise ValidationError('You cannot issue the approval if it is not with an assessor')
                    if not self.applicant_address:
                        raise ValidationError('The applicant needs to have set their postal address before approving this proposal.')

                    if self.application_fees.count() < 1 and not self.migrated:
                        raise ValidationError('Payment record not found for the Annual Admission Application: {}'.format(self))
                    elif self.application_fees.count() > 1:
                        raise ValidationError('More than 1 payment records found for the Annual Admission Application: {}'.format(self))

                    if details:
                        # When auto_approve, there are no 'details' because details are created from the modal when assessment
                        self.proposed_issuance_approval = {
                            #'start_date': current_date.strftime('%d/%m/%Y'),
                            #'expiry_date': self.end_date.strftime('%d/%m/%Y'),
                            'details': details.get('details'),
                            'cc_email': details.get('cc_email'),
                        }
                    else:
                        self.proposed_issuance_approval = {}
                self.save()

                # Create/update approval
                created = None
                if self.proposal_type in (ProposalType.objects.filter(code__in=(PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT))):
                    approval = self.approval.child_obj
                    approval.current_proposal=self
                    if type(self.child_obj) == WaitingListApplication:
                        approval.wla_queue_date = current_datetime
                    approval.issue_date = current_datetime
                    approval.start_date = current_datetime.date()
                    approval.expiry_date = self.end_date
                    approval.submitter = self.submitter
                    approval.save()
                else:
                    approval, created = self.approval_class.objects.update_or_create(
                    #approval, created = cls.objects.update_or_create(
                        current_proposal=self,
                        defaults={
                            'issue_date': current_datetime,
                            #'wla_queue_date': current_datetime,
                            'start_date': current_datetime.date(),
                            'expiry_date': self.end_date,
                            'submitter': self.submitter,
                            #'internal_status': 'waiting',
                        }
                    )
                    if type(self.child_obj) == WaitingListApplication:
                        approval.wla_queue_date = current_datetime
                        approval.internal_status = 'waiting'
                        approval.save()
                    # if created:
                    #     approval.fee_period = self.fee_period  # It's better to
                    #     approval.save()
                self.approval = approval
                self.save()

                # always reset this flag
                approval.renewal_sent = False
                if type(self.child_obj) == AnnualAdmissionApplication:
                    approval.export_to_mooring_booking = True
                approval.save()

                # Generate compliances
                from mooringlicensing.components.compliances.models import Compliance, ComplianceUserAction
                #if created:
                    #if self.proposal_type == PROPOSAL_TYPE_AMENDMENT:
                if self.previous_application:
                    approval_compliances = Compliance.objects.filter(approval=self.approval,
                                                                     proposal=self.previous_application,
                                                                     processing_status='future')
                    if approval_compliances:
                        for c in approval_compliances:
                            c.delete()
                    # Log creation
                    # Generate the document
                    # approval.generate_doc(request.user)
                    self.generate_compliances(approval, request)
                    # send the doc and log in approval and org
                else:
                    # Generate the document
                    # approval.generate_doc(request.user)
                    # Delete the future compliances if Approval is reissued and generate the compliances again.
                    approval_compliances = Compliance.objects.filter(approval=approval, proposal=self,
                                                                     processing_status='future')
                    if approval_compliances:
                        for c in approval_compliances:
                            c.delete()
                    # Log proposal action
                    self.log_user_action(ProposalUserAction.ACTION_UPDATE_APPROVAL_.format(self.id), request)
                    # Log entry for organisation
                    applicant_field = getattr(self, self.applicant_field)
                    applicant_field.log_user_action(ProposalUserAction.ACTION_UPDATE_APPROVAL_.format(self.id), request)

                # set proposal status to approved - can change later after manage_stickers
                self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                self.customer_status = Proposal.CUSTOMER_STATUS_APPROVED
                self.save()

                # Update stickers
                moas_to_be_reallocated, stickers_to_be_returned = self.approval.manage_stickers(self)

                ## set proposal status after manage_stickers
                from mooringlicensing.components.approvals.models import Sticker
                #awaiting_payment = False
                awaiting_printing = False

                #for application_fee in self.application_fees.all():
                 #   if application_fee.unpaid:
                  #      awaiting_payment = True

                if self.approval:
                    stickers = self.approval.stickers.filter(status__in=(Sticker.STICKER_STATUS_READY, Sticker.STICKER_STATUS_AWAITING_PRINTING))
                    if stickers.count() >0:
                        awaiting_printing = True

                #if awaiting_payment:
                 #   self.processing_status = Proposal.PROCESSING_STATUS_AWAITING_PAYMENT
                  #  self.customer_status = Proposal.CUSTOMER_STATUS_AWAITING_PAYMENT
                if awaiting_printing:
                    self.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                    self.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
                    # Log proposal action
                    self.log_user_action(ProposalUserAction.ACTION_PRINTING_STICKER.format(self.id), request)
                else:
                    self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                    self.customer_status = Proposal.CUSTOMER_STATUS_APPROVED
                self.save()

                # write approval history
                approval.write_approval_history()
                # set wla order
                approval = approval.set_wla_order()

                # send Proposal approval email with attachment
                approval.generate_doc(request.user)
                send_application_approved_or_declined_email(self, 'approved', request, stickers_to_be_returned)
                self.save(version_comment='Final Approval: {}'.format(self.approval.lodgement_number))
                self.approval.documents.all().update(can_delete=False)

                # TODO: do we need to return anything?
                return self

            except:
                raise

    def final_approval_for_AUA_MLA(self, request=None, details=None):
        with transaction.atomic():
            try:
                self.proposed_decline_status = False
                current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
                current_date = current_datetime.date()

                # Validation & update proposed_issuance_approval
                if (self.processing_status == Proposal.PROCESSING_STATUS_AWAITING_PAYMENT and self.fee_paid) or self.proposal_type == PROPOSAL_TYPE_AMENDMENT:
                    # TODO: rework this
                    # for 'Awaiting Payment' approval. External/Internal user fires this method after full payment via Make/Record Payment
                    pass
                else:
                    if request and not self.can_assess(request.user):
                        raise exceptions.ProposalNotAuthorized()
                    if request and self.processing_status not in (Proposal.PROCESSING_STATUS_WITH_APPROVER,):
                        raise ValidationError('You cannot issue the approval if it is not with an assessor')
                    if not self.applicant_address:
                        raise ValidationError('The applicant needs to have set their postal address before approving this proposal.')

                # if no request, must be a system reissue - skip payment section
                if request:
                    ## update proposed_issuance_approval
                    ria_mooring_name = ''
                    mooring_id = details.get('mooring_id')
                    if mooring_id:
                        ria_mooring_name = Mooring.objects.get(id=mooring_id).name

                    self.proposed_issuance_approval = {
                        # 'start_date' : details.get('start_date').strftime('%d/%m/%Y'),
                        # 'expiry_date' : details.get('expiry_date').strftime('%d/%m/%Y'),
                        'mooring_bay_id': details.get('mooring_bay_id'),
                        'mooring_id': mooring_id,
                        'ria_mooring_name': ria_mooring_name,
                        'details': details.get('details'),
                        'cc_email': details.get('cc_email'),
                        'mooring_on_approval': details.get('mooring_on_approval'),
                        'vessel_ownership': details.get('vessel_ownership'),
                    }
                    self.save()

                    ## prepare invoice
                    from mooringlicensing.components.payments_ml.utils import create_fee_lines, make_serializable
                    from mooringlicensing.components.payments_ml.models import FeeConstructor, ApplicationFee

                    # create fee lines tells us whether a payment is required
                    line_items, fee_items_to_store = self.child_obj.create_fee_lines()  # Accessed by AU and ML

                    total_amount = sum(line_item['price_incl_tax'] for line_item in line_items)

                    if total_amount == 0:
                        # Call a function where mooringonapprovals and stickers are handled, because when total_amount == 0,
                        # Ledger skips the payment step, which calling the function below
                        approval, created = self.child_obj.update_or_create_approval(datetime.datetime.now(pytz.timezone(TIME_ZONE)), request=request)
                    else:
                        # proposal type must be awaiting payment
                        self.processing_status = Proposal.PROCESSING_STATUS_AWAITING_PAYMENT
                        self.customer_status = Proposal.CUSTOMER_STATUS_AWAITING_PAYMENT
                        self.save()

                        from mooringlicensing.components.payments_ml.models import FeeItem
                        from mooringlicensing.components.payments_ml.models import FeeItemApplicationFee

                        try:
                            logger.info('Creating invoice for the application: {}'.format(self))

                            basket = createCustomBasket(line_items, self.submitter, PAYMENT_SYSTEM_ID)
                            order = CreateInvoiceBasket(payment_method='other', system=PAYMENT_SYSTEM_PREFIX).create_invoice_and_order(
                                basket, 0, None, None, user=self.submitter, invoice_text='Payment Invoice')
                            invoice = Invoice.objects.get(order_number=order.number)
                            application_fee = ApplicationFee.objects.create(
                                proposal=self,
                                invoice_reference=invoice.reference,
                                payment_type=ApplicationFee.PAYMENT_TYPE_TEMPORARY,
                            )

                            # Link between ApplicationFee and FeeItem(s)
                            for item in fee_items_to_store:
                                FeeItemApplicationFee.objects.create(
                                        fee_item=item['fee_item'],
                                        application_fee=application_fee,
                                        vessel_details=item['vessel_details'],
                                    )

                            send_application_approved_or_declined_email(self, 'approved', request)

                        except Exception as e:
                            err_msg = 'Failed to create invoice'
                            logger.error('{}\n{}'.format(err_msg, str(e)))
                else:
                    # system reissue
                    approval, created = self.child_obj.update_or_create_approval(datetime.datetime.now(pytz.timezone(TIME_ZONE)))

                return self

            except:
                raise

    #def send_emails_for_payment_required(self, request, invoice):
    #    attachments = []
    #    if invoice:
    #        invoice_bytes = create_invoice_pdf_bytes('invoice.pdf', self.invoice,)
    #        attachment = ('invoice#{}.pdf'.format(self.invoice.reference), invoice_bytes, 'application/pdf')
    #        attachments.append(attachment)
    #    # ret_value = send_emails_for_payment_required(request, self, attachments)
    #    ret_value = send_application_processed_email(self, 'approved', request)
    #    return ret_value

    def final_approval(self, request=None, details=None):
        if self.child_obj.code in (WaitingListApplication.code, AnnualAdmissionApplication.code):
            self.final_approval_for_WLA_AAA(request, details)
        elif self.child_obj.code in (AuthorisedUserApplication.code, MooringLicenceApplication.code):
            return self.final_approval_for_AUA_MLA(request, details)

    def generate_compliances(self,approval, request):
        today = timezone.now().date()
        timedelta = datetime.timedelta
        from mooringlicensing.components.compliances.models import Compliance, ComplianceUserAction
        #For amendment type of Proposal, check for copied requirements from previous proposal
        #if self.proposal_type == PROPOSAL_TYPE_AMENDMENT:
        if self.previous_application:
            try:
                for r in self.requirements.filter(copied_from__isnull=False):
                    cs=[]
                    cs=Compliance.objects.filter(requirement=r.copied_from, proposal=self.previous_application, processing_status='due')
                    if cs:
                        if r.is_deleted == True:
                            for c in cs:
                                c.processing_status='discarded'
                                c.customer_status = 'discarded'
                                c.reminder_sent=True
                                c.post_reminder_sent=True
                                c.save()
                        if r.is_deleted == False:
                            for c in cs:
                                c.proposal= self
                                c.approval=approval
                                c.requirement=r
                                c.save()
            except:
                raise
        #requirement_set= self.requirements.filter(copied_from__isnull=True).exclude(is_deleted=True)
        requirement_set= self.requirements.all().exclude(is_deleted=True)

        #for req in self.requirements.all():
        for req in requirement_set:
            try:
                if req.due_date and req.due_date >= today:
                    current_date = req.due_date
                    #create a first Compliance
                    try:
                        compliance= Compliance.objects.get(requirement = req, due_date = current_date)
                    except Compliance.DoesNotExist:
                        compliance =Compliance.objects.create(
                                    proposal=self,
                                    due_date=current_date,
                                    processing_status='future',
                                    approval=approval,
                                    requirement=req,
                        )
                        compliance.log_user_action(ComplianceUserAction.ACTION_CREATE.format(compliance.id),request)
                    if req.recurrence:
                        while current_date < approval.expiry_date:
                            for x in range(req.recurrence_schedule):
                            #Weekly
                                if req.recurrence_pattern == 1:
                                    current_date += timedelta(weeks=1)
                            #Monthly
                                elif req.recurrence_pattern == 2:
                                    current_date += timedelta(weeks=4)
                                    pass
                            #Yearly
                                elif req.recurrence_pattern == 3:
                                    current_date += timedelta(days=365)
                            # Create the compliance
                            if current_date <= approval.expiry_date:
                                try:
                                    compliance= Compliance.objects.get(requirement = req, due_date = current_date)
                                except Compliance.DoesNotExist:
                                    compliance =Compliance.objects.create(
                                                proposal=self,
                                                due_date=current_date,
                                                processing_status='future',
                                                approval=approval,
                                                requirement=req,
                                    )
                                    compliance.log_user_action(ComplianceUserAction.ACTION_CREATE.format(compliance.id),request)
            except:
                raise

    def renew_approval(self,request):
        with transaction.atomic():
            previous_proposal = self
            try:
                # TODO: check this logic
                #proposal_qs = Proposal.objects.filter(previous_application = previous_proposal)
                #if proposal_qs and proposal_qs[0].customer_status=='with_assessor':
                #    raise ValidationError('A renewal for this licence has already been lodged and is awaiting review.')
            #except Proposal.DoesNotExist:
                proposal = clone_proposal_with_status_reset(self)
                proposal.proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_RENEWAL)
                proposal.submitter = request.user
                proposal.previous_application = self
                proposal.proposed_issuance_approval= None

                req=self.requirements.all().exclude(is_deleted=True)
                from copy import deepcopy
                if req:
                    for r in req:
                        old_r = deepcopy(r)
                        r.proposal = proposal
                        r.copied_from=None
                        r.copied_for_renewal=True
                        if r.due_date:
                            r.due_date=None
                            r.require_due_date=True
                        r.id = None
                        r.district_proposal=None
                        r.save()
                # Create a log entry for the proposal
                self.log_user_action(ProposalUserAction.ACTION_RENEW_PROPOSAL.format(self.id),request)
                # Create a log entry for the organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_RENEW_PROPOSAL.format(self.id),request)
                #Log entry for approval
                from mooringlicensing.components.approvals.models import ApprovalUserAction
                self.approval.log_user_action(ApprovalUserAction.ACTION_RENEW_APPROVAL.format(self.approval.id),request)
                proposal.save(version_comment='New Amendment/Renewal Application created, from origin {}'.format(proposal.previous_application_id))
                return proposal
            except Exception as e:
                raise e

    def amend_approval(self,request):
        with transaction.atomic():
            previous_proposal = self
            try:
                # TODO: check this logic
                #amend_conditions = {
                #'previous_application': previous_proposal,
                #'proposal_type': ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT)
                #}
                #existing_proposal_qs=Proposal.objects.filter(**amend_conditions)
                #if existing_proposal_qs and existing_proposal_qs[0].customer_status=='under_review':
                #    raise ValidationError('An amendment for this licence has already been lodged and is awaiting review.')
            #except Proposal.DoesNotExist:
                proposal = clone_proposal_with_status_reset(self)
                proposal.proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT)
                #proposal.training_completed = True
                proposal.submitter = request.user
                proposal.previous_application = self
                req=self.requirements.all().exclude(is_deleted=True)
                from copy import deepcopy
                if req:
                    for r in req:
                        old_r = deepcopy(r)
                        r.proposal = proposal
                        r.copied_from=old_r
                        r.id = None
                        r.district_proposal=None
                        r.save()
                # Create a log entry for the proposal
                self.log_user_action(ProposalUserAction.ACTION_AMEND_PROPOSAL.format(self.id),request)
                # Create a log entry for the organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_AMEND_PROPOSAL.format(self.id),request)
                #Log entry for approval
                from mooringlicensing.components.approvals.models import ApprovalUserAction
                self.approval.log_user_action(ApprovalUserAction.ACTION_AMEND_APPROVAL.format(self.approval.id),request)
                proposal.save(version_comment='New Amendment/Renewal Application created, from origin {}'.format(proposal.previous_application_id))
                return proposal
            except Exception as e:
                raise e

    @property
    def application_type(self):
        application_type = ApplicationType.objects.get(code=self.application_type_code)
        return application_type

    # tmp property required to fix dev data
    @property
    def no_child_obj(self):
        no_child_obj = True
        if hasattr(self, 'waitinglistapplication'):
            no_child_obj = False
        elif hasattr(self, 'annualadmissionapplication'):
            no_child_obj = False
        elif hasattr(self, 'authoriseduserapplication'):
            no_child_obj = False
        elif hasattr(self, 'mooringlicenceapplication'):
            no_child_obj = False
        return no_child_obj

    @property
    def child_obj(self):
        if hasattr(self, 'waitinglistapplication'):
            return self.waitinglistapplication
        elif hasattr(self, 'annualadmissionapplication'):
            return self.annualadmissionapplication
        elif hasattr(self, 'authoriseduserapplication'):
            return self.authoriseduserapplication
        elif hasattr(self, 'mooringlicenceapplication'):
            return self.mooringlicenceapplication
        else:
            raise ObjectDoesNotExist("Proposal must have an associated child object - WLA, AA, AU or ML")

    @property
    def previous_application_notnull_vessel(self):
        prev_application = self.previous_application
        while prev_application and not prev_application.vessel_details:
            prev_application = prev_application.previous_application
        return prev_application

    @property
    def previous_application_status_filter(self):
        prev_application = self.previous_application
        while prev_application and prev_application.processing_status in ['discarded', 'declined'] and prev_application.previous_application:
            prev_application = prev_application.previous_application
        return prev_application

    @property
    def approval_class(self):
        from mooringlicensing.components.approvals.models import WaitingListAllocation, AnnualAdmissionPermit, AuthorisedUserPermit, MooringLicence
        if hasattr(self, 'waitinglistapplication'):
            return WaitingListAllocation
        elif hasattr(self, 'annualadmissionapplication'):
            return AnnualAdmissionPermit
        elif hasattr(self, 'authoriseduserapplication'):
            return AuthorisedUserPermit
        elif hasattr(self, 'mooringlicenceapplication'):
            return MooringLicence
        else:
            raise ObjectDoesNotExist("Proposal must have an associated child object - WLA, AA, AU or ML")

    # def update_or_create_approval(self, target_datetime=datetime.datetime.now(pytz.timezone(TIME_ZONE)), request=None):
    #     approval, created = self.child_obj.update_or_create_approval(target_datetime, request)
    #     self.refresh_from_db()
    #     return approval, created

    # def process_after_approval(self, request=None, total_amount=None):
    #     if hasattr(self.child_obj, 'processes_after_approval'):
    #         self.child_obj.processes_after_approval(request, total_amount)
    #         self.refresh_from_db()  # Somehow this is needed...

    # def get_fee_amount_adjusted(self, fee_item, vessel_length):
    #     return self.child_obj.get_fee_amount_adjusted(fee_item, vessel_length)

    @property
    def application_type_code(self):
        if type(self) == Proposal:
            return self.child_obj.code
        else:
            return self.code

    @property
    def description(self):
        #if hasattr(self, 'child_obj'):
        #if type(self) == Proposal:
        return self.child_obj.description
        #return ''

    @classmethod
    def application_type_descriptions(cls):
        type_list = []
        for application_type in Proposal.__subclasses__():
            type_list.append(application_type.description)
        return type_list

    @classmethod
    def application_types_dict(cls, apply_page):
        type_list = []
        for application_type in Proposal.__subclasses__():
            if apply_page:
                if application_type.apply_page_visibility:
                    type_list.append({
                        "code": application_type.code,
                        "description": application_type.description,
                        "new_application_text": application_type.new_application_text
                        })
            else:
                type_list.append({
                    "code": application_type.code,
                    "description": application_type.description,
                    "new_application_text": application_type.new_application_text
                })

        return type_list

    def get_target_date(self, applied_date):
        if self.proposal_type.code == settings.PROPOSAL_TYPE_AMENDMENT:
            if applied_date < self.approval.latest_applied_season.start_date:
                # This amendment application is being applied after the renewal but before the new season starts
                # Set the target date used for calculation to the 1st date of the latest season applied
                target_date = self.approval.latest_applied_season.start_date
            elif self.approval.latest_applied_season.start_date <= applied_date <= self.approval.latest_applied_season.end_date:
                # This amendment application is being applied during the latest season applied to the approval
                # This is the most likely case
                target_date = applied_date
            else:
                msg = 'Approval: {} cannot be amended before renewal'.format(self.approval)
                logger.error(msg)
                raise Exception(msg)
        elif self.proposal_type.code == settings.PROPOSAL_TYPE_RENEWAL:
            if applied_date < self.approval.latest_applied_season.start_date:  # This should be same as self.approval.expiry_date
                # This renewal is being applied before the latest season starts
                msg = 'Approval: {} has been probably renewed, already'.format(self.approval)
                logger.error(msg)
                raise Exception(msg)
            elif self.approval.latest_applied_season.start_date <= applied_date <= self.approval.latest_applied_season.end_date:
                # This renewal application is being applied before the licence expiry
                # This is the most likely case
                # Set the target_date to the 1st day of the next season
                target_date = self.approval.latest_applied_season.end_date + datetime.timedelta(days=1)
            else:
                # Renewal application is being applied after the approval expiry date... Not sure if this is allowed.
                target_date = applied_date
        elif self.proposal_type.code == settings.PROPOSAL_TYPE_NEW:
            target_date = applied_date
        else:
            raise ValueError('Unknown proposal type of the proposal: {}'.format(self))

        return target_date

    def auto_approve(self, request):
        ## If renewal and no change to vessel
        #if self.proposal_type == ProposalType.objects.get(code=PROPOSAL_TYPE_RENEWAL):
        if self.proposal_type in ProposalType.objects.filter(code__in=[PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT]):
            auto_approve = True
            #auto_approve = False
            ## current and previous application both do not have a vessel
            if not self.vessel_details and not self.previous_application_status_filter.vessel_details:
                #auto_approve = True
                pass
            ## either current or previous application does not have a vessel
            elif not self.vessel_details or not self.previous_application_status_filter.vessel_details:
                auto_approve = False
                #pass
            #elif self.previous_application_status_filter and (
            ## compare current vessel data to previous application's vessel data
            elif (
                    # Vessel Details and rego
                    self.vessel_details.vessel != self.previous_application_status_filter.vessel_details.vessel or
                    self.vessel_details.vessel_type != self.previous_application_status_filter.vessel_details.vessel_type or
                    #self.vessel_details.vessel_overall_length != self.previous_application_status_filter.vessel_details.vessel_overall_length or
                    self.vessel_details.vessel_length != self.previous_application_status_filter.vessel_details.vessel_length or
                    self.vessel_details.vessel_draft != self.previous_application_status_filter.vessel_details.vessel_draft or
                    self.vessel_details.vessel_beam != self.previous_application_status_filter.vessel_details.vessel_beam or
                    self.vessel_details.vessel_weight != self.previous_application_status_filter.vessel_details.vessel_weight or
                    # Vessel Ownership
                    self.percentage != self.previous_application_status_filter.percentage or
                    self.individual_owner != self.previous_application_status_filter.individual_owner or
                    self.company_ownership_percentage != self.previous_application_status_filter.company_ownership_percentage or
                    self.company_ownership_name != self.previous_application_status_filter.company_ownership_name
                    ):
                auto_approve = False
                #pass
            ## WLA
            if (type(self.child_obj) == WaitingListApplication and 
                    self.preferred_bay != self.previous_application_status_filter.preferred_bay
                    ):
                auto_approve = False

            if auto_approve:
                self.final_approval_for_WLA_AAA(request, details={}, auto_approve=auto_approve)


def update_sticker_doc_filename(instance, filename):
    return '{}/stickers/batch/{}'.format(settings.MEDIA_APP_DIR, filename)


def update_sticker_response_doc_filename(instance, filename):
    return '{}/stickers/response/{}'.format(settings.MEDIA_APP_DIR, filename)


class StickerPrintingContact(models.Model):
    TYPE_EMIAL_TO = 'to'
    TYPE_EMAIL_CC = 'cc'
    TYPE_EMAIL_BCC = 'bcc'
    TYPES = (
        (TYPE_EMIAL_TO, 'To'),
        (TYPE_EMAIL_CC, 'Cc'),
        (TYPE_EMAIL_BCC, 'Bcc'),
    )
    email = models.EmailField(blank=True, null=True)
    type = models.CharField(max_length=255, choices=TYPES, blank=False, null=False,)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return '{} ({})'.format(self.email, self.type)

    class Meta:
        app_label = 'mooringlicensing'


class StickerPrintingBatch(Document):
    _file = models.FileField(upload_to=update_sticker_doc_filename, max_length=512)
    emailed_datetime = models.DateTimeField(blank=True, null=True)  # Once emailed, this field has a value

    class Meta:
        app_label = 'mooringlicensing'


class StickerPrintingResponseEmail(models.Model):
    email_subject = models.CharField(max_length=255, blank=True, null=True)
    email_body = models.TextField(null=True, blank=True)
    email_date = models.CharField(max_length=255, blank=True, null=True)
    email_from = models.CharField(max_length=255, blank=True, null=True)
    email_message_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        app_label = 'mooringlicensing'


class StickerPrintingResponse(Document):
    _file = models.FileField(upload_to=update_sticker_response_doc_filename, max_length=512)
    sticker_printing_response_email = models.ForeignKey(StickerPrintingResponseEmail, blank=True, null=True)
    processed = models.BooleanField(default=False)  # Processed by a cron to update sticker details
    no_errors_when_process = models.NullBooleanField(default=None)

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def email_subject(self):
        if self.sticker_printing_response_email:
            return self.sticker_printing_response_email.email_subject
        return ''

    @property
    def email_date(self):
        if self.sticker_printing_response_email:
            return self.sticker_printing_response_email.email_date
        return ''


# class StickerMixin(models.Model):
#     stickers_document = models.ForeignKey(StickersDocument, blank=True, null=True)
#
#     class Meta:
#         abstract = True
#         app_label = 'mooringlicensing'


class WaitingListApplication(Proposal):
    proposal = models.OneToOneField(Proposal, parent_link=True)
    code = 'wla'
    prefix = 'WL'

    new_application_text = "I want to be included on the waiting list for a mooring license"

    apply_page_visibility = True
    description = 'Waiting List Application'

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    def create_fee_lines(self):
        """
        Create the ledger lines - line item for application fee sent to payment system
        """
        from mooringlicensing.components.payments_ml.models import FeeConstructor
        from mooringlicensing.components.payments_ml.utils import generate_line_item

        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        current_datetime_str = current_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')
        target_date = self.get_target_date(current_datetime.date())
        logger.info('Creating fee lines for the proposal: {}, target date: {}'.format(self.lodgement_number, target_date))

        # Any changes to the DB should be made after the success of payment process
        db_processes_after_success = {}
        accept_null_vessel = False

        application_type = self.application_type

        if self.vessel_details:
            vessel_length = self.vessel_details.vessel_applicable_length
        else:
            # No vessel specified in the application
            if self.does_accept_null_vessel:
                # For the amendment application or the renewal application, vessel field can be blank when submit.
                vessel_length = -1
                accept_null_vessel = True
            else:
                msg = 'No vessel specified for the application {}'.format(self.lodgement_number)
                logger.error(msg)
                raise Exception(msg)

        # Retrieve FeeItem object from FeeConstructor object
        fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_date(application_type,
                                                                                          target_date)
        if not fee_constructor:
            # Fees have not been configured for this application type and date
            msg = 'FeeConstructor object for the ApplicationType: {} not found for the date: {} for the application: {}'.format(
                application_type, target_date, self.lodgement_number)
            logger.error(msg)
            raise Exception(msg)

        fee_item = fee_constructor.get_fee_item(vessel_length, self.proposal_type, target_date, accept_null_vessel=accept_null_vessel)
        fee_amount_adjusted = self.get_fee_amount_adjusted(fee_item, vessel_length)

        if fee_item.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
            # This application is 'Amendment' application.  fee_item is already for 'Amendment'
            fee_item_for_amendment_calculation = fee_item
        else:
            # We want to store the fee_item considered to be paid in order to calculate the amount for the amendment application
            proposal_type_amendment = ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT)
            fee_item_for_amendment_calculation = fee_constructor.get_fee_item(vessel_length, proposal_type_amendment, target_date, accept_null_vessel=accept_null_vessel)

        db_processes_after_success['season_start_date'] = fee_constructor.fee_season.start_date.__str__()
        db_processes_after_success['season_end_date'] = fee_constructor.fee_season.end_date.__str__()
        db_processes_after_success['datetime_for_calculating_fee'] = current_datetime_str
        # db_processes_after_success['fee_item_id'] = fee_item.id if fee_item else 0
        db_processes_after_success['fee_item_id'] = fee_item_for_amendment_calculation.id if fee_item_for_amendment_calculation else 0

        line_items = []
        line_items.append(
            generate_line_item(application_type, fee_amount_adjusted, fee_constructor, self, current_datetime))

        logger.info('{}'.format(line_items))

        return line_items, db_processes_after_success

    def get_fee_amount_adjusted(self, fee_item_being_applied, vessel_length):
        """
        Retrieve all the fee_items for this vessel
        """
        if fee_item_being_applied:
            fee_amount_adjusted = fee_item_being_applied.get_absolute_amount(vessel_length)

            if self.proposal_type.code in (PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL):
                # When new/renewal, no need to adjust the amount
                pass
            else:
                # When amendment, amount needs to be adjusted
                logger.info('Adjusting the fee amount for proposal: {}, fee_item: {}, vessel_length: {}'.format(
                    self.lodgement_number, fee_item_being_applied, vessel_length
                ))

                if self.approval:  # This should be True
                    max_fee_item = self.approval.get_max_fee_item(fee_item_being_applied.fee_period.fee_season)
                    if max_fee_item:  # This should be True
                        fee_amount_adjusted = fee_amount_adjusted - max_fee_item.get_absolute_amount()
                        logger.info('Deduct {} from {}'.format(fee_item_being_applied, max_fee_item))

                fee_amount_adjusted = 0 if fee_amount_adjusted <= 0 else fee_amount_adjusted
        else:
            if self.does_accept_null_vessel:
                # TODO: We don't charge for this application but when new replacement vessel details are provided,calculate fee and charge it
                fee_amount_adjusted = 0
            else:
                raise Exception('FeeItem not found.')

        return fee_amount_adjusted

    @property
    def assessor_group(self):
        return Group.objects.get(name="Mooring Licensing - Assessors: Waiting List")

    @property
    def approver_group(self):
        return None

    @property
    def assessor_recipients(self):
        return [i.email for i in self.assessor_group.user_set.all()]

    @property
    def approver_recipients(self):
        return []

    def is_assessor(self, user):
        return user in self.assessor_group.user_set.all()

    def is_approver(self, user):
        return False

    def save(self, *args, **kwargs):
        #application_type_acronym = self.application_type.acronym if self.application_type else None
        super(WaitingListApplication, self).save(*args, **kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()
        self.proposal.refresh_from_db()

    #def set_status_after_payment_success(self):
    #    # self.proposal.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR  # Not very sure why we need to specify 'proposal', but this works
    #    # self.proposal.customer_status = Proposal.CUSTOMER_STATUS_WITH_ASSESSOR
    #    self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR  # Doesn't update parent.processing_status... why?
    #    self.customer_status = Proposal.CUSTOMER_STATUS_WITH_ASSESSOR
    #    self.save()

    def send_emails_after_payment_success(self, request):
        attachments = []
        if self.invoice:
            invoice_bytes = create_invoice_pdf_bytes('invoice.pdf', self.invoice,)
            attachment = ('invoice#{}.pdf'.format(self.invoice.reference), invoice_bytes, 'application/pdf')
            attachments.append(attachment)
        ret_value = send_confirmation_email_upon_submit(request, self, True, attachments)
        send_notification_email_upon_submit_to_assessor(request, self, attachments)
        return ret_value

    #def update_or_create_approval(self, current_datetime, request=None):
    #    created = None
    #    if self.proposal_type in (ProposalType.objects.filter(code__in=(PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT))):
    #        approval = self.approval
    #        approval.current_proposal=self
    #        # TODO: should this be reset?
    #        approval.wla_queue_date = current_datetime
    #        approval.issue_date = current_datetime
    #        approval.start_date = current_datetime.date()
    #        approval.expiry_date = self.end_date
    #        approval.submitter = self.submitter
    #        approval.save()
    #    else:
    #        approval, created = self.approval_class.objects.update_or_create(
    #        #approval, created = cls.objects.update_or_create(
    #            current_proposal=self,
    #            defaults={
    #                'issue_date': current_datetime,
    #                'wla_queue_date': current_datetime,
    #                #'start_date': current_date.strftime('%Y-%m-%d'),
    #                #'expiry_date': self.end_date.strftime('%Y-%m-%d'),
    #                'start_date': current_datetime.date(),
    #                'expiry_date': self.end_date,
    #                'submitter': self.submitter,
    #                'internal_status': 'waiting',
    #            }
    #        )
    #        if created:
    #            self.approval = approval
    #            self.save()
    #    # write approval history
    #    approval.write_approval_history()
    #    # set wla order
    #    approval = approval.set_wla_order()
    #    return approval, created

    #def process_after_payment_success(self, request):
    #    self.lodgement_date = datetime.datetime.now(pytz.timezone(TIME_ZONE))
    #    self.log_user_action(ProposalUserAction.ACTION_LODGE_APPLICATION.format(self.id), request)

    #    ret1 = self.send_emails_after_payment_success(request)
    #    if not ret1:
    #        raise ValidationError('An error occurred while submitting proposal (Submit email notifications failed)')
    #    self.save()

    @property
    def does_accept_null_vessel(self):
        if self.proposal_type.code in (PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL):
            return True
        return False

    def process_after_approval(self, request=None, total_amount=0):
        pass

    def does_have_valid_associations(self):
        """
        Check if this application has valid associations with other applications and approvals
        """
        # TODO: correct the logic.  just partially implemented
        valid = True

        # Rules for proposal
        proposals = WaitingListApplication.objects.\
            filter(vessel_details__vessel=self.vessel_details.vessel).\
            exclude(
                Q(id=self.id) | Q(processing_status__in=(Proposal.PROCESSING_STATUS_DECLINED, Proposal.PROCESSING_STATUS_APPROVED, Proposal.PROCESSING_STATUS_DISCARDED))
            )
        if proposals:
            # The vessel in this application is already part of another application
            valid = False

        # Rules for approval
        # from mooringlicensing.components.approvals.models import ApprovalHistory
        # approvals = [ah.approval for ah in ApprovalHistory.objects.filter(end_date=None, vessel_ownership__vessel=self.vessel_details.vessel)]
        # approvals = list(dict.fromkeys(approvals))  # remove duplicates

        return valid


class AnnualAdmissionApplication(Proposal):
    proposal = models.OneToOneField(Proposal, parent_link=True)
    code = 'aaa'
    prefix = 'AA'
    new_application_text = "I want to apply for an annual admission permit"
    apply_page_visibility = True
    description = 'Annual Admission Application'

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    def create_fee_lines(self):
        """
        Create the ledger lines - line item for application fee sent to payment system
        """
        from mooringlicensing.components.payments_ml.models import FeeConstructor
        from mooringlicensing.components.payments_ml.utils import generate_line_item

        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        current_datetime_str = current_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')
        target_date = self.get_target_date(current_datetime.date())
        annual_admission_type = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)  # Used for AUA / MLA

        logger.info('Creating fee lines for the proposal: {}, target date: {}'.format(self.lodgement_number, target_date))

        # Any changes to the DB should be made after the success of payment process
        db_processes_after_success = {}
        accept_null_vessel = False

        if self.vessel_details:
            vessel_length = self.vessel_details.vessel_applicable_length
        else:
            # No vessel specified in the application
            if self.does_accept_null_vessel:
                # For the amendment application or the renewal application, vessel field can be blank when submit.
                vessel_length = -1
                accept_null_vessel = True
            else:
                msg = 'No vessel specified for the application {}'.format(self.lodgement_number)
                logger.error(msg)
                raise Exception(msg)

        # Retrieve FeeItem object from FeeConstructor object
        fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_date(self.application_type, target_date)
        if self.application_type.code in (AuthorisedUserApplication.code, MooringLicenceApplication.code):
            # There is also annual admission fee component for the AUA/MLA.
            fee_constructor_for_aa = FeeConstructor.get_fee_constructor_by_application_type_and_date(annual_admission_type, target_date)
            if not fee_constructor_for_aa:
                # Fees have not been configured for the annual admission application and date
                msg = 'FeeConstructor object for the Annual Admission Application not found for the date: {} for the application: {}'.format(target_date, self.lodgement_number)
                logger.error(msg)
                raise Exception(msg)
        if not fee_constructor:
            # Fees have not been configured for this application type and date
            msg = 'FeeConstructor object for the ApplicationType: {} not found for the date: {} for the application: {}'.format(self.application_type, target_date, self.lodgement_number)
            logger.error(msg)
            raise Exception(msg)

        fee_item = fee_constructor.get_fee_item(vessel_length, self.proposal_type, target_date, accept_null_vessel=accept_null_vessel)
        fee_amount_adjusted = self.get_fee_amount_adjusted(fee_item, vessel_length)

        if fee_item.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
            # This application is 'Amendment' application.  fee_item is already for 'Amendment'
            fee_item_for_amendment_calculation = fee_item
        else:
            # We want to store the fee_item considered to be paid in order to calculate the amount for the amendment application
            proposal_type_amendment = ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT)
            fee_item_for_amendment_calculation = fee_constructor.get_fee_item(vessel_length, proposal_type_amendment, target_date, accept_null_vessel=accept_null_vessel)

        db_processes_after_success['season_start_date'] = fee_constructor.fee_season.start_date.__str__()
        db_processes_after_success['season_end_date'] = fee_constructor.fee_season.end_date.__str__()
        db_processes_after_success['datetime_for_calculating_fee'] = current_datetime_str
        # db_processes_after_success['fee_item_id'] = fee_item.id if fee_item else 0
        db_processes_after_success['fee_item_id'] = fee_item_for_amendment_calculation.id if fee_item_for_amendment_calculation else 0

        line_items = []
        line_items.append(generate_line_item(self.application_type, fee_amount_adjusted, fee_constructor, self, current_datetime))

        logger.info('{}'.format(line_items))

        return line_items, db_processes_after_success

    def get_fee_amount_adjusted(self, fee_item_being_applied, vessel_length):
        """
        Retrieve all the fee_items for this vessel
        """
        if fee_item_being_applied:
            fee_amount_adjusted = fee_item_being_applied.get_absolute_amount(vessel_length)

            if self.proposal_type.code in (PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL):
                # When new/renewal, no need to adjust the amount
                pass
            else:
                # When amendment, amount needs to be adjusted
                logger.info('Adjusting the fee amount for proposal: {}, fee_item: {}, vessel_length: {}'.format(
                    self.lodgement_number, fee_item_being_applied, vessel_length
                ))

                if self.approval:  # This should be True
                    max_fee_item = self.approval.get_max_fee_item(fee_item_being_applied.fee_period.fee_season)
                    if max_fee_item:  # This should be True
                        fee_amount_adjusted = fee_amount_adjusted - max_fee_item.get_absolute_amount()
                        logger.info('Deduct {} from {}'.format(fee_item_being_applied, max_fee_item))

                fee_amount_adjusted = 0 if fee_amount_adjusted <= 0 else fee_amount_adjusted
        else:
            if self.does_accept_null_vessel:
                # TODO: We don't charge for this application but when new replacement vessel details are provided,calculate fee and charge it
                fee_amount_adjusted = 0
            else:
                raise Exception('FeeItem not found.')

        return fee_amount_adjusted

    @property
    def assessor_group(self):
        return Group.objects.get(name="Mooring Licensing - Assessors: Annual Admission")

    @property
    def approver_group(self):
        return None

    @property
    def assessor_recipients(self):
        return [i.email for i in self.assessor_group.user_set.all()]

    @property
    def approver_recipients(self):
        return []

    def is_assessor(self, user):
        return user in self.assessor_group.user_set.all()

    def is_approver(self, user):
        return False

    def save(self, *args, **kwargs):
        #application_type_acronym = self.application_type.acronym if self.application_type else None
        super(AnnualAdmissionApplication, self).save(*args,**kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()
        self.proposal.refresh_from_db()

    def send_emails_after_payment_success(self, request):
        attachments = []
        if self.invoice:
            invoice_bytes = create_invoice_pdf_bytes('invoice.pdf', self.invoice,)
            attachment = ('invoice#{}.pdf'.format(self.invoice.reference), invoice_bytes, 'application/pdf')
            attachments.append(attachment)
        ret_value = send_confirmation_email_upon_submit(request, self, True, attachments)
        send_notification_email_upon_submit_to_assessor(request, self, attachments)
        return ret_value

    #def process_after_payment_success(self, request):
    #    self.lodgement_date = datetime.datetime.now(pytz.timezone(TIME_ZONE))
    #    self.log_user_action(ProposalUserAction.ACTION_LODGE_APPLICATION.format(self.id), request)

    #    ret1 = self.send_emails_after_payment_success(request)
    #    if not ret1:
    #        raise ValidationError('An error occurred while submitting proposal (Submit email notifications failed)')

    #    self.save()

    def process_after_approval(self, request=None, total_amount=0):
        pass

    #@property
    #def does_accept_null_vessel(self):
     #   return False
    @property
    def does_accept_null_vessel(self):
        if self.proposal_type.code in (PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL):
            return True
        return False

    def does_have_valid_associations(self):
        """
        Check if this application has valid associations with other applications and approvals
        """
        # TODO: implement logic
        return True


class AuthorisedUserApplication(Proposal):
    proposal = models.OneToOneField(Proposal, parent_link=True)
    code = 'aua'
    prefix = 'AU'
    new_application_text = "I want to apply for an an authorised user permit"
    apply_page_visibility = True
    description = 'Authorised User Application'

    # This uuid is used to generate the URL for the AUA endorsement link
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    def create_fee_lines(self):
        """ Create the ledger lines - line item for application fee sent to payment system """
        from mooringlicensing.components.payments_ml.models import FeeConstructor
        from mooringlicensing.components.payments_ml.utils import generate_line_item

        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        target_date = self.get_target_date(current_datetime.date())
        annual_admission_type = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)  # Used for AUA / MLA
        accept_null_vessel = False

        logger.info('Creating fee lines for the proposal: {}, target date: {}'.format(self.lodgement_number, target_date))

        if self.vessel_details:
            vessel_length = self.vessel_details.vessel_applicable_length
        else:
            # No vessel specified in the application
            if self.does_accept_null_vessel:
                # For the amendment application or the renewal application, vessel field can be blank when submit.
                vessel_length = -1
                accept_null_vessel = True
                # this_is_null_vessel_app = True
            else:
                msg = 'No vessel specified for the application {}'.format(self.lodgement_number)
                logger.error(msg)
                raise Exception(msg)

        # Retrieve FeeItem object from FeeConstructor object
        fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_date(self.application_type, target_date)
        fee_constructor_for_aa = FeeConstructor.get_fee_constructor_by_application_type_and_date(annual_admission_type, target_date)

        # There is also annual admission fee component for the AUA/MLA if needed.
        current_approvals_dict = self.vessel_details.vessel.get_current_approvals(target_date)
        aap_exists_for_this_vessel = False
        ml_exists_for_this_vessel = False
        for key, approvals in current_approvals_dict.items():
            if key == 'mls' and approvals.count():
                ml_exists_for_this_vessel = True
            if approvals.count():
                aap_exists_for_this_vessel = True

        if ml_exists_for_this_vessel:
            # When there is 'current' ML, no charge for the AUP
            return [], {}  # no line items, no db process

        fee_items_to_store = []
        line_items = []

        fee_item = fee_constructor.get_fee_item(vessel_length, self.proposal_type, target_date, accept_null_vessel=accept_null_vessel)
        fee_amount_adjusted = self.get_fee_amount_adjusted(fee_item, vessel_length)
        fee_item_amendment_calculation = self.get_corresponding_amendment_fee_item(accept_null_vessel, fee_constructor, fee_item, target_date, vessel_length)
        fee_items_to_store.append({'fee_item': fee_item_amendment_calculation, 'vessel_details': self.vessel_details})
        line_items.append(generate_line_item(self.application_type, fee_amount_adjusted, fee_constructor, self, current_datetime))

        if not aap_exists_for_this_vessel:
            fee_item_for_aa = fee_constructor_for_aa.get_fee_item(vessel_length, self.proposal_type, target_date) if fee_constructor_for_aa else None
            fee_amount_adjusted_additional = self.get_fee_amount_adjusted(fee_item_for_aa, vessel_length) if fee_item_for_aa else None
            fee_item_for_aa_amendment_calculation = self.get_corresponding_amendment_fee_item(accept_null_vessel, fee_constructor_for_aa, fee_item_for_aa, target_date, vessel_length)
            fee_items_to_store.append({'fee_item': fee_item_for_aa_amendment_calculation, 'vessel_details': self.vessel_details})
            line_items.append(generate_line_item(annual_admission_type, fee_amount_adjusted_additional, fee_constructor_for_aa, self, current_datetime))

        logger.info('{}'.format(line_items))

        return line_items, fee_items_to_store

    def get_fee_amount_adjusted(self, fee_item_being_applied, vessel_length):
        """
        Retrieve all the fee_items for this vessel
        """
        if fee_item_being_applied:
            fee_amount_adjusted = fee_item_being_applied.get_absolute_amount(vessel_length)
            target_fee_season = fee_item_being_applied.fee_period.fee_season
            # for_annual_admission_component = True if target_fee_season.application_type.code == AnnualAdmissionApplication.code else False

            if self.proposal_type.code in (PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL):
                # When new/renewal, no need to adjust the amount
                pass
            else:
                # When amendment, amount needs to be adjusted
                logger.info('Adjusting the fee amount for proposal: {}, fee_item: {}, vessel_length: {}'.format(self.lodgement_number, fee_item_being_applied, vessel_length))

                if self.approval:  # This should be True
                    max_fee_item = self.approval.get_max_fee_item(fee_item_being_applied.fee_period.fee_season)

                    if max_fee_item:  # This should be True
                        fee_amount_adjusted = fee_amount_adjusted - max_fee_item.get_absolute_amount()
                        logger.info('Deduct {} from {}'.format(fee_item_being_applied, max_fee_item))

                fee_amount_adjusted = 0 if fee_amount_adjusted <= 0 else fee_amount_adjusted
        else:
            if self.does_accept_null_vessel:
                # TODO: We don't charge for this application but when new replacement vessel details are provided,calculate fee and charge it
                fee_amount_adjusted = 0
            else:
                raise Exception('FeeItem not found.')

        return fee_amount_adjusted

    def get_due_date_for_endorsement_by_target_date(self, target_date=timezone.localtime(timezone.now()).date()):
        days_type = NumberOfDaysType.objects.get(code=CODE_DAYS_FOR_ENDORSER_AUA)
        days_setting = NumberOfDaysSetting.get_setting_by_date(days_type, target_date)
        if not days_setting:
            # No number of days found
            raise ImproperlyConfigured("NumberOfDays: {} is not defined for the date: {}".format(days_type.name, target_date))
        due_date = self.lodgement_date + datetime.timedelta(days=days_setting.number_of_days)
        return due_date

    @property
    def assessor_group(self):
        return Group.objects.get(name="Mooring Licensing - Assessors: Authorised User")

    @property
    def approver_group(self):
        return Group.objects.get(name="Mooring Licensing - Approvers: Authorised User")

    @property
    def assessor_recipients(self):
        return [i.email for i in self.assessor_group.user_set.all()]

    @property
    def approver_recipients(self):
        return [i.email for i in self.approver_group.user_set.all()]

    def is_assessor(self, user):
        return user in self.assessor_group.user_set.all()

    def is_approver(self, user):
        return user in self.approver_group.user_set.all()

    def save(self, *args, **kwargs):
        super(AuthorisedUserApplication, self).save(*args, **kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()
        self.proposal.refresh_from_db()

    def send_emails_after_payment_success(self, request):
        # ret_value = send_submit_email_notification(request, self)
        # TODO: Send payment success email to the submitter (applicant)
        return True

    def get_mooring_authorisation_preference(self):
        if self.keep_existing_mooring and self.previous_application:
            return self.previous_application.child_obj.get_mooring_authorisation_preference()
        else:
            return self.mooring_authorisation_preference

    def process_after_submit(self, request):
        #self.refresh_from_db()  # required to update self.mooring_authorisation_preference, but not very sure why
        self.lodgement_date = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        self.save()
        self.log_user_action(ProposalUserAction.ACTION_LODGE_APPLICATION.format(self.id), request)

        mooring_preference = self.get_mooring_authorisation_preference()

        if mooring_preference.lower() != 'ria':
            # When this application is AUA, and the mooring authorisation preference is not RIA
            self.processing_status = Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT
            self.customer_status = Proposal.CUSTOMER_STATUS_AWAITING_ENDORSEMENT
            self.save()
            # Email to endorser
            send_endorsement_of_authorised_user_application_email(request, self)
            send_confirmation_email_upon_submit(request, self, False)
        else:
            self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
            self.customer_status = Proposal.CUSTOMER_STATUS_WITH_ASSESSOR
            self.save()
            send_confirmation_email_upon_submit(request, self, False)
            send_notification_email_upon_submit_to_assessor(request, self)

    def update_or_create_approval(self, current_datetime, request=None, auto_renew=None):
        # This function is called after payment success for new/amendment/renewal application

        created = None

        ## find any current AUP for this submitter with the same vessel
        #au_list = self.approval_class.objects.filter(
        #        status='current',
        #        submitter=self.submitter,
        #        current_proposal__vessel_details__vessel=self.vessel_details.vessel,
        #        )
        #if au_list:
        #    # change proposal to amendment application
        #    self.proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT)

        # Manage approval
        if self.proposal_type.code == PROPOSAL_TYPE_NEW:
            # When new application
            approval, created = self.approval_class.objects.update_or_create(
                current_proposal=self,
                defaults={
                    'issue_date': current_datetime,
                    'start_date': current_datetime.date(),
                    'expiry_date': self.end_date,
                    'submitter': self.submitter,
                }
            )
            if created:
                self.approval = approval
                self.save()
        elif self.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
            # When amendment application
            approval = self.approval.child_obj
            approval.current_proposal = self
            approval.issue_date = current_datetime
            approval.start_date = current_datetime.date()
            # We don't need to update expiry_date when amendment.  Also self.end_date can be None.
            # approval.expiry_date = self.end_date
            approval.submitter = self.submitter
            approval.save()
        elif self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
            # When renewal application
            approval = self.approval.child_obj
            approval.current_proposal = self
            approval.issue_date = current_datetime
            approval.start_date = current_datetime.date()
            approval.expiry_date = self.end_date
            approval.submitter = self.submitter
            approval.renewal_sent = False
            approval.expiry_notice_sent = False
            approval.renewal_count += 1
            approval.save()

        # update proposed_issuance_approval and MooringOnApproval if not system reissue
        existing_mooring_count = None
        if request and not auto_renew:
            # Create MooringOnApproval records
            ## also see logic in approval.add_mooring()
            mooring_id_pk = self.proposed_issuance_approval.get('mooring_id')
            ria_selected_mooring = None
            if mooring_id_pk:
                ria_selected_mooring = Mooring.objects.get(id=mooring_id_pk)

            existing_mooring_count = approval.mooringonapproval_set.count()
            if ria_selected_mooring:
                moa, created = approval.add_mooring(mooring=ria_selected_mooring, site_licensee=False)
            else:
                if approval.current_proposal.mooring:
                    moa, created = approval.add_mooring(mooring=approval.current_proposal.mooring, site_licensee=True)
            # updating checkboxes
            #if self.approval:
            for moa1 in self.proposed_issuance_approval.get('mooring_on_approval'):
                for moa2 in self.approval.mooringonapproval_set.filter(mooring__mooring_licence__status='current'):
                    # convert proposed_issuance_approval to an end_date
                    if moa1.get("id") == moa2.id and not moa1.get("checked") and not moa2.end_date:
                        moa2.end_date = current_datetime.date()
                        moa2.save()
        if request:
            # Generate compliances
            from mooringlicensing.components.compliances.models import Compliance, ComplianceUserAction
            #if created:
                #if self.proposal_type == PROPOSAL_TYPE_AMENDMENT:
            if self.previous_application:
                approval_compliances = Compliance.objects.filter(approval=self.approval,
                                                                 proposal=self.previous_application,
                                                                 processing_status='future')
                if approval_compliances:
                    for c in approval_compliances:
                        c.delete()
                # Log creation
                # Generate the document
                approval.generate_doc(request.user)
                self.generate_compliances(approval, request)
                # send the doc and log in approval and org
            else:
                # Generate the document
                approval.generate_doc(request.user)
                # Delete the future compliances if Approval is reissued and generate the compliances again.
                approval_compliances = Compliance.objects.filter(approval=approval, proposal=self,
                                                                 processing_status='future')
                if approval_compliances:
                    for c in approval_compliances:
                        c.delete()

        # always reset this flag
        approval.renewal_sent = False
        approval.export_to_mooring_booking = True
        approval.save()

        # set proposal status to approved - can change later after manage_stickers
        self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
        self.customer_status = Proposal.CUSTOMER_STATUS_APPROVED
        self.save()

        # Retrieve newely added moorings, and send authorised user summary doc to the licence holder
        mls_to_be_emailed = None
        from mooringlicensing.components.approvals.models import MooringOnApproval, MooringLicence, Approval, Sticker
        new_moas = MooringOnApproval.objects.filter(approval=approval, sticker__isnull=True)  # New moa doesn't have stickers.
        for new_moa in new_moas:
            mls_to_be_emailed = MooringLicence.objects.filter(mooring=new_moa.mooring, status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,])

        # manage stickers
        moas_to_be_reallocated, stickers_to_be_returned = approval.manage_stickers(self)

        ## set proposal status after manage _stickers
        awaiting_printing = False

        if self.approval:
            stickers = self.approval.stickers.filter(status__in=(Sticker.STICKER_STATUS_READY, Sticker.STICKER_STATUS_AWAITING_PRINTING))
            if stickers.count() >0:
                awaiting_printing = True

        if awaiting_printing or auto_renew:
            self.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
            self.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
            # Log proposal action
            self.log_user_action(ProposalUserAction.ACTION_PRINTING_STICKER.format(self.id), request)
        else:
            self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
            self.customer_status = Proposal.CUSTOMER_STATUS_APPROVED
        self.save()

        # Email
        send_aua_approved_or_declined_email_new_renewal(self, 'approved_paid', request, stickers_to_be_returned)
        # Email to ML holder when new moorings added
        for mooring_licence in mls_to_be_emailed:
            mooring_licence.generate_au_summary_doc(request.user)
            send_au_summary_to_ml_holder(mooring_licence, request)

        # Log proposal action
        if request:
            self.log_user_action(ProposalUserAction.ACTION_APPROVE_APPLICATION.format(self.id), request)
        else:
            self.log_user_action(ProposalUserAction.ACTION_APPROVE_APPLICATION.format(self.id))

        # Write approval history
        if existing_mooring_count and approval.mooringonapproval_set.count() > existing_mooring_count:
            approval.write_approval_history('mooring_add')
        elif created:
            approval.write_approval_history('new')
        else:
            approval.write_approval_history()
        #approval.write_approval_history()

        return approval, created

    @property
    def does_accept_null_vessel(self):
        return False

    def does_have_valid_associations(self):
        """
        Check if this application has valid associations with other applications and approvals
        """
        # TODO: implement logic
        return True


class MooringLicenceApplication(Proposal):
    REASON_FOR_EXPIRY_NOT_SUBMITTED = 'not_submitted'
    REASON_FOR_EXPIRY_NO_DOCUMENTS = 'no_documents'

    proposal = models.OneToOneField(Proposal, parent_link=True)
    code = 'mla'
    prefix = 'ML'
    new_application_text = ""
    apply_page_visibility = False
    description = 'Mooring Licence Application'

    # This uuid is used to generate the URL for the ML document upload page
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    class Meta:
        app_label = 'mooringlicensing'

    # def process_after_payment_success(self, request):
    #     pass
    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    def create_fee_lines(self):
        """ Create the ledger lines - line item for application fee sent to payment system """
        from mooringlicensing.components.payments_ml.models import FeeConstructor
        from mooringlicensing.components.payments_ml.utils import generate_line_item

        accept_null_vessel = False
        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        target_date = self.get_target_date(current_datetime.date())
        annual_admission_type = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)  # Used for AUA / MLA

        logger.info('Creating fee lines for the proposal: {}, target date: {}'.format(self.lodgement_number, target_date))

        # Retrieve FeeItem object from FeeConstructor object
        fee_constructor_for_ml = FeeConstructor.get_fee_constructor_by_application_type_and_date(self.application_type, target_date)
        fee_constructor_for_aa = FeeConstructor.get_fee_constructor_by_application_type_and_date(annual_admission_type, target_date)

        vessel_detais_list_to_be_processed = [self.vessel_details,]
        vessel_details_largest = self.vessel_details
        if self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
            # Only when 'Renewal' application, we are interested in the existing vessels on the ML
            vessel_list = self.approval.child_obj.vessel_list_for_payment
            for vessel in vessel_list:
                if vessel != self.vessel_details.vessel:
                    vessel_detais_list_to_be_processed.append(vessel.latest_vessel_details)
                    if vessel_details_largest.vessel_applicable_length < vessel.latest_vessel_details.vessel_applicable_length:
                        vessel_details_largest = vessel.latest_vessel_details

        line_items = []  # Store all the line items
        fee_items_to_store = []  # Store all the fee_items

        # For Mooring Licence component
        if vessel_details_largest:
            vessel_length = vessel_details_largest.vessel_applicable_length
        else:
            # No vessel specified in the application
            if self.does_accept_null_vessel:
                # For the amendment application or the renewal application, vessel field can be blank when submit.
                vessel_length = -1
                accept_null_vessel = True
            else:
                msg = 'No vessel specified for the application {}'.format(self.lodgement_number)
                logger.error(msg)
                raise Exception(msg)

        fee_item = fee_constructor_for_ml.get_fee_item(vessel_length, self.proposal_type, target_date, accept_null_vessel=accept_null_vessel)
        fee_amount_adjusted = self.get_fee_amount_adjusted(fee_item, vessel_length)
        fee_item_amendment_calculation = self.get_corresponding_amendment_fee_item(accept_null_vessel, fee_constructor_for_ml, fee_item, target_date, vessel_length)
        fee_items_to_store.append({'fee_item': fee_item_amendment_calculation, 'vessel_details': vessel_details_largest})
        line_items.append(generate_line_item(self.application_type, fee_amount_adjusted, fee_constructor_for_ml, self, current_datetime))

        # For Annual Admission component
        for vessel_details in vessel_detais_list_to_be_processed:
            vessel_length = vessel_details.vessel_applicable_length

            # Check if there is already an AA component paid for this vessel
            # current_approvals_dict = self.vessel_details.vessel.get_current_approvals()
            current_approvals_dict = vessel_details.vessel.get_current_approvals(target_date)
            aap_exists_for_this_vessel = False
            for key, approvals in current_approvals_dict.items():
                if approvals.count():
                    aap_exists_for_this_vessel = True

            if not aap_exists_for_this_vessel:
                # For annual admission component
                fee_item_for_aa = fee_constructor_for_aa.get_fee_item(vessel_length, self.proposal_type, target_date)
                fee_amount_adjusted_additional = self.get_fee_amount_adjusted(fee_item_for_aa, vessel_length)
                fee_item_for_aa_amendment_calculation = self.get_corresponding_amendment_fee_item(accept_null_vessel, fee_constructor_for_aa, fee_item_for_aa, target_date, vessel_length)
                fee_items_to_store.append({'fee_item': fee_item_for_aa_amendment_calculation, 'vessel_details': vessel_details})
                line_items.append(generate_line_item(annual_admission_type, fee_amount_adjusted_additional, fee_constructor_for_aa, self, current_datetime))

        logger.info('{}'.format(line_items))

        return line_items, fee_items_to_store

    def get_fee_amount_adjusted(self, fee_item_being_applied, vessel_length):
        """
        Retrieve all the fee_items for this vessel
        """
        if fee_item_being_applied:
            fee_amount_adjusted = fee_item_being_applied.get_absolute_amount(vessel_length)
            target_fee_season = fee_item_being_applied.fee_period.fee_season
            for_annual_admission_component = True if target_fee_season.application_type.code == AnnualAdmissionApplication.code else False

            if self.proposal_type.code in (PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL):
                # When new/renewal, no need to adjust the amount
                pass
            else:
                # When amendment, amount needs to be adjusted
                logger.info('Adjusting the fee amount for proposal: {}, fee_item: {}, vessel_length: {}'.format(self.lodgement_number, fee_item_being_applied, vessel_length))

                if self.approval:  # This should be True
                    if for_annual_admission_component:
                        # For annual admission component, we mind the vessel
                        max_fee_item = self.approval.get_max_fee_item(fee_item_being_applied.fee_period.fee_season, self.vessel_details)
                    else:
                        max_fee_item = self.approval.get_max_fee_item(fee_item_being_applied.fee_period.fee_season)

                    if max_fee_item:  # This should be True
                        logger.info('Deduct {} from {} (absolute amount: {})'.format(max_fee_item, fee_item_being_applied, fee_amount_adjusted))
                        fee_amount_adjusted = fee_amount_adjusted - max_fee_item.get_absolute_amount()

                fee_amount_adjusted = 0 if fee_amount_adjusted <= 0 else fee_amount_adjusted
        else:
            if self.does_accept_null_vessel:
                # TODO: We don't charge for this application but when new replacement vessel details are provided,calculate fee and charge it
                fee_amount_adjusted = 0
            else:
                raise Exception('FeeItem not found.')

        logger.info('Adjusted amount: {}'.format(fee_amount_adjusted))
        return fee_amount_adjusted

    def get_document_upload_url(self, request):
        document_upload_url = request.build_absolute_uri(reverse('mla-documents-upload', kwargs={'uuid_str': self.uuid}))
        return document_upload_url

    @property
    def assessor_group(self):
        return Group.objects.get(name="Mooring Licensing - Assessors: Mooring Licence")

    @property
    def approver_group(self):
        return Group.objects.get(name="Mooring Licensing - Approvers: Mooring Licence")

    @property
    def assessor_recipients(self):
        return [i.email for i in self.assessor_group.user_set.all()]

    @property
    def approver_recipients(self):
        return [i.email for i in self.approver_group.user_set.all()]

    def is_assessor(self, user):
        return user in self.assessor_group.user_set.all()

    def is_approver(self, user):
        return user in self.approver_group.user_set.all()

    def save(self, *args, **kwargs):
        #application_type_acronym = self.application_type.acronym if self.application_type else None
        super(MooringLicenceApplication, self).save(*args, **kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()
        self.proposal.refresh_from_db()
        print('refresh_from_db1')

    def process_after_submit_other_documents(self, request):
        # Somehow in this function, followings update parent too as we expected as polymorphism
        self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
        self.customer_status = Proposal.CUSTOMER_STATUS_WITH_ASSESSOR
        if self.waiting_list_allocation:
            self.waiting_list_allocation.internal_status = 'submitted'
            self.waiting_list_allocation.save()
        self.save()

        # Log actions
        self.log_user_action(ProposalUserAction.ACTION_SUBMIT_OTHER_DOCUMENTS, request)

        # Send email to assessors
        send_other_documents_submitted_notification_email(request, self)

    def send_emails_after_payment_success(self, request):
        # ret_value = send_submit_email_notification(request, self)
        # TODO: Send email (payment success, granted/printing-sticker)
        return True

    def process_after_submit(self, request):
        self.lodgement_date = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        self.save()
        self.log_user_action(ProposalUserAction.ACTION_LODGE_APPLICATION.format(self.id), request)
        if self.proposal_type in (ProposalType.objects.filter(code__in=(PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT))):
            self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
            self.customer_status = Proposal.CUSTOMER_STATUS_WITH_ASSESSOR
            self.save()
        else:
            self.processing_status = Proposal.PROCESSING_STATUS_AWAITING_DOCUMENTS
            self.customer_status = Proposal.CUSTOMER_STATUS_AWAITING_DOCUMENTS
            self.save()
            send_documents_upload_for_mooring_licence_application_email(request, self)

    def update_or_create_approval(self, current_datetime, request=None, auto_renew=None):
        try:
            # renewal/amendment/reissue - associated ML must have a mooring
            if self.approval and self.approval.child_obj.mooring:
                existing_mooring_licence = self.approval.child_obj
            else:
                existing_mooring_licence = self.allocated_mooring.mooring_licence if self.allocated_mooring else None
            mooring = existing_mooring_licence.mooring if existing_mooring_licence else self.allocated_mooring
            #existing_mooring_licence_vessel_count = len(existing_mooring_licence.vessel_list) if existing_mooring_licence else None
            existing_mooring_licence_vessel_count = existing_mooring_licence.vesselownershiponapproval_set.count() if existing_mooring_licence else None
            created = None

            if self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
                approval = self.approval.child_obj
                approval.current_proposal=self
                approval.issue_date = current_datetime
                approval.start_date = current_datetime.date()
                approval.expiry_date = self.end_date
                approval.submitter = self.submitter
                approval.save()
            elif self.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
                approval = self.approval.child_obj
                approval.current_proposal=self
                approval.issue_date = current_datetime
                approval.start_date = current_datetime.date()
                # We don't need to update expiry_date when amendment.  Also self.end_date can be None.
                # approval.expiry_date = self.end_date
                approval.submitter = self.submitter
                approval.save()
            else:
                approval, created = self.approval_class.objects.update_or_create(
                    current_proposal=self,
                    defaults={
                        'issue_date': current_datetime,
                        'start_date': current_datetime.date(),
                        'expiry_date': self.end_date,
                        'submitter': self.submitter,
                    }
                )
                # associate mooring licence with mooring, only on NEW proposal_type
                if not self.approval:
                    self.allocated_mooring.mooring_licence = approval
                    self.allocated_mooring.save()
                # always associate proposal with approval
                if created:
                    self.approval = approval
                    self.save()
                # Move WLA to status approved
                if self.waiting_list_allocation:
                    self.waiting_list_allocation.internal_status = 'approved'
                    self.waiting_list_allocation.status = 'fulfilled'
                    self.waiting_list_allocation.wla_order = None
                    self.waiting_list_allocation.save()
                    self.waiting_list_allocation.set_wla_order()

            # update proposed_issuance_approval and VesselOwnership if not system reissue
            if request and not auto_renew:
                # Create VesselOwnershipOnApproval records
                ## also see logic in approval.add_vessel_ownership()
                vooa, created = approval.add_vessel_ownership(vessel_ownership=self.vessel_ownership)

                # updating checkboxes
                #if self.approval:
                for vo1 in self.proposed_issuance_approval.get('vessel_ownership'):
                    for vo2 in self.approval.vesselownershiponapproval_set.all():
                        # convert proposed_issuance_approval to an end_date
                        if vo1.get("id") == vo2.vessel_ownership.id and not vo1.get("checked") and not vo2.end_date:
                            vo2.end_date = current_datetime.date()
                            vo2.save()
            if request:
                # Generate compliances
                from mooringlicensing.components.compliances.models import Compliance, ComplianceUserAction
                #if self.proposal_type == PROPOSAL_TYPE_AMENDMENT:
                if self.previous_application:
                    approval_compliances = Compliance.objects.filter(approval=self.approval,
                                                                     proposal=self.previous_application,
                                                                     processing_status='future')
                    if approval_compliances:
                        for c in approval_compliances:
                            c.delete()
                    # Log creation
                    # Generate the document
                    # approval.generate_doc(request.user)
                    self.generate_compliances(approval, request)
                    # send the doc and log in approval and org
                else:
                    # Generate the document
                    # approval.generate_doc(request.user)
                    # Delete the future compliances if Approval is reissued and generate the compliances again.
                    approval_compliances = Compliance.objects.filter(approval=approval, proposal=self,
                                                                     processing_status='future')
                    if approval_compliances:
                        for c in approval_compliances:
                            c.delete()

            mooring.log_user_action(
                    MooringUserAction.ACTION_ASSIGN_MOORING_LICENCE.format(
                        str(approval),
                        ),
                    request
                    )
            # always reset this flag
            approval.renewal_sent = False
            approval.export_to_mooring_booking = True
            approval.save()

            # set proposal status to approved - can change later after manage_stickers
            self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
            self.customer_status = Proposal.CUSTOMER_STATUS_APPROVED
            self.save()

            # manage stickers
            moas_to_be_reallocated, stickers_to_be_returned = approval.manage_stickers(self)

            ## set proposal status after manage _stickers
            from mooringlicensing.components.approvals.models import Sticker
            #awaiting_payment = False
            awaiting_printing = False

            #for application_fee in self.application_fees.all():
             #   if application_fee.unpaid:
              #      awaiting_payment = True

            if self.approval:
                stickers = self.approval.stickers.filter(status__in=(Sticker.STICKER_STATUS_READY, Sticker.STICKER_STATUS_AWAITING_PRINTING))
                if stickers.count() >0:
                    awaiting_printing = True

            #if awaiting_payment:
             #   self.processing_status = Proposal.PROCESSING_STATUS_AWAITING_PAYMENT
              #  self.customer_status = Proposal.CUSTOMER_STATUS_AWAITING_PAYMENT
            if awaiting_printing or auto_renew:
                self.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                self.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_PRINTING_STICKER.format(self.id), request)
            else:
                self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                self.customer_status = Proposal.CUSTOMER_STATUS_APPROVED
            self.save()

            if request:
                # Creating documents should be performed at the end
                approval.generate_doc(request.user)
                if self.proposal_type.code in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT,]:
                    approval.generate_au_summary_doc(request.user)

            # Email with attachments
            send_mla_approved_or_declined_email_new_renewal(self, 'approved_paid', request, stickers_to_be_returned)

            # Log proposal action
            if request:
                self.log_user_action(ProposalUserAction.ACTION_APPROVE_APPLICATION.format(self.id), request)
            else:
                self.log_user_action(ProposalUserAction.ACTION_APPROVE_APPLICATION.format(self.id))

            # write approval history
            #if existing_mooring_licence_vessel_count and len(approval.child_obj.vessel_list) > existing_mooring_licence_vessel_count:
            if existing_mooring_licence_vessel_count and existing_mooring_licence_vessel_count < approval.vesselownershiponapproval_set.count():
                approval.write_approval_history('vessel_add')
            elif created:
                approval.write_approval_history('new')
            else:
                approval.write_approval_history()
            return approval, created
        except Exception as e:
            print(e)
            msg = 'Payment taken for Proposal: {}, but approval creation has failed\n{}'.format(self.lodgement_number, str(e))
            logger.error(msg)
            raise e

    @property
    def does_accept_null_vessel(self):
        if self.proposal_type.code in (PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL):
            return True
        return False

    #def get_fee_amount_adjusted_back(self, fee_item_being_applied, vessel_length):
    #    from mooringlicensing.components.proposals.utils import get_fee_amount_adjusted

    #    # TODO: Check if adjusting is required or not.  For example, it is not required when adding a new vessel
    #    if self.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
    #        if self.vessel_details in self.approval.vessel_details_list_for_payment:
    #            pass
    #            # Adjust amount

    #    return get_fee_amount_adjusted(self, fee_item_being_applied, vessel_length)

    def does_have_valid_associations(self):
        """
        Check if this application has valid associations with other applications and approvals
        """
        # TODO: implement logic
        return True


class ProposalLogDocument(Document):
    log_entry = models.ForeignKey('ProposalLogEntry',related_name='documents')
    _file = models.FileField(upload_to=update_proposal_comms_log_filename, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'


class ProposalLogEntry(CommunicationsLogEntry):
    proposal = models.ForeignKey(Proposal, related_name='comms_logs')

    def __str__(self):
        return '{} - {}'.format(self.reference, self.subject)

    class Meta:
        app_label = 'mooringlicensing'

    def save(self, **kwargs):
        # save the application reference if the reference not provided
        if not self.reference:
            if hasattr(self.proposal, 'reference'):
                self.reference = self.proposal.reference
        super(ProposalLogEntry, self).save(**kwargs)


# not for admin - data comes from Mooring Bookings
class MooringBay(RevisionedMixin):
    name = models.CharField(max_length=100)
    mooring_bookings_id = models.IntegerField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Mooring Bays"
        app_label = 'mooringlicensing'


class PrivateMooringManager(models.Manager):
    def get_queryset(self):
        #latest_ids = Mooring.objects.values("vessel").annotate(id=Max('id')).values_list('id', flat=True)
        return super(PrivateMooringManager, self).get_queryset().filter(mooring_bookings_mooring_specification=2)


class AuthorisedUserMooringManager(models.Manager):
    def get_queryset(self):
        #latest_ids = Mooring.objects.values("vessel").annotate(id=Max('id')).values_list('id', flat=True)
        return super(AuthorisedUserMooringManager, self).get_queryset().filter(mooring_bookings_mooring_specification=2, mooring_licence__status='current')


class AvailableMooringManager(models.Manager):
    def get_queryset(self):
        #latest_ids = Mooring.objects.values("vessel").annotate(id=Max('id')).values_list('id', flat=True)
        # nor that are on a mooring licence application that is in status other than approved, declined or discarded.
        #lookups = (
         #       Q(mooring_bookings_mooring_specification=2) & (Q(mooring_licence__isnull=True) | ~Q(mooring_licence__status='current'))
          #      & (Q(ria_generated_proposal__processing_status__in=['approved', 'declined', 'discarded']) | Q(ria_generated_proposal=None))
           #     )
        available_ids = []
        for mooring in Mooring.private_moorings.all():
            # first check mooring_licence status
            if not mooring.mooring_licence or mooring.mooring_licence.status != 'current':
                # now check whether there are any blocking proposals
                blocking_proposal = False
                for proposal in mooring.ria_generated_proposal.all():
                    if proposal.processing_status not in ['approved', 'declined', 'discarded']:
                        blocking_proposal = True
                if not blocking_proposal:
                    available_ids.append(mooring.id)

        #return super(AvailableMooringManager, self).get_queryset().filter(lookups)
        return super(AvailableMooringManager, self).get_queryset().filter(id__in=available_ids)


# not for admin - data comes from Mooring Bookings
class Mooring(RevisionedMixin):
    MOORING_SPECIFICATION = (
         (1, 'Rental Mooring'),
         (2, 'Private Mooring'),
    )

    name = models.CharField(max_length=100)
    mooring_bay = models.ForeignKey(MooringBay)
    active = models.BooleanField(default=True)
    vessel_size_limit = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # does not exist in MB
    vessel_draft_limit = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_beam_limit = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_weight_limit = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # tonnage
    # stored for debugging purposes, not used in this system
    mooring_bookings_id = models.IntegerField()
    mooring_bookings_mooring_specification = models.IntegerField(choices=MOORING_SPECIFICATION)
    mooring_bookings_bay_id = models.IntegerField()
    # model managers
    objects = models.Manager()
    private_moorings = PrivateMooringManager()
    authorised_user_moorings = AuthorisedUserMooringManager()
    available_moorings = AvailableMooringManager()
    # Used for WLAllocation create MLApplication check
    #mooring_licence = models.ForeignKey('MooringLicence', blank=True, null=True)
    # mooring licence can onl,y have one Mooring
    mooring_licence = models.OneToOneField('MooringLicence', blank=True, null=True, related_name="mooring")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Moorings"
        app_label = 'mooringlicensing'

    @property
    def specification_display(self):
        return self.get_mooring_bookings_mooring_specification_display()

    def log_user_action(self, action, request):
        return MooringUserAction.log_action(self, action, request.user)

    @property
    def status(self):
        from mooringlicensing.components.approvals.models import MooringOnApproval
        #status = 'Unlicensed'
        status = ''
        ## check for Mooring Licences
        #if MooringOnApproval.objects.filter(mooring=self, approval__status='current'):
        if self.mooring_licence and self.mooring_licence.status in ['current', 'suspended']:
            status = 'Licensed'
        if not status:
            # check for Mooring Applications
            proposals = self.ria_generated_proposal.exclude(processing_status__in=['approved', 'declined', 'discarded'])
            for proposal in proposals:
                if proposal.child_obj.code == 'mla':
                    status = 'Licence Application'
        return status if status else 'Unlicenced'

    #@property
    def suitable_vessel(self, vessel_details):
        suitable = True
        if vessel_details.vessel_applicable_length > self.vessel_size_limit or vessel_details.vessel_draft > self.vessel_draft_limit:
            suitable = False
        return suitable

class MooringLogDocument(Document):
    log_entry = models.ForeignKey('MooringLogEntry',related_name='documents')
    _file = models.FileField(upload_to=update_mooring_comms_log_filename, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'


class MooringLogEntry(CommunicationsLogEntry):
    mooring = models.ForeignKey(Mooring, related_name='comms_logs')

    def __str__(self):
        return '{} - {}'.format(self.reference, self.subject)

    class Meta:
        app_label = 'mooringlicensing'

class MooringUserAction(UserAction):
    ACTION_ASSIGN_MOORING_LICENCE = "Assign Mooring Licence {}"
    ACTION_SWITCH_MOORING_LICENCE = "Remove existing Mooring Licence {} and assign {}"

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ('-when',)

    @classmethod
    def log_action(cls, mooring, action, user):
        return cls.objects.create(
            mooring=mooring,
            who=user,
            what=str(action)
        )

    mooring = models.ForeignKey(Mooring, related_name='action_logs')


class Vessel(RevisionedMixin):
    rego_no = models.CharField(max_length=200, unique=True, blank=False, null=False)
    # can be individual or company owner
    ## TODO no longer required???
    blocking_owner = models.ForeignKey('VesselOwnership', blank=True, null=True, related_name='blocked_vessel')

    class Meta:
        verbose_name_plural = "Vessels"
        app_label = 'mooringlicensing'

    def __str__(self):
        return self.rego_no

    def get_current_approvals(self, target_date):
        # Return all the approvals where this vessel is on.
        from mooringlicensing.components.approvals.models import Approval, AnnualAdmissionPermit, AuthorisedUserPermit, MooringLicence

        existing_aaps = AnnualAdmissionPermit.objects.filter(
            status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,),
            start_date__lte=target_date,
            expiry_date__gte=target_date,
            current_proposal__vessel_details__vessel=self,
        )
        existing_aups = AuthorisedUserPermit.objects.filter(
            status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,),
            start_date__lte=target_date,
            expiry_date__gte=target_date,
            current_proposal__vessel_details__vessel=self,
        )
        existing_mls = MooringLicence.objects.filter(
            status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,),
            start_date__lte=target_date,
            expiry_date__gte=target_date,
            proposal__processing_status__in=(Proposal.PROCESSING_STATUS_PRINTING_STICKER, Proposal.PROCESSING_STATUS_APPROVED,),
            proposal__vessel_details__vessel=self,
            proposal__vessel_ownership__end_date__isnull=True,
        )

        return {
            'aaps': existing_aaps,
            'aups': existing_aups,
            'mls': existing_mls
        }

    ## at submit
    def check_blocking_ownership(self, vessel_ownership, proposal_being_processed):
        from mooringlicensing.components.approvals.models import Approval, MooringLicence
        # Requirement: If vessel is owned by multiple parties then there must be no other application
        #   in status other than issued, declined or discarded where the applicant is another owner than this applicant
        proposals_filter = Q(vessel_ownership__vessel=self) & ~Q(Q(vessel_ownership=vessel_ownership) |
                    Q(processing_status__in=['printing_sticker', 'approved', 'declined', 'discarded']) |
                    Q(id=proposal_being_processed.id))
        if Proposal.objects.filter(proposals_filter):
            raise serializers.ValidationError("Another owner of this vessel has an unresolved application outstanding")

        # Requirement:  Annual Admission Permit, Authorised User Permit or Mooring Licence in status other than expired, cancelled, or surrendered
        #   where Permit or Licence holder is an owner other than the applicant of this Waiting List application
        ## ML Filter
        ml_filter = Q(
                ~Q(
                    Q(status__in=['cancelled', 'expired', 'surrendered']) | 
                    Q(proposal__vessel_ownership=vessel_ownership) | 
                    Q(proposal=proposal_being_processed)
                    ) &
                #Q(proposal__processing_status__in=[Proposal.PROCESSING_STATUS_PRINTING_STICKER, Proposal.PROCESSING_STATUS_APPROVED]) &
                #Q(proposal__vessel_ownership__end_date__isnull=True) &
                #Q(proposal__vessel_ownership__mooring_licence_end_date__isnull=True) &
                #Q(proposal__vessel_ownership__vessel=self)
                Q(vesselownershiponapproval__approval__current_proposal__processing_status__in=[Proposal.PROCESSING_STATUS_PRINTING_STICKER, Proposal.PROCESSING_STATUS_APPROVED]) &
                Q(vesselownershiponapproval__vessel_ownership__end_date__isnull=True) &
                Q(vesselownershiponapproval__end_date__isnull=True) &
                Q(vesselownershiponapproval__vessel_ownership__vessel=self)
                )
        ## Other Approvals filter
        approval_filter = Q(
                Q(current_proposal__vessel_ownership__vessel=self) & 
                ~Q(current_proposal__vessel_ownership=vessel_ownership) &
                ~Q(proposal=proposal_being_processed)
                )
        if MooringLicence.objects.filter(ml_filter) or Approval.objects.filter(approval_filter):
            raise serializers.ValidationError("Another owner of this vessel holds a current Licence/Permit")

    @property
    def latest_vessel_details(self):
        #return self.vesseldetails_set.order_by('updated')[0]
        return self.filtered_vesseldetails_set.first()

    @property
    def filtered_vesselownership_set(self):
        return self.vesselownership_set.filter(
                id__in=VesselOwnership.filtered_objects.values_list('id', flat=True)
                )

    @property
    def filtered_vesseldetails_set(self):
        return self.vesseldetails_set.filter(
                id__in=VesselDetails.filtered_objects.values_list('id', flat=True)
                )


class VesselLogDocument(Document):
    log_entry = models.ForeignKey('VesselLogEntry',related_name='documents')
    _file = models.FileField(upload_to=update_vessel_comms_log_filename, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'


class VesselLogEntry(CommunicationsLogEntry):
    vessel = models.ForeignKey(Vessel, related_name='comms_logs')

    def __str__(self):
        return '{} - {}'.format(self.reference, self.subject)

    class Meta:
        app_label = 'mooringlicensing'

class VesselDetailsManager(models.Manager):
    def get_queryset(self):
        latest_ids = VesselDetails.objects.values("vessel").annotate(id=Max('id')).values_list('id', flat=True)
        return super(VesselDetailsManager, self).get_queryset().filter(id__in=latest_ids)
        #return self.first()


class VesselDetails(RevisionedMixin): # ManyToManyField link in Proposal
    vessel_type = models.CharField(max_length=20, choices=VESSEL_TYPES)
    vessel = models.ForeignKey(Vessel)
    vessel_name = models.CharField(max_length=400)
    #vessel_overall_length = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # exists in MB as 'size'
    vessel_length = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # does not exist in MB
    vessel_draft = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_beam = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_weight = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # tonnage
    berth_mooring = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)
    #status = models.CharField(max_length=50, choices=STATUS_TYPES, default="draft") # can be approved, old, draft, declined
    #owner = models.ForeignKey('Owner') # this owner can edit
    # for cron job
    exported = models.BooleanField(default=False) # must be False after every add/edit
    objects = models.Manager()
    filtered_objects = VesselDetailsManager()

    class Meta:
        verbose_name_plural = "Vessel Details"
        app_label = 'mooringlicensing'

    def __str__(self):
        return "{}".format(self.id)

    @property
    def vessel_applicable_length(self):
        #return self.vessel_overall_length
        return self.vessel_length


class CompanyOwnership(RevisionedMixin):
    STATUS_TYPES = (
            ('approved', 'Approved'),
            ('draft', 'Draft'),
            ('old', 'Old'),
            ('declined', 'Declined'),
            )
    blocking_proposal = models.ForeignKey(Proposal, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_TYPES, default="draft") # can be approved, old, draft, declined
    vessel = models.ForeignKey(Vessel)
    company = models.ForeignKey('Company')
    percentage = models.IntegerField(null=True, blank=True)
    ## TODO: delete start and end dates if no longer required
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True)
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Company Ownership"
        app_label = 'mooringlicensing'
        #unique_together = ['owner', 'vessel', 'org_name']

    def __str__(self):
        return "{}: {}".format(self.company, self.percentage)

    def save(self, *args, **kwargs):
        from mooringlicensing.components.approvals.models import AuthorisedUserPermit, MooringLicence
        ## do not allow multiple draft or approved status per vessel_id
        # restrict multiple draft records
        if not self.pk:
            vessel_details_set = CompanyOwnership.objects.filter(vessel=self.vessel, company=self.company)
            for vd in vessel_details_set:
                if vd.status == "draft":
                    raise ValueError("Multiple draft status records for the same company/vessel combination are not allowed")
                elif vd.status == "approved" and self.status == "approved":
                    raise ValueError("Multiple approved status records for the same company/vessel combination are not allowed")
        existing_record = True if CompanyOwnership.objects.filter(id=self.id) else False
        if existing_record:
            prev_end_date = CompanyOwnership.objects.get(id=self.id).end_date
        super(CompanyOwnership, self).save(*args,**kwargs)
        ## Reissue associated ML and AUPs if end-dated
        if existing_record and not prev_end_date and self.end_date:
            aup_set = AuthorisedUserPermit.objects.filter(current_proposal__vessel_ownership__company_ownership=self)
            for aup in aup_set:
                #if aup.status in ['current', 'suspended']:
                if aup.status == 'current':
                    aup.internal_reissue()
            ## ML
            vo_set = self.vesselownership_set.all()
            for vo in vo_set:
                proposal_set = vo.proposal_set.all()
                for proposal in proposal_set:
                    if proposal.approval and type(proposal.approval) == MooringLicence and proposal.approval.status == 'current':
                        proposal.approval.internal_reissue()


class VesselOwnershipManager(models.Manager):
    def get_queryset(self):
        latest_ids = VesselOwnership.objects.values("owner", "vessel", "company_ownership").annotate(id=Max('id')).values_list('id', flat=True)
        return super(VesselOwnershipManager, self).get_queryset().filter(id__in=latest_ids)


class VesselOwnership(RevisionedMixin):
    owner = models.ForeignKey('Owner')
    vessel = models.ForeignKey(Vessel)
    company_ownership = models.ForeignKey(CompanyOwnership, null=True, blank=True)
    percentage = models.IntegerField(null=True, blank=True)
    start_date = models.DateTimeField(default=timezone.now)
    # date of sale
    end_date = models.DateField(null=True, blank=True)
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)
    # for cron job
    exported = models.BooleanField(default=False) # must be False after every add/edit
    objects = models.Manager()
    filtered_objects = VesselOwnershipManager()
    ## replaced by vesselownershiponapproval.end_date
    #mooring_licence_end_date = models.DateField(blank=True, null=True)
    ## Name as shown on DoT registration papers
    dot_name = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Vessel Details Ownership"
        app_label = 'mooringlicensing'
        #unique_together = ['owner', 'vessel', 'org_name']

    def __str__(self):
        return "{}: {}".format(self.owner, self.vessel)

    def get_fee_items_paid(self):
        # Return all the fee_items for this vessel
        fee_items = []
        from mooringlicensing.components.approvals.models import Approval
        for proposal in self.proposal_set.filter(approval__isnull=False, approval__status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,)):
            for item in proposal.get_fee_items_paid():
                if item not in fee_items:
                    fee_items.append(item)
            # fee_items += proposal.get_fee_items_paid()
        return fee_items

    def save(self, *args, **kwargs):
        from mooringlicensing.components.approvals.models import AuthorisedUserPermit, MooringLicence
        existing_record = True if VesselOwnership.objects.filter(id=self.id) else False
        if existing_record:
            prev_end_date = VesselOwnership.objects.get(id=self.id).end_date
        super(VesselOwnership, self).save(*args,**kwargs)
        ## Reissue associated ML and AUPs if end-dated
        if existing_record and not prev_end_date and self.end_date:
            #import ipdb; ipdb.set_trace()
            aup_set = AuthorisedUserPermit.objects.filter(current_proposal__vessel_ownership=self)
            for aup in aup_set:
                #if aup.status in ['current', 'suspended']:
                if aup.status == 'current':
                    aup.internal_reissue()
            ## ML
            proposal_set = self.proposal_set.all()
            for proposal in proposal_set:
                if proposal.approval and type(proposal.approval) == MooringLicence and proposal.approval.status == 'current':
                    proposal.approval.internal_reissue()



class VesselRegistrationDocument(Document):
    #proposal = models.ForeignKey(Proposal,related_name='vessel_registration_documents')
    vessel_ownership = models.ForeignKey(VesselOwnership,related_name='vessel_registration_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Vessel Registration Papers"


class Owner(RevisionedMixin):
    emailuser = models.OneToOneField(EmailUser)
    # add on approval only
    vessels = models.ManyToManyField(Vessel, through=VesselOwnership) # these owner/vessel association

    class Meta:
        verbose_name_plural = "Owners"
        app_label = 'mooringlicensing'

    def __str__(self):
        return self.emailuser.get_full_name()

    #@property
    #def owner_name(self):
    #    if self.org_name:
    #        return self.org_contact
    #    else:
    #        self.emailuser.get_full_name()


class Company(RevisionedMixin):
    name = models.CharField(max_length=200, unique=True, blank=True, null=True)
    vessels = models.ManyToManyField(Vessel, through=CompanyOwnership) # these owner/vessel association

    class Meta:
        verbose_name_plural = "Companies"
        app_label = 'mooringlicensing'
        #unique_together = ['owner', 'vessel', 'org_name']

    def __str__(self):
        return "{}: {}".format(self.name, self.id)



class InsuranceCertificateDocument(Document):
    proposal = models.ForeignKey(Proposal,related_name='insurance_certificate_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Insurance Certificate Documents"


class HullIdentificationNumberDocument(Document):
    proposal = models.ForeignKey(Proposal,related_name='hull_identification_number_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Hull Identification Number Documents"


class ElectoralRollDocument(Document):
    #emailuser = models.ForeignKey(EmailUser,related_name='electoral_roll_documents')
    proposal = models.ForeignKey(Proposal,related_name='electoral_roll_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Electoral Roll Document"


class MooringReportDocument(Document):
    proposal = models.ForeignKey(Proposal, related_name='mooring_report_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255, null=True, blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide = models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden = models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Mooring Report Document"


class WrittenProofDocument(Document):
    proposal = models.ForeignKey(Proposal, related_name='written_proof_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255, null=True, blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide = models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden = models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Written Proof Document"


class SignedLicenceAgreementDocument(Document):
    proposal = models.ForeignKey(Proposal, related_name='signed_licence_agreement_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255, null=True, blank=True)
    can_delete = models.BooleanField(default=True)
    can_hide = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Signed Licence Agreement"


class ProofOfIdentityDocument(Document):
    proposal = models.ForeignKey(Proposal, related_name='proof_of_identity_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255, null=True, blank=True)
    can_delete = models.BooleanField(default=True)
    can_hide = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Proof Of Identity"


class ProposalRequest(models.Model):
    proposal = models.ForeignKey(Proposal, related_name='proposalrequest_set')
    subject = models.CharField(max_length=200, blank=True)
    text = models.TextField(blank=True)
    officer = models.ForeignKey(EmailUser, null=True)

    def __str__(self):
        return '{} - {}'.format(self.subject, self.text)

    class Meta:
        app_label = 'mooringlicensing'


class ComplianceRequest(ProposalRequest):
    REASON_CHOICES = (('outstanding', 'There are currently outstanding returns for the previous licence'),
                      ('other', 'Other'))
    reason = models.CharField('Reason', max_length=30, choices=REASON_CHOICES, default=REASON_CHOICES[0][0])

    class Meta:
        app_label = 'mooringlicensing'


class AmendmentReason(models.Model):
    reason = models.CharField('Reason', max_length=125)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Amendment Reason" # display name in Admin
        verbose_name_plural = "Application Amendment Reasons"

    def __str__(self):
        return self.reason


class AmendmentRequest(ProposalRequest):
    STATUS_CHOICES = (('requested', 'Requested'), ('amended', 'Amended'))
    #REASON_CHOICES = (('insufficient_detail', 'The information provided was insufficient'),
    #                  ('missing_information', 'There was missing information'),
    #                  ('other', 'Other'))
    # try:
    #     # model requires some choices if AmendmentReason does not yet exist or is empty
    #     REASON_CHOICES = list(AmendmentReason.objects.values_list('id', 'reason'))
    #     if not REASON_CHOICES:
    #         REASON_CHOICES = ((0, 'The information provided was insufficient'),
    #                           (1, 'There was missing information'),
    #                           (2, 'Other'))
    # except:
    #     REASON_CHOICES = ((0, 'The information provided was insufficient'),
    #                       (1, 'There was missing information'),
    #                       (2, 'Other'))


    status = models.CharField('Status', max_length=30, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0])
    #reason = models.CharField('Reason', max_length=30, choices=REASON_CHOICES, default=REASON_CHOICES[0][0])
    reason = models.ForeignKey(AmendmentReason, blank=True, null=True)
    #reason = models.ForeignKey(AmendmentReason)

    class Meta:
        app_label = 'mooringlicensing'

    def generate_amendment(self,request):
        with transaction.atomic():
            try:
                if not self.proposal.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.status == 'requested':
                    proposal = self.proposal
                    if proposal.processing_status != 'draft':
                        proposal.processing_status = 'draft'
                        proposal.customer_status = 'draft'
                        proposal.save()
                        # proposal.documents.all().update(can_hide=True)
                        # proposal.required_documents.all().update(can_hide=True)
                    # Create a log entry for the proposal
                    proposal.log_user_action(ProposalUserAction.ACTION_ID_REQUEST_AMENDMENTS, request)
                    # Create a log entry for the organisation
                    applicant_field = getattr(proposal, proposal.applicant_field)
                    applicant_field.log_user_action(ProposalUserAction.ACTION_ID_REQUEST_AMENDMENTS, request)

                    # send email

                    send_amendment_email_notification(self, request, proposal)

                self.save()
            except:
                raise


#class Assessment(ProposalRequest):
#    STATUS_CHOICES = (('awaiting_assessment', 'Awaiting Assessment'), ('assessed', 'Assessed'),
#                      ('assessment_expired', 'Assessment Period Expired'))
#    assigned_assessor = models.ForeignKey(EmailUser, blank=True, null=True)
#    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0])
#    date_last_reminded = models.DateField(null=True, blank=True)
#    #requirements = models.ManyToManyField('Requirement', through='AssessmentRequirement')
#    comment = models.TextField(blank=True)
#    purpose = models.TextField(blank=True)
#
#    class Meta:
#        app_label = 'mooringlicensing'

class ProposalDeclinedDetails(models.Model):
    #proposal = models.OneToOneField(Proposal, related_name='declined_details')
    proposal = models.OneToOneField(Proposal)
    officer = models.ForeignKey(EmailUser, null=False)
    reason = models.TextField(blank=True)
    cc_email = models.TextField(null=True)

    class Meta:
        app_label = 'mooringlicensing'


#class ProposalOnHold(models.Model):
#    #proposal = models.OneToOneField(Proposal, related_name='onhold')
#    proposal = models.OneToOneField(Proposal)
#    officer = models.ForeignKey(EmailUser, null=False)
#    comment = models.TextField(blank=True)
#    documents = models.ForeignKey(ProposalDocument, blank=True, null=True, related_name='onhold_documents')
#
#    class Meta:
#        app_label = 'mooringlicensing'


@python_2_unicode_compatible
class ProposalStandardRequirement(RevisionedMixin):
    text = models.TextField()
    code = models.CharField(max_length=10, unique=True)
    obsolete = models.BooleanField(default=False)
    application_type = models.ForeignKey(ApplicationType, null=True, blank=True)
    participant_number_required = models.BooleanField(default=False)
    default = models.BooleanField(default=False)

    def __str__(self):
        return self.code

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Standard Requirement"
        verbose_name_plural = "Application Standard Requirements"

    # def clean(self):
    #     if self.application_type:
    #         try:
    #             default = ProposalStandardRequirement.objects.get(default=True, application_type=self.application_type)
    #         except ProposalStandardRequirement.DoesNotExist:
    #             default = None

    #     if not self.pk:
    #         if default and self.default:
    #             raise ValidationError('There can only be one default Standard requirement per Application type')


class ProposalUserAction(UserAction):
    ACTION_CREATE_CUSTOMER_ = "Create customer {}"
    ACTION_CREATE_PROFILE_ = "Create profile {}"
    ACTION_LODGE_APPLICATION = "Lodge application {}"
    ACTION_ASSIGN_TO_ASSESSOR = "Assign application {} to {} as the assessor"
    ACTION_UNASSIGN_ASSESSOR = "Unassign assessor from application {}"
    ACTION_ASSIGN_TO_APPROVER = "Assign application {} to {} as the approver"
    ACTION_UNASSIGN_APPROVER = "Unassign approver from application {}"
    ACTION_ACCEPT_ID = "Accept ID"
    ACTION_RESET_ID = "Reset ID"
    ACTION_ID_REQUEST_UPDATE = 'Request ID update'
    ACTION_ACCEPT_CHARACTER = 'Accept character'
    ACTION_RESET_CHARACTER = "Reset character"
    ACTION_ACCEPT_REVIEW = 'Accept review'
    ACTION_RESET_REVIEW = "Reset review"
    ACTION_ID_REQUEST_AMENDMENTS = "Request amendments"
    ACTION_SEND_FOR_ASSESSMENT_TO_ = "Send for assessment to {}"
    ACTION_SEND_ASSESSMENT_REMINDER_TO_ = "Send assessment reminder to {}"
    ACTION_DECLINE = "Decline application {}"
    ACTION_ENTER_CONDITIONS = "Enter requirement"
    ACTION_CREATE_CONDITION_ = "Create requirement {}"
    ACTION_ISSUE_APPROVAL_ = "Issue Licence for application {}"
    ACTION_AWAITING_PAYMENT_APPROVAL_ = "Awaiting Payment for application {}"
    ACTION_PRINTING_STICKER = "Printing Sticker for application {}"
    ACTION_APPROVE_APPLICATION = "Approve application {}"
    ACTION_UPDATE_APPROVAL_ = "Update Licence for application {}"
    ACTION_EXPIRED_APPROVAL_ = "Expire Approval for proposal {}"
    ACTION_DISCARD_PROPOSAL = "Discard application {}"
    ACTION_APPROVAL_LEVEL_DOCUMENT = "Assign Approval level document {}"
    ACTION_SUBMIT_OTHER_DOCUMENTS = 'Submit other documents'
    # Assessors
    ACTION_SAVE_ASSESSMENT_ = "Save assessment {}"
    ACTION_CONCLUDE_ASSESSMENT_ = "Conclude assessment {}"
    ACTION_PROPOSED_APPROVAL = "Application {} has been proposed for approval"
    ACTION_PROPOSED_DECLINE = "Application {} has been proposed for decline"

    ACTION_ENTER_REQUIREMENTS = "Enter Requirements for proposal {}"
    ACTION_BACK_TO_PROCESSING = "Back to processing for proposal {}"

    #Approval
    ACTION_REISSUE_APPROVAL = "Reissue licence for application {}"
    ACTION_CANCEL_APPROVAL = "Cancel licence for application {}"
    ACTION_EXTEND_APPROVAL = "Extend licence"
    ACTION_SUSPEND_APPROVAL = "Suspend licence for application {}"
    ACTION_REINSTATE_APPROVAL = "Reinstate licence for application {}"
    ACTION_SURRENDER_APPROVAL = "Surrender licence for application {}"
    ACTION_RENEW_PROPOSAL = "Create Renewal application for application {}"
    ACTION_AMEND_PROPOSAL = "Create Amendment application for application {}"
    #Vessel
    ACTION_CREATE_VESSEL = "Create Vessel {}"
    ACTION_EDIT_VESSEL= "Edit Vessel {}"
    ACTION_PUT_ONHOLD = "Put Application On-hold {}"
    ACTION_REMOVE_ONHOLD = "Remove Application On-hold {}"
    ACTION_WITH_QA_OFFICER = "Send Application QA Officer {}"
    ACTION_QA_OFFICER_COMPLETED = "QA Officer Assessment Completed {}"

    # monthly invoicing by cron
    ACTION_SEND_BPAY_INVOICE = "Send BPAY invoice {} for application {} to {}"
    ACTION_SEND_MONTHLY_INVOICE = "Send monthly invoice {} for application {} to {}"
    ACTION_SEND_MONTHLY_CONFIRMATION = "Send monthly confirmation for booking ID {}, for application {} to {}"
    ACTION_SEND_PAYMENT_DUE_NOTIFICATION = "Send monthly invoice/BPAY payment due notification {} for application {} to {}"

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ('-when',)

    @classmethod
    def log_action(cls, proposal, action, user=None):
        return cls.objects.create(
            proposal=proposal,
            who=user,
            what=str(action)
        )

    who = models.ForeignKey(EmailUser, null=True, blank=True)
    when = models.DateTimeField(null=False, blank=False, auto_now_add=True)
    what = models.TextField(blank=False)
    proposal = models.ForeignKey(Proposal, related_name='action_logs')


class ProposalRequirement(OrderedModel):
    RECURRENCE_PATTERNS = [(1, 'Weekly'), (2, 'Monthly'), (3, 'Yearly')]
    standard_requirement = models.ForeignKey(ProposalStandardRequirement,null=True,blank=True)
    free_requirement = models.TextField(null=True,blank=True)
    standard = models.BooleanField(default=True)
    proposal = models.ForeignKey(Proposal,related_name='requirements')
    due_date = models.DateField(null=True,blank=True)
    recurrence = models.BooleanField(default=False)
    recurrence_pattern = models.SmallIntegerField(choices=RECURRENCE_PATTERNS,default=1)
    recurrence_schedule = models.IntegerField(null=True,blank=True)
    copied_from = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    copied_for_renewal = models.BooleanField(default=False)
    require_due_date = models.BooleanField(default=False)

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def requirement(self):
        return self.standard_requirement.text if self.standard else self.free_requirement

    def can_referral_edit(self,user):
        if self.proposal.processing_status=='with_referral':
            if self.referral_group:
                group =  ReferralRecipientGroup.objects.filter(id=self.referral_group.id)
                #user=request.user
                if group and group[0] in user.referralrecipientgroup_set.all():
                    return True
                else:
                    return False
        return False

    def can_district_assessor_edit(self,user):
        allowed_status=['with_district_assessor', 'partially_approved', 'partially_declined']
        if self.district_proposal and self.district_proposal.processing_status=='with_assessor_requirements' and self.proposal.processing_status in allowed_status:
            if self.district_proposal.can_process_requirements(user):
                return True
        return False

    def add_documents(self, request):
        with transaction.atomic():
            try:
                # save the files
                data = json.loads(request.data.get('data'))
                if not data.get('update'):
                    documents_qs = self.requirement_documents.filter(input_name='requirement_doc', visible=True)
                    documents_qs.delete()
                for idx in range(data['num_files']):
                    _file = request.data.get('file-'+str(idx))
                    document = self.requirement_documents.create(_file=_file, name=_file.name)
                    document.input_name = data['input_name']
                    document.can_delete = True
                    document.save()
                # end save documents
                self.save()
            except:
                raise
        return



#@python_2_unicode_compatible
##class ProposalStandardRequirement(models.Model):
#class ChecklistQuestion(RevisionedMixin):
#    TYPE_CHOICES = (
#        ('assessor_list','Assessor Checklist'),
#        ('referral_list','Referral Checklist')
#    )
#    ANSWER_TYPE_CHOICES = (
#        ('yes_no','Yes/No type'),
#        ('free_text','Free text type')
#    )
#    text = models.TextField()
#    list_type = models.CharField('Checklist type', max_length=30, choices=TYPE_CHOICES,
#                                         default=TYPE_CHOICES[0][0])
#    answer_type = models.CharField('Answer type', max_length=30, choices=ANSWER_TYPE_CHOICES,
#                                         default=ANSWER_TYPE_CHOICES[0][0])
#
#    #correct_answer= models.BooleanField(default=False)
#    #application_type = models.ForeignKey(ApplicationType,blank=True, null=True)
#    obsolete = models.BooleanField(default=False)
#    order = models.PositiveSmallIntegerField(default=1)
#
#    def __str__(self):
#        return self.text
#
#    class Meta:
#        app_label = 'mooringlicensing'
#
#
#class ProposalAssessment(RevisionedMixin):
#    proposal=models.ForeignKey(Proposal, related_name='assessment')
#    completed = models.BooleanField(default=False)
#    submitter = models.ForeignKey(EmailUser, blank=True, null=True, related_name='proposal_assessment')
#    #referral_assessment=models.BooleanField(default=False)
#    #referral_group = models.ForeignKey(ReferralRecipientGroup,null=True,blank=True,related_name='referral_assessment')
#    #referral=models.ForeignKey(Referral, related_name='assessment',blank=True, null=True )
#    # def __str__(self):
#    #     return self.proposal
#
#    class Meta:
#        app_label = 'mooringlicensing'
#        unique_together = ('proposal',)
#
#    @property
#    def checklist(self):
#        return self.answers.all()
#
#
#class ProposalAssessmentAnswer(RevisionedMixin):
#    question=models.ForeignKey(ChecklistQuestion, related_name='answers')
#    answer = models.NullBooleanField()
#    assessment=models.ForeignKey(ProposalAssessment, related_name='answers', null=True, blank=True)
#    text_answer= models.CharField(max_length=256, blank=True, null=True)
#
#    def __str__(self):
#        return self.question.text
#
#    class Meta:
#        app_label = 'mooringlicensing'
#        verbose_name = "Assessment answer"
#        verbose_name_plural = "Assessment answers"


@receiver(pre_delete, sender=Proposal)
def delete_documents(sender, instance, *args, **kwargs):
    for document in instance.documents.all():
        document.delete()

def clone_proposal_with_status_reset(original_proposal):
    """
    To Test:
         from mooringlicensing.components.proposals.models import clone_proposal_with_status_reset
         p=Proposal.objects.get(id=57)
         p0=clone_proposal_with_status_reset(p)
    """
    with transaction.atomic():
        try:
            proposal = type(original_proposal.child_obj).objects.create()
            print("type(proposal)")
            print(type(proposal))

            proposal.customer_status = 'draft'
            proposal.processing_status = 'draft'
            proposal.previous_application = original_proposal
            proposal.approval = original_proposal.approval

            proposal.save(no_revision=True)
            return proposal
        except:
            raise

def searchKeyWords(searchWords, searchProposal, searchApproval, searchCompliance, is_internal= True):
    from mooringlicensing.utils import search, search_approval, search_compliance
    from mooringlicensing.components.approvals.models import Approval
    from mooringlicensing.components.compliances.models import Compliance
    qs = []
    application_types=[ApplicationType.TCLASS, ApplicationType.EVENT, ApplicationType.FILMING]
    if is_internal:
        #proposal_list = Proposal.objects.filter(application_type__name='T Class').exclude(processing_status__in=['discarded','draft'])
        proposal_list = Proposal.objects.filter(application_type__name__in=application_types).exclude(processing_status__in=['discarded','draft'])
        approval_list = Approval.objects.all().order_by('lodgement_number', '-issue_date').distinct('lodgement_number')
        compliance_list = Compliance.objects.all()
    if searchWords:
        if searchProposal:
            for p in proposal_list:
                #if p.data:
                if p.search_data:
                    try:
                        #results = search(p.data[0], searchWords)
                        results = search(p.search_data, searchWords)
                        final_results = {}
                        if results:
                            for r in results:
                                for key, value in r.items():
                                    final_results.update({'key': key, 'value': value})
                            res = {
                                'number': p.lodgement_number,
                                'id': p.id,
                                'type': 'Proposal',
                                'applicant': p.applicant,
                                'text': final_results,
                                }
                            qs.append(res)
                    except:
                        raise
        if searchApproval:
            for a in approval_list:
                try:
                    results = search_approval(a, searchWords)
                    qs.extend(results)
                except:
                    raise
        if searchCompliance:
            for c in compliance_list:
                try:
                    results = search_compliance(c, searchWords)
                    qs.extend(results)
                except:
                    raise
    return qs

def search_reference(reference_number):
    from mooringlicensing.components.approvals.models import Approval
    from mooringlicensing.components.compliances.models import Compliance
    proposal_list = Proposal.objects.all().exclude(processing_status__in=['discarded'])
    approval_list = Approval.objects.all().order_by('lodgement_number', '-issue_date').distinct('lodgement_number')
    compliance_list = Compliance.objects.all().exclude(processing_status__in=['future'])
    record = {}
    try:
        result = proposal_list.get(lodgement_number = reference_number)
        record = {  'id': result.id,
                    'type': 'proposal' }
    except Proposal.DoesNotExist:
        try:
            result = approval_list.get(lodgement_number = reference_number)
            record = {  'id': result.id,
                        'type': 'approval' }
        except Approval.DoesNotExist:
            try:
                for c in compliance_list:
                    if c.reference == reference_number:
                        record = {  'id': c.id,
                                    'type': 'compliance' }
            except:
                raise ValidationError('Record with provided reference number does not exist')
    if record:
        return record
    else:
        raise ValidationError('Record with provided reference number does not exist')

from ckeditor.fields import RichTextField
class HelpPage(models.Model):
    HELP_TEXT_EXTERNAL = 1
    HELP_TEXT_INTERNAL = 2
    HELP_TYPE_CHOICES = (
        (HELP_TEXT_EXTERNAL, 'External'),
        (HELP_TEXT_INTERNAL, 'Internal'),
    )

    #application_type = models.ForeignKey(ApplicationType)
    #application_type = models.CharField(max_length=10, blank=True, null=True)
    content = RichTextField()
    description = models.CharField(max_length=256, blank=True, null=True)
    help_type = models.SmallIntegerField('Help Type', choices=HELP_TYPE_CHOICES, default=HELP_TEXT_EXTERNAL)
    version = models.SmallIntegerField(default=1, blank=False, null=False)

    class Meta:
        app_label = 'mooringlicensing'
        unique_together = (
                #'application_type',
                'help_type',
                'version'
                )


import reversion
reversion.register(Proposal, follow=["waitinglistapplication", "annualadmissionapplication", "authoriseduserapplication", "mooringlicenceapplication",
    "documents","comms_logs",
    "insurance_certificate_documents","hull_identification_number_documents", "electoral_roll_documents","mooring_report_documents",
    "written_proof_documents","signed_licence_agreement_documents","proof_of_identity_documents",
    "proposalrequest_set","proposaldeclineddetails",
    "requirements","compliances","approvals",
    ])
reversion.register(WaitingListApplication)
reversion.register(AnnualAdmissionApplication)
reversion.register(AuthorisedUserApplication)
reversion.register(MooringLicenceApplication)
reversion.register(ProposalDocument)
reversion.register(ProposalLogDocument)
reversion.register(ProposalLogEntry, follow=["documents"])
reversion.register(InsuranceCertificateDocument)
reversion.register(HullIdentificationNumberDocument)
reversion.register(ElectoralRollDocument)
reversion.register(MooringReportDocument)
reversion.register(WrittenProofDocument)
reversion.register(SignedLicenceAgreementDocument)
reversion.register(ProofOfIdentityDocument)
reversion.register(ProposalRequest)
reversion.register(ProposalDeclinedDetails)
reversion.register(ProposalRequirement, follow=["requirement_documents",])
reversion.register(RequirementDocument)

reversion.register(MooringBay)
reversion.register(Mooring, follow=["mooring_bay", "mooring_licence"])
reversion.register(MooringLogDocument)
reversion.register(MooringLogEntry, follow=["documents"])
reversion.register(MooringUserAction)

reversion.register(Vessel, follow=["blocking_owner",])
reversion.register(VesselLogDocument)
reversion.register(VesselLogEntry, follow=["documents"])
reversion.register(VesselDetails, follow=["vessel"])
reversion.register(CompanyOwnership, follow=["blocking_proposal", "vessel", "company"])
reversion.register(VesselOwnership, follow=["owner", "vessel", "company_ownership"])
reversion.register(Owner)
reversion.register(Company)
reversion.register(ProposalType)

