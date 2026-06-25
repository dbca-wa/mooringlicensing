import logging
import ledger_api_client
import mimetypes
import requests
from dateutil.relativedelta import relativedelta
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.utils.encoding import smart_str
from django.urls import reverse
from django.conf import settings
from mooringlicensing import settings
from mooringlicensing.components.emails.emails import TemplateEmailBase, _extract_email_headers
from mooringlicensing.components.main.models import FileExtensionWhitelist
from ledger_api_client.ledger_models import EmailUserRO as EmailUser, EmailUserRO
from mooringlicensing.components.emails.utils import get_user_as_email_user, get_public_url, make_http_https
from django.core.files.base import ContentFile
import os

from mooringlicensing.components.users.utils import _log_user_email

from django.core.files.storage import FileSystemStorage
private_storage = FileSystemStorage(
    location=settings.PRIVATE_MEDIA_STORAGE_LOCATION,
    base_url=settings.PRIVATE_MEDIA_BASE_URL,
)

logger = logging.getLogger(__name__)
SYSTEM_NAME = settings.SYSTEM_NAME_SHORT + ' Automated Message'


class ApprovalExpireNotificationEmail(TemplateEmailBase):
    subject = 'Approval expired'  # This is default and should be overwitten
    html_template = 'mooringlicensing/emails_2/approval_expire_notification.html'
    txt_template = 'mooringlicensing/emails_2/approval_expire_notification.txt'

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
    html_template = 'mooringlicensing/emails_2/approval_cancelled_due_to_no_vessels_nominated.html'
    txt_template = 'mooringlicensing/emails_2/approval_cancelled_due_to_no_vessels_nominated.txt'

    def __init__(self, approval):
        self.subject = self.subject.format(approval.lodgement_number)


class AuthorisedUserNoMooringsNotificationEmail(TemplateEmailBase):
    subject = 'No moorings remaining'  # This is default and should be overwitten
    html_template = 'mooringlicensing/emails_2/auth_user_no_moorings_notification.html'
    txt_template = 'mooringlicensing/emails_2/auth_user_no_moorings_notification.txt'

    def __init__(self, approval):
        self.subject = 'Amended: {} {} - {}.'.format(approval.child_obj.description, approval.child_obj.lodgement_number, settings.RIA_NAME)


class AuthorisedUserMooringRemovedNotificationEmail(TemplateEmailBase):
    subject = 'Mooring removed'  # This is default and should be overwitten
    html_template = 'mooringlicensing/emails_2/email_38.html'
    txt_template = 'mooringlicensing/emails_2/email_38.txt'

    def __init__(self, approval):
        self.subject = 'Amended: {} {} - {}.'.format(approval.child_obj.description, approval.child_obj.lodgement_number, settings.RIA_NAME)


def send_auth_user_mooring_removed_notification(approval, mooring_licence, stickers_to_be_returned):
    email = AuthorisedUserMooringRemovedNotificationEmail(approval)
    proposal = approval.current_proposal

    url=settings.SITE_URL if settings.SITE_URL else ''
    url += reverse('external')

    if "-internal" in url:
        # remove '-internal'. This email is for external applicants
        url = ''.join(url.split('-internal'))

    context = {
        'recipient': proposal.proposal_applicant,
        'dashboard_external_url': get_public_url(),
        'approval': approval,
        'proposal': proposal,
        'mooring_licence': mooring_licence,
        'mooring': mooring_licence.mooring,
        'url': make_http_https(url),
        'stickers_to_be_returned': stickers_to_be_returned,
    }
    all_ccs = []
    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, context=context)
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        try:
            sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
        except:
            sender_user = None

        _log_approval_email(msg, approval, sender=sender_user)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender_user)


def send_approval_expire_email_notification(approval):
    email = ApprovalExpireNotificationEmail(approval)
    proposal = approval.current_proposal

    url = settings.SITE_URL if settings.SITE_URL else ''
    url += reverse('external')

    if "-internal" in url:
        # remove '-internal'. This email is for external applicants
        url = ''.join(url.split('-internal'))

    context = {
        'recipient': proposal.proposal_applicant,
        'public_url': get_public_url(),
        'approval': approval,
        'proposal': proposal,
        'url': make_http_https(url),
    }
    all_ccs = []
    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, context=context)
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        try:
            sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
        except:
            sender_user = None

        _log_approval_email(msg, approval, sender=sender_user)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender_user)


