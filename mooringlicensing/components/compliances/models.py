
from __future__ import unicode_literals

from django.db import models,transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from mooringlicensing.helpers import is_internal
from mooringlicensing.components.main.models import (
    CommunicationsLogEntry,
    UserAction,
    Document, RevisionedMixin, SanitiseMixin
)
from django.core.files.storage import FileSystemStorage
from mooringlicensing.components.proposals.models import ProposalRequirement
from mooringlicensing.components.compliances.email import (
                        send_compliance_accept_email_notification,
                        send_amendment_email_notification,
                        send_reminder_email_notification,
                        send_external_submit_email_notification,
                        send_submit_email_notification,
                        send_internal_reminder_email_notification,
                        send_due_email_notification,
                        send_internal_due_email_notification
                        )

private_storage = FileSystemStorage(  # We want to store files in secure place (outside of the media folder)
    location=settings.PRIVATE_MEDIA_STORAGE_LOCATION,
    base_url=settings.PRIVATE_MEDIA_BASE_URL,
)

import logging

from mooringlicensing.ledger_api_utils import retrieve_email_userro

logger = logging.getLogger(__name__)


class Compliance(RevisionedMixin):
    PROCESSING_STATUS_DUE = 'due'
    PROCESSING_STATUS_OVERDUE = 'overdue'
    PROCESSING_STATUS_FUTURE = 'future'
    PROCESSING_STATUS_WITH_ASSESSOR = 'with_assessor'
    PROCESSING_STATUS_APPROVED = 'approved'
    PROCESSING_STATUS_DISCARDED = 'discarded'
    PROCESSING_STATUS_CHOICES = ((PROCESSING_STATUS_DUE, 'Due'),
                                 (PROCESSING_STATUS_OVERDUE, 'Overdue'),
                                 (PROCESSING_STATUS_FUTURE, 'Future'),
                                 (PROCESSING_STATUS_WITH_ASSESSOR, 'With Assessor'),
                                 (PROCESSING_STATUS_APPROVED, 'Approved'),
                                 (PROCESSING_STATUS_DISCARDED, 'Discarded'),
                                 )

    CUSTOMER_STATUS_DUE = 'due'
    CUSTOMER_STATUS_OVERDUE = 'overdue'
    CUSTOMER_STATUS_FUTURE = 'future'
    CUSTOMER_STATUS_WITH_ASSESSOR = 'with_assessor'
    CUSTOMER_STATUS_APPROVED = 'approved'
    CUSTOMER_STATUS_DISCARDED = 'discarded'
    CUSTOMER_STATUS_CHOICES = ((CUSTOMER_STATUS_DUE, 'Due'),
                               (CUSTOMER_STATUS_OVERDUE, 'Overdue'),
                               (CUSTOMER_STATUS_FUTURE, 'Future'),
                               (CUSTOMER_STATUS_WITH_ASSESSOR, 'Under Review'),
                               (CUSTOMER_STATUS_APPROVED, 'Approved'),
                               (CUSTOMER_STATUS_DISCARDED, 'Discarded'),
                               )

    lodgement_number = models.CharField(max_length=9, blank=True, default='')
    proposal = models.ForeignKey('mooringlicensing.Proposal', related_name='compliances', on_delete=models.CASCADE)
    approval = models.ForeignKey('mooringlicensing.Approval', related_name='compliances', on_delete=models.CASCADE)
    due_date = models.DateField()
    text = models.TextField(blank=True)

    processing_status = models.CharField(choices=PROCESSING_STATUS_CHOICES,max_length=20)
    customer_status = models.CharField(choices=CUSTOMER_STATUS_CHOICES,max_length=20)
    assigned_to = models.IntegerField( null=True, blank=True)
    requirement = models.ForeignKey(ProposalRequirement, blank=True, null=True, related_name='compliance_requirement', on_delete=models.SET_NULL)
    lodgement_date = models.DateTimeField(blank=True, null=True)
    submitter = models.IntegerField(blank=True, null=True)
    post_reminder_sent = models.BooleanField(default=False)
    due_reminder_count = models.PositiveSmallIntegerField('Number of times a due reminder has been sent', default=0)

    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)

    class Meta:
        app_label = 'mooringlicensing'

    @property
    def submitter_obj(self):
        return retrieve_email_userro(self.submitter) if self.submitter else None
    
    @property
    def holder_id(self):
        if self.proposal and self.proposal.proposal_applicant:
            return self.proposal.proposal_applicant.email_user_id
        else:
            return None

    @property
    def holder_obj(self):
        return retrieve_email_userro(
            self.proposal.proposal_applicant.email_user_id
        ) if (self.proposal.proposal_applicant and 
            self.proposal.proposal_applicant.email_user_id
        ) else None

    @property
    def title(self):
        return self.proposal.title

    @property
    def holder(self):
        return self.proposal.applicant

    @property
    def reference(self):
        return self.lodgement_number

    @property
    def allowed_assessors(self):
        return self.proposal.compliance_assessors

    @property
    def can_user_view(self):
        """
        :return: True if the compliance is not in the editable status for external user.
        """
        return self.customer_status == Compliance.CUSTOMER_STATUS_WITH_ASSESSOR or self.customer_status == Compliance.CUSTOMER_STATUS_APPROVED

    @property
    def can_process(self):
        """
        :return: True if the compliance is ready for assessment.
        """
        return self.processing_status == Compliance.PROCESSING_STATUS_WITH_ASSESSOR

    @property
    def amendment_requests(self):
        qs = ComplianceAmendmentRequest.objects.filter(compliance = self)
        return qs

    def save(self, *args, **kwargs):
        super(Compliance, self).save(*args,**kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = 'C{0:06d}'.format(self.pk)
            self.lodgement_number = new_lodgment_id
            self.save()

    def submit(self,request):
        with transaction.atomic():
            try:
                if self.processing_status=='discarded':
                    raise ValidationError('You cannot submit this compliance with requirements as it has been discarded.')
                if self.processing_status in ['future','due','overdue']:
                    self.processing_status = 'with_assessor'
                    self.customer_status = 'with_assessor'
                    self.submitter = request.user.id

                    if request.FILES:
                        for f in request.FILES:
                            document = self.documents.create(
                                name=str(request.FILES[f]),
                                _file = request.FILES[f]
                            )
                    if self.amendment_requests:
                        qs = self.amendment_requests.filter(status = "requested")
                        if (qs):
                            for q in qs:
                                q.status = 'amended'
                                q.save()

                self.lodgement_date = timezone.now()
                self.save(version_comment='Compliance Submitted: {}'.format(self.id))
                self.proposal.save(version_comment='Compliance Submitted: {}'.format(self.id))
                self.log_user_action(ComplianceUserAction.ACTION_SUBMIT_REQUEST.format(self.id),request)
                send_external_submit_email_notification(request,self)
                send_submit_email_notification(request,self)
                self.documents.all().update(can_delete=False)
            except:
                raise

    def delete_document(self, request, document):
        if (
            is_internal(request) or 
            (
                self.processing_status in ['future','due','overdue'] and
                (request.user.id == self.holder_id or is_internal(request))
            )
        ):
            with transaction.atomic():
                try:
                    if document:
                        doc = self.documents.get(id=document[2])
                        if doc.can_delete:
                            doc.delete()
                    return self
                except:
                    raise ValidationError('Document not found')


    def assign_to(self, user, request):
        with transaction.atomic():
            if is_internal(request) and user in self.allowed_assessors and request.user in self.allowed_assessors:
                self.assigned_to = user.id
                self.save()
                self.log_user_action(ComplianceUserAction.ACTION_ASSIGN_TO.format(user.get_full_name()),request)

    def unassign(self,request):
        with transaction.atomic():
            if is_internal(request) and request.user in self.allowed_assessors:
                self.assigned_to = None
                self.save()
                self.log_user_action(ComplianceUserAction.ACTION_UNASSIGN,request)

    def accept(self, request):
        with transaction.atomic():
            if self.processing_status == Compliance.PROCESSING_STATUS_WITH_ASSESSOR and is_internal(request) and request.user in self.allowed_assessors:
                self.processing_status = Compliance.PROCESSING_STATUS_APPROVED
                self.customer_status = Compliance.CUSTOMER_STATUS_APPROVED
                self.save()
                self.log_user_action(ComplianceUserAction.ACTION_CONCLUDE_REQUEST.format(self.id),request)
                send_compliance_accept_email_notification(self,request)

    def send_reminder(self, user=None):
        with transaction.atomic():
            try:
                if self.processing_status == Compliance.PROCESSING_STATUS_DUE and self.reminder_sent is False:
                    send_due_email_notification(self)
                    send_internal_due_email_notification(self)
                    self.reminder_sent = True
                    self.save()
                    ComplianceUserAction.log_action(self, ComplianceUserAction.ACTION_REMINDER_SENT.format(self.id), user)
                    logger.info('Pre due date reminder sent for Compliance {} '.format(self.lodgement_number))

                if self.processing_status == Compliance.PROCESSING_STATUS_OVERDUE and self.post_reminder_sent is False:
                    send_reminder_email_notification(self)
                    send_internal_reminder_email_notification(self)
                    self.post_reminder_sent = True
                    self.reminder_sent = True
                    self.save()
                    ComplianceUserAction.log_action(self, ComplianceUserAction.ACTION_REMINDER_SENT.format(self.id), user)
                    logger.info('Post due date reminder sent for Compliance {} '.format(self.lodgement_number))

            except Exception as e:
                logger.info('Error sending Reminder Compliance {}\n{}'.format(self.lodgement_number, e))

    def log_user_action(self, action, request):
        if request.user:
            return ComplianceUserAction.log_action(self, action, request.user)
        else:
            return ComplianceUserAction.log_action(self, action, None)

    def __str__(self):
        return self.lodgement_number


def update_proposal_complaince_filename(instance, filename):
    return '{}/proposals/{}/compliance/{}'.format(settings.MEDIA_APP_DIR, instance.compliance.proposal.id,filename)


class ComplianceDocument(Document):
    compliance = models.ForeignKey('Compliance', related_name='documents', on_delete=models.CASCADE)
    _file = models.FileField(storage=private_storage, upload_to=update_proposal_complaince_filename, max_length=512)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted

    def delete(self):
        if self.can_delete:
            return super(ComplianceDocument, self).delete()
        logger.info('Cannot delete existing document object after Compliance has been submitted (including document submitted before Compliance pushback to status Due): {}'.format(self.name))

    class Meta:
        app_label = 'mooringlicensing'


class ComplianceUserAction(UserAction):
    ACTION_CREATE = "Create compliance {}"
    ACTION_SUBMIT_REQUEST = "Submit compliance {}"
    ACTION_ASSIGN_TO = "Assign to {}"
    ACTION_UNASSIGN = "Unassign"
    ACTION_DECLINE_REQUEST = "Decline request"
    ACTION_ID_REQUEST_AMENDMENTS = "Request amendments"
    ACTION_REMINDER_SENT = "Reminder sent for due compliance {}"
    ACTION_OVERDUE_REMINDER_SENT = "Post due date reminder sent for Compliance {}"
    ACTION_STATUS_CHANGE = "Change status to Due for compliance {}"
    # Assessors
    ACTION_CONCLUDE_REQUEST = "Conclude request {}"

    @classmethod
    def log_action(cls, compliance, action, user):
        return cls.objects.create(
            compliance=compliance,
            who=user.id if user else None,
            what=str(action)
        )

    compliance = models.ForeignKey(Compliance, related_name='action_logs', on_delete=models.CASCADE)

    class Meta:
        app_label = 'mooringlicensing'


class ComplianceLogEntry(CommunicationsLogEntry):
    compliance = models.ForeignKey(Compliance, related_name='comms_logs', on_delete=models.CASCADE)

    def save(self, **kwargs):
        # save the request id if the reference not provided
        if not self.reference:
            self.reference = self.compliance.id
        super(ComplianceLogEntry, self).save(**kwargs)

    class Meta:
        app_label = 'mooringlicensing'


def update_compliance_comms_log_filename(instance, filename):
    return '{}/proposals/{}/compliance/communications/{}'.format(settings.MEDIA_APP_DIR, instance.log_entry.compliance.proposal.id,filename)


class ComplianceLogDocument(Document):
    log_entry = models.ForeignKey('ComplianceLogEntry', related_name='documents', on_delete=models.CASCADE)
    _file = models.FileField(storage=private_storage, upload_to=update_compliance_comms_log_filename, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'


class ComplianceAmendmentReason(SanitiseMixin):
    reason = models.CharField('Reason', max_length=125)

    class Meta:
        app_label = 'mooringlicensing'

    def __str__(self):
        return self.reason


class ComplianceAmendmentRequest(SanitiseMixin):
    STATUS_CHOICES = (('requested', 'Requested'), ('amended', 'Amended'))

    compliance = models.ForeignKey(Compliance, on_delete=models.CASCADE)
    status = models.CharField('Status', max_length=30, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0])
    reason = models.ForeignKey(ComplianceAmendmentReason, blank=True, null=True, on_delete=models.SET_NULL)
    text = models.TextField(blank=True)

    class Meta:
        app_label = 'mooringlicensing'

    def generate_amendment(self,request):
        with transaction.atomic():
          if self.status == 'requested':
            compliance = self.compliance
            if compliance.processing_status != 'due':
                compliance.processing_status = 'due'
                compliance.customer_status = 'due'
                compliance.save()
            # Create a log entry for the proposal
            compliance.log_user_action(ComplianceUserAction.ACTION_ID_REQUEST_AMENDMENTS,request)
            send_amendment_email_notification(self,request, compliance)


import reversion
reversion.register(Compliance)
