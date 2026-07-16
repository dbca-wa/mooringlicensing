import logging
import mimetypes
import pytz
import requests
from ledger_api_client.ledger_models import EmailUserRO as EmailUser, Invoice

from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.utils.encoding import smart_str
from django.urls import reverse
from django.conf import settings
from django.core.files.base import ContentFile

from mooringlicensing.components.approvals.email import log_mla_created_proposal_email, _log_approval_email
from mooringlicensing.components.compliances.email import _log_compliance_email
from mooringlicensing.components.emails.emails import TemplateEmailBase
from datetime import datetime

from mooringlicensing.components.main.models import NumberOfDaysType, NumberOfDaysSetting, private_storage, FileExtensionWhitelist
from mooringlicensing.components.emails.utils import get_user_as_email_user, make_url_for_internal, get_public_url, \
    make_http_https
from mooringlicensing.components.users.utils import _log_user_email
from mooringlicensing.ledger_api_utils import retrieve_email_userro, get_invoice_payment_status
from mooringlicensing.settings import CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA, CODE_DAYS_IN_PERIOD_MLA, \
    PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_SWAP_MOORINGS, MOORING_LICENSING_EXTERNAL_URL

logger = logging.getLogger(__name__)

SYSTEM_NAME = settings.SYSTEM_NAME_SHORT + ' Automated Message'


def log_proposal_email(msg, proposal, sender, attachments=[]):
    try:
        sender_user = sender if isinstance(sender, EmailUser) else EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
    except:
        sender_user = None

    _log_proposal_email(msg, proposal, sender=sender_user, attachments=attachments)
    _log_user_email(msg, proposal.applicant_obj, proposal.applicant_obj, sender=sender_user, attachments=attachments)


def _log_proposal_email(email_message, proposal, sender=None, file_bytes=None, filename=None, attachments=[]):
    from mooringlicensing.components.proposals.models import ProposalLogEntry
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
        to = proposal.applicant_obj.email
        fromm = smart_str(sender) if sender else SYSTEM_NAME
        all_ccs = ''

    customer = proposal.applicant_obj

    staff = sender.id

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
        check = attachment[0].split(".")
        filename = attachment[0]
        try:
            if len(check) < 2 or not FileExtensionWhitelist.objects.filter(name=check[len(check)-1].lower()).exists():
                filename = attachment[0] + ".pdf"
        except Exception as e:
            logger.error(e)
            filename = attachment[0] + ".pdf"
        email_entry_document = email_entry.documents.create(name=filename)
        email_entry_document._file.save(filename, ContentFile(attachment[1]), save=False)
        email_entry_document.save()

    return email_entry


def send_confirmation_email_upon_submit(request, proposal, payment_made, attachments=[]):
    # 1 a and b
    if proposal.no_email_notifications:
        return

    if payment_made:
        subject='Submission Received: Application {}  - Rottnest Island Authority'.format(proposal.lodgement_number)
    else:
        subject='Submission Received: Application {} - Rottnest Island Authority'.format(proposal.lodgement_number)
    email = TemplateEmailBase(
        subject=subject,
        html_template='mooringlicensing/emails_2/email_1a_and_b.html',
        txt_template='mooringlicensing/emails_2/email_1a_and_b.txt',
    )

    # Configure recipients, contents, etc
    context = {
        'public_url': get_public_url(),
        'dashboard_external_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'payment_made': payment_made,
    }
    to_address = proposal.applicant_obj.email
    cc = []
    bcc = proposal.assessor_recipients

    # Send email
    # in send() method, self.html_template is rendered by context and attached as alternative
    # In other words, self.html_template should be full html-email
    msg = email.send(to_address, context=context, attachments=attachments, cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)

    return msg


def send_notification_email_upon_submit_to_assessor(request, proposal, attachments=[]):
    # 2
    if proposal.no_email_notifications:
        return
    
    email = TemplateEmailBase(
        subject='Assessment required: a new application submission is awaiting assessment',
        html_template='mooringlicensing/emails_2/email_2.html',
        txt_template='mooringlicensing/emails_2/email_2.txt',
    )

    url = request.build_absolute_uri(reverse('internal-proposal-detail', kwargs={'proposal_pk': proposal.id}))
    url = make_url_for_internal(url)

    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'proposal_internal_url': url,
    }
    to_address = proposal.assessor_recipients
    cc = []
    bcc = []

    # Send email
    # in send() method, self.html_template is rendered by context and attached as alternative
    # In other words, self.html_template should be full html-email
    msg = email.send(to_address, context=context, attachments=attachments, cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)

    return msg


def send_approver_approve_decline_email_notification(request, proposal):
    # 3
    if proposal.no_email_notifications:
        return
    
    email = TemplateEmailBase(
        subject='Approval required: an assessed application is awaiting approval or decline',
        html_template='mooringlicensing/emails_2/email_3.html',
        txt_template='mooringlicensing/emails_2/email_3.txt',
    )
    url = request.build_absolute_uri(reverse('internal-proposal-detail', kwargs={'proposal_pk': proposal.id}))
    url = make_url_for_internal(url)

    context = {
        'public_url': get_public_url(),
        'details': proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else '',
        'proposal': proposal,
        'proposal_internal_url': url
    }

    msg = email.send(proposal.approver_recipients, context=context)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender)
    return msg


def send_amendment_email_notification(amendment_request, request, proposal):
    # 5
    if proposal.no_email_notifications:
        return
    
    application_type = None
    if proposal.application_type and proposal.application_type.description:
        application_type = proposal.application_type.description

    email = TemplateEmailBase(
        subject='Amendment Required: {} {} - Rottnest Island Authority'.format(application_type ,proposal.lodgement_number),
        html_template='mooringlicensing/emails_2/email_5.html',
        txt_template='mooringlicensing/emails_2/email_5.txt',
    )

    reason = amendment_request.reason.reason
    url = MOORING_LICENSING_EXTERNAL_URL + reverse('external-proposal-detail', kwargs={'proposal_pk': proposal.id})

    context = {
        'public_url': get_public_url(),
        'recipient': proposal.proposal_applicant,
        'proposal': proposal,
        'reason': reason,
        'text': amendment_request.text,
        'proposal_external_url': url,
    }

    to = proposal.applicant_obj.email
    all_ccs = []
    msg = email.send(to, cc=all_ccs, context=context)
    if msg:
        sender = get_user_as_email_user(msg.from_email)

        _log_proposal_email(msg, proposal, sender=sender)
        _log_user_email(msg, proposal.applicant_obj, proposal.applicant_obj, sender=sender)