def send_approval_cancelled_due_to_no_vessels_nominated_mail(approval, request=None):
    from mooringlicensing.components.approvals.models import MooringLicence

    email = ApprovalCancelledDueToNoVesselsNominatedEmail(approval)
    proposal = approval.current_proposal

    if approval.application_type.code == MooringLicence.code:
        # When ML
        due_date = approval.get_most_recent_end_date() + relativedelta(months=+6)
    else:
        # When WL
        due_date = approval.current_proposal.vessel_ownership.end_date + relativedelta(months=+6)

    context = {
        'recipient': proposal.proposal_applicant,
        'public_url': get_public_url(),
        'approval': approval,
        'due_date': due_date,
    }

    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
    except:
        sender_user = None

    to_address = approval.applicant_obj.email
    all_ccs = []
    bcc = approval.current_proposal.approver_recipients

    msg = email.send(to_address, context=context, attachments=[], cc=all_ccs, bcc=bcc,)
    if msg:
        _log_approval_email(msg, approval, sender=sender_user)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender_user)

    return msg

def send_vessel_nomination_reminder_mail(approval, request=None):
    
    email = TemplateEmailBase(
        subject='First and final reminder: Vessel requirements for {} - Rottnest Island Authority'.format(approval.description),
        html_template='mooringlicensing/emails_2/email_10.html',
        txt_template='mooringlicensing/emails_2/email_10.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    url = url + reverse('external')

    proposal = approval.current_proposal

    context = {
        'recipient': proposal.proposal_applicant,
        'public_url': get_public_url(),
        'approval': approval,
        'date_to_nominate_new_vessel': approval.current_proposal.vessel_ownership.end_date + relativedelta(months=+6),
        'dashboard_external_url': make_http_https(url),
    }

    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
    except:
        sender_user = None

    to_address = approval.applicant_obj.email
    all_ccs = []
    bcc = []

    msg = email.send(to_address, context=context, attachments=[], cc=all_ccs, bcc=bcc,)
    if msg:
        _log_approval_email(msg, approval, sender=sender_user)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender_user)

    return msg
    

def _log_approval_email(email_message, approval, sender=None, attachments=[]):
    from mooringlicensing.components.approvals.models import ApprovalLogEntry
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
        to = approval.current_proposal.applicant_obj.email
        fromm = smart_str(sender) if sender else SYSTEM_NAME
        all_ccs = ''

    customer = approval.current_proposal.proposal_applicant.email_user_id

    staff = sender

    kwargs = {
        'subject': subject,
        'text': text,
        'approval': approval,
        'customer': customer,
        #'staff': staff.id,
        'to': to,
        'fromm': fromm,
        'cc': all_ccs
    }

    email_entry = ApprovalLogEntry.objects.create(**kwargs)

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


