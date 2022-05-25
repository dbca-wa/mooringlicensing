from __future__ import unicode_literals
from django.core.files.base import ContentFile

import datetime
import logging
import re

import pytz
from django.db import models,transaction
from django.dispatch import receiver
from django.db.models.signals import pre_delete
from django.db.models import Count
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.contrib.postgres.fields.jsonb import JSONField
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from ledger.settings_base import TIME_ZONE
from ledger.accounts.models import EmailUser, RevisionedMixin
from ledger.payments.invoice.models import Invoice
from mooringlicensing.components.approvals.pdf import create_dcv_permit_document, create_dcv_admission_document, \
    create_approval_doc, create_renewal_doc
from mooringlicensing.components.emails.utils import get_public_url
from mooringlicensing.components.organisations.models import Organisation
from mooringlicensing.components.payments_ml.models import StickerActionFee
from mooringlicensing.components.proposals.models import Proposal, ProposalUserAction, MooringBay, Mooring, \
    StickerPrintingBatch, StickerPrintingResponse, Vessel, VesselOwnership, ProposalType
from mooringlicensing.components.main.models import CommunicationsLogEntry, UserAction, Document, \
    GlobalSettings  # , ApplicationType
from mooringlicensing.components.approvals.email import (
    send_approval_expire_email_notification,
    send_approval_cancel_email_notification,
    send_approval_suspend_email_notification,
    send_approval_reinstate_email_notification,
    send_approval_surrender_email_notification,
    send_auth_user_no_moorings_notification,
    send_auth_user_mooring_removed_notification,
)
from mooringlicensing.helpers import is_customer
from mooringlicensing.settings import PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_NEW

logger = logging.getLogger('mooringlicensing')


def update_waiting_list_offer_doc_filename(instance, filename):
    return '{}/proposals/{}/approvals/{}/waiting_list_offer/{}'.format(settings.MEDIA_APP_DIR, instance.approval.current_proposal.id, instance.id, filename)

def update_approval_doc_filename(instance, filename):
    return '{}/proposals/{}/approvals/{}'.format(settings.MEDIA_APP_DIR, instance.approval.current_proposal.id,filename)

def update_approval_comms_log_filename(instance, filename):
    return '{}/proposals/{}/approvals/communications/{}'.format(settings.MEDIA_APP_DIR, instance.log_entry.approval.current_proposal.id,filename)