def send_create_mooring_licence_application_email_notification(request, waiting_list_allocation, mooring_licence_application):
    # 6
    if mooring_licence_application.no_email_notifications:
        return
    
    allocated_mooring = mooring_licence_application.allocated_mooring
    email = TemplateEmailBase(
        subject='Offer for Mooring Site Licence {} - Rottnest Island Authority'.format(allocated_mooring.name),
        html_template='mooringlicensing/emails_2/email_6.html',
        txt_template='mooringlicensing/emails_2/email_6.txt',
    )

    ria_generated_proposal = waiting_list_allocation.ria_generated_proposal.all()[0] if waiting_list_allocation.ria_generated_proposal.all() else None

    url = MOORING_LICENSING_EXTERNAL_URL + reverse('external-proposal-detail', kwargs={'proposal_pk': mooring_licence_application.id})

    today = datetime.now(pytz.timezone(settings.TIME_ZONE)).date()
    days_type = NumberOfDaysType.objects.filter(code=CODE_DAYS_IN_PERIOD_MLA).first()
    days_setting_application_period = NumberOfDaysSetting.get_setting_by_date(days_type, today)
    days_type = NumberOfDaysType.objects.filter(code=CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA).first()
    days_setting_documents_period = NumberOfDaysSetting.get_setting_by_date(days_type, today)
    details = request.data.get('message_details', '')

    context = {
        'public_url': get_public_url(),
        'wla': waiting_list_allocation,
        'recipient': mooring_licence_application.applicant_obj,
        'application_period': days_setting_application_period.number_of_days,
        'documents_period': days_setting_documents_period.number_of_days,
        'proposal_external_url': url,
        'details': details,
    }
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
    except:
        sender_user = None

    attachments = []
    if waiting_list_allocation.waiting_list_offer_documents.all():
        for doc in waiting_list_allocation.waiting_list_offer_documents.all():
            file_name = doc.name
            attachment = (file_name, doc._file.file.read())
            attachments.append(attachment)

    bcc = request.data.get('cc_email')
    bcc_list = bcc.split(',')
    msg = None
    if mooring_licence_application.applicant_obj:
        msg = email.send(mooring_licence_application.applicant_obj.email, bcc=bcc_list, attachments=attachments, context=context)
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        log_mla_created_proposal_email(msg, ria_generated_proposal, sender=sender_user)
        _log_user_email(msg, mooring_licence_application.applicant_obj.id, mooring_licence_application.applicant_obj.id, sender=sender_user, attachments=attachments)


def send_documents_upload_for_mooring_licence_application_email(request, proposal):
    # 7
    if proposal.no_email_notifications:
        return
    
    allocated_mooring = proposal.allocated_mooring
    email = TemplateEmailBase(
        subject='Additional documents required: Application for mooring site licence {} - Rottnest Island Authority'.format(allocated_mooring.name),
        html_template='mooringlicensing/emails_2/email_7.html',
        txt_template='mooringlicensing/emails_2/email_7.txt',
    )

    today = datetime.now(pytz.timezone(settings.TIME_ZONE)).date()
    days_type = NumberOfDaysType.objects.filter(code=CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA).first()
    days_setting = NumberOfDaysSetting.get_setting_by_date(days_type, today)

    url = request.build_absolute_uri(reverse('external-proposal-detail', kwargs={'proposal_pk': proposal.id}))

    # Configure recipients, contents, etc
    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'proposal_external_url': make_http_https(url),
        'num_of_days_to_submit_documents': days_setting.number_of_days,
    }
    to_address = proposal.applicant_obj.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        _log_proposal_email(msg, proposal, sender=sender)
        _log_user_email(msg, proposal.applicant_obj, proposal.applicant_obj, sender=sender)

    return msg


def send_compliance_due_date_notification(approval, compliance,):
    #  8
    email = TemplateEmailBase(
        subject='Due: Compliance requirement for permit or licence - Deadline {} - Rottnest Island Authority'.format(compliance.due_date),
        html_template='mooringlicensing/emails_2/email_8.html',
        txt_template='mooringlicensing/emails_2/email_8.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    url = url + reverse('external-compliance-detail')

    context = {
        'public_url': get_public_url(),
        'approval': approval,
        'compliance': compliance,
        'recipient': compliance.holder_obj,
        'compliance_external_url': make_http_https(url),
    }
    to_address = retrieve_email_userro(compliance.submitter).email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        _log_compliance_email(msg, compliance, sender=sender)
        _log_user_email(msg, compliance.proposal.applicant_obj, compliance.submitter, sender=sender)
    return msg


def send_compliance_overdue_notification(request, approval, compliance,):
    # 9
    email = TemplateEmailBase(
        subject='OVERDUE: Compliance requirement for permit or licence - Rottnest Island Authority',
        html_template='mooringlicensing/emails_2/email_9.html',
        txt_template='mooringlicensing/emails_2/email_9.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    url = url + reverse('external-compliance-detail')

    context = {
        'public_url': get_public_url(),
        'approval': approval,
        'compliance': compliance,
        'recipient': compliance.holder_obj,
        'compliance_external_url': make_http_https(url),
    }
    to_address = retrieve_email_userro(compliance.submitter).email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        _log_compliance_email(msg, compliance, sender=sender)
        _log_user_email(msg, compliance.proposal.applicant_obj, compliance.submitter, sender=sender)
    return msg

# 10
# send_vessel_nomination_reminder_mail() at approval.email.py

def send_invitee_reminder_email(approval, due_date, request=None):
    # 11
    proposal = approval.current_proposal
    if proposal.no_email_notifications:
        return
    allocated_mooring = proposal.allocated_mooring
    email = TemplateEmailBase(
        subject='REMINDER : Your Offer for mooring site licence {} is about to lapse - Rottnest Island Authority'.format(allocated_mooring.name),
        html_template='mooringlicensing/emails_2/email_11.html',
        txt_template='mooringlicensing/emails_2/email_11.txt',
    )
    
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
    except:
        sender_user = None
        
    context = {
        'public_url': get_public_url(),
        'approval': approval,
        'recipient': proposal.proposal_applicant,
        'due_date': due_date,
    }
    to_address = approval.applicant_obj.email
    all_ccs = []
    bcc = []

    msg = email.send(to_address, context=context, attachments=[], cc=all_ccs, bcc=bcc,)
    if msg:
        _log_approval_email(msg, approval, sender=sender_user)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender_user)

def send_expire_application_email(proposal, due_date,):
    if proposal.no_email_notifications:
        return

    html_template = 'mooringlicensing/emails_2/application_expire_notification.html'
    txt_template = 'mooringlicensing/emails_2/application_expire_notification.txt'

    email = TemplateEmailBase(
        subject='Expired: Authorised User Permit {} - Rottnest Island Authority'.format(proposal.lodgement_number),
        html_template=html_template,
        txt_template=txt_template,
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    dashboard_url = url + reverse('external')

    # Configure recipients, contents, etc
    context = {
        'url': url,
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'dashboard_url': make_http_https(dashboard_url),
    }
    to_address = proposal.applicant_obj.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender)
    return msg

def send_expire_notification_to_assessor(proposal, due_date):
    if proposal.no_email_notifications:
        return
    email = TemplateEmailBase(
        subject='Expired application - not paid on time',
        html_template='mooringlicensing/emails_2/assessor_expiry_notification.html',
        txt_template='mooringlicensing/emails_2/assessor_expiry_notification.txt',
    )

    context = {
        'public_url': get_public_url(),
        'applicant': proposal.applicant_obj,
        'due_date': due_date,
        'recipient': proposal.proposal_applicant,
        'proposal': proposal
    }

    to_address = proposal.assessor_recipients
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender)
    return msg

