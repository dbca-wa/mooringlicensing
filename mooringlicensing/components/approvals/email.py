import logging
from dateutil.relativedelta import relativedelta

from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.utils.encoding import smart_text
from django.core.urlresolvers import reverse
from django.conf import settings
from datetime import date, timedelta

from mooringlicensing.components.emails.emails import TemplateEmailBase
from mooringlicensing.components.proposals.email import (
        _log_user_email as log_proposal_user_email,
        )
from ledger.accounts.models import EmailUser

from mooringlicensing.components.proposals.models import ProposalApproverGroup

logger = logging.getLogger(__name__)

SYSTEM_NAME = settings.SYSTEM_NAME_SHORT + ' Automated Message'


class ApprovalExpireNotificationEmail(TemplateEmailBase):
    subject = 'Approval expired'  # This is default and should be overwitten
    html_template = 'mooringlicensing/emails/approval_expire_notification.html'
    txt_template = 'mooringlicensing/emails/approval_expire_notification.txt'

    def __init__(self, approval):
        self.subject = '{} - {} expired.'.format(settings.RIA_NAME, approval.child_obj.description)


class ApprovalVesselNominationNotificationEmail(TemplateEmailBase):
    subject = 'Nominate vessel for Permit {}'
    html_template = 'mooringlicensing/emails/approval_vessel_nomination_reminder.html'
    txt_template = 'mooringlicensing/emails/approval_vessel_nomination_reminder.txt'

    def __init__(self, approval):
        self.subject = self.subject.format(approval.lodgement_number)


class ApprovalCancelledDueToNoVesselsNominatedEmail(TemplateEmailBase):
    subject = 'Notification: Approval {} cancelled'
    html_template = 'mooringlicensing/emails/approval_cancelled_due_to_no_vessels_nominated.html'
    txt_template = 'mooringlicensing/emails/approval_cancelled_due_to_no_vessels_nominated.txt'

    def __init__(self, approval):
        self.subject = self.subject.format(approval.lodgement_number)


class ApprovalVesselNominationReminderEmail(TemplateEmailBase):
    subject = 'Reminder: Nominate vessel for Permit {}'
    html_template = 'mooringlicensing/emails/approval_vessel_nomination_reminder.html'
    txt_template = 'mooringlicensing/emails/approval_vessel_nomination_reminder.txt'

    def __init__(self, approval):
        self.subject = self.subject.format(approval.lodgement_number)


class ApprovalCancelNotificationEmail(TemplateEmailBase):
    subject = 'Approval cancelled'  # This is default and should be overwitten
    html_template = 'mooringlicensing/emails/approval_cancel_notification.html'
    txt_template = 'mooringlicensing/emails/approval_cancel_notification.txt'

    def __init__(self, approval):
        self.subject = '{} - {} cancelled.'.format(settings.RIA_NAME, approval.child_obj.description)


class ApprovalSuspendNotificationEmail(TemplateEmailBase):
    subject = 'Approval suspended'  # This is default and should be overwitten
    html_template = 'mooringlicensing/emails/approval_suspend_notification.html'
    txt_template = 'mooringlicensing/emails/approval_suspend_notification.txt'

    def __init__(self, approval):
        self.subject = '{} - {} suspended.'.format(settings.RIA_NAME, approval.child_obj.description)


class ApprovalSurrenderNotificationEmail(TemplateEmailBase):
    subject = 'Approval surrendered'
    html_template = 'mooringlicensing/emails/approval_surrender_notification.html'
    txt_template = 'mooringlicensing/emails/approval_surrender_notification.txt'

    def __init__(self, approval):
        self.subject = '{} - {} surrendered.'.format(settings.RIA_NAME, approval.child_obj.description)


