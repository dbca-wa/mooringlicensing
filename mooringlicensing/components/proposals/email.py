import logging
import mimetypes
import pytz
from ledger.accounts.models import EmailUser
from ledger.payments.invoice.models import Invoice

from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.utils.encoding import smart_text
from django.core.urlresolvers import reverse
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError

from mooringlicensing.components.approvals.email import log_mla_created_proposal_email, _log_approval_email, _log_org_email, _log_user_email
from mooringlicensing.components.compliances.email import _log_compliance_email
from mooringlicensing.components.emails.emails import TemplateEmailBase
from datetime import datetime

from mooringlicensing.components.main.models import NumberOfDaysType, NumberOfDaysSetting
from mooringlicensing.components.emails.utils import get_user_as_email_user, make_url_for_internal, get_public_url, \
    make_url_for_external
from mooringlicensing.settings import CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA, CODE_DAYS_IN_PERIOD_MLA, \
    PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL

logger = logging.getLogger(__name__)

SYSTEM_NAME = settings.SYSTEM_NAME_SHORT + ' Automated Message'


def log_proposal_email(msg, proposal, sender, attachments=[]):
    try:
        sender_user = sender if isinstance(sender, EmailUser) else EmailUser.objects.get(email__icontains=sender)
    except:
        sender_user = EmailUser.objects.create(email=sender, password='')

    _log_proposal_email(msg, proposal, sender=sender_user, attachments=attachments)
    if proposal.org_applicant:
        _log_org_email(msg, proposal.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, proposal.submitter, proposal.submitter, sender=sender_user, attachments=attachments)


def _log_proposal_email(email_message, proposal, sender=None, file_bytes=None, filename=None, attachments=[]):
    from mooringlicensing.components.proposals.models import ProposalLogEntry
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

    for attachment in attachments:
        path_to_file = '{}/proposals/{}/communications/{}'.format(settings.MEDIA_APP_DIR, proposal.id, attachment[0])
        path = default_storage.save(path_to_file, ContentFile(attachment[1]))
        email_entry.documents.get_or_create(_file=path_to_file, name=attachment[0])

    return email_entry


def _log_org_email(email_message, organisation, customer ,sender=None):
    from mooringlicensing.components.organisations.models import OrganisationLogEntry
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


def _log_user_email(email_message, target_email_user, customer, sender=None, attachments=[]):
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
        'emailuser': target_email_user if target_email_user else customer,
        'customer': customer,
        'staff': staff,
        'to': to,
        'fromm': fromm,
        'cc': all_ccs
    }

    email_entry = EmailUserLogEntry.objects.create(**kwargs)

    for attachment in attachments:
        path_to_file = '{}/emailuser/{}/communications/{}'.format(settings.MEDIA_APP_DIR, target_email_user.id, attachment[0])
        path = default_storage.save(path_to_file, ContentFile(attachment[1]))
        email_entry.documents.get_or_create(_file=path_to_file, name=attachment[0])

    return email_entry


def send_confirmation_email_upon_submit(request, proposal, payment_made, attachments=[]):
    # 1
    email = TemplateEmailBase(
        subject='Submission Received: Rottnest Island Boating Application {}'.format(proposal.lodgement_number),
        html_template='mooringlicensing/emails_2/email_1.html',
        txt_template='mooringlicensing/emails_2/email_1.txt',
    )

    # Configure recipients, contents, etc
    context = {
        'public_url': get_public_url(request),
        'dashboard_external_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'payment_made': payment_made,
    }
    to_address = proposal.submitter.email
    cc = []
    bcc = []

    # Send email
    # in send() method, self.html_template is rendered by context and attached as alternative
    # In other words, self.html_template should be full html-email
    msg = email.send(to_address, context=context, attachments=attachments, cc=cc, bcc=bcc,)
    if not msg:
        raise ValidationError('An error occurred while submitting proposal (Submit email notifications failed)')
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments)

    return msg


def send_notification_email_upon_submit_to_assessor(request, proposal, attachments=[]):
    # 2
    email = TemplateEmailBase(
        subject='Assessment required: a new application submission is awaiting assessment',
        html_template='mooringlicensing/emails_2/email_2.html',
        txt_template='mooringlicensing/emails_2/email_2.txt',
    )

    url = request.build_absolute_uri(reverse('internal-proposal-detail', kwargs={'proposal_pk': proposal.id}))
    url = make_url_for_internal(url)

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'proposal_internal_url': url,
    }
    to_address = proposal.assessor_recipients
    cc = []
    bcc = []

    # Send email
    # in send() method, self.html_template is rendered by context and attached as alternative
    # In other words, self.html_template should be full html-email
    msg = email.send(to_address, context=context, attachments=attachments, cc=cc, bcc=bcc,)
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments)

    return msg


def send_approver_approve_decline_email_notification(request, proposal):
    # 3
    email = TemplateEmailBase(
        subject='Approval required: an assessed application is awaiting approval or decline',
        html_template='mooringlicensing/emails_2/email_3.html',
        txt_template='mooringlicensing/emails_2/email_3.txt',
    )

    url = request.build_absolute_uri(reverse('internal-proposal-detail', kwargs={'proposal_pk': proposal.id}))
    url = make_url_for_internal(url)

    context = {
        'public_url': get_public_url(request),
        # 'details': proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else '',
        'proposal': proposal,
        'proposal_internal_url': url
    }

    msg = email.send(proposal.approver_recipients, context=context)
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender)
    return msg

# TODO: #4