class WaitingListOfferDocument(Document):
    approval = models.ForeignKey('Approval',related_name='waiting_list_offer_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Waiting List Offer Documents"


class RenewalDocument(Document):
    approval = models.ForeignKey('Approval',related_name='renewal_documents')
    _file = models.FileField(upload_to=update_approval_doc_filename)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted

    def delete(self):
        if self.can_delete:
            return super(RenewalDocument, self).delete()
        logger.info('Cannot delete existing document object after Proposal has been submitted (including document submitted before Proposal pushback to status Draft): {}'.format(self.name))

    class Meta:
        app_label = 'mooringlicensing'


class AuthorisedUserSummaryDocument(Document):
    approval = models.ForeignKey('Approval', related_name='authorised_user_summary_documents')
    _file = models.FileField(upload_to=update_approval_doc_filename, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'


class ApprovalDocument(Document):
    approval = models.ForeignKey('Approval',related_name='documents')
    _file = models.FileField(upload_to=update_approval_doc_filename, max_length=512)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted

    def delete(self):
        if self.can_delete:
            return super(ApprovalDocument, self).delete()
        logger.info('Cannot delete existing document object after Application has been submitted (including document submitted before Application pushback to status Draft): {}'.format(self.name))

    class Meta:
        app_label = 'mooringlicensing'


class MooringOnApproval(RevisionedMixin):
    approval = models.ForeignKey('Approval')
    mooring = models.ForeignKey(Mooring)
    sticker = models.ForeignKey('Sticker', blank=True, null=True)
    site_licensee = models.BooleanField()
    end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        approval = self.approval.lodgement_number if self.approval else ' '
        mooring = self.mooring.name if self.mooring else ' '
        sticker = self.sticker.number if self.sticker else ' '
        return 'ID:{} ({}-{}-{})'.format(self.id, approval, mooring, sticker)

    def save(self, *args, **kwargs):
        existing_ria_moorings = MooringOnApproval.objects.filter(approval=self.approval, mooring=self.mooring, site_licensee=False).count()
        if existing_ria_moorings >= 2 and not self.site_licensee:
            raise ValidationError('Maximum of two RIA selected moorings allowed per Authorised User Permit')

        kwargs.pop('version_user', None)
        kwargs.pop('version_comment', None)
        kwargs['no_revision'] = True
        super(MooringOnApproval, self).save(*args,**kwargs)

    class Meta:
        app_label = 'mooringlicensing'
        unique_together = ("mooring", "approval")


class VesselOwnershipOnApproval(RevisionedMixin):
    approval = models.ForeignKey('Approval')
    vessel_ownership = models.ForeignKey(VesselOwnership)
    end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return 'ID:{} ({}-{})'.format(self.id, self.approval, self.vessel_ownership)

    class Meta:
        app_label = 'mooringlicensing'
        unique_together = ("vessel_ownership", "approval")


class ApprovalHistory(RevisionedMixin):
    #REASON_NEW = 'new'
    #REASON_REPLACEMENT_STICKER = 'replacement_sticker'
    #REASON_VESSEL_ADD = 'vessel_add'
    #REASON_VESSEL_SOLD = 'vessel_sold'
    #REASON_MOORING_ADD = 'mooring_add'
    #REASON_MOORING_SWAP = 'mooring_swap'

    #REASON_CHOICES = (
    #    (REASON_NEW, 'New'),
    #    (REASON_REPLACEMENT_STICKER, 'Replacement sticker'),
    #    (REASON_VESSEL_ADD, 'Vessel added'),
    #    (REASON_VESSEL_SOLD, 'Vessel sold'),
    #    (REASON_MOORING_ADD, 'New mooring'),
    #    (REASON_MOORING_SWAP, 'Mooring swap'),
    #)

    #reason = models.CharField(max_length=40, choices=REASON_CHOICES, blank=True, null=True)
    reason = models.CharField(max_length=100, blank=True, null=True)
                                       #default=REASON_CHOICES[0][0])
    approval = models.ForeignKey('Approval')
    # can be null due to requirement to allow null vessels on renewal/amendment applications
    vessel_ownership = models.ForeignKey(VesselOwnership, blank=True, null=True)
    proposal = models.ForeignKey(Proposal,related_name='approval_history_records')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)
    stickers = models.ManyToManyField('Sticker')
    approval_letter = models.ForeignKey(ApprovalDocument, blank=True, null=True)
    # derive from proposal

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ['-id',]

    def __str__(self):
        return '{}, {}'.format(self.id, self.reason)


class Approval(RevisionedMixin):
    APPROVAL_STATUS_CURRENT = 'current'
    APPROVAL_STATUS_EXPIRED = 'expired'
    APPROVAL_STATUS_CANCELLED = 'cancelled'
    APPROVAL_STATUS_SURRENDERED = 'surrendered'
    APPROVAL_STATUS_SUSPENDED = 'suspended'
    APPROVAL_STATUS_FULFILLED = 'fulfilled'

    STATUS_CHOICES = (
        (APPROVAL_STATUS_CURRENT, 'Current'),
        (APPROVAL_STATUS_EXPIRED, 'Expired'),
        (APPROVAL_STATUS_CANCELLED, 'Cancelled'),
        (APPROVAL_STATUS_SURRENDERED, 'Surrendered'),
        (APPROVAL_STATUS_SUSPENDED, 'Suspended'),
        (APPROVAL_STATUS_FULFILLED, 'Fulfilled'),
    )
    # waiting list allocation approvals
    INTERNAL_STATUS_WAITING = 'waiting' #b #y
    INTERNAL_STATUS_OFFERED = 'offered' #b - no change to queue #y
    INTERNAL_STATUS_SUBMITTED = 'submitted' #c - no change to queue #y
    INTERNAL_STATUS_CHOICES = (
        (INTERNAL_STATUS_WAITING, 'Waiting for offer'),
        (INTERNAL_STATUS_OFFERED, 'Mooring Licence offered'),
        (INTERNAL_STATUS_SUBMITTED, 'Mooring Licence application submitted'),
        )
    lodgement_number = models.CharField(max_length=9, blank=True, unique=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES,
                                       default=STATUS_CHOICES[0][0])
    internal_status = models.CharField(max_length=40, choices=INTERNAL_STATUS_CHOICES, blank=True, null=True)
    licence_document = models.ForeignKey(ApprovalDocument, blank=True, null=True, related_name='licence_document')
    authorised_user_summary_document = models.ForeignKey(AuthorisedUserSummaryDocument, blank=True, null=True, related_name='approvals')
    cover_letter_document = models.ForeignKey(ApprovalDocument, blank=True, null=True, related_name='cover_letter_document')
    replaced_by = models.OneToOneField('self', blank=True, null=True, related_name='replace')
    current_proposal = models.ForeignKey(Proposal,related_name='approvals', null=True)
    renewal_document = models.ForeignKey(RenewalDocument, blank=True, null=True, related_name='renewal_document')
    renewal_sent = models.BooleanField(default=False)
    issue_date = models.DateTimeField()
    wla_queue_date = models.DateTimeField(blank=True, null=True)
    original_issue_date = models.DateField(auto_now_add=True)
    start_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    surrender_details = JSONField(blank=True,null=True)
    suspension_details = JSONField(blank=True,null=True)
    submitter = models.ForeignKey(EmailUser, on_delete=models.PROTECT, blank=True, null=True, related_name='mooringlicensing_approvals')
    org_applicant = models.ForeignKey(Organisation,on_delete=models.PROTECT, blank=True, null=True, related_name='org_approvals')
    proxy_applicant = models.ForeignKey(EmailUser,on_delete=models.PROTECT, blank=True, null=True, related_name='proxy_approvals')
    extracted_fields = JSONField(blank=True, null=True)
    cancellation_details = models.TextField(blank=True)
    extend_details = models.TextField(blank=True)
    cancellation_date = models.DateField(blank=True, null=True)
    set_to_cancel = models.BooleanField(default=False)
    set_to_suspend = models.BooleanField(default=False)
    set_to_surrender = models.BooleanField(default=False)

    renewal_count = models.PositiveSmallIntegerField('Number of times an Approval has been renewed', default=0)
    migrated=models.BooleanField(default=False)
    expiry_notice_sent = models.BooleanField(default=False)
    # for cron job
    exported = models.BooleanField(default=False) # must be False after every add/edit
    moorings = models.ManyToManyField(Mooring, through=MooringOnApproval)
    vessel_ownerships = models.ManyToManyField(VesselOwnership, through=VesselOwnershipOnApproval)
    wla_order = models.PositiveIntegerField(help_text='wla order per mooring bay', null=True)
    vessel_nomination_reminder_sent = models.BooleanField(default=False)
    reissued= models.BooleanField(default=False)
    # mark as True when Approval is re/issued
    export_to_mooring_booking = models.BooleanField(default=False)

    class Meta:
        app_label = 'mooringlicensing'
        unique_together = ('lodgement_number', 'issue_date')
        ordering = ['-id',]

    def get_max_fee_item(self, fee_season, vessel_details=None):
        max_fee_item = None
        for proposal in self.proposal_set.all():
            fee_items = proposal.get_fee_items_paid(fee_season, vessel_details)

            for fee_item in fee_items:
                if not max_fee_item:
                    max_fee_item = fee_item
                else:
                    if max_fee_item.get_absolute_amount() < fee_item.get_absolute_amount():
                        max_fee_item = fee_item
        return max_fee_item

    def get_licence_document_as_attachment(self):
        attachment = None
        if self.licence_document:
            licence_document = self.licence_document._file
            if licence_document is not None:
                file_name = self.licence_document.name
                attachment = (file_name, licence_document.file.read(), 'application/pdf')
        return attachment

    @property
    def postal_address_line1(self):
        ret_value = ''
        if self.submitter:
            if self.submitter.postal_same_as_residential:
                ret_value = self.submitter.residential_address.line1
            else:
                if self.submitter.postal_address:
                    ret_value = self.submitter.postal_address.line1
            if not ret_value:
                # Shouldn't reach here, but if so, just return residential address
                ret_value = self.submitter.residential_address.line1
        return ret_value

    @property
    def postal_address_line2(self):
        ret_value = ''
        if self.submitter:
            if self.submitter.postal_same_as_residential:
                ret_value = self.submitter.residential_address.line2
            else:
                if self.submitter.postal_address:
                    ret_value = self.submitter.postal_address.line2
            if not ret_value:
                # Shouldn't reach here, but if so, just return residential address
                ret_value = self.submitter.residential_address.line2
        return ret_value

    @property
    def postal_address_state(self):
        ret_value = ''
        if self.submitter:
            if self.submitter.postal_same_as_residential:
                ret_value = self.submitter.residential_address.state
            else:
                if self.submitter.postal_address:
                    ret_value = self.submitter.postal_address.state
            if not ret_value:
                # Shouldn't reach here, but if so, just return residential address
                ret_value = self.submitter.residential_address.state
        return ret_value

    @property
    def postal_address_suburb(self):
        ret_value = ''
        if self.submitter:
            if self.submitter.postal_same_as_residential:
                ret_value = self.submitter.residential_address.locality
            else:
                if self.submitter.postal_address:
                    ret_value = self.submitter.postal_address.locality
            if not ret_value:
                # Shouldn't reach here, but if so, just return residential address
                ret_value = self.submitter.residential_address.locality
        return ret_value

    @property
    def postal_address_postcode(self):
        ret_value = ''
        if self.submitter:
            if self.submitter.postal_same_as_residential:
                ret_value = self.submitter.residential_address.postcode
            else:
                if self.submitter.postal_address:
                    ret_value = self.submitter.postal_address.postcode
            if not ret_value:
                # Shouldn't reach here, but if so, just return residential address
                ret_value = self.submitter.residential_address.postcode
        return ret_value

    @property
    def description(self):
        if hasattr(self, 'child_obj'):
            return self.child_obj.description
        return ''

    def write_approval_history(self, reason=None):
        history_count = self.approvalhistory_set.count()
        if not history_count:
            new_approval_history_entry = ApprovalHistory.objects.create(
                vessel_ownership=self.current_proposal.vessel_ownership,
                approval=self,
                proposal=self.current_proposal,
                start_date=self.issue_date,
                approval_letter=self.licence_document,
                reason='New application {}'.format(str(self.current_proposal)),
            )
        elif reason:
            new_approval_history_entry = ApprovalHistory.objects.create(
                vessel_ownership=self.current_proposal.vessel_ownership,
                approval=self,
                proposal=self.current_proposal,
                start_date=self.issue_date,
                approval_letter=self.licence_document,
                reason=reason,
            )
        else:
            new_approval_history_entry = ApprovalHistory.objects.create(
                vessel_ownership=self.current_proposal.vessel_ownership,
                approval=self,
                proposal=self.current_proposal,
                start_date=self.issue_date,
                approval_letter=self.licence_document,
            )

        # Move this logic to the 'export_and_email_sticker_data' cron job
        # stickers = self.stickers.filter(status__in=['ready', 'current', 'awaiting_printing'])
        # for sticker in stickers:
        #     new_approval_history_entry.stickers.add(sticker)

        approval_history = self.approvalhistory_set.all()
        ## rewrite history
        # current_proposal.previous_application must be set on renewal/amendment
        if self.current_proposal.previous_application:
            previous_application = self.current_proposal.previous_application
            qs = self.approvalhistory_set.filter(proposal=previous_application)
            if qs:
                # previous history entry exists
                end_date = self.issue_date
                previous_history_entry = self.approvalhistory_set.filter(proposal=previous_application)[0]
                # check vo sale date
                if previous_history_entry.vessel_ownership and previous_history_entry.vessel_ownership.end_date:
                    end_date = previous_history_entry.vessel_ownership.end_date
                # update previous_history_entry
                previous_history_entry.end_date = end_date
                previous_history_entry.save()

                if self.current_proposal.proposal_type.code == PROPOSAL_TYPE_AMENDMENT and self.current_proposal.vessel_ownership == self.current_proposal.previous_application.vessel_ownership:
                    # When renewal and vessel not changed
                    # Copy stickers from previous history to new history
                    for sticker in previous_history_entry.stickers.all():
                        new_approval_history_entry.stickers.add(sticker)

        # TODO: need to worry about all entries for this approval?
        ## reason
        return new_approval_history_entry

    def add_vessel_ownership(self, vessel_ownership):
        # do not add if this vessel_ownership already exists for the approval 
        vessel_ownership_on_approval = None
        created = None
        if not self.vesselownershiponapproval_set.filter(vessel_ownership=vessel_ownership):
            vessel_ownership_on_approval, created = VesselOwnershipOnApproval.objects.update_or_create(
                    vessel_ownership=vessel_ownership,
                    approval=self,
                    )
        return vessel_ownership_on_approval, created

    def add_mooring(self, mooring, site_licensee):
        # do not add if this mooring already exists for the approval
        mooring_on_approval = None
        created = None
        if not self.mooringonapproval_set.filter(mooring=mooring):
            mooring_on_approval, created = MooringOnApproval.objects.update_or_create(
                    mooring=mooring,
                    approval=self,
                    site_licensee=site_licensee
                    )
            if created:
                logger.info('Mooring {} has been added to the approval {}'.format(mooring.name, self.lodgement_number))
        return mooring_on_approval, created

    #def set_wla_order(self):
    #    place = 1
    #    # set wla order per bay for current allocations
    #    if type(self) == WaitingListAllocation:
    #        for w in WaitingListAllocation.objects.filter(
    #                wla_queue_date__isnull=False,
    #                current_proposal__preferred_bay=self.current_proposal.preferred_bay,
    #                status__in=['current', 'suspended']).order_by(
    #                #status='current').order_by(
    #                        'wla_queue_date'):
    #            w.wla_order = place
    #            w.save()
    #            place += 1
    #    self.refresh_from_db()
    #    return self

    @property
    def bpay_allowed(self):
        if self.org_applicant:
            return self.org_applicant.bpay_allowed
        return False

    @property
    def monthly_invoicing_allowed(self):
        if self.org_applicant:
            return self.org_applicant.monthly_invoicing_allowed
        return False

    @property
    def monthly_invoicing_period(self):
        if self.org_applicant:
            return self.org_applicant.monthly_invoicing_period
        return None

    @property
    def monthly_payment_due_period(self):
        if self.org_applicant:
            return self.org_applicant.monthly_payment_due_period
        return None

    @property
    def applicant(self):
        if self.org_applicant:
            return self.org_applicant.organisation.name
        elif self.proxy_applicant:
            return "{} {}".format(
                self.proxy_applicant.first_name,
                self.proxy_applicant.last_name)
        else:
            try:
                return "{} {}".format(
                    self.submitter.first_name,
                    self.submitter.last_name)
            except:
                return "Applicant Not Set"

    @property
    def linked_applications(self):
        ids = Proposal.objects.filter(approval__lodgement_number=self.lodgement_number).values_list('id', flat=True)
        all_linked_ids = Proposal.objects.filter(Q(previous_application__in=ids) | Q(id__in=ids)).values_list('lodgement_number', flat=True)
        return all_linked_ids

    @property
    def applicant_type(self):
        if self.org_applicant:
            return "org_applicant"
        elif self.proxy_applicant:
            return "proxy_applicant"
        else:
            return "submitter"

    @property
    def is_org_applicant(self):
        return True if self.org_applicant else False

    @property
    def applicant_id(self):
        if self.org_applicant:
            return self.org_applicant.id
        elif self.proxy_applicant:
            return self.proxy_applicant.id
        else:
            return self.submitter.id

    @property
    def title(self):
        return self.current_proposal.title

    @property
    def next_id(self):
        ids = map(int, [re.sub('^[A-Za-z]*', '', i) for i in Approval.objects.all().values_list('lodgement_number', flat=True) if i])
        ids = list(ids)
        return max(ids) + 1 if ids else 1

    def save(self, *args, **kwargs):
        kwargs.pop('version_user', None)
        kwargs.pop('version_comment', None)
        kwargs['no_revision'] = True
        super(Approval, self).save(*args, **kwargs)
        self.child_obj.refresh_from_db()
        if type(self.child_obj) == MooringLicence and self.status in ['expired', 'cancelled', 'surrendered']:
            self.child_obj.update_auth_user_permits()

    def __str__(self):
        return self.lodgement_number

    @property
    def reference(self):
        return 'L{}'.format(self.id)

    @property
    def can_external_action(self):
        return self.status == 'current' or self.status == 'suspended'

    @property
    def can_reissue(self):
        return self.status == 'current' or self.status == 'suspended'

    @property
    def can_reinstate(self):
        return (self.status == 'cancelled' or self.status == 'suspended' or self.status == 'surrendered') and self.can_action

    @property
    def allowed_assessors(self):
        return self.current_proposal.allowed_assessors

    def allowed_assessors_user(self, request):
        return self.current_proposal.allowed_assessors_user(request)

    def is_assessor(self,user):
        return self.current_proposal.is_assessor(user)

    def is_approver(self,user):
        return self.current_proposal.is_approver(user)

    @property
    def is_issued(self):
        return self.licence_number is not None and len(self.licence_number) > 0

    @property
    def can_action(self):
        if not (self.set_to_cancel or self.set_to_suspend or self.set_to_surrender):
                return True
        else:
            return False

    @property
    def code(self):
        return self.child_obj.code

    @property
    def amend_or_renew(self):
        try:
            if not self.status in ['current', 'suspended', 'fulfilled']:
                return None
            amend_renew = 'amend'
            ## test whether any renewal or amendment applications have been created
            customer_status_choices = []
            ria_generated_proposal_qs = None
            if type(self.child_obj) == WaitingListAllocation:
                customer_status_choices = ['with_assessor', 'draft']
                ria_generated_proposal_qs = self.child_obj.ria_generated_proposal.filter(customer_status__in=customer_status_choices)
            else:
                if type(self.child_obj) == AnnualAdmissionPermit:
                    customer_status_choices = ['with_assessor', 'draft', 'printing_sticker']
                elif type(self.child_obj) == AuthorisedUserPermit:
                    customer_status_choices = ['with_assessor', 'draft', 'awaiting_endorsement', 'printing_sticker', 'awaiting_payment']
                elif type(self.child_obj) == MooringLicence:
                    customer_status_choices = ['with_assessor', 'draft', 'awaiting_endorsement', 'printing_sticker', 'awaiting_payment', 'awaiting_documents']
            existing_proposal_qs=self.proposal_set.filter(customer_status__in=customer_status_choices,
                    proposal_type__in=ProposalType.objects.filter(code__in=[PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL]))
            ## cannot amend or renew
            if existing_proposal_qs or ria_generated_proposal_qs:
                amend_renew = None
            ## If Approval has been set for renewal, this takes priority
            elif self.renewal_document and self.renewal_sent:
                amend_renew = 'renew'
            return amend_renew
        except Exception as e:
            raise e

    def generate_doc(self, preview=False):
        if preview:
            from mooringlicensing.doctopdf import create_approval_doc_bytes
            return create_approval_doc_bytes(self)

        self.licence_document = create_approval_doc(self)  # Update the attribute to the latest doc

        self.save(version_comment='Created Approval PDF: {}'.format(self.licence_document.name))
        self.current_proposal.save(version_comment='Created Approval PDF: {}'.format(self.licence_document.name))
        logger.debug('Licence document for the approval: {} has been created'.format(self.lodgement_number))

        if hasattr(self, 'approval') and self.approval:
            self.approval.licence_document = self.licence_document
            self.approval.save()

    def generate_au_summary_doc(self, user):
        from mooringlicensing.doctopdf import create_authorised_user_summary_doc_bytes

        if hasattr(self, 'mooring'):
            moa_set = MooringOnApproval.objects.filter(
                mooring=self.mooring,
                approval__status__in=[Approval.APPROVAL_STATUS_SUSPENDED, Approval.APPROVAL_STATUS_CURRENT,]
            )
            if moa_set.count() > 0:
                # Authorised User exists
                contents_as_bytes = create_authorised_user_summary_doc_bytes(self)

                filename = 'authorised-user-summary-{}.pdf'.format(self.lodgement_number)
                document = AuthorisedUserSummaryDocument.objects.create(approval=self, name=filename)

                # Save the bytes to the disk
                document._file.save(filename, ContentFile(contents_as_bytes), save=True)

                self.authorised_user_summary_document = document  # Update to the latest doc
                self.save(version_comment='Created Authorised User Summary PDF: {}'.format(self.authorised_user_summary_document.name))
                self.current_proposal.save(version_comment='Created Authorised User Summary PDF: {}'.format(self.authorised_user_summary_document.name))

    def generate_renewal_doc(self):
        self.renewal_document = create_renewal_doc(self, self.current_proposal)
        self.save(version_comment='Created Renewal PDF: {}'.format(self.renewal_document.name))
        self.current_proposal.save(version_comment='Created Renewal PDF: {}'.format(self.renewal_document.name))

    def log_user_action(self, action, request=None):
        if request:
            return ApprovalUserAction.log_action(self, action, request.user)
        else:
            return ApprovalUserAction.log_action(self, action)

    def expire_approval(self, user):
        with transaction.atomic():
            try:
                today = timezone.localtime(timezone.now()).date()
                if self.status == Approval.APPROVAL_STATUS_CURRENT and self.expiry_date < today:
                    self.status = Approval.APPROVAL_STATUS_EXPIRED
                    self.save()
                    send_approval_expire_email_notification(self)
                    proposal = self.current_proposal
                    ApprovalUserAction.log_action(self, ApprovalUserAction.ACTION_EXPIRE_APPROVAL.format(self.id), user)
                    ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_EXPIRED_APPROVAL_.format(proposal.id), user)
            except:
                raise

    def approval_cancellation(self,request,details):
        with transaction.atomic():
            try:
                if not request.user in self.allowed_assessors:
                    raise ValidationError('You do not have access to cancel this approval')
                if not self.can_reissue and self.can_action:
                    raise ValidationError('You cannot cancel approval if it is not current or suspended')
                self.cancellation_date = details.get('cancellation_date').strftime('%Y-%m-%d')
                self.cancellation_details = details.get('cancellation_details')
                cancellation_date = datetime.datetime.strptime(self.cancellation_date,'%Y-%m-%d')
                cancellation_date = cancellation_date.date()
                self.cancellation_date = cancellation_date # test hack
                today = timezone.now().date()
                if cancellation_date <= today:
                    if not self.status == 'cancelled':
                        self.status = 'cancelled'
                        self.set_to_cancel = False
                        send_approval_cancel_email_notification(self)
                else:
                    self.set_to_cancel = True
                self.save()
                if type(self.child_obj) == WaitingListAllocation:
                    wla = self.child_obj
                    wla.internal_status = None
                    wla.wla_queue_date = None
                    wla.wla_order = None
                    wla.save()
                    wla.set_wla_order()
                # Log proposal action
                self.log_user_action(ApprovalUserAction.ACTION_CANCEL_APPROVAL.format(self.id),request)
                # Log entry for organisation
                self.current_proposal.log_user_action(ProposalUserAction.ACTION_CANCEL_APPROVAL.format(self.current_proposal.id),request)
            except:
                raise

    def approval_suspension(self,request,details):
        with transaction.atomic():
            try:
                if not request.user in self.allowed_assessors:
                    raise ValidationError('You do not have access to suspend this approval')
                if not self.can_reissue and self.can_action:
                    raise ValidationError('You cannot suspend approval if it is not current or suspended')
                if details.get('to_date'):
                    to_date= details.get('to_date').strftime('%d/%m/%Y')
                else:
                    to_date=''
                self.suspension_details = {
                    'from_date' : details.get('from_date').strftime('%d/%m/%Y'),
                    'to_date' : to_date,
                    'details': details.get('suspension_details'),
                }
                today = timezone.now().date()
                from_date = datetime.datetime.strptime(self.suspension_details['from_date'],'%d/%m/%Y')
                from_date = from_date.date()
                if from_date <= today:
                    if not self.status == 'suspended':
                        self.status = 'suspended'
                        self.set_to_suspend = False
                        self.save()
                        send_approval_suspend_email_notification(self)
                else:
                    self.set_to_suspend = True
                self.save()
                if type(self.child_obj) == MooringLicence:
                    self.child_obj.update_auth_user_permits()
                # Log approval action
                self.log_user_action(ApprovalUserAction.ACTION_SUSPEND_APPROVAL.format(self.id),request)
                # Log entry for proposal
                self.current_proposal.log_user_action(ProposalUserAction.ACTION_SUSPEND_APPROVAL.format(self.current_proposal.id),request)
            except:
                raise

    def reinstate_approval(self,request):
        with transaction.atomic():
            try:
                if not request.user in self.allowed_assessors:
                    raise ValidationError('You do not have access to reinstate this approval')
                if not self.can_reinstate:
                    raise ValidationError('You cannot reinstate approval at this stage')
                today = timezone.now().date()
                if not self.can_reinstate and self.expiry_date>= today:
                    raise ValidationError('You cannot reinstate approval at this stage')
                if self.status == 'cancelled':
                    self.cancellation_details =  ''
                    self.cancellation_date = None
                if self.status == 'surrendered':
                    self.surrender_details = {}
                if self.status == 'suspended':
                    self.suspension_details = {}
                previous_status = self.status
                self.status = 'current'
                self.save()
                if type(self.child_obj) == WaitingListAllocation and previous_status in ['cancelled', 'surrendered']:
                    wla = self.child_obj
                    wla.internal_status = 'waiting'
                    current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
                    wla.wla_queue_date = current_datetime
                    wla.save()
                    wla.set_wla_order()
                send_approval_reinstate_email_notification(self, request)
                # Log approval action
                self.log_user_action(ApprovalUserAction.ACTION_REINSTATE_APPROVAL.format(self.id),request)
                # Log entry for proposal
                self.current_proposal.log_user_action(ProposalUserAction.ACTION_REINSTATE_APPROVAL.format(self.current_proposal.id),request)
            except:
                raise

    def approval_surrender(self,request,details):
        with transaction.atomic():
            try:
                if not request.user.mooringlicensing_organisations.filter(organisation_id = self.applicant_id):
                    if request.user not in self.allowed_assessors and not is_customer(request):
                        raise ValidationError('You do not have access to surrender this approval')
                if not self.can_reissue and self.can_action:
                    raise ValidationError('You cannot surrender approval if it is not current or suspended')
                self.surrender_details = {
                    'surrender_date' : details.get('surrender_date').strftime('%d/%m/%Y'),
                    'details': details.get('surrender_details'),
                }
                today = timezone.now().date()
                surrender_date = datetime.datetime.strptime(self.surrender_details['surrender_date'],'%d/%m/%Y')
                surrender_date = surrender_date.date()
                if surrender_date <= today:
                    if not self.status == 'surrendered':
                        self.status = 'surrendered'
                        self.set_to_surrender = False
                        self.save()
                        send_approval_surrender_email_notification(self)
                else:
                    self.set_to_surrender = True
                self.save()
                if type(self.child_obj) == WaitingListAllocation:
                    wla = self.child_obj
                    wla.internal_status = None
                    wla.wla_queue_date = None
                    wla.wla_order = None
                    wla.save()
                    wla.set_wla_order()
                # Log approval action
                self.log_user_action(ApprovalUserAction.ACTION_SURRENDER_APPROVAL.format(self.id),request)
                # Log entry for proposal
                self.current_proposal.log_user_action(ProposalUserAction.ACTION_SURRENDER_APPROVAL.format(self.current_proposal.id),request)
            except:
                raise

    # required to clean db of approvals with no child objs
    @property
    def no_child_obj(self):
        no_child_obj = True
        if hasattr(self, 'waitinglistallocation'):
            no_child_obj = False
        elif hasattr(self, 'annualadmissionpermit'):
            no_child_obj = False
        elif hasattr(self, 'authoriseduserpermit'):
            no_child_obj = False
        elif hasattr(self, 'mooringlicence'):
            no_child_obj = False
        return no_child_obj

    @property
    def child_obj(self):
        if hasattr(self, 'waitinglistallocation'):
            return self.waitinglistallocation
        elif hasattr(self, 'annualadmissionpermit'):
            return self.annualadmissionpermit
        elif hasattr(self, 'authoriseduserpermit'):
            return self.authoriseduserpermit
        elif hasattr(self, 'mooringlicence'):
            return self.mooringlicence
        else:
            raise ObjectDoesNotExist("Approval must have an associated child object - WLA, AAP, AUP or ML")

    @classmethod
    def approval_types_dict(cls, include_codes=[]):
        type_list = []
        for approval_type in Approval.__subclasses__():
            if hasattr(approval_type, 'code'):
                if approval_type.code in include_codes:
                    type_list.append({
                        "code": approval_type.code,
                        "description": approval_type.description,
                    })

        return type_list

    def get_fee_items(self):
        fee_items = []
        for proposal in self.proposal_set.all():
            for application_fee in proposal.application_fees.all():
                if application_fee.fee_items:
                    for fee_item in application_fee.fee_items.all():
                        fee_items.append(fee_item)
                else:
                    # Should not reach here, however the data generated at the early stage of the development may reach here.
                    logger.error('ApplicationFee: {} does not have any fee_item.  It should have at least one.')
        return fee_items

    @property
    def latest_applied_season(self):
        latest_applied_season = None

        for fee_item in self.get_fee_items():
            if latest_applied_season:
                if latest_applied_season.end_date < fee_item.fee_period.fee_season.end_date:
                    latest_applied_season = fee_item.fee_period.fee_season
            else:
                latest_applied_season = fee_item.fee_period.fee_season

        return latest_applied_season

    def _handle_stickers_to_be_removed(self, stickers_to_be_removed, stickers_to_be_replaced_for_renewal=[]):
        for sticker in stickers_to_be_removed:
            if sticker.status in [Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING,]:
                if sticker in stickers_to_be_replaced_for_renewal:
                    # For renewal, old sticker is still in 'current' status until new sticker gets 'current' status
                    # When new sticker gets 'current' status, old sticker gets 'expired' status
                    pass
                else:
                    sticker.status = Sticker.STICKER_STATUS_TO_BE_RETURNED
                    sticker.save()
                # TODO: email to the permission holder to notify the existing sticker to be returned
            elif sticker.status == Sticker.STICKER_STATUS_TO_BE_RETURNED:
                # Do nothing
                pass
            elif sticker.status in [Sticker.STICKER_STATUS_READY, Sticker.STICKER_STATUS_NOT_READY_YET,]:
                sticker.status = Sticker.STICKER_STATUS_CANCELLED
                sticker.save()
            else:
                # Do nothing
                pass

    def manage_stickers(self, proposal):
        return self.child_obj.manage_stickers(proposal)