class ApprovalReinstateNotificationEmail(TemplateEmailBase):
    subject = 'Approval reinstated'
    html_template = 'mooringlicensing/emails/approval_reinstate_notification.html'
    txt_template = 'mooringlicensing/emails/approval_reinstate_notification.txt'

    def __init__(self, approval):
        self.subject = '{} - {} reinstated.'.format(settings.RIA_NAME, approval.child_obj.description)


class ApprovalRenewalNotificationEmail(TemplateEmailBase):
    subject = 'Approval renewal'
    html_template = 'mooringlicensing/emails/approval_renewal_notification.html'
    txt_template = 'mooringlicensing/emails/approval_renewal_notification.txt'

    def __init__(self, approval):
        self.subject = '{} - {} renewal.'.format(settings.RIA_NAME, approval.child_obj.description)


class CreateMooringLicenceApplicationEmail(TemplateEmailBase):
    subject = 'Approval created'
    html_template = 'mooringlicensing/emails/create_mooring_licence_application_notification.html'
    txt_template = 'mooringlicensing/emails/create_mooring_licence_application_notification.txt'

    def __init__(self, approval):
        self.subject = '{} - {} created.'.format(settings.RIA_NAME, approval.child_obj.description)


def send_approval_expire_email_notification(approval):
    # if approval.is_lawful_authority:
    #     email = FilmingLawfulAuthorityApprovalExpireNotificationEmail()
    # if approval.is_filming_licence:
    #     email = FilmingLicenceApprovalExpireNotificationEmail()
    # else:
    #     email = ApprovalExpireNotificationEmail()
    email = ApprovalExpireNotificationEmail(approval)
    proposal = approval.current_proposal

    url=settings.SITE_URL if settings.SITE_URL else ''
    url += reverse('external')

    if "-internal" in url:
        # remove '-internal'. This email is for external submitters
        url = ''.join(url.split('-internal'))

    context = {
        'approval': approval,
        'proposal': proposal,
        'url': url
    }
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]
    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context)
    sender = settings.DEFAULT_FROM_EMAIL
    try:
    	sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)

    _log_approval_email(msg, approval, sender=sender_user)
    #_log_org_email(msg, approval.applicant, proposal.submitter, sender=sender_user)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)


def send_vessel_nomination_notification_main(approval, request=None):
    from mooringlicensing.components.approvals.models import WaitingListAllocation, MooringLicence#, AnnualAdmissionPermit, AuthorisedUserPermit
    email = ApprovalVesselNominationNotificationEmail(approval)
    proposal = approval.current_proposal

    due_date = approval.expiry_date
    sale_date = approval.current_proposal.vessel_ownership.end_date
    six_months = timedelta(weeks=26)
    if type(approval.child_obj) in (WaitingListAllocation, MooringLicence):
        due_date = sale_date if (sale_date + six_months) < approval.expiry_date else approval.expiry_date

    context = {
        'approval': approval,
        'due_date': due_date,
    }

    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)

    to_address = approval.submitter.email
    all_ccs = []
    bcc = []
    # if proposal.org_applicant and proposal.org_applicant.email:
    #     cc_list = proposal.org_applicant.email
    #     if cc_list:
    #         all_ccs = [cc_list]
    msg = email.send(to_address, context=context, attachments=[], cc=all_ccs, bcc=bcc,)

    _log_approval_email(msg, approval, sender=sender_user)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)

    return msg


def send_approval_cancelled_due_to_no_vessels_nominated_mail(approval, request=None):
    email = ApprovalCancelledDueToNoVesselsNominatedEmail(approval)
    proposal = approval.current_proposal

    context = {
        'approval': approval,
        'due_date': approval.current_proposal.vessel_ownership.end_date + relativedelta(months=+6),
    }

    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)


    approver_group = ProposalApproverGroup.objects.all().first()
    to_address = approval.submitter.email
    all_ccs = []
    bcc = approver_group.members_email
    # if proposal.org_applicant and proposal.org_applicant.email:
    #     cc_list = proposal.org_applicant.email
    #     if cc_list:
    #         all_ccs = [cc_list]
    msg = email.send(to_address, context=context, attachments=[], cc=all_ccs, bcc=bcc,)

    _log_approval_email(msg, approval, sender=sender_user)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)

    return msg