def send_amendment_email_notification(amendment_request, request, proposal):
    # 5
    email = TemplateEmailBase(
        subject='Amendment Required: Rottnest Island Boating Application {}'.format(proposal.lodgement_number),
        html_template='mooringlicensing/emails_2/email_5.html',
        txt_template='mooringlicensing/emails_2/email_5.txt',
    )

    reason = amendment_request.reason.reason
    url = request.build_absolute_uri(reverse('external-proposal-detail', kwargs={'proposal_pk': proposal.id}))

    context = {
        'public_url': get_public_url(request),
        'recipient': proposal.submitter,
        'proposal': proposal,
        'reason': reason,
        'text': amendment_request.text,
        'proposal_external_url': make_url_for_external(url),
    }

    to = proposal.submitter.email
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]

    msg = email.send(to, cc=all_ccs, context=context)
    sender = get_user_as_email_user(msg.from_email)

    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.org_applicant:
        _log_org_email(msg, proposal.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, proposal.submitter, proposal.submitter, sender=sender)


def send_create_mooring_licence_application_email_notification(request, waiting_list_allocation, mooring_licence_application):
    # 6
    email = TemplateEmailBase(
        subject='Offer for Rottnest Island Mooring Site Licence - Rottnest Island Authority',
        html_template='mooringlicensing/emails_2/email_6.html',
        txt_template='mooringlicensing/emails_2/email_6.txt',
    )

    ria_generated_proposal = waiting_list_allocation.ria_generated_proposal.all()[0] if waiting_list_allocation.ria_generated_proposal.all() else None

    url = request.build_absolute_uri(reverse('external-proposal-detail', kwargs={'proposal_pk': mooring_licence_application.id}))

    today = datetime.now(pytz.timezone(settings.TIME_ZONE)).date()
    days_type = NumberOfDaysType.objects.get(code=CODE_DAYS_IN_PERIOD_MLA)
    days_setting_application_period = NumberOfDaysSetting.get_setting_by_date(days_type, today)
    days_type = NumberOfDaysType.objects.get(code=CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA)
    days_setting_documents_period = NumberOfDaysSetting.get_setting_by_date(days_type, today)

    context = {
        'public_url': get_public_url(request),
        'wla': waiting_list_allocation,
        'recipient': mooring_licence_application.submitter,
        'application_period': days_setting_application_period.number_of_days,
        'documents_period': days_setting_documents_period.number_of_days,
        'proposal_external_url': url,
    }
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)

    attachments = []
    if waiting_list_allocation.waiting_list_offer_documents.all():
        for doc in waiting_list_allocation.waiting_list_offer_documents.all():
            file_name = doc.name
            attachment = (file_name, doc._file.file.read())
            attachments.append(attachment)

    bcc = request.data.get('cc_email')
    bcc_list = bcc.split(',')
    msg = email.send(mooring_licence_application.submitter.email, bcc=bcc_list, attachments=attachments, context=context)
    sender = settings.DEFAULT_FROM_EMAIL
    log_mla_created_proposal_email(msg, ria_generated_proposal, sender=sender_user)
    _log_user_email(msg, ria_generated_proposal.submitter, ria_generated_proposal.submitter, sender=sender_user, attachments=attachments)


def send_documents_upload_for_mooring_licence_application_email(request, proposal):
    # 7
    email = TemplateEmailBase(
        subject='Additional Documents Required: Application for Rottnest Island Mooring Site Licence',
        html_template='mooringlicensing/emails_2/email_7.html',
        txt_template='mooringlicensing/emails_2/email_7.txt',
    )
    document_upload_url = proposal.get_document_upload_url(request)

    today = datetime.now(pytz.timezone(settings.TIME_ZONE)).date()
    days_type = NumberOfDaysType.objects.get(code=CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA)
    days_setting = NumberOfDaysSetting.get_setting_by_date(days_type, today)

    url = request.build_absolute_uri(reverse('external-proposal-detail', kwargs={'proposal_pk': proposal.id}))

    # Configure recipients, contents, etc
    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'documents_upload_url': document_upload_url,
        'proposal_external_url': url,
        'num_of_days_to_submit_documents': days_setting.number_of_days,
    }
    to_address = proposal.submitter.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)

    sender = get_user_as_email_user(msg.from_email)
    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.org_applicant:
        _log_org_email(msg, proposal.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, proposal.submitter, proposal.submitter, sender=sender)

    return msg


def send_comppliance_due_date_notification(approval, compliance,):
    #  8
    email = TemplateEmailBase(
        subject='Due: Compliance Requirement for Rottnest Island Permit or Licence - Deadline {}'.format(compliance.due_date),
        html_template='mooringlicensing/emails_2/email_8.html',
        txt_template='mooringlicensing/emails_2/email_8.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    url = url + reverse('external-compliance-detail')

    context = {
        'public_url': get_public_url(),
        'approval': approval,
        'compliance': compliance,
        'recipient': compliance.submitter,
        'compliance_external_url': url,
    }
    to_address = compliance.submitter.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)

    sender = get_user_as_email_user(msg.from_email)
    _log_compliance_email(msg, compliance, sender=sender)
    if compliance.proposal.org_applicant:
        _log_org_email(msg, compliance.proposal.org_applicant, compliance.submitter, sender=sender)
    else:
        _log_user_email(msg, compliance.proposal.submitter, compliance.submitter, sender=sender)
    return msg