class WaitingListAllocation(Approval):
    approval = models.OneToOneField(Approval, parent_link=True)
    code = 'wla'
    prefix = 'WLA'
    description = 'Waiting List Allocation'
    template_file_key = GlobalSettings.KEY_WLA_TEMPLATE_FILE

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    def get_context_for_licence_permit(self):
        try:
            # v_details = self.current_proposal.vessel_details
            v_details = self.current_proposal.latest_vessel_details
            v_ownership = self.current_proposal.vessel_ownership
            if v_details and not v_ownership.end_date:
                vessel_rego_no = v_details.vessel.rego_no
                vessel_name = v_details.vessel_name
                vessel_length = v_details.vessel_applicable_length
                vessel_draft = v_details.vessel_draft
            else:
                vessel_rego_no = ''
                vessel_name = ''
                vessel_length = ''
                vessel_draft = ''

            # Return context for the licence/permit document
            context = {
                'approval': self,
                'application': self.current_proposal,
                'issue_date': self.issue_date.strftime('%d/%m/%Y'),
                'applicant_name': self.submitter.get_full_name(),
                'applicant_full_name': self.submitter.get_full_name(),
                'bay_name': self.current_proposal.preferred_bay.name,
                'allocation_date': self.wla_queue_date.strftime('%d/%m/%Y'),
                'position_number': self.wla_order,
                'vessel_rego_no': vessel_rego_no,
                'vessel_name': vessel_name,
                'vessel_length': vessel_length,
                'vessel_draft': vessel_draft,
                'public_url': get_public_url(),
            }
            return context
        except Exception as e:
            msg = 'Waiting List Allocation: {} cannot generate document. {}'.format(self.lodgement_number, str(e))
            logger.error(msg)
            raise e

    def save(self, *args, **kwargs):
        if self.lodgement_number == '':
            self.lodgement_number = self.prefix + '{0:06d}'.format(self.next_id)
        kwargs.pop('version_user', None)
        kwargs.pop('version_comment', None)
        kwargs['no_revision'] = True
        super(Approval, self).save(*args, **kwargs)

    def manage_stickers(self, proposal):
        # No stickers for WL
        proposal.processing_status = Proposal.PROCESSING_STATUS_APPROVED
        proposal.customer_status = Proposal.CUSTOMER_STATUS_APPROVED
        proposal.save()
        return [], []

    def set_wla_order(self):
        place = 1
        # set wla order per bay for current allocations
        for w in WaitingListAllocation.objects.filter(
                wla_queue_date__isnull=False,
                current_proposal__preferred_bay=self.current_proposal.preferred_bay,
                status__in=['current', 'suspended']).order_by(
                #status='current').order_by(
                        'wla_queue_date'):
            w.wla_order = place
            w.save()
            place += 1
        self.refresh_from_db()
        return self


