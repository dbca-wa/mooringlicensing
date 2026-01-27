from __future__ import unicode_literals
from django.core.files.storage import FileSystemStorage
from django_countries.fields import CountryField
from dateutil.relativedelta import relativedelta

import datetime
from decimal import Decimal
import traceback

import pytz
import uuid
from mooringlicensing.components.approvals.email import send_aup_revoked_due_to_mooring_swap_email
from mooringlicensing.components.proposals.email import send_aua_declined_by_endorser_email

from mooringlicensing.ledger_api_utils import (
    retrieve_email_userro, get_invoice_payment_status, retrieve_system_user
)
from ledger_api_client.utils import calculate_excl_gst, get_invoice_properties, cancel_invoice
from mooringlicensing.settings import (
    PROPOSAL_TYPE_SWAP_MOORINGS, TIME_ZONE,
    GROUP_ASSESSOR_MOORING_LICENCE, 
    GROUP_APPROVER_MOORING_LICENCE, 
    PRIVATE_MEDIA_STORAGE_LOCATION, PRIVATE_MEDIA_BASE_URL,
    PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL, 
    PROPOSAL_TYPE_NEW, CODE_DAYS_FOR_ENDORSER_AUA, STICKER_EXPORT_RUN_TIME_MESSAGE
)

from django.db import models, transaction
from django.dispatch import receiver
from django.db.models.signals import pre_delete
from django.core.exceptions import ValidationError, ObjectDoesNotExist, ImproperlyConfigured
from django.db.models import JSONField
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from django.urls import reverse
from ledger_api_client.ledger_models import EmailUserRO
from ledger_api_client.ledger_models import Invoice
from mooringlicensing import exceptions, settings
from mooringlicensing.components.main.models import (
    CommunicationsLogEntry,
    GlobalSettings,
    UserAction,
    Document, ApplicationType, NumberOfDaysType, NumberOfDaysSetting, RevisionedMixin, SanitiseMixin
)

import requests
import ledger_api_client

from mooringlicensing.components.proposals.email import (
    send_application_approved_or_declined_email,
    send_amendment_email_notification,
    send_confirmation_email_upon_submit,
    send_approver_approve_decline_email_notification,
    send_proposal_approver_sendback_email_notification, send_endorsement_of_authorised_user_application_email,
    send_documents_upload_for_mooring_licence_application_email,
    send_other_documents_submitted_notification_email, send_notification_email_upon_submit_to_assessor,
    send_au_summary_to_ml_holder, send_application_discarded_email,
)
from mooringlicensing.ordered_model import OrderedModel
import copy
from django.db.models import Q, Max
from rest_framework import serializers
from ledger_api_client.managed_models import SystemUser
from mooringlicensing.components.users.utils import get_user_name

import logging

logger = logging.getLogger(__name__)
logger_for_payment = logging.getLogger(__name__)

private_storage = FileSystemStorage(  # We want to store files in secure place (outside of the media folder)
    location=PRIVATE_MEDIA_STORAGE_LOCATION,
    base_url=PRIVATE_MEDIA_BASE_URL,
)

def update_proposal_doc_filename(instance, filename):
    return '{}/proposals/{}/documents/{}'.format(settings.MEDIA_APP_DIR, instance.proposal.id,filename)

def update_onhold_doc_filename(instance, filename):
    return '{}/proposals/{}/on_hold/{}'.format(settings.MEDIA_APP_DIR, instance.proposal.id,filename)

def update_proposal_required_doc_filename(instance, filename):
    return '{}/proposals/{}/required_documents/{}'.format(settings.MEDIA_APP_DIR, instance.proposal.id,filename)

def update_proposal_comms_log_filename(instance, filename):
    return '{}/proposals/{}/communications/{}/{}'.format(settings.MEDIA_APP_DIR, instance.log_entry.proposal.id, instance.log_entry.id, filename)

def update_vessel_comms_log_filename(instance, filename):
    return '{}/vessels/{}/communications/{}/{}'.format(settings.MEDIA_APP_DIR, instance.log_entry.vessel.id, instance.log_entry.id, filename)

def update_mooring_comms_log_filename(instance, filename):
    return '{}/moorings/{}/communications/{}/{}'.format(settings.MEDIA_APP_DIR, instance.log_entry.mooring.id, instance.log_entry.id, filename)

#copied from helpers
def is_applicant_postal_address_set(instance):
    applicant = instance.proposal_applicant
    return applicant and (applicant.postal_address_line1 and
        applicant.postal_address_locality and
        applicant.postal_address_state and
        applicant.postal_address_country and 
        applicant.postal_address_postcode)

