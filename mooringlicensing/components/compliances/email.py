import logging

from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.utils.encoding import smart_str
from django.urls import reverse
from django.conf import settings

from mooringlicensing.components.emails.emails import TemplateEmailBase
from ledger_api_client.ledger_models import EmailUserRO as EmailUser

from mooringlicensing.components.emails.utils import get_public_url, make_http_https
from mooringlicensing.components.users.utils import _log_user_email

logger = logging.getLogger(__name__)

SYSTEM_NAME = settings.SYSTEM_NAME_SHORT + ' Automated Message'


class ComplianceExternalSubmitSendNotificationEmail(TemplateEmailBase):
    subject = 'Compliance Requirement Submission - Rottnest Island Authority'
    html_template = 'mooringlicensing/emails/send_external_submit_notification.html'
    txt_template = 'mooringlicensing/emails/send_external_submit_notification.txt'


class ComplianceSubmitSendNotificationEmail(TemplateEmailBase):
    subject = 'A new Compliance has been submitted.'
    html_template = 'mooringlicensing/emails/send_submit_notification.html'
    txt_template = 'mooringlicensing/emails/send_submit_notification.txt'


class ComplianceAcceptNotificationEmail(TemplateEmailBase):
    subject = 'Approved: Compliance Requirement Submission - Rottnest Island Authority'
    html_template = 'mooringlicensing/emails/compliance_accept_notification.html'
    txt_template = 'mooringlicensing/emails/compliance_accept_notification.txt'


class ComplianceAmendmentRequestSendNotificationEmail(TemplateEmailBase):
    subject = 'Licence/Permit requirement.'
    html_template = 'mooringlicensing/emails/send_amendment_notification.html'
    txt_template = 'mooringlicensing/emails/send_amendment_notification.txt'


class ComplianceReminderNotificationEmail(TemplateEmailBase):
    subject = 'Compliance Requirement Overdue - Rottnest Island Authority'
    html_template = 'mooringlicensing/emails/send_reminder_notification.html'
    txt_template = 'mooringlicensing/emails/send_reminder_notification.txt'


class ComplianceInternalReminderNotificationEmail(TemplateEmailBase):
    subject = 'A Compliance with requirements has passed the due date.'
    html_template = 'mooringlicensing/emails/send_internal_reminder_notification.html'
    txt_template = 'mooringlicensing/emails/send_internal_reminder_notification.txt'


class ComplianceDueNotificationEmail(TemplateEmailBase):
    subject = 'Compliance Requirement Due - Rottnest Island Authority'
    html_template = 'mooringlicensing/emails/send_due_notification.html'
    txt_template = 'mooringlicensing/emails/send_due_notification.txt'


class ComplianceInternalDueNotificationEmail(TemplateEmailBase):
    subject = 'A Compliance with requirements is due for submission.'
    html_template = 'mooringlicensing/emails/send_internal_due_notification.html'
    txt_template = 'mooringlicensing/emails/send_internal_due_notification.txt'


def send_amendment_email_notification(amendment_request, request, compliance, is_test=False):
    email = ComplianceAmendmentRequestSendNotificationEmail()
    reason = amendment_request.reason.reason
    url = request.build_absolute_uri(reverse('external-compliance-detail',kwargs={'compliance_pk': compliance.id}))
    url = ''.join(url.split('-internal'))
    login_url = request.build_absolute_uri(reverse('external'))
    login_url = ''.join(login_url.split('-internal'))
    context = {
        'compliance': compliance,
        'reason': reason,
        'amendment_request_text': amendment_request.text,
        'url': make_http_https(url),
        'public_url': get_public_url(),
    }

    holder = compliance.holder_obj.email if compliance.holder_obj and compliance.holder_obj.email else compliance.proposal.applicant_obj.email
    all_ccs = []
    msg = email.send(holder,cc=all_ccs, context=context)
    if is_test:
        return
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_compliance_email(msg, compliance, sender=sender)
        _log_user_email(msg, compliance.proposal.applicant_obj, compliance.holder_id, sender=sender)


#send reminder emails if Compliance has not been lodged by due date. Used in Cron job so cannot use 'request' parameter
def send_reminder_email_notification(compliance, is_test=False):
    """ Used by the management command, therefore have no request object - therefore explicitly defining base_url """
    email = ComplianceReminderNotificationEmail()
    url=settings.SITE_URL if settings.SITE_URL else ''
    url+=reverse('external-compliance-detail',kwargs={'compliance_pk': compliance.id})
    login_url=settings.SITE_URL if settings.SITE_URL else ''
    login_url+=reverse('external')

    recipient = None
    if compliance.proposal and compliance.proposal.applicant_obj:
        recipient = compliance.proposal.applicant_obj

    context = {
        'compliance': compliance,
        'url': make_http_https(url),
        'login_url': login_url,
        'public_url': get_public_url(),
        'recipient': recipient,
    }

    holder = compliance.holder_obj.email if compliance.holder_obj and compliance.holder_obj.email else compliance.proposal.applicant_obj.email
    all_ccs = []
    msg = email.send(holder, cc=all_ccs, context=context)
    if is_test:
        return
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        try:
            sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
        except:
            sender_user = None

        _log_compliance_email(msg, compliance, sender=sender_user)
        _log_user_email(msg, compliance.proposal.applicant_obj, compliance.holder_obj, sender=sender_user)


def send_internal_reminder_email_notification(compliance, is_test=False):
    from mooringlicensing.components.emails.utils import make_url_for_internal
    email = ComplianceInternalReminderNotificationEmail()
    url = settings.SITE_URL
    url += reverse('internal-compliance-detail', kwargs={'compliance_pk': compliance.id})
    url = make_url_for_internal(url)

    context = {
        'compliance': compliance,
        'url': make_http_https(url),
        'public_url': get_public_url(),
    }

    msg = email.send(compliance.proposal.assessor_recipients, context=context)
    if is_test:
        return
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        try:
            sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
        except:
            sender_user = None

        _log_compliance_email(msg, compliance, sender=sender_user)
        _log_user_email(msg, compliance.proposal.applicant_obj, compliance.holder_id, sender=sender_user)