class AnnualAdmissionPermit(Approval):
    approval = models.OneToOneField(Approval, parent_link=True)
    code = 'aap'
    prefix = 'AAP'
    description = 'Annual Admission Permit'
    sticker_colour = 'blue'
    template_file_key = GlobalSettings.KEY_AAP_TEMPLATE_FILE

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    def get_context_for_licence_permit(self):
        try:
            # Return context for the licence/permit document
            v_details = self.current_proposal.latest_vessel_details
            v_ownership = self.current_proposal.vessel_ownership
            if v_details and not v_ownership.end_date:
                vessel_rego_no = v_details.vessel.rego_no
                vessel_name = v_details.vessel_name
                vessel_length = v_details.vessel_applicable_length
            else:
                vessel_rego_no = ''
                vessel_name = ''
                vessel_length = ''

            context = {
                'approval': self,
                'application': self.current_proposal,
                'issue_date': self.issue_date.strftime('%d/%m/%Y'),
                'applicant_name': self.submitter.get_full_name(),
                'p_address_line1': self.postal_address_line1,
                'p_address_line2': self.postal_address_line2,
                'p_address_suburb': self.postal_address_suburb,
                'p_address_state': self.postal_address_state,
                'p_address_postcode': self.postal_address_postcode,
                'vessel_rego_no': vessel_rego_no,
                'vessel_name': vessel_name,
                'vessel_length': vessel_length,
                'expiry_date': self.expiry_date.strftime('%d/%m/%Y'),
                'public_url': get_public_url(),
            }
            return context
        except Exception as e:
            msg = 'Annual Admission Permit: {} cannot generate permit. {}'.format(self.lodgement_number, str(e))
            logger.error(msg)
            raise e

    def save(self, *args, **kwargs):
        if self.lodgement_number == '':
            self.lodgement_number = self.prefix + '{0:06d}'.format(self.next_id)
        kwargs.pop('version_user', None)
        kwargs.pop('version_comment', None)
        kwargs['no_revision'] = True
        super(Approval, self).save(*args, **kwargs)

    def _create_new_sticker_by_proposal(self, proposal):
        sticker = Sticker.objects.create(
            approval=self,
            vessel_ownership=proposal.vessel_ownership,
            fee_constructor=proposal.fee_constructor,
            proposal_initiated=proposal,
            fee_season=self.latest_applied_season,
        )
        return sticker

    def _get_current_stickers(self):
        current_stickers = self.stickers.filter(
            status__in=[
                Sticker.STICKER_STATUS_CURRENT,
                Sticker.STICKER_STATUS_AWAITING_PRINTING,
            ]
        )
        return current_stickers

    def manage_stickers(self, proposal):
        # When new
        if proposal.proposal_type.code == PROPOSAL_TYPE_NEW:
            # New sticker created with status Ready
            new_sticker = self._create_new_sticker_by_proposal(proposal)

            # Application goes to status Printing Sticker
            proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
            proposal.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
            proposal.save()

            return [], []
        elif proposal.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
            if proposal.vessel_ownership == proposal.previous_application.vessel_ownership:
                return [], []
            else:
                # New sticker created with status Ready
                new_sticker = self._create_new_sticker_by_proposal(proposal)

                # Old sticker goes to status To be Returned
                current_stickers = self._get_current_stickers()
                for current_sticker in current_stickers:
                    current_sticker.status = Sticker.STICKER_STATUS_TO_BE_RETURNED
                    current_sticker.save()

                if current_stickers:
                    if proposal.vessel_ownership == proposal.previous_application.vessel_ownership:
                        # When the application does not change to new vessel,
                        # it gets 'printing_sticker' status
                        proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                        proposal.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
                        proposal.save()
                    else:
                        # When the application changes to new vessel
                        # it gets 'sticker_to_be_returned' status
                        new_sticker.status = Sticker.STICKER_STATUS_NOT_READY_YET
                        new_sticker.save()
                        proposal.processing_status = Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED
                        proposal.customer_status = Proposal.CUSTOMER_STATUS_STICKER_TO_BE_RETURNED
                        proposal.save()
                else:
                    # Even when 'amendment' application, there might be no current stickers because of sticker-lost, etc
                    proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                    proposal.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
                    proposal.save()

                return [], list(current_stickers)
        elif proposal.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
            if not proposal.approval.reissued or not proposal.keep_existing_vessel:
                # New sticker goes to ready
                current_stickers = self._get_current_stickers()
                sticker_to_be_replaced = current_stickers.first()  # There should be 0 or 1 current sticker (0: when vessel sold before renewal)
                new_sticker = Sticker.objects.create(
                    approval=self,
                    # vessel_ownership=sticker_to_be_replaced.vessel_ownership,
                    vessel_ownership=proposal.vessel_ownership if proposal.vessel_ownership else sticker_to_be_replaced.vessel_ownership if sticker_to_be_replaced else None,
                    fee_constructor=proposal.fee_constructor if proposal.fee_constructor else sticker_to_be_replaced.fee_constructor if sticker_to_be_replaced else None,
                    proposal_initiated=proposal,
                    fee_season=self.latest_applied_season,
                )

                # Old sticker goes to status Expired when new sticker is printed
                new_sticker.sticker_to_replace = sticker_to_be_replaced
                new_sticker.save()

                # Application goes to status Printing Sticker
                proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                proposal.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
                proposal.save()

                return [], []
            else:
                return [], []


class AuthorisedUserPermit(Approval):
    approval = models.OneToOneField(Approval, parent_link=True)
    code = 'aup'
    prefix = 'AUP'
    description = 'Authorised User Permit'
    sticker_colour = 'yellow'
    template_file_key = GlobalSettings.KEY_AUP_TEMPLATE_FILE

    class Meta:
        app_label = 'mooringlicensing'

    def get_authorised_by(self):
        preference = self.current_proposal.child_obj.get_mooring_authorisation_preference()
        return preference

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    def get_context_for_licence_permit(self):
        try:
            # Return context for the licence/permit document
            moorings = []
            for mooring in self.current_moorings:
                m = {}
                # calculate phone number(s)
                numbers = []
                if mooring.mooring_licence.submitter.mobile_number:
                    numbers.append(mooring.mooring_licence.submitter.mobile_number)
                elif mooring.mooring_licence.submitter.phone_number:
                    numbers.append(mooring.mooring_licence.submitter.phone_number)
                m['name'] = mooring.name
                m['licensee_full_name'] = mooring.mooring_licence.submitter.get_full_name()
                m['licensee_email'] = mooring.mooring_licence.submitter.email
                m['licensee_phone'] = ', '.join(numbers)
                moorings.append(m)

            v_details = self.current_proposal.latest_vessel_details
            v_ownership = self.current_proposal.vessel_ownership
            if v_details and not v_ownership.end_date:
                vessel_rego_no = v_details.vessel.rego_no
                vessel_name = v_details.vessel_name
                vessel_length = v_details.vessel_applicable_length
                vessel_draft = v_details.vessel_draft
            else:
                vessel_rego_no = ''
                vessel_name = ''
                vessel_length = ''
                vessel_draft = ''

            context = {
                'approval': self,
                'application': self.current_proposal,
                'issue_date': self.issue_date.strftime('%d/%m/%Y'),
                'applicant_name': self.submitter.get_full_name(),
                'p_address_line1': self.postal_address_line1,
                'p_address_line2': self.postal_address_line2,
                'p_address_suburb': self.postal_address_suburb,
                'p_address_state': self.postal_address_state,
                'p_address_postcode': self.postal_address_postcode,
                'vessel_rego_no': vessel_rego_no,
                'vessel_name': vessel_name,
                'vessel_length': vessel_length,
                'vessel_draft': vessel_draft,
                'moorings': moorings,  # m.name, m.licensee_full_name, m.licensee_email, m.licensee_phone
                'expiry_date': self.expiry_date.strftime('%d/%m/%Y'),
                'public_url': get_public_url(),
            }
            return context
        except Exception as e:
            msg = 'Authorised User Permit: {} cannot generate permit. {}'.format(self.lodgement_number, str(e))
            logger.error(msg)
            raise e

    def save(self, *args, **kwargs):
        if self.lodgement_number == '':
            self.lodgement_number = self.prefix + '{0:06d}'.format(self.next_id)
        kwargs.pop('version_user', None)
        kwargs.pop('version_comment', None)
        kwargs['no_revision'] = True
        super(Approval, self).save(*args, **kwargs)

    def internal_reissue(self, mooring_licence=None):
        ## now reissue approval
        if self.current_proposal.vessel_ownership and not self.current_proposal.vessel_ownership.end_date:
            # When there is a current vessel
            self.current_proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
            self.current_proposal.save()
        self.reissued=True
        self.save()
        # Create a log entry for the proposal and approval
        self.current_proposal.log_user_action(ProposalUserAction.ACTION_REISSUE_APPROVAL.format(self.lodgement_number))
        self.approval.log_user_action(ApprovalUserAction.ACTION_REISSUE_APPROVAL.format(self.lodgement_number))
        if mooring_licence:
            self.approval.log_user_action(ApprovalUserAction.ACTION_REISSUE_APPROVAL_ML.format(mooring_licence.lodgement_number))
        ## final approval
        self.current_proposal.final_approval()

    def update_moorings(self, mooring_licence):
        if mooring_licence.status not in ['current', 'suspended']:
            # end date relationship between aup and mooring attached to mooring_licence
            moa = self.mooringonapproval_set.get(mooring__mooring_licence=mooring_licence)
            moa.end_date = datetime.datetime.now().date()
            moa.save()
        if not self.mooringonapproval_set.filter(mooring__mooring_licence__status='current'):
            ## When no moorings left on authorised user permit, include information that permit holder can amend and apply for new mooring up to expiry date.
            send_auth_user_no_moorings_notification(self.approval)
        for moa in self.mooringonapproval_set.all():
            ## notify authorised user permit holder that the mooring is no longer available
            if moa.mooring == mooring_licence.mooring:
                ## send email to auth user
                send_auth_user_mooring_removed_notification(self.approval, mooring_licence)
        self.internal_reissue(mooring_licence)

    @property
    def current_moorings(self):
        moorings = []
        moas = self.mooringonapproval_set.filter(Q(end_date__isnull=True) & Q(mooring__mooring_licence__status=MooringLicence.APPROVAL_STATUS_CURRENT))
        for moa in moas:
            moorings.append(moa.mooring)
        return moorings

    #def previous_moorings(self, proposal=None):
    #    moorings_str = ''
    #    #if vooa.vessel_ownership.vessel.rego_no != self.current_proposal.rego_no or self.current_proposal.keep_existing_vessel:
    #     #   attribute_list.append(vooa.vessel_ownership.vessel.rego_no)
    #    for moa in self.mooringonapproval_set.all():
    #        # do not show mooring from latest application in "Current Moorings"
    #        #if not moa.mooring.id == self.current_proposal.proposed_issuance_approval.get("mooring_id"):
    #        if ((self.current_proposal.proposed_issuance_approval and moa.mooring.id != self.current_proposal.proposed_issuance_approval.get("mooring_id")) 
    #                or self.current_proposal.keep_existing_mooring 
    #                or (proposal and proposal.processing_status in [
    #                    'draft', 
    #                    'with_assessor', 
    #                    'with_assessor_requirements', 
    #                    'with_approver', 
    #                    'awaiting_endorsement', 
    #                    'awaiting_documents', 
    #                    'awaiting_payment'])
    #                ):
    #            moorings_str += moa.mooring.name + ','
    #    # truncate trailing comma
    #    moorings_str = moorings_str[0:-1]
    #    return moorings_str

    #def previous_moorings(self):
    #    moorings_str = ''
    #    total_moorings = self.mooringonapproval_set.count()
    #    if total_moorings > 1:
    #        for moa in self.mooringonapproval_set.all():
    #            # do not show mooring from latest application in "Current Moorings"
    #            #if not moa.mooring.id == self.current_proposal.proposed_issuance_approval.get("mooring_id"):
    #            if ((self.current_proposal.proposed_issuance_approval and moa.mooring.id != self.current_proposal.proposed_issuance_approval.get("mooring_id")) 
    #                    or self.current_proposal.keep_existing_mooring):
    #                moorings_str += moa.mooring.name + ','
    #        # truncate trailing comma
    #        moorings_str = moorings_str[0:-1]
    #    # only 1 mooring
    #    elif total_moorings:
    #        moorings_str = self.mooringonapproval_set.first().mooring.name
    #    #return moorings_str[0:-1] if moorings_str else ''
    #    return moorings_str

    def _get_current_moas(self):
        moas_current = self.mooringonapproval_set. \
            filter(Q(end_date__isnull=True) | Q(mooring__mooring_licence__status=MooringLicence.APPROVAL_STATUS_CURRENT)). \
            filter(sticker__status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])
        return moas_current

    def manage_stickers(self, proposal):
        moas_to_be_reallocated = []  # MooringOnApproval objects to be on the new stickers
        stickers_to_be_returned = []  # Stickers to be returned
        stickers_to_be_replaced = []  # Stickers to be replaced by new stickers.  Temporarily used
        stickers_to_be_replaced_for_renewal = []  # When replaced for renewal, sticker doesn't need to be returned.  This is used for that.

        # 1. Find all the moorings which should be assigned to the new stickers
        new_moas = MooringOnApproval.objects.filter(approval=self, sticker__isnull=True)  # New moa doesn't have stickers.
        for moa in new_moas:
            if moa not in moas_to_be_reallocated:
                if moa.approval and moa.approval.current_proposal and moa.approval.current_proposal.vessel_details:
                    moas_to_be_reallocated.append(moa)
                else:
                    # Null vessel
                    pass

        # 2. Find all the moas to be removed
        # 3. Fild all the stickers to be replaced by the moas found at the #2, then find all the moas to be replaced
        moas_to_be_removed = []
        if proposal.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
            # When renewal, all the current/awaiting_printing stickers to be replaced
            # All the sticker gets 'expired' status once payment made
            moas_current = self._get_current_moas()
            for moa in moas_current:
                if moa.sticker not in stickers_to_be_replaced:
                    stickers_to_be_replaced.append(moa.sticker)
                    stickers_to_be_replaced_for_renewal.append(moa.sticker)
            moas_to_be_removed = self.mooringonapproval_set. \
                filter(Q(end_date__isnull=False) | ~Q(mooring__mooring_licence__status=MooringLicence.APPROVAL_STATUS_CURRENT)). \
                filter(sticker__status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])
        elif proposal.proposal_type.code == PROPOSAL_TYPE_AMENDMENT and proposal.vessel_ownership != proposal.previous_application.vessel_ownership:
            # When amendment and vessel changed, all the current/awaiting_printing stickers to be replaced
            moas_current = self._get_current_moas()
            for moa in moas_current:
                if moa.sticker not in stickers_to_be_replaced:
                    stickers_to_be_replaced.append(moa.sticker)
            moas_to_be_removed = self.mooringonapproval_set. \
                filter(Q(end_date__isnull=False) | ~Q(mooring__mooring_licence__status=MooringLicence.APPROVAL_STATUS_CURRENT)). \
                filter(sticker__status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])
        else:
            # MooringOnApprovals which has end_date OR related ML is not current status, but sticker is still in current/awaiting_printing status
            moas_to_be_removed = self.mooringonapproval_set.\
                filter(Q(end_date__isnull=False) | ~Q(mooring__mooring_licence__status=MooringLicence.APPROVAL_STATUS_CURRENT)).\
                filter(sticker__status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])
            for moa in moas_to_be_removed:
                if moa.sticker not in stickers_to_be_replaced:
                    stickers_to_be_replaced.append(moa.sticker)

        # Handle vessel changes
        self.handle_vessel_changes(moas_to_be_reallocated, stickers_to_be_replaced)

        # Find moas on the stickers which are to be replaced
        for sticker in stickers_to_be_replaced:
            stickers_to_be_returned.append(sticker)
            for moa in sticker.mooringonapproval_set.all():
                # This sticker is possibly to be removed, but it may have current mooring(s)
                if moa not in moas_to_be_removed and moa not in moas_to_be_reallocated:
                    # This moa is not to be removed.  Therefore, it should be reallocated
                    moas_to_be_reallocated.append(moa)

        if len(moas_to_be_reallocated) > 0:
            # There is at least one mooring to be allocated to a new sticker
            if len(moas_to_be_reallocated) % 4 != 0:
                # The number of moorings to be allocated is not a multiple of 4, which requires existing non-filled sticker to be replaced, too
                # Find sticker which doesn't have 4 moorings on it
                stickers = self.stickers.filter(
                    status__in=(Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING)).annotate(
                    num_of_moorings=Count('mooringonapproval')).filter(num_of_moorings__lt=4)
                if stickers.count() == 1:
                    # There is one sticker found, which doesn't have 4 moorings
                    sticker = stickers.first()
                    if sticker not in stickers_to_be_returned:
                        stickers_to_be_returned.append(sticker)
                    for moa in sticker.mooringonapproval_set.all():
                        if moa not in moas_to_be_reallocated:
                            moas_to_be_reallocated.append(moa)
                elif stickers.count() > 1:
                    # Should not reach here
                    raise ValueError('AUP: {} has more than one stickers without 4 moorings'.format(self.lodgement_number))

        # Finally, assign mooring(s) to new sticker(s)
        self._assign_to_new_stickers(moas_to_be_reallocated, proposal, stickers_to_be_replaced_for_renewal)
        self._handle_stickers_to_be_removed(stickers_to_be_returned, stickers_to_be_replaced_for_renewal)

        # There may be sticker(s) to be returned by record-sale
        stickers_return = proposal.approval.stickers.filter(status__in=[Sticker.STICKER_STATUS_TO_BE_RETURNED,])
        for sticker in stickers_return:
            stickers_to_be_returned.append(sticker)

        return moas_to_be_reallocated, stickers_to_be_returned

    def handle_vessel_changes(self, moas_to_be_reallocated, stickers_to_be_replaced):
        if self.approval.current_proposal.vessel_removed:
            # self.current_proposal.vessel_ownership.vessel_removed --> All the stickers to be returned
            # A vessel --> No vessels
            stickers = self.stickers.filter(
                status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])
            for sticker in stickers:
                if sticker not in stickers_to_be_replaced:
                    stickers_to_be_replaced.append(sticker)
        if self.approval.current_proposal.vessel_swapped:
            # All the stickers to be removed and all the mooring on them to be reallocated
            # A vessel --> Another vessel
            stickers = self.stickers.filter(
                status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])
            for sticker in stickers:
                if sticker not in stickers_to_be_replaced:
                    stickers_to_be_replaced.append(sticker)
        if self.approval.current_proposal.vessel_amend_new:
            # --> Create new sticker
            # No vessels --> New vessel
            moas_list = self.mooringonapproval_set. \
                filter(
                Q(end_date__isnull=True) & Q(mooring__mooring_licence__status=MooringLicence.APPROVAL_STATUS_CURRENT))
            for moa in moas_list:
                if moa not in moas_to_be_reallocated:
                    moas_to_be_reallocated.append(moa)

    def _assign_to_new_stickers(self, moas_to_be_on_new_sticker, proposal, stickers_to_be_replaced_for_renewal=[]):
        new_sticker = None
        for moa_to_be_on_new_sticker in moas_to_be_on_new_sticker:
            if not new_sticker or new_sticker.mooringonapproval_set.count() % 4 == 0:
                # There is no stickers to fill, or there is a sticker but already be filled with 4 moas, create a new sticker
                stickers_to_be_returned = Sticker.objects.filter(approval=self, status__in=[Sticker.STICKER_STATUS_TO_BE_RETURNED,])
                # if proposal.proposal_type.code == PROPOSAL_TYPE_AMENDMENT and proposal.vessel_ownership != proposal.previous_application.vessel_ownership:
                if stickers_to_be_returned.count():
                    # We don't want to print a new sticker if there is a sticker with 'to_be_returned' status for this permit
                    new_status = Sticker.STICKER_STATUS_NOT_READY_YET  # This sticker gets 'ready' status once the sticker with 'to be returned' status is returned.
                else:
                    new_status = Sticker.STICKER_STATUS_READY
                new_sticker = Sticker.objects.create(
                    approval=self,
                    vessel_ownership=moa_to_be_on_new_sticker.sticker.vessel_ownership if moa_to_be_on_new_sticker.sticker else proposal.vessel_ownership,
                    fee_constructor=proposal.fee_constructor if proposal.fee_constructor else moa_to_be_on_new_sticker.sticker.fee_constructor if moa_to_be_on_new_sticker.sticker else None,
                    proposal_initiated=proposal,
                    fee_season=self.latest_applied_season,
                    status=new_status
                )
            if moa_to_be_on_new_sticker.sticker in stickers_to_be_replaced_for_renewal:
                # Store old sticker in the new sticker in order to set 'expired' status to it once the new sticker gets 'current' status
                new_sticker.sticker_to_replace = moa_to_be_on_new_sticker.sticker
                new_sticker.save()
            # Update moa by a new sticker
            moa_to_be_on_new_sticker.sticker = new_sticker
            moa_to_be_on_new_sticker.save()