class ProposalDocument(Document):
    proposal = models.ForeignKey('Proposal',related_name='documents', on_delete=models.CASCADE)
    _file = models.FileField(storage=private_storage,upload_to=update_proposal_doc_filename, max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Document"


VESSEL_TYPES = (
        ('catamaran', 'Catamaran'),
        ('bow_rider', 'Bow Rider'),
        ('cabin_ruiser', 'Cabin Cruiser'),
        ('centre_console', 'Centre Console'),
        ('ferry', 'Ferry'),
        ('rigid_inflatable', 'Rigid Inflatable'),
        ('half_cabin', 'Half Cabin'),
        ('inflatable', 'Inflatable'),
        ('launch', 'Launch'),
        ('motor_sailer', 'Motor Sailer'),
        ('multihull', 'Multihull'),
        ('open_boat', 'Open Boat'),
        ('power_boat', 'Power Boat'),
        ('pwc', 'PWC'),
        ('Runabout', 'Runabout'),
        ('fishing_boat', 'Fishing Boat'),
        ('tender', 'Tender'),
        ('walkaround', 'Walkaround'),
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

class ProposalTypeManager(models.Manager):
    def get_by_natural_key(self, code):
        return self.get(code=code)

class ProposalType(models.Model):
    code = models.CharField(max_length=30, blank=True, null=True, unique=True)
    description = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return self.description if self.description else ''
    
    objects = ProposalTypeManager()

    class Meta:
        app_label = 'mooringlicensing'

    def natural_key(self):
        return (self.code,)


class ProposalProofOfIdentityDocument(models.Model):
    proof_of_identity_document = models.ForeignKey('ProofOfIdentityDocument', on_delete=models.CASCADE)
    proposal = models.ForeignKey('Proposal', on_delete=models.CASCADE)
    enabled = models.BooleanField(default=True)

    class Meta:
        app_label = 'mooringlicensing'


class ProposalMooringReportDocument(models.Model):
    mooring_report_document = models.ForeignKey('MooringReportDocument', on_delete=models.CASCADE)
    proposal = models.ForeignKey('Proposal', on_delete=models.CASCADE)
    enabled = models.BooleanField(default=True)

    class Meta:
        app_label = 'mooringlicensing'


class ProposalWrittenProofDocument(models.Model):
    written_proof_document = models.ForeignKey('WrittenProofDocument', on_delete=models.CASCADE)
    proposal = models.ForeignKey('Proposal', on_delete=models.CASCADE)
    enabled = models.BooleanField(default=True)

    class Meta:
        app_label = 'mooringlicensing'


class ProposalSignedLicenceAgreementDocument(models.Model):
    signed_licence_agreement_document = models.ForeignKey('SignedLicenceAgreementDocument', on_delete=models.CASCADE)
    proposal = models.ForeignKey('Proposal', on_delete=models.CASCADE)
    enabled = models.BooleanField(default=True)

    class Meta:
        app_label = 'mooringlicensing'

class Proposal(RevisionedMixin):

    CUSTOMER_STATUS_DRAFT = 'draft'
    CUSTOMER_STATUS_WITH_ASSESSOR = 'with_assessor'
    CUSTOMER_STATUS_WITH_APPROVER = 'with_approver'
    CUSTOMER_STATUS_AWAITING_ENDORSEMENT = 'awaiting_endorsement'
    CUSTOMER_STATUS_AWAITING_DOCUMENTS = 'awaiting_documents'
    CUSTOMER_STATUS_STICKER_TO_BE_RETURNED = 'sticker_to_be_returned'
    CUSTOMER_STATUS_PRINTING_STICKER = 'printing_sticker'
    CUSTOMER_STATUS_APPROVED = 'approved'
    CUSTOMER_STATUS_DECLINED = 'declined'
    CUSTOMER_STATUS_DISCARDED = 'discarded'
    CUSTOMER_STATUS_AWAITING_PAYMENT = 'awaiting_payment'
    CUSTOMER_STATUS_EXPIRED = 'expired'
    CUSTOMER_STATUS_CHOICES = (
        (CUSTOMER_STATUS_DRAFT, 'Draft'),
        (CUSTOMER_STATUS_WITH_ASSESSOR, 'Under Review'),
        (CUSTOMER_STATUS_WITH_APPROVER, 'Under Review'),
        (CUSTOMER_STATUS_AWAITING_ENDORSEMENT, 'Awaiting Endorsement'),
        (CUSTOMER_STATUS_AWAITING_DOCUMENTS, 'Awaiting Documents'),
        (CUSTOMER_STATUS_STICKER_TO_BE_RETURNED, 'Sticker to be Returned'),
        (CUSTOMER_STATUS_PRINTING_STICKER, 'Printing Sticker'),
        (CUSTOMER_STATUS_APPROVED, 'Approved'),
        (CUSTOMER_STATUS_DECLINED, 'Declined'),
        (CUSTOMER_STATUS_DISCARDED, 'Discarded'),
        (CUSTOMER_STATUS_AWAITING_PAYMENT, 'Awaiting Payment'),
        (CUSTOMER_STATUS_EXPIRED, 'Expired'),
    )

    # List of statuses from above that allow a customer to edit an application.
    CUSTOMER_EDITABLE_STATE = [
        CUSTOMER_STATUS_DRAFT,
    ]

    # List of statuses from above that allow a customer to view an application (read-only)
    CUSTOMER_VIEWABLE_STATE = [
        CUSTOMER_STATUS_WITH_ASSESSOR,
        CUSTOMER_STATUS_WITH_APPROVER,
        CUSTOMER_STATUS_AWAITING_PAYMENT,
        CUSTOMER_STATUS_STICKER_TO_BE_RETURNED,
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
    PROCESSING_STATUS_STICKER_TO_BE_RETURNED = 'sticker_to_be_returned'
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
        (PROCESSING_STATUS_STICKER_TO_BE_RETURNED, 'Sticker to be Returned'),
        (PROCESSING_STATUS_PRINTING_STICKER, 'Printing Sticker'),
        (PROCESSING_STATUS_AWAITING_ENDORSEMENT, 'Awaiting Endorsement'),
        (PROCESSING_STATUS_AWAITING_DOCUMENTS, 'Awaiting Documents'),
        (PROCESSING_STATUS_APPROVED, 'Approved'),
        (PROCESSING_STATUS_DECLINED, 'Declined'),
        (PROCESSING_STATUS_DISCARDED, 'Discarded'),
        (PROCESSING_STATUS_AWAITING_PAYMENT, 'Awaiting Payment'),
        (PROCESSING_STATUS_EXPIRED, 'Expired'),
    )

    proposal_type = models.ForeignKey(ProposalType, blank=True, null=True, on_delete=models.SET_NULL)

    proposed_issuance_approval = JSONField(blank=True, null=True)

    invoice_property_cache = JSONField(null=True, blank=True, default=dict)

    reissue_vessel_properties = JSONField(null=True, blank=True, default=dict) #store vessel and vessel ownership details for a reissued approval to compare to on re-approval

    customer_status = models.CharField('Customer Status', 
        max_length=40, choices=CUSTOMER_STATUS_CHOICES,
        default=CUSTOMER_STATUS_CHOICES[0][0])

    lodgement_number = models.CharField(max_length=9, blank=True, default='')

    lodgement_date = models.DateTimeField(blank=True, null=True)

    submitter = models.IntegerField(blank=True, null=True)

    assigned_officer = models.IntegerField(blank=True, null=True)
    assigned_approver = models.IntegerField(blank=True, null=True)
    processing_status = models.CharField('Processing Status', 
        max_length=40, choices=PROCESSING_STATUS_CHOICES,
        default=PROCESSING_STATUS_CHOICES[0][0])

    approval = models.ForeignKey('mooringlicensing.Approval',null=True,blank=True, on_delete=models.SET_NULL)
    previous_application = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, related_name="succeeding_proposals")

    proposed_decline_status = models.BooleanField(default=False)
    title = models.CharField(max_length=255,null=True,blank=True)

    #If the proposal is created as part of migration of approvals
    migrated = models.BooleanField(default=False)
    
    vessel_details = models.ForeignKey('VesselDetails', blank=True, null=True, on_delete=models.SET_NULL)
    vessel_ownership = models.ForeignKey('VesselOwnership', blank=True, null=True, on_delete=models.SET_NULL)
    # draft proposal status VesselDetails records - goes to VesselDetails master record after submit
    rego_no = models.CharField(max_length=200, blank=True, null=True)
    vessel_id = models.IntegerField(null=True,blank=True)
    vessel_type = models.CharField(max_length=20, choices=VESSEL_TYPES, blank=True)
    vessel_name = models.CharField(max_length=400, blank=True)
    vessel_length = models.DecimalField(max_digits=8, decimal_places=2, null=True) # does not exist in MB
    vessel_draft = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    vessel_beam = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    vessel_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True) # tonnage
    berth_mooring = models.CharField(max_length=200, blank=True)
    # only for draft status proposals, otherwise retrieve from within vessel_ownership
    dot_name = models.CharField(max_length=200, blank=True, null=True)
    percentage = models.IntegerField(null=True, blank=True)
    individual_owner = models.BooleanField(null=True)
    company_ownership_percentage = models.IntegerField(null=True, blank=True)
    company_ownership_name = models.CharField(max_length=200, blank=True, null=True)
    ## Insurance component field
    insurance_choice = models.CharField(max_length=20, choices=INSURANCE_CHOICES, blank=True)
    
    ## WLA
    preferred_bay = models.ForeignKey('MooringBay', null=True, blank=True, on_delete=models.SET_NULL)
    ## Electoral Roll component field
    silent_elector = models.BooleanField(null=True) # if False, user is on electoral roll
    
    # AUA
    mooring_authorisation_preference = models.CharField(max_length=20, choices=MOORING_AUTH_PREFERENCES, blank=True)
    bay_preferences_numbered = ArrayField(
            models.IntegerField(null=True, blank=True),
            blank=True,null=True,
            )
    
    ## MLA
    allocated_mooring = models.ForeignKey('Mooring', null=True, blank=True, on_delete=models.SET_NULL, related_name="ria_generated_proposal")
    waiting_list_allocation = models.ForeignKey('mooringlicensing.WaitingListAllocation',null=True,blank=True, related_name="ria_generated_proposal", on_delete=models.SET_NULL)
    date_invited = models.DateField(blank=True, null=True)  # The date RIA has invited the WLAllocation holder.  This application is expired in a configurable number of days after the invitation without submit.
    invitee_reminder_sent = models.BooleanField(default=False)
    invitee_reminder_date = models.DateTimeField(blank=True, null=True)
    temporary_document_collection_id = models.IntegerField(blank=True, null=True)
    # MLA documents
    proof_of_identity_documents = models.ManyToManyField('ProofOfIdentityDocument', through=ProposalProofOfIdentityDocument)
    mooring_report_documents = models.ManyToManyField('MooringReportDocument', through=ProposalMooringReportDocument)
    written_proof_documents = models.ManyToManyField('WrittenProofDocument', through=ProposalWrittenProofDocument)
    signed_licence_agreement_documents = models.ManyToManyField('SignedLicenceAgreementDocument', through=ProposalSignedLicenceAgreementDocument)

    # AUA amendment
    listed_moorings = models.ManyToManyField('Mooring', related_name='listed_on_proposals')
    keep_existing_mooring = models.BooleanField(default=True)
    
    # MLA amendment
    listed_vessels = models.ManyToManyField('VesselOwnership', 'listed_on_proposals')
    keep_existing_vessel = models.BooleanField(default=True)

    fee_season = models.ForeignKey('FeeSeason', null=True, blank=True, on_delete=models.SET_NULL)  # In some case, proposal doesn't have any fee related objects.  Which results in the impossibility to retrieve season, start_date, end_date, etc.
                                                                        # To avoid that, this fee_season field is used in order to store those data.
    auto_approve = models.BooleanField(default=False)
    null_vessel_on_create = models.BooleanField(default=True)
    payment_reminder_sent = models.BooleanField(default=False)
    payment_due_date = models.DateField(blank=True, null=True) #date when payment is due for future invoices

    bypass_payment_reason = JSONField(blank=True,null=True)

    no_email_notifications = models.BooleanField(default=False)

    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application"
        verbose_name_plural = "Applications"
    
    def bypass_payment(self, request):
        logger.info(f'Bypassing payment for Proposal: [{self}].')
        with transaction.atomic():
            from mooringlicensing.helpers import is_system_admin
            from mooringlicensing.components.payments_ml.models import ApplicationFee, FeeCalculation, FeeItemApplicationFee

            if not is_system_admin(request):
                raise serializers.ValidationError("User not authorised to bypass payment")
            
            if self.processing_status != Proposal.PROCESSING_STATUS_AWAITING_PAYMENT:
                raise serializers.ValidationError("Application not awaiting payment")

            try:
                invoice_reference = request.data['invoice_ref']
            except:
                raise serializers.ValidationError("Invoice reference not provided")

            try:
                bypass_reason = request.data['bypass_payment_reason']
            except:
                raise serializers.ValidationError("Bypass payment reason not provided")

            try:
                record_amount_as_paid = request.data['record_amount_as_paid']
            except:
                raise serializers.ValidationError("Record amount paid option not provided")

            #prepayment logic
            try:
                application_fee = ApplicationFee.objects.filter(invoice_reference=invoice_reference).last()
            except:
                raise serializers.ValidationError("Application fee with provided invoice reference does not exist")
            
            db_processes = {
                        'for_existing_invoice': True,
                        'fee_item_application_fee_ids': [],
                    }
            fee_item_application_fees = FeeItemApplicationFee.objects.filter(application_fee=application_fee)
            for fee_item_application_fee in fee_item_application_fees:
                db_processes['fee_item_application_fee_ids'].append(fee_item_application_fee.id)

            new_fee_calculation = FeeCalculation.objects.create(uuid=application_fee.uuid, data=db_processes)
            
            #preload logic
            try:
                invoice = Invoice.objects.get(reference=invoice_reference)
            except:
                raise serializers.ValidationError("Invoice with provided reference does not exist")
            
            uuid = application_fee.uuid

            if FeeCalculation.objects.filter(uuid=uuid).exists():
                fee_calculation = FeeCalculation.objects.order_by("id").filter(uuid=uuid).last()
            else:
                raise serializers.ValidationError("Fee calculation for application fee uuid does not exist")

            db_operations = fee_calculation.data
            proposal = application_fee.proposal

            if 'for_existing_invoice' in db_operations and db_operations['for_existing_invoice']:
                if record_amount_as_paid:
                    #record the amount as paid, as if a normal payment has just taken place
                    for idx in db_operations['fee_item_application_fee_ids']:
                        fee_item_application_fee = FeeItemApplicationFee.objects.get(id=int(idx))
                        fee_item_application_fee.amount_paid = fee_item_application_fee.amount_to_be_paid
                        fee_item_application_fee.save()
                else:
                    #change the amount to be paid to 0 so that future fees are not affected
                    for idx in db_operations['fee_item_application_fee_ids']:
                        fee_item_application_fee = FeeItemApplicationFee.objects.get(id=int(idx))
                        fee_item_application_fee.amount_to_be_paid = 0
                        fee_item_application_fee.amount_paid = 0
                        fee_item_application_fee.save()

            application_fee.invoice_reference = invoice_reference
            application_fee.handled_in_preload = datetime.datetime.now()

            application_fee.payment_status = 'paid'
            if record_amount_as_paid:
                inv_props = get_invoice_properties(invoice.id)
                if 'data' in inv_props and 'invoice' in inv_props['data']:
                    amount = inv_props['data']['invoice']['amount'] if "amount" in inv_props['data']['invoice'] else ""

                    previous_application_fees = ApplicationFee.objects.filter(proposal=proposal, cancelled=False).filter(Q(payment_status='paid')|Q(payment_status='over_paid')).order_by("handled_in_preload")
                    previous_application_fee_cost = previous_application_fees.last().cost if previous_application_fees.last() else 0.0

                    application_fee.cost = float(amount) + float(previous_application_fee_cost)
            else:
                application_fee.cost = 0

            check_application_fee = ApplicationFee.objects.get(uuid=uuid)
            if check_application_fee.handled_in_preload:
                logger.error(f'Handled in preload flag set to True while attempting to bypass payment')
                raise serializers.ValidationError("Handled in preload flag set to True while attempting to bypass payment")
            
            application_fee.save()

            if application_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY:
                application_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                application_fee.expiry_time = None

                if self.application_type.code in (AuthorisedUserApplication.code, MooringLicenceApplication.code):
                    # For AUA or MLA, as payment has been done, create approval
                    self.child_obj.update_or_create_approval(datetime.datetime.now(pytz.timezone(TIME_ZONE)), request)
                else:
                    raise serializers.ValidationError("Bypassing payment can only be done for AUA and MLA")
                application_fee.handled_in_preload = datetime.datetime.now()
                application_fee.save()

            #fee success logic
            self.refresh_from_db()

            fee_item_application_fees = FeeItemApplicationFee.objects.filter(application_fee=application_fee)
            fee_item_application_fees.update(vessel_details=self.vessel_details)
            
            #cancel invoice
            ledger_cancellation = True
            try:     
                for inv in self.invoices_display():
                    try:
                        inv_props = get_invoice_properties(inv.id)
                        if Decimal(inv_props['data']['invoice']['balance']) > 0:
                            res = cancel_invoice(inv.reference)
                            logger.info(f'Response for cancelling invoice: [{inv.reference}]: {res["message"]}.')
                            if not "message" in res or (res["message"] != 'success' and res["message"] != 'Invoice not found'): #Invoice not found, the invoice does not exist so we do not need to cancel it
                                ledger_cancellation = False
                                continue
                        else:
                            continue #invoice has already been paid for
                    except:
                        ledger_cancellation = False
                        continue
            except Exception as e:  
                ledger_cancellation = False          
                raise serializers.ValidationError("Unable to cancel proposal payment - ledger invoice cancellation failed with error:", str(e))
            
            if not ledger_cancellation:
                raise serializers.ValidationError("Unable to cancel proposal payment - ledger invoice cancellation failed")
            
            logger.info(f"Application payment bypass successful for {self}")
            
        self.bypass_payment_reason = {
                'bypass_time' : datetime.datetime.now().strftime('%d/%m/%Y'),
                'details': bypass_reason,
                'amount_recorded_as_paid': record_amount_as_paid,
            }
        if record_amount_as_paid:
            self.log_user_action(f"Payment for Proposal {self} bypassed. Reason: {bypass_reason}. Invoiced amount recorded as paid for purposes of future fee calculations.")
        else:
            self.log_user_action(f"Payment for Proposal {self} bypassed. Reason: {bypass_reason}. Invoiced amount not recorded as paid for purposes of future fee calculations.")
        self.save()

    def cancel_payment(self, request):
        logger.info(f'Cancelling payment for Proposal: [{self}].')
        with transaction.atomic():
            if not ((self.proposal_applicant and request.user.id == self.proposal_applicant.email_user_id) or self.is_assessor(request.user)):
                raise serializers.ValidationError("User not authorised to cancel proposal payment")

            if self.processing_status != Proposal.PROCESSING_STATUS_AWAITING_PAYMENT and self.processing_status != Proposal.PROCESSING_STATUS_EXPIRED:
                raise serializers.ValidationError("Unable to cancel proposal payment (not awaiting payment)")
            
            #Remove Ledger Invoice - proceed only if successful
            ledger_cancellation = True
            try:     
                for inv in self.invoices_display():
                    try:
                        inv_props = get_invoice_properties(inv.id)
                        if Decimal(inv_props['data']['invoice']['balance']) > 0:
                            res = cancel_invoice(inv.reference)
                            logger.info(f'Response for cancelling invoice: [{inv.reference}]: {res["message"]}.')
                            if not "message" in res or (res["message"] != 'success' and res["message"] != 'Invoice not found'): #Invoice not found, the invoice does not exist so we do not need to cancel it
                                ledger_cancellation = False
                                continue
                        else:
                            continue #invoice has already been paid for
                    except:
                        ledger_cancellation = False
                        continue
            except Exception as e:  
                ledger_cancellation = False          
                raise serializers.ValidationError("Unable to cancel proposal payment - ledger invoice cancellation failed with error:", str(e))
            
            if not ledger_cancellation:
                raise serializers.ValidationError("Unable to cancel proposal payment - ledger invoice cancellation failed")

            #Cancel Application Fees
            self.application_fees.update(cancelled=True)
            #Empty Invoice Property Cache
            self.invoice_propery_cache = {}
            #Set status to discarded
            self.processing_status = Proposal.PROCESSING_STATUS_DISCARDED
            self.save()

            self.child_obj.process_after_discarded()
            send_application_discarded_email(self, request)
        
    #proposals cannot be auto-approved if an existing approval has non-exported stickers
    def approval_has_pending_stickers(self):
        from mooringlicensing.components.approvals.models import Sticker
        return (self.approval != None and self.approval.stickers.filter(status__in=[Sticker.STICKER_STATUS_READY, Sticker.STICKER_STATUS_NOT_READY_YET,]).exists())

    def populate_reissue_vessel_properties(self):

        #get vessel ownership and vessel details of proposal and save them to reissue_vessel_properties
        #these values can then be compared to the new values on approval
        try:
            self.reissue_vessel_properties = {
                "vessel_ownership": {
                    "id": self.vessel_ownership.id,
                    "owner": self.vessel_ownership.owner.id,
                    "vessel": self.vessel_ownership.vessel.id,
                    "percentage": self.vessel_ownership.percentage,
                    "start_date": self.vessel_ownership.start_date.strftime('%d/%m/%Y') if self.vessel_ownership.start_date != None else None,
                    "end_date": self.vessel_ownership.end_date.strftime('%d/%m/%Y') if self.vessel_ownership.end_date != None else None,
                    "created": self.vessel_ownership.created.strftime('%d/%m/%Y') if self.vessel_ownership.created != None else None,
                    "updated": self.vessel_ownership.updated.strftime('%d/%m/%Y') if self.vessel_ownership.updated != None else None,
                    "dot_name": self.vessel_ownership.dot_name,
                    "company_ownerships": list(self.vessel_ownership.company_ownerships.values_list('id',flat=True))
                },
                "vessel_details": {
                    "vessel_type": self.vessel_details.vessel_type,
                    "vessel": self.vessel_details.vessel.id,
                    "berth_mooring": self.vessel_details.berth_mooring,
                    "vessel_beam": str(self.vessel_details.vessel_beam),
                    "vessel_draft": str(self.vessel_details.vessel_draft),
                    "vessel_length": str(self.vessel_details.vessel_length),
                    "vessel_name": self.vessel_details.vessel_name,
                    "vessel_weight": str(self.vessel_details.vessel_weight),
                }
            }
            self.save()
        except Exception as e:
            print(e)
            self.reissue_vessel_properties = {}

    def get_latest_vessel_ownership_by_vessel(self, vessel):
        if self.previous_application:
            if self.previous_application.vessel_ownership:
                if self.previous_application.vessel_ownership.vessel == vessel:
                    # Same vessel is found.
                    return self.previous_application.vessel_ownership
                else:
                    # vessel of the previous application is differenct vessel.  Search further back.
                    return self.previous_application.get_latest_vessel_ownership_by_vessel(vessel)
            else:
                # vessel_ownership is None or so (Null vessel case).  Search further back.
                return self.previous_application.get_latest_vessel_ownership_by_vessel(vessel)
        else:
            # No previous application exists
            return None

    def copy_proof_of_identity_documents(self, proposal):
        for doc in self.proof_of_identity_documents.all():
            link_item = ProposalProofOfIdentityDocument.objects.get(proposal=self, proof_of_identity_document=doc)
            if link_item.enabled:
                # Create link to the proposal only when the doc is not deleted.
                ProposalProofOfIdentityDocument.objects.create(proposal=proposal, proof_of_identity_document=doc)

    def copy_mooring_report_documents(self, proposal):
        for doc in self.mooring_report_documents.all():
            link_item = ProposalMooringReportDocument.objects.get(proposal=self, mooring_report_document=doc)
            if link_item.enabled:
                # Create link to the proposal only when the doc is not deleted.
                ProposalMooringReportDocument.objects.create(proposal=proposal, mooring_report_document=doc)

    def copy_written_proof_documents(self, proposal):
        for doc in self.written_proof_documents.all():
            link_item = ProposalWrittenProofDocument.objects.get(proposal=self, written_proof_document=doc)
            if link_item.enabled:
                # Create link to the proposal only when the doc is not deleted.
                ProposalWrittenProofDocument.objects.create(proposal=proposal, written_proof_document=doc)
        
    def copy_signed_licence_agreement_documents(self, proposal):
        for doc in self.signed_licence_agreement_documents.all():
            link_item = ProposalSignedLicenceAgreementDocument.objects.get(proposal=self, signed_licence_agreement_document=doc)
            if link_item.enabled:
                # Create link to the proposal only when the doc is not deleted.
                ProposalSignedLicenceAgreementDocument.objects.create(proposal=proposal, signed_licence_agreement_document=doc)
                
    def copy_insurance_document(self, proposal):
        try:
            old_insurance_doc = InsuranceCertificateDocument.objects.filter(proposal=self).last()
            if old_insurance_doc:
                new_insurance_doc = old_insurance_doc
                new_insurance_doc.id = None
                new_insurance_doc.proposal = proposal
                new_insurance_doc.save()
        except Exception as e:
            logger.error(e)

                
    def copy_vessel_registration_documents(self, proposal):
        doc_list = VesselRegistrationDocument.objects.filter(proposal=self)
        if doc_list.count() > 0:
            doc = doc_list.last() #get the latest vesssel registration document
            doc.pk = None
            doc.proposal = proposal
            doc.can_delete = True
            doc.save()

    def copy_hull_identification_number_document(self, proposal):
        doc_list = HullIdentificationNumberDocument.objects.filter(proposal=self)
        if doc_list.count() > 0:
            doc = doc_list.last() #get the latest vesssel registration document
            doc.pk = None
            doc.proposal = proposal
            doc.can_delete = True
            doc.save()

    def __str__(self):
        return str(self.lodgement_number)

    def withdraw(self, request, *args, **kwargs):
        #only an assessor should be able to withdraw
        if self.is_assessor(request.user): 
            self.processing_status = Proposal.PROCESSING_STATUS_DISCARDED
            self.save()
            logger.info(f'Status: [{self.processing_status}] has been set to the proposal: [{self}].')
            self.log_user_action(ProposalUserAction.ACTION_WITHDRAW_PROPOSAL.format(self.lodgement_number), request)

            # Perform post-processing for each application type after discarding.
            self.child_obj.process_after_withdrawn()

    def destroy(self, request, *args, **kwargs):
        #only the applicant or an assessor should be able to discard while in draft
        if self.processing_status == Proposal.PROCESSING_STATUS_DRAFT and ((self.proposal_applicant and request.user.id == self.proposal_applicant.email_user_id) or self.is_assessor(request.user)):
            self.processing_status = Proposal.PROCESSING_STATUS_DISCARDED
            self.save()
            logger.info(f'Status: [{self.processing_status}] has been set to the proposal: [{self}].')
            self.log_user_action(ProposalUserAction.ACTION_DISCARD_PROPOSAL.format(self.lodgement_number), request)

            # Perform post-processing for each application type after discarding.
            self.child_obj.process_after_discarded()

            # Send email
            send_application_discarded_email(self, request)

    def copy_vessel_details(self, proposal):
        proposal.rego_no = self.rego_no
        proposal.vessel_id = self.vessel_id
        proposal.vessel_type = self.vessel_type
        proposal.vessel_name = self.vessel_name
        proposal.vessel_length = self.vessel_length
        proposal.vessel_draft = self.vessel_draft
        proposal.vessel_beam = self.vessel_beam
        proposal.vessel_weight = self.vessel_weight
        proposal.berth_mooring = self.berth_mooring

        proposal.dot_name = self.dot_name
        proposal.percentage = self.percentage
        proposal.individual_owner = self.individual_owner
        proposal.company_ownership_percentage = self.company_ownership_percentage
        proposal.company_ownership_name = self.company_ownership_name

        proposal.save()

    def get_previous_vessel_ownerships(self):
        vessel_ownerships = []
        get_out_of_loop = False

        if self.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,]:
            # When the proposal being processed is an amendment/renewal application,
            # we want to exclude the ownership percentages from the previous applications.
            proposal = self

            proposal_id_list = []
            continue_loop = True
            while continue_loop:
                if proposal.id in proposal_id_list:
                    continue_loop = False
                    break
                proposal_id_list.append(proposal.id)

                if proposal.previous_application:
                    if proposal.previous_application.vessel_ownership:
                        vessel_ownerships.append(proposal.previous_application.vessel_ownership)

                if get_out_of_loop:
                    continue_loop = False
                    break

                # Retrieve the previous application
                proposal = proposal.previous_application

                if not proposal:
                    # No previous application exists.  Get out of the loop
                    continue_loop = False
                    break
                else:
                    # Previous application exists
                    if proposal.proposal_type.code in [PROPOSAL_TYPE_NEW,]:
                        # Previous application is 'new'/'renewal'
                        # In this case, we don't want to go back any further once this proposal is processed in the next loop.  Therefore we set the flat to True
                        get_out_of_loop = True

        return list(set(vessel_ownerships))

    @property
    def submitter_obj(self):
        return retrieve_email_userro(self.submitter) if self.submitter else None
    
    @property
    def applicant_obj(self):
        return retrieve_email_userro(
            self.proposal_applicant.email_user_id
        ) if (self.proposal_applicant and 
            self.proposal_applicant.email_user_id
        ) else None

    def get_fee_amount_adjusted(self, fee_item_being_applied, vessel_length, max_amount_paid):
        """
        Retrieve all the fee_items for this vessel
        """
        logger.info(f'Adjusting the fee amount for proposal: [{self}], fee_item: [{fee_item_being_applied}], vessel_length: [{vessel_length}]')
        if not fee_item_being_applied:
            msg = f'FeeItem is None.  Cannot proceed to calculate the fee_amount_adjusted for the proposal: [{self}]...'
            logger.exception(msg)
            raise ValidationError(msg)

        fee_amount_adjusted = fee_item_being_applied.get_absolute_amount(vessel_length)

        annual_admission_type = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)
        if self.proposal_type.code in (PROPOSAL_TYPE_AMENDMENT,) or fee_item_being_applied.application_type == annual_admission_type:
            # When amendment or adjusting an AA component, amount needs to be adjusted
            logger.info(f'Deduct $[{max_amount_paid}] from $[{fee_amount_adjusted}]')
            fee_amount_adjusted = fee_amount_adjusted - max_amount_paid
            logger.info(f'Result amount: $[{fee_amount_adjusted}]')

            fee_amount_adjusted = Decimal('0.00') if fee_amount_adjusted <= 0 else fee_amount_adjusted

        return fee_amount_adjusted

    def get_max_amount_paid_for_main_component(self):
        logger.info(f'Calculating the max amount paid for the main component...')
        max_amount_paid_for_main_component = 0

        if self.proposal_type.code not in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL]:
            prev_application = self.previous_application
            max_amounts_paid = self.get_amounts_paid_so_far(prev_application)  # None: we don't mind vessel for main component
            if self.application_type in max_amounts_paid:
                # When there is an AAP component
                if max_amount_paid_for_main_component < max_amounts_paid[self.application_type]:
                    # Update variable
                    max_amount_paid_for_main_component = max_amounts_paid[self.application_type]

        return max_amount_paid_for_main_component

    def get_max_amount_paid_for_aa_component(self, target_date, vessel=None):
        logger.info(f'Calculating the max amount paid for the AA component, which can be transferred for the vessel: [{vessel}]...')

        max_amount_paid_for_aa_component = 0

        if self.proposal_type.code not in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL]:
            # Get max amount for AA from this proposal history
            max_amount_paid = self.get_amount_paid_so_far_for_aa_through_this_proposal(self.previous_application, vessel)
            if max_amount_paid_for_aa_component < max_amount_paid:
                max_amount_paid_for_aa_component = max_amount_paid

            # Get max amount for this vessel from other current/suspended approvals
            if vessel:
                current_approvals = vessel.get_current_aaps(target_date)
                for approval in current_approvals:
                    # Current approval exists
                    max_amount_paid = self.get_amounts_paid_so_far_for_aa_through_other_approvals(approval.current_proposal, vessel)  # We mind vessel for AA component
                    # When there is an AAP component
                    if max_amount_paid_for_aa_component < max_amount_paid:
                        # Update variable
                        max_amount_paid_for_aa_component = max_amount_paid

        return max_amount_paid_for_aa_component

    def payment_required(self):
        payment_required = False
        if self.application_fees and self.application_fees.filter(cancelled=False).count():
            try:
                application_fee = self.get_main_application_fee()
                invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
                if get_invoice_payment_status(invoice.id) not in ('paid', 'over_paid'):
                    payment_required = True
            except Exception as e:
                logger.error(e)      
        return payment_required

    #NOTE: This function has been implemented as a workaround for a difficult data issued (the cause of which remains undetermined)
    #FeeItemApplicationFee records are being saved with the wrong vessel
    #Should the problem be resolved and the data corrected, this function can (and should be) be retired and removed
    def get_AA_fee_item_application_vessels(self,proposal):
        """ 
        This is a specialised function built for the purpose of working around a data issue with existing vessel fee records
        
        An unknown bug has caused the AA fee item application fees to store only one vessel for the same ML, instead of the actual vessel that the AA item applies to

        Using other records available this function will retrieve the correct vessel records and map them to the ids of:
            FeeItemApplicationFee.objects.filter(application_fee__proposal=proposal, fee_item__fee_constructor__application_type=annual_admission_type)
        
        Correct records can be found via listed_vessels on the proposal (use dimensions to match, ensure every vessel is represented in rare instances where multiple dimensions are the same)

        Restrict this function to ML renewals only
        """
        from mooringlicensing.components.payments_ml.models import FeeItemApplicationFee
        annual_admission_type = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)
        #get fiafs
        fiafs = FeeItemApplicationFee.objects.filter(application_fee__proposal=proposal, fee_item__fee_constructor__application_type=annual_admission_type)
        #get proposal vessels
        vessel_ownerships = proposal.listed_vessels.all()
        vessels = []
        for vo in vessel_ownerships:
            vessels.append(vo.vessel)
        accounted_for = []
        mapped_rego_nos = {}
        missing_size_category = []
        for fiaf in fiafs:
            fix = False
            if fiaf.vessel_details and fiaf.vessel_details.vessel:
                recorded_vessel = fiaf.vessel_details.vessel
                #check if vessel already accounted for
                if recorded_vessel.rego_no in accounted_for:
                    logger.warning(f"Fee Item Application Fee has incorrectly recorded {recorded_vessel.rego_no} in place of the correct rego no, correcting for deduction calculations...")
                    fix = True
                #check if recorded vessel length complies with its own category
                if not fix and fiaf.fee_item and fiaf.fee_item.vessel_size_category:
                    min_length = fiaf.fee_item.vessel_size_category.start_size if fiaf.fee_item.vessel_size_category.include_start_size else 0
                    max_length = fiaf.fee_item.vessel_size_category.get_max_allowed_length()
                    length = fiaf.vessel_details.vessel_applicable_length
                    if length < min_length or length > max_length[0] or (not max_length[1] and length == max_length[0]):
                        logger.warning(f"Fee Item Application Fee has incorrectly recorded {recorded_vessel.rego_no} in place of the correct rego no, correcting for deduction calculations...")
                        fix = True
                elif recorded_vessel and not (fiaf.fee_item and fiaf.fee_item.vessel_size_category):
                    logger.warning(f"Fee Item Application Fee has no vessel size category")
                    missing_size_category.append(fiaf)
                if fix:
                    for vessel in vessels:
                        if vessel.rego_no != recorded_vessel.rego_no:
                            #accounted for?
                            if vessel.rego_no in accounted_for:
                                continue
                            if fiaf.fee_item and fiaf.fee_item.vessel_size_category:
                                min_length = fiaf.fee_item.vessel_size_category.start_size if fiaf.fee_item.vessel_size_category.include_start_size else 0
                                max_length = fiaf.fee_item.vessel_size_category.get_max_allowed_length()

                                vessel_details = VesselDetails.objects.filter(vessel_id=vessel.id).order_by('-id').first()
                                length = vessel_details.vessel_applicable_length
                                #length complies? (if max_length[1] if false then length cannot equal max length, otherwise it is allowed)
                                if length < min_length or length > max_length[0] or (not max_length[1] and length == max_length[0]):
                                    continue
                            else:
                                logger.warning(f"Fee Item Application Fee has no vessel size category")
                                if not fiaf in missing_size_category:
                                    missing_size_category.append(fiaf)
                            #not accounted for, length complies, use this vessel
                            accounted_for.append(vessel.rego_no)
                            mapped_rego_nos[fiaf.id] = vessel
                            break
                else:
                    accounted_for.append(recorded_vessel.rego_no)
                    mapped_rego_nos[fiaf.id] = recorded_vessel
        still_missing = []
        #check if all vessels are accounted for, if not may be due to missing size cats so rearrange
        for vessel in vessels:
            if not vessel.rego_no in accounted_for:
                still_missing.append(vessel)
        if still_missing:
            logger.warning(f"One or more Fee Item Application Fee records cannot be properly accounted for in deductions")
            if missing_size_category:
                logger.warning(f"One or more Fee Item Application Fee records are missing size categories, which has caused problems with determining deductions")

        return mapped_rego_nos

    def get_amount_paid_so_far_for_aa_through_this_proposal(self, proposal, vessel):
        from mooringlicensing.components.payments_ml.models import FeeItemApplicationFee
        from mooringlicensing.components.payments_ml.models import FeeConstructor
        from mooringlicensing.components.approvals.models import MooringLicence, AuthorisedUserPermit, VesselOwnershipOnApproval, ApprovalHistory
        logger.info(f'Calculating the amount paid so far for the AA component through the proposal(s) which leads to the proposal: [{self}]...')

        max_amount_paid = 0
        valid_deductions = 0
        previously_applied_deductions = 0

        max_amount_paid_per_vessel = {}
        
        target_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        target_date = target_datetime.date()
        annual_admission_type = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)

        proposal_id_list = []
        continue_loop = True

        target_proposal = proposal
        latest_vessel_ownership = VesselOwnership.objects.filter(vessel=vessel,end_date=None).order_by('-id').first()

        # run loop to first find BASE AMOUNT PAID FOR THE TARGET VESSEL
        # run a second loop to find VALID DEDUCTIONS
        # run a third loop to find PREVIOUSLY APPLIED DEDUCTIONS
        # Subtract third loop results from second loop - add second loop results to first loop

        # first loop - payments for the target vessel
        while continue_loop:
            if proposal:
                if proposal.id in proposal_id_list:
                    continue_loop = False
                    break
                proposal_id_list.append(proposal.id)

                fee_item_application_fee_vessels = []
                if proposal.proposal_type.code == PROPOSAL_TYPE_RENEWAL and type(proposal.child_obj) == MooringLicenceApplication:
                    #specialised function to get CORRECT fee_item_application_fee vessels 
                    fee_item_application_fee_vessels = self.get_AA_fee_item_application_vessels(proposal)

                for fee_item_application_fee in FeeItemApplicationFee.objects.filter(application_fee__proposal=proposal, fee_item__fee_constructor__application_type=annual_admission_type):
                    # We are interested only in the AnnualAdmission component
                    logger.info(f'FeeItemApplicationFee: [{fee_item_application_fee}] found through the proposal: [{proposal}]')
                    try:
                        target_vessel = fee_item_application_fee.vessel_details.vessel
                        if proposal.proposal_type.code == PROPOSAL_TYPE_RENEWAL and type(proposal.child_obj) == MooringLicenceApplication:
                            incorrect_vessel = target_vessel
                            target_vessel = fee_item_application_fee_vessels[fee_item_application_fee.id]
                            if incorrect_vessel != target_vessel:
                                logger.warning(f"FeeItemApplicationFee: [{fee_item_application_fee}] incorrectly recorded {incorrect_vessel.rego_no} as vessel. Correct vessel should be {target_vessel.rego_no} which has been substituted for calculations.")
                    except:
                        logger.warning("Application fee missing vessel details - invoices may require review")
                        target_vessel = None

                    # Retrieve the current approvals of the target_vessel
                    if target_vessel:
                        current_approvals = target_vessel.get_current_approvals(target_date)
                        logger.info(f'Current approvals for the vessel: [{target_vessel}]: {current_approvals}')

                        if (not proposal.vessel_ownership and vessel == target_vessel) or proposal.vessel_ownership == latest_vessel_ownership:
                            # This is paid for AA component for a target_vessel
                            # In this case, we can transfer this amount
                            amount_paid = fee_item_application_fee.amount_paid if fee_item_application_fee.amount_paid else 0
        
                            max_amount_paid += amount_paid
                            logger.info(f'Amount: [{amount_paid}] has been factored in to the current max AA amount paid.')
                            if amount_paid > 0:
                                logger.info(f'Transferable amount: [{fee_item_application_fee}], which already has been paid.')
                        else:
                            #for tracking max payments of other vessels - used to determine potential deductions where no payment exists (for all but the vessel on this proposal)
                            amount_paid = fee_item_application_fee.amount_paid if fee_item_application_fee.amount_paid else 0
                            if target_vessel.rego_no in max_amount_paid_per_vessel:
                                max_amount_paid_per_vessel[target_vessel.rego_no] += amount_paid
                            else:
                                max_amount_paid_per_vessel[target_vessel.rego_no] = amount_paid
             
                if proposal.proposal_type.code in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL, ]:
                    # Now, 'prev_application' is the very first application for this season
                    # We are not interested in any older applications
                    continue_loop = False
                    break
                else:
                    # Assign the previous application, then perform checking above again
                    proposal = proposal.previous_application
            else:
                continue_loop = False
                break

        proposal = target_proposal
        proposal_id_list = []
        continue_loop = True
        # second loop - applicable deductions from all valid approval proposals
        while continue_loop:
            if proposal:
                if proposal.id in proposal_id_list:
                    continue_loop = False
                    break
                proposal_id_list.append(proposal.id)

                fee_item_application_fee_vessels = []
                if proposal.proposal_type.code == PROPOSAL_TYPE_RENEWAL and type(proposal.child_obj) == MooringLicenceApplication:
                    #specialised function to get CORRECT fee_item_application_fee vessels 
                    fee_item_application_fee_vessels = self.get_AA_fee_item_application_vessels(proposal)

                for fee_item_application_fee in FeeItemApplicationFee.objects.filter(application_fee__proposal=proposal, fee_item__fee_constructor__application_type=annual_admission_type):
                    # We are interested only in the AnnualAdmission component
                    logger.info(f'FeeItemApplicationFee: [{fee_item_application_fee}] found through the proposal: [{proposal}]')
                    try:
                        target_vessel = fee_item_application_fee.vessel_details.vessel
                        if proposal.proposal_type.code == PROPOSAL_TYPE_RENEWAL and type(proposal.child_obj) == MooringLicenceApplication:
                            incorrect_vessel = target_vessel
                            target_vessel = fee_item_application_fee_vessels[fee_item_application_fee.id]
                            if incorrect_vessel != target_vessel:
                                logger.warning(f"FeeItemApplicationFee: [{fee_item_application_fee}] incorrectly recorded {incorrect_vessel.rego_no} as vessel. Correct vessel should be {target_vessel.rego_no} which has been substituted for calculations.")
                    except:
                        logger.warning("Application fee missing vessel details - invoices may require review")
                        target_vessel = None

                    # Retrieve the current approvals of the target_vessel
                    if target_vessel and target_proposal and target_proposal.proposal_applicant:
                        current_approvals = target_vessel.get_current_approvals(target_date)
                        logger.info(f'Current approvals for the vessel: [{target_vessel}]: {current_approvals}')

                        #filter the current approvals to only match those of the current user
                        current_approvals['aaps'] = current_approvals['aaps'].filter(current_proposal__proposal_applicant__email_user_id=target_proposal.proposal_applicant.email_user_id)
                        current_approvals['aups'] = current_approvals['aups'].filter(current_proposal__proposal_applicant__email_user_id=target_proposal.proposal_applicant.email_user_id)
                        current_approvals['mls'] = current_approvals['mls'].filter(current_proposal__proposal_applicant__email_user_id=target_proposal.proposal_applicant.email_user_id)
                    
                        logger.info(f'Current approvals for the vessel belonging to the same applicant: [{target_vessel}]: {current_approvals}')

                    deduct = False
                    #For when the vessel on the currently observed proposal is NOT the target vessel
                    #We calculate deductions here to factor instances where another vessel has been removed from the approval, to discount from the total cost
                    if target_vessel and target_vessel != vessel:
                        
                        if proposal.approval and proposal.approval.child_obj and type(proposal.approval.child_obj) == MooringLicence:
                            # When ML, customer is adding a new vessel to the ML
                            if not current_approvals['aaps'] and not current_approvals['aups'] and not current_approvals['mls']:
                                # However, old vessel (target vessel) is no longer on any licence/permit.
                                logger.info(f'Vessel: [{vessel}] is being added to the approval: [{proposal.approval}], however the vessel [{target_vessel}] is no longer on any permit/licence.  We can transfer the amount paid: [{fee_item_application_fee}].')
                                deduct = True
                            else:
                                # We have to charge full amount  --> Go to next loop
                                logger.info(f'Vessel: [{vessel}] is being added to the approval: [{proposal.approval}] and the vessel: [{target_vessel}] is still on another licence/permit.  We cannot transfer the amount paid: [{fee_item_application_fee}] for the vessel: [{vessel}].')
                                deduct = False
                                #continue
                        if proposal.approval and proposal.approval.child_obj and type(proposal.approval.child_obj) == AuthorisedUserPermit:
                            # When AU, customer is replacing the current vessel
                            for key, qs in current_approvals.items():
                                # We want to exclude the approval being amended(modified) because the target_vessel is being removed from it.
                                current_approvals[key] = qs.exclude(id=self.approval.id)
                                deduct = True
                            if current_approvals['aaps'] or current_approvals['aups'] or current_approvals['mls']:
                                # When the current vessel is still used for other approvals --> Go to next loop
                                # But this fee_item_application_fee is still used for other approval(s)
                                logger.info(f'Existing Vessel: [{target_vessel}] still has current approval(s): [{current_approvals}].  We don\'t transfer the amount paid: [{fee_item_application_fee}].')
                                deduct = False
                                #continue

                    potential_deduction = fee_item_application_fee.amount_paid if fee_item_application_fee.amount_paid else 0

                    if (potential_deduction < 0 and not deduct) or (deduct and potential_deduction > 0):
                        valid_deductions += potential_deduction
                        logger.info(f'Amount: [{potential_deduction}] has been factored in to the current max AA amount paid.')
                        if valid_deductions > 0:
                            logger.info(f'Transferable amount: [{fee_item_application_fee}], which already has been paid.')

                if proposal.proposal_type.code in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL, ]:
                    # Now, 'prev_application' is the very first application for this season
                    # We are not interested in any older applications
                    continue_loop = False
                    break
                else:
                    # Assign the previous application, then perform checking above again
                    proposal = proposal.previous_application
            else:
                continue_loop = False
                break
                    
        proposal = target_proposal
        proposal_id_list = []
        continue_loop = True
        # third loop - deductions that have already been applied
        while continue_loop:
            if proposal:
                if proposal.id in proposal_id_list:
                    continue_loop = False
                    break
                proposal_id_list.append(proposal.id)

                if proposal != target_proposal:

                    #This fee items was charged 0 meaning that the entire sum for the AA was deducted for the target vessel OR the fee was bypassed for having already been paid
                    #To determine which:
                    # - get pertaining vessel for (missing) line item
                    # - find max paid (actual) for the specific vessel
                    # - get expected full amount for vessel
                    # - subtract payment from expected full amount
                    # - any remainder is a former deduction
                    if (not FeeItemApplicationFee.objects.filter(application_fee__proposal=proposal,fee_item__fee_constructor__application_type=annual_admission_type).exists() and proposal.vessel_ownership):

                        target_vessel = proposal.vessel_ownership.vessel
                        max_paid_for_vessel = 0
                        if target_vessel and target_vessel.rego_no and target_vessel.rego_no in max_amount_paid_per_vessel:
                            max_paid_for_vessel = max_amount_paid_per_vessel[target_vessel.rego_no]

                        if proposal.vessel_ownership != latest_vessel_ownership:
                            try:
                                paid_date = ApprovalHistory.objects.filter(proposal=proposal).first().start_date.date()
                                fee_constructor_for_aa = FeeConstructor.get_fee_constructor_by_application_type_and_date(annual_admission_type, paid_date)
                                fee_item = fee_constructor_for_aa.get_fee_item(proposal.vessel_length, proposal.proposal_type, paid_date)
                                logger.info(f'Proposal: [{proposal}] AA would have cost ${fee_item.get_absolute_amount(proposal.vessel_length)} if paid for')

                                deduction_for_zero_payment = fee_item.get_absolute_amount(proposal.vessel_length) - max_paid_for_vessel
                                logger.info(f'Proposal: Vessel on [{proposal}] was charged ${max_paid_for_vessel}')

                                if deduction_for_zero_payment > 0:
                                    logger.info(f'Proposal: [{proposal}] was deducted ${deduction_for_zero_payment}')
                                    previously_applied_deductions += deduction_for_zero_payment

                            except:
                                logger.warning(f'Unable to determine proposal approval start date - will be unable to determine how much would have been paid for it')
                        
                    #Here a fee item exists. A deduction may have been made for one of three reasons:
                    # - Another vessel ownership is no longer valid
                    # - A valid AA payment is no longer applied
                    # - A vessel increased in size and the former total has been removed
                    # - In the case of the first two items, deductions SHOULD be factored and removed from future deductions
                    # - In the last case, the original payment for the vessel should be factored before any potential former deductions are determined as the "deduction" in those cases have actually been paid for and are still valid
                    # - To do this, we must use the max paid value for the vessel in question, and subtract the payment from expected full amount
                    for fee_item_application_fee in FeeItemApplicationFee.objects.filter(application_fee__proposal=proposal, fee_item__fee_constructor__application_type=annual_admission_type):
                        
                        # We are interested only in the AnnualAdmission component
                        logger.info(f'FeeItemApplicationFee: [{fee_item_application_fee}] found through the proposal: [{proposal}]')

                        try:
                            target_vessel = fee_item_application_fee.vessel_details.vessel
                        except:
                            logger.warning("Application fee missing vessel details - invoices may require review")
                            target_vessel = None

                        if proposal.vessel_ownership == latest_vessel_ownership:
                            continue
                        
                        # Retrieve the current approvals of the target_vessel
                        if target_vessel:
                            current_approvals = target_vessel.get_current_approvals(target_date)
                            logger.info(f'Current approvals for the vessel: [{target_vessel}]: {current_approvals}')
                        
                        # This is paid for AA component for a target_vessel, but that vessel is no longer on any permit/licence
                        # In this case, we can transfer this amount
                        amount_paid = fee_item_application_fee.amount_paid if fee_item_application_fee.amount_paid else 0
                        if target_vessel and target_vessel.rego_no and target_vessel.rego_no in max_amount_paid_per_vessel:
                            full_amount_paid = max_amount_paid_per_vessel[target_vessel.rego_no]
                        else:
                            full_amount_paid = amount_paid

                        #factor in discounted payments (subtract difference between cost and paid (deduction-(cost-paid)))
                        if fee_item_application_fee.fee_item and fee_item_application_fee.fee_item.fee_period and fee_item_application_fee.fee_item.fee_period.start_date:
                            fee_constructor_for_aa = FeeConstructor.get_fee_constructor_by_application_type_and_date(annual_admission_type, fee_item_application_fee.fee_item.fee_period.start_date)
                            fee_item = fee_constructor_for_aa.get_fee_item(proposal.vessel_length, proposal.proposal_type, fee_item_application_fee.fee_item.fee_period.start_date)

                            amount_paid_deduction = fee_item.get_absolute_amount(proposal.vessel_length) - full_amount_paid
                            #only show logs if a) the deduction has been reduced but there is still an amount to apply or b) a prior deduction needs to taken away from a total deduction
                            if amount_paid_deduction > 0:
                                logger.info(f'Proposal: [{proposal}] AA would have cost ${fee_item.get_absolute_amount(proposal.vessel_length)} if paid for in full')
                                logger.info(f'Proposal: [{proposal}] AA had ${amount_paid_deduction} deducted from its cost')
                                previously_applied_deductions += amount_paid_deduction

                        else:
                            logger.warning(f'Fee Item has no fee period start date - will be unable to determine how much would have been paid for it')

                if proposal.proposal_type.code in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL, ]:
                    # Now, 'prev_application' is the very first application for this season
                    # We are not interested in any older applications
                    continue_loop = False
                    break
                else:
                    # Assign the previous application, then perform checking above again
                    proposal = proposal.previous_application
            else:
                continue_loop = False
                break    

        
        deductions_to_be_factored = valid_deductions - previously_applied_deductions
        logger.info(f"${max_amount_paid} has been paid for this vessel. There are ${valid_deductions} worth of potential deductions on this approval. ${previously_applied_deductions} has already been applied (or specified deductions must be applied again).")
        if deductions_to_be_factored > 0:
            max_amount_paid += deductions_to_be_factored

        if max_amount_paid < 0:
            logger.warning(f'Max amount paid is negative ({max_amount_paid}) - prior discounts may have been nullified on reinstating vessels or applicant has been undercharged')

        return max_amount_paid

    def get_amounts_paid_so_far(self, proposal):
        from mooringlicensing.components.payments_ml.models import FeeItemApplicationFee

        max_amounts_paid = {
            ApplicationType.objects.get(code=WaitingListApplication.code): Decimal('0.0'),
            ApplicationType.objects.get(code=AnnualAdmissionApplication.code): Decimal('0.0'),
            ApplicationType.objects.get(code=AuthorisedUserApplication.code): Decimal('0.0'),
            ApplicationType.objects.get(code=MooringLicenceApplication.code): Decimal('0.0'),
        }

        proposal_id_list = []
        continue_loop = True

        while continue_loop:
            if proposal:
                if proposal.id in proposal_id_list:
                    continue_loop = False
                    break
                proposal_id_list.append(proposal.id)

                for fee_item_application_fee in FeeItemApplicationFee.objects.filter(
                    application_fee__proposal=proposal):
                        # When not for AAP component
                        # or for AAP component and fee_item paid is for this vessel
                        amount_paid = fee_item_application_fee.amount_paid
                        if amount_paid:
                            max_amounts_paid[fee_item_application_fee.application_type] += amount_paid
                if proposal.proposal_type.code in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL, ]:
                    # Now, 'prev_application' is the very first application for this season
                    # We are not interested in any older applications
                    continue_loop = False
                    break
                else:
                    # Assign the previous application, then perform checking above again
                    proposal = proposal.previous_application
            else:
                continue_loop = False
                break
        return max_amounts_paid

    def get_amounts_paid_so_far_for_aa_through_other_approvals(self, proposal, vessel):
        from mooringlicensing.components.payments_ml.models import FeeItemApplicationFee
        annual_admission_type = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)

        max_amount_paid = 0
        proposal_id_list = []
        continue_loop = True

        while continue_loop:
            if proposal:
                if proposal.id in proposal_id_list:
                    continue_loop = False
                    break
                proposal_id_list.append(proposal.id)

                for fee_item_application_fee in FeeItemApplicationFee.objects.filter(
                    application_fee__proposal=proposal,
                    fee_item__fee_constructor__application_type=annual_admission_type,
                    vessel_details__vessel=vessel):
                    # When not for AAP component
                    # or for AAP component and fee_item paid is for this vessel
                    amount_paid = fee_item_application_fee.amount_paid
                    if amount_paid:
                        max_amount_paid += amount_paid
                if proposal.proposal_type.code in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL, ]:
                    # Now, 'prev_application' is the very first application for this season
                    # We are not interested in any older applications
                    continue_loop = False
                    break
                else:
                    # Assign the previous application, then perform checking above again
                    proposal = proposal.previous_application
            else:
                continue_loop = False
                break
        return max_amount_paid

    @property
    def latest_vessel_details(self):
        if self.vessel_ownership:
            return self.vessel_ownership.vessel.latest_vessel_details
        else:
            return None

    def get_invoice_property_cache(self):
        if len(self.invoice_property_cache) == 0:
            self.update_invoice_property_cache()
        return self.invoice_property_cache
    
    def update_invoice_property_cache(self, save=True):
        for inv in self.invoices_display():
            inv_props = get_invoice_properties(inv.id)

            self.invoice_property_cache[inv.id] = {
                'payment_status': inv_props['data']['invoice']['payment_status'],
                'reference': inv_props['data']['invoice']['reference'],
                'amount': inv_props['data']['invoice']['amount'],
                'settlement_date': inv_props['data']['invoice']['settlement_date'],
            }
            
        if save:
           self.save()
        return self.invoice_property_cache

    def invoices_display(self):
        invoice_references = [item.invoice_reference for item in self.application_fees.filter(cancelled=False).filter(system_invoice=False)]
        return Invoice.objects.filter(reference__in=invoice_references)

    def get_fee_items_paid(self, fee_season, vessel_details=None):
        from mooringlicensing.components.payments_ml.models import FeeItemApplicationFee

        fee_items = []

        queries = Q()
        queries &= Q(application_fee__in=self.application_fees.filter(cancelled=False).all())
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
        if type(self) is Proposal:
            if type(self.child_obj) not in [AuthorisedUserApplication, AnnualAdmissionApplication]:
                raise ValidationError("Only for AUP, AAA")
        else:
            if type(self) not in [AuthorisedUserApplication, AnnualAdmissionApplication]:
                raise ValidationError("Only for AUP, AAA")
        removed = False
        if self.approval and self.approval.reissued and (
            "vessel_ownership" in self.reissue_vessel_properties and
            "end_date" in self.reissue_vessel_properties["vessel_ownership"] and
            not self.reissue_vessel_properties["vessel_ownership"]["end_date"] and
            (not self.vessel_ownership or self.vessel_ownership.end_date)
        ):
            removed = True
        elif (
                self.previous_application and
                self.previous_application.vessel_ownership and
                not self.previous_application.vessel_ownership.end_date and  # There was a vessel in the previous application and not sold
                (not self.vessel_ownership or self.vessel_ownership.end_date)
        ):
            removed = True
        return removed

    @property
    def vessel_swapped(self):
        # for AUP, AAP manage_stickers
        if type(self) is Proposal:
            if type(self.child_obj) not in [AuthorisedUserApplication, AnnualAdmissionApplication]:
                raise ValidationError("Only for AUP, AAA")
        else:
            if type(self) not in [AuthorisedUserApplication, AnnualAdmissionApplication]:
                raise ValidationError("Only for AUP, AAA")

        changed = False
        if self.approval and self.approval.reissued and (
            "vessel_ownership" in self.reissue_vessel_properties and
            "end_date" in self.reissue_vessel_properties["vessel_ownership"] and
            "vessel_details" in self.reissue_vessel_properties and
            "rego_no" in self.reissue_vessel_properties["vessel_details"] and
            not self.reissue_vessel_properties["vessel_ownership"]["end_date"] and
            self.vessel_ownership and
            not self.vessel_ownership.end_date and  # Not sold yet
            self.vessel_ownership.vessel.rego_no != self.reissue_vessel_properties["vessel_details"]["rego_no"]
        ):
            changed = True
        elif (
                self.previous_application and
                self.previous_application.vessel_ownership and
                not self.previous_application.vessel_ownership.end_date and  # Not sold yet
                self.vessel_ownership and
                not self.vessel_ownership.end_date and  # Not sold yet
                self.vessel_ownership.vessel.rego_no != self.previous_application.vessel_ownership.vessel.rego_no
        ):
            changed = True
        return changed

    @property
    def vessel_null_to_new(self):
        # for AUP, AAP manage_stickers
        if type(self) is Proposal:
            if type(self.child_obj) not in [AuthorisedUserApplication, AnnualAdmissionApplication]:
                raise ValidationError("Only for AUP, AAA")
        else:
            if type(self) not in [AuthorisedUserApplication, AnnualAdmissionApplication]:
                raise ValidationError("Only for AUP, AAA")

        new = False
        if self.approval and self.approval.reissued and (
            (
                not "vessel_ownership" in self.reissue_vessel_properties or 
                ("end_date" in self.reissue_vessel_properties["vessel_ownership"] and 
                self.reissue_vessel_properties["vessel_ownership"]["end_date"])
            ) and
            self.vessel_ownership and
            not self.vessel_ownership.end_date
        ):
            new = True
        elif (
                self.previous_application and
                (not self.previous_application.vessel_ownership or self.previous_application.vessel_ownership.end_date) and
                self.vessel_ownership and
                not self.vessel_ownership.end_date
        ):
            new = True
        return new

    @property
    def final_status(self):
        final_status = False
        if self.processing_status in ([Proposal.PROCESSING_STATUS_PRINTING_STICKER, Proposal.PROCESSING_STATUS_APPROVED]):
            final_status = True
        return final_status

    #check proposal for any remaining site licensee mooring requests - update to with assessor otherwise    
    def check_endorsements(self, request):
        if self.processing_status != Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT:
            if (self.is_assessor(request.user) and (
                self.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR or
                self.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS
            )):
                return
            raise serializers.ValidationError("proposal not awaiting endorsement")
        #only proceed if status is awaiting endorsement and request user is an endorser (or internal)
        site_licensee_mooring_request = self.site_licensee_mooring_request.all()
        if not (self.is_assessor(request.user) or site_licensee_mooring_request.filter(site_licensee_email=request.user.email).exists()):
            raise serializers.ValidationError("user not authorised to check endorsements")

        if not (site_licensee_mooring_request.filter(declined_by_endorser=False,approved_by_endorser=False,enabled=True).exists()):
            #if all requests are endorsed or declined, set proposal status with assessor
            self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
            self.save()
            logger.info(f'All site licensee mooring requests endorsed or declined for the Proposal: [{self}].')

            send_notification_email_upon_submit_to_assessor(request, self)

    def update_customer_status(self):
        matrix = {
            Proposal.PROCESSING_STATUS_DRAFT: Proposal.CUSTOMER_STATUS_DRAFT,
            Proposal.PROCESSING_STATUS_WITH_ASSESSOR: Proposal.CUSTOMER_STATUS_WITH_ASSESSOR,
            Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS: Proposal.CUSTOMER_STATUS_WITH_ASSESSOR,
            Proposal.PROCESSING_STATUS_WITH_APPROVER: Proposal.CUSTOMER_STATUS_WITH_APPROVER,
            Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED: Proposal.CUSTOMER_STATUS_STICKER_TO_BE_RETURNED,
            Proposal.PROCESSING_STATUS_PRINTING_STICKER: Proposal.CUSTOMER_STATUS_PRINTING_STICKER,
            Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT: Proposal.CUSTOMER_STATUS_AWAITING_ENDORSEMENT,
            Proposal.PROCESSING_STATUS_AWAITING_DOCUMENTS: Proposal.CUSTOMER_STATUS_AWAITING_DOCUMENTS,
            Proposal.PROCESSING_STATUS_APPROVED: Proposal.CUSTOMER_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_DECLINED: Proposal.CUSTOMER_STATUS_DECLINED,
            Proposal.PROCESSING_STATUS_DISCARDED: Proposal.CUSTOMER_STATUS_DISCARDED,
            Proposal.PROCESSING_STATUS_AWAITING_PAYMENT: Proposal.CUSTOMER_STATUS_AWAITING_PAYMENT,
            Proposal.PROCESSING_STATUS_EXPIRED: Proposal.CUSTOMER_STATUS_EXPIRED,
        }
        self.customer_status = matrix[self.processing_status]

    def rego_no_uppercase(self):
        if self.rego_no:
            self.rego_no = self.rego_no.upper()

    def save(self, *args, **kwargs):
        kwargs.pop('version_user', None)
        kwargs.pop('version_comment', None)
        kwargs['no_revision'] = True
        self.update_customer_status()
        self.rego_no_uppercase()
        if self.pk:
            self.update_invoice_property_cache(save=False)
        super(Proposal, self).save(**kwargs)
        if type(self) == Proposal:
            self.child_obj.refresh_from_db()

    def get_main_application_fee(self):
        main_af = None
        for af in self.application_fees.filter(cancelled=False):
            if af and af.fee_constructor:
                main_af = af
                break
            elif af and self.proposal_type and self.proposal_type.code == PROPOSAL_TYPE_SWAP_MOORINGS:
                main_af = af
                break
        logger.debug(f'Main ApplicationFee: [{main_af}] found for the Proposal: [{self}].')
        return main_af

    @property
    def fee_constructor(self):
        application_fee = self.get_main_application_fee()
        if application_fee:
            return application_fee.fee_constructor
        else:
            return None

    @property
    def invoice(self):
        invoice = None
        application_fee = self.get_main_application_fee()
        try:
            if (application_fee):
                invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
        except ObjectDoesNotExist:
            invoice = None
        return invoice

    @property
    def start_date(self):
        start_date = None
        application_fee = self.get_main_application_fee()
        if application_fee:
            start_date = application_fee.fee_constructor.start_date
        elif self.fee_season:
            # application_fee can be None when there are no charges for this proposal i.e. AU doesn't charge anything when ML exists for the same vessel.
            start_date = self.fee_season.start_date
        return start_date

    @property
    def end_date(self):
        end_date = None
        application_fee = self.get_main_application_fee()
        if application_fee:
            end_date = application_fee.fee_constructor.end_date
        elif self.fee_season:
            # application_fee can be None when there are no charges for this proposal i.e. AU doesn't charge anything when ML exists for the same vessel.
            end_date = self.fee_season.end_date
        return end_date

    @property
    def fee_paid(self):
        inv_props = self.get_invoice_property_cache()
        try:
            invoice_payment_status = inv_props[self.invoice.id]['payment_status']
            if (self.invoice and invoice_payment_status in ['paid', 'over_paid']) or self.proposal_type==PROPOSAL_TYPE_AMENDMENT:
                return True
        except:
            return False
        return False

    @property
    def fee_amount(self):
        return self.invoice.amount if self.fee_paid else None

    @property
    def applicant(self):
        if self.proposal_applicant:
            applicant = retrieve_system_user(self.proposal_applicant.email_user_id)
            if applicant:
                return "{} {}".format(
                    applicant.legal_first_name,
                    applicant.legal_last_name)
        return ""

    @property
    def applicant_email(self):
        if self.proposal_applicant:
            return self.proposal_applicant.email
        return ""

    @property
    def applicant_id(self):
        if self.proposal_applicant:
            return self.proposal_applicant.email_user_id
        return None

    @property
    def get_history(self):
        """ Return the prev proposal versions """
        l = []
        proposal_ids = []
        p = copy.deepcopy(self)
        while (p.previous_application):
            if p.id in proposal_ids:
                break
            proposal_ids.append(p.id)
            l.append( dict(id=p.previous_application.id, modified=p.previous_application.modified_date) )
            p = p.previous_application
        return l

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
    def can_user_cancel_payment(self):
        """
        :return: True if the application is in one of the approved status.
        """
        return self.customer_status in [self.CUSTOMER_STATUS_AWAITING_PAYMENT, self.CUSTOMER_STATUS_EXPIRED]

    @property
    def permit(self):
        return self.approval.licence_document._file.url if self.approval else None

    @property
    def allowed_assessors(self):
        if self.processing_status == 'with_approver':
            group = self.__approver_group()
        else:
            group = self.__assessor_group()
        ids = group.get_system_group_member_ids() if group else []
        users = EmailUserRO.objects.filter(id__in=ids)
        return users

    @property
    def compliance_assessors(self):
        group = self.__assessor_group()
        ids = group.get_system_group_member_ids() if group else []
        users = EmailUserRO.objects.filter(id__in=ids)
        return users

    def allowed_assessors_user(self, request):
        if self.processing_status == 'with_approver':
            group = self.__approver_group()
        else:
            group = self.__assessor_group()
        return True if group and request.user.id in group.get_system_group_member_ids() else False

    @property
    def can_officer_process(self):
        """ :return: True if the application is in one of the processable status for Assessor role."""
        officer_view_state = [
            Proposal.PROCESSING_STATUS_DRAFT,
            Proposal.PROCESSING_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_DECLINED,
            Proposal.PROCESSING_STATUS_DISCARDED,
            Proposal.PROCESSING_STATUS_AWAITING_PAYMENT,
            Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT,
            Proposal.PROCESSING_STATUS_AWAITING_DOCUMENTS,
            Proposal.PROCESSING_STATUS_PRINTING_STICKER,
            Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED,
            Proposal.PROCESSING_STATUS_EXPIRED,
        ]
        return False if self.processing_status in officer_view_state else True

    @property
    def amendment_requests(self):
        qs = AmendmentRequest.objects.filter(proposal=self)
        return qs

    #Check if there is an pending amendment request exist for the proposal
    @property
    def pending_amendment_request(self):
        qs = AmendmentRequest.objects.filter(proposal = self, status = "requested")
        if qs:
            return True
        return False

    def __assessor_group(self):
        return self.child_obj.assessor_group

    def __approver_group(self):
        return self.child_obj.approver_group

    @property
    def assessor_recipients(self):
        return self.child_obj.assessor_recipients

    @property
    def approver_recipients(self):
        return self.child_obj.approver_recipients

    #Check if the user is member of assessor group for the Proposal
    def is_assessor(self, user):
        if isinstance(user, EmailUserRO):
            return self.child_obj.is_assessor(user)

    #Check if the user is member of assessor group for the Proposal
    def is_approver(self, user):
        if isinstance(user, EmailUserRO):
            return self.child_obj.is_approver(user)

    def can_assess(self, user):
        if self.processing_status in [Proposal.PROCESSING_STATUS_WITH_ASSESSOR, Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS,Proposal.PROCESSING_STATUS_DRAFT,Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT]:
            return self.child_obj.is_assessor(user)
        elif self.processing_status in [Proposal.PROCESSING_STATUS_WITH_APPROVER, Proposal.PROCESSING_STATUS_AWAITING_PAYMENT, Proposal.PROCESSING_STATUS_PRINTING_STICKER]:
            return self.child_obj.is_approver(user)
        else:
            return False

    def has_approver_mode(self,user):
        if isinstance(user, EmailUserRO):
            status_without_approver = [
                Proposal.PROCESSING_STATUS_WITH_ASSESSOR, 
                Proposal.PROCESSING_STATUS_APPROVED, 
                Proposal.PROCESSING_STATUS_AWAITING_PAYMENT, 
                Proposal.PROCESSING_STATUS_DECLINED, 
                Proposal.PROCESSING_STATUS_DRAFT,
                Proposal.PROCESSING_STATUS_PRINTING_STICKER,
                Proposal.PROCESSING_STATUS_EXPIRED,
            ]
            if self.processing_status in status_without_approver:
                return False
            else:
                if self.assigned_officer:
                    if self.assigned_officer == user.id:
                        return self.child_obj.is_approver(user)
                    else:
                        return False
                else:
                    return self.child_obj.is_approver(user)

    def has_assessor_mode(self,user):
        if isinstance(user, EmailUserRO):
            status_without_assessor = [
                Proposal.PROCESSING_STATUS_WITH_APPROVER, 
                Proposal.PROCESSING_STATUS_APPROVED, 
                Proposal.PROCESSING_STATUS_AWAITING_PAYMENT, 
                Proposal.PROCESSING_STATUS_DECLINED,
                Proposal.PROCESSING_STATUS_PRINTING_STICKER,
                Proposal.PROCESSING_STATUS_EXPIRED,
            ]
            if self.processing_status in status_without_assessor:
                return False
            else:
                if self.assigned_officer:
                    if self.assigned_officer == user.id:
                        return self.child_obj.is_assessor(user)
                    else:
                        return False
                else:
                    return self.child_obj.is_assessor(user)

    def log_user_action(self, action, request=None):
        if request:
            return ProposalUserAction.log_action(self, action, request.user.id)
        else:
            return ProposalUserAction.log_action(self, action)

    def update(self,request,viewset):
        from mooringlicensing.components.proposals.utils import save_proponent_data
        
        with transaction.atomic():
            if self.can_user_edit:
                # Save the data first
                save_proponent_data(self,request,viewset.action)
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
                    if officer.id != self.assigned_approver:
                        self.assigned_approver = officer.id
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_ASSIGN_TO_APPROVER.format(self.id,'{}({})'.format(officer.get_full_name(),officer.email)),request)
                else:
                    if officer.id != self.assigned_officer:
                        self.assigned_officer = officer.id
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_ASSIGN_TO_ASSESSOR.format(self.id,'{}({})'.format(officer.get_full_name(),officer.email)),request)
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
                else:
                    if self.assigned_officer:
                        self.assigned_officer = None
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_UNASSIGN_ASSESSOR.format(self.id),request)
            except:
                raise

    def add_default_requirements(self):
        # Add default standard requirements to Proposal
        due_date = None
        default_requirements = ProposalStandardRequirement.objects.filter(application_type=self.application_type, default=True, obsolete=False)
        if default_requirements:
            for req in default_requirements:
                r, created = ProposalRequirement.objects.get_or_create(proposal=self, standard_requirement=req, due_date=due_date)

    def move_to_status(self, request, status, approver_comment):
        #TODO current status validation was not added to this function, some will be added as of writing but further review may be required
        if not status:
            raise serializers.ValidationError('Status is required')
        if status not in [Proposal.PROCESSING_STATUS_WITH_ASSESSOR, Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS, Proposal.PROCESSING_STATUS_WITH_APPROVER]:
            raise serializers.ValidationError('The status provided is not allowed')
        if not self.can_assess(request.user):
            raise exceptions.ProposalNotAuthorized()
        if self.processing_status in [Proposal.PROCESSING_STATUS_APPROVED, Proposal.PROCESSING_STATUS_PRINTING_STICKER, Proposal.PROCESSING_STATUS_DECLINED, Proposal.PROCESSING_STATUS_DISCARDED, Proposal.PROCESSING_STATUS_AWAITING_PAYMENT]:
            raise serializers.ValidationError('Current status cannot be changed manually')

        if self.processing_status != status:
            if self.processing_status == Proposal.PROCESSING_STATUS_WITH_APPROVER:
                self.approver_comment = ''
                if approver_comment:
                    self.approver_comment = approver_comment
                    self.save()
                    send_proposal_approver_sendback_email_notification(request, self)
            self.processing_status = status
            self.save()
            logger.info(f'Status:[{status}] has been set to the proposal: [{self}]')
            if status == self.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS:
                self.add_default_requirements()

            # Create a log entry for the proposal
            if self.processing_status == self.PROCESSING_STATUS_WITH_ASSESSOR:
                self.log_user_action(ProposalUserAction.ACTION_BACK_TO_PROCESSING.format(self.lodgement_number), request)
            elif self.processing_status == self.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS:
                self.log_user_action(ProposalUserAction.ACTION_ENTER_REQUIREMENTS.format(self.lodgement_number), request)

    def bypass_endorsement(self,request):
        if self.is_assessor(request.user):
            if type(self.child_obj) == AuthorisedUserApplication and self.processing_status == Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT:
                self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
                self.save()
                send_notification_email_upon_submit_to_assessor(request, self)
            else:
                serializers.ValidationError("Invalid application type")
        else:
            raise ValidationError('Not authorised to bypass endorsement')

    def request_endorsement(self,request):
        if self.is_assessor(request.user):
            if type(self.child_obj) == AuthorisedUserApplication and self.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR:
                if self.site_licensee_mooring_request.filter(enabled=True,declined_by_endorser=False,approved_by_endorser=False).exists():
                    #run function to move to awaiting_endorsement
                    self.processing_status = Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT
                    self.save()
                    send_endorsement_of_authorised_user_application_email(request, self.child_obj)
                else:
                    serializers.ValidationError("No site licensee moorings requests that require action")
            else:
                serializers.ValidationError("Invalid application type")
        else:
            raise ValidationError('Not authorised to request endorsement')

    def reissue_approval(self, request):
        with transaction.atomic():
            vessels = []
            if type(self.child_obj) == MooringLicenceApplication:
                vessels.extend([vo.vessel for vo in self.listed_vessels.all()])
            else:
                if self.vessel_details:
                    vessels.append(self.vessel_details.vessel)
            # Non MLA
            proposals = [proposal for proposal in Proposal.objects.filter(vessel_details__vessel__in=vessels).
                    exclude(id=self.id).
                    exclude(processing_status__in=['discarded', 'sticker_to_be_returned', 'printing_sticker', 'approved', 'declined'])
                        ]
            # MLA
            proposals.extend([proposal for proposal in Proposal.objects.
                filter(listed_vessels__end_date__isnull=True).
                filter(listed_vessels__vessel__in=vessels).
                exclude(id=self.id).
                exclude(processing_status__in=['discarded', 'sticker_to_be_returned', 'printing_sticker', 'approved', 'declined'])
                ])

            if not self.processing_status == Proposal.PROCESSING_STATUS_APPROVED:
                raise ValidationError('You cannot change the current status at this time')
            elif proposals:
                raise ValidationError('Error message: there is an application in status other than (Discarded, Sticker To Be Returned, Printing Sticker, Approved, or Declined)')
            elif self.approval and self.approval.can_reissue and self.is_approver(request.user):
                self.populate_reissue_vessel_properties()
                # update vessel details
                if self.vessel_details:
                    vessel_details = self.vessel_details.vessel.latest_vessel_details
                    self.vessel_type = vessel_details.vessel_type if vessel_details else ''
                    self.vessel_name = vessel_details.vessel_name if vessel_details else ''
                    self.vessel_length = vessel_details.vessel_length if vessel_details else 0.00
                    self.vessel_draft = vessel_details.vessel_draft if vessel_details else 0.00
                    self.vessel_beam = vessel_details.vessel_beam if vessel_details else 0.00
                    self.vessel_weight = vessel_details.vessel_weight if vessel_details else 0.00
                    self.berth_mooring = vessel_details.berth_mooring if vessel_details else ''

                self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
                self.proposed_issuance_approval = {}
                self.save()
                
                self.approval.reissued=True
                self.approval.save()
                # Create a log entry for the proposal
                self.log_user_action(ProposalUserAction.ACTION_REISSUE_APPROVAL.format(self.lodgement_number), request)
            else:
                raise ValidationError('Cannot reissue Approval')

    def proposed_decline(self,request,details):
        with transaction.atomic():
            logger.info(f'Processing proposed decline... for the Proposal: [{self}]')
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status != Proposal.PROCESSING_STATUS_WITH_ASSESSOR:
                    raise ValidationError('You cannot propose to decline if it is not with assessor')

                reason = details.get('reason', '')
                ProposalDeclinedDetails.objects.update_or_create(
                    proposal=self,
                    defaults={
                        'officer': request.user.id,
                        'reason': reason,
                        'cc_email': details.get('cc_email', None)
                    }
                )
                self.proposed_decline_status = True
                approver_comment = ''
                self.move_to_status(request, Proposal.PROCESSING_STATUS_WITH_APPROVER, approver_comment)
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_PROPOSED_DECLINE.format(self.lodgement_number), request)

                send_approver_approve_decline_email_notification(request, self)
            except:
                raise

    def final_decline(self, request, details):
        from mooringlicensing.components.approvals.models import WaitingListAllocation

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

                if self.approval and self.approval.reissued:
                    #if the approval was reissued, revert the proposal to what it was before reissue
                    self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                    self.approval.reissued = False
                    self.save()
                    return

                proposal_decline, success = ProposalDeclinedDetails.objects.update_or_create(
                    proposal=self,
                    defaults={
                        'officer': request.user.id,
                        'reason': details.get('reason', ''),
                        'cc_email': details.get('cc_email',None)
                    }
                )
                self.proposed_decline_status = True
                self.processing_status = Proposal.PROCESSING_STATUS_DECLINED
                self.save()
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_DECLINE.format(self.id),request)
                # update WLA internal_status
                ## ML
                if type(self.child_obj) == MooringLicenceApplication and self.waiting_list_allocation:
                    # Originated WLAllocation should gets the status 'waiting' again.
                    self.waiting_list_allocation.internal_status = WaitingListAllocation.INTERNAL_STATUS_WAITING
                    self.waiting_list_allocation.save()
                    logger.info(f'Internal status: [{WaitingListAllocation.INTERNAL_STATUS_WAITING}] has been set to the WLAllocation: [{self.waiting_list_allocation}.]')
                    self.waiting_list_allocation.set_wla_order()
                send_application_approved_or_declined_email(self, 'declined', request)
            except:
                raise


    def proposed_approval(self, request, details):
        from mooringlicensing.components.approvals.models import MooringOnApproval
        with transaction.atomic():
            try:
                logger.info(f'Processing proposed approval... for the Proposal: [{self}]')
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status != Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS:
                    raise ValidationError('You cannot propose for approval if it is not with assessor for requirements')

                current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
                current_date = current_datetime.date()

                ria_mooring_name = ''
                mooring_id = details.get('mooring_id')
                mooring_on_approval = details.get('mooring_on_approval')
                mooring_on_approval.reverse()
                id_list = []
                checked_list = []
                temp = []

                #sanitise mooring on approval - count only entry per id and only the latest among each id
                for i in mooring_on_approval:
                    if "id" in i and "checked" in i and not i["id"] in id_list:
                        temp.append(i)
                        checked_list.append(i["checked"])
                        id_list.append(i["id"])
                mooring_on_approval = temp

                temp = id_list
                id_list = []
                for i in range(len(temp)):
                    if checked_list[i]:
                        id_list.append(temp[i])

                requested_mooring_on_approval = details.get('requested_mooring_on_approval')
                requested_mooring_on_approval.reverse()
                requested_id_list = []
                requested_checked_list = []
                temp = []

                for i in requested_mooring_on_approval:
                    if "id" in i and "checked" in i and not i["id"] in requested_id_list:
                        temp.append(i)
                        requested_checked_list.append(i["checked"])
                        requested_id_list.append(i["id"])

                requested_mooring_on_approval = temp

                temp = requested_id_list
                requested_id_list = []
                for i in range(len(temp)):
                    if requested_checked_list[i]:
                        requested_id_list.append(temp[i])

                if mooring_id:
                    try:
                        mooring = Mooring.objects.get(id=mooring_id)
                        ria_mooring_name = mooring.name
                    except:
                        mooring = None
                        if self.application_type.code == "aua" and self.mooring_authorisation_preference != "site_licensee":
                            raise serializers.ValidationError("Mooring id provided is invalid")
                #check mooring_on_approval and requested_mooring_on_approval - if both are empty at this stage for an aua return error 
                elif self.application_type.code == "aua":
                    if not mooring_on_approval or mooring_on_approval == []:
                        if self.mooring_authorisation_preference == "site_licensee":
                            if not requested_mooring_on_approval or requested_mooring_on_approval == []:
                                raise serializers.ValidationError("No mooring provided")
                        else:
                            raise serializers.ValidationError("No mooring provided")

                        #check if mooring on approval list has at least one checked value
                        if self.mooring_authorisation_preference != "site_licensee" and not True in checked_list:
                            raise serializers.ValidationError("No mooring provided")
                        elif self.mooring_authorisation_preference == "site_licensee" and not True in requested_checked_list:
                            raise serializers.ValidationError("No mooring provided")

                check_old_moorings = MooringOnApproval.objects.filter(id__in=id_list)          
                check_new_moorings = Mooring.objects.filter(id__in=requested_id_list)

                if mooring_id:
                    if (self.vessel_length > mooring.vessel_size_limit or
                        self.vessel_draft > mooring.vessel_draft_limit or
                        (self.vessel_weight > mooring.vessel_weight_limit and mooring.vessel_weight_limit > 0)):
                        raise serializers.ValidationError("Vessel dimensions are not compatible with one or more moorings")

                for i in check_old_moorings:
                    if not i.mooring:
                        raise serializers.ValidationError("Mooring does not exist")
                    
                    if not self.vessel_length or not self.vessel_draft or not self.vessel_weight:
                        raise serializers.ValidationError("One or more vessel dimensions are not specified")

                    if (self.vessel_length > i.mooring.vessel_size_limit or
                        self.vessel_draft > i.mooring.vessel_draft_limit or
                        (self.vessel_weight > i.mooring.vessel_weight_limit and i.mooring.vessel_weight_limit > 0)):
                        raise serializers.ValidationError("Vessel dimensions are not compatible with one or more moorings")
                    
                for i in check_new_moorings:
                    
                    if not self.vessel_length or not self.vessel_draft or not self.vessel_weight:
                        raise serializers.ValidationError("One or more vessel dimensions are not specified")

                    if (self.vessel_length > i.vessel_size_limit or
                        self.vessel_draft > i.vessel_draft_limit or
                        (self.vessel_weight > i.vessel_weight_limit and i.vessel_weight_limit > 0)):
                        raise serializers.ValidationError("Vessel dimensions are not compatible with one or more moorings")
                    
                if not mooring_id and (not id_list and not requested_id_list) and self.application_type.code == "aua":
                    raise serializers.ValidationError("No mooring provided")
                
                if self.application_type.code == "mla":
                    mooring = self.allocated_mooring
                    if ((self.vessel_length and self.vessel_length > mooring.vessel_size_limit) or
                        (self.vessel_draft and self.vessel_draft > mooring.vessel_draft_limit) or
                        (self.vessel_weight and self.vessel_weight > mooring.vessel_weight_limit and mooring.vessel_weight_limit > 0)):
                        raise serializers.ValidationError("Proposed vessel dimensions are not compatible with the mooring")

                self.proposed_issuance_approval = {
                    'current_date': current_date.strftime('%d/%m/%Y'), 
                    'mooring_bay_id': details.get('mooring_bay_id'),
                    'mooring_id': mooring_id,
                    'ria_mooring_name': ria_mooring_name,
                    'details': details.get('details'),
                    'cc_email': details.get('cc_email'),
                    'mooring_on_approval': mooring_on_approval,
                    'requested_mooring_on_approval': requested_mooring_on_approval,
                    'vessel_ownership': details.get('vessel_ownership'),
                }
                self.proposed_decline_status = False
                approver_comment = ''
                self.move_to_status(request, Proposal.PROCESSING_STATUS_WITH_APPROVER, approver_comment)
                self.assigned_officer = None
                self.save()
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_PROPOSED_APPROVAL.format(self.lodgement_number), request)

                send_approver_approve_decline_email_notification(request, self)
                return self

            except:
                raise

    def final_approval_for_WLA_AAA(self, request, details=None):
        from mooringlicensing.components.proposals.utils import submit_vessel_data
        from mooringlicensing.components.payments_ml.models import FeeItemApplicationFee
        with transaction.atomic():
            try:
                if self.proposed_decline_status:
                    raise ValidationError('This Application was proposed to be declined. Send back to assessor if it needs to be approved.')

                logger.info(f'Processing final_approval...for the proposal: [{self}].')

                submit_vessel_data(self, request, approving=True)
                self.refresh_from_db()

                current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))

                # Validation & update proposed_issuance_approval
                if not ((self.processing_status == Proposal.PROCESSING_STATUS_AWAITING_PAYMENT and self.fee_paid) or 
                    self.proposal_type == PROPOSAL_TYPE_AMENDMENT):
                    if request and not self.auto_approve and not self.can_assess(request.user):
                        raise exceptions.ProposalNotAuthorized()
                    if not self.auto_approve and self.processing_status not in (Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS, Proposal.PROCESSING_STATUS_WITH_ASSESSOR):
                        raise ValidationError('You cannot issue the approval if it is not with an assessor')
                    if not is_applicant_postal_address_set(self):
                        raise ValidationError('The applicant needs to have set their postal address before approving this proposal.')

                    if self.application_fees.filter(cancelled=False).count() < 1:
                        raise ValidationError('Payment record not found for the Annual Admission Application: {}'.format(self))
                    
                    if details:
                        # When auto_approve, there are no 'details' because details are created from the modal when assessment
                        self.proposed_issuance_approval = {
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
                    approval.issue_date = current_datetime
                    approval.start_date = current_datetime.date()
                    approval.expiry_date = self.end_date
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
                    if created:
                        logger.info(f'New approval: [{approval}] has been created.')
                        approval.log_user_action(f'New approval: {approval} has been created.', request)
                self.approval = approval
                self.save()

                #update FeeItemApplicationFee with vessel details
                application_fee = self.get_main_application_fee()
                fee_item_application_fees = FeeItemApplicationFee.objects.filter(application_fee=application_fee)
                fee_item_application_fees.update(vessel_details=self.vessel_details)

                # only reset this flag if it is a renewal
                if self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
                    approval.renewal_sent = False
                
                if type(self.child_obj) == AnnualAdmissionApplication:
                    approval.export_to_mooring_booking = True
                approval.save()
                # set auto_approve ProposalRequirement due dates to those from previous application + 12 months
                if self.auto_approve and self.proposal_type.code == 'renewal':
                    for req in self.requirements.filter(is_deleted=False):
                        if req.copied_from and req.copied_from.due_date:
                            req.due_date = req.copied_from.due_date + relativedelta(months=+12)
                            req.save()

                # Generate compliances
                from mooringlicensing.components.compliances.models import Compliance
                target_proposal = self.previous_application if self.proposal_type.code == 'amendment' else self
                for compliance in Compliance.objects.filter(
                    approval=approval.approval,
                    proposal=target_proposal,
                    processing_status='future',
                    ):
                    compliance.processing_status='discarded'
                    compliance.customer_status = 'discarded'
                    compliance.post_reminder_sent=True
                    compliance.save()
                self.generate_compliances(approval, request)

                # Log proposal action
                if details:
                    # When not auto-approve
                    self.log_user_action(ProposalUserAction.ACTION_APPROVED.format(self.lodgement_number), request)
                else:
                    # When auto approve
                    self.log_user_action(ProposalUserAction.ACTION_AUTO_APPROVED.format(self.lodgement_number),)

                # set proposal status to approved - can change later after manage_stickers
                self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                self.save()

                # Update stickers
                new_sticker, sticker_to_be_returned = self.approval.manage_stickers(self)

                # Handle this proposal status
                if self.approval and self.approval.reissued:
                    # Can only change the conditions, so goes to Approved
                    self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                else:
                    if sticker_to_be_returned:
                        self.processing_status = Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED
                    elif new_sticker:
                        self.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                self.save()

                # set wla order
                from mooringlicensing.components.approvals.models import WaitingListAllocation
                if (type(approval) == WaitingListAllocation and 
                        (self.proposal_type.code == PROPOSAL_TYPE_NEW or 
                            (self.previous_application.preferred_bay != self.preferred_bay)
                            )
                        ):
                    from mooringlicensing.components.approvals.models import Approval
                    approval.internal_status = Approval.INTERNAL_STATUS_WAITING
                    approval.wla_queue_date = current_datetime
                    approval.save()
                    approval = approval.set_wla_order()

                # send Proposal approval email with attachment
                approval.generate_doc()
                if request:
                    send_application_approved_or_declined_email(self, 'approved', request, [sticker_to_be_returned,])
                self.save(version_comment='Final Approval: {}'.format(self.approval.lodgement_number))
                self.approval.approval_documents.all().update(can_delete=False)

                # write approval history
                if self.approval and self.approval.reissued:
                    approval.write_approval_history('Reissue via application {}'.format(self.lodgement_number))
                elif self.proposal_type == ProposalType.objects.get(code=PROPOSAL_TYPE_RENEWAL):
                    approval.write_approval_history('Renewal application {}'.format(self.lodgement_number))
                elif self.proposal_type == ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT):
                    approval.write_approval_history('Amendment application {}'.format(self.lodgement_number))
                else:
                    approval.write_approval_history()

                # Reset flag
                if self.approval:
                    self.approval.reissued = False
                    self.approval.save()

                return self

            except Exception as e:
                raise

    def refresh(self):
        if self.approval:
            self.approval.refresh_from_db()
        self.refresh_from_db()
        if self.child_obj:
            self.child_obj.refresh_from_db()

    def final_approval_for_AUA_MLA(self, request=None):
        with transaction.atomic():
            try:
                if self.proposed_decline_status:
                    raise ValidationError('This Application was proposed to be declined. Send back to assessor if it needs to be approved.')
                from mooringlicensing.components.approvals.models import Sticker
                from mooringlicensing.components.proposals.utils import submit_vessel_data
                logger.info(f'Processing final_approval... for the proposal: [{self}].')

                submit_vessel_data(self, request, approving=True)
                self.refresh_from_db()

                # Validation & update proposed_issuance_approval
                if not ((self.processing_status == Proposal.PROCESSING_STATUS_AWAITING_PAYMENT and self.fee_paid) or self.proposal_type == PROPOSAL_TYPE_AMENDMENT):
                    if request and not self.can_assess(request.user):
                        raise exceptions.ProposalNotAuthorized()
                    if request and self.processing_status not in (Proposal.PROCESSING_STATUS_WITH_APPROVER,):
                        raise ValidationError('You cannot issue the approval if it is not with an assessor')
                    if not is_applicant_postal_address_set(self):
                        raise ValidationError('The applicant needs to have set their postal address before approving this proposal.')

                # if no request, must be a system reissue - skip payment section
                # when reissuing, no new invoices should be created
                if not request or (request and self.approval and self.approval.reissued):
                    # system reissue or admin reissue
                    approval, created = self.child_obj.update_or_create_approval(datetime.datetime.now(pytz.timezone(TIME_ZONE)), request)
                    #--- Reflect any changes made in the function above (update_or_create_approval) ---#
                    self.refresh()
                    #-------------------------------#
                    self.approval = approval.approval
                    self.save()
                else:
                    ## prepare invoice
                    from mooringlicensing.components.payments_ml.models import ApplicationFee

                    # create fee lines tells us whether a payment is required
                    line_items, fee_items_to_store = self.child_obj.create_fee_lines()  # Accessed by AU and ML

                    total_amount = sum(line_item['price_incl_tax'] for line_item in line_items)

                    if total_amount == 0:

                        # Call a function where mooringonapprovals and stickers are handled, because when total_amount == 0,
                        # Ledger skips the payment step, which calling the function below
                        approval, created = self.child_obj.update_or_create_approval(datetime.datetime.now(pytz.timezone(TIME_ZONE)), request=request)

                        #--- Reflect any changes made in the function above (update_or_create_approval) ---#
                        if self.approval:
                            self.approval.refresh_from_db()
                        self.refresh_from_db()  # Reflect child_ojb's attributes, such as processing_status, to this proposal object.
                        self.child_obj.refresh_from_db()
                        #-------------------------------#
                    else:
                        # proposal type must be awaiting payment
                        self.processing_status = Proposal.PROCESSING_STATUS_AWAITING_PAYMENT
                        self.save()
                        logger.info(f'Status: [{Proposal.PROCESSING_STATUS_AWAITING_PAYMENT}] has been set to the proposal: [{self}]')

                        from mooringlicensing.components.payments_ml.models import FeeItem
                        from mooringlicensing.components.payments_ml.models import FeeItemApplicationFee

                        try:
                            logger.info(f'Creating future invoice for the application: [{self}]...')
                            ### Future Invoice ###
                            reference = self.previous_application.lodgement_number if self.previous_application else self.lodgement_number
                            invoice_text = 'Payment Invoice'
                            basket_params = {
                                'products': line_items,
                                'vouchers': [],
                                'system': settings.PAYMENT_SYSTEM_ID,
                                'custom_basket': True,
                                'booking_reference': reference,
                                'booking_reference_link': reference,
                                'no_payment': False,
                                'tax_override': True,
                            }
                            logger.info(f'basket_params: {basket_params}')

                            from ledger_api_client.utils import create_basket_session, process_create_future_invoice
                            basket_hash = create_basket_session(request, self.proposal_applicant.email_user_id, basket_params)

                            application_fee = ApplicationFee.objects.create(
                                proposal=self,
                                payment_type=ApplicationFee.PAYMENT_TYPE_TEMPORARY,
                            )
                            return_preload_url = settings.MOORING_LICENSING_EXTERNAL_URL + reverse("ledger-api-success-callback", kwargs={"uuid": application_fee.uuid})

                            basket_hash_split = basket_hash.split("|")

                            invoice_name = self.proposal_applicant.get_full_name()
                            today = timezone.localtime(timezone.now()).date()
                            days_type = NumberOfDaysType.objects.filter(code=settings.CODE_DAYS_BEFORE_DUE_PAYMENT).first()
                            days_setting = NumberOfDaysSetting.get_setting_by_date(days_type, today)
                            self.payment_due_date = today + datetime.timedelta(days=days_setting.number_of_days)
                            self.save()

                            payment_due_date = self.payment_due_date.strftime("%d/%m/%Y") if self.payment_due_date else None
                            pcfi = process_create_future_invoice(basket_hash_split[0], invoice_text, return_preload_url, invoice_name, payment_due_date)

                            application_fee.invoice_reference = pcfi['data']['invoice']
                            application_fee.save()
                            logger.info(f'ApplicationFee: [{application_fee}] has been created for the proposal: [{self}].')
                            ### END: Future Invoice ###

                            # Link between ApplicationFee and FeeItem(s)
                            for item in fee_items_to_store:
                                fee_item = FeeItem.objects.get(id=item['fee_item_id'])
                                vessel_details_id = item['vessel_details_id']  # This could be '' when null vessel application
                                vessel_details = None
                                if vessel_details_id:
                                    vessel_details = VesselDetails.objects.get(id=vessel_details_id)
                                amount_to_be_paid = item['fee_amount_adjusted']
                                fiaf = FeeItemApplicationFee.objects.create(
                                    fee_item=fee_item,
                                    application_fee=application_fee,
                                    vessel_details=vessel_details,
                                    amount_to_be_paid=amount_to_be_paid,
                                )
                                logger.info(f'FeeItemApplicationFee: [{fiaf}] has been created.')
                  
                            if not self.proposal_type.code == settings.PROPOSAL_TYPE_SWAP_MOORINGS and not self.payment_required():
                                self.approval.generate_doc()
                            
                            send_application_approved_or_declined_email(self, 'approved', request)
                            self.log_user_action(ProposalUserAction.ACTION_APPROVE_APPLICATION.format(self.lodgement_number), request)

                        except Exception as e:
                            print(e)
                            err_msg = 'Failed to create invoice'
                            logger.error('{}\n{}'.format(err_msg, str(e)))
                            raise serializers.ValidationError(err_msg)

                # Reset flag
                if self.approval:
                    self.approval.reissued = False
                    self.approval.save()

                return self
            except Exception as e:
                print(e)
                msg = 'final_approval_for_AUA_MLA. lodgement number {}, error: {}'.format(self.lodgement_number, str(e))
                logger.error(msg)
                logger.error(traceback.print_exc())
                raise e

    def final_approval(self, request=None, details=None):
        if self.child_obj.code in (WaitingListApplication.code, AnnualAdmissionApplication.code):
            self.final_approval_for_WLA_AAA(request, details)
        elif self.child_obj.code in (AuthorisedUserApplication.code, MooringLicenceApplication.code):
            return self.final_approval_for_AUA_MLA(request)

    def generate_compliances(self,approval, request):
        today = timezone.now().date()
        from mooringlicensing.components.compliances.models import Compliance, ComplianceUserAction
        if self.previous_application:
            try:
                for r in self.requirements.filter(copied_from__isnull=False):
                    cs=[]
                    cs=Compliance.objects.filter(requirement=r.copied_from, proposal=self.previous_application, processing_status__in=['due','approved'])
                    if cs:
                        if r.is_deleted == True:
                            for c in cs:
                                c.processing_status='discarded'
                                c.customer_status = 'discarded'
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
        requirement_set= self.requirements.all().exclude(is_deleted=True)

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
                                    customer_status='future',
                                    approval=approval,
                                    requirement=req,
                        )
                        compliance.log_user_action(ComplianceUserAction.ACTION_CREATE.format(compliance.id),request)
                    if req.recurrence:
                        while current_date < approval.expiry_date:
                            for x in range(req.recurrence_schedule):
                                #Weekly
                                if req.recurrence_pattern == 1:
                                    current_date += relativedelta(weeks=+1)
                                #Monthly
                                elif req.recurrence_pattern == 2:
                                    current_date += relativedelta(months=+1)
                                #Yearly
                                elif req.recurrence_pattern == 3:
                                    current_date += relativedelta(years=+1)
                                #if the recurrence pattern id is invalid, set current date to expiry to break the loop
                                else:
                                    current_date = approval.expiry_date
                            # Create the compliance
                            if current_date <= approval.expiry_date:
                                try:
                                    compliance= Compliance.objects.get(requirement = req, due_date = current_date)
                                except Compliance.DoesNotExist:
                                    compliance =Compliance.objects.create(
                                                proposal=self,
                                                due_date=current_date,
                                                processing_status='future',
                                                customer_status='future',
                                                approval=approval,
                                                requirement=req,
                                    )
                                    compliance.log_user_action(ComplianceUserAction.ACTION_CREATE.format(compliance.id),request)
            except:
                raise

    def add_vessels_and_moorings_from_licence(self):
        if self.approval and type(self) is MooringLicenceApplication:
            for vooa in self.approval.vesselownershiponapproval_set.filter(
                    Q(end_date__isnull=True) &
                    Q(vessel_ownership__end_date__isnull=True)
                    ):
                self.listed_vessels.add(vooa.vessel_ownership)
        elif self.approval and type(self) is AuthorisedUserApplication:
            for moa in self.approval.mooringonapproval_set.filter(
                    Q(end_date__isnull=True)
                    ):
                self.listed_moorings.add(moa.mooring)
        self.save()

    def clone_proposal_with_status_reset(self):
        with transaction.atomic():
            try:
                proposal = type(self.child_obj).objects.create()
                proposal.processing_status = Proposal.PROCESSING_STATUS_DRAFT
                proposal.previous_application = self
                proposal.approval = self.approval
                proposal.mooring_authorisation_preference = self.mooring_authorisation_preference
                proposal.null_vessel_on_create = not self.vessel_on_proposal()

                logger.info(f'Cloning the proposal: [{self}] to the proposal: [{proposal}]...')

                proposal.save(no_revision=True)
                self.proposal_applicant.copy_self_to_proposal(proposal)
         
                return proposal
            except:
                raise

    def renew_approval(self,request):
        from mooringlicensing.helpers import is_internal
        from mooringlicensing.components.approvals.models import Approval
        if (
            ((self.proposal_applicant and request.user.id == self.proposal_applicant.email_user_id) or is_internal(request)) and
            self.approval and
            self.approval.status in [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED, Approval.APPROVAL_STATUS_FULFILLED]
            ):
            with transaction.atomic():
                try:
                    logger.info(f'Renewing approval: [{self.approval}]...')

                    proposal = self.clone_proposal_with_status_reset()
                    proposal.proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_RENEWAL)
                    proposal.submitter = request.user.id
                    proposal.previous_application = self
                    proposal.proposed_issuance_approval= None

                    from mooringlicensing.components.approvals.models import MooringLicence
                    if self.approval.child_obj.code == MooringLicence.code:
                        proposal.allocated_mooring = self.approval.child_obj.mooring
                        # Copy links to the documents so that the documents are shown on the amendment application form
                        self.copy_proof_of_identity_documents(proposal)
                        self.copy_mooring_report_documents(proposal)
                        self.copy_written_proof_documents(proposal)
                        self.copy_signed_licence_agreement_documents(proposal)
                        self.copy_insurance_document(proposal)

                    req=self.requirements.all().exclude(is_deleted=True)
                    from copy import deepcopy
                    if req:
                        for r in req:
                            old_r = deepcopy(r)
                            r.proposal = proposal
                            r.copied_from=old_r
                            r.copied_for_renewal=True
                            if r.due_date:
                                r.due_date=None
                                r.require_due_date=True
                            r.id = None
                            r.district_proposal=None
                            r.save()

                    #Log entry for approval
                    from mooringlicensing.components.approvals.models import ApprovalUserAction
                    self.approval.log_user_action(ApprovalUserAction.ACTION_RENEW_APPROVAL.format(self.approval.id),request)
                    proposal.save(version_comment='New Amendment/Renewal Application created, from origin {}'.format(proposal.previous_application_id))
                    proposal.add_vessels_and_moorings_from_licence()

                    #proposal creation action log
                    proposal.log_user_action(f'Proposal: {proposal} created as Renewal Application for {self.approval}.', request)

                    return proposal
                except Exception as e:
                    raise e

    def amend_approval(self,request):
        from mooringlicensing.helpers import is_internal
        from mooringlicensing.components.approvals.models import Approval
        if (
            ((self.proposal_applicant and request.user.id == self.proposal_applicant.email_user_id) or is_internal(request)) and
            self.approval and
            self.approval.status in [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED, Approval.APPROVAL_STATUS_FULFILLED]
            ):
            with transaction.atomic():
                try:
                    logger.info(f'Amending approval: [{self.approval}]...')

                    add_vessel = request.data.get('add_vessel', False)  # This value comes from the radio button implemented on the proposal_apply.vue
                    proposal = self.clone_proposal_with_status_reset()
                    proposal.proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT)
                    proposal.submitter = request.user.id
                    proposal.previous_application = self
                    proposal.keep_existing_vessel = not add_vessel

                    from mooringlicensing.components.approvals.models import MooringLicence
                    if self.approval.child_obj.code == MooringLicence.code:
                        proposal.allocated_mooring = self.approval.child_obj.mooring

                        # Copy links to the documents so that the documents are shown on the amendment application form
                        self.copy_proof_of_identity_documents(proposal)
                        self.copy_mooring_report_documents(proposal)
                        self.copy_written_proof_documents(proposal)
                        self.copy_signed_licence_agreement_documents(proposal)
                        self.copy_insurance_document(proposal)

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

                    #Log entry for approval
                    from mooringlicensing.components.approvals.models import ApprovalUserAction
                    self.approval.log_user_action(ApprovalUserAction.ACTION_AMEND_APPROVAL.format(self.approval.id),request)

                    proposal.save(version_comment='New Amendment/Renewal Application created, from origin {}'.format(proposal.previous_application_id))
                    proposal.add_vessels_and_moorings_from_licence()

                    #proposal creation action log
                    proposal.log_user_action(f'Proposal: {proposal} created as Amendment Application for {self.approval}.', request)

                    return proposal
                except Exception as e:
                    raise e

    @property
    def application_type(self):
        application_type = ApplicationType.objects.get(code=self.application_type_code)
        return application_type

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

    @property
    def application_type_code(self):
        if type(self) == Proposal:
            return self.child_obj.code
        else:
            return self.code

    @property
    def description(self):
        return self.child_obj.description

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

    @classmethod
    def application_categories_dict(cls, apply_page):
        category_list = []
        for category in settings.PROPOSAL_TYPES:
            category_list.append({
                "code": category['code'],
                "description": category['description'],
            })
        return category_list

    def get_target_date(self, applied_date):
        logger.info(f'Proposal.get_target_date() is called with the parameter applied_date: {applied_date}')

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
            if (
                applied_date < self.approval.latest_applied_season.start_date 
                ):  # This should be same as self.approval.expiry_date
                # This renewal is being applied before the latest season starts
                # Therefore this application is renewal application reissued.
                target_date = self.approval.latest_applied_season.start_date
            elif self.approval.latest_applied_season.start_date <= applied_date <= self.approval.latest_applied_season.end_date:
                # This renewal application is being applied before the licence expiry
                # This is the most likely case
                # Set the target_date to the 1st day of the next season
                target_date = self.approval.latest_applied_season.end_date + datetime.timedelta(days=1)
            else:
                # Renewal application is being applied after the approval expiry date... Not sure if this is allowed.
                target_date = applied_date
        elif self.proposal_type.code in [settings.PROPOSAL_TYPE_NEW, settings.PROPOSAL_TYPE_SWAP_MOORINGS,]:
            target_date = applied_date
        else:
            raise ValueError('Unknown proposal type of the proposal: {}'.format(self))

        return target_date

    def vessel_on_proposal(self):
        from mooringlicensing.components.approvals.models import MooringLicence
        # Test to see if vessel should be read in from submitted data
        vessel_exists = False
        if self.approval and type(self.approval) is not MooringLicence:
            vessel_exists = (True if
                self.approval and self.approval.current_proposal and 
                self.approval.current_proposal.vessel_details and
                self.approval.current_proposal.vessel_ownership and
                not self.approval.current_proposal.vessel_ownership.end_date #end_date means sold
                else False)
        else:
            vessel_exists = True if self.listed_vessels.filter(end_date__isnull=True) else False
        return vessel_exists

    #TODO does not appear to be in use but may still be needed - review
    def validate_vessel_length(self, request):
        self.child_obj.validate_vessel_length(request)

    def validate_against_existing_proposals_and_approvals(self, request=None):
        self.child_obj.validate_against_existing_proposals_and_approvals(request)

    #determines if the preferred mooring bay has changed (evaluate as true if the bay has been chosen for the first time for the application)
    def mooring_preference_changed(self):
        
        previous_application_preferred_bay_id = None
        if self.previous_application and self.previous_application.preferred_bay:
            previous_application_preferred_bay_id = self.previous_application.preferred_bay.id

        if self.preferred_bay_id != previous_application_preferred_bay_id:
            return True

        return False

    #determines if the vessel category has increased for a vessel recorded on the application
    def has_higher_vessel_category(self):
        from mooringlicensing.components.proposals.utils import get_max_vessel_length_for_main_component
        max_vessel_length_with_no_payment = get_max_vessel_length_for_main_component(self)
        length = 0
        if self.vessel_length and self.rego_no:
            if (max_vessel_length_with_no_payment[0] < self.vessel_length or (
                max_vessel_length_with_no_payment[0] == self.vessel_length and
                not max_vessel_length_with_no_payment[1])):
                return True
        return False

    #check if the provided vessel on the proposal (by rego no) is in different length category (for the application) to an existing instance of that same vessel
    def has_different_vessel_category(self):
        from mooringlicensing.components.proposals.utils import get_vessel_length_category

        if not self.rego_no:
            return False
        
        vdqs = VesselDetails.objects.filter(vessel__rego_no=self.rego_no)
        if not vdqs.exists():
            return False
        else:
            vessel_details = vdqs.last()
            if vessel_details.vessel_length == self.vessel_length:
                return False

            if not self.vessel_length: #if we are here it means that the vessel details length is not none, therefore is the vessel length of the proposal is None it is in a different category
                return True

            current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
            current_datetime_str = current_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')
            target_date = self.get_target_date(current_datetime.date())
            #category of application
            new_category = get_vessel_length_category(target_date, self.vessel_length, self.proposal_type, self.application_type)
            #category of existing vessel (using params of application aside from the actual vessel_length)
            #we use the category of the current application because different applications types have their own ranges - we want to check the classification of the length of each vessel on the same terms
            #(different dates and proposal types should have consistent length ranges anyway, which is what we are concerned with)
            old_category = get_vessel_length_category(target_date, vessel_details.vessel_length, self.proposal_type, self.application_type)
            
            if old_category != new_category:
                return True
            else:
                return False

    def vessel_mooring_compatible(self, mooring):
        if not self.vessel_length or not self.vessel_draft or not self.vessel_weight:
            return False
        if (self.vessel_length > mooring.vessel_size_limit or
            self.vessel_draft > mooring.vessel_draft_limit or
            (mooring.vessel_weight_limit and self.vessel_weight > mooring.vessel_weight_limit)):
            return False
        return True

    #determines if the vessel and moorings are still compatible (if either have changed)
    def vessel_moorings_compatible(self, request=None):
        #get moorings
        if self.mooring_authorisation_preference and self.mooring_changed(request):
            #if preference has changed then check preference type
            #if a mooring has been nominated, check the vessel by that mooring - return False if incompatible
            if self.mooring_authorisation_preference == "site_licensee":
                if not self.vessel_mooring_compatible(self.mooring):
                    return False
            #otherwise, return False - RIA selection will require approval anyway
            elif self.mooring_authorisation_preference == "ria":
                return False
                    
        if self.approval:
            #check by existing active moorings for approval - whether nominated or ria - return False if any are incompatible
            moa_set = self.approval.mooringonapproval_set.filter(active=True)
            for i in moa_set:
                if not self.vessel_mooring_compatible(i.mooring):
                    return False

        return True


    def keeping_current_vessel(self):
        #on client-side check, user input is used to determine this value when the proposal vessel registration has already been saved
        #however, no such check is required to determine if the vessel is being kept or not - 
        # we just need to check if the proposal's vessel registration is the same or not

        if self.application_type_code != 'mla':
            previous_rego_no = None
            if (self.previous_application and 
                self.previous_application.vessel_details and
                self.previous_application.vessel_details.vessel and
                self.previous_application.vessel_ownership and
                not self.previous_application.vessel_ownership.end_date): #end_date means sold
                previous_rego_no = self.previous_application.vessel_details.vessel.rego_no

            if(previous_rego_no and
                previous_rego_no == self.rego_no):
                return True
        
        return False
    
    def vessel_ownership_changed(self):

        previous_ownership = None

        if self.application_type_code == 'mla':
            from mooringlicensing.components.approvals.models import VesselOwnershipOnApproval
            #account for multiple vessel ownerships
            previous_ownerships = None
            approval = None
            if self.previous_application:
                approval = self.previous_application.approval
                previous_ownerships = VesselOwnershipOnApproval.objects.filter(approval=approval).order_by('vessel_ownership__vessel','vessel_ownership__created','vessel_ownership__id').distinct('vessel_ownership__vessel')
                if previous_ownerships.exists():
                    previous_ownerships = previous_ownerships.filter(end_date=None)

            if previous_ownerships:
                #check if vo rego_no in previous_ownerships, if not return True
                if not self.rego_no: #if no rego no has been provided, then no vessel has changed
                    return False
                if previous_ownerships.filter(vessel_ownership__vessel__rego_no=self.rego_no).exists():
                    #otherwise set previous_owernship to the vo with the corresponding rego_no
                    previous_ownership = previous_ownerships.filter(vessel_ownership__vessel__rego_no=self.rego_no).last().vessel_ownership
                else:
                    return True

        else: 
            if self.previous_application:
                previous_ownership = self.previous_application.vessel_ownership
            
        if previous_ownership:
            previous_company_ownership = previous_ownership.get_latest_company_ownership()
            company_name = self.company_ownership_name
            company_percentage = self.company_ownership_percentage

            if previous_company_ownership:
                if self.individual_owner:
                    return True
                elif company_name and company_percentage:
                    if (previous_company_ownership.company.name.strip() != company_name.strip()):
                        return True
                    if (previous_company_ownership.percentage and company_percentage and
                        previous_company_ownership.percentage != company_percentage
                    ):
                        return True
            else: #no previous company ownership
                if not self.individual_owner: #company ownership
                    return True
                
        return False

    def mooring_changed(self, request=None):
        #on client-side check, user input is used to determine this value when the selected mooring has already been saved
        #however, no such check is required to determine if a new mooring is being selected or not - 
        # we just need to check if the proposal's mooring is the same or not

        #check
        if self.previous_application:
            if (self.mooring_authorisation_preference != self.previous_application.mooring_authorisation_preference):
                return True
            
            if request and "keep_existing_mooring" in request.data.get("proposal") and not request.data.get("proposal")["keep_existing_mooring"]:
                if self.mooring_authorisation_preference != 'site_licensee' or request.data.get("proposal")["site_licensee_moorings"] != []:
                    return True
            
        return False