def send_comliance_overdue_notification(request, approval, compliance,):
    # 9
    email = TemplateEmailBase(
        subject='OVERDUE: Compliance Requirement for Rottnest Island Boating Permit or Licence',
        html_template='mooringlicensing/emails_2/email_9.html',
        txt_template='mooringlicensing/emails_2/email_9.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    url = url + reverse('external-compliance-detail')

    context = {
        'public_url': get_public_url(request),
        'approval': approval,
        'compliance': compliance,
        'recipient': compliance.submitter,
        'compliance_external_url': url,
    }
    to_address = compliance.submitter.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)

    sender = get_user_as_email_user(msg.from_email)
    _log_compliance_email(msg, compliance, sender=sender)
    if compliance.proposal.org_applicant:
        _log_org_email(msg, compliance.proposal.org_applicant, compliance.submitter, sender=sender)
    else:
        _log_user_email(msg, compliance.proposal.submitter, compliance.submitter, sender=sender)
    return msg

# 10
# send_vessel_nomination_reminder_mail() at approval.email.py


def send_invitee_reminder_email(proposal, due_date, number_of_days, request=None):
    # 11
    email = TemplateEmailBase(
        subject='REMINDER : Your Offer for a Rottnest Island Mooring Site Licence is About to Lapse - Rottnest Island Authority',
        html_template='mooringlicensing/emails/email_11.html',
        txt_template='mooringlicensing/emails/email_11.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    url = url + reverse('external-proposal-detail', kwargs={'proposal_pk': proposal.id})

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'proposal_external_url': url,
        'due_date': due_date,
        'number_of_days': number_of_days,
    }
    to_address = proposal.submitter.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender)
    return msg


def send_expire_mooring_licence_application_email(proposal, reason, due_date,):
    # 12 email to mooring licence applicant when mooring licence application is not submitted within configurable
    #    number of days after being invited to apply for a mooring licence
    html_template = 'mooringlicensing/emails_2/email_12.html'
    txt_template = 'mooringlicensing/emails_2/email_12.txt'

    email = TemplateEmailBase(
        subject='Lapsed: Offer for Rottnest Island Mooring Site Licence - Rottnest Island Authority',
        html_template=html_template,
        txt_template=txt_template,
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    dashboard_url = url + reverse('external')

    # Configure recipients, contents, etc
    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'dashboard_url': dashboard_url,
    }
    to_address = proposal.submitter.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender)
    return msg


def send_expire_mooring_licence_by_no_documents_email(proposal, reason, due_date,):
    # 13
    # Expire mooring licence application if additional documents are not submitted within a configurable number of days
    # from the initial submit of the mooring licence application and email to inform the applicant
    html_template = 'mooringlicensing/emails_2/email_13.html'
    txt_template = 'mooringlicensing/emails_2/email_13.txt'

    email = TemplateEmailBase(
        subject='Lapsed: Offer for Rottnest Island Mooring Site Licence - Rottnest Island Authority',
        html_template=html_template,
        txt_template=txt_template,
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    dashboard_url = url + reverse('external')

    # Configure recipients, contents, etc
    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'dashboard_url': dashboard_url,
    }
    to_address = proposal.submitter.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender)
    return msg


def send_expire_mla_notification_to_assessor(proposal, reason, due_date):
    # 14
    # email to assessor group when invite to apply for a mooring licence is expired, either because mooring licence is not submitted or additional documents are not submitted
    # (internal)
    email = TemplateEmailBase(
        subject='Expired mooring licence application - not submitted on time',
        html_template='mooringlicensing/emails_2/email_14.html',
        txt_template='mooringlicensing/emails_2/email_14.txt',
    )

    mooring_name = proposal.mooring.name if proposal.mooring else ''

    context = {
        'public_url': get_public_url(),
        'applicant': proposal.submitter,
        'due_date': due_date,
        'mooring_name': mooring_name,
        'recipient': proposal.submitter
    }

    to_address = proposal.assessor_recipients
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender)
    return msg


def send_endorser_reminder_email(proposal, request=None):
    # 15
    # email to authorised user application endorser if application is not endorsed or declined within configurable number of days
    email = TemplateEmailBase(
        subject='Endorsement Request: Application for Authorised Use of Mooring Site <mooring name> - Rottnest Island Authority',
        html_template='mooringlicensing/emails_2/email_15.html',
        txt_template='mooringlicensing/emails_2/email_15.txt',
    )

    url = settings.SITE_URL if settings.SITE_URL else ''
    endorse_url = url + reverse('endorse-url', kwargs={'uuid_str': proposal.uuid})
    decline_url = url + reverse('decline-url', kwargs={'uuid_str': proposal.uuid})
    proposal_url = url + reverse('external-proposal-detail', kwargs={'proposal_pk': proposal.id})

    try:
        endorser = EmailUser.objects.get(email=proposal.site_licensee_email)
    except:
        # Should not reach here
        return

    mooring_name = proposal.mooring.name if proposal.mooring else ''
    due_date = proposal.get_due_date_for_endorsement_by_target_date()

    # Configure recipients, contents, etc
    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'endorser': endorser,
        'applicant': proposal.submitter,
        'endorse_url': endorse_url,
        'decline_url': decline_url,
        'proposal_url': proposal_url,
        'mooring_name': mooring_name,
        'due_date': due_date,
    }
    to_address = proposal.site_licensee_email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender)
    return msg