class MooringLicence(Approval):
    approval = models.OneToOneField(Approval, parent_link=True)
    code = 'ml'
    prefix = 'MOL'
    description = 'Mooring Licence'
    sticker_colour = 'red'
    template_file_key = GlobalSettings.KEY_ML_TEMPLATE_FILE

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def child_obj(self):
        raise NotImplementedError('This method cannot be called on a child_obj')

    def get_context_for_au_summary(self):
        if not hasattr(self, 'mooring'):
            # There should not be AuthorisedUsers for this ML
            return {}
        moa_set = MooringOnApproval.objects.filter(
            mooring=self.mooring,
            approval__status__in=[Approval.APPROVAL_STATUS_SUSPENDED, Approval.APPROVAL_STATUS_CURRENT,]
        )

        authorised_persons = []

        for moa in moa_set:
            authorised_person = {}
            if type(moa.approval.child_obj) == AuthorisedUserPermit:
                aup = moa.approval.child_obj
                authorised_by = aup.get_authorised_by()
                authorised_by = authorised_by.upper().replace('_', ' ')

                authorised_person['full_name'] = aup.submitter.get_full_name()
                authorised_person['vessel'] = {
                    'rego_no': aup.current_proposal.vessel_details.vessel.rego_no if aup.current_proposal.vessel_details else '',
                    'vessel_name': aup.current_proposal.vessel_details.vessel_name if aup.current_proposal.vessel_details else '',
                    'length': aup.current_proposal.vessel_details.vessel_applicable_length if aup.current_proposal.vessel_details else '',
                    'draft': aup.current_proposal.vessel_details.vessel_draft if aup.current_proposal.vessel_details else '',
                }
                authorised_person['authorised_date'] = aup.issue_date.strftime('%d/%m/%Y')
                authorised_person['authorised_by'] = authorised_by
                authorised_person['mobile_number'] = aup.submitter.mobile_number
                authorised_person['email_address'] = aup.submitter.email
                authorised_persons.append(authorised_person)

        today = datetime.datetime.now(pytz.timezone(settings.TIME_ZONE)).date()

        context = {
            'approval': self,
            'application': self.current_proposal,
            'issue_date': self.issue_date.strftime('%d/%m/%Y'),
            'applicant_first_name': self.submitter.first_name,
            'mooring_name': self.mooring.name,
            'authorised_persons': authorised_persons,
            'public_url': get_public_url(),
            'doc_generated_date': today.strftime('%d/%m/%Y'),
        }

        return context

    def get_context_for_licence_permit(self):
        try:
            logger.info("self.issue_date: {}".format(self.issue_date))
            logger.info("self.expiry_date: {}".format(self.expiry_date))
            # Return context for the licence/permit document
            licenced_vessel = None
            additional_vessels = []

            max_vessel_length = 0
            # for vessel in self.current_vessels:
            current_vessels = self.get_current_vessels_for_licence_doc()
            for vessel in current_vessels:
                v = {}
                v['vessel_rego_no'] = vessel['rego_no']
                v['vessel_name'] = vessel['latest_vessel_details'].vessel_name
                v['vessel_length'] = vessel['latest_vessel_details'].vessel_applicable_length
                v['vessel_draft'] = vessel['latest_vessel_details'].vessel_draft
                if not licenced_vessel:
                    # No licenced vessel stored yet
                    licenced_vessel = v
                else:
                    if licenced_vessel['vessel_length'] < v['vessel_length']:
                        # Found a larger vessel than the one stored as a licenced.  Replace it by the larger one.
                        additional_vessels.append(licenced_vessel)
                        licenced_vessel = v
                    else:
                        additional_vessels.append(v)

            context = {
                'approval': self,
                'application': self.current_proposal,
                'issue_date': self.issue_date.strftime('%d/%m/%Y'),
                'applicant_name': self.submitter.get_full_name(),
                'p_address_line1': self.postal_address_line1,
                'p_address_line2': self.postal_address_line2,
                'p_address_suburb': self.postal_address_suburb,
                'p_address_state': self.postal_address_state,
                'p_address_postcode': self.postal_address_postcode,
                'licenced_vessel': licenced_vessel,  # vessel_rego_no, vessel_name, vessel_length, vessel_draft
                'additional_vessels': additional_vessels,
                'mooring': self.mooring,
                'expiry_date': self.expiry_date.strftime('%d/%m/%Y'),
                'public_url': get_public_url(),
            }
            return context
        except Exception as e:
            msg = 'Mooring Licence: {} cannot generate licence. {}'.format(self.lodgement_number, str(e))
            logger.error(msg)
            raise e

    def save(self, *args, **kwargs):
        if self.lodgement_number == '':
            self.lodgement_number = self.prefix + '{0:06d}'.format(self.next_id)
        kwargs.pop('version_user', None)
        kwargs.pop('version_comment', None)
        kwargs['no_revision'] = True
        super(Approval, self).save(*args, **kwargs)

    def internal_reissue(self):
        ## now reissue approval
        self.current_proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
        self.current_proposal.save()
        self.reissued=True
        self.save()
        # Create a log entry for the proposal and approval
        self.current_proposal.log_user_action(ProposalUserAction.ACTION_REISSUE_APPROVAL.format(self.lodgement_number))
        self.approval.log_user_action(ApprovalUserAction.ACTION_REISSUE_APPROVAL.format(self.lodgement_number))
        ## final approval
        self.current_proposal.final_approval()

    def update_auth_user_permits(self):
        if hasattr(self, 'mooring'):
            moa_set = MooringOnApproval.objects.filter(
                mooring=self.mooring,
                # approval__status='current'
                approval__status__in=[Approval.APPROVAL_STATUS_SUSPENDED, Approval.APPROVAL_STATUS_CURRENT,],
            )
            for moa in moa_set:
                if type(moa.approval.child_obj) == AuthorisedUserPermit:
                    moa.approval.child_obj.update_moorings(self)

    def _create_new_sticker_by_proposal(self, proposal):
        sticker = Sticker.objects.create(
            approval=self,
            vessel_ownership=proposal.vessel_ownership,
            fee_constructor=proposal.fee_constructor,
            proposal_initiated=proposal,
            fee_season=self.latest_applied_season,
        )
        return sticker

    def _get_current_stickers(self):
        current_stickers = self.stickers.filter(
            status__in=[
                Sticker.STICKER_STATUS_CURRENT,
                Sticker.STICKER_STATUS_AWAITING_PRINTING,
            ]
        )
        return current_stickers

    def manage_stickers(self, proposal):