def log_mla_created_proposal_email(email_message, proposal, sender=None):
    from mooringlicensing.components.proposals.models import ProposalLogEntry, ProposalLogDocument
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

    staff = sender

    kwargs = {
        'subject': subject,
        'text': text,
        'proposal': proposal,
        'customer': customer,
        'staff': staff.id,
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


#####
### After refactoring ###
#####
def send_dcv_permit_mail(dcv_permit, invoice, request):
    # 26
    # email to applicant upon successful payment of dcv permit application with details of issued dcv permit
    email = TemplateEmailBase(
        subject='Issued: Domestic commercial vessel permit - Rottnest Island Authority',
        html_template='mooringlicensing/emails_2/email_26.html',
        txt_template='mooringlicensing/emails_2/email_26.txt',
    )

    context = {
        'public_url': get_public_url(),
        'dcv_permit': dcv_permit,
        'recipient': dcv_permit.submitter,
    }

    attachments = []

    # attach invoice
    api_key = settings.LEDGER_API_KEY
    url = settings.LEDGER_API_URL+'/ledgergw/invoice-pdf/'+api_key+'/' + invoice.reference
    invoice_pdf = requests.get(url=url)
    if invoice_pdf.status_code == 200:
        attachment = (f'invoice#{invoice.reference}', invoice_pdf.content, 'application/pdf')
        attachments.append(attachment)

    # attach DcvPermit
    dcv_permit_doc = dcv_permit.dcv_permit_documents.first()
    filename = str(dcv_permit_doc)
    content = dcv_permit_doc._file.read()
    mime = mimetypes.guess_type(dcv_permit_doc.filename)[0]
    attachments.append((filename, content, mime))

    to = dcv_permit.submitter_obj.email
    cc = []
    bcc = []

    # Update bcc if
    dcv_group = ledger_api_client.managed_models.SystemGroup.objects.get(name="Mooring Licensing - DCV Permit Admin")
    ids = dcv_group.get_system_group_member_ids()
    users = EmailUserRO.objects.filter(id__in=ids)

    if users:
        bcc = [user.email for user in users]

    msg = email.send(
        to,
        context=context,
        attachments=attachments,
        cc=cc,
        bcc=bcc,
    )
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        email_data = _extract_email_headers(msg, sender=sender)


def send_dcv_admission_mail(dcv_admission, invoice, request):
    # 27
    # email to external user upon payment of dcv admission fees
    email = TemplateEmailBase(
        subject='Payment received: Remittance of admission fees paid for commercial vessel visit - Rottnest Island Authority',
        html_template='mooringlicensing/emails_2/email_27.html',
        txt_template='mooringlicensing/emails_2/email_27.txt',
    )
    summary = dcv_admission.get_summary()
    vessel_rego_no = dcv_admission.dcv_vessel.rego_no

    context = {
        'public_url': get_public_url(),
        'dcv_admission': dcv_admission,
        'recipient': dcv_admission.submitter_obj if dcv_admission.submitter_obj else dcv_admission.dcv_organisation.name,
        'summary': summary,
        'vessel_rego_no': vessel_rego_no,
    }

    attachments = []

    # attach invoice
    if invoice:
        api_key = settings.LEDGER_API_KEY
        url = settings.LEDGER_API_URL+'/ledgergw/invoice-pdf/'+api_key+'/' + invoice.reference
        invoice_pdf = requests.get(url=url)
        if invoice_pdf.status_code == 200:
            attachment = (f'invoice#{invoice.reference}', invoice_pdf.content, 'application/pdf')
            attachments.append(attachment)

    # attach DcvPermit
    if dcv_admission.dcv_admission_documents:
        dcv_admission_doc = dcv_admission.dcv_admission_documents.first()
        if dcv_admission_doc:
            filename = str(dcv_admission_doc)
            content = dcv_admission_doc._file.read()
            mime = mimetypes.guess_type(dcv_admission_doc.filename)[0]
            attachments.append((filename, content, mime))

    to = dcv_admission.submitter_obj.email 
    cc = []
    bcc = dcv_admission.admin_recipients

    msg = email.send(
        to,
        context=context,
        attachments=attachments,
        cc=cc,
        bcc=bcc,
    )
    if msg:
        sender = get_user_as_email_user(msg.from_email)
        email_data = _extract_email_headers(msg, sender=sender)


def send_approval_cancel_email_notification(approval):
    # 28 Cancelled
    # email to licence/permit holder when licence/permit is cancelled
    email = TemplateEmailBase(
        subject='Cancelled: {} {} - Rottnest Island Authority'.format(approval.description, approval.lodgement_number),
        html_template='mooringlicensing/emails_2/email_28.html',
        txt_template='mooringlicensing/emails_2/email_28.txt',
    )
    proposal = approval.current_proposal

    context = {
        'public_url': get_public_url(),
        'approval': approval,
        'recipient': proposal.proposal_applicant,
        'cancel_start_date': approval.cancellation_date,
        'details': approval.cancellation_details,
    }
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
    except:
        sender_user = None
    all_ccs = []
    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, context=context)
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender_user)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender_user)


def send_approval_suspend_email_notification(approval, request=None):
    # 29 Suspended
    # email to licence/permit holder when licence/permit is suspended
    email = TemplateEmailBase(
        subject='Suspended: {} {} - Rottnest Island Authority'.format(approval.description, approval.lodgement_number),
        html_template='mooringlicensing/emails_2/email_29.html',
        txt_template='mooringlicensing/emails_2/email_29.txt',
    )
    proposal = approval.current_proposal

    if request and 'test-emails' in request.path_info:
        details = 'This are my test details'
        from_date = '01/01/1970'
        to_date = '01/01/2070'
    else:
        details = approval.suspension_details['details']
        from_date = approval.suspension_details['from_date'] if 'from_date' in approval.suspension_details else ''
        to_date = approval.suspension_details['to_date'] if 'to_date' in approval.suspension_details else ''

    context = {
        'recipient': proposal.proposal_applicant,
        'public_url': get_public_url(),
        'approval': approval,
        'details': details,
        'from_date': from_date,
        'to_date': to_date
    }
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
    except:
        sender_user = None
    all_ccs = []
    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, context=context)
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender_user)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender_user)