def send_approval_renewal_email_notification(approval):
    # 16
    # email as renewal reminders for waiting list allocations, annual admission permits, authorised user permits,
    # mooring licences and dcv permits a configurable number of days before the expiry date, including if the status
    # is suspended (technically dcv permits are not renewed, the holder is invited to apply for a new one for the next season)
    
    proposal = approval.current_proposal
    email = TemplateEmailBase(
        #subject='First and Final Notice: Renewal of your Rottnest Island {} {} for {}'.format(approval.description, approval.lodgement_number, '(todo)'),  # TODO
        subject='First and Final Notice: Renewal of your Rottnest Island {} {} for {}'.format(approval.description, approval.lodgement_number, proposal.vessel_details.vessel.rego_no),  # TODO
        html_template='mooringlicensing/emails_2/email_16.html',
        txt_template='mooringlicensing/emails_2/email_16.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    url = url + reverse('external')

    context = {
        'public_url': get_public_url(),
        'approval': approval,
        #'vessel_rego_no': '(todo)',  # TODO
        'vessel_rego_no': proposal.vessel_details.vessel.rego_no,  # TODO
        'recipient': proposal.submitter,
        'expiry_date': approval.expiry_date,
        'dashboard_external_url': url,
    }

    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)

    attachments = []
    attachment = approval.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    msg = email.send(proposal.submitter.email, cc=[], attachments=attachments, context=context)

    from mooringlicensing.components.approvals.models import Approval
    if isinstance(approval, Approval):
        _log_approval_email(msg, approval, sender=sender_user)
        if approval.org_applicant:
            _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
        else:
            _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user, attachments=attachments)
    else:
        # TODO: log for DcvPermit???
        pass


def send_application_approved_or_declined_email(proposal, decision, request, stickers_to_be_returned=[]):
    # 17 --- 25
    # email to applicant when application is issued or declined (waiting list allocation application)
    from mooringlicensing.components.proposals.models import WaitingListApplication, AnnualAdmissionApplication, AuthorisedUserApplication, MooringLicenceApplication

    if proposal.application_type.code == WaitingListApplication.code:
        # 17
        send_wla_approved_or_declined_email(proposal, decision, request)  # require_payment should be always False for WLA because it should be paid at this stage.
    elif proposal.application_type.code == AnnualAdmissionApplication.code:
        # 18, 19
        send_aaa_approved_or_declined_email(proposal, decision, request, stickers_to_be_returned)  # require_payment should be always False for AAA because it should be paid at this stage.
    elif proposal.application_type.code == AuthorisedUserApplication.code:
        if proposal.proposal_type.code in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL]:
            # 20
            send_aua_approved_or_declined_email_new_renewal(proposal, decision, request, stickers_to_be_returned)
        elif proposal.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
            payment_required = False
            if proposal.application_fees.count():
                application_fee = proposal.application_fees.first()
                invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
                if invoice.payment_status not in ('paid', 'over_paid'):
                    payment_required = True
            if payment_required:
                # 22 (22a, 22b, 22c)
                send_aua_approved_or_declined_email_amendment_payment_required(proposal, decision, request, stickers_to_be_returned)
            else:
                # 21
                send_aua_approved_or_declined_email_amendment_payment_not_required(proposal, decision, request, stickers_to_be_returned)
        else:
            pass
    elif proposal.application_type.code == MooringLicenceApplication.code:
        # 23, 24, 25
        if proposal.proposal_type.code in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL]:
            send_mla_approved_or_declined_email_new_renewal(proposal, decision, request, stickers_to_be_returned)
        elif proposal.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
            payment_required = False
            if proposal.application_fees.count():
                application_fee = proposal.application_fees.first()
                invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
                if invoice.payment_status not in ('paid', 'over_paid'):
                    payment_required = True
            if payment_required:
                send_mla_approved_or_declined_email_amendment_payment_required(proposal, decision, request, stickers_to_be_returned)
            else:
                send_mla_approved_or_declined_email_amendment_payment_not_required(proposal, decision, request, stickers_to_be_returned)
        else:
            pass

    else:
        # Should not reach here
        logger.warning('The type of the proposal {} is unknown'.format(proposal.lodgement_number))