def send_payment_reminder_email(proposal, request=None):
    if proposal.no_email_notifications:
        return
    email = TemplateEmailBase(
        subject='Payment reminder: Application {} - Rottnest Island Authority'.format(proposal.lodgement_number),
        html_template='mooringlicensing/emails_2/application_payment_reminder.html',
        txt_template='mooringlicensing/emails_2/application_payment_reminder.txt',
    )

    url = settings.SITE_URL if settings.SITE_URL else ''

    due_date = proposal.payment_due_date

    # Configure recipients, contents, etc
    context = {
        'url': url,
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'applicant': proposal.applicant_obj,
        'due_date': due_date,
    }
    to_address = proposal.applicant_obj.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender)

    return msg


def send_expire_mooring_licence_application_email(proposal, reason, due_date,):
    # 12 email to mooring licence applicant when mooring licence application is not submitted within configurable
    #    number of days after being invited to apply for a mooring licence

    if proposal.no_email_notifications:
        return
    
    allocated_mooring = proposal.allocated_mooring
    html_template = 'mooringlicensing/emails_2/email_12.html'
    txt_template = 'mooringlicensing/emails_2/email_12.txt'

    email = TemplateEmailBase(
        subject='Lapsed: Offer for mooring site Licence {} - Rottnest Island Authority'.format(allocated_mooring.name),
        html_template=html_template,
        txt_template=txt_template,
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    dashboard_url = url + reverse('external')

    # Configure recipients, contents, etc
    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'dashboard_url': make_http_https(dashboard_url),
    }
    to_address = proposal.applicant_obj.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender)
    return msg


def send_expire_mooring_licence_by_no_documents_email(proposal, reason, due_date,):
    # 13
    # Expire mooring licence application if additional documents are not submitted within a configurable number of days
    # from the initial submit of the mooring licence application and email to inform the applicant

    if proposal.no_email_notifications:
        return
    
    html_template = 'mooringlicensing/emails_2/email_13.html'
    txt_template = 'mooringlicensing/emails_2/email_13.txt'
    allocated_mooring = proposal.allocated_mooring
    email = TemplateEmailBase(
        subject='Lapsed: Offer for mooring site licence {} - Rottnest Island Authority'.format(allocated_mooring.name),
        html_template=html_template,
        txt_template=txt_template,
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    dashboard_url = url + reverse('external')

    # Configure recipients, contents, etc
    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'dashboard_url': make_http_https(dashboard_url),
    }
    to_address = proposal.applicant_obj.email
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender)
    return msg


def send_expire_mla_notification_to_assessor(proposal, reason, due_date):
    # 14
    # email to assessor group when invite to apply for a mooring licence is expired, either because mooring licence is not submitted or additional documents are not submitted
    # (internal)

    if proposal.no_email_notifications:
        return
    
    email = TemplateEmailBase(
        subject='Expired mooring site licence application - not submitted on time',
        html_template='mooringlicensing/emails_2/email_14.html',
        txt_template='mooringlicensing/emails_2/email_14.txt',
    )

    mooring_name = proposal.mooring.name if proposal.mooring else ''

    context = {
        'public_url': get_public_url(),
        'applicant': proposal.applicant_obj,
        'due_date': due_date,
        'mooring_name': mooring_name,
        'recipient': proposal.proposal_applicant
    }

    to_address = proposal.assessor_recipients
    cc = []
    bcc = []

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender)
    return msg