def send_approval_surrender_email_notification(approval, request=None, already_surrendered=True, stickers_to_be_returned=[]):
    # 30 Surrendered
    # email to licence/permit holder when licence/permit is surrendered
    if already_surrendered:
        email = TemplateEmailBase(
            subject='Surrendered: {} {} - effective {} - Rottnest Island Authority'.format(approval.description, approval.lodgement_number, approval.surrender_details['surrender_date']),
            html_template='mooringlicensing/emails_2/email_30.html',
            txt_template='mooringlicensing/emails_2/email_30.txt',
        )
    else:
        email = TemplateEmailBase(
            subject='Surrendered: {} {} - effective {} - Rottnest Island Authority'.format(approval.description, approval.lodgement_number, approval.surrender_details['surrender_date']),
            html_template='mooringlicensing/emails_2/email_30_future.html',
            txt_template='mooringlicensing/emails_2/email_30_future.txt',
        )
    proposal = approval.current_proposal

    if request and 'test-emails' in request.path_info:
        details = 'This are my test details'
        surrender_date = '01/01/1970'
    else:
        details = approval.surrender_details['details']
        surrender_date = approval.surrender_details['surrender_date']

    context = {
        'public_url': get_public_url(),
        'approval': approval,
        'recipient': proposal.proposal_applicant,
        'details': details,
        'surrender_date': surrender_date,
        'stickers_to_be_returned': stickers_to_be_returned,
    }
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
    except:
        sender_user = None
    all_ccs = []
    bccs = proposal.assessor_recipients

    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, context=context, bcc=bccs)
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender_user)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender_user)


def send_swap_moorings_application_created_notification(mooring_licence, request):
    email = TemplateEmailBase(
        subject=f'Submission Received: Mooring Site Licence Swap - Rottnest Island Authority',
        html_template='mooringlicensing/emails_2/swap_moorings_application_created.html',
        txt_template='mooringlicensing/emails_2/swap_moorings_application_created.txt',
    )
    proposal = mooring_licence.current_proposal

    context = {
        'dashboard_external_url': get_public_url(),
        'recipient': mooring_licence.applicant_obj,
    }
    all_ccs = []
    all_bccs = []
    attachments = []

    all_bccs = proposal.assessor_recipients

    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, bcc=all_bccs, context=context, attachments=attachments)
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, mooring_licence, sender=sender, attachments=attachments)
        _log_user_email(msg, mooring_licence.applicant_obj, proposal.applicant_obj, sender=sender)


def send_approval_reinstate_email_notification(approval):
    # 31 Reinstated
    # email to licence/permit holder when licence/permit is reinstated or when suspension ends
    email = TemplateEmailBase(
        subject='Re-instated: {} {} - Rottnest Island Authority'.format(approval.description, approval.lodgement_number),
        html_template='mooringlicensing/emails_2/email_31.html',
        txt_template='mooringlicensing/emails_2/email_31.txt',
    )
    proposal = approval.current_proposal

    context = {
        'public_url': get_public_url(),
        'approval': approval,
        'recipient': proposal.proposal_applicant,
    }
    all_ccs = []
    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, context=context)
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender)


def send_reissue_ml_after_sale_recorded_email(approval, request, vessel_ownership, stickers_to_be_returned):
    # 32 (only for ML)
    # email to licence or mooring licence holder upon automatic re-issue after date of sale is recorded (regardless of whether new vessel added at that time)
    proposal = approval.current_proposal

    # Retrieve mooring
    mooring_name = ''
    if hasattr(approval, 'mooring'):
        mooring_name = approval.mooring.name
    else:
        # Should not reach here
        logger.error('Mooring not found for {} when sending the automatic re-issue email after date of sale is recorded.'.format(approval.lodgement_number))

    # Calculate due date
    sale_date = vessel_ownership.end_date
    six_months = relativedelta(months=6)
    due_date = sale_date + six_months

    email = TemplateEmailBase(
        subject='Notice to return vessel sticker(s) - {} removed from mooring site licence {} - Rottnest Island Authority'.format(vessel_ownership.vessel.rego_no,mooring_name),
        html_template='mooringlicensing/emails_2/email_32.html',
        txt_template='mooringlicensing/emails_2/email_32.txt',
    )

    attachments = []
    attachment = approval.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(),
        'recipient': proposal.proposal_applicant,
        'vessel_rego_no': vessel_ownership.vessel.rego_no,
        'stickers_to_be_returned': stickers_to_be_returned,
        'due_date': due_date,
        'dashboard_external_url': get_public_url(),
    }
    all_ccs = []
    all_bccs = proposal.assessor_recipients

    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, bcc=all_bccs, context=context, attachments=attachments)
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender, attachments=attachments)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender)