def send_wla_approved_or_declined_email(proposal, decision, request):
    # 17
    # email to applicant when application is issued or declined (waiting list allocation application)
    all_ccs = []
    all_bccs = []

    if decision == 'approved':
        # Internal user approved WLA
        subject = 'Confirmation: Allocation of a Position on a Mooring Site Licence Waiting List - Rottnest Island Authority'
        details = proposal.proposed_issuance_approval.get('details')
        cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_invoice = False
        attach_licence_doc = True

    elif decision == 'declined':
        # Internal user declined WLA
        subject = 'Declined: Application for a Position on a Mooring Site Licence Waiting List - Rottnest Island Authority'
        details = proposal.proposaldeclineddetails.reason
        cc_list = proposal.proposaldeclineddetails.cc_email
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_invoice = False
        attach_licence_doc = False

    # Attachments
    attachments = get_attachments(attach_invoice, attach_licence_doc, proposal)

    html_template = 'mooringlicensing/emails_2/email_17.html'
    txt_template = 'mooringlicensing/emails_2/email_17.txt'

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'proposal_type_code': proposal.proposal_type.code,
        'decision': decision,
        'details': details,
    }

    email = TemplateEmailBase(
        subject=subject,
        html_template=html_template,
        txt_template=txt_template,
    )

    to_address = proposal.submitter.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)

    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_aaa_approved_or_declined_email(proposal, decision, request, stickers_to_be_returned=[]):
    # 18 new/renewal, approval/decline
    # email to applicant when application is issued or declined (annual admission application, new and renewal)
    # 19 amendment, approval/decline
    # email to applicant when application is issued or declined (annual admission application, amendment)
    all_ccs = []
    all_bccs = []
    attach_invoice = False
    attach_licence_doc = False
    subject = ''
    details = ''
    if decision == 'approved':
        subject = 'Your annual admission application {} has been approved'.format(proposal.lodgement_number)
        details = proposal.proposed_issuance_approval.get('details')
        cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_invoice = False
        attach_licence_doc = True
    elif decision == 'declined':
        subject = 'Your annual admission application {} has been declined'.format(proposal.lodgement_number)
        details = proposal.proposaldeclineddetails.reason
        cc_list = proposal.proposaldeclineddetails.cc_email
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_invoice = False
        attach_licence_doc = False
    else:
        logger.warning('Decision is unclear when sending AAA approved/declined email for {}'.format(proposal.lodgement_number))

    # Attachments
    attachments = get_attachments(attach_invoice, attach_licence_doc, proposal)

    if proposal.proposal_type.code in (PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL):
        # New / Renewal
        html_template = 'mooringlicensing/emails_2/email_18.html'
        txt_template = 'mooringlicensing/emails_2/email_18.txt'
    elif proposal.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
        # Amendment
        html_template = 'mooringlicensing/emails_2/email_19.html'
        txt_template = 'mooringlicensing/emails_2/email_19.txt'
    else:
        logger.warning('ProposalType is unclear when sending AAA approved/declined email for {}'.format(proposal.lodgement_number))

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,  # TODO???: if existing sticker needs to be replaced, assign sticker object here
    }

    email = TemplateEmailBase(
        subject=subject,
        html_template=html_template,
        txt_template=txt_template,
    )

    to_address = proposal.submitter.email
    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)

    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_aua_approved_or_declined_email_new_renewal(proposal, decision, request, stickers_to_be_returned):
    # 20 AUA new/renewal, approval/decline
    # email to applicant when application is issued or declined (authorised user application, new and renewal)

    all_ccs = []
    all_bccs = []

    subject = ''
    details = ''
    attachments = []
    payment_url = ''
    html_template = 'mooringlicensing/emails_2/'
    txt_template = 'mooringlicensing/emails_2/'

    if decision == 'approved':
        # for payment
        html_template += 'email_20a.html'
        txt_template += 'email_20a.txt'
        subject = 'Payment Due: Application for Rottnest Island Authorised User Permit'
        details = proposal.proposed_issuance_approval.get('details')
        cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(True, False, proposal)

        # Generate payment_url if needed
        if proposal.application_fees.count():
            application_fee = proposal.application_fees.first()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            if invoice.payment_status not in ('paid', 'over_paid'):
                # Payment required
                payment_url = '{}/application_fee_existing/{}'.format(get_public_url(request), proposal.id)
    elif decision == 'approved_paid':
        # after payment
        html_template += 'email_20b.html'
        txt_template += 'email_20b.txt'
        subject = 'Approved: Application for Rottnest Island Authorised User Permit'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(False, True, proposal)
    elif decision == 'declined':
        # declined
        html_template += 'email_20c.html'
        txt_template += 'email_20c.txt'
        subject = 'Declined: Application for Rottnest Island Authorised User Permit'
        details = proposal.proposaldeclineddetails.reason
        cc_list = proposal.proposaldeclineddetails.cc_email
        if cc_list:
            all_ccs = cc_list.split(',')
    else:
        logger.warning('Decision is unclear when sending AAA approved/declined email for {}'.format(proposal.lodgement_number))

    email = TemplateEmailBase(
        subject=subject,
        html_template=html_template,
        txt_template=txt_template
    )

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,  # TODO: if existing sticker needs to be replaced, assign sticker object here.
        'payment_url': payment_url,
    }

    to_address = proposal.submitter.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)

    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_aua_approved_or_declined_email_amendment_payment_not_required(proposal, decision, request, stickers_to_be_returned):
    #21
    # email to applicant when application is issued or declined (authorised user application, amendment where no payment is required)
    all_ccs = []
    all_bccs = []

    subject = ''
    details = ''
    attachments = []

    if decision == 'approved':
        subject = 'Approved: Amendment Application for Rottnest Island Authorised User Permit'
        details = proposal.proposed_issuance_approval.get('details')
        cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(False, True, proposal)
    elif decision == 'approved_paid':
        subject = 'Approved: Amendment Application for Rottnest Island Authorised User Permit'
        details = proposal.proposed_issuance_approval.get('details')
        cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(False, True, proposal)
    elif decision == 'declined':
        subject = 'Declined: Amendment Application for Rottnest Island Authorised User Permit'
        details = proposal.proposaldeclineddetails.reason
        cc_list = proposal.proposaldeclineddetails.cc_email
        if cc_list:
            all_ccs = cc_list.split(',')
    else:
        logger.warning('Decision is unclear when sending AUA approved/declined email for {}'.format(proposal.lodgement_number))

    email = TemplateEmailBase(
        subject=subject,
        html_template='mooringlicensing/emails_2/email_21.html',
        txt_template='mooringlicensing/emails_2/email_21.txt',
    )

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,  # TODO: if existing sticker needs to be replaced, assign sticker object here.
    }

    to_address = proposal.submitter.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)

    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_aua_approved_or_declined_email_amendment_payment_required(proposal, decision, request, stickers_to_be_returned):
    #22
    # email to applicant when application is issued or declined (authorised user application, amendment where payment is required)
    all_ccs = []
    all_bccs = []
    attach_invoice = False
    attach_licence_doc = False

    subject = ''
    details = ''
    attachments = []
    payment_url = ''
    html_template = 'mooringlicensing/emails_2/'
    txt_template = 'mooringlicensing/emails_2/'

    if decision == 'approved':
        # for payment
        html_template += 'email_22a.html'
        txt_template += 'email_22a.txt'
        subject = 'Payment Due: Amendment to Rottnest Island Authorised User Permit'
        details = proposal.proposed_issuance_approval.get('details')
        cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(True, False, proposal)

        # Generate payment_url if needed
        if proposal.application_fees.count():
            application_fee = proposal.application_fees.first()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            if invoice.payment_status not in ('paid', 'over_paid'):
                # Payment required
                payment_url = '{}/application_fee_existing/{}'.format(get_public_url(request), proposal.id)
    elif decision == 'approved_paid':
        # after payment
        html_template += 'email_22b.html'
        txt_template += 'email_22b.txt'
        subject = 'Approved: Amendment to Rottnest Island Authorised User Permit'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(False, True, proposal)
    elif decision == 'declined':
        # declined
        html_template += 'email_22c.html'
        txt_template += 'email_22c.txt'
        subject = 'Declined: Amendment Application for Rottnest Island Authorised User Permit'
        details = proposal.proposaldeclineddetails.reason
        cc_list = proposal.proposaldeclineddetails.cc_email
        if cc_list:
            all_ccs = cc_list.split(',')
    else:
        logger.warning('Decision is unclear when sending AAA approved/declined email for {}'.format(proposal.lodgement_number))

    email = TemplateEmailBase(
        subject=subject,
        html_template=html_template,
        txt_template=txt_template,
    )

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,  # TODO: if existing sticker needs to be replaced, assign sticker object here.
        'payment_url': payment_url,
    }

    to_address = proposal.submitter.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)

    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments)
    return msg