class ProposalApplicant(RevisionedMixin):
    email_user_id = models.IntegerField(null=True, blank=True)
    proposal = models.OneToOneField(Proposal, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposal_applicant")

    # Name, etc
    first_name = models.CharField(max_length=128, null=True, blank=True, verbose_name='Given name(s)')
    last_name = models.CharField(max_length=128, null=True, blank=True)
    dob = models.DateField(auto_now=False, auto_now_add=False, null=True, blank=True, verbose_name="date of birth", help_text='')

    # Residential address
    residential_address_line1 = models.CharField('Line 1', max_length=255, null=True, blank=True)
    residential_address_line2 = models.CharField('Line 2', max_length=255, null=True, blank=True)
    residential_address_line3 = models.CharField('Line 3', max_length=255, null=True, blank=True)
    residential_address_locality = models.CharField('Suburb / Town', max_length=255, null=True, blank=True)
    residential_address_state = models.CharField(max_length=255, default='WA', null=True, blank=True)
    residential_address_country = CountryField(default='AU', null=True, blank=True)
    residential_address_postcode = models.CharField(max_length=10, null=True, blank=True)

    # Postal address
    postal_address_line1 = models.CharField('Line 1', max_length=255, null=True, blank=True)
    postal_address_line2 = models.CharField('Line 2', max_length=255, null=True, blank=True)
    postal_address_line3 = models.CharField('Line 3', max_length=255, null=True, blank=True)
    postal_address_locality = models.CharField('Suburb / Town', max_length=255, null=True, blank=True)
    postal_address_state = models.CharField(max_length=255, default='WA', null=True, blank=True)
    postal_address_country = CountryField(default='AU', null=True, blank=True)
    postal_address_postcode = models.CharField(max_length=10, null=True, blank=True)

    # Contact
    email = models.EmailField(null=True, blank=True,)
    phone_number = models.CharField(max_length=50, null=True, blank=True, verbose_name="phone number", help_text='')
    mobile_number = models.CharField(max_length=50, null=True, blank=True, verbose_name="mobile number", help_text='')
    
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    updated_at = models.DateTimeField(blank=True, null=True, auto_now=True)

    class Meta:
        app_label = 'mooringlicensing'

    def __str__(self):
        return f'{self.email}: {self.first_name} {self.last_name} (ID: {self.id})'
        
    def get_full_name(self):
        full_name = '{} {}'.format(self.first_name, self.last_name)
        return full_name

    def copy_self_to_proposal(self, target_proposal):
        proposal_applicant = ProposalApplicant.objects.create(
            proposal=target_proposal,

            first_name = self.first_name,
            last_name = self.last_name,
            dob = self.dob,

            residential_address_line1 = self.residential_address_line1,
            residential_address_line2 = self.residential_address_line2,
            residential_address_line3 = self.residential_address_line3,
            residential_address_locality = self.residential_address_locality,
            residential_address_state = self.residential_address_state,
            residential_address_country = self.residential_address_country,
            residential_address_postcode = self.residential_address_postcode,

            postal_address_line1 = self.postal_address_line1,
            postal_address_line2 = self.postal_address_line2,
            postal_address_line3 = self.postal_address_line3,
            postal_address_locality = self.postal_address_locality,
            postal_address_state = self.postal_address_state,
            postal_address_country = self.postal_address_country,
            postal_address_postcode = self.postal_address_postcode,

            email_user_id = self.email_user_id,
            email = self.email,
            phone_number = self.phone_number,
            mobile_number = self.mobile_number,
        )
        logger.info(f'ProposalApplicant: [{proposal_applicant}] has been created for the Proposal: [{target_proposal}] by copying the ProposalApplicant: [{self}].')

def update_sticker_doc_filename(instance, filename):
    return '{}/stickers/batch/{}'.format(settings.MEDIA_APP_DIR, filename)


def update_sticker_response_doc_filename(instance, filename):
    return '{}/stickers/response/{}'.format(settings.MEDIA_APP_DIR, filename)


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


class StickerPrintedContact(models.Model):
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
    _file = models.FileField(storage=private_storage,upload_to=update_sticker_doc_filename, max_length=512)
    emailed_datetime = models.DateTimeField(blank=True, null=True)  # Once emailed, this field has a value

    class Meta:
        app_label = 'mooringlicensing'


class StickerPrintingResponseEmail(SanitiseMixin):
    email_subject = models.CharField(max_length=255, blank=True, null=True)
    email_body = models.TextField(null=True, blank=True)
    email_date = models.CharField(max_length=255, blank=True, null=True)
    email_from = models.CharField(max_length=255, blank=True, null=True)
    email_message_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        app_label = 'mooringlicensing'

    def __str__(self):
        return f'Id: {self.id}, subject: {self.email_subject}'


class StickerPrintingResponse(Document):
    _file = models.FileField(storage=private_storage,upload_to=update_sticker_response_doc_filename, max_length=512)
    sticker_printing_response_email = models.ForeignKey(StickerPrintingResponseEmail, blank=True, null=True, on_delete=models.SET_NULL)
    processed = models.BooleanField(default=False)  # Processed by a cron to update sticker details
    no_errors_when_process = models.BooleanField(null=True, default=None)

    class Meta:
        app_label = 'mooringlicensing'

    def __str__(self):
        if self._file:
            return f'Id: {self.id}, {self._file.url}'
        else:
            return f'Id: {self.id}'

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


class WaitingListApplication(Proposal):
    proposal = models.OneToOneField(Proposal, parent_link=True, on_delete=models.CASCADE)
    code = 'wla'
    prefix = 'WL'

    new_application_text = "I want to apply for a position on the waiting list for a mooring site licence"

    apply_page_visibility = True
    description = 'Waiting List Application'

    class Meta:
        app_label = 'mooringlicensing'
    
    def set_auto_approve(self,request):

        #check WLA auto approval conditions
        if (self.is_assessor(request.user) or 
            self.is_approver(request.user) or
            (self.proposal_applicant and 
            self.proposal_applicant.email_user_id == request.user.id)
            ):

            if not self.vessel_on_proposal() and not self.mooring_preference_changed() and not self.rego_no: 
                self.auto_approve = True
                self.save()
            elif (
                (not self.vessel_on_proposal() and self.rego_no) or 
                self.mooring_preference_changed() or 
                self.has_higher_vessel_category() or
                self.has_different_vessel_category() or
                not self.vessel_moorings_compatible() or
                not self.keeping_current_vessel() or
                self.vessel_ownership_changed()
                ):
                self.auto_approve = False        
                self.save()
            else:
                self.auto_approve = True
                self.save()
        

    def validate_against_existing_proposals_and_approvals(self,request=None):
        from mooringlicensing.components.approvals.models import Approval, WaitingListAllocation, MooringLicence
        today = datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()

        vessel = self.vessel_ownership.vessel if self.vessel_ownership and (not self.vessel_ownership.end_date or self.vessel_ownership.end_date > today) else None

        # Get blocking proposals 
        # Checking if there are any applications still in progress
        proposals = Proposal.objects.filter(
            ((Q(vessel_details__vessel=vessel) & ~Q(vessel_details__vessel=None)) &
            (Q(vessel_ownership__end_date__gt=today) | Q(vessel_ownership__end_date__isnull=True)) |
            Q(rego_no=self.rego_no)) & # Vessel has not been sold yet
            ~Q(processing_status__in=[  # Blocking proposal's status is not in the statuses listed
            Proposal.PROCESSING_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_PRINTING_STICKER, #printing sticker is treated the same as approved
            Proposal.PROCESSING_STATUS_DECLINED,
            Proposal.PROCESSING_STATUS_EXPIRED,
            Proposal.PROCESSING_STATUS_DISCARDED,
        ])
        ).exclude(id=self.id)

        child_proposals = [proposal.child_obj for proposal in proposals]
        logger.debug(f'child_proposals: [{child_proposals}]')
        
        blocking_proposals = []  
        for proposal in child_proposals:
            if proposal.succeeding_proposals.count() == 0: # There are no succeeding proposals, which means this proposal is the lastest proposal.
                if type(proposal) == WaitingListApplication or type(proposal) == MooringLicenceApplication:
                    blocking_proposals.append(proposal)
                elif (proposal.proposal_applicant and 
                    self.proposal_applicant and 
                    proposal.proposal_applicant.email_user_id != self.proposal_applicant.email_user_id):            
                    blocking_proposals.append(proposal)

        # Get blocking approvals
        if vessel:
            approvals = Approval.objects.filter(
                (
                    (Q(current_proposal__vessel_ownership__vessel=vessel) & ~Q(current_proposal__vessel_ownership__vessel=None)) | 
                    Q(current_proposal__vessel_ownership__vessel__rego_no=self.rego_no)
                ) &
                (
                    Q(current_proposal__vessel_ownership__end_date__gt=today) | 
                    Q(current_proposal__vessel_ownership__end_date=None)
                )
            ).exclude(id=self.approval_id).filter(status__in=Approval.APPROVED_STATUSES)
        else:
            approvals = []

        blocking_approvals = []

        for approval in approvals:
            if type(approval.child_obj) == WaitingListAllocation or type(approval.child_obj) == MooringLicence:
                blocking_approvals.append(approval)
            elif (approval.child_obj.current_proposal and 
                approval.child_obj.current_proposal.proposal_applicant and 
                self.proposal_applicant and 
                approval.child_obj.current_proposal.proposal_applicant.email_user_id != self.proposal_applicant.email_user_id):     
                blocking_approvals.append(approval) 

        if (blocking_proposals):
            from mooringlicensing.helpers import is_internal
            msg = f'The vessel: {self.rego_no} is already listed in another active application'
            if request and is_internal(request):
                msg = f'The vessel: {self.rego_no} is already listed in another active application {blocking_proposals}'
            logger.error(msg)
            raise serializers.ValidationError(msg)
        elif (blocking_approvals):
            from mooringlicensing.helpers import is_internal
            msg = f'The vessel: {self.rego_no} is already listed in another active license'
            if request and is_internal(request):
                msg = f'The vessel: {self.rego_no} is already listed in another active license {blocking_approvals}'
            logger.error(msg)
            raise serializers.ValidationError(msg)
        # Person can have only one WLA, Waiting List application, Mooring Licence, and Mooring Licence application
        elif (
                self.proposal_applicant and (
                    WaitingListApplication.get_intermediate_proposals(self.proposal_applicant.email_user_id).exclude(id=self.id) or
                    WaitingListAllocation.get_intermediate_approvals(self.proposal_applicant.email_user_id).exclude(approval=self.approval) or
                    MooringLicenceApplication.get_intermediate_proposals(self.proposal_applicant.email_user_id) or
                    MooringLicence.get_valid_approvals(self.proposal_applicant.email_user_id)
                )
            ):
            msg = "Person can have only one WLA, Waiting List application, Mooring Site Licence, and Mooring Site Licence application"
            logger.error(msg)
            raise serializers.ValidationError(msg)
    
    
    def validate_vessel_length(self, request):
        min_mooring_vessel_size_str = GlobalSettings.objects.get(key=GlobalSettings.KEY_MINUMUM_MOORING_VESSEL_LENGTH).value
        min_mooring_vessel_size = float(min_mooring_vessel_size_str)

        if self.vessel_details.vessel_applicable_length < min_mooring_vessel_size:
            logger.error("Proposal {}: Vessel must be at least {}m in length".format(self, min_mooring_vessel_size_str))
            raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_mooring_vessel_size_str))

    def process_after_discarded(self):
        logger.debug(f'called in [{self}]')

    def process_after_withdrawn(self):
        logger.debug(f'called in [{self}]')

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    @staticmethod
    def get_intermediate_proposals(email_user_id):
        proposals = WaitingListApplication.objects.filter(proposal_applicant__email_user_id=email_user_id).exclude(processing_status__in=[
            Proposal.PROCESSING_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_DECLINED,
            Proposal.PROCESSING_STATUS_DISCARDED,
            Proposal.PROCESSING_STATUS_EXPIRED,
        ])
        return proposals

    def create_fee_lines(self):
        """
        Create the ledger lines - line item for application fee sent to payment system
        """
        logger.info(f'Creating fee lines for the WaitingListApplication: [{self}]...')

        from mooringlicensing.components.payments_ml.models import FeeConstructor
        from mooringlicensing.components.payments_ml.utils import generate_line_item

        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        current_datetime_str = current_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')
        target_date = self.get_target_date(current_datetime.date())
        logger.info('Creating fee lines for the proposal: [{}], target date: {}'.format(self, target_date))

        # Any changes to the DB should be made after the success of payment process
        db_processes_after_success = {}
        accept_null_vessel = False

        application_type = self.application_type

        if self.vessel_length and self.rego_no:
            vessel_length = self.vessel_length
        else:
            # No vessel specified in the application
            if self.does_accept_null_vessel:
                # For the amendment application or the renewal application, vessel field can be blank when submit.
                vessel_length = -1
                accept_null_vessel = True
            else:
                msg = 'The application fee admin data has not been set up correctly for the Waiting List application type.  Please contact the Rottnest Island Authority.'
                logger.error(msg)
                raise Exception(msg)

        logger.info(f'vessel_length: {vessel_length}')

        # Retrieve FeeItem object from FeeConstructor object
        fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_date(application_type, target_date)

        logger.info(f'FeeConstructor (for main component(WL)): {fee_constructor}')

        if not fee_constructor:
            # Fees have not been configured for this application type and date
            msg = 'FeeConstructor object for the ApplicationType: {} not found for the date: {} for the application: {}'.format(
                application_type, target_date, self.lodgement_number)
            logger.error(msg)
            raise Exception(msg)

        # Retrieve amounts paid
        max_amount_paid = self.get_max_amount_paid_for_main_component()
        logger.info(f'Max amount paid so far (for main component(WL)): ${max_amount_paid}')
        fee_item = fee_constructor.get_fee_item(vessel_length, self.proposal_type, target_date, accept_null_vessel=accept_null_vessel)
        logger.info(f'FeeItem (for main component(WL)): [{fee_item}] has been retrieved for calculation.')
        fee_amount_adjusted = self.get_fee_amount_adjusted(fee_item, vessel_length, max_amount_paid)
        logger.info(f'Fee amount adjusted (for main component(WL)) to be paid: ${fee_amount_adjusted}')

        db_processes_after_success['season_start_date'] = fee_constructor.fee_season.start_date.__str__()
        db_processes_after_success['season_end_date'] = fee_constructor.fee_season.end_date.__str__()
        db_processes_after_success['datetime_for_calculating_fee'] = current_datetime_str
        db_processes_after_success['fee_item_id'] = fee_item.id if fee_item else 0
        db_processes_after_success['fee_amount_adjusted'] = str(fee_amount_adjusted)

        line_items = []
        line_items.append(
            generate_line_item(application_type, fee_amount_adjusted, fee_constructor, self, current_datetime))

        logger.info(f'line_items calculated: {line_items}')

        return line_items, db_processes_after_success

    @property
    def assessor_group(self):
        return ledger_api_client.managed_models.SystemGroup.objects.get(name="Mooring Licensing - Assessors: Waiting List")

    @property
    def approver_group(self):
        return None

    @property
    def assessor_recipients(self):
        return [retrieve_email_userro(id).email for id in self.assessor_group.get_system_group_member_ids()]

    @property
    def approver_recipients(self):
        return []

    def is_assessor(self, user):
        from mooringlicensing.helpers import belongs_to
        if isinstance(user, EmailUserRO) and self.assessor_group:
            return belongs_to(user, self.assessor_group.name)

    def is_approver(self, user):
        from mooringlicensing.helpers import belongs_to
        if isinstance(user, EmailUserRO) and self.assessor_group:
            return belongs_to(user, self.assessor_group.name)

    def save(self, *args, **kwargs):
        super(WaitingListApplication, self).save(*args, **kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()
        self.proposal.refresh_from_db()

    def send_emails_after_payment_success(self, request):
        attachments = []
        if self.invoice:
            api_key = settings.LEDGER_API_KEY
            url = settings.LEDGER_API_URL+'/ledgergw/invoice-pdf/'+api_key+'/' + self.invoice.reference
            invoice_pdf = requests.get(url=url)

            if invoice_pdf.status_code == 200:
                attachment = ('invoice#{}.pdf'.format(self.invoice.reference), invoice_pdf.content, 'application/pdf')
                attachments.append(attachment)
        try:
            ret_value = send_confirmation_email_upon_submit(request, self, True, attachments)
            if not self.auto_approve:
                send_notification_email_upon_submit_to_assessor(request, self, attachments)
        except Exception as e:
            logger.exception("Error when sending confirmation/notification email upon submit.", exc_info=True)


    @property
    def does_accept_null_vessel(self):
        #if a vessel is sold, WLA/MLA can be amended/renewed without a new one
        if self.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,]:
            return True
        return False

    def process_after_approval(self, request=None, total_amount=0):
        logger.debug(f'called in [{self}]')