def send_reissue_wla_after_sale_recorded_email(approval, request, vessel_ownership, stickers_to_be_returned):
    # 33 (only for WLA)
    # email to licence or waitlist holder upon automatic re-issue after date of sale is recorded (regardless of whether new vessel added at that time)
    proposal = approval.current_proposal

    sale_date = vessel_ownership.end_date
    six_months = relativedelta(months=6)
    due_date = sale_date + six_months

    email = TemplateEmailBase(
        subject='Nomination of suitable vessel due {} - mooring site licence waiting list allocation – Rottnest Island Authority'.format(due_date),
        html_template='mooringlicensing/emails_2/email_33.html',
        txt_template='mooringlicensing/emails_2/email_33.txt',
    )

    attachments = []
    attachment = approval.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(),
        'recipient': proposal.proposal_applicant,
        'vessel_rego_no': vessel_ownership.vessel.rego_no,
        'stickers_to_be_returned': stickers_to_be_returned,
        'due_date': due_date,
        'dashboard_external_url': get_public_url(),
    }
    all_ccs = []
    all_bccs = proposal.assessor_recipients

    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, bcc=all_bccs, context=context, attachments=attachments)
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender, attachments=attachments)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender)


def send_reissue_aup_after_sale_recorded_email(approval, request, vessel_ownership, stickers_to_be_returned):
    # 34 (only for AUP)
    # email to authorised user permit holder upon automatic re-issue after date of sale is recorded (regardless of whether new vessel added at that time)
    proposal = approval.current_proposal

    # Calculate new vessle nomination due date
    sale_date = vessel_ownership.end_date
    six_months = relativedelta(months=6)
    due_date = sale_date + six_months

    email = TemplateEmailBase(
        subject='Notice to return vessel sticker(s) - {} removed from authorised user permit – Rottnest Island Authority'.format(vessel_ownership.vessel.rego_no),
        html_template='mooringlicensing/emails_2/email_34.html',
        txt_template='mooringlicensing/emails_2/email_34.txt',
    )

    attachments = []
    attachment = approval.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(),
        'recipient': proposal.proposal_applicant,
        'vessel_rego_no': vessel_ownership.vessel.rego_no,
        'stickers_to_be_returned': stickers_to_be_returned,
        'due_date': due_date,
        'dashboard_external_url': get_public_url(),
        'cancelation_policy_url': settings.CANCELATION_POLICY_URL,
        'approval': approval,
    }
    all_ccs = []
    all_bccs = proposal.assessor_recipients

    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, bcc=all_bccs, context=context, attachments=attachments)
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender, attachments=attachments)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender)


def send_reissue_aap_after_sale_recorded_email(approval, request, vessel_ownership, stickers_to_be_returned):
    # 35 (only for AAP)
    # email to annual admission permit holder upon automatic re-issue after date of sale is recorded (regardless of whether new vessel added at that time)
    proposal = approval.current_proposal

    # Calculate new vessel nomination due date
    sale_date = vessel_ownership.end_date
    six_months = relativedelta(months=6)
    due_date = sale_date + six_months

    email = TemplateEmailBase(
        subject='Notice to return vessel sticker(s) - {} removed from annual admission permit – Rottnest Island Authority'.format(vessel_ownership.vessel.rego_no),
        html_template='mooringlicensing/emails_2/email_35.html',
        txt_template='mooringlicensing/emails_2/email_35.txt',
    )

    attachments = []
    attachment = approval.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(),
        'recipient': proposal.proposal_applicant,
        'vessel_rego_no': vessel_ownership.vessel.rego_no,
        'stickers_to_be_returned': stickers_to_be_returned,
        'due_date': due_date,
        'dashboard_external_url': get_public_url(),
        'cancelation_policy_url': settings.CANCELATION_POLICY_URL,
    }
    all_ccs = []
    all_bccs = proposal.assessor_recipients

    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, bcc=all_bccs, context=context, attachments=attachments)
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender, attachments=attachments)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender)