def send_endorser_reminder_email(proposal, request=None):

    if proposal.no_email_notifications:
        return
    
    allocated_mooring = proposal.allocated_mooring
    # 15
    # email to authorised user application endorser if application is not endorsed or declined within configurable number of days
    email = TemplateEmailBase(
        subject='Endorsement request: Application for authorised use of {} - Rottnest Island Authority'.format(allocated_mooring.name),
        html_template='mooringlicensing/emails_2/email_15.html',
        txt_template='mooringlicensing/emails_2/email_15.txt',
    )

    url = settings.SITE_URL if settings.SITE_URL else ''
    endorse_url = url + reverse('endorse-url', kwargs={'uuid_str': proposal.uuid})
    decline_url = url + reverse('decline-url', kwargs={'uuid_str': proposal.uuid})
    proposal_url = url + reverse('external-proposal-detail', kwargs={'proposal_pk': proposal.id})

    msgs = []
    for site_licensee_mooring in proposal.site_licensee_mooring_request.filter(enabled=True,endorser_reminder_sent=False):
        try:
            endorser = EmailUser.objects.filter(email__iexact=site_licensee_mooring.site_licensee_email, is_active=True).order_by('-id').first()
        except:
            # Should not reach here
            continue

        mooring_name = site_licensee_mooring.mooring.name if proposal.mooring else ''
        due_date = proposal.get_due_date_for_endorsement_by_target_date()

        # Configure recipients, contents, etc
        context = {
            'public_url': get_public_url(),
            'proposal': proposal,
            'recipient': proposal.proposal_applicant,
            'endorser': endorser,
            'applicant': proposal.proposal_applicant,
            'endorse_url': make_http_https(endorse_url),
            'decline_url': make_http_https(decline_url),
            'proposal_url': make_http_https(proposal_url),
            'mooring_name': mooring_name,
            'due_date': due_date,
        }
        to_address = site_licensee_mooring.site_licensee_email
        cc = []
        bcc = []

        # Send email
        try:
            msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
            if msg:
                sender = get_user_as_email_user(msg.from_email)
                log_proposal_email(msg, proposal, sender)
                site_licensee_mooring.endorser_reminder_sent = True
                site_licensee_mooring.save()
                msgs.append(msg)
        except Exception as e:
            err_msg = 'Error sending reminder to endorser for Proposal {}'.format(proposal.lodgement_number)
            logger.error('{}\n{}'.format(err_msg, str(e)))

    return msgs


def send_approval_renewal_email_notification(approval):
    # 16
    # email as renewal reminders for waiting list allocations, annual admission permits, authorised user permits,
    # mooring licences and dcv permits a configurable number of days before the expiry date, including if the status
    # is suspended (technically dcv permits are not renewed, the holder is invited to apply for a new one for the next season)
    
    current_year = datetime.now().year
    next_fee_season = f"{current_year} - {current_year + 1}"
    proposal = approval.current_proposal

    vessel_owned = False
    if proposal.vessel_ownership.end_date == None:
        vessel_owned = True

    if vessel_owned:
        subject = 'Invitation to renew your {} for {} - vessel {} - Rottnest Island Authority'.format(approval.description, next_fee_season, proposal.vessel_details.vessel.rego_no)
    else:
        subject = 'Invitation to renew your {} for {} - Rottnest Island Authority'.format(approval.description, next_fee_season)

    if approval.code == 'ml':
        subject= 'Invitation to renew {} {} for {} season - {} - Rottnest Island Authority'.format(approval.description, approval.child_obj.mooring.name, next_fee_season, proposal.proposal_applicant.get_full_name())

    email = TemplateEmailBase(
        subject=subject,
        html_template='mooringlicensing/emails_2/email_16.html',
        txt_template='mooringlicensing/emails_2/email_16.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    url = url + reverse('external')

    context = {
        'public_url': get_public_url(),
        'approval': approval,
        'vessel_owned': vessel_owned,
        'vessel_rego_no': proposal.vessel_details.vessel.rego_no,
        'recipient': proposal.proposal_applicant,
        'expiry_date': approval.expiry_date,
        'dashboard_external_url': make_http_https(url),
        'mooring': approval.child_obj.mooring.name if approval.code == 'ml' else None
    }

    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
    except:
        sender_user = None

    attachments = []
    attachment = approval.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    msg = email.send(proposal.applicant_obj.email, cc=[], attachments=attachments, context=context)
    if msg:
        from mooringlicensing.components.approvals.models import Approval
        if isinstance(approval, Approval):
            _log_approval_email(msg, approval, sender=sender_user)
            _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender_user, attachments=attachments)


def send_application_approved_or_declined_email(proposal, decision, request, stickers_to_be_returned=[]):
    # 17 --- 25
    # email to applicant when application is issued or declined (waiting list allocation application)

    if proposal.no_email_notifications:
        return
    
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
            payment_required = proposal.payment_required()
            if payment_required:
                # 22 (22a, 22b, 50a)
                send_aua_approved_or_declined_email_amendment_payment_required(proposal, decision, request, stickers_to_be_returned)
            else:
                # 21
                send_aua_approved_or_declined_email_amendment_payment_not_required(proposal, decision, request, stickers_to_be_returned)
        else:
            pass
    elif proposal.application_type.code == MooringLicenceApplication.code:
        if proposal.proposal_type.code in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL]:
            # 23
            send_mla_approved_or_declined_email_new_renewal(proposal, decision, request, stickers_to_be_returned)
        elif proposal.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
            payment_required = False
            if proposal.application_fees.filter(cancelled=False).count() and proposal.get_main_application_fee():
                application_fee = proposal.get_main_application_fee()
                invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
                if get_invoice_payment_status(invoice.id) not in ('paid', 'over_paid'):
                    payment_required = True
            if payment_required:
                # 25
                send_mla_approved_or_declined_email_amendment_payment_required(proposal, decision, request, stickers_to_be_returned)
            else:
                # 24
                send_mla_approved_or_declined_email_amendment_payment_not_required(proposal, decision, request, stickers_to_be_returned)
        elif proposal.proposal_type.code == PROPOSAL_TYPE_SWAP_MOORINGS:
            send_mla_approved_or_declined_email_swap_mooring(proposal, decision, request, stickers_to_be_returned)
    else:
        # Should not reach here
        logger.warning('The type of the proposal {} is unknown'.format(proposal.lodgement_number))