def get_attachments(attach_invoice, attach_licence_doc, proposal, attach_au_summary_doc=False):
    from mooringlicensing.components.payments_ml.invoice_pdf import create_invoice_pdf_bytes

    proposal.refresh_from_db()
    if proposal.approval:  # For AU/ML new application, approval is not created yet before payments
        proposal.approval.refresh_from_db()

    attachments = []
    if attach_invoice and proposal.invoice:
        # Attach invoice
        invoice_bytes = create_invoice_pdf_bytes('invoice.pdf', proposal.invoice, )
        attachment = ('invoice#{}.pdf'.format(proposal.invoice.reference), invoice_bytes, 'application/pdf')
        attachments.append(attachment)
    if attach_licence_doc and proposal.approval and proposal.approval.licence_document:
        # Attach licence document
        licence_document = proposal.approval.licence_document._file
        if licence_document is not None:
            file_name = proposal.approval.licence_document.name
            attachment = (file_name, licence_document.file.read(), 'application/pdf')
            attachments.append(attachment)

            # add requirement documents
            for requirement in proposal.requirements.exclude(is_deleted=True):
                for doc in requirement.requirement_documents.all():
                    file_name = doc._file.name
                    attachment = (file_name, doc._file.file.read())
                    attachments.append(attachment)
    if attach_au_summary_doc and proposal.approval and proposal.approval.authorised_user_summary_document:
        au_summary_document = proposal.approval.authorised_user_summary_document._file
        if au_summary_document is not None:
            file_name = proposal.approval.authorised_user_summary_document.name
            attachment = (file_name, au_summary_document.file.read(), 'application/pdf')
            attachments.append(attachment)

    return attachments


def send_au_summary_to_ml_holder(mooring_licence, request, au_proposal):
    subject = 'Authorised User Summary for {} - Rottnest Island Authority'.format(mooring_licence.mooring.name)
    attachments = []

    email = TemplateEmailBase(
        subject=subject,
        html_template='mooringlicensing/emails_2/au_summary.html',
        txt_template='mooringlicensing/emails_2/au_summary.txt',
    )

    if mooring_licence.authorised_user_summary_document:
        au_summary_document = mooring_licence.authorised_user_summary_document._file
        if au_summary_document is not None:
            file_name = mooring_licence.authorised_user_summary_document.name
            attachment = (file_name, au_summary_document.file.read(), 'application/pdf')
            attachments.append(attachment)

    proposal = mooring_licence.current_proposal
    context = {
        'authorised_user_full_name': au_proposal.applicant,
        'mooring_number': mooring_licence.mooring.name,
        'yourself_or_ria': 'ria' if au_proposal.mooring_authorisation_preference == 'RIA' else 'yourself',
        'approval_date': au_proposal.approval.issue_date.strftime('%d/%m/%Y'),
        'public_url': get_public_url(request),
        # 'approval': approval,
        'recipient': mooring_licence.applicant,
        'url_for_au_dashboard_page': get_public_url(request),  # Do we have AU dashboard page for external???
    }

    to_address = mooring_licence.submitter.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=[], bcc=[],)

    sender = get_user_as_email_user(msg.from_email)
    # log_proposal_email(msg, proposal, sender, attachments)
    _log_approval_email(msg, mooring_licence, sender, attachments)
    return msg