class AnnualAdmissionApplication(Proposal):
    proposal = models.OneToOneField(Proposal, parent_link=True, on_delete=models.CASCADE)
    code = 'aaa'
    prefix = 'AA'
    new_application_text = "I want to apply for an annual admission permit"
    apply_page_visibility = True
    description = 'Annual Admission Application'

    def set_auto_approve(self,request):

        if self.approval_has_pending_stickers():
            self.auto_approve = False        
            self.save()
        else:
            #check AAA auto approval conditions
            if (self.is_assessor(request.user) or 
                self.is_approver(request.user) or
                (self.proposal_applicant and 
                self.proposal_applicant.email_user_id == request.user.id)
                ):
                if self.proposal_type and (
                self.proposal_type.code == PROPOSAL_TYPE_AMENDMENT or 
                self.proposal_type.code == PROPOSAL_TYPE_RENEWAL):
                    self.auto_approve = True
                    self.save()

    def validate_against_existing_proposals_and_approvals(self,request=None):
        from mooringlicensing.components.approvals.models import Approval, WaitingListAllocation, AnnualAdmissionPermit, MooringLicence, AuthorisedUserPermit
        today = datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()

        vessel = self.vessel_ownership.vessel if self.vessel_ownership and (not self.vessel_ownership.end_date or self.vessel_ownership.end_date > today) else None

        # Get blocking proposals
        proposals = Proposal.objects.filter(
            ((Q(vessel_details__vessel=vessel) & ~Q(vessel_details__vessel=None)) &
            (Q(vessel_ownership__end_date__gt=today) | Q(vessel_ownership__end_date__isnull=True)) |
            Q(rego_no=self.rego_no)) & # Vessel has not been sold yet
            ~Q(processing_status__in=[  # Blocking proposal's status is not in the statuses listed
            Proposal.PROCESSING_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_PRINTING_STICKER, #printing sticker is treated the same as approved
            Proposal.PROCESSING_STATUS_DECLINED,
            Proposal.PROCESSING_STATUS_EXPIRED,
            Proposal.PROCESSING_STATUS_DISCARDED,
        ])
        ).exclude(id=self.id)

        child_proposals = [proposal.child_obj for proposal in proposals]
        logger.debug(f'child_proposals: [{child_proposals}]')
        proposals_mla = []
        proposals_aaa = []
        proposals_aua = []
        proposals_wla = []
        for proposal in child_proposals:
            if type(proposal) == MooringLicenceApplication:
                proposals_mla.append(proposal)
            if type(proposal) == AnnualAdmissionApplication:
                proposals_aaa.append(proposal)
            if type(proposal) == AuthorisedUserApplication:
                proposals_aua.append(proposal)
            if type(proposal) == WaitingListApplication:
                #only blocks if from a different user/owner
                if (proposal.proposal_applicant and 
                    self.proposal_applicant and 
                    proposal.proposal_applicant.email_user_id != self.proposal_applicant.email_user_id):
                    proposals_wla.append(proposal)

        # Get blocking approvals
        if vessel:
            approvals = Approval.objects.filter(
                (
                    (Q(current_proposal__vessel_ownership__vessel=vessel) & ~Q(current_proposal__vessel_ownership__vessel=None)) | 
                    Q(current_proposal__vessel_ownership__vessel__rego_no=self.rego_no)
                ) &
                (
                    Q(current_proposal__vessel_ownership__end_date__gt=today) | 
                    Q(current_proposal__vessel_ownership__end_date=None)
                )
            ).exclude(id=self.approval_id).filter(status__in=Approval.APPROVED_STATUSES)
        else:
            approvals = []

        approvals_ml = []
        approvals_aap = []
        approvals_aup = []
        approvals_wla = []
        for approval in approvals:
            if type(approval.child_obj) == MooringLicence:
                approvals_ml.append(approval)
            if type(approval.child_obj) == AnnualAdmissionPermit:
                approvals_aap.append(approval)
            if type(approval.child_obj) == AuthorisedUserPermit:
                approvals_aup.append(approval)
            if type(approval.child_obj) == WaitingListAllocation:
                #only blocks if from a different user/owner
                if (approval.child_obj.current_proposal and 
                    approval.child_obj.current_proposal.proposal_applicant and 
                    self.proposal_applicant and 
                    approval.child_obj.current_proposal.proposal_applicant.email_user_id != self.proposal_applicant.email_user_id):
                    approvals_wla.append(approval)

        if proposals_aaa or approvals_aap or proposals_aua or approvals_aup or proposals_mla or approvals_ml or proposals_wla or approvals_wla:
            list_sum = proposals_aaa + proposals_aua + proposals_mla + approvals_aap + approvals_aup + approvals_ml + proposals_wla + approvals_wla
            raise serializers.ValidationError("The vessel in the application is already listed in " +
            ", ".join(['{} {} '.format(item.description, item.lodgement_number) for item in list_sum]))

    def validate_vessel_length(self, request):
        min_vessel_size_str = GlobalSettings.objects.get(key=GlobalSettings.KEY_MINIMUM_VESSEL_LENGTH).value
        min_vessel_size = float(min_vessel_size_str)

        if self.vessel_details.vessel_applicable_length < min_vessel_size:
            logger.error("Proposal {}: Vessel must be at least {}m in length".format(self, min_vessel_size_str))
            raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_vessel_size_str))

    def process_after_discarded(self):
        logger.debug(f'called in [{self}]')

    def process_after_withdrawn(self):
        logger.debug(f'called in [{self}]')

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    def create_fee_lines(self):
        """
        Create the ledger lines - line item for application fee sent to payment system
        """
        logger.info(f'Creating fee lines for the AnnualAdmissionApplication: [{self}]...')

        from mooringlicensing.components.payments_ml.models import FeeConstructor
        from mooringlicensing.components.payments_ml.utils import generate_line_item

        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        current_datetime_str = current_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')
        target_date = self.get_target_date(current_datetime.date())
        annual_admission_type = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)  # Used for AUA / MLA

        logger.info('Creating fee lines for the proposal: [{}], target date: {}'.format(self, target_date))

        # Any changes to the DB should be made after the success of payment process
        db_processes_after_success = {}
        accept_null_vessel = False

        if self.vessel_length and self.rego_no:
            vessel_length = self.vessel_length
        else:
            # No vessel specified in the application
            if self.does_accept_null_vessel:
                # For the amendment application or the renewal application, vessel field can be blank when submit.
                vessel_length = -1
                accept_null_vessel = True
            else:
                msg = 'The application fee admin data has not been set up correctly for the Annual Admission Permit application type.  Please contact the Rottnest Island Authority.'
                logger.error(msg)
                raise Exception(msg)

        logger.info(f'vessel_length: {vessel_length}')

        # Retrieve FeeItem object from FeeConstructor object
        fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_date(self.application_type, target_date)

        logger.info(f'FeeConstructor (for main component(AA)): {fee_constructor}')

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

        # Retrieve amounts paid
        max_amount_paid = self.get_max_amount_paid_for_main_component()
        logger.info(f'Max amount paid so far (for main component(AA)): ${max_amount_paid}')
        fee_item = fee_constructor.get_fee_item(vessel_length, self.proposal_type, target_date, accept_null_vessel=accept_null_vessel)
        logger.info(f'FeeItem (for main component(AA)): [{fee_item}] has been retrieved for calculation.')
        fee_amount_adjusted = self.get_fee_amount_adjusted(fee_item, vessel_length, max_amount_paid)
        logger.info(f'Fee amount adjusted (for main component(AA)) to be paid: ${fee_amount_adjusted}')

        db_processes_after_success['season_start_date'] = fee_constructor.fee_season.start_date.__str__()
        db_processes_after_success['season_end_date'] = fee_constructor.fee_season.end_date.__str__()
        db_processes_after_success['datetime_for_calculating_fee'] = current_datetime_str
        db_processes_after_success['fee_item_id'] = fee_item.id if fee_item else 0
        db_processes_after_success['fee_amount_adjusted'] = str(fee_amount_adjusted)

        line_items = []
        line_items.append(generate_line_item(self.application_type, fee_amount_adjusted, fee_constructor, self, current_datetime))

        logger.info(f'line_items calculated: {line_items}')

        return line_items, db_processes_after_success

    @property
    def assessor_group(self):
        return ledger_api_client.managed_models.SystemGroup.objects.get(name="Mooring Licensing - Assessors: Annual Admission")

    @property
    def approver_group(self):
        return None

    @property
    def assessor_recipients(self):
        return [retrieve_email_userro(id).email for id in self.assessor_group.get_system_group_member_ids()]

    @property
    def approver_recipients(self):
        return []

    def is_assessor(self, user):
        from mooringlicensing.helpers import belongs_to
        if isinstance(user, EmailUserRO) and self.assessor_group:
            return belongs_to(user, self.assessor_group.name)

    def is_approver(self, user):
        from mooringlicensing.helpers import belongs_to
        if isinstance(user, EmailUserRO) and self.assessor_group:
            return belongs_to(user, self.assessor_group.name)

    def save(self, *args, **kwargs):
        super(AnnualAdmissionApplication, self).save(*args,**kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()
        self.proposal.refresh_from_db()

    def send_emails_after_payment_success(self, request):
        attachments = []
        if self.invoice:
            api_key = settings.LEDGER_API_KEY
            url = settings.LEDGER_API_URL+'/ledgergw/invoice-pdf/'+api_key+'/' + self.invoice.reference
            invoice_pdf = requests.get(url=url)

            if invoice_pdf.status_code == 200:
                attachment = (f'invoice#{self.invoice.reference}', invoice_pdf.content, 'application/pdf')
                attachments.append(attachment)
        if not self.auto_approve:
            try:
                send_confirmation_email_upon_submit(request, self, True, attachments)
                send_notification_email_upon_submit_to_assessor(request, self, attachments)
            except Exception as e:
                logger.exception("Error when sending confirmation/notification email upon submit.", exc_info=True)


    def process_after_approval(self, request=None, total_amount=0):
        logger.debug(f'called in [{self}]')

    @property
    def does_accept_null_vessel(self):
        #if a vessel has been sold, a amendment/renewal can be made without submitting a new one
        if self.proposal_type.code in (PROPOSAL_TYPE_AMENDMENT,PROPOSAL_TYPE_RENEWAL):
            return True
        return False


class AuthorisedUserApplication(Proposal):
    proposal = models.OneToOneField(Proposal, parent_link=True, on_delete=models.CASCADE)
    code = 'aua'
    prefix = 'AU'
    new_application_text = "I want to apply for an authorised user permit"
    apply_page_visibility = True
    description = 'Authorised User Application'

    # This uuid is used to generate the URL for the AUA endorsement link
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    def validate_against_existing_proposals_and_approvals(self,request=None):
        from mooringlicensing.components.approvals.models import Approval, AuthorisedUserPermit
        today = datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()

        vessel = self.vessel_ownership.vessel if self.vessel_ownership and (not self.vessel_ownership.end_date or self.vessel_ownership.end_date > today) else None

        # Get blocking proposals
        proposals = Proposal.objects.filter(
            ((Q(vessel_details__vessel=vessel) & ~Q(vessel_details__vessel=None)) &
            (Q(vessel_ownership__end_date__gt=today) | Q(vessel_ownership__end_date__isnull=True)) |
            Q(rego_no=self.rego_no)) & # Vessel has not been sold yet
            ~Q(processing_status__in=[  # Blocking proposal's status is not in the statuses listed
            Proposal.PROCESSING_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_PRINTING_STICKER, #printing sticker is treated the same as approved
            Proposal.PROCESSING_STATUS_DECLINED,
            Proposal.PROCESSING_STATUS_EXPIRED,
            Proposal.PROCESSING_STATUS_DISCARDED,
        ])
        ).exclude(id=self.id)

        child_proposals = [proposal.child_obj for proposal in proposals]
        logger.debug(f'child_proposals: [{child_proposals}]')

        proposals_aua = []
        proposals_other = []
        for proposal in child_proposals:
            if type(proposal) == AuthorisedUserApplication:
                proposals_aua.append(proposal)
            elif (proposal.proposal_applicant and 
                self.proposal_applicant and 
                proposal.proposal_applicant.email_user_id != self.proposal_applicant.email_user_id):
                proposals_other.append(proposal)

        # Get blocking approvals
        if vessel:
            approvals = Approval.objects.filter(
                (
                    (Q(current_proposal__vessel_ownership__vessel=vessel) & ~Q(current_proposal__vessel_ownership__vessel=None)) | 
                    Q(current_proposal__vessel_ownership__vessel__rego_no=self.rego_no)
                ) &
                (
                    Q(current_proposal__vessel_ownership__end_date__gt=today) | 
                    Q(current_proposal__vessel_ownership__end_date=None)
                )
            ).exclude(id=self.approval_id).filter(status__in=Approval.APPROVED_STATUSES)
        else:
            approvals = []
        
        approvals_aup = []
        approvals_other = []
        for approval in approvals:
            if type(approval.child_obj) == AuthorisedUserPermit:
                approvals_aup.append(approval)
            elif (approval.child_obj.current_proposal and 
                approval.child_obj.current_proposal.proposal_applicant and 
                self.proposal_applicant and 
                approval.child_obj.current_proposal.proposal_applicant.email_user_id != self.proposal_applicant.email_user_id):
                approvals_other.append(approval)

        if proposals_aua or approvals_aup:
            raise serializers.ValidationError("The vessel in the application is already listed in " +  
                ", ".join(['{} {} '.format(proposal.description, proposal.lodgement_number) for proposal in proposals_aua]) +
                ", ".join(['{} {} '.format(approval.description, approval.lodgement_number) for approval in approvals_aup])
            )
        elif proposals_other or approvals_other:
            raise serializers.ValidationError("The vessel in the application is already listed in " +  
                ", ".join(['{} {} '.format(proposal.description, proposal.lodgement_number) for proposal in proposals_other]) +
                ", ".join(['{} {} '.format(approval.description, approval.lodgement_number) for approval in approvals_other])
            )

    def validate_vessel_length(self, request):
        min_vessel_size_str = GlobalSettings.objects.get(key=GlobalSettings.KEY_MINIMUM_VESSEL_LENGTH).value
        min_vessel_size = float(min_vessel_size_str)

        if self.vessel_details.vessel_applicable_length < min_vessel_size:
            logger.error("Proposal {}: Vessel must be at least {}m in length".format(self, min_vessel_size_str))
            raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_vessel_size_str))

        # check new site licensee moorings
        proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}
            
        site_licensee_moorings_data = proposal_data.get('site_licensee_moorings')
        moorings = Mooring.objects
        for i in site_licensee_moorings_data:
            mooring = moorings.filter(mooring__id=i["mooring_id"]).first()
            if (self.vessel_details.vessel_applicable_length > mooring.vessel_size_limit or
            self.vessel_details.vessel_draft > mooring.vessel_draft_limit):
                logger.error("Proposal {}: Vessel unsuitable for mooring".format(self))
                raise serializers.ValidationError("Vessel unsuitable for mooring")

        if self.approval:
            # Amend / Renewal
            if proposal_data.get('keep_existing_mooring'):
                # check existing moorings against current vessel dimensions
                for moa in self.approval.mooringonapproval_set.filter(end_date__isnull=True):
                    if self.vessel_details.vessel_applicable_length > moa.mooring.vessel_size_limit:
                        logger.error(f"Vessel applicable lentgh: [{self.vessel_details.vessel_applicable_length}] is not suitable for the mooring: [{moa.mooring}]")
                        raise serializers.ValidationError(f"Vessel length: {self.vessel_details.vessel_applicable_length}[m] is not suitable for the vessel size limit: {moa.mooring.vessel_size_limit} [m] of the mooring: [{moa.mooring}]")
                    if self.vessel_details.vessel_draft > moa.mooring.vessel_draft_limit:
                        logger.error(f"Vessel draft: [{self.vessel_details.vessel_draft}] is not suitable for the mooring: [{moa.mooring}]")
                        raise serializers.ValidationError(f"Vessel draft: {self.vessel_details.vessel_draft} [m] is not suitable for the vessel draft limit: {moa.mooring.vessel_draft_limit} [m] of the mooring: [{moa.mooring}]")

    def process_after_discarded(self):
        logger.debug(f'called in [{self}]')

    def process_after_withdrawn(self):
        logger.debug(f'called in [{self}]')

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    def create_fee_lines(self):
        """ Create the ledger lines - line item for application fee sent to payment system """
        logger.info(f'Creating fee lines for the AuthorisedUserApplication: [{self}]...')

        from mooringlicensing.components.payments_ml.models import FeeConstructor
        from mooringlicensing.components.payments_ml.utils import generate_line_item

        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        target_date = self.get_target_date(current_datetime.date())
        annual_admission_type = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)  # Used for AUA / MLA
        accept_null_vessel = False

        logger.info('Creating fee lines for the proposal: [{}], target date: {}'.format(self, target_date))

        if self.vessel_length and self.rego_no:
            vessel_length = self.vessel_length
        else:
            # No vessel specified in the application
            if self.does_accept_null_vessel:
                # For the amendment application or the renewal application, vessel field can be blank when submit.
                vessel_length = -1
                accept_null_vessel = True
            else:
                msg = 'The application fee admin data has not been set up correctly for the Authorised User Permit application type.  Please contact the Rottnest Island Authority.'
                logger.error(msg)
                raise Exception(msg)

        logger.info(f'vessel_length: {vessel_length}')

        # Retrieve FeeItem object from FeeConstructor object
        fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_date(self.application_type, target_date)
        fee_constructor_for_aa = FeeConstructor.get_fee_constructor_by_application_type_and_date(annual_admission_type, target_date)

        logger.info(f'FeeConstructor (for main component(AU)): {fee_constructor}')
        logger.info(f'FeeConstructor (for AA component): {fee_constructor_for_aa}')

        # There is also annual admission fee component for the AUA/MLA if needed.
        ml_exists_for_this_vessel = False
        application_has_vessel = True if self.vessel_details or self.rego_no else False

        vessel_details = self.vessel_details if self.vessel_details else None

        if not vessel_details:
            vd_qs = VesselDetails.objects.filter(vessel__rego_no=self.rego_no).order_by('-id')
            if vd_qs.exists():
                vessel_details = vd_qs.first()
                vessel_details.vessel_length = self.vessel_length

        if application_has_vessel:
            if vessel_details:
                # When there is a vessel in this application
                current_approvals_dict = vessel_details.vessel.get_current_approvals(target_date)
                for key, approvals in current_approvals_dict.items():
                    if key == 'mls' and approvals.count():
                        ml_exists_for_this_vessel = True

                if ml_exists_for_this_vessel:
                    logger.info(f'ML for the vessel: {vessel_details.vessel} exists. No charges for the AUP: {self}')

                    # When there is 'current' ML, no charge for the AUP
                    # But before leaving here, we want to store the fee_season under this application the user is applying for.
                    self.fee_season = fee_constructor.fee_season
                    self.save()

                    logger.info(f'FeeSeason: {fee_constructor.fee_season} is saved under the proposal: {self}')
                    fee_lines = [generate_line_item(self.application_type, 0, fee_constructor, self, current_datetime),]

                    return fee_lines, {}  # no line items, no db process
                else:
                    logger.info(f'ML for the vessel: {vessel_details.vessel} does not exist.')
        else:
            # Null vessel application
            logger.info(f'This is null vessel application')

        fee_items_to_store = []
        line_items = []

        # Retrieve amounts paid
        max_amount_paid = self.get_max_amount_paid_for_main_component()
        logger.info(f'Max amount paid so far (for main component(AU)): ${max_amount_paid}')
        fee_item = fee_constructor.get_fee_item(vessel_length, self.proposal_type, target_date, accept_null_vessel=accept_null_vessel)
        logger.info(f'FeeItem (for main component(AU)): [{fee_item}] has been retrieved for calculation.')
        fee_amount_adjusted = self.get_fee_amount_adjusted(fee_item, vessel_length, max_amount_paid)
        logger.info(f'Fee amount adjusted (for main component(AU)) to be paid: ${fee_amount_adjusted}')

        fee_items_to_store.append({
            'fee_item_id': fee_item.id,
            'vessel_details_id': vessel_details.id if vessel_details else '',
            'fee_amount_adjusted': str(fee_amount_adjusted),
        })
        line_items.append(generate_line_item(self.application_type, fee_amount_adjusted, fee_constructor, self, current_datetime))

        if application_has_vessel:
            if vessel_details:
                # When the application has a vessel, user have to pay for the AA component, too.
                max_amount_paid = self.get_max_amount_paid_for_aa_component(target_date, vessel_details.vessel)
                logger.info(f'Max amount paid so far (for AA component): ${max_amount_paid}')
                fee_item_for_aa = fee_constructor_for_aa.get_fee_item(vessel_length, self.proposal_type, target_date) if fee_constructor_for_aa else None
                logger.info(f'FeeItem (for AA component): [{fee_item_for_aa}] has been retrieved for calculation.')
                fee_amount_adjusted_additional = self.get_fee_amount_adjusted(fee_item_for_aa, vessel_length, max_amount_paid)
                logger.info(f'Fee amount adjusted (for AA component) to be paid: ${fee_amount_adjusted_additional}')

                fee_items_to_store.append({
                    'fee_item_id': fee_item_for_aa.id,
                    'vessel_details_id': vessel_details.id if vessel_details else '',
                    'fee_amount_adjusted': str(fee_amount_adjusted_additional),
                })
                line_items.append(generate_line_item(annual_admission_type, fee_amount_adjusted_additional, fee_constructor_for_aa, self, current_datetime))
            else:
                fee_item_for_aa = fee_constructor_for_aa.get_fee_item(vessel_length, self.proposal_type, target_date) if fee_constructor_for_aa else None
                logger.info(f'FeeItem (for AA component): [{fee_item_for_aa}] has been retrieved for calculation.')
                fee_amount_adjusted_additional = self.get_fee_amount_adjusted(fee_item_for_aa, vessel_length, 0)
                logger.info(f'Fee amount adjusted (for AA component) to be paid: ${fee_amount_adjusted_additional}')

                fee_items_to_store.append({
                    'fee_item_id': fee_item_for_aa.id,
                    'vessel_details_id': '',
                    'fee_amount_adjusted': str(fee_amount_adjusted_additional),
                })
                line_items.append(generate_line_item(annual_admission_type, fee_amount_adjusted_additional, fee_constructor_for_aa, self, current_datetime))

        logger.info(f'line_items calculated: {line_items}')

        return line_items, fee_items_to_store

    def get_due_date_for_endorsement_by_target_date(self, target_date=timezone.localtime(timezone.now()).date()):
        days_type = NumberOfDaysType.objects.filter(code=CODE_DAYS_FOR_ENDORSER_AUA).first()
        days_setting = NumberOfDaysSetting.get_setting_by_date(days_type, target_date)
        if not days_setting:
            # No number of days found
            raise ImproperlyConfigured("NumberOfDays: {} is not defined for the date: {}".format(days_type.name, target_date))
        due_date = self.lodgement_date + datetime.timedelta(days=days_setting.number_of_days)
        return due_date

    @property
    def assessor_group(self):
        return ledger_api_client.managed_models.SystemGroup.objects.get(name="Mooring Licensing - Assessors: Authorised User")

    @property
    def approver_group(self):
        return ledger_api_client.managed_models.SystemGroup.objects.get(name="Mooring Licensing - Approvers: Authorised User")

    @property
    def assessor_recipients(self):
        return [retrieve_email_userro(i).email for i in self.assessor_group.get_system_group_member_ids()]

    @property
    def approver_recipients(self):
        return [retrieve_email_userro(i).email for i in self.approver_group.get_system_group_member_ids()]

    def is_assessor(self, user):
        from mooringlicensing.helpers import belongs_to
        if isinstance(user, EmailUserRO) and self.assessor_group:
            return belongs_to(user, self.assessor_group.name)

    def is_approver(self, user):
        from mooringlicensing.helpers import belongs_to
        if isinstance(user, EmailUserRO) and self.approver_group:
            return belongs_to(user, self.approver_group.name)

    def save(self, *args, **kwargs):
        super(AuthorisedUserApplication, self).save(*args, **kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()
        self.proposal.refresh_from_db()

    def send_emails_after_payment_success(self, request):
        return True

    def get_mooring_authorisation_preference(self):
        if self.keep_existing_mooring and self.previous_application:
            return self.previous_application.child_obj.get_mooring_authorisation_preference()
        else:
            return self.mooring_authorisation_preference

    def set_auto_approve(self,request):

        if self.approval_has_pending_stickers():
            self.auto_approve = False        
            self.save()
        else:
            #check AUP auto approval conditions
            if (self.is_assessor(request.user) or 
                self.is_approver(request.user) or
                (self.proposal_applicant and 
                self.proposal_applicant.email_user_id == request.user.id)
                ):

                #check if amendment or renewal
                if self.proposal_type and (
                    self.proposal_type.code == PROPOSAL_TYPE_AMENDMENT or 
                    self.proposal_type.code == PROPOSAL_TYPE_RENEWAL):
                    if (not self.vessel_on_proposal() or
                        self.mooring_changed(request) or
                        not self.vessel_moorings_compatible(request) or
                        self.has_higher_vessel_category() or
                        self.has_different_vessel_category() or
                        not self.keeping_current_vessel() or
                        self.vessel_ownership_changed()
                        ):
                        self.auto_approve = False
                        self.save()
                    else:
                        self.auto_approve = True
                        self.save()
                else:
                    self.auto_approve = False
                    self.save()

    def process_after_submit(self, request):
        self.lodgement_date = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        self.save()
        self.log_user_action(ProposalUserAction.ACTION_LODGE_APPLICATION.format(self.lodgement_number), request)
        mooring_preference = self.get_mooring_authorisation_preference()

        if not (self.auto_approve and (self.proposal_type.code == PROPOSAL_TYPE_RENEWAL or self.proposal_type.code == PROPOSAL_TYPE_AMENDMENT)):
            if ((mooring_preference.lower() != 'ria' and self.proposal_type.code == PROPOSAL_TYPE_NEW) or
                (mooring_preference.lower() != 'ria' and self.proposal_type.code != PROPOSAL_TYPE_NEW and not self.keep_existing_mooring)):
                # Mooring preference is 'site_licensee' and which is new mooring applying for.
                self.processing_status = Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT
                self.save()
                # Email to endorser
                send_endorsement_of_authorised_user_application_email(request, self)
                send_confirmation_email_upon_submit(request, self, False)
            else:
                if not self.auto_approve:
                    self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
                    self.save()
                    send_confirmation_email_upon_submit(request, self, False)
                    send_notification_email_upon_submit_to_assessor(request, self)

    def update_or_create_approval(self, current_datetime, request=None):
        from mooringlicensing.components.proposals.utils import submit_vessel_data
        logger.info(f'Updating/Creating Authorised User Permit from the application: [{self}]...')
        try:
            # This function is called after payment success for new/amendment/renewal application
            # Manage approval
            approval_created = False
            if self.proposal_type.code == PROPOSAL_TYPE_NEW:
                # When new application
                approval, approval_created = self.approval_class.objects.update_or_create(
                    current_proposal=self,
                    defaults={
                        'issue_date': current_datetime,
                        'start_date': current_datetime.date(),
                        'expiry_date': self.end_date,
                        'submitter': self.submitter,
                    }
                )
                if approval_created:
                    from mooringlicensing.components.approvals.models import Approval
                    logger.info(f'Approval: [{approval}] has been created.')
                    approval.cancel_existing_annual_admission_permit(current_datetime.date())

                    self.approval = approval
                    self.save()

            elif self.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
                if self.auto_approve and request:
                    submit_vessel_data(self, request, approving=True)
                    self.refresh_from_db()

                # When amendment application
                approval = self.approval.child_obj
                approval.current_proposal = self
                approval.issue_date = current_datetime
                approval.start_date = current_datetime.date()
                # We don't need to update expiry_date when amendment.  Also self.end_date can be None.
                approval.submitter = self.submitter
                approval.save()
            elif self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
                if self.auto_approve and request:
                    submit_vessel_data(self, request, approving=True)
                    self.refresh_from_db()

                # When renewal application
                approval = self.approval.child_obj
                approval.current_proposal = self
                approval.issue_date = current_datetime
                approval.start_date = current_datetime.date()
                approval.expiry_date = self.end_date
                approval.submitter = self.submitter
                approval.renewal_sent = False
                approval.renewal_count += 1
                approval.save()

            # update proposed_issuance_approval and MooringOnApproval if not system reissue (no request) or auto_approve
            if request and not self.auto_approve:
                # Create MooringOnApproval records
                ## also see logic in approval.add_mooring()
                mooring_id_pk = self.proposed_issuance_approval.get('mooring_id')
                ria_selected_mooring = None
                if mooring_id_pk:
                    ria_selected_mooring = Mooring.objects.get(id=mooring_id_pk)

                if ria_selected_mooring:
                    approval.add_mooring(mooring=ria_selected_mooring, site_licensee=False)
                else:
                    for moa in self.proposed_issuance_approval.get('requested_mooring_on_approval'):
                        if moa.get("checked"):
                            requested_mooring = Mooring.objects.get(id=moa.get("id"))
                            approval.add_mooring(mooring=requested_mooring, site_licensee=True)
                # updating checkboxes
                for moa1 in self.proposed_issuance_approval.get('mooring_on_approval'):
                    for moa2 in self.approval.mooringonapproval_set.filter(mooring__mooring_licence__status='current'):
                        # convert proposed_issuance_approval to an end_date
                        if moa1.get("id") == moa2.id and not moa1.get("checked") and not moa2.end_date:
                            moa2.end_date = current_datetime.date()
                            moa2.active = False
                            moa2.save()
                        elif moa1.get("id") == moa2.id and moa1.get("checked") and moa2.end_date:
                            moa2.end_date = None
                            moa2.active = True
                            moa2.save()
            # set auto_approve renewal application ProposalRequirement due dates to those from previous application + 12 months
            if self.auto_approve and self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
                for req in self.requirements.filter(is_deleted=False):
                    if req.copied_from and req.copied_from.due_date:
                        req.due_date = req.copied_from.due_date + relativedelta(months=+12)
                        req.save()
            # do not process compliances for system reissue
            if request:
                # Generate compliances
                from mooringlicensing.components.compliances.models import Compliance, ComplianceUserAction
                target_proposal = self.previous_application if self.proposal_type.code == PROPOSAL_TYPE_AMENDMENT else self.proposal
                for compliance in Compliance.objects.filter(
                    approval=approval.approval,
                    proposal=target_proposal,
                    processing_status='future',
                    ):
                    compliance.processing_status='discarded'
                    compliance.customer_status = 'discarded'
                    compliance.post_reminder_sent=True
                    compliance.save()
                self.generate_compliances(approval, request)

            # only reset this flag if it is a renewal
            if self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
                approval.renewal_sent = False
                
            approval.export_to_mooring_booking = True
            approval.save()

            # set proposal status to approved - can change later after manage_stickers
            self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
            self.save()

            # Retrieve newely added moorings, and send authorised user summary doc to the licence holder
            mls_to_be_emailed = []
            from mooringlicensing.components.approvals.models import MooringOnApproval, MooringLicence, Approval, Sticker
            new_moas = MooringOnApproval.objects.filter(approval=approval, sticker__isnull=True, end_date__isnull=True, active=True)  # New moa doesn't have stickers.
            for new_moa in new_moas:
                mls_to_be_emailed = MooringLicence.objects.filter(mooring=new_moa.mooring, status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,])

            # manage stickers
            moas_to_be_reallocated, stickers_to_be_returned = approval.manage_stickers(self)

            self.refresh_from_db()
            #####
            # Set proposal status after manage _stickers
            #####
            stickers_to_be_printed = []
            if self.approval:
                stickers_not_exported = self.approval.stickers.filter(status__in=[Sticker.STICKER_STATUS_NOT_READY_YET, Sticker.STICKER_STATUS_READY,])
                stickers_to_be_printed = self.approval.stickers.filter(status__in=[Sticker.STICKER_STATUS_AWAITING_PRINTING,])

            if len(stickers_to_be_returned):
                a_sticker = stickers_to_be_returned[0]  # All the stickers to be returned should have the same vessel, so just pick the first one
                if self.vessel_ownership and a_sticker.vessel_ownership.vessel.rego_no == self.vessel_ownership.vessel.rego_no:
                    # Same vessel
                    if stickers_not_exported:
                        self.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                        self.log_user_action(ProposalUserAction.ACTION_PRINTING_STICKER.format(self.lodgement_number), )
                    else:
                        self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                else:
                    # Vessel changed OR null vessel
                    # there is a sticker to be returned, application status gets 'Sticker to be Returned' status
                    self.processing_status = Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED
                    self.log_user_action(ProposalUserAction.ACTION_STICKER_TO_BE_RETURNED.format(self.lodgement_number), request)
            else:
                # There are no stickers to be returned - before and after the sticker for this application has been printed
                if stickers_not_exported:
                    #if we are here, it is an entirely new application and we need a sticker (or a renewal where the vessel has been changed)
                    self.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                    self.log_user_action(ProposalUserAction.ACTION_PRINTING_STICKER.format(self.lodgement_number),)
                else:
                    #otherwise with no stickers to be returned, the application should be approved - this can only occur on an auto-approved amend/renew
                    self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                    self.log_user_action(ProposalUserAction.ACTION_PRINTING_STICKER.format(self.lodgement_number),)

            self.save()
            self.proposal.save()

            approval.generate_doc()
            self.proposal.refresh()  # so that the approval doc field is updated by the doc generated above

            # Email - do not send if internal reissue (i.e. only send if there is a request)
            if request:
                send_application_approved_or_declined_email(self.proposal, 'approved_paid', request, stickers_to_be_returned)

            # Email to ML holder when new moorings added
            for mooring_licence in mls_to_be_emailed:
                mooring_licence.generate_au_summary_doc()
                if not self.mooring_authorisation_preference == 'ria':
                    send_au_summary_to_ml_holder(mooring_licence, request, self)

            # Log proposal action
            if self.auto_approve or not request:
                self.log_user_action(ProposalUserAction.ACTION_AUTO_APPROVED.format(self.id))

            # Write approval history
            if self.approval and self.approval.reissued:
                if request:
                    approval.write_approval_history('Reissue via application {}'.format(self.lodgement_number))
            elif self.proposal_type == ProposalType.objects.get(code=PROPOSAL_TYPE_RENEWAL):
                approval.write_approval_history('Renewal application {}'.format(self.lodgement_number))
            elif self.proposal_type == ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT):
                approval.write_approval_history('Amendment application {}'.format(self.lodgement_number))
            else:
                approval.write_approval_history()

            self.save()
            self.proposal.save()

            return approval, approval_created
        except Exception as e:
            print(e)
            msg = 'Payment taken for Proposal: {}, but approval creation has failed\n{}'.format(self.lodgement_number, str(e))
            logger.error(msg)
            logger.error(traceback.print_exc())
            raise e

    @property
    def does_accept_null_vessel(self):
        #if a vessel has been sold, a amendment/renewal can be made without submitting a new one
        if self.proposal_type.code in (PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,):
            return True
        return False