def send_wla_approved_or_declined_email(proposal, decision, request):
    # 17 a and b
    # email to applicant when application is issued or declined (waiting list allocation application)
    if proposal.no_email_notifications:
        return
    
    all_ccs = []
    all_bccs = []

    if decision == 'approved':
        # Internal user approved WLA
        subject = 'Confirmation: Position on mooring site licence waiting list - Rottnest Island Authority'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_invoice = False
        attach_licence_doc = True

    elif decision == 'declined':
        # Internal user declined WLA
        subject = 'Declined: Application for a position on a mooring site licence waiting list - Rottnest Island Authority'
        details = proposal.proposaldeclineddetails.reason if proposal.proposaldeclineddetails else ''
        cc_list = proposal.proposaldeclineddetails.cc_email if proposal.proposaldeclineddetails else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_invoice = False
        attach_licence_doc = False

    # Attachments
    attachments = get_attachments(attach_invoice, attach_licence_doc, proposal)

    html_template = 'mooringlicensing/emails_2/email_17a_and_b.html'
    txt_template = 'mooringlicensing/emails_2/email_17a_and_b.txt'

    url = settings.SITE_URL if settings.SITE_URL else ''
    proposal_url = url + reverse('external-proposal-detail', kwargs={'proposal_pk': proposal.id})

    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'proposal_type_code': proposal.proposal_type.code,
        'decision': decision,
        'details': details,
        'proposal_url': make_http_https(proposal_url),
    }

    email = TemplateEmailBase(
        subject=subject,
        html_template=html_template,
        txt_template=txt_template,
    )

    to_address = proposal.applicant_obj.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_aaa_approved_or_declined_email(proposal, decision, request, stickers_to_be_returned=[]):
    # 18 a and b new/renewal, approval/decline
    # email to applicant when application is issued or declined (annual admission application, new and renewal)
    # 19 a and b amendment, approval/decline
    # email to applicant when application is issued or declined (annual admission application, amendment)
    if proposal.no_email_notifications:
        return
    
    all_ccs = []
    all_bccs = []
    attach_invoice = False
    attach_licence_doc = False
    subject = ''
    details = ''
    if decision == 'approved':
        subject = 'Approved: Application for annual admission permit - Rottnest Island Authority'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_invoice = True if proposal.auto_approve else False
        attach_licence_doc = True
    elif decision == 'declined':
        subject = 'Declined: Application for annual admission permit - Rottnest Island Authority'
        details = proposal.proposaldeclineddetails.reason if proposal.proposaldeclineddetails else ''
        cc_list = proposal.proposaldeclineddetails.cc_email if proposal.proposaldeclineddetails else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_invoice = True if proposal.auto_approve else False
        attach_licence_doc = False
    else:
        logger.warning('Decision is unclear when sending AAA approved/declined email for {}'.format(proposal.lodgement_number))

    # Attachments
    attachments = get_attachments(attach_invoice, attach_licence_doc, proposal)

    if proposal.proposal_type.code in (PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL):
        # New / Renewal
        html_template = 'mooringlicensing/emails_2/email_18a_and_b.html'
        txt_template = 'mooringlicensing/emails_2/email_18a_and_b.txt'
    elif proposal.proposal_type.code == PROPOSAL_TYPE_AMENDMENT:
        # Amendment
        html_template = 'mooringlicensing/emails_2/email_19a_and_b.html'
        txt_template = 'mooringlicensing/emails_2/email_19a_and_b.txt'
    else:
        logger.warning('ProposalType is unclear when sending AAA approved/declined email for {}'.format(proposal.lodgement_number))

    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,
    }

    email = TemplateEmailBase(
        subject=subject,
        html_template=html_template,
        txt_template=txt_template,
    )

    to_address = proposal.applicant_obj.email
    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_aua_approved_or_declined_email_new_renewal(proposal, decision, request, stickers_to_be_returned):
    # 20 AUA new/renewal, approval/decline
    # email to applicant when application is issued or declined (authorised user application, new and renewal)
    if proposal.no_email_notifications:
        return

    all_ccs = []
    all_bccs = []

    subject = ''
    details = ''
    cc_list = ''
    attachments = []
    payment_url = ''
    html_template = 'mooringlicensing/emails_2/'
    txt_template = 'mooringlicensing/emails_2/'

    if decision == 'approved':
        # for payment
        html_template += 'email_20a.html'
        txt_template += 'email_20a.txt'
        subject = 'Payment Due: Application for authorised user permit – Rottnest Island Authority'
        if proposal.proposed_issuance_approval:
            details = proposal.proposed_issuance_approval.get('details')
            cc_list = proposal.proposed_issuance_approval.get('cc_email')

        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(True, False, proposal)

        # Generate payment_url if needed
        if proposal.application_fees.filter(cancelled=False).count():
            application_fee = proposal.get_main_application_fee()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            if get_invoice_payment_status(invoice.id) not in ('paid', 'over_paid'):
                # Payment required
                payment_url = '{}/application_fee_existing/{}/'.format(get_public_url(), invoice.reference)
    elif decision == 'approved_paid':
        # after payment
        html_template += 'email_50a.html'
        txt_template += 'email_50a.txt'
        subject = 'Approved: Application for Rottnest Island Authorised User Permit'
        if proposal.proposed_issuance_approval:
            details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
            cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(True, True, proposal)
    elif decision == 'declined':
        # declined
        html_template += 'email_20b.html'
        txt_template += 'email_20b.txt'
        subject = 'Declined: Application for authorised user permit – Rottnest Island Authority'
        if proposal.proposaldeclineddetails:
            details = proposal.proposaldeclineddetails.reason if proposal.proposaldeclineddetails else ''
            cc_list = proposal.proposaldeclineddetails.cc_email if proposal.proposaldeclineddetails else ''
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
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,
        'payment_url': payment_url,
    }

    to_address = proposal.applicant_obj.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_aua_approved_or_declined_email_amendment_payment_not_required(proposal, decision, request, stickers_to_be_returned):
    #21 a and b
    # email to applicant when application is issued or declined (authorised user application, amendment where no payment is required)
    if proposal.no_email_notifications:
        return
    
    all_ccs = []
    all_bccs = []
    cc_list = ''
    subject = ''
    details = ''
    attachments = []
    
    if decision == 'approved':
        subject = 'Approved: Authorised User Permit Amendment - Rottnest Island Authority'
        cc_list = ''
        if proposal.proposed_issuance_approval:
            details = proposal.proposed_issuance_approval.get('details')
            cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(False, True, proposal)
    elif decision == 'approved_paid':
        subject = 'Approved: Authorised User Permit Amendment - Rottnest Island Authority'
        cc_list = ''
        if proposal.proposed_issuance_approval:
            details = proposal.proposed_issuance_approval.get('details')
            cc_list = proposal.proposed_issuance_approval.get('cc_email')
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(False, True, proposal)
    elif decision == 'declined':
        subject = 'Declined: Application to amend authorised user permit – Rottnest Island Authority'
        cc_list = ''
        if proposal.proposaldeclineddetails:
            details = proposal.proposaldeclineddetails.reason
            cc_list = proposal.proposaldeclineddetails.cc_email
        if cc_list:
            all_ccs = cc_list.split(',')
    else:
        logger.warning('Decision is unclear when sending AUA approved/declined email for {}'.format(proposal.lodgement_number))

    email = TemplateEmailBase(
        subject=subject,
        html_template='mooringlicensing/emails_2/email_21a_and_b.html',
        txt_template='mooringlicensing/emails_2/email_21a_and_b.txt',
    )

    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,
    }

    to_address = proposal.applicant_obj.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_aua_approved_or_declined_email_amendment_payment_required(proposal, decision, request, stickers_to_be_returned):
    #22
    # email to applicant when application is issued or declined (authorised user application, amendment where payment is required)
    if proposal.no_email_notifications:
        return
    
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
        subject = 'Payment due: Application to amend authorised user permit - Rottnest Island Authority'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(True, False, proposal)

        # Generate payment_url if needed
        if proposal.application_fees.filter(cancelled=False).count():
            application_fee = proposal.get_main_application_fee()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            if get_invoice_payment_status(invoice.id) not in ('paid', 'over_paid'):
                # Payment required
                payment_url = '{}/application_fee_existing/{}/'.format(get_public_url(), invoice.reference)
    elif decision == 'approved_paid':
        # after payment
        html_template += 'email_50a.html'
        txt_template += 'email_50a.txt'
        subject = 'Approved: Amendment to Rottnest Island Authorised User Permit'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(False, True, proposal)
    elif decision == 'declined':
        # declined
        html_template += 'email_22b.html'
        txt_template += 'email_22b.txt'
        subject = 'Declined: Application to amend authorised user permit - Rottnest Island Authority'
        details = proposal.proposaldeclineddetails.reason if proposal.proposaldeclineddetails else ''
        cc_list = proposal.proposaldeclineddetails.cc_email if proposal.proposaldeclineddetails else ''
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
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,
        'payment_url': make_http_https(payment_url),
    }

    to_address = retrieve_email_userro(proposal.submitter).email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)
    return msg