def send_mla_approved_or_declined_email_new_renewal(proposal, decision, request, stickers_to_be_returned):
    # 23 ML new/renewal, approval/decline
    # email to applicant when application is issued or declined (mooring licence application, new and renewal)
    all_ccs = []
    all_bccs = []
    attach_invoice = False
    attach_licence_doc = False
    html_template = 'mooringlicensing/emails_2/'
    txt_template = 'mooringlicensing/emails_2/'

    subject = ''
    details = ''
    attachments = []
    payment_url = ''

    if decision == 'approved':
        # for payment
        html_template += 'email_23a.html'
        txt_template += 'email_23a.txt'
        subject = 'Payment Due: Application for Rottnest Island Mooring Site Licence'
        details = proposal.proposed_issuance_approval.get('details')
        cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(True, False, proposal)

        # Generate payment_url if needed
        if proposal.application_fees.count():
            application_fee = proposal.application_fees.first()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            if invoice.payment_status not in ('paid', 'over_paid'):
                # Payment required
                payment_url = '{}/application_fee_existing/{}'.format(get_public_url(request), proposal.id)
    elif decision == 'approved_paid':
        html_template += 'email_23b.html'
        txt_template += 'email_23b.txt'
        subject = 'Approved: Application for Rottnest Island Mooring Site Licence'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')

        attach_au_summary_doc = True if proposal.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,] else False
        attachments = get_attachments(False, True, proposal, attach_au_summary_doc)

    elif decision == 'declined':
        html_template += 'email_23c.html'
        txt_template += 'email_23c.txt'
        subject = 'Declined: Application for Rottnest Island Mooring Site Licence'
        details = proposal.proposaldeclineddetails.reason
        cc_list = proposal.proposaldeclineddetails.cc_email
        if cc_list:
            all_ccs = cc_list.split(',')

    else:
        logger.warning('Decision is unclear when sending AAA approved/declined email for {}'.format(proposal.lodgement_number))

    email = TemplateEmailBase(
        subject=subject,
        html_template=html_template,
        txt_template=txt_template,
    )

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,  # TODO: if existing sticker needs to be replaced, assign sticker object here.
        'payment_url': payment_url,
    }

    to_address = proposal.submitter.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)

    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_mla_approved_or_declined_email_amendment_payment_not_required(proposal, decision, request, stickers_to_be_returned):
    # 24 ML amendment(no payment), approval/decline
    # email to applicant when application is issued or declined (mooring licence application, amendment where no payment is required)
    all_ccs = []
    all_bccs = []
    attach_invoice = False
    attach_licence_doc = False

    subject = ''
    details = ''
    attachments = []

    if decision == 'approved':
        subject = 'Approved: Amendment Application for Rottnest Island Mooring Site Licence'
        details = proposal.proposed_issuance_approval.get('details')
        cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_au_summary_doc = True if proposal.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,] else False
        attachments = get_attachments(False, True, proposal, attach_au_summary_doc)
    elif decision == 'declined':
        subject = 'Declined: Amendment Application for Rottnest Island Mooring Site Licence'
        details = proposal.proposaldeclineddetails.reason
        cc_list = proposal.proposaldeclineddetails.cc_email
        if cc_list:
            all_ccs = cc_list.split(',')
    else:
        logger.warning('Decision is unclear when sending AAA approved/declined email for {}'.format(proposal.lodgement_number))

    email = TemplateEmailBase(
        subject=subject,
        html_template='mooringlicensing/emails_2/email_24.html',
        txt_template = 'mooringlicensing/emails_2/email_24.txt',
    )

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,  # TODO: if existing sticker needs to be replaced, assign sticker object here.
    }

    to_address = proposal.submitter.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)

    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_mla_approved_or_declined_email_amendment_payment_required(proposal, decision, request, stickers_to_be_returned):
    # 25 ML amendment(payment), approval/decline
    # email to applicant when application is issued or declined (mooring licence application, amendment where payment is required) 
    all_ccs = []
    all_bccs = []

    subject = ''
    details = ''
    attachments = []
    payment_url = ''
    html_template = 'mooringlicensing/emails_2/'
    txt_template = 'mooringlicensing/emails_2/'

    if decision == 'approved':
        # for payment
        html_template += 'email_25a.html'
        txt_template += 'email_25a.txt'
        subject = 'Payment Due: Amendment Application for Rottnest Island Mooring Site Licence'
        details = proposal.proposed_issuance_approval.get('details')
        cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_au_summary_doc = True if proposal.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,] else False
        attachments = get_attachments(True, False, proposal, attach_au_summary_doc)

        # Generate payment_url if needed
        if proposal.application_fees.count():
            application_fee = proposal.application_fees.first()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            if invoice.payment_status not in ('paid', 'over_paid'):
                # Payment required
                payment_url = '{}/application_fee_existing/{}'.format(get_public_url(request), proposal.id)
    elif decision == 'approved_paid':
        # after payment
        html_template += 'email_25b.html'
        txt_template += 'email_25b.txt'
        subject = 'Approved: Amendment Application for Rottnest Island Mooring Site Licence'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_au_summary_doc = True if proposal.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT,
                                                                        PROPOSAL_TYPE_RENEWAL, ] else False
        attachments = get_attachments(False, True, proposal, attach_au_summary_doc)
    elif decision == 'declined':
        # declined
        html_template += 'email_25c.html'
        txt_template += 'email_25c.txt'
        subject = 'Declined: Amendment Application for Rottnest Island Mooring Site Licence'
        details = proposal.proposaldeclineddetails.reason
        cc_list = proposal.proposaldeclineddetails.cc_email
        if cc_list:
            all_ccs = cc_list.split(',')
    else:
        logger.warning('Decision is unclear when sending AAA approved/declined email for {}'.format(proposal.lodgement_number))

    email = TemplateEmailBase(
        subject=subject,
        html_template=html_template,
        txt_template=txt_template,
    )

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'approval': proposal.approval,
        'recipient': proposal.submitter,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,  # TODO: if existing sticker needs to be replaced, assign sticker object here.
        'payment_url': payment_url,
    }

    to_address = proposal.submitter.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)

    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_other_documents_submitted_notification_email(request, proposal):
    email = TemplateEmailBase(
        subject='Application: {} is ready for assessment.  Other documents have been submitted.'.format(proposal.description),
        html_template='mooringlicensing/emails/send_documents_submitted_for_mla.html',
        txt_template='mooringlicensing/emails/send_documents_submitted_for_mla.txt',
    )
    url = request.build_absolute_uri(reverse('internal-proposal-detail', kwargs={'proposal_pk': proposal.id}))
    url = make_url_for_internal(url)

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'url': url,
    }
    to_address = proposal.assessor_recipients
    cc = []
    bcc = []

    attachments = []
    for my_file in proposal.mooring_report_documents.all():
        extract_file_for_attachment(attachments, my_file)
    for my_file in proposal.written_proof_documents.all():
        extract_file_for_attachment(attachments, my_file)
    for my_file in proposal.signed_licence_agreement_documents.all():
        extract_file_for_attachment(attachments, my_file)
    for my_file in proposal.proof_of_identity_documents.all():
        extract_file_for_attachment(attachments, my_file)

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=cc, bcc=bcc,)
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender, attachments=attachments)
    if proposal.org_applicant:
        _log_org_email(msg, proposal.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, proposal.submitter, proposal.submitter, sender=sender, attachments=attachments)

    return msg