#        # Retrieve all the stickers regardless of the status
#        stickers_present = list(self.stickers.all())
#
#        stickers_required = []  # Store all the stickers we want to keep
#
#        # Loop through all the current vessels
#        for vessel_ownership in self.vessel_ownership_list:
#            # Look for the sticker for the vessel
#            sticker = self.stickers.filter(
#                status__in=(
#                    Sticker.STICKER_STATUS_CURRENT,
#                    Sticker.STICKER_STATUS_AWAITING_PRINTING,
#                    Sticker.STICKER_STATUS_TO_BE_RETURNED,),
#                vessel_ownership=vessel_ownership,
#            )
#            if sticker:
#                sticker = sticker.first()
#            else:
#                # Sticker not found --> Create it
#                sticker = Sticker.objects.create(
#                    approval=self,
#                    vessel_ownership=proposal.vessel_ownership,
#                    fee_constructor=proposal.fee_constructor,
#                    proposal_initiated=proposal,
#                    fee_season=self.latest_applied_season,
#                )
#            stickers_required.append(sticker)
#
#        if proposal.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
#            for sticker_to_be_replaced in stickers_required:
#                new_sticker = Sticker.objects.create(
#                    approval=self,
#                    vessel_ownership=sticker_to_be_replaced.vessel_ownership,
#                    fee_constructor=proposal.fee_constructor if proposal.fee_constructor else sticker_to_be_replaced.fee_constructor if sticker_to_be_replaced else None,
#                    proposal_initiated=proposal,
#                    fee_season=self.latest_applied_season,
#                )
#                new_sticker.sticker_to_replace = sticker_to_be_replaced
#                new_sticker.save()
#            return [], []  # Is this correct?
#
#        else:
#            # Calculate the stickers which are no longer needed.  Some stickers could be in the 'awaiting_printing'/'to_be_returned' status.
#            stickers_to_be_returned = [sticker for sticker in stickers_present if sticker not in stickers_required]
#
#            # Update sticker status
#            self._handle_stickers_to_be_removed(stickers_to_be_returned)
#
#            return [], stickers_to_be_returned

        if proposal.proposal_type.code == PROPOSAL_TYPE_NEW:
            # New sticker created with status Ready
            new_sticker = self._create_new_sticker_by_proposal(proposal)

            # Application goes to status Printing Sticker
            proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
            proposal.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
            proposal.save()

            return [], []

        elif proposal.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
            current_stickers = self._get_current_stickers()
            stickers_required = []  # Store all the stickers we want to keep
            new_sticker_created = False

            for vessel_ownership in self.vessel_ownership_list:
                # Look for the sticker for the vessel
                stickers = self.stickers.filter(
                    status__in=(
                        Sticker.STICKER_STATUS_CURRENT,
                        Sticker.STICKER_STATUS_AWAITING_PRINTING,
                        Sticker.STICKER_STATUS_TO_BE_RETURNED,),
                    vessel_ownership=vessel_ownership,
                )
                if stickers:
                    sticker = stickers.order_by('number').last()
                else:
                    # Sticker not found --> Create it
                    sticker = Sticker.objects.create(
                        approval=self,
                        vessel_ownership=proposal.vessel_ownership,
                        fee_constructor=proposal.fee_constructor,
                        proposal_initiated=proposal,
                        fee_season=self.latest_applied_season,
                    )
                    new_sticker_created = True
                stickers_required.append(sticker)

            # Calculate the stickers which are no longer needed.  There should be none always...?
            stickers_to_be_returned = [sticker for sticker in current_stickers if sticker not in stickers_required]

            # Update sticker status
            self._handle_stickers_to_be_removed(stickers_to_be_returned)

            if new_sticker_created:
                proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                proposal.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
            else:
                proposal.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                proposal.customer_status = Proposal.CUSTOMER_STATUS_APPROVED
            proposal.save()

            return [], stickers_to_be_returned

        elif proposal.proposal_type.code == PROPOSAL_TYPE_RENEWAL:
            stickers_required = []
            stickers_to_be_replaced = []

            for vessel_ownership in self.vessel_ownership_list:
                # Look for the sticker for the vessel
                existing_sticker = self.stickers.filter(
                    status__in=(
                        Sticker.STICKER_STATUS_CURRENT,
                        Sticker.STICKER_STATUS_AWAITING_PRINTING,
                        Sticker.STICKER_STATUS_TO_BE_RETURNED,),
                    vessel_ownership=vessel_ownership,
                )
                if existing_sticker:
                    existing_sticker = existing_sticker.first()
                    stickers_to_be_replaced.append(existing_sticker)

                # Sticker not found --> Create it
                new_sticker = Sticker.objects.create(
                    approval=self,
                    # vessel_ownership=proposal.vessel_ownership,
                    vessel_ownership=vessel_ownership,
                    fee_constructor=proposal.fee_constructor,
                    proposal_initiated=proposal,
                    fee_season=self.latest_applied_season,
                )
                stickers_required.append(new_sticker)

                if existing_sticker:
                    new_sticker.sticker_to_replace = existing_sticker
                    new_sticker.save()

            if len(stickers_required):
                proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                proposal.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
                proposal.save()

            return [], []  # Is this correct?

    def current_vessel_attributes(self, attribute=None, proposal=None):
        attribute_list = []
        vooas = self.vesselownershiponapproval_set.filter(
                Q(end_date__isnull=True) &
                Q(vessel_ownership__end_date__isnull=True)
                )
        for vooa in vooas:
            if not attribute:
                attribute_list.append(vooa.vessel_ownership)
            elif attribute == 'vessel_details':
                attribute_list.append(vooa.vessel_ownership.vessel.latest_vessel_details)
            elif attribute == 'vessel':
                attribute_list.append(vooa.vessel_ownership.vessel)
            #elif attribute == 'current_vessels':
            #    if not (vooa.vessel_ownership.vessel.rego_no == self.current_proposal.rego_no):
            #        attribute_list.append({
            #            "rego_no": vooa.vessel_ownership.vessel.rego_no,
            #            "latest_vessel_details": vooa.vessel_ownership.vessel.latest_vessel_details
            #            })
            elif attribute == 'current_vessels_for_licence_doc':
                attribute_list.append({
                    "rego_no": vooa.vessel_ownership.vessel.rego_no,
                    "latest_vessel_details": vooa.vessel_ownership.vessel.latest_vessel_details
                })
            #elif attribute == 'current_vessels_rego':
            #    #if not (vooa.vessel_ownership.vessel.rego_no == self.current_proposal.rego_no):
            #    if (vooa.vessel_ownership.vessel.rego_no != self.current_proposal.rego_no 
            #    or self.current_proposal.keep_existing_vessel
            #    or (proposal and proposal.processing_status in [
            #        'draft', 
            #        'with_assessor', 
            #        'with_assessor_requirements', 
            #        'with_approver', 
            #        'awaiting_endorsement', 
            #        'awaiting_documents', 
            #        'awaiting_payment'])
            #    ):
            #        attribute_list.append(vooa.vessel_ownership.vessel.rego_no)
        return attribute_list

    @property
    def vessel_list(self):
        return self.current_vessel_attributes('vessel')

    def get_most_recent_end_date(self):
        # This function returns None if no vessels have been sold
        # If even one vessel has been sold, this function returns the end_date even if there is a current vessel.
        proposal = self.proposal_set.latest('vessel_ownership__end_date')
        return proposal.vessel_ownership.end_date

    @property
    def vessel_list_for_payment(self):
        vessels = []
        for proposal in self.proposal_set.all():
            if (
                    proposal.final_status and
                    proposal.vessel_details and
                    not proposal.vessel_ownership.end_date  # and  # vessel has not been sold by this owner
                    # We don't worry about if existing vessel(s) is removed or not because regardless of it, payments made for that vessel.
                    # not proposal.vessel_ownership.mooring_licence_end_date  # vessel has been unchecked
            ):
                if proposal.vessel_details.vessel not in vessels:
                    vessels.append(proposal.vessel_details.vessel)
        return vessels

    # This function may not be used
    @property
    def vessel_details_list_for_payment(self):
        vessel_details = []
        for proposal in self.proposal_set.all():
            if (
                    proposal.final_status and
                    proposal.vessel_details not in vessel_details and
                    not proposal.vessel_ownership.end_date  # vessel has not been sold by this owner
                    # We don't worry about if existing vessel(s) is removed or not because regardless of it, payments made for that vessel.
            ):
                vessel_details.append(proposal.vessel_details)
        return vessel_details

    @property
    def vessel_details_list(self):
        return self.current_vessel_attributes('vessel_details')

    @property
    def vessel_ownership_list(self):
        return self.current_vessel_attributes()

    #@property
    #def current_vessels(self):
    #    return self.current_vessel_attributes('current_vessels')

    def get_current_vessels_for_licence_doc(self):
        return self.current_vessel_attributes('current_vessels_for_licence_doc')

    ##@property
    #def current_vessels_rego(self, proposal=None):
    #    return self.current_vessel_attributes('current_vessels_rego', proposal)


class PreviewTempApproval(Approval):
    class Meta:
        app_label = 'mooringlicensing'


class ApprovalLogEntry(CommunicationsLogEntry):
    approval = models.ForeignKey(Approval, related_name='comms_logs')

    class Meta:
        app_label = 'mooringlicensing'

    def save(self, **kwargs):
        # save the application reference if the reference not provided
        if not self.reference:
            self.reference = self.approval.id
        super(ApprovalLogEntry, self).save(**kwargs)