def get_attachments(attach_invoice, attach_licence_doc, proposal, attach_au_summary_doc=False):
    logger.info(f'get_attachments() is called...')

    attachments = []
    if attach_invoice and proposal.invoice:
        # Attach invoice
        logger.info(f'Attaching invoice...')

        url = f'{settings.LEDGER_API_URL}/ledgergw/invoice-pdf/{settings.LEDGER_API_KEY}/{proposal.invoice.reference}'
        invoice_pdf = requests.get(url=url)
        if invoice_pdf.status_code == 200:
            inv_name = 'invoice#{}.pdf'.format(proposal.invoice.reference)
            attachment = (inv_name, invoice_pdf.content, 'application/pdf')
            attachments.append(attachment)
            logger.info(f'Invoice: {inv_name} has been attached.')
        else:
            logger.error(f'Status code: {invoice_pdf.status_code}. Could not retrieve invoice_pdf for the invoice reference: {proposal.invoice.reference}')

    if attach_licence_doc and proposal.approval and proposal.approval.licence_document:
        # Attach licence document
        logger.info(f'Attaching licence document...')

        proposal.refresh_from_db()
        proposal.approval.refresh_from_db()

        licence_document = proposal.approval.licence_document._file
        if licence_document is not None:
            file_name = proposal.approval.licence_document.name
            attachment = (file_name, licence_document.file.read(), 'application/pdf')
            attachments.append(attachment)
            logger.info(f'Licence/Permit document: {file_name} has been attached.')

    if attach_au_summary_doc and proposal.approval and proposal.approval.authorised_user_summary_document:
        logger.info(f'Attaching AU summary document...')

        au_summary_document = proposal.approval.authorised_user_summary_document._file
        if au_summary_document is not None:
            file_name = proposal.approval.authorised_user_summary_document.name
            try:
                attachment = (file_name, au_summary_document.file.read(), 'application/pdf')
                attachments.append(attachment)
                logger.info(f'AU summary document: {file_name} has been attached.')
            except:
                logger.warning(f'AU summary document: {file_name} not attached, appears missing from system.')       

    return attachments


def send_au_summary_to_ml_holder(mooring_licence, au_proposal):
    if au_proposal.no_email_notifications:
        return
    
    subject = 'Authorised User Summary for {} - Rottnest Island Authority'.format(mooring_licence.mooring.name)
    attachments = []

    email = TemplateEmailBase(
        subject=subject,
        html_template='mooringlicensing/emails_2/email_40.html',
        txt_template='mooringlicensing/emails_2/email_40.txt',
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
        'public_url': get_public_url(),
        'recipient': mooring_licence.applicant,
        'url_for_au_dashboard_page': get_public_url(),
    }

    to_address = mooring_licence.applicant_obj.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=[], bcc=[],)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        _log_approval_email(msg, mooring_licence, sender, attachments)
    return msg