def extract_file_for_attachment(attachments, my_file):
    if my_file._file is not None:
        file_name = my_file._file.name
        mime = mimetypes.guess_type(file_name)[0]
        if mime:
            attachment = (my_file.name, my_file._file.read(), mime)
            attachments.append(attachment)


def send_sticker_printing_batch_email(batches):
    if batches.count() == 0:
        return

    email = TemplateEmailBase(
        subject='Sticker Printing Batch',
        html_template='mooringlicensing/emails/send_sticker_printing_batch.html',
        txt_template='mooringlicensing/emails/send_sticker_printing_batch.txt',
    )

    attachments = []
    for batch in batches:
        if batch._file is not None:
            file_name = batch._file.name
            mime = mimetypes.guess_type(file_name)[0]
            if mime:
                attachment = (batch.name, batch._file.read(), mime)
                attachments.append(attachment)

    context = {
        'batches': batches,
        'public_url': get_public_url(),
    }

    from mooringlicensing.components.proposals.models import StickerPrintingContact
    tos = StickerPrintingContact.objects.filter(type=StickerPrintingContact.TYPE_EMIAL_TO, enabled=True)
    ccs = StickerPrintingContact.objects.filter(type=StickerPrintingContact.TYPE_EMAIL_CC, enabled=True)
    bccs = StickerPrintingContact.objects.filter(type=StickerPrintingContact.TYPE_EMAIL_BCC, enabled=True)

    to_address = [contact.email for contact in tos]
    cc = [contact.email for contact in ccs]
    bcc = [contact.email for contact in bccs]

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=cc, bcc=bcc,)

    return msg


def send_endorsement_of_authorised_user_application_email(request, proposal):
    email = TemplateEmailBase(
        subject='Endorsement of Authorised user application',
        html_template='mooringlicensing/emails/send_endorsement_of_aua.html',
        txt_template='mooringlicensing/emails/send_endorsement_of_aua.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    endorse_url = url + reverse('endorse-url', kwargs={'uuid_str': proposal.uuid})
    decline_url = url + reverse('decline-url', kwargs={'uuid_str': proposal.uuid})
    proposal_url = url + reverse('external-proposal-detail', kwargs={'proposal_pk': proposal.id})

    try:
        endorser = EmailUser.objects.get(email=proposal.site_licensee_email)
    except:
        # Should not reach here
        return

    mooring_name = proposal.mooring.name if proposal.mooring else ''
    due_date = proposal.get_due_date_for_endorsement_by_target_date()

    # Configure recipients, contents, etc
    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'endorser': endorser,
        'applicant': proposal.submitter,
        'endorse_url': endorse_url,
        'decline_url': decline_url,
        'proposal_url': proposal_url,
        'mooring_name': mooring_name,
        'due_date': due_date,
    }

    to_address = proposal.site_licensee_email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    # sender = request.user if request else settings.DEFAULT_FROM_EMAIL
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender)

    return msg


def send_proposal_approver_sendback_email_notification(request, proposal):
    email = TemplateEmailBase(
        subject='An Application has been sent back by approver.',
        html_template='mooringlicensing/emails/send_approver_sendback_notification.html',
        txt_template='mooringlicensing/emails/send_approver_sendback_notification.txt',
    )
    url = request.build_absolute_uri(reverse('internal-proposal-detail', kwargs={'proposal_pk': proposal.id}))
    url = make_url_for_internal(url)

    if 'test-emails' in request.path_info:
        approver_comment = 'This is my test comment'
    else:
        approver_comment = proposal.approver_comment

    context = {
        'public_url': get_public_url(request),
        'proposal': proposal,
        'recipient': proposal.submitter,
        'url': url,
        'approver_comment': approver_comment
    }

    msg = email.send(proposal.assessor_recipients, context=context)
    # sender = request.user if request else settings.DEFAULT_FROM_EMAIL
    sender = get_user_as_email_user(msg.from_email)
    log_proposal_email(msg, proposal, sender)
    return msg




# Followings are in the approval/email
# 26 DCVPermit
# 27 DCVAdmission
# 28 Cancelled
# 29 Suspended
# 30 Surrendered
# 31 Reinstated