class ApprovalLogDocument(Document):
    log_entry = models.ForeignKey('ApprovalLogEntry',related_name='documents', null=True,)
    _file = models.FileField(upload_to=update_approval_comms_log_filename, null=True, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'

class ApprovalUserAction(UserAction):
    ACTION_CREATE_APPROVAL = "Create approval {}"
    ACTION_UPDATE_APPROVAL = "Create approval {}"
    ACTION_EXPIRE_APPROVAL = "Expire approval {}"
    ACTION_CANCEL_APPROVAL = "Cancel approval {}"
    ACTION_EXTEND_APPROVAL = "Extend approval {}"
    ACTION_SUSPEND_APPROVAL = "Suspend approval {}"
    ACTION_REINSTATE_APPROVAL = "Reinstate approval {}"
    ACTION_SURRENDER_APPROVAL = "Surrender approval {}"
    ACTION_RENEW_APPROVAL = "Create renewal Application for approval {}"
    ACTION_AMEND_APPROVAL = "Create amendment Application for approval {}"
    ACTION_REISSUE_APPROVAL = "Reissue approval {}"
    ACTION_REISSUE_APPROVAL_ML = "Reissued due to change in Mooring Licence {}"
    ACTION_RENEWAL_NOTICE_SENT_FOR_APPROVAL = "Renewal notice sent for approval {}"

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ('-when',)

    @classmethod
    def log_action(cls, approval, action, user=None):
        return cls.objects.create(
            approval=approval,
            who=user,
            what=str(action)
        )

    who = models.ForeignKey(EmailUser, null=True, blank=True)
    when = models.DateTimeField(null=False, blank=False, auto_now_add=True)
    what = models.TextField(blank=False)
    approval= models.ForeignKey(Approval, related_name='action_logs')


class DcvOrganisation(RevisionedMixin):
    name = models.CharField(max_length=128, null=True, blank=True)
    abn = models.CharField(max_length=50, null=True, blank=True, verbose_name='ABN', unique=True)

    def __str__(self):
        return self.name

    class Meta:
        app_label = 'mooringlicensing'


class DcvVessel(RevisionedMixin):
    rego_no = models.CharField(max_length=200, unique=True, blank=True, null=True)
    vessel_name = models.CharField(max_length=400, blank=True)
    dcv_organisation = models.ForeignKey(DcvOrganisation, blank=True, null=True)

    def __str__(self):
        return self.rego_no

    class Meta:
        app_label = 'mooringlicensing'


class DcvAdmission(RevisionedMixin):
    LODGEMENT_NUMBER_PREFIX = 'DCV'

    submitter = models.ForeignKey(EmailUser, blank=True, null=True, related_name='dcv_admissions')
    lodgement_number = models.CharField(max_length=10, blank=True, unique=True)
    lodgement_datetime = models.DateTimeField(blank=True, null=True)  # This is the datetime when payment
    skipper = models.CharField(max_length=50, blank=True, null=True)
    contact_number = models.CharField(max_length=50, blank=True, null=True)
    dcv_vessel = models.ForeignKey(DcvVessel, blank=True, null=True, related_name='dcv_admissions')

    class Meta:
        app_label = 'mooringlicensing'

    def __str__(self):
        return self.lodgement_number

    @property
    def fee_paid(self):
        if self.invoice and self.invoice.payment_status in ['paid', 'over_paid']:
            return True
        return False

    @property
    def invoice(self):
        invoice = None
        for dcv_admission_fee in self.dcv_admission_fees.all():
            if dcv_admission_fee.fee_items.count():
                invoice = Invoice.objects.get(reference=dcv_admission_fee.invoice_reference)
        return invoice

        # if self.dcv_admission_fees.count() < 1:
        #     return None
        # elif self.dcv_admission_fees.count() == 1:
        #     dcv_admission_fee = self.dcv_admission_fees.first()
        #     try:
        #         invoice = Invoice.objects.get(reference=dcv_admission_fee.invoice_reference)
        #     except:
        #         invoice = None
        #     return invoice
        # else:
        #     msg = 'DcvAdmission: {} has {} DcvAdmissionFees.  There should be 0 or 1.'.format(self, self.dcv_admission_fees.count())
        #     logger.error(msg)
        #     raise ValidationError(msg)

    @classmethod
    def get_next_id(cls):
        ids = map(int, [i.split(cls.LODGEMENT_NUMBER_PREFIX)[1] for i in cls.objects.all().values_list('lodgement_number', flat=True) if i])
        ids = list(ids)
        return max(ids) + 1 if len(ids) else 1

    def save(self, **kwargs):
        if self.lodgement_number in ['', None]:
            self.lodgement_number = self.LODGEMENT_NUMBER_PREFIX + '{0:06d}'.format(self.get_next_id())
        super(DcvAdmission, self).save(**kwargs)

    def generate_dcv_admission_doc(self):
        for arrival in self.dcv_admission_arrivals.all():
            # Document is created per arrival
            permit_document = create_dcv_admission_document(arrival)

    def get_summary(self):
        summary = []
        for arrival in self.dcv_admission_arrivals.all():
            summary.append(arrival.get_summary())
        return summary

    def get_admission_urls(self):
        urls = []
        for admission in self.admissions.all():
            urls.append(admission._file.url)
        return urls


class DcvAdmissionArrival(RevisionedMixin):
    dcv_admission = models.ForeignKey(DcvAdmission, null=True, blank=True, related_name='dcv_admission_arrivals')
    arrival_date = models.DateField(null=True, blank=True)
    departure_date = models.DateField(null=True, blank=True)
    private_visit = models.BooleanField(default=False)
    fee_season = models.ForeignKey('FeeSeason', null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)  # This is the season.start_date when payment
    end_date = models.DateField(null=True, blank=True)  # This is the season.end_date when payment
    fee_constructor = models.ForeignKey('FeeConstructor', on_delete=models.PROTECT, blank=True, null=True, related_name='dcv_admission_arrivals')

    class Meta:
        app_label = 'mooringlicensing'

    def get_context_for_licence_permit(self):
        today = timezone.localtime(timezone.now()).date()
        context = {
            'lodgement_number': self.dcv_admission.lodgement_number,
            'organisation_name': self.dcv_admission.dcv_vessel.dcv_organisation.name if self.dcv_admission.dcv_vessel.dcv_organisation else '',
            'organisation_abn': self.dcv_admission.dcv_vessel.dcv_organisation.abn if self.dcv_admission.dcv_vessel.dcv_organisation else '',
            'issue_date': today.strftime('%d/%m/%Y'),
            'vessel_rego_no': self.dcv_admission.dcv_vessel.rego_no,
            'vessel_name': self.dcv_admission.dcv_vessel.vessel_name,
            'arrival': self.get_summary(),
            'public_url': get_public_url(),
            'date_registered': self.dcv_admission.lodgement_datetime.strftime('%d/%m/%Y'),
        }
        return context

    def __str__(self):
        return '{} ({}-{})'.format(self.dcv_admission, self.arrival_date, self.departure_date)

    def get_summary(self):
        summary_dict = {'arrival_date': self.arrival_date.strftime('%d/%m/%Y') if self.arrival_date else '', 'departure_date': self.departure_date.strftime('%d/%m/%Y') if self.departure_date else ''}
        for age_group_choice in AgeGroup.NAME_CHOICES:
            age_group = AgeGroup.objects.get(code=age_group_choice[0])
            dict_type = {}
            for admission_type_choice in AdmissionType.TYPE_CHOICES:
                admission_type = AdmissionType.objects.get(code=admission_type_choice[0])
                num_of_people = self.numberofpeople_set.get(age_group=age_group, admission_type=admission_type)
                dict_type[admission_type_choice[0]] = num_of_people.number
            summary_dict[age_group_choice[0]] = dict_type
        return summary_dict


class AgeGroup(models.Model):
    AGE_GROUP_ADULT = 'adult'
    AGE_GROUP_CHILD = 'child'

    NAME_CHOICES = (
        (AGE_GROUP_ADULT, 'Adult'),
        (AGE_GROUP_CHILD, 'Child'),
    )
    code = models.CharField(max_length=40, choices=NAME_CHOICES, default=NAME_CHOICES[0][0])

    def __str__(self):
        for item in self.NAME_CHOICES:
            if self.code == item[0]:
                return item[1]
        return ''

    class Meta:
        app_label = 'mooringlicensing'


class AdmissionType(models.Model):
    ADMISSION_TYPE_LANDING = 'landing'
    ADMISSION_TYPE_EXTENDED_STAY = 'extended_stay'
    ADMISSION_TYPE_NOT_LANDING = 'not_landing'
    ADMISSION_TYPE_APPROVED_EVENTS = 'approved_events'

    TYPE_CHOICES = (
        (ADMISSION_TYPE_LANDING, 'Landing'),
        (ADMISSION_TYPE_EXTENDED_STAY, 'Extended stay'),
        (ADMISSION_TYPE_NOT_LANDING, 'Not landing'),
        (ADMISSION_TYPE_APPROVED_EVENTS, 'Approved events'),
    )
    code = models.CharField(max_length=40, choices=TYPE_CHOICES, default=TYPE_CHOICES[0][0])

    def __str__(self):
        for item in self.TYPE_CHOICES:
            if self.code == item[0]:
                return item[1]
        return ''

    class Meta:
        app_label = 'mooringlicensing'


class NumberOfPeople(RevisionedMixin):
    number = models.PositiveSmallIntegerField(null=True, blank=True, default=0)
    dcv_admission_arrival = models.ForeignKey(DcvAdmissionArrival, null=True, blank=True)
    age_group = models.ForeignKey(AgeGroup, null=True, blank=True)
    admission_type = models.ForeignKey(AdmissionType, null=True, blank=True)

    class Meta:
        app_label = 'mooringlicensing'

    def __str__(self):
        return '{} ({}, {}, {})'.format(self.number, self.dcv_admission_arrival, self.age_group, self.admission_type)


class DcvPermit(RevisionedMixin):
    description = 'DCV Permit'

    DCV_PERMIT_STATUS_CURRENT = 'current'
    DCV_PERMIT_STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = (
        (DCV_PERMIT_STATUS_CURRENT, 'Current'),
        (DCV_PERMIT_STATUS_EXPIRED, 'Expired'),
    )
    LODGEMENT_NUMBER_PREFIX = 'DCVP'

    submitter = models.ForeignKey(EmailUser, blank=True, null=True, related_name='dcv_permits')
    lodgement_number = models.CharField(max_length=10, blank=True, unique=True)
    lodgement_datetime = models.DateTimeField(blank=True, null=True)  # This is the datetime when payment
    fee_season = models.ForeignKey('FeeSeason', null=True, blank=True, related_name='dcv_permits')
    start_date = models.DateField(null=True, blank=True)  # This is the season.start_date when payment
    end_date = models.DateField(null=True, blank=True)  # This is the season.end_date when payment
    dcv_vessel = models.ForeignKey(DcvVessel, blank=True, null=True, related_name='dcv_permits')
    dcv_organisation = models.ForeignKey(DcvOrganisation, blank=True, null=True)
    renewal_sent = models.BooleanField(default=False)
    migrated = models.BooleanField(default=False)

    @property
    def postal_address_line1(self):
        ret_value = ''
        if self.submitter:
            if self.submitter.postal_same_as_residential:
                ret_value = self.submitter.residential_address.line1
            else:
                if self.submitter.postal_address:
                    ret_value = self.submitter.postal_address.line1
            if not ret_value:
                # Shouldn't reach here, but if so, just return residential address
                ret_value = self.submitter.residential_address.line1
        return ret_value

    @property
    def postal_address_line2(self):
        ret_value = ''
        if self.submitter:
            if self.submitter.postal_same_as_residential:
                ret_value = self.submitter.residential_address.line2
            else:
                if self.submitter.postal_address:
                    ret_value = self.submitter.postal_address.line2
            if not ret_value:
                # Shouldn't reach here, but if so, just return residential address
                ret_value = self.submitter.residential_address.line2
        return ret_value

    @property
    def postal_address_state(self):
        ret_value = ''
        if self.submitter:
            if self.submitter.postal_same_as_residential:
                ret_value = self.submitter.residential_address.state
            else:
                if self.submitter.postal_address:
                    ret_value = self.submitter.postal_address.state
            if not ret_value:
                # Shouldn't reach here, but if so, just return residential address
                ret_value = self.submitter.residential_address.state
        return ret_value

    @property
    def postal_address_suburb(self):
        ret_value = ''
        if self.submitter:
            if self.submitter.postal_same_as_residential:
                ret_value = self.submitter.residential_address.locality
            else:
                if self.submitter.postal_address:
                    ret_value = self.submitter.postal_address.locality
            if not ret_value:
                # Shouldn't reach here, but if so, just return residential address
                ret_value = self.submitter.residential_address.locality
        return ret_value

    @property
    def postal_address_postcode(self):
        ret_value = ''
        if self.submitter:
            if self.submitter.postal_same_as_residential:
                ret_value = self.submitter.residential_address.postcode
            else:
                if self.submitter.postal_address:
                    ret_value = self.submitter.postal_address.postcode
            if not ret_value:
                # Shouldn't reach here, but if so, just return residential address
                ret_value = self.submitter.residential_address.postcode
        return ret_value

    def get_context_for_licence_permit(self):
        context = {
            'lodgement_number': self.lodgement_number,
            'organisation_name': self.dcv_organisation.name if self.dcv_organisation else '',
            'organisation_abn': self.dcv_organisation.abn if self.dcv_organisation else '',
            'issue_date': self.lodgement_datetime.strftime('%d/%m/%Y'),
            'p_address_line1': self.postal_address_line1,
            'p_address_line2': self.postal_address_line2,
            'p_address_suburb': self.postal_address_suburb,
            'p_address_state': self.postal_address_state,
            'p_address_postcode': self.postal_address_postcode,
            'vessel_rego_no': self.dcv_vessel.rego_no,
            'vessel_name': self.dcv_vessel.vessel_name,
            'expiry_date': self.end_date.strftime('%d/%m/%Y'),
            'public_url': get_public_url(),
        }
        return context

    def get_licence_document_as_attachment(self):
        attachment = None
        if self.permits.count():
            licence_document = self.permits.first()._file
            if licence_document is not None:
                file_name = self.licence_document.name
                attachment = (file_name, licence_document.file.read(), 'application/pdf')
        return attachment

    def get_target_date(self, applied_date):
        return applied_date

    @property
    def expiry_date(self):
        return self.expiry_date

    @property
    def fee_paid(self):
        if self.invoice and self.invoice.payment_status in ['paid', 'over_paid']:
            return True
        return False

    @property
    def invoice(self):
        invoice = None
        for dcv_permit_fee in self.dcv_permit_fees.all():
            if dcv_permit_fee.fee_items.count():
                invoice = Invoice.objects.get(reference=dcv_permit_fee.invoice_reference)
        return invoice

        # if self.dcv_permit_fees.count() < 1:
        #     return None
        # elif self.dcv_permit_fees.count() == 1:
        #     dcv_permit_fee = self.dcv_permit_fees.first()
        #     try:
        #         invoice = Invoice.objects.get(reference=dcv_permit_fee.invoice_reference)
        #         return invoice
        #     except:
        #         return None
        # else:
        #     msg = 'DcvPermit: {} has {} DcvPermitFees.  There should be 0 or 1.'.format(self, self.dcv_permit_fees.count())
        #     logger.error(msg)
        #     raise ValidationError(msg)

    @classmethod
    def get_next_id(cls):
        ids = map(int, [i.split(cls.LODGEMENT_NUMBER_PREFIX)[1] for i in cls.objects.all().values_list('lodgement_number', flat=True) if i])
        ids = list(ids)
        return max(ids) + 1 if len(ids) else 1

    @property
    def status(self, target_date=datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()):
        if self.start_date:
            if self.start_date <= target_date <= self.end_date:
                return self.STATUS_CHOICES[0]
            else:
                return self.STATUS_CHOICES[1]
        else:
            return None

    def save(self, **kwargs):
        if self.lodgement_number in ['', None]:
            self.lodgement_number = self.LODGEMENT_NUMBER_PREFIX + '{0:06d}'.format(self.get_next_id())
        super(DcvPermit, self).save(**kwargs)

    def generate_dcv_permit_doc(self):
        permit_document = create_dcv_permit_document(self)

    def get_fee_amount_adjusted(self, fee_item, vessel_length):
        # Adjust fee amount if needed
        # return fee_item.amount
        return fee_item.get_absolute_amount(vessel_length)

    class Meta:
        app_label = 'mooringlicensing'

    def __str__(self):
        return f'{self.lodgement_number} (M)' if self.migrated else f'{self.lodgement_number}'

def update_dcv_admission_doc_filename(instance, filename):
    return '{}/dcv_admissions/{}/admissions/{}'.format(settings.MEDIA_APP_DIR, instance.id, filename)


def update_dcv_permit_doc_filename(instance, filename):
    return '{}/dcv_permits/{}/permits/{}'.format(settings.MEDIA_APP_DIR, instance.id, filename)


class DcvAdmissionDocument(Document):
    dcv_admission = models.ForeignKey(DcvAdmission, related_name='admissions')
    _file = models.FileField(upload_to=update_dcv_admission_doc_filename, max_length=512)
    can_delete = models.BooleanField(default=False)  # after initial submit prevent document from being deleted

    def delete(self, using=None, keep_parents=False):
        if self.can_delete:
            return super(DcvAdmissionDocument, self).delete(using, keep_parents)
        logger.info('Cannot delete existing document object after Application has been submitted : {}'.format(self.name))

    class Meta:
        app_label = 'mooringlicensing'


class DcvPermitDocument(Document):
    dcv_permit = models.ForeignKey(DcvPermit, related_name='permits')
    _file = models.FileField(upload_to=update_dcv_permit_doc_filename, max_length=512)
    can_delete = models.BooleanField(default=False)  # after initial submit prevent document from being deleted

    def delete(self, using=None, keep_parents=False):
        if self.can_delete:
            return super(DcvPermitDocument, self).delete(using, keep_parents)
        logger.info('Cannot delete existing document object after Application has been submitted : {}'.format(self.name))

    class Meta:
        app_label = 'mooringlicensing'


class Sticker(models.Model):
    STICKER_STATUS_READY = 'ready'
    STICKER_STATUS_NOT_READY_YET = 'not_ready_yet'
    STICKER_STATUS_AWAITING_PRINTING = 'awaiting_printing'
    STICKER_STATUS_CURRENT = 'current'
    STICKER_STATUS_TO_BE_RETURNED = 'to_be_returned'
    STICKER_STATUS_RETURNED = 'returned'
    STICKER_STATUS_LOST = 'lost'
    STICKER_STATUS_EXPIRED = 'expired'
    STICKER_STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STICKER_STATUS_READY, 'Ready'),
        (STICKER_STATUS_NOT_READY_YET, 'Not Ready Yet'),
        (STICKER_STATUS_AWAITING_PRINTING, 'Awaiting Printing'),
        (STICKER_STATUS_CURRENT, 'Current'),
        (STICKER_STATUS_TO_BE_RETURNED, 'To be Returned'),
        (STICKER_STATUS_RETURNED, 'Returned'),
        (STICKER_STATUS_LOST, 'Lost'),
        (STICKER_STATUS_EXPIRED, 'Expired'),
        (STICKER_STATUS_CANCELLED, 'Cancelled')
    )
    EXPOSED_STATUS = (
        STICKER_STATUS_AWAITING_PRINTING,
        STICKER_STATUS_CURRENT,
        STICKER_STATUS_TO_BE_RETURNED,
        STICKER_STATUS_RETURNED,
        STICKER_STATUS_LOST,
        STICKER_STATUS_EXPIRED,
    )
    STATUSES_FOR_FILTER = (
        STICKER_STATUS_AWAITING_PRINTING,
        STICKER_STATUS_CURRENT,
        STICKER_STATUS_TO_BE_RETURNED,
        STICKER_STATUS_RETURNED,
        STICKER_STATUS_LOST,
        STICKER_STATUS_EXPIRED,
        STICKER_STATUS_CANCELLED,
    )

    colour_default = 'green'
    colour_matrix = [
        {'length': 10, 'colour': 'green'},
        {'length': 12, 'colour': 'grey'},
        {'length': 14, 'colour': 'purple'},
        {'length': 16, 'colour': 'blue'},
        {'length': 1000, 'colour': 'white'},  # This is returned whenever any of the previous doesn't fit the requirement.
    ]
    number = models.CharField(max_length=9, blank=True, default='', unique=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0])
    sticker_printing_batch = models.ForeignKey(StickerPrintingBatch, blank=True, null=True)  # When None, most probably 'awaiting_
    sticker_printing_response = models.ForeignKey(StickerPrintingResponse, blank=True, null=True)
    approval = models.ForeignKey(Approval, blank=True, null=True, related_name='stickers')  # Sticker links to either approval or dcv_permit, never to both.
    dcv_permit = models.ForeignKey(DcvPermit, blank=True, null=True, related_name='stickers')
    printing_date = models.DateField(blank=True, null=True)  # The day this sticker printed
    mailing_date = models.DateField(blank=True, null=True)  # The day this sticker sent
    fee_constructor = models.ForeignKey('FeeConstructor', blank=True, null=True)
    fee_season = models.ForeignKey('FeeSeason', blank=True, null=True)
    vessel_ownership = models.ForeignKey('VesselOwnership', blank=True, null=True)
    proposal_initiated = models.ForeignKey('Proposal', blank=True, null=True)  # This propposal created this sticker object.  Can be None when sticker created by RequestNewSticker action or so.
    sticker_to_replace = models.ForeignKey('self', null=True, blank=True)  # This sticker object replaces the sticker_to_replace for renewal

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ['-number']

    def get_invoices(self):
        invoices = []
        for action_detail in self.sticker_action_details.all():
            if action_detail.sticker_action_fee and action_detail.sticker_action_fee.invoice_reference:
                inv = Invoice.objects.get(reference=action_detail.sticker_action_fee.invoice_reference)
                invoices.append(inv)
        return invoices

    def get_moorings(self):
        moorings = []

        if self.approval.code == AnnualAdmissionPermit.code:
            # No associated moorings
            pass
        elif self.approval.code == AuthorisedUserPermit.code:
            valid_moas = self.mooringonapproval_set.filter(Q(end_date__isnull=True))
            for moa in valid_moas:
                moorings.append(moa.mooring)
        elif self.approval.code == MooringLicence.code:
            if hasattr(self.approval.child_obj, 'mooring'):
                moorings.append(self.approval.child_obj.mooring)
            else:
                logger.error(
                    'Failed to retrieve the mooring for the sticker {} because the associated MooringLicence {} does not have a mooring'.format(
                        self.number, self.approval.lodgement_number))

        return moorings

    def __str__(self):
        return '{} ({})'.format(self.number, self.status)

    def record_lost(self):
        self.status = Sticker.STICKER_STATUS_LOST
        self.save()
        self.update_other_stickers()

    def record_returned(self):
        self.status = Sticker.STICKER_STATUS_RETURNED
        self.save()
        self.update_other_stickers()

    def update_other_stickers(self):
        stickers_not_ready_yet = self.approval.stickers.filter(status=Sticker.STICKER_STATUS_NOT_READY_YET)
        stickers_to_be_returned = self.approval.stickers.filter(status=Sticker.STICKER_STATUS_TO_BE_RETURNED)
        proposals_initiated = []
        if not stickers_to_be_returned.count():
            # If there are no stickers with 'To be returned', change 'Not ready yet' stickers to 'Ready' so that it is picked up for exporting.
            for sticker in stickers_not_ready_yet:
                sticker.status = Sticker.STICKER_STATUS_READY
                sticker.save()
                if sticker.proposal_initiated and sticker.proposal_initiated not in proposals_initiated:
                    proposals_initiated.append(sticker.proposal_initiated)
        for proposal in proposals_initiated:
            if proposal.processing_status == Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED:
                stickers_to_be_returned = Sticker.objects.filter(status=Sticker.STICKER_STATUS_TO_BE_RETURNED, proposal_initiated=proposal)
                if not stickers_to_be_returned:
                    # If proposal is in 'Sticker to be Returned' status and there are no stickers with 'To be returned' status,
                    # this proposal should get the status 'Printing Sticker'
                    proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                    proposal.customer_status = Proposal.CUSTOMER_STATUS_PRINTING_STICKER
                    proposal.save()

    def request_replacement(self, new_status):
        self.status = new_status
        self.save()

        # Create replacement sticker
        new_sticker = Sticker.objects.create(
            approval=self.approval,
            vessel_ownership=self.vessel_ownership,
            fee_constructor=self.fee_constructor,
            fee_season=self.approval.latest_applied_season,
        )

        return new_sticker

    def get_sticker_colour(self):
        colour = self.approval.child_obj.sticker_colour
        colour += '/' + self.get_vessel_size_colour()
        return colour

    def get_white_info(self):
        white_info = ''
        colour = self.get_sticker_colour()
        if colour in [AuthorisedUserPermit.sticker_colour + '/white', MooringLicence.sticker_colour + '/white',]:
            if self.vessel_applicable_length > 26:
                white_info = self.vessel_applicable_length
            elif self.vessel_applicable_length > 24:
                white_info = 26
            elif self.vessel_applicable_length > 22:
                white_info = 24
            elif self.vessel_applicable_length > 20:
                white_info = 22
            elif self.vessel_applicable_length > 18:
                white_info = 20
            elif self.vessel_applicable_length > 16:
                white_info = 18
        return white_info

    def get_vessel_size_colour(self):
        last_item = None
        for item in self.colour_matrix:
            last_item = item
            if self.vessel_applicable_length <= item['length']:
                return item['colour']
        return last_item['colour']  # This returns the last item when reached

    @property
    def next_number(self):
        min_dcv_sticker_number = GlobalSettings.objects.get(key=GlobalSettings.KEY_MINUMUM_STICKER_NUMBER_FOR_DCV_PERMIT).value
        min_dcv_sticker_number = int(min_dcv_sticker_number)
        try:
            ids = [int(i) for i in Sticker.objects.all().values_list('number', flat=True) if i and int(i) < min_dcv_sticker_number]
            return max(ids) + 1 if ids else 1
        except Exception as e:
            print(e)

    def save(self, *args, **kwargs):
        super(Sticker, self).save(*args, **kwargs)
        if self.number == '':
            self.number = '{0:07d}'.format(self.next_number)
            self.save()

    @property
    def first_name(self):
        if self.approval and self.approval.submitter:
            return self.approval.submitter.first_name
        return '---'

    @property
    def last_name(self):
        if self.approval and self.approval.submitter:
            return self.approval.submitter.last_name
        return '---'

    @property
    def postal_address_line1(self):
        if self.approval and self.approval.submitter and self.approval.submitter.postal_address:
            return self.approval.submitter.postal_address.line1
        return '---'

    @property
    def postal_address_line2(self):
        if self.approval and self.approval.submitter and self.approval.submitter.postal_address:
            return self.approval.submitter.postal_address.line2
        return '---'

    @property
    def postal_address_state(self):
        if self.approval and self.approval.submitter and self.approval.submitter.postal_address:
            return self.approval.submitter.postal_address.state
        return '---'

    @property
    def postal_address_suburb(self):
        if self.approval and self.approval.submitter and self.approval.submitter.postal_address:
            return self.approval.submitter.postal_address.locality
        return '---'

    @property
    def vessel_registration_number(self):
        if self.vessel_ownership and self.vessel_ownership.vessel:
            return self.vessel_ownership.vessel.rego_no
        return '---'

    @property
    def vessel_applicable_length(self):
        if self.vessel_ownership and self.vessel_ownership.vessel and self.vessel_ownership.vessel.latest_vessel_details:
            return self.vessel_ownership.vessel.latest_vessel_details.vessel_applicable_length
        raise ValueError('Vessel size not found for the sticker: {}'.format(self))

    @property
    def postal_address_postcode(self):
        if self.approval and self.approval.submitter and self.approval.submitter.postal_address:
            return self.approval.submitter.postal_address.postcode
        return '---'