def send_mla_approved_or_declined_email_new_renewal(proposal, decision, request, stickers_to_be_returned):
    # 23 ML new/renewal, approval/decline
    # email to applicant when application is issued or declined (mooring licence application, new and renewal)
    if proposal.no_email_notifications:
        return
    
    all_ccs = []
    all_bccs = []
    allocated_mooring = proposal.allocated_mooring
    html_template = 'mooringlicensing/emails_2/'
    txt_template = 'mooringlicensing/emails_2/'

    subject = ''
    details = ''
    attachments = []
    payment_url = ''
    approval = None

    if decision == 'approved':
        # for payment
        html_template += 'email_23a.html'
        txt_template += 'email_23a.txt'
        subject = 'Payment due: Application for mooring site licence {} – Rottnest Island Authority'.format(allocated_mooring.name)
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(True, False, proposal)

        # Generate payment_url if needed
        if proposal.application_fees.filter(cancelled=False).count():
            application_fee = proposal.get_main_application_fee()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            if get_invoice_payment_status(invoice.id) not in ('paid', 'over_paid'):
                # Payment required
                payment_url = '{}/application_fee_existing/{}/'.format(get_public_url(), invoice.reference)
    elif decision == 'approved_paid':
        html_template += 'email_51a.html'
        txt_template += 'email_51a.txt'
        subject = 'Approved: Application for Rottnest Island Mooring Site Licence'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')

        approval = proposal.approval
        attach_au_summary_doc = True if proposal.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,] else False
        attachments = get_attachments(True, True, proposal, attach_au_summary_doc)

    elif decision == 'declined':
        html_template += 'email_23b.html'
        txt_template += 'email_23b.txt'
        subject = 'Declined: Application for mooring site licence {} - Rottnest Island Authority'.format(allocated_mooring.name)
        details = proposal.proposaldeclineddetails.reason if proposal.proposaldeclineddetails else ''
        cc_list = proposal.proposaldeclineddetails.cc_email if proposal.proposaldeclineddetails else ''
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
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,
        'payment_url': make_http_https(payment_url),
        'approval': approval,
    }

    to_address = proposal.applicant_obj.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_mla_approved_or_declined_email_swap_mooring(proposal, decision, request, stickers_to_be_returned):
    # ML swap mooring, approval/decline
    # email to applicant when application is issued or declined (mooring licence application, swap mooring)
    if proposal.no_email_notifications:
        return
    
    all_ccs = []
    all_bccs = []
    allocated_mooring = proposal.allocated_mooring
    html_template = 'mooringlicensing/emails_2/'
    txt_template = 'mooringlicensing/emails_2/'

    subject = ''
    details = ''
    attachments = []
    payment_url = ''
    approval = None

    if decision == 'approved':
        # for payment
        html_template += 'email_23a.html'
        txt_template += 'email_23a.txt'

        subject = 'Payment due: Application for mooring site licence {} – Rottnest Island Authority'.format(allocated_mooring.name)

        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attachments = get_attachments(True, False, proposal)

        # Generate payment_url if needed
        if proposal.application_fees.filter(cancelled=False).count():
            application_fee = proposal.get_main_application_fee()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            if get_invoice_payment_status(invoice.id) not in ('paid', 'over_paid'):
                # Payment required
                payment_url = '{}/application_fee_existing/{}/'.format(get_public_url(), invoice.reference)

    elif decision == 'approved_paid':
        html_template += 'email_51a.html'
        txt_template += 'email_51a.txt'
        subject = 'Approved: Application for Rottnest Island Mooring Site Licence'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')

        approval = proposal.approval
        attach_au_summary_doc = True if proposal.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,] else False
        attachments = get_attachments(True, True, proposal, attach_au_summary_doc)

    elif decision == 'declined':
        html_template += 'email_23b.html'
        txt_template += 'email_23b.txt'
        subject = 'Declined: Application for mooring site licence {} - Rottnest Island Authority'.format(allocated_mooring.name)
        details = proposal.proposaldeclineddetails.reason if proposal.proposaldeclineddetails else ''
        cc_list = proposal.proposaldeclineddetails.cc_email if proposal.proposaldeclineddetails else ''
        if cc_list:
            all_ccs = cc_list.split(',')

    else:
        logger.warning('Decision is unclear when sending MLA approved/declined email for {}'.format(proposal.lodgement_number))

    email = TemplateEmailBase(
        subject=subject,
        html_template=html_template,
        txt_template=txt_template,
    )

    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,
        'payment_url': make_http_https(payment_url),
        'approval': approval,
    }

    to_address = proposal.applicant_obj.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_mla_approved_or_declined_email_amendment_payment_not_required(proposal, decision, request, stickers_to_be_returned):
    # 24 a and b ML amendment(no payment), approval/decline
    # email to applicant when application is issued or declined (mooring licence application, amendment where no payment is required)
    if proposal.no_email_notifications:
        return
    
    all_ccs = []
    all_bccs = []
    allocated_mooring = proposal.allocated_mooring

    subject = ''
    details = ''
    attachments = []

    if decision == 'approved':
        subject = 'Approved: Application to amend mooring site licence {} – Rottnest Island Authority'.format(allocated_mooring.name)
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_au_summary_doc = True if proposal.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,] else False
        attachments = get_attachments(False, True, proposal, attach_au_summary_doc)
    elif decision == 'approved_paid':
        subject = 'Approved: Mooring Site Licence Amendment - Rottnest Island Authority'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_au_summary_doc = True if proposal.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,] else False
        attachments = get_attachments(False, True, proposal, attach_au_summary_doc)
    elif decision == 'declined':
        subject = 'Declined: Application to amend mooring site licence {} – Rottnest Island Authority'.format(allocated_mooring.name)
        details = proposal.proposaldeclineddetails.reason if proposal.proposaldeclineddetails else ''
        cc_list = proposal.proposaldeclineddetails.cc_email if proposal.proposaldeclineddetails else ''
        if cc_list:
            all_ccs = cc_list.split(',')
    else:
        logger.warning('Decision is unclear when sending AAA approved/declined email for {}'.format(proposal.lodgement_number))

    email = TemplateEmailBase(
        subject=subject,
        html_template='mooringlicensing/emails_2/email_24a_and_b.html',
        txt_template = 'mooringlicensing/emails_2/email_24a_and_b.txt',
    )

    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,
    }

    to_address = proposal.applicant_obj.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)
    return msg