class MooringLicenceApplication(Proposal):
    REASON_FOR_EXPIRY_NOT_SUBMITTED = 'not_submitted'
    REASON_FOR_EXPIRY_NO_DOCUMENTS = 'no_documents'

    proposal = models.OneToOneField(Proposal, parent_link=True, on_delete=models.CASCADE)
    code = 'mla'
    prefix = 'ML'
    new_application_text = ""
    apply_page_visibility = False
    description = 'Mooring Site Licence Application'

    # This uuid is used to generate the URL for the ML document upload page
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    def reinstate_wl_allocation(self, request):
        wlallocation = self.waiting_list_allocation.reinstate_wla_order()
        self.log_user_action(f'Reinstate Waiting List Alocation: {wlallocation.lodgement_number} back to the waiting list queue.', request)
        return wlallocation

    def validate_against_existing_proposals_and_approvals(self,request=None):
        from mooringlicensing.components.approvals.models import Approval, ApprovalHistory, MooringLicence
        today = datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()

        vessel = self.vessel_ownership.vessel if self.vessel_ownership and (not self.vessel_ownership.end_date or self.vessel_ownership.end_date > today) else None

        # Get blocking proposals
        proposals = Proposal.objects.filter(
            ((Q(vessel_details__vessel=vessel) & ~Q(vessel_details__vessel=None)) &
            (Q(vessel_ownership__end_date__gt=today) | Q(vessel_ownership__end_date__isnull=True)) |
            Q(rego_no=self.rego_no)) & # Vessel has not been sold yet
            ~Q(processing_status__in=[  # Blocking proposal's status is not in the statuses listed
            Proposal.PROCESSING_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_PRINTING_STICKER, #printing sticker is treated the same as approved
            Proposal.PROCESSING_STATUS_DECLINED,
            Proposal.PROCESSING_STATUS_EXPIRED,
            Proposal.PROCESSING_STATUS_DISCARDED,
        ])
        ).exclude(id=self.id)

        child_proposals = [proposal.child_obj for proposal in proposals]
        logger.debug(f'child_proposals: [{child_proposals}]')

        proposals_mla = []
        proposals_other = []
        for proposal in child_proposals:
            if type(proposal) == MooringLicenceApplication:
                proposals_mla.append(proposal)
            elif (proposal.proposal_applicant and 
                self.proposal_applicant and 
                proposal.proposal_applicant.email_user_id != self.proposal_applicant.email_user_id):
                proposals_other.append(proposal)

        # Get blocking approvals
        if vessel:
            approvals = Approval.objects.filter(
                (
                    (Q(current_proposal__vessel_ownership__vessel=vessel) & ~Q(current_proposal__vessel_ownership__vessel=None)) | 
                    Q(current_proposal__vessel_ownership__vessel__rego_no=self.rego_no)
                ) &
                (
                    Q(current_proposal__vessel_ownership__end_date__gt=today) | 
                    Q(current_proposal__vessel_ownership__end_date=None)
                )
            ).exclude(id=self.approval_id).filter(status__in=Approval.APPROVED_STATUSES)
        else:
            approvals = []

        approvals_ml = []
        approvals_other = []
        for approval in approvals:
            if type(approval.child_obj) == MooringLicence:
                approvals_ml.append(approval)
            elif (approval.child_obj.current_proposal and 
                approval.child_obj.current_proposal.proposal_applicant and 
                self.proposal_applicant and 
                approval.child_obj.current_proposal.proposal_applicant.email_user_id != self.proposal_applicant.email_user_id):
                approvals_other.append(approval)

        if proposals_mla or approvals_ml:
            raise serializers.ValidationError("The vessel in the application is already listed in " +  
                ", ".join(['{} {} '.format(proposal.description, proposal.lodgement_number) for proposal in proposals_mla]) +
                ", ".join(['{} {} '.format(approval.description, approval.lodgement_number) for approval in approvals_ml])
            )
        elif proposals_other or approvals_other:
            raise serializers.ValidationError("The vessel in the application is already listed in " +  
                ", ".join(['{} {} '.format(proposal.description, proposal.lodgement_number) for proposal in proposals_other]) +
                ", ".join(['{} {} '.format(approval.description, approval.lodgement_number) for approval in approvals_other])
            )

    def validate_vessel_length(self, request):
        min_vessel_size_str = GlobalSettings.objects.get(key=GlobalSettings.KEY_MINIMUM_VESSEL_LENGTH).value
        min_vessel_size = float(min_vessel_size_str)
        min_mooring_vessel_size_str = GlobalSettings.objects.get(key=GlobalSettings.KEY_MINUMUM_MOORING_VESSEL_LENGTH).value
        min_mooring_vessel_size = float(min_mooring_vessel_size_str)

        if self.proposal_type.code in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT]:
            # Even when renewal/amendment, there might not be the vessels on the approval because of the sales of the vessels.  Check it.
            min_vessel_applicable_length = self.approval.child_obj.get_current_min_vessel_applicable_length()

            if min_vessel_applicable_length > min_mooring_vessel_size:
                # There is already a sufficient size vessel for ML.
                if self.vessel_details.vessel_applicable_length < min_vessel_size:
                    logger.error("Proposal {}: Vessel must be at least {}m in length".format(self, min_vessel_size_str))
                    raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_vessel_size_str))
            else:
                # There are no sufficient size vessels for ML.
                if self.vessel_details.vessel_applicable_length < min_mooring_vessel_size:
                    logger.error("Proposal {}: Vessel must be at least {}m in length".format(self, min_mooring_vessel_size_str))
                    raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_mooring_vessel_size))
            if self.vessel_details.vessel_applicable_length > self.approval.child_obj.mooring.vessel_size_limit or self.vessel_details.vessel_draft > self.approval.child_obj.mooring.vessel_draft_limit:
                # Vessel is too long / Vessel draft is too deep
                logger.error("Proposal {}: Vessel unsuitable for mooring".format(self))
                raise serializers.ValidationError("Vessel unsuitable for mooring")
        elif self.vessel_details.vessel_applicable_length < min_mooring_vessel_size:
            logger.error("Proposal {}: Vessel must be at least {}m in length".format(self, min_mooring_vessel_size_str))
            raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_mooring_vessel_size_str))

    def process_after_discarded(self):
        if self.waiting_list_allocation:
            self.waiting_list_allocation.process_after_discarded()

    def process_after_withdrawn(self):
        if self.waiting_list_allocation:
            self.waiting_list_allocation.process_after_withdrawn()

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    @staticmethod
    def get_intermediate_proposals(email_user_id):
        proposals = MooringLicenceApplication.objects.filter(proposal_applicant__email_user_id=email_user_id).exclude(processing_status__in=[
            Proposal.PROCESSING_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_DECLINED,
            Proposal.PROCESSING_STATUS_DISCARDED,
            Proposal.PROCESSING_STATUS_EXPIRED,
        ])
        return proposals

    def create_fee_lines(self):
        """ Create the ledger lines - line item for application fee sent to payment system """
        logger.info(f'Creating fee lines for the MooringLicenceApplication: [{self}]...')

        from mooringlicensing.components.payments_ml.models import FeeConstructor
        from mooringlicensing.components.payments_ml.utils import generate_line_item

        accept_null_vessel = False
        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        target_date = self.get_target_date(current_datetime.date())
        annual_admission_type = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)  # Used for AUA / MLA

        if self.proposal_type.code == PROPOSAL_TYPE_SWAP_MOORINGS:
            from mooringlicensing.components.payments_ml.models import OracleCodeItem
            total_amount = float(GlobalSettings.objects.get(key=GlobalSettings.KEY_FEE_AMOUNT_OF_SWAP_MOORINGS).value)
            incur_gst = True if GlobalSettings.objects.get(key=GlobalSettings.KEY_SWAP_MOORINGS_INCLUDES_GST).value.lower() in ['true', 't', 'yes', 'y'] else False
            if settings.ROUND_FEE_ITEMS:
                # In debug environment, we want to avoid decimal number which may cause some kind of error.
                total_amount = round(float(total_amount))
                total_amount_excl_tax = round(float(calculate_excl_gst(total_amount))) if incur_gst else round(float(total_amount))
            else:
                total_amount_excl_tax = float(calculate_excl_gst(total_amount) if incur_gst else total_amount)

            oracle_code = OracleCodeItem.objects.filter(date_of_enforcement__lte=target_date, application_type__code='mooring_swap').last().value
            # When this proposal is for Swap-Moorings, it's easy.
            return [{
                'ledger_description': 'Mooring Swap',
                'oracle_code': oracle_code,
                'price_incl_tax': total_amount, 
                'price_excl_tax': total_amount_excl_tax,
                'quantity': 1,
            }], []

        logger.info('Creating fee lines for the proposal: [{}], target date: {}'.format(self.lodgement_number, target_date))

        # Retrieve FeeItem object from FeeConstructor object
        fee_constructor_for_ml = FeeConstructor.get_fee_constructor_by_application_type_and_date(self.application_type, target_date)
        fee_constructor_for_aa = FeeConstructor.get_fee_constructor_by_application_type_and_date(annual_admission_type, target_date)

        logger.info(f'FeeConstructor (for main component(ML)): [{fee_constructor_for_ml}] has been retrieved for calculation.')
        logger.info(f'FeeConstructor (for AA component): [{fee_constructor_for_aa}] has been retrieved for calculation.')

        vessel_detais_list_to_be_processed = []
        vessel_details_largest = None  # As a default value
        largest_rego_no = None
        
        if self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
            # Only when 'Renewal' application, we are interested in the existing vessels
            vessel_list = self.approval.child_obj.vessel_list_for_payment()
            for vessel in vessel_list:
                vessel_detais_list_to_be_processed.append(vessel.latest_vessel_details)
                if vessel_details_largest:
                    if vessel_details_largest.vessel_applicable_length < vessel.latest_vessel_details.vessel_applicable_length:
                        vessel_details_largest = vessel.latest_vessel_details
                        largest_rego_no = vessel.rego_no
                else:
                    vessel_details_largest = vessel.latest_vessel_details
                    largest_rego_no = vessel.rego_no

        line_items = []  # Store all the line items
        fee_items_to_store = []  # Store all the fee_items

        logger.info(f'Largest vessel details are [{vessel_details_largest}] for the application: [{self}].')

        # For Mooring Licence component
        if self.vessel_length and self.rego_no:
            if vessel_details_largest:
                if self.vessel_length > vessel_details_largest.vessel_applicable_length:
                    vessel_length = self.vessel_length
                    largest_rego_no = self.rego_no
                else:
                    vessel_length = vessel_details_largest.vessel_applicable_length
            else:
                vessel_length = self.vessel_length
                largest_rego_no = self.rego_no
        else:
            # No vessel specified in the application
            if self.does_accept_null_vessel:
                # For the amendment application or the renewal application, vessel field can be blank when submit.
                vessel_length = -1
                accept_null_vessel = True
            else:
                msg = 'The application fee admin data has not been set up correctly for the Mooring Site Licence application type.  Please contact the Rottnest Island Authority.'
                logger.error(msg)
                raise Exception(msg)

        logger.info(f'The largest size of vessels to be considered here is [{vessel_length}]m for the proposal: [{self}].')

        # Retrieve amounts paid
        max_amount_paid = self.get_max_amount_paid_for_main_component()
        logger.info(f'Max amount paid so far (for main component(ML)): ${max_amount_paid}')
        fee_item = fee_constructor_for_ml.get_fee_item(vessel_length, self.proposal_type, target_date, accept_null_vessel=accept_null_vessel)
        logger.info(f'FeeItem (for main component(ML)): [{fee_item}] has been retrieved for calculation.')
        fee_amount_adjusted = self.get_fee_amount_adjusted(fee_item, vessel_length, max_amount_paid)
        logger.info(f'Fee amount adjusted (for main component(ML)) to be paid: ${fee_amount_adjusted}')

        if vessel_details_largest:
            fee_items_to_store.append({
                'fee_item_id': fee_item.id,
                'vessel_details_id': vessel_details_largest.id if vessel_details_largest else '',
                'fee_amount_adjusted': str(fee_amount_adjusted),
            })
            line_items.append(generate_line_item(self.application_type, fee_amount_adjusted, fee_constructor_for_ml, self, current_datetime, largest_rego_no))
        else: #if there is no vessel_details_largest then use the provided proposal details
            fee_items_to_store.append({
                'fee_item_id': fee_item.id,
                'vessel_details_id': '',
                'fee_amount_adjusted': str(fee_amount_adjusted),
            })
            line_items.append(generate_line_item(self.application_type, fee_amount_adjusted, fee_constructor_for_ml, self, current_datetime, self.rego_no))

        # For Annual Admission component
        if vessel_detais_list_to_be_processed:
            submitted_vessel_processed = False
            for vessel_details in vessel_detais_list_to_be_processed:
                # Annual admission fee is applied to each vessel.
                if not vessel_details:
                    continue  # When the application was submitted with null-vessel and there are no existing vessels, process reaches this line.
                vessel_length = vessel_details.vessel_applicable_length
                if self.rego_no == vessel_details.vessel.rego_no:
                    submitted_vessel_processed = True
                    vessel_length = self.vessel_length
                max_amount_paid = self.get_max_amount_paid_for_aa_component(target_date, vessel_details.vessel)
                logger.info(f'Max amount paid so far (for AA component): ${max_amount_paid}')
                # Check if there is already an AA component paid for this vessel
                fee_item_for_aa = fee_constructor_for_aa.get_fee_item(vessel_length, self.proposal_type, target_date)
                logger.info(f'FeeItem (for AA component): [{fee_item_for_aa}] has been retrieved for calculation.')
                fee_amount_adjusted_additional = self.get_fee_amount_adjusted(fee_item_for_aa, vessel_length, max_amount_paid)
                logger.info(f'Fee amount adjusted (for AA component): ${fee_amount_adjusted_additional}')

                fee_items_to_store.append({
                    'fee_item_id': fee_item_for_aa.id,
                    'vessel_details_id': vessel_details.id if vessel_details else '',
                    'fee_amount_adjusted': str(fee_amount_adjusted_additional),
                })
                line_items.append(generate_line_item(annual_admission_type, fee_amount_adjusted_additional, fee_constructor_for_aa, self, current_datetime, vessel_details.vessel.rego_no))
            #for when a new vessel is submitted on a renewal
            if not submitted_vessel_processed:
                vessel_length = self.vessel_length
                fee_item_for_aa = fee_constructor_for_aa.get_fee_item(vessel_length, self.proposal_type, target_date)
                logger.info(f'FeeItem (for AA component): [{fee_item_for_aa}] has been retrieved for calculation.')
                fee_amount_adjusted_additional = self.get_fee_amount_adjusted(fee_item_for_aa, vessel_length, 0)
                fee_items_to_store.append({
                    'fee_item_id': fee_item_for_aa.id,
                    'vessel_details_id': '',
                    'fee_amount_adjusted': str(fee_amount_adjusted_additional),
                })
                line_items.append(generate_line_item(annual_admission_type, fee_amount_adjusted_additional, fee_constructor_for_aa, self, current_datetime, self.rego_no))

        else: #only one vessel to process on the application, not a renewal
            vessel_details_qs = VesselDetails.objects.filter(vessel__rego_no=self.rego_no).order_by('id')
            vessel_details = None
            
            if vessel_details_qs.exists():
                vessel_details = vessel_details_qs.last()
                max_amount_paid = self.get_max_amount_paid_for_aa_component(target_date, vessel_details.vessel)
            else:
                max_amount_paid = self.get_max_amount_paid_for_aa_component(target_date)
            logger.info(f'Max amount paid so far (for AA component): ${max_amount_paid}')
            # Check if there is already an AA component paid for this vessel
            if vessel_length > 0:
                fee_item_for_aa = fee_constructor_for_aa.get_fee_item(vessel_length, self.proposal_type, target_date)
                logger.info(f'FeeItem (for AA component): [{fee_item_for_aa}] has been retrieved for calculation.')
                fee_amount_adjusted_additional = self.get_fee_amount_adjusted(fee_item_for_aa, vessel_length, max_amount_paid)
                logger.info(f'Fee amount adjusted (for AA component): ${fee_amount_adjusted_additional}')

                fee_items_to_store.append({
                    'fee_item_id': fee_item_for_aa.id,
                    'vessel_details_id': vessel_details.id if vessel_details else '',
                    'fee_amount_adjusted': str(fee_amount_adjusted_additional),
                })
                line_items.append(generate_line_item(annual_admission_type, fee_amount_adjusted_additional, fee_constructor_for_aa, self, current_datetime, self.rego_no))

        logger.info(f'line_items calculated: {line_items}')
        logger.info(f'fee_items_to_store: {fee_items_to_store}')

        self.fee_season = fee_constructor_for_ml.fee_season
        self.save()

        return line_items, fee_items_to_store

    def get_document_upload_url(self, request):
        document_upload_url = request.build_absolute_uri(reverse('mla-documents-upload', kwargs={'uuid_str': self.uuid}))
        return document_upload_url

    @property
    def assessor_group(self):
        return ledger_api_client.managed_models.SystemGroup.objects.get(name=GROUP_ASSESSOR_MOORING_LICENCE)

    @property
    def approver_group(self):
        return ledger_api_client.managed_models.SystemGroup.objects.get(name=GROUP_APPROVER_MOORING_LICENCE)

    @property
    def assessor_recipients(self):
        emails = []
        for id in self.assessor_group.get_system_group_member_ids():
            emails.append(retrieve_email_userro(id).email)
        return emails

    @property
    def approver_recipients(self):
        emails = []
        for id in self.approver_group.get_system_group_member_ids():
            emails.append(retrieve_email_userro(id).email)
        return emails

    def is_assessor(self, user):
        from mooringlicensing.helpers import belongs_to
        if isinstance(user, EmailUserRO) and self.assessor_group:
            return belongs_to(user, self.assessor_group.name)

    def is_approver(self, user):
        from mooringlicensing.helpers import belongs_to
        if isinstance(user, EmailUserRO) and self.approver_group:
            return belongs_to(user, self.approver_group.name)

    def save(self, *args, **kwargs):
        super(MooringLicenceApplication, self).save(*args, **kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()
        self.proposal.refresh_from_db()

    def process_after_submit_other_documents(self, request):
        from mooringlicensing.components.approvals.models import WaitingListAllocation
        self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
        if self.waiting_list_allocation:
            self.waiting_list_allocation.internal_status = WaitingListAllocation.INTERNAL_STATUS_SUBMITTED
            self.waiting_list_allocation.save()
        self.save()

        # Log actions
        self.log_user_action(ProposalUserAction.ACTION_SUBMIT_OTHER_DOCUMENTS, request)

        # Send email to assessors
        send_other_documents_submitted_notification_email(request, self)

    def send_emails_after_payment_success(self, request):
        return True

    def has_new_vessel(self):
        from mooringlicensing.components.approvals.models import VesselOwnershipOnApproval
        if self.previous_application:
            approval = self.previous_application.approval
            if VesselOwnershipOnApproval.objects.filter(vessel_ownership__vessel__rego_no=self.rego_no,vessel_ownership__end_date=None,approval=approval).exists():
                return False
            else:
                return True
        return True


    def set_auto_approve(self,request):

        if self.approval_has_pending_stickers():
            self.auto_approve = False        
            self.save()
        else:    
            #check MLA auto approval conditions
            if (self.is_assessor(request.user) or 
                self.is_approver(request.user) or
                (self.proposal_applicant and 
                self.proposal_applicant.email_user_id == request.user.id)
                ):

                #check if amendment or renewal
                if self.proposal_type and (
                    self.proposal_type.code == PROPOSAL_TYPE_AMENDMENT or 
                    self.proposal_type.code == PROPOSAL_TYPE_RENEWAL):
                    if (not self.vessel_on_proposal() or
                        not self.vessel_moorings_compatible(request) or
                        self.has_higher_vessel_category() or
                        self.has_different_vessel_category() or
                        self.vessel_ownership_changed() or
                        self.has_new_vessel()
                        ):
                        self.auto_approve = False
                        self.save()
                    else:
                        self.auto_approve = True
                        self.save()
                else:
                    self.auto_approve = False
                    self.save()

    def process_after_submit(self, request):
        self.lodgement_date = datetime.datetime.now(pytz.timezone(TIME_ZONE))
        self.log_user_action(ProposalUserAction.ACTION_LODGE_APPLICATION.format(self.lodgement_number), request)

        if self.proposal_type in (ProposalType.objects.filter(code__in=[PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT,])):
            # Renewal
            if not self.auto_approve:
                self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
                send_confirmation_email_upon_submit(request, self, False)
                send_notification_email_upon_submit_to_assessor(request, self)
        else:
            # New
            if self.amendment_requests.count():
                # Amendment request
                self.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
                send_confirmation_email_upon_submit(request, self, False)
                send_notification_email_upon_submit_to_assessor(request, self)
            else:
                self.processing_status = Proposal.PROCESSING_STATUS_AWAITING_DOCUMENTS
                send_documents_upload_for_mooring_licence_application_email(request, self)
                send_notification_email_upon_submit_to_assessor(request, self)
        self.save()
        logger.info(f'Status: [{self.processing_status}] has been set to the proposal: [{self}].')

    def update_or_create_approval(self, current_datetime, request=None):
        from mooringlicensing.components.proposals.utils import submit_vessel_data
        from mooringlicensing.components.approvals.models import Approval
        logger.info(f'Updating/Creating Mooring Site Licence from the application: [{self}]...')
        try:
            # renewal/amendment/reissue - associated ML must have a mooring
            if self.approval and hasattr(self.approval.child_obj, 'mooring') and self.approval.child_obj.mooring:
                existing_mooring_licence = self.approval.child_obj
            else:
                existing_mooring_licence = self.allocated_mooring.mooring_licence if self.allocated_mooring else None
            
            if self.proposal_type.code == settings.PROPOSAL_TYPE_SWAP_MOORINGS:
                # When swap moorings, self.allocated_mooring should have a target mooring.
                mooring = self.allocated_mooring
            else:
                mooring = existing_mooring_licence.mooring if existing_mooring_licence else self.allocated_mooring

            approval_created = False

            if self.proposal_type.code in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_SWAP_MOORINGS,]:
                approval = self.approval.child_obj
                approval.current_proposal=self
                approval.issue_date = current_datetime
                approval.start_date = current_datetime.date()

                if self.auto_approve and request:
                    submit_vessel_data(self, request, approving=True)
                    self.refresh_from_db()

                if self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
                    # When renewal, we have to update the expiry_date of the approval
                    approval.expiry_date = self.end_date
                    #if the approval expired, set back to current on being re-approved
                    if approval.status == Approval.APPROVAL_STATUS_EXPIRED:
                        approval.status = Approval.APPROVAL_STATUS_CURRENT

                approval.submitter = self.submitter
                approval.save()
                if self.proposal_type.code == PROPOSAL_TYPE_SWAP_MOORINGS:
                    current_mooring = approval.mooring if hasattr(approval, 'mooring') else None
                    target_mooring = self.allocated_mooring

                    if current_mooring:
                        if current_mooring.mooring_licence == approval:
                            # Mooring should only ever have one mooring license assigned at a time, set mooring_licence to None prior to adding new one
                            current_mooring.mooring_licence = None
                            current_mooring.save()
                            logger.info(f'Remove the link between the MSL: [{approval}] and the mooring: [{current_mooring}].')
                            current_mooring.handle_aups_after_save_mooring(request)

                            temp_licence = target_mooring.mooring_licence
                            target_mooring.mooring_licence = None
                            target_mooring.save()
                            logger.info(f'Remove the link between the MSL: [{temp_licence}] and the mooring: [{target_mooring}].')
                            target_mooring.handle_aups_after_save_mooring(request)

                    # Create new relation between the approval and the mooring
                    target_mooring.mooring_licence = approval
                    target_mooring.save()
                    target_mooring.mooring_licence.authorised_user_summary_document = None
                    logger.info(f'Create a link between the MSL: [{approval}] and the mooring: [{target_mooring}].')
            else:
                approval, approval_created = self.approval_class.objects.update_or_create(
                    current_proposal=self,
                    defaults={
                        'issue_date': current_datetime,
                        'start_date': current_datetime.date(),
                        'expiry_date': self.end_date,
                        'submitter': self.submitter,
                    }
                )

                if approval_created:
                    logger.info(f'Approval: [{approval}] has been created.')
                    approval.cancel_existing_annual_admission_permit(current_datetime.date())

                # associate mooring licence with mooring, only on NEW proposal_type
                if not self.approval:
                    self.allocated_mooring.mooring_licence = approval
                    self.allocated_mooring.save()
                # always associate proposal with approval
                if approval_created:
                    self.approval = approval
                    self.save()
                # Move WLA to status approved
                if self.waiting_list_allocation:
                    self.waiting_list_allocation.process_after_approval()

            # update proposed_issuance_approval and MooringOnApproval if not system reissue (no request) or auto_approve
            if request and not self.auto_approve:
                # Create VesselOwnershipOnApproval records
                ## also see logic in approval.add_vessel_ownership()
                vooa, created = approval.add_vessel_ownership(vessel_ownership=self.vessel_ownership)

                # updating checkboxes
                for vo1 in self.proposed_issuance_approval.get('vessel_ownership'):
                    for vo2 in self.approval.vesselownershiponapproval_set.all():
                        # convert proposed_issuance_approval to an end_date
                        if vo1.get("id") == vo2.vessel_ownership.id and not vo1.get("checked") and not vo2.end_date:
                            vo2.end_date = current_datetime.date()
                            vo2.save()
                        elif vo1.get("id") == vo2.vessel_ownership.id and vo1.get("checked") and vo2.end_date:
                            vo2.end_date = None
                            vo2.save()
            # set auto_approve renewal application ProposalRequirement due dates to those from previous application + 12 months
            if self.auto_approve and self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
                for req in self.requirements.filter(is_deleted=False):
                    if req.copied_from and req.copied_from.due_date:
                        req.due_date = req.copied_from.due_date + relativedelta(months=+12)
                        req.save()
            # do not process compliances for system reissue
            if request:
                # Generate compliances
                from mooringlicensing.components.compliances.models import Compliance, ComplianceUserAction
                target_proposal = self.previous_application if self.proposal_type.code == PROPOSAL_TYPE_AMENDMENT else self.proposal
                for compliance in Compliance.objects.filter(
                    approval=approval.approval,
                    proposal=target_proposal,
                    processing_status='future',
                    ):
                    compliance.processing_status = Compliance.PROCESSING_STATUS_DISCARDED
                    compliance.customer_status = Compliance.CUSTOMER_STATUS_DISCARDED
                    compliance.post_reminder_sent=True
                    compliance.save()
                self.generate_compliances(approval, request)

            if request:
                mooring.log_user_action(
                    MooringUserAction.ACTION_ASSIGN_MOORING_LICENCE.format(
                        str(approval),
                    ),
                    request
                )
                
            # only reset this flag if it is a renewal
            if self.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
                approval.renewal_sent = False

            approval.export_to_mooring_booking = True
            approval.save()

            # set proposal status to approved - can change later after manage_stickers
            self.processing_status = Proposal.PROCESSING_STATUS_APPROVED
            self.save()

            # manage stickers
            moas_to_be_reallocated, stickers_to_be_returned = approval.manage_stickers(self)

            # Creating documents should be performed at the end
            approval.generate_doc()

            #end all approval moorings on previous ML
            if self.proposal_type.code == settings.PROPOSAL_TYPE_SWAP_MOORINGS:
                approval.process_mooring_approvals_before_swap()

            if self.proposal_type.code in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_SWAP_MOORINGS,]:
                approval.generate_au_summary_doc()

            # Email with attachments
            send_application_approved_or_declined_email(self, 'approved_paid', request, stickers_to_be_returned)

            # Log proposal action
            if self.auto_approve or not request:
                self.log_user_action(ProposalUserAction.ACTION_AUTO_APPROVED.format(self.id))

            # write approval history
            if self.approval and self.approval.reissued:
                approval.write_approval_history('Reissue via application {}'.format(self.lodgement_number))
            elif self.proposal_type == ProposalType.objects.get(code=PROPOSAL_TYPE_RENEWAL):
                approval.write_approval_history('Renewal application {}'.format(self.lodgement_number))
            elif self.proposal_type == ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT):
                approval.write_approval_history('Amendment application {}'.format(self.lodgement_number))
            else:
                approval.write_approval_history()

            return approval, approval_created
        except Exception as e:
            print(e)
            msg = 'Payment taken for Proposal: {}, but approval creation has failed\n{}'.format(self.lodgement_number, str(e))
            logger.error(msg)
            logger.error(traceback.print_exc())
            raise e

    @property
    def does_accept_null_vessel(self):
        if self.proposal_type.code in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_SWAP_MOORINGS,]:
            return True
        return False