def send_vessel_nomination_reminder_mail(approval, request=None):
    email = ApprovalVesselNominationReminderEmail(approval)
    proposal = approval.current_proposal

    context = {
        'approval': approval,
        'due_date': approval.current_proposal.vessel_ownership.end_date + relativedelta(months=+6),
    }

    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)

    to_address = approval.submitter.email
    all_ccs = []
    bcc = []
    # if proposal.org_applicant and proposal.org_applicant.email:
    #     cc_list = proposal.org_applicant.email
    #     if cc_list:
    #         all_ccs = [cc_list]
    msg = email.send(to_address, context=context, attachments=[], cc=all_ccs, bcc=bcc,)

    _log_approval_email(msg, approval, sender=sender_user)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)

    return msg


def send_approval_cancel_email_notification(approval):
    email = ApprovalCancelNotificationEmail(approval)
    proposal = approval.current_proposal

    context = {
        'approval': approval,

    }
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]
    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context)
    sender = settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender_user)
    #_log_org_email(msg, approval.applicant, proposal.submitter, sender=sender_user)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)


def send_approval_suspend_email_notification(approval, request=None):
    email = ApprovalSuspendNotificationEmail(approval)
    proposal = approval.current_proposal

    if request and 'test-emails' in request.path_info:
        details = 'This are my test details'
        from_date = '01/01/1970'
        to_date = '01/01/2070'
    else:
        details = approval.suspension_details['details'],
        from_date = approval.suspension_details['from_date'],
        to_date = approval.suspension_details['to_date']

    context = {
        'approval': approval,
        'details': details,
        'from_date': from_date,
        'to_date': to_date
    }
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]
    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context)
    sender = settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender_user)
    #_log_org_email(msg, approval.applicant, proposal.submitter, sender=sender_user)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)


def send_approval_surrender_email_notification(approval, request=None):
    email = ApprovalSurrenderNotificationEmail(approval)
    proposal = approval.current_proposal

    if request and 'test-emails' in request.path_info:
        details = 'This are my test details'
        surrender_date = '01/01/1970'
    else:
        details = approval.surrender_details['details'],
        surrender_date = approval.surrender_details['surrender_date'],

    context = {
        'approval': approval,
        'details': details,
        'surrender_date': surrender_date,
    }
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]
    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context)
    sender = settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender_user)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)


def send_approval_renewal_email_notification(approval):
    email = ApprovalRenewalNotificationEmail(approval)
    proposal = approval.current_proposal
    url=settings.SITE_URL if settings.SITE_URL else ''
    url += reverse('external')

    if "-internal" in url:
        # remove '-internal'. This email is for external submitters
        url = ''.join(url.split('-internal'))


    context = {
        'approval': approval,
        'proposal': approval.current_proposal,
        'url': url,
    }
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)
    #attach renewal notice
    if approval.renewal_document and approval.renewal_document._file is not None:
        renewal_document= approval.renewal_document._file
        file_name = approval.renewal_document.name
        attachment = (file_name, renewal_document.file.read(), 'application/pdf')
        attachment = [attachment]
    else:
        attachment = []
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]
    msg = email.send(proposal.submitter.email,cc=all_ccs, attachments=attachment, context=context)
    sender = settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender_user)
    #_log_org_email(msg, approval.applicant, proposal.submitter, sender=sender_user)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)