class StickerActionDetail(models.Model):
    sticker = models.ForeignKey(Sticker, blank=True, null=True, related_name='sticker_action_details')
    reason = models.TextField(blank=True)
    date_created = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    date_updated = models.DateTimeField(blank=True, null=True, auto_now=True)
    date_of_lost_sticker = models.DateField(blank=True, null=True)
    date_of_returned_sticker = models.DateField(blank=True, null=True)
    action = models.CharField(max_length=50, null=True, blank=True)
    user = models.ForeignKey(EmailUser, null=True, blank=True)
    sticker_action_fee = models.ForeignKey(StickerActionFee, null=True, blank=True, related_name='sticker_action_details')

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ['-date_created']


@receiver(pre_delete, sender=Approval)
def delete_documents(sender, instance, *args, **kwargs):
    if hasattr(instance, 'documents'):
        for document in instance.documents.all():
            try:
                document.delete()
            except:
                pass


import reversion
reversion.register(WaitingListOfferDocument, follow=[])
reversion.register(RenewalDocument, follow=['renewal_document'])
reversion.register(AuthorisedUserSummaryDocument, follow=['approvals'])
reversion.register(ApprovalDocument, follow=['approvalhistory_set', 'licence_document', 'cover_letter_document'])
reversion.register(MooringOnApproval, follow=['approval', 'mooring', 'sticker'])
reversion.register(VesselOwnershipOnApproval, follow=['approval', 'vessel_ownership'])
reversion.register(ApprovalHistory, follow=[])
#reversion.register(Approval, follow=['proposal_set', 'ria_generated_proposal', 'waiting_list_offer_documents', 'renewal_documents', 'authorised_user_summary_documents', 'documents', 'mooringonapproval_set', 'vesselownershiponapproval_set', 'approvalhistory_set', 'replace', 'comms_logs', 'action_logs', 'stickers', 'compliances'])
reversion.register(Approval)
reversion.register(WaitingListAllocation, follow=['proposal_set', 'ria_generated_proposal', 'waiting_list_offer_documents', 'renewal_documents', 'authorised_user_summary_documents', 'documents', 'mooringonapproval_set', 'vesselownershiponapproval_set', 'approvalhistory_set', 'replace', 'comms_logs', 'action_logs', 'stickers', 'compliances'])
reversion.register(AnnualAdmissionPermit, follow=['proposal_set', 'waiting_list_offer_documents', 'renewal_documents', 'authorised_user_summary_documents', 'documents', 'mooringonapproval_set', 'vesselownershiponapproval_set', 'approvalhistory_set', 'replace', 'comms_logs', 'action_logs', 'stickers', 'compliances'])
reversion.register(AuthorisedUserPermit, follow=['proposal_set', 'waiting_list_offer_documents', 'renewal_documents', 'authorised_user_summary_documents', 'documents', 'mooringonapproval_set', 'vesselownershiponapproval_set', 'approvalhistory_set', 'replace', 'comms_logs', 'action_logs', 'stickers', 'compliances'])
reversion.register(MooringLicence, follow=['proposal_set', 'waiting_list_offer_documents', 'renewal_documents', 'authorised_user_summary_documents', 'documents', 'mooringonapproval_set', 'vesselownershiponapproval_set', 'approvalhistory_set', 'replace', 'comms_logs', 'action_logs', 'stickers', 'compliances', 'mooring'])
reversion.register(PreviewTempApproval, follow=['proposal_set', 'waiting_list_offer_documents', 'renewal_documents', 'authorised_user_summary_documents', 'documents', 'mooringonapproval_set', 'vesselownershiponapproval_set', 'approvalhistory_set', 'replace', 'comms_logs', 'action_logs', 'stickers', 'compliances'])
reversion.register(ApprovalLogEntry, follow=['documents'])
reversion.register(ApprovalLogDocument, follow=[])
reversion.register(ApprovalUserAction, follow=[])
reversion.register(DcvOrganisation, follow=['dcvvessel_set', 'dcvpermit_set'])
reversion.register(DcvVessel, follow=['dcv_admissions', 'dcv_permits'])
reversion.register(DcvAdmission, follow=['dcv_admission_arrivals', 'admissions'])
reversion.register(DcvAdmissionArrival, follow=['numberofpeople_set'])
reversion.register(AgeGroup, follow=['numberofpeople_set'])
reversion.register(AdmissionType, follow=['numberofpeople_set'])
reversion.register(NumberOfPeople, follow=[])
reversion.register(DcvPermit, follow=['permits', 'stickers'])
reversion.register(DcvAdmissionDocument, follow=[])
reversion.register(DcvPermitDocument, follow=[])
reversion.register(Sticker, follow=['mooringonapproval_set', 'approvalhistory_set', 'sticker_action_details'])
reversion.register(StickerActionDetail, follow=[])