class ProposalLogDocument(Document):
    log_entry = models.ForeignKey('ProposalLogEntry',related_name='documents', on_delete=models.CASCADE)
    _file = models.FileField(storage=private_storage,upload_to=update_proposal_comms_log_filename, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'


class ProposalLogEntryManager(models.Manager):
    def create(self, *args, **kwargs):
        if 'customer' in kwargs and isinstance(kwargs['customer'], EmailUserRO):
            kwargs['customer'] = kwargs['customer'].id
        if 'staff' in kwargs and isinstance(kwargs['staff'], EmailUserRO):
            kwargs['staff'] = kwargs['staff'].id
        return super(ProposalLogEntryManager, self).create(*args, **kwargs)


class ProposalLogEntry(CommunicationsLogEntry):
    proposal = models.ForeignKey(Proposal, related_name='comms_logs', on_delete=models.CASCADE)
    objects = ProposalLogEntryManager()

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


class MooringBay(RevisionedMixin):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=3, blank=True, null=True)
    mooring_bookings_id = models.IntegerField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Mooring Bays"
        app_label = 'mooringlicensing'


class PrivateMooringManager(models.Manager):
    def get_queryset(self):
        return super(PrivateMooringManager, self).get_queryset().filter(mooring_bookings_mooring_specification=2)