# waiting list allocation notice
def send_create_mooring_licence_application_email_notification(request, approval):
    email = CreateMooringLicenceApplicationEmail(approval)
    proposal = approval.current_proposal
    ria_generated_proposal = approval.ria_generated_proposal.all()[0] if approval.ria_generated_proposal.all() else None
    #url=settings.SITE_URL if settings.SITE_URL else ''
    #url += reverse('external')

    url = request.build_absolute_uri(reverse('external-proposal-detail',kwargs={'proposal_pk': proposal.id}))
    if "-internal" in url:
        # remove '-internal'. This email is for external submitters
        url = ''.join(url.split('-internal'))

    context = {
        'approval': approval,
        'proposal': proposal,
        'mla_proposal': ria_generated_proposal,
        'url': url,
        'message_details': request.data.get('message_details'),
    }
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)

    attachments = []
    if approval.waiting_list_offer_documents.all():
        for doc in approval.waiting_list_offer_documents.all():
            #file_name = doc._file.name
            file_name = doc.name
            attachment = (file_name, doc._file.file.read())
            attachments.append(attachment)

    bcc = request.data.get('cc_email')
    bcc_list = bcc.split(',')
    msg = email.send(proposal.submitter.email,bcc=bcc_list, attachments=attachments, context=context)
    #msg = email.send(proposal.submitter.email, attachments=attachments, context=context)
    sender = settings.DEFAULT_FROM_EMAIL
    #_log_approval_email(msg, approval, sender=sender_user)
    log_mla_created_proposal_email(msg, ria_generated_proposal, sender=sender_user)
    #_log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)
    log_proposal_user_email(msg, ria_generated_proposal.submitter, ria_generated_proposal.submitter, sender=sender_user)


def send_approval_reinstate_email_notification(approval, request):
    email = ApprovalReinstateNotificationEmail(approval)
    proposal = approval.current_proposal

    context = {
        'approval': approval,

    }
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]
    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context)
    sender = request.user if request else settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender)
    #_log_org_email(msg, approval.applicant, proposal.submitter, sender=sender)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender)



def _log_approval_email(email_message, approval, sender=None):
    from mooringlicensing.components.approvals.models import ApprovalLogEntry
    if isinstance(email_message, (EmailMultiAlternatives, EmailMessage,)):
        # TODO this will log the plain text body, should we log the html instead
        text = email_message.body
        subject = email_message.subject
        fromm = smart_text(sender) if sender else smart_text(email_message.from_email)
        # the to email is normally a list
        if isinstance(email_message.to, list):
            to = ','.join(email_message.to)
        else:
            to = smart_text(email_message.to)
        # we log the cc and bcc in the same cc field of the log entry as a ',' comma separated string
        all_ccs = []
        if email_message.cc:
            all_ccs += list(email_message.cc)
        if email_message.bcc:
            all_ccs += list(email_message.bcc)
        all_ccs = ','.join(all_ccs)

    else:
        text = smart_text(email_message)
        subject = ''
        to = approval.current_proposal.submitter.email
        fromm = smart_text(sender) if sender else SYSTEM_NAME
        all_ccs = ''

    customer = approval.current_proposal.submitter

    staff = sender

    kwargs = {
        'subject': subject,
        'text': text,
        'approval': approval,
        'customer': customer,
        'staff': staff,
        'to': to,
        'fromm': fromm,
        'cc': all_ccs
    }

    email_entry = ApprovalLogEntry.objects.create(**kwargs)

    return email_entry