def send_due_email_notification(compliance, is_test=False):
    email = ComplianceDueNotificationEmail()
    url = settings.SITE_URL
    url += reverse('external-compliance-detail', kwargs={'compliance_pk': compliance.id})

    holder = compliance.holder_obj if compliance.holder_obj and compliance.holder_obj.email else compliance.proposal.applicant_obj

    context = {
        'recipient': holder,
        'compliance': compliance,
        'due_date': compliance.due_date.strftime('%d/%m/%Y'),
        'external_compliance_url': make_http_https(url),
        'public_url': get_public_url(),
    }

    all_ccs = []
    msg = email.send(holder.email, cc=all_ccs, context=context)
    if is_test:
        return
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        try:
            sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
        except:
            sender_user = None

        _log_compliance_email(msg, compliance, sender=sender_user)
        _log_user_email(msg, compliance.proposal.applicant_obj, compliance.holder_id, sender=sender_user)


def send_internal_due_email_notification(compliance, is_test=False):
    from mooringlicensing.components.emails.utils import make_url_for_internal

    email = ComplianceInternalDueNotificationEmail()
    url = settings.SITE_URL
    url += reverse('internal-compliance-detail', kwargs={'compliance_pk': compliance.id})
    url = make_url_for_internal(url)

    context = {
        'compliance': compliance,
        'url': make_http_https(url),
        'public_url': get_public_url(),
    }

    msg = email.send(compliance.proposal.assessor_recipients, context=context)
    if is_test:
        return
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        try:
            sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
        except:
            sender_user = None
        _log_compliance_email(msg, compliance, sender=sender_user)
        _log_user_email(msg, compliance.proposal.applicant_obj, compliance.holder_id, sender=sender_user)


def send_compliance_accept_email_notification(compliance,request, is_test=False):
    email = ComplianceAcceptNotificationEmail()

    holder = compliance.holder_obj if compliance.holder_obj else compliance.proposal.applicant_obj
    context = {
        'compliance': compliance,
        'public_url': get_public_url(),
        'recipient': holder,
    }
    all_ccs = []
    msg = email.send(holder.email, cc=all_ccs, context=context)
    if is_test:
        return
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_compliance_email(msg, compliance, sender=sender)
        _log_user_email(msg, compliance.proposal.applicant_obj, compliance.holder_id, sender=sender)


def send_external_submit_email_notification(request, compliance, is_test=False):
    email = ComplianceExternalSubmitSendNotificationEmail()
    url = request.build_absolute_uri(reverse('external-compliance-detail',kwargs={'compliance_pk': compliance.id}))
    url = ''.join(url.split('-internal'))
    holder = compliance.holder_obj if compliance.holder_obj and compliance.holder_obj.email else compliance.proposal.applicant_obj

    context = {
        'compliance': compliance,
        'recipient': holder,
        'url': make_http_https(url),
        'due_date': compliance.due_date.strftime('%d/%m/%Y'),
        'public_url': get_public_url(),
    }
    all_ccs = []
    msg = email.send(holder.email,cc=all_ccs, context=context)
    if is_test:
        return
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_compliance_email(msg, compliance, sender=sender)
        _log_user_email(msg, compliance.proposal.applicant_obj, compliance.holder_id, sender=sender)


def send_submit_email_notification(request, compliance, is_test=False):
    from mooringlicensing.components.emails.utils import make_url_for_internal

    email = ComplianceSubmitSendNotificationEmail()
    url = request.build_absolute_uri(reverse('internal-compliance-detail', kwargs={'compliance_pk': compliance.id}))
    url = make_url_for_internal(url)

    context = {
        'compliance': compliance,
        'url': make_http_https(url),
        'public_url': get_public_url(),
    }

    msg = email.send(compliance.proposal.assessor_recipients, context=context)
    if is_test:
        return
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_compliance_email(msg, compliance, sender=sender)
        _log_user_email(msg, compliance.proposal.applicant_obj, compliance.holder_id, sender=sender)


def _log_compliance_email(email_message, compliance, sender=None):
    from mooringlicensing.components.compliances.models import ComplianceLogEntry
    if isinstance(email_message, (EmailMultiAlternatives, EmailMessage,)):
        text = email_message.body
        subject = email_message.subject
        fromm = smart_str(sender) if sender else smart_str(email_message.from_email)
        # the to email is normally a list
        if isinstance(email_message.to, list):
            to = ','.join(email_message.to)
        else:
            to = smart_str(email_message.to)
        # we log the cc and bcc in the same cc field of the log entry as a ',' comma separated string
        all_ccs = []
        if email_message.cc:
            all_ccs += list(email_message.cc)
        if email_message.bcc:
            all_ccs += list(email_message.bcc)
        all_ccs = ','.join(all_ccs)

    else:
        text = smart_str(email_message)
        subject = ''
        to = compliance.holder_obj.email
        fromm = smart_str(sender) if sender else SYSTEM_NAME
        all_ccs = ''

    customer = compliance.holder_id

    if isinstance(sender, EmailUser):
        staff = sender
    else:
        staff = EmailUser.objects.get(sender)

    kwargs = {
        'subject': subject,
        'text': text,
        'compliance': compliance,
        'customer': customer,
        'staff': staff.id,
        'to': to,
        'fromm': fromm,
        'cc': all_ccs
    }

    email_entry = ComplianceLogEntry.objects.create(**kwargs)

    return email_entry