class AuthorisedUserMooringManager(models.Manager):
    def get_queryset(self):
        ret = super(AuthorisedUserMooringManager, self).get_queryset().filter(mooring_bookings_mooring_specification=2,)
        return ret


class AvailableMooringManager(models.Manager):
    def get_queryset(self):
        from mooringlicensing.components.approvals.models import Approval

        available_ids = []
        for mooring in Mooring.private_moorings.all():
            # first check mooring_licence status
            if not mooring.mooring_licence or mooring.mooring_licence.status != Approval.APPROVAL_STATUS_CURRENT:
                # now check whether there are any blocking proposals
                blocking_proposal = False
                for proposal in mooring.ria_generated_proposal.all():
                    if proposal.processing_status not in [
                        Proposal.PROCESSING_STATUS_APPROVED, 
                        Proposal.PROCESSING_STATUS_DECLINED, 
                        Proposal.PROCESSING_STATUS_DISCARDED, 
                        Proposal.PROCESSING_STATUS_EXPIRED,
                    ]:
                        blocking_proposal = True
                if not blocking_proposal:
                    available_ids.append(mooring.id)

        return super(AvailableMooringManager, self).get_queryset().filter(id__in=available_ids)


class Mooring(RevisionedMixin):
    MOORING_SPECIFICATION = (
         (1, 'Rental Mooring'),
         (2, 'Private Mooring'),
    )

    name = models.CharField(max_length=100)
    mooring_bay = models.ForeignKey(MooringBay, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    vessel_size_limit = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', help_text = "Any required changes should be done via Mooring Bookings.") # does not exist in MB
    vessel_draft_limit = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', help_text = "Any required changes should be done via Mooring Bookings.")
    vessel_beam_limit = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_weight_limit = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', help_text = "Any required changes should be done via Mooring Bookings.") # tonnage
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
    # mooring licence can onl,y have one Mooring
    mooring_licence = models.OneToOneField('MooringLicence', blank=True, null=True, related_name="mooring", on_delete=models.SET_NULL)
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)

    def handle_aups_after_save_mooring(self, request):
        logger.debug(f'in handle_aups_after_save_mooring().  self: [{self}]')

        from mooringlicensing.components.approvals.models import Approval, MooringOnApproval

        today=datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()

        if not self.mooring_licence:
            # This mooring doesn't have a link to any mooring_licences
            query = Q()
            query &= Q(mooring=self)
            query &= Q(approval__status__in=[Approval.APPROVAL_STATUS_SUSPENDED, Approval.APPROVAL_STATUS_CURRENT,])
            query &= Q(Q(end_date__gt=today) | Q(end_date__isnull=True))  # No end date or future end date
            query &= Q(active=True)
            
            # Retrieve all the AUPs which link to the mooring without any MSLs.  Which means we have to set the end_date and cancell the AUPs.
            active_mooring_on_approvals = MooringOnApproval.objects.filter(query)

            for active_mooring_on_approval in active_mooring_on_approvals:
                logger.debug(f'active_mooring_on_approval: [{active_mooring_on_approval}]')

                # Set end date.
                active_mooring_on_approval.end_date = today  
                active_mooring_on_approval.save()
                logger.info(f'End date: [{today}] has been set to the MooringOnApproval: [{active_mooring_on_approval}] .')

                active_mooring_on_approval.approval.manage_stickers()  
                active_mooring_on_approval.approval.generate_doc()
                send_aup_revoked_due_to_mooring_swap_email(request, active_mooring_on_approval.approval.child_obj, active_mooring_on_approval.mooring, [active_mooring_on_approval.sticker,])
        

    def __str__(self):
        return f'{self.name} (Bay: {self.mooring_bay.name})'

    class Meta:
        verbose_name_plural = "Moorings"
        app_label = 'mooringlicensing'

    def log_user_action(self, action, request):
        return MooringUserAction.log_action(self, action, request.user.id)

    @property
    def status(self):
        status = ''
        ## check for Mooring Licences
        if self.mooring_licence and self.mooring_licence.status in ['current', 'suspended']:
            status = 'Licensed'
        if not status:
            # check for Mooring Applications
            proposals = self.ria_generated_proposal.exclude(processing_status__in=['approved', 'declined', 'discarded'])
            for proposal in proposals:
                if proposal.child_obj.code == 'mla':
                    status = 'Licence Application'
        return status if status else 'Unlicensed'

    def suitable_vessel(self, vessel_details):
        suitable = True
        if vessel_details.vessel_applicable_length > self.vessel_size_limit or vessel_details.vessel_draft > self.vessel_draft_limit:
            suitable = False
        return suitable


class ProposalSiteLicenseeMooringRequest(models.Model):
    proposal = models.ForeignKey(Proposal, null=True, blank=True, on_delete=models.SET_NULL, related_name="site_licensee_mooring_request")
    site_licensee_email = models.CharField(max_length=200, blank=True, null=True)
    mooring = models.ForeignKey(Mooring, null=True, blank=True, on_delete=models.SET_NULL, related_name="site_licensee_mooring_request")
    endorser_reminder_sent = models.BooleanField(default=False)
    declined_by_endorser = models.BooleanField(default=False)
    approved_by_endorser = models.BooleanField(default=False)

    enabled = models.BooleanField(default=True) #enabled for proposal by submitter/applicant
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = 'mooringlicensing'

    def endorse_approved(self, request):
        if not self.proposal or self.proposal.processing_status != Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT:
            if not (self.proposal.is_assessor(request.user) and (
                self.proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR or
                self.proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS
            )):
                raise serializers.ValidationError("proposal not awaiting endorsement")
        
        if not self.proposal.is_assessor(request.user) and self.site_licensee_email != request.user.email:
            raise serializers.ValidationError("user not authorised to approve endorsement")
        
        if (self.declined_by_endorser or self.approved_by_endorser):
            raise serializers.ValidationError("site licensee mooring request already approved/declined")
        self.approved_by_endorser = True
        self.declined_by_endorser = False
        self.save()
        logger.info(f'Endorsement approved for the Proposal: [{self.proposal}], Mooring: [{self.mooring}] by the endorser: [{request.user}].')
        self.proposal.check_endorsements(request)

    def endorse_declined(self, request):
        if not self.proposal or self.proposal.processing_status != Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT:
            if not (self.proposal.is_assessor(request.user) and (
                self.proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR or
                self.proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS
            )):
                raise serializers.ValidationError("proposal not awaiting endorsement")
        
        if not self.proposal.is_assessor(request.user) and self.site_licensee_email != request.user.email:
            raise serializers.ValidationError("user not authorised to approve endorsement")
        
        if (self.declined_by_endorser or self.approved_by_endorser):
            raise serializers.ValidationError("site licensee mooring request already approved/declined")
        self.declined_by_endorser = True
        self.approved_by_endorser = False
        self.save()
        logger.info(f'Endorsement declined for the Proposal: [{self.proposal}], Mooring: [{self.mooring}] by the endorser: [{request.user}].')
        send_aua_declined_by_endorser_email(self.proposal,request)
        self.proposal.check_endorsements(request)