from mooringlicensing.components.organisations.models import OrganisationLogEntry, Organisation
def _log_org_email(email_message, organisation, customer ,sender=None):
    if not isinstance(organisation, Organisation):
        # is a proxy_applicant
        return None

    if isinstance(email_message, (EmailMultiAlternatives, EmailMessage,)):
        # TODO this will log the plain text body, should we log the html instead
        text = email_message.body
        subject = email_message.subject
        fromm = smart_text(sender) if sender else smart_text(email_message.from_email)
        # the to email is normally a list
        if isinstance(email_message.to, list):
            to = ','.join(email_message.to)
        else:
            to = smart_text(email_message.to)
        # we log the cc and bcc in the same cc field of the log entry as a ',' comma separated string
        all_ccs = []
        if email_message.cc:
            all_ccs += list(email_message.cc)
        if email_message.bcc:
            all_ccs += list(email_message.bcc)
        all_ccs = ','.join(all_ccs)

    else:
        text = smart_text(email_message)
        subject = ''
        to = customer
        fromm = smart_text(sender) if sender else SYSTEM_NAME
        all_ccs = ''

    customer = customer

    staff = sender

    kwargs = {
        'subject': subject,
        'text': text,
        'organisation': organisation,
        'customer': customer,
        'staff': staff,
        'to': to,
        'fromm': fromm,
        'cc': all_ccs
    }

    email_entry = OrganisationLogEntry.objects.create(**kwargs)

    return email_entry

def _log_user_email(email_message, emailuser, customer ,sender=None):
    from ledger.accounts.models import EmailUserLogEntry
    if isinstance(email_message, (EmailMultiAlternatives, EmailMessage,)):
        # TODO this will log the plain text body, should we log the html instead
        text = email_message.body
        subject = email_message.subject
        fromm = smart_text(sender) if sender else smart_text(email_message.from_email)
        # the to email is normally a list
        if isinstance(email_message.to, list):
            to = ','.join(email_message.to)
        else:
            to = smart_text(email_message.to)
        # we log the cc and bcc in the same cc field of the log entry as a ',' comma separated string
        all_ccs = []
        if email_message.cc:
            all_ccs += list(email_message.cc)
        if email_message.bcc:
            all_ccs += list(email_message.bcc)
        all_ccs = ','.join(all_ccs)

    else:
        text = smart_text(email_message)
        subject = ''
        to = customer
        fromm = smart_text(sender) if sender else SYSTEM_NAME
        all_ccs = ''

    customer = customer

    staff = sender

    kwargs = {
        'subject': subject,
        'text': text,
        'emailuser': emailuser,
        'customer': customer,
        'staff': staff,
        'to': to,
        'fromm': fromm,
        'cc': all_ccs
    }

    email_entry = EmailUserLogEntry.objects.create(**kwargs)

    return email_entry

def log_mla_created_proposal_email(email_message, proposal, sender=None):
    from mooringlicensing.components.proposals.models import ProposalLogEntry, ProposalLogDocument
    if isinstance(email_message, (EmailMultiAlternatives, EmailMessage,)):
        # TODO this will log the plain text body, should we log the html instead
        text = email_message.body
        subject = email_message.subject
        fromm = smart_text(sender) if sender else smart_text(email_message.from_email)
        # the to email is normally a list
        if isinstance(email_message.to, list):
            to = ','.join(email_message.to)
        else:
            to = smart_text(email_message.to)
        # we log the cc and bcc in the same cc field of the log entry as a ',' comma separated string
        all_ccs = []
        if email_message.cc:
            all_ccs += list(email_message.cc)
        if email_message.bcc:
            all_ccs += list(email_message.bcc)
        all_ccs = ','.join(all_ccs)

    else:
        text = smart_text(email_message)
        subject = ''
        to = proposal.submitter.email
        fromm = smart_text(sender) if sender else SYSTEM_NAME
        all_ccs = ''

    customer = proposal.submitter

    staff = sender

    kwargs = {
        'subject': subject,
        'text': text,
        'proposal': proposal,
        'customer': customer,
        'staff': staff,
        'to': to,
        'fromm': fromm,
        'cc': all_ccs
    }

    email_entry = ProposalLogEntry.objects.create(**kwargs)

    if proposal.waiting_list_allocation.waiting_list_offer_documents.all():
        # attach the files to the comms_log also
        for doc in proposal.waiting_list_allocation.waiting_list_offer_documents.all():
            ProposalLogDocument.objects.create(
                    log_entry=email_entry,
                    _file=doc._file,
                    name=doc.name
                    )

    return email_entry