def send_sticker_replacement_email(request, old_sticker_numbers, approval, invoice_reference):
    # 36
    # email to licence/permit holder when sticker replacement request has been submitted (with payment)
    proposal = approval.current_proposal
    vessel_rego = proposal.vessel_ownership.vessel.rego_no
    email = TemplateEmailBase(
        subject='Sticker replacement for {} - vessel {} - Rottnest Island Authority'.format(approval.description, vessel_rego),
        html_template='mooringlicensing/emails_2/email_36.html',
        txt_template='mooringlicensing/emails_2/email_36.txt',
    )

    # Attach invoice
    attachments = []

    url = f'{settings.LEDGER_API_URL}/ledgergw/invoice-pdf/{settings.LEDGER_API_KEY}/{invoice_reference}'
    invoice_pdf = requests.get(url=url)
    if invoice_pdf.status_code == 200:
        attachment = ('invoice#{}.pdf'.format(invoice_reference), invoice_pdf.content, 'application/pdf')
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(),
        'recipient': proposal.proposal_applicant,
        'approval': approval,
        'old_sticker_numbers': ','.join(old_sticker_numbers),
        'vessel_rego_no': vessel_rego,
        'dashboard_external_url': get_public_url(),
    }

    all_ccs = []
    bcc = proposal.assessor_recipients

    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, bcc=bcc, context=context, attachments=attachments)
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender, attachments=attachments)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender)


def send_aup_revoked_due_to_mooring_swap_email(authorised_user_permit, mooring, stickers_to_be_returned):
    # 37
    # email to authorised user when mooring site authorisation revoked due to licensee mooring swap and to return sticker
    proposal = authorised_user_permit.current_proposal
    approval = authorised_user_permit
    vessel_rego = proposal.vessel_ownership.vessel.rego_no
    email = TemplateEmailBase(
        subject='Notice to return vessel sticker(s) - Authorised use of {} revoked due to exchange of mooring site licences - vessel {} - Rottnest Island Authority'.format(mooring.name, vessel_rego),
        html_template='mooringlicensing/emails_2/email_37.html',
        txt_template='mooringlicensing/emails_2/email_37.txt',
    )

    attachments = []
    attachment = authorised_user_permit.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(),
        'recipient': authorised_user_permit.applicant_obj,
        'mooring': mooring,
        'stickers_to_be_returned': stickers_to_be_returned,
        'dashboard_external_url': get_public_url(),
    }

    all_ccs = []
    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, context=context, attachments=attachments)
    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender, attachments=attachments)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender)


def send_aup_revoked_due_to_relinquishment_email(request, authorised_user_permit, mooring, stickers_to_be_returned):
    # 38
    # email to authorised user when mooring site authorisation revoked due to mooring site licence relinquishment and to return sticker
    proposal = authorised_user_permit.current_proposal
    approval = authorised_user_permit
    vessel_rego = proposal.vessel_ownership.vessel.rego_no
    email = TemplateEmailBase(
        subject='Notice to return vessel sticker(s) - Authorised use of {} revoked due to relinquishment of mooring site licence – vessel {} - Rottnest Island Authority'.format(mooring.name, vessel_rego),
        html_template='mooringlicensing/emails_2/email_38.html',
        txt_template='mooringlicensing/emails_2/email_38.txt',
    )

    attachments = []
    attachment = authorised_user_permit.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(),
        'recipient': authorised_user_permit.applicant_obj,
        'mooring': mooring,
        'stickers_to_be_returned': stickers_to_be_returned,
        'dashboard_external_url': get_public_url(),
    }

    all_ccs = []
    msg = email.send(proposal.applicant_obj.email, cc=all_ccs, context=context, attachments=attachments)
    if msg:
        sender = request.user if request else settings.DEFAULT_FROM_EMAIL
        _log_approval_email(msg, approval, sender=sender, attachments=attachments)
        _log_user_email(msg, approval.applicant_obj, proposal.applicant_obj, sender=sender)