class MooringLogDocument(Document):
    log_entry = models.ForeignKey('MooringLogEntry',related_name='documents', on_delete=models.CASCADE)
    _file = models.FileField(storage=private_storage,upload_to=update_mooring_comms_log_filename, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'


class MooringLogEntry(CommunicationsLogEntry):
    mooring = models.ForeignKey(Mooring, related_name='comms_logs', on_delete=models.CASCADE)

    def __str__(self):
        return '{} - {}'.format(self.reference, self.subject)

    class Meta:
        app_label = 'mooringlicensing'

class MooringUserAction(UserAction):
    ACTION_ASSIGN_MOORING_LICENCE = "Assign Mooring Site Licence {}"
    ACTION_SWITCH_MOORING_LICENCE = "Remove existing Mooring Site Licence {} and assign {}"

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ('-when',)

    @classmethod
    def log_action(cls, mooring, action, user):
        return cls.objects.create(
            mooring=mooring,
            who=user.id if isinstance(user, EmailUserRO) else user,
            what=str(action)
        )

    mooring = models.ForeignKey(Mooring, related_name='action_logs', on_delete=models.CASCADE)


class Vessel(RevisionedMixin):
    rego_no = models.CharField(max_length=200, unique=True, blank=False, null=False)
    blocking_owner = models.ForeignKey('VesselOwnership', blank=True, null=True, related_name='blocked_vessel', on_delete=models.SET_NULL)
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)

    class Meta:
        verbose_name_plural = "Vessels"
        app_label = 'mooringlicensing'

    def __str__(self):
        return self.rego_no

    def rego_no_uppercase(self):
        if self.rego_no:
            self.rego_no = self.rego_no.upper()

    def save(self, **kwargs):
        self.rego_no_uppercase()
        super(Vessel, self).save(**kwargs)

    def get_current_wlas(self, target_date):
        from mooringlicensing.components.approvals.models import Approval, WaitingListAllocation
        existing_wlas = WaitingListAllocation.objects.filter(
            status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,),
            start_date__lte=target_date,
            expiry_date__gte=target_date,
            current_proposal__vessel_details__vessel=self,
            current_proposal__vessel_ownership__end_date__isnull=True,
        ).distinct()
        return existing_wlas

    def get_current_aaps(self, target_date):
        from mooringlicensing.components.approvals.models import Approval, AnnualAdmissionPermit
        existing_aaps = AnnualAdmissionPermit.objects.filter(
            status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,),
            start_date__lte=target_date,
            expiry_date__gte=target_date,
            current_proposal__vessel_details__vessel=self,
            current_proposal__vessel_ownership__end_date__isnull=True,
        ).distinct()
        return existing_aaps

    def get_current_aups(self, target_date):
        from mooringlicensing.components.approvals.models import Approval, AuthorisedUserPermit
        existing_aups = AuthorisedUserPermit.objects.filter(
            status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,),
            start_date__lte=target_date,
            expiry_date__gte=target_date,
            current_proposal__vessel_details__vessel=self,
            current_proposal__vessel_ownership__end_date__isnull=True,
        ).distinct()
        return existing_aups

    def get_current_mls(self, target_date):
        from mooringlicensing.components.approvals.models import Approval, MooringLicence, VesselOwnershipOnApproval
        
        approval_ids = list(VesselOwnershipOnApproval.objects.filter(vessel_ownership__vessel=self,vessel_ownership__end_date__isnull=True,end_date__isnull=True).values_list("approval__id", flat=True))
        
        existing_mls = MooringLicence.objects.filter(
            status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,),
            start_date__lte=target_date,
            expiry_date__gte=target_date,
            proposal__processing_status__in=(Proposal.PROCESSING_STATUS_PRINTING_STICKER, Proposal.PROCESSING_STATUS_APPROVED,),
            id__in=approval_ids
        ).distinct()
        return existing_mls

    def get_current_approvals(self, target_date):
        # Return all the approvals where this vessel is on.
        existing_wla = self.get_current_wlas(target_date)
        existing_aaps = self.get_current_aaps(target_date)
        existing_aups = self.get_current_aups(target_date)
        existing_mls = self.get_current_mls(target_date)

        return {
            'wla': existing_wla,
            'aaps': existing_aaps,
            'aups': existing_aups,
            'mls': existing_mls
        }

    ## at submit
    def check_blocking_ownership(self, vessel_ownership, proposal_being_processed, request):
        logger.info(f'Checking blocking ownership for the proposal: [{proposal_being_processed}]...')
        from mooringlicensing.components.approvals.models import (
            Approval, MooringLicence, AuthorisedUserPermit, AnnualAdmissionPermit, WaitingListAllocation
        )

        #common blocks
        #another application of the same type that is not accepted, (printing sticker,) discarded, or declined
        #another approval of the same type that is current or suspended - unless this is an amendment or renewal of a previous application
        #another application of any kind where the vessel is owned by another user that is not accepted, (printing sticker,) discarded, or declined
        #another approval of any other kind (though effectively all kinds) where the vessel is owned by another user that is current or suspended

        #WL, AA, (and ML but that is taken care of above) blocks
        #a mooring license application that is not accepted, (printing sticker,) discarded, or declined 
        #a current or suspended mooring approval

        #AA blocks
        #an authorised User application that is not accepted, (printing sticker,) discarded, or declined (does not apply in reverse)
        #a current or suspended Authorised User Permit (does not apply in reverse)

        #application/proposal block
        today = datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()
        proposals_filter = Q()
        proposals_filter &= ((Q(vessel_ownership__vessel=self) & 
                            (Q(vessel_ownership__end_date__gt=today) | 
                            Q(vessel_ownership__end_date=None)) |
                            Q(rego_no=self.rego_no)))  # Blocking proposal is for the same vessel which has not been sold yet
        proposals_filter &= ~Q(processing_status__in=[  # Blocking proposal's status is not in the statuses listed
            Proposal.PROCESSING_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_PRINTING_STICKER, #printing sticker is treated the same as approved
            Proposal.PROCESSING_STATUS_DECLINED,
            Proposal.PROCESSING_STATUS_EXPIRED,
            Proposal.PROCESSING_STATUS_DISCARDED,
        ])
        proposals_filter &= ~Q(id=proposal_being_processed.id)  # Blocking proposal is not the proposal being processed

        blocking_proposals = []
        blocking_aua = []
        blocking_mla = []

        if not vessel_ownership.owner or not vessel_ownership.owner.emailuser:
            raise serializers.ValidationError("Invalid vessel ownership")

        blocking_ownerships = Proposal.objects.filter(proposals_filter).exclude(proposal_applicant__email_user_id=vessel_ownership.owner.emailuser).exclude(vessel_ownership__owner__emailuser=vessel_ownership.owner.emailuser)
        for bp in blocking_ownerships:
            logger.debug(f'blocking_ownership: [{bp}]')

        if blocking_ownerships:
            from mooringlicensing.helpers import is_internal
            logger.info(f'Blocking ownerships(s): [{blocking_ownerships}] found.  This vessel: [{self}] is already listed with RIA under another owner.')
            if request and is_internal(request):
                raise serializers.ValidationError(f"Blocking application(s): {str(list(blocking_ownerships.values_list("lodgement_number",flat=True)))} found. This vessel is already listed with RIA under another active application with another owner.")
            else:
                raise serializers.ValidationError("This vessel is already listed with RIA under another active application with another owner.")

        if proposal_being_processed.application_type_code == 'aua':
            blocking_proposals = AuthorisedUserApplication.objects.filter(proposals_filter)
        elif proposal_being_processed.application_type_code == 'aaa':
            blocking_proposals = AnnualAdmissionApplication.objects.filter(proposals_filter)
            blocking_aua = AuthorisedUserApplication.objects.filter(proposals_filter)
            blocking_mla = MooringLicenceApplication.objects.filter(proposals_filter)
        elif proposal_being_processed.application_type_code == 'wla':
            blocking_proposals = WaitingListApplication.objects.filter(proposals_filter)
            blocking_mla = MooringLicenceApplication.objects.filter(proposals_filter)
        elif proposal_being_processed.application_type_code == 'mla':
            blocking_proposals = MooringLicenceApplication.objects.filter(proposals_filter)
        else:
            raise serializers.ValidationError("Invalid application type")
        
        for bp in blocking_proposals:
            logger.debug(f'blocking_proposal: [{bp}]')
        for bp in blocking_aua:
            logger.debug(f'blocking_aua: [{bp}]')
        for bp in blocking_mla:
            logger.debug(f'blocking_mla: [{bp}]')      

        if blocking_proposals:
            logger.info(f'Blocking proposal(s): [{blocking_proposals}] found.')
            raise serializers.ValidationError("This vessel is already listed with RIA under another active " + proposal_being_processed.application_type.description)
        if blocking_aua:
            logger.info(f'Blocking Authorised User Application(s): [{blocking_aua}] found.')
            raise serializers.ValidationError("This vessel is already listed with RIA under another active Authorised User Application")
        if blocking_mla:
            logger.info(f'Blocking Mooring License Application: [{blocking_mla}] found.')
            raise serializers.ValidationError("This vessel is already listed with RIA under another active Mooring License Application")

        #license/permit/approval block
        approval_filter = Q()
        approval_filter &= Q(current_proposal__vessel_ownership__vessel=self) # Approval is for the same vessel
        approval_filter &= (Q(current_proposal__vessel_ownership__end_date__gt=today) | Q(current_proposal__vessel_ownership__end_date=None)) # The vessel has not been sold yet
        approval_filter &= ~Q(id=proposal_being_processed.approval.id) if proposal_being_processed.approval else Q() # We don't want to include the approval that this the proposal is for
        approval_filter &= ~Q(status__in=[
                    Approval.APPROVAL_STATUS_CANCELLED,
                    Approval.APPROVAL_STATUS_EXPIRED,
                    Approval.APPROVAL_STATUS_SURRENDERED,
                    Approval.APPROVAL_STATUS_FULFILLED])
        
        blocking_approvals = []
        blocking_aup = []
        blocking_ml = []

        blocking_approved_ownerships = Approval.objects.filter(approval_filter).exclude(current_proposal__vessel_ownership__owner__emailuser=vessel_ownership.owner.emailuser)
        if blocking_approved_ownerships:
            logger.info(f'Blocking ownerships(s): [{blocking_approved_ownerships}] found.  Another owner of this vessel: [{self}] holds a current Licence/Permit.')
            raise serializers.ValidationError("This vessel is already listed under a current Licence/Permit under another owner")

        if proposal_being_processed.application_type_code == 'aua':
            blocking_approvals = AuthorisedUserPermit.objects.filter(approval_filter)
        elif proposal_being_processed.application_type_code == 'aaa':
            blocking_approvals = AnnualAdmissionPermit.objects.filter(approval_filter)
            blocking_aup = AuthorisedUserPermit.objects.filter(approval_filter)
            blocking_ml = MooringLicence.objects.filter(approval_filter)
        elif proposal_being_processed.application_type_code == 'wla':
            blocking_approvals = WaitingListAllocation.objects.filter(approval_filter)
            blocking_ml = MooringLicence.objects.filter(approval_filter)
        elif proposal_being_processed.application_type_code == 'mla':
            blocking_approvals = MooringLicence.objects.filter(approval_filter)
        else:
            raise serializers.ValidationError("Invalid application type")

        if blocking_approvals:
            logger.info(f'Blocking approval(s): [{blocking_approvals}] found.  Another owner of this vessel: [{self}] holds a current Licence/Permit.')
            raise serializers.ValidationError("This vessel is already listed under a current " + proposal_being_processed.approval_class.description)
        if blocking_aup:
            logger.info(f'Blocking Authorised User Permit(s): [{blocking_aup}] found.  Another owner of this vessel: [{self}] holds a current Licence/Permit.')
            raise serializers.ValidationError("This vessel is listed under a current Authorised User Permit - cannot submit a new " + proposal_being_processed.application_type.description)
        if blocking_ml:
            logger.info(f'Blocking Mooring License: [{blocking_ml}] found.  Another owner of this vessel: [{self}] holds a current Licence/Permit.')
            raise serializers.ValidationError("This vessel is listed under a current Mooring License - cannot submit a new " + proposal_being_processed.application_type.description)
        
    @property
    def latest_vessel_details(self):
        return self.filtered_vesseldetails_set.first()

    @property
    def filtered_vesselownership_set(self):
        #exclude any vessel ownerships created before the latest end_date
        end_date_qs = self.vesselownership_set.exclude(end_date=None).order_by('end_date')
        if end_date_qs.exists():
            end_date = end_date_qs.last().end_date
            end_id = end_date_qs.last().id #because the end_date and created_date lack granularity, we have to use the id as well
            #NOTE: as of now id order corresponds with created_date - if that changes this check will also need to be updated
            return self.vesselownership_set.filter(
                id__in=VesselOwnership.filtered_objects.values_list('id', flat=True),
                created__gte=end_date,
                id__gt=end_id,
            )
        else:
            return self.vesselownership_set.filter(
                id__in=VesselOwnership.filtered_objects.values_list('id', flat=True),
            )

    @property
    def filtered_vesseldetails_set(self):
        return self.vesseldetails_set.filter(
                id__in=VesselDetails.filtered_objects.values_list('id', flat=True)
                )


class VesselLogDocument(Document):#
    log_entry = models.ForeignKey('VesselLogEntry',related_name='documents', on_delete=models.CASCADE)
    _file = models.FileField(storage=private_storage,upload_to=update_vessel_comms_log_filename, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'


class VesselLogEntry(CommunicationsLogEntry):
    vessel = models.ForeignKey(Vessel, related_name='comms_logs', on_delete=models.CASCADE)

    def __str__(self):
        return '{} - {}'.format(self.reference, self.subject)

    class Meta:
        app_label = 'mooringlicensing'

class VesselDetailsManager(models.Manager):
    def get_queryset(self):
        latest_ids = VesselDetails.objects.values("vessel").annotate(id=Max('id')).values_list('id', flat=True)
        return super(VesselDetailsManager, self).get_queryset().filter(id__in=latest_ids)


class VesselDetails(RevisionedMixin): # ManyToManyField link in Proposal
    vessel_type = models.CharField(max_length=20, choices=VESSEL_TYPES)
    vessel = models.ForeignKey(Vessel, on_delete=models.CASCADE)
    vessel_name = models.CharField(max_length=400, null=True, blank=True)
    vessel_length = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # does not exist in MB
    vessel_draft = models.DecimalField(max_digits=8, decimal_places=2)
    vessel_beam = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_weight = models.DecimalField(max_digits=8, decimal_places=2) # tonnage
    berth_mooring = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    filtered_objects = VesselDetailsManager()

    class Meta:
        verbose_name_plural = "Vessel Details"
        app_label = 'mooringlicensing'

    def __str__(self):
        return "{}".format(self.id)

    @property
    def vessel_applicable_length(self):
        return float(self.vessel_length)


class CompanyOwnership(RevisionedMixin):

    COMPANY_OWNERSHIP_STATUS_APPROVED = 'approved'
    COMPANY_OWNERSHIP_STATUS_DRAFT = 'draft'
    COMPANY_OWNERSHIP_STATUS_OLD = 'old'
    COMPANY_OWNERSHIP_STATUS_DECLINED = 'declined'
    STATUS_TYPES = (
        (COMPANY_OWNERSHIP_STATUS_APPROVED, 'Approved'),
        (COMPANY_OWNERSHIP_STATUS_DRAFT, 'Draft'),
        (COMPANY_OWNERSHIP_STATUS_OLD, 'Old'),
        (COMPANY_OWNERSHIP_STATUS_DECLINED, 'Declined'),
    )
    blocking_proposal = models.ForeignKey(Proposal, blank=True, null=True, on_delete=models.SET_NULL)

    vessel = models.ForeignKey(Vessel, on_delete=models.CASCADE)
    company = models.ForeignKey('Company', on_delete=models.CASCADE)
    percentage = models.IntegerField(null=True, blank=True)

    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True, blank=True)

    class Meta:
        verbose_name_plural = "Company Ownership"
        app_label = 'mooringlicensing'

    def __str__(self):
        return f"{self.company}: {self.percentage}%"

    def save(self, *args, **kwargs):
        super(CompanyOwnership, self).save(*args,**kwargs)


class VesselOwnershipCompanyOwnership(RevisionedMixin):
    COMPANY_OWNERSHIP_STATUS_APPROVED = 'approved'
    COMPANY_OWNERSHIP_STATUS_DRAFT = 'draft'
    COMPANY_OWNERSHIP_STATUS_OLD = 'old'
    COMPANY_OWNERSHIP_STATUS_DECLINED = 'declined'
    STATUS_TYPES = (
        (COMPANY_OWNERSHIP_STATUS_APPROVED, 'Approved'),
        (COMPANY_OWNERSHIP_STATUS_DRAFT, 'Draft'),
        (COMPANY_OWNERSHIP_STATUS_OLD, 'Old'),
        (COMPANY_OWNERSHIP_STATUS_DECLINED, 'Declined'),
    )
    vessel_ownership = models.ForeignKey('VesselOwnership', null=True, on_delete=models.SET_NULL)
    company_ownership = models.ForeignKey(CompanyOwnership, null=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=50, choices=STATUS_TYPES, default=COMPANY_OWNERSHIP_STATUS_DRAFT) # can be approved, old, draft, declined
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)

    class Meta:
        app_label = 'mooringlicensing'

    def __str__(self):
        return f'id:{self.id}, vessel_ownership: [{self.vessel_ownership}], company_ownership: [{self.company_ownership}], status: [{self.status}]'


class VesselOwnershipManager(models.Manager):
    def get_queryset(self):
        # Do not show sold vessels
        latest_ids = VesselOwnership.objects.filter(end_date__isnull=True).values("owner", "vessel", "company_ownerships").annotate(id=Max('id')).values_list('id', flat=True)
        return super(VesselOwnershipManager, self).get_queryset().filter(id__in=latest_ids)


class VesselOwnership(RevisionedMixin):
    owner = models.ForeignKey('Owner', on_delete=models.CASCADE)
    vessel = models.ForeignKey(Vessel, on_delete=models.CASCADE)
    percentage = models.IntegerField(null=True, blank=True)
    start_date = models.DateTimeField(default=timezone.now)
    # date of sale
    end_date = models.DateField(null=True, blank=True)
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    filtered_objects = VesselOwnershipManager()
    ## Name as shown on DoT registration papers
    dot_name = models.CharField(max_length=200, blank=True, null=True)
    company_ownerships = models.ManyToManyField(CompanyOwnership, blank=True, related_name='vessel_ownerships', through=VesselOwnershipCompanyOwnership)

    class Meta:
        verbose_name_plural = "Vessel Ownership"
        app_label = 'mooringlicensing'

    def get_latest_company_ownership(self, status_list=[VesselOwnershipCompanyOwnership.COMPANY_OWNERSHIP_STATUS_DRAFT, VesselOwnershipCompanyOwnership.COMPANY_OWNERSHIP_STATUS_APPROVED,]):
        if self.company_ownerships.count():
            company_ownership = self.company_ownerships.filter(vesselownershipcompanyownership__status__in=status_list).order_by('created').last()
            return company_ownership
        return CompanyOwnership.objects.none()
    
    @property
    def applicable_owner_name(self):
        co = self.get_latest_company_ownership([VesselOwnershipCompanyOwnership.COMPANY_OWNERSHIP_STATUS_APPROVED,])
        if co:
            return co.company.name
        else:
            return str(self.owner)

    @property
    def applicable_percentage(self):
        co = self.get_latest_company_ownership([VesselOwnershipCompanyOwnership.COMPANY_OWNERSHIP_STATUS_APPROVED,])
        if co:
            return co.percentage
        else:
            return self.percentage

    @property
    def individual_owner(self):
        if self.get_latest_company_ownership():
            return False
        else:
            return True

    def __str__(self):
        return f'id:{self.id}, owner: {self.owner}, company_ownership: [{self.get_latest_company_ownership([VesselOwnershipCompanyOwnership.COMPANY_OWNERSHIP_STATUS_APPROVED, VesselOwnershipCompanyOwnership.COMPANY_OWNERSHIP_STATUS_DRAFT,])}], vessel: {self.vessel}'


    def get_fee_items_paid(self):
        # Return all the fee_items for this vessel
        fee_items = []
        from mooringlicensing.components.approvals.models import Approval
        for proposal in self.proposal_set.filter(approval__isnull=False, approval__status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,)):
            for item in proposal.get_fee_items_paid():
                if item not in fee_items:
                    fee_items.append(item)
        return fee_items

    def save(self, *args, **kwargs):
        from mooringlicensing.components.approvals.models import AuthorisedUserPermit, MooringLicence
        existing_record = True if VesselOwnership.objects.filter(id=self.id) else False
        if existing_record:
            prev_end_date = VesselOwnership.objects.get(id=self.id).end_date
        super(VesselOwnership, self).save(*args,**kwargs)

class VesselRegistrationDocument(Document):
    @staticmethod
    def relative_path_to_file(proposal_id, filename):
        return f'proposal/{proposal_id}/vessel_registration_documents/{filename}'

    def upload_to(self, filename):
        proposal_id = self.proposal.id
        return self.relative_path_to_file(proposal_id, filename)

    vessel_ownership = models.ForeignKey(VesselOwnership, null=True, blank=True, related_name='vessel_registration_documents', on_delete=models.CASCADE)
    _file = models.FileField(
        null=True,
        max_length=512,
        storage=private_storage,
        upload_to=upload_to
    )
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    proposal = models.ForeignKey(Proposal, null=True, blank=True, related_name='temp_vessel_registration_documents', on_delete=models.CASCADE)
    original_file_name = models.CharField(max_length=512, null=True, blank=True)
    original_file_ext = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Vessel Registration Papers"

    def __str__(self):
        ret_str = f'{self.original_file_name}{self.original_file_ext}'
        if self._file:
            ret_str += f' ({self._file.url})'
        return ret_str

class Owner(RevisionedMixin):
    emailuser = models.IntegerField(unique=True)  # unique=True keeps the OneToOne relation
    # add on approval only
    vessels = models.ManyToManyField(Vessel, through=VesselOwnership) # these owner/vessel association
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)

    class Meta:
        verbose_name_plural = "Owners"
        app_label = 'mooringlicensing'

    @property
    def emailuser_obj(self):
        return retrieve_email_userro(self.emailuser)

    def __str__(self):
        if self.emailuser:
            from mooringlicensing.ledger_api_utils import retrieve_email_userro
            emailuser = retrieve_email_userro(self.emailuser)
            if emailuser:
                try:
                    return get_user_name(SystemUser.objects.get(ledger_id=emailuser))["full_name"]
                except:
                    return emailuser.get_full_name()
            else:
                return ''
        else:
            return ''


class Company(RevisionedMixin):
    name = models.CharField(max_length=200, unique=True, blank=True, null=True)
    vessels = models.ManyToManyField(Vessel, through=CompanyOwnership) # these owner/vessel association
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)

    class Meta:
        verbose_name_plural = "Companies"
        app_label = 'mooringlicensing'

    def __str__(self):
        return f'{self.name} (id: {self.id})'


class InsuranceCertificateDocument(Document):
    @staticmethod
    def relative_path_to_file(proposal_id, filename):
        return f'proposal/{proposal_id}/insurance_certificate_documents/{filename}'

    def upload_to(self, filename):
        proposal_id = self.proposal.id
        return self.relative_path_to_file(proposal_id, filename)

    proposal = models.ForeignKey(Proposal,related_name='insurance_certificate_documents', on_delete=models.CASCADE)
    _file = models.FileField(
        null=True,
        max_length=512,
        storage=private_storage,
        upload_to=upload_to
    )
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Insurance Certificate Documents"


class HullIdentificationNumberDocument(Document):
    @staticmethod
    def relative_path_to_file(proposal_id, filename):
        return f'proposal/{proposal_id}/hull_identification_number_documents/{filename}'

    def upload_to(self, filename):
        proposal_id = self.proposal.id
        return self.relative_path_to_file(proposal_id, filename)

    proposal = models.ForeignKey(Proposal,related_name='hull_identification_number_documents', on_delete=models.CASCADE)
    _file = models.FileField(
        null=True,
        max_length=512,
        storage=private_storage,
        upload_to=upload_to
    )
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Hull Identification Number Documents"


class ElectoralRollDocument(Document):
    @staticmethod
    def relative_path_to_file(proposal_id, filename):
        return f'proposal/{proposal_id}/electoral_roll_documents/{filename}'

    def upload_to(self, filename):
        proposal_id = self.proposal.id
        return self.relative_path_to_file(proposal_id, filename)

    proposal = models.ForeignKey(Proposal,related_name='electoral_roll_documents', on_delete=models.CASCADE)
    _file = models.FileField(
        null=True,
        max_length=512,
        storage=private_storage,
        upload_to=upload_to
    )
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Electoral Roll Document"


class MooringReportDocument(Document):
    @staticmethod
    def relative_path_to_file(proposal_id, filename):
        return f'proposal/{proposal_id}/mooring_report_documents/{filename}'

    def upload_to(self, filename):
        proposal = self.proposal_set.first()
        return self.relative_path_to_file(proposal.id, filename)

    _file = models.FileField(
        null=True,
        max_length=512,
        storage=private_storage,
        upload_to=upload_to
    )
    input_name = models.CharField(max_length=255, null=True, blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide = models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden = models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Mooring Report Document"


class WrittenProofDocument(Document):

    @staticmethod
    def relative_path_to_file(proposal_id, filename):
        return f'proposal/{proposal_id}/written_proof_documents/{filename}'

    def upload_to(self, filename):
        proposal = self.proposal_set.first()
        return self.relative_path_to_file(proposal.id, filename)

    _file = models.FileField(
        null=True,
        max_length=512,
        storage=private_storage,
        upload_to=upload_to
    )
    input_name = models.CharField(max_length=255, null=True, blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide = models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden = models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Written Proof Document"


class SignedLicenceAgreementDocument(Document):
    @staticmethod
    def relative_path_to_file(proposal_id, filename):
        return f'proposal/{proposal_id}/signed_licence_agreement_documents/{filename}'

    def upload_to(self, filename):
        proposal = self.proposal_set.first()
        return self.relative_path_to_file(proposal.id, filename)

    _file = models.FileField(
        null=True,
        max_length=512,
        storage=private_storage,
        upload_to=upload_to
    )
    input_name = models.CharField(max_length=255, null=True, blank=True)
    can_delete = models.BooleanField(default=True)
    can_hide = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Signed Licence Agreement"


class ProofOfIdentityDocument(Document):
    @staticmethod
    def relative_path_to_file(proposal_id, filename):
        return f'proposal/{proposal_id}/proof_of_identity_documents/{filename}'

    def upload_to(self, filename):
        proposal = self.proposal_set.first()
        return self.relative_path_to_file(proposal.id, filename)

    _file = models.FileField(
        null=True,
        max_length=512,
        storage=private_storage,
        upload_to=upload_to
    )
    input_name = models.CharField(max_length=255, null=True, blank=True)
    can_delete = models.BooleanField(default=True)
    can_hide = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Proof Of Identity"


class ProposalRequest(SanitiseMixin):
    proposal = models.ForeignKey(Proposal, related_name='proposalrequest_set', on_delete=models.CASCADE)
    subject = models.CharField(max_length=200, blank=True)
    text = models.TextField(blank=True)
    officer = models.IntegerField(null=True, blank=True)

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


class AmendmentReason(SanitiseMixin):
    reason = models.CharField('Reason', max_length=125)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Amendment Reason" # display name in Admin
        verbose_name_plural = "Application Amendment Reasons"

    def __str__(self):
        return self.reason


class AmendmentRequest(ProposalRequest):
    STATUS_CHOICES = (('requested', 'Requested'), ('amended', 'Amended'))

    status = models.CharField('Status', max_length=30, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0])
    reason = models.ForeignKey(AmendmentReason, blank=True, null=True, on_delete=models.SET_NULL)

    class Meta:
        app_label = 'mooringlicensing'

    def generate_amendment(self,request):
        with transaction.atomic():
            try:
                if not self.proposal.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.status == 'requested':
                    proposal = self.proposal
                    if proposal.processing_status != Proposal.PROCESSING_STATUS_DRAFT:
                        proposal.processing_status = Proposal.PROCESSING_STATUS_DRAFT
                        proposal.save()
                        logger.info(f'Status: [{Proposal.PROCESSING_STATUS_DRAFT}] has been set to the proposal: [{proposal}]')
                    # Create a log entry for the proposal
                    proposal.log_user_action(ProposalUserAction.ACTION_ID_REQUEST_AMENDMENTS, request)

                    # send email
                    send_amendment_email_notification(self, request, proposal)

                self.save()
            except:
                raise


class ProposalDeclinedDetails(SanitiseMixin):
    proposal = models.OneToOneField(Proposal, null=True, on_delete=models.SET_NULL)
    officer = models.IntegerField(null=True, blank=True)
    reason = models.TextField(blank=True)
    cc_email = models.TextField(null=True)

    class Meta:
        app_label = 'mooringlicensing'


class ProposalStandardRequirement(RevisionedMixin):
    text = models.TextField()
    code = models.CharField(max_length=10, unique=True)
    obsolete = models.BooleanField(default=False)
    application_type = models.ForeignKey(ApplicationType, null=True, blank=True, on_delete=models.CASCADE)
    default = models.BooleanField(default=False)

    def __str__(self):
        return self.code

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Standard Requirement"
        verbose_name_plural = "Application Standard Requirements"


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
    ACTION_ISSUE_APPROVAL_ = "Issue Approval for application {}"
    ACTION_AWAITING_PAYMENT_APPROVAL_ = "Awaiting Payment for application {}"
    ACTION_PRINTING_STICKER = "Printing Sticker for application {}"
    ACTION_STICKER_TO_BE_RETURNED = "Sticker to be returned for application {}"
    ACTION_APPROVE_APPLICATION = "Approve application {}"
    ACTION_UPDATE_APPROVAL_ = "Update Approval for application {}"
    ACTION_APPROVED = "Grant application {}"
    ACTION_AUTO_APPROVED = "Grant application {}"
    ACTION_EXPIRED_PROPOSAL = "Proposal expired {} due to no payment"
    ACTION_EXPIRED_APPROVAL_ = "Expire Approval for proposal {}"
    ACTION_DISCARD_PROPOSAL = "Discard application {}"
    ACTION_WITHDRAW_PROPOSAL = "Withdraw application {}"
    ACTION_SUBMIT_OTHER_DOCUMENTS = 'Submit other documents'
    # Assessors
    ACTION_SAVE_ASSESSMENT_ = "Save assessment {}"
    ACTION_CONCLUDE_ASSESSMENT_ = "Conclude assessment {}"
    ACTION_PROPOSED_APPROVAL = "Application {} has been proposed for approval"
    ACTION_PROPOSED_DECLINE = "Application {} has been proposed for decline"

    ACTION_ENTER_REQUIREMENTS = "Enter Requirements for proposal {}"
    ACTION_BACK_TO_PROCESSING = "Back to processing for proposal {}"

    #Approval
    ACTION_REISSUE_APPROVAL = "Reissue approval for application {}"
    ACTION_CANCEL_APPROVAL = "Cancel approval for application {}"
    ACTION_EXTEND_APPROVAL = "Extend approval"
    ACTION_SUSPEND_APPROVAL = "Suspend approval for application {}"
    ACTION_REINSTATE_APPROVAL = "Reinstate approval for application {}"
    ACTION_SURRENDER_APPROVAL = "Surrender approval for application {}"
    ACTION_RENEW_PROPOSAL = "Create Renewal application for application {}"
    ACTION_AMEND_PROPOSAL = "Create Amendment application for application {}"
    ACTION_SWAP_MOORINGS_PROPOSAL = "Create Swap moorings application for application {}"
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
            who=user.id if isinstance(user, EmailUserRO) else user,
            what=str(action)
        )

    who = models.IntegerField(null=True, blank=True)
    when = models.DateTimeField(null=False, blank=False, auto_now_add=True)
    what = models.TextField(blank=False)
    proposal = models.ForeignKey(Proposal, related_name='action_logs', on_delete=models.CASCADE)


class ProposalRequirement(OrderedModel):
    RECURRENCE_PATTERNS = [(1, 'Weekly'), (2, 'Monthly'), (3, 'Yearly')]
    standard_requirement = models.ForeignKey(ProposalStandardRequirement,null=True,blank=True,on_delete=models.SET_NULL)
    free_requirement = models.TextField(null=True,blank=True)
    standard = models.BooleanField(default=True)
    proposal = models.ForeignKey(Proposal,related_name='requirements',on_delete=models.CASCADE)
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

@receiver(pre_delete, sender=Proposal)
def delete_documents(sender, instance, *args, **kwargs):
    for document in instance.documents.all():
        document.delete()

import reversion
reversion.register(ProposalDocument)
reversion.register(Proposal, follow=['proposal_applicant'])
reversion.register(ProposalApplicant)
reversion.register(StickerPrintingContact, follow=[])
reversion.register(StickerPrintingBatch, follow=['sticker_set'])
reversion.register(StickerPrintingResponseEmail, follow=['stickerprintingresponse_set'])
reversion.register(StickerPrintingResponse, follow=['sticker_set'])
reversion.register(WaitingListApplication, follow=['documents', 'succeeding_proposals', 'comms_logs', 'companyownership_set', 'insurance_certificate_documents', 'hull_identification_number_documents', 'electoral_roll_documents', 'mooring_report_documents', 'written_proof_documents', 'signed_licence_agreement_documents', 'proof_of_identity_documents', 'proposalrequest_set', 'proposaldeclineddetails', 'action_logs', 'requirements', 'approval_history_records', 'approvals', 'sticker_set', 'compliances'])
reversion.register(AnnualAdmissionApplication, follow=['documents', 'succeeding_proposals', 'comms_logs', 'companyownership_set', 'insurance_certificate_documents', 'hull_identification_number_documents', 'electoral_roll_documents', 'mooring_report_documents', 'written_proof_documents', 'signed_licence_agreement_documents', 'proof_of_identity_documents', 'proposalrequest_set', 'proposaldeclineddetails', 'action_logs', 'requirements', 'approval_history_records', 'approvals', 'sticker_set', 'compliances'])
reversion.register(AuthorisedUserApplication, follow=['documents', 'succeeding_proposals', 'comms_logs', 'companyownership_set', 'insurance_certificate_documents', 'hull_identification_number_documents', 'electoral_roll_documents', 'mooring_report_documents', 'written_proof_documents', 'signed_licence_agreement_documents', 'proof_of_identity_documents', 'proposalrequest_set', 'proposaldeclineddetails', 'action_logs', 'requirements', 'approval_history_records', 'approvals', 'sticker_set', 'compliances'])
reversion.register(MooringLicenceApplication, follow=['documents', 'succeeding_proposals', 'comms_logs', 'companyownership_set', 'insurance_certificate_documents', 'hull_identification_number_documents', 'electoral_roll_documents', 'mooring_report_documents', 'written_proof_documents', 'signed_licence_agreement_documents', 'proof_of_identity_documents', 'proposalrequest_set', 'proposaldeclineddetails', 'action_logs', 'requirements', 'approval_history_records', 'approvals', 'sticker_set', 'compliances'])
reversion.register(ProposalLogDocument, follow=[])
reversion.register(ProposalLogEntry, follow=['documents'])
reversion.register(MooringBay, follow=['proposal_set', 'mooring_set'])
reversion.register(Mooring, follow=['ria_generated_proposal', 'comms_logs', 'action_logs', 'approval_set'])
reversion.register(MooringLogDocument, follow=[])
reversion.register(MooringLogEntry, follow=['documents'])
reversion.register(MooringUserAction, follow=[])
reversion.register(Vessel, follow=['comms_logs', 'vesseldetails_set', 'companyownership_set', 'vesselownership_set', 'owner_set', 'company_set'])
reversion.register(VesselLogDocument, follow=[])
reversion.register(VesselLogEntry, follow=['documents'])
reversion.register(VesselDetails, follow=['proposal_set'])
reversion.register(CompanyOwnership, follow=['blocking_proposal', 'vessel', 'company'])
reversion.register(VesselOwnership, follow=['owner', 'vessel', 'company_ownerships'])
reversion.register(VesselRegistrationDocument, follow=[])
reversion.register(Owner, follow=['vesselownership_set'])
reversion.register(Company, follow=['companyownership_set'])
reversion.register(InsuranceCertificateDocument, follow=[])
reversion.register(HullIdentificationNumberDocument, follow=[])
reversion.register(ElectoralRollDocument, follow=[])
reversion.register(MooringReportDocument, follow=[])
reversion.register(WrittenProofDocument, follow=[])
reversion.register(SignedLicenceAgreementDocument, follow=[])
reversion.register(ProofOfIdentityDocument, follow=[])
reversion.register(ProposalRequest, follow=[])
reversion.register(ComplianceRequest, follow=[])
reversion.register(AmendmentReason, follow=['amendmentrequest_set'])
reversion.register(AmendmentRequest, follow=[])
reversion.register(ProposalDeclinedDetails, follow=[])
reversion.register(ProposalStandardRequirement, follow=['proposalrequirement_set'])
reversion.register(ProposalUserAction, follow=[])
reversion.register(ProposalRequirement, follow=['proposalrequirement_set', 'compliance_requirement'])