def send_mla_approved_or_declined_email_amendment_payment_required(proposal, decision, request, stickers_to_be_returned):
    # 25 ML amendment(payment), approval/decline
    # email to applicant when application is issued or declined (mooring licence application, amendment where payment is required) 
    if proposal.no_email_notifications:
        return
    
    all_ccs = []
    all_bccs = []
    subject = ''
    details = ''
    attachments = []
    payment_url = ''
    html_template = 'mooringlicensing/emails_2/'
    txt_template = 'mooringlicensing/emails_2/'
    allocated_mooring = proposal.allocated_mooring
    if decision == 'approved':
        # for payment
        html_template += 'email_25a.html'
        txt_template += 'email_25a.txt'
        subject = 'Payment Due: Application to amend mooring site licence {} – Rottnest Island Authority'.format(allocated_mooring.name)
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_au_summary_doc = True if proposal.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,] else False
        attachments = get_attachments(True, False, proposal, attach_au_summary_doc)

        # Generate payment_url if needed
        if proposal.application_fees.filter(cancelled=False).count():
            application_fee = proposal.get_main_application_fee()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            if get_invoice_payment_status(invoice.id) not in ('paid', 'over_paid'):
                # Payment required
                payment_url = '{}/application_fee_existing/{}/'.format(get_public_url(), invoice.reference)
    elif decision == 'approved_paid':
        # after payment
        html_template += 'email_25b.html'
        txt_template += 'email_25b.txt'
        subject = 'Approved: Mooring Site Licence Amendment - Rottnest Island Authority'
        details = proposal.proposed_issuance_approval.get('details') if proposal.proposed_issuance_approval else ''
        cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
        if cc_list:
            all_ccs = cc_list.split(',')
        attach_au_summary_doc = True if proposal.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT,
                                                                        PROPOSAL_TYPE_RENEWAL, ] else False
        attachments = get_attachments(False, True, proposal, attach_au_summary_doc)
    elif decision == 'declined':
        # declined
        html_template += 'email_25b.html'
        txt_template += 'email_25b.txt'
        subject = 'Declined: Application to amend mooring site licence {} – Rottnest Island Authority'.format(allocated_mooring.name)
        details = proposal.proposaldeclineddetails.reason if proposal.proposaldeclineddetails else ''
        cc_list = proposal.proposaldeclineddetails.cc_email if proposal.proposaldeclineddetails else ''
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
        'public_url': get_public_url(),
        'proposal': proposal,
        'approval': proposal.approval,
        'recipient': proposal.proposal_applicant,
        'decision': decision,
        'details': details,
        'stickers_to_be_returned': stickers_to_be_returned,
        'payment_url': make_http_https(payment_url),
    }

    to_address = proposal.applicant_obj.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)
    return msg

def send_aua_declined_by_endorser_email(proposal, request):
    # email to applicant when application is issued or declined (mooring licence application, amendment where payment is required) 
    if proposal.no_email_notifications:
        return
    
    all_ccs = []
    all_bccs = []

    subject = ''
    attachments = []
    html_template = 'mooringlicensing/emails_2/email_52.html'
    txt_template = 'mooringlicensing/emails_2/email_52.txt'

    subject = 'Declined: Application for authorised user permit - vessel <vessel registration number> - Rottnest Island Authority'
    
    cc_list = proposal.proposed_issuance_approval.get('cc_email') if proposal.proposed_issuance_approval else ''
    if cc_list:
        all_ccs = cc_list.split(',')

    email = TemplateEmailBase(
        subject=subject,
        html_template=html_template,
        txt_template=txt_template,
    )

    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
        'approval': proposal.approval,
        'recipient': proposal.proposal_applicant,
    }

    to_address = proposal.applicant_obj.email

    # Send email
    msg = email.send(to_address, context=context, attachments=attachments, cc=all_ccs, bcc=all_bccs,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments)
    return msg

def send_other_documents_submitted_notification_email(request, proposal):
    if proposal.no_email_notifications:
        return
    
    email = TemplateEmailBase(
        subject='Application: {} is ready for assessment.  Other documents have been submitted.'.format(proposal.description),
        html_template='mooringlicensing/emails/send_documents_submitted_for_mla.html',
        txt_template='mooringlicensing/emails/send_documents_submitted_for_mla.txt',
    )
    url = request.build_absolute_uri(reverse('internal-proposal-detail', kwargs={'proposal_pk': proposal.id}))
    url = make_url_for_internal(url)

    context = {
        'public_url': get_public_url(),
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
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender, attachments=attachments)
        _log_user_email(msg, proposal.applicant_obj, proposal.applicant_obj, sender=sender, attachments=attachments)

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

    if proposal.no_email_notifications:
        return
    
    email = TemplateEmailBase(
        subject='Endorsement Required:  Authorised User Permit - Rottnest Island Authority',
        html_template='mooringlicensing/emails/send_endorsement_of_aua.html',
        txt_template='mooringlicensing/emails/send_endorsement_of_aua.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    login_url = MOORING_LICENSING_EXTERNAL_URL + reverse('external')

    msgs = []
    for site_licensee_mooring_request in proposal.site_licensee_mooring_request.filter(enabled=True,declined_by_endorser=False,approved_by_endorser=False):
        #replace with multiple site licensee emails
        try:
            endorser = EmailUser.objects.filter(email__iexact=site_licensee_mooring_request.site_licensee_email, is_active=True).order_by('-id').first()
        except:
            # Should not reach here
            return

        #iterate through each site licensee mooring request
        mooring_name = site_licensee_mooring_request.mooring.name if site_licensee_mooring_request.mooring else ''
        due_date = proposal.get_due_date_for_endorsement_by_target_date()

        # Configure recipients, contents, etc
        context = {
            'public_url': get_public_url(),
            'proposal': proposal,
            'recipient': proposal.proposal_applicant,
            'endorser': endorser,
            'applicant': proposal.proposal_applicant,
            'mooring_name': mooring_name,
            'due_date': due_date,
            'login_url': login_url,
        }

        to_address = site_licensee_mooring_request.site_licensee_email
        cc = []
        bcc = []

        # Send email
        msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
        if msg:
            sender = get_user_as_email_user(msg.from_email)
            log_proposal_email(msg, proposal, sender)
            msgs.append(msg)

    return msgs

def send_application_discarded_email(proposal, request):
    if proposal.no_email_notifications:
        return
    
    email = TemplateEmailBase(
        subject='Application Discarded - Rottnest Island Authority',
        html_template='mooringlicensing/emails_2/application_discarded.html',
        txt_template='mooringlicensing/emails_2/application_discarded.txt',
    )

    context = {
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
    }

    to_address = proposal.applicant_obj.email
    cc = []
    bcc = proposal.assessor_recipients

    # Send email
    msg = email.send(to_address, context=context, attachments=[], cc=cc, bcc=bcc,)
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        log_proposal_email(msg, proposal, sender)
    return msg

def send_proposal_approver_sendback_email_notification(request, proposal):
    if proposal.no_email_notifications:
        return
    
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
        'public_url': get_public_url(),
        'proposal': proposal,
        'recipient': proposal.proposal_applicant,
        'url': url,
        'approver_comment': approver_comment
    }

    msg = email.send(proposal.assessor_recipients, context=context)
    if msg:
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