import logging
import mimetypes
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import Group
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.utils.encoding import smart_text
from django.core.urlresolvers import reverse
from django.conf import settings
from datetime import timedelta
from ledger.payments.pdf import create_invoice_pdf_bytes
from mooringlicensing import settings
from mooringlicensing.components.emails.emails import TemplateEmailBase, _extract_email_headers
from ledger.accounts.models import EmailUser
from mooringlicensing.components.emails.utils import get_user_as_email_user, get_public_url, make_http_https
from mooringlicensing.components.organisations.models import OrganisationLogEntry, Organisation
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


logger = logging.getLogger(__name__)
SYSTEM_NAME = settings.SYSTEM_NAME_SHORT + ' Automated Message'


class ApprovalExpireNotificationEmail(TemplateEmailBase):
    subject = 'Approval expired'  # This is default and should be overwitten
    # html_template = 'mooringlicensing/emails/approval_expire_notification.html'
    # txt_template = 'mooringlicensing/emails/approval_expire_notification.txt'
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
        self.subject = '{} - {} expired.'.format(settings.RIA_NAME, approval.child_obj.description)


class AuthorisedUserMooringRemovedNotificationEmail(TemplateEmailBase):
    subject = 'Mooring removed'  # This is default and should be overwitten
    html_template = 'mooringlicensing/emails_2/auth_user_mooring_removed_notification.html'
    txt_template = 'mooringlicensing/emails_2/auth_user_mooring_removed_notification.txt'

    def __init__(self, approval):
        self.subject = '{} - {} expired.'.format(settings.RIA_NAME, approval.child_obj.description)


def send_auth_user_no_moorings_notification(approval):
    email = AuthorisedUserNoMooringsNotificationEmail(approval)
    proposal = approval.current_proposal

    url=settings.SITE_URL if settings.SITE_URL else ''
    url += reverse('external')

    if "-internal" in url:
        # remove '-internal'. This email is for external submitters
        url = ''.join(url.split('-internal'))

    context = {
        'recipient': approval.submitter,
        'public_url': get_public_url(),
        'approval': approval,
        'proposal': proposal,
        'url': make_http_https(url),
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


def send_auth_user_mooring_removed_notification(approval, mooring_licence):
    email = AuthorisedUserMooringRemovedNotificationEmail(approval)
    proposal = approval.current_proposal

    url=settings.SITE_URL if settings.SITE_URL else ''
    url += reverse('external')

    if "-internal" in url:
        # remove '-internal'. This email is for external submitters
        url = ''.join(url.split('-internal'))

    context = {
        'recipient': approval.submitter,
        'public_url': get_public_url(),
        'approval': approval,
        'proposal': proposal,
        'mooring_licence': mooring_licence,
        'url': make_http_https(url),
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


def send_approval_expire_email_notification(approval):
    # if approval.is_lawful_authority:
    #     email = FilmingLawfulAuthorityApprovalExpireNotificationEmail()
    # if approval.is_filming_licence:
    #     email = FilmingLicenceApprovalExpireNotificationEmail()
    # else:
    #     email = ApprovalExpireNotificationEmail()
    email = ApprovalExpireNotificationEmail(approval)
    proposal = approval.current_proposal

    url = settings.SITE_URL if settings.SITE_URL else ''
    url += reverse('external')

    if "-internal" in url:
        # remove '-internal'. This email is for external submitters
        url = ''.join(url.split('-internal'))

    context = {
        'recipient': approval.submitter,
        'public_url': get_public_url(),
        'approval': approval,
        'proposal': proposal,
        'url': make_http_https(url),
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
        'recipient': approval.submitter,
        'public_url': get_public_url(request),
        'approval': approval,
        'due_date': due_date,
    }

    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)


    #approver_group = ProposalApproverGroup.objects.all().first()
    to_address = approval.submitter.email
    all_ccs = []
    #bcc = approver_group.members_email
    # TODO: fix bcc with correct security group
    bcc = []
    msg = email.send(to_address, context=context, attachments=[], cc=all_ccs, bcc=bcc,)

    _log_approval_email(msg, approval, sender=sender_user)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)

    return msg


def send_vessel_nomination_reminder_mail(approval, request=None):
    # 10
    email = TemplateEmailBase(
        subject='First and Final Reminder: Vessel Requirements for {} - Rottnest Island Authority'.format(approval.description),
        html_template='mooringlicensing/emails_2/email_10.html',
        txt_template='mooringlicensing/emails_2/email_10.txt',
    )
    url = settings.SITE_URL if settings.SITE_URL else ''
    url = url + reverse('external')

    proposal = approval.current_proposal

    context = {
        'recipient': approval.submitter,
        'public_url': get_public_url(request),
        'approval': approval,
        'date_to_nominate_new_vessel': approval.current_proposal.vessel_ownership.end_date + relativedelta(months=+6),
        'dashboard_external_url': make_http_https(url),
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

    msg = email.send(to_address, context=context, attachments=[], cc=all_ccs, bcc=bcc,)

    _log_approval_email(msg, approval, sender=sender_user)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender_user)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender_user)

    return msg


def _log_approval_email(email_message, approval, sender=None, attachments=[]):
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

    for attachment in attachments:
        path_to_file = '{}/approvals/{}/communications/{}'.format(settings.MEDIA_APP_DIR, approval.id, attachment[0])
        path = default_storage.save(path_to_file, ContentFile(attachment[1]))
        email_entry.documents.get_or_create(_file=path_to_file, name=attachment[0])

    return email_entry


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


#####
### After refactoring ###
#####
def send_dcv_permit_mail(dcv_permit, invoice, request):
    # 26
    # email to applicant upon successful payment of dcv permit application with details of issued dcv permit
    email = TemplateEmailBase(
        subject='Dcv Permit.',
        # html_template='mooringlicensing/emails/dcv_permit_mail.html',
        # txt_template='mooringlicensing/emails/dcv_permit_mail.txt',
        html_template='mooringlicensing/emails_2/email_26.html',
        txt_template='mooringlicensing/emails_2/email_26.txt',
    )

    context = {
        'public_url': get_public_url(request),
        'dcv_permit': dcv_permit,
        'recipient': dcv_permit.submitter,
    }

    attachments = []

    # attach invoice
    contents = create_invoice_pdf_bytes('invoice.pdf', invoice,)
    attachments.append(('invoice#{}.pdf'.format(invoice.reference), contents, 'application/pdf'))

    # attach DcvPermit
    dcv_permit_doc = dcv_permit.permits.first()
    filename = str(dcv_permit_doc)
    content = dcv_permit_doc._file.read()
    mime = mimetypes.guess_type(dcv_permit_doc.filename)[0]
    attachments.append((filename, content, mime))

    to = dcv_permit.submitter.email
    cc = []
    bcc = []

    # Update bcc if
    dcv_group = Group.objects.get(name=settings.GROUP_DCV_PERMIT_ADMIN)
    users = dcv_group.user_set.all()
    if users:
        bcc = [user.email for user in users]

    msg = email.send(
        to,
        context=context,
        attachments=attachments,
        cc=cc,
        bcc=bcc,
    )

    sender = get_user_as_email_user(msg.from_email)
    email_data = _extract_email_headers(msg, sender=sender)
    return email_data


def send_dcv_admission_mail(dcv_admission, invoice, request):
    # 27
    # email to external user upon payment of dcv admission fees
    email = TemplateEmailBase(
        subject='DCV Admission fees',
        # html_template='mooringlicensing/emails/dcv_admission_mail.html',
        # txt_template='mooringlicensing/emails/dcv_admission_mail.txt',
        html_template='mooringlicensing/emails_2/email_27.html',
        txt_template='mooringlicensing/emails_2/email_27.txt',
    )
    summary = dcv_admission.get_summary()

    context = {
        'public_url': get_public_url(request),
        'dcv_admission': dcv_admission,
        'recipient': dcv_admission.submitter,
        'summary': summary,
    }

    attachments = []

    # attach invoice
    if invoice:
        contents = create_invoice_pdf_bytes('invoice.pdf', invoice,)
        attachments.append(('invoice#{}.pdf'.format(invoice.reference), contents, 'application/pdf'))

    # attach DcvPermit
    if dcv_admission.admissions:
        dcv_admission_doc = dcv_admission.admissions.first()
        if dcv_admission_doc:
            filename = str(dcv_admission_doc)
            content = dcv_admission_doc._file.read()
            mime = mimetypes.guess_type(dcv_admission_doc.filename)[0]
            attachments.append((filename, content, mime))

    to = dcv_admission.submitter.email
    cc = []
    bcc = []

    msg = email.send(
        to,
        context=context,
        attachments=attachments,
        cc=cc,
        bcc=bcc,
    )

    sender = get_user_as_email_user(msg.from_email)
    email_data = _extract_email_headers(msg, sender=sender)
    return email_data


def send_approval_cancel_email_notification(approval):
    # 28 Cancelled
    # email to licence/permit holder when licence/permit is cancelled
    email = TemplateEmailBase(
        subject='Cancellation of your {} {}'.format(approval.description, approval.lodgement_number),
        # html_template='mooringlicensing/emails/approval_cancel_notification.html',
        # txt_template='mooringlicensing/emails/approval_cancel_notification.txt',
        html_template='mooringlicensing/emails_2/email_28.html',
        txt_template='mooringlicensing/emails_2/email_28.txt',
    )
    proposal = approval.current_proposal

    context = {
        'public_url': get_public_url(),
        'approval': approval,
        'recipient': approval.submitter,
        'cancel_start_date': approval.cancellation_date,
        'details': approval.cancellation_details,
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
    # 29 Suspended
    # email to licence/permit holder when licence/permit is suspended
    email = TemplateEmailBase(
        subject='Suspension of your {} {}'.format(approval.description, approval.lodgement_number),
        # html_template='mooringlicensing/emails/approval_suspend_notification.html',
        # txt_template='mooringlicensing/emails/approval_suspend_notification.txt',
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
        'recipient': approval.submitter,
        'public_url': get_public_url(request),
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
    # 30 Surrendered
    # email to licence/permit holder when licence/permit is surrendered
    email = TemplateEmailBase(
        subject='Surrendered: Rottnest Island {} {} - Effective {}'.format(approval.description, approval.lodgement_number, approval.surrender_details['surrender_date']),
        # html_template='mooringlicensing/emails/approval_surrender_notification.html',
        # txt_template='mooringlicensing/emails/approval_surrender_notification.txt',
        html_template='mooringlicensing/emails_2/email_30.html',
        txt_template='mooringlicensing/emails_2/email_30.txt',
    )
    proposal = approval.current_proposal

    if request and 'test-emails' in request.path_info:
        details = 'This are my test details'
        surrender_date = '01/01/1970'
    else:
        details = approval.surrender_details['details'],
        surrender_date = approval.surrender_details['surrender_date'],

    context = {
        'public_url': get_public_url(request),
        'approval': approval,
        'recipient': approval.submitter,
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


def send_approval_reinstate_email_notification(approval, request):
    # 31 Reinstated
    # email to licence/permit holder when licence/permit is reinstated or when suspension ends
    email = TemplateEmailBase(
        subject='Reinstated: Rottnest Island {} {}'.format(approval.description, approval.lodgement_number),
        # html_template='mooringlicensing/emails/approval_reinstate_notification.html',
        # txt_template='mooringlicensing/emails/approval_reinstate_notification.txt',
        html_template='mooringlicensing/emails_2/email_31.html',
        txt_template='mooringlicensing/emails_2/email_31.txt',
    )
    proposal = approval.current_proposal

    context = {
        'public_url': get_public_url(request),
        'approval': approval,
        'recipient': approval.submitter,
        'details': '',  # TODO
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
        subject='Vessel Removed from Rottnest Island Mooring Site Licence {} - Notice to Return Sticker to RIA'.format(mooring_name),
        html_template='mooringlicensing/emails_2/email_32.html',
        txt_template='mooringlicensing/emails_2/email_32.txt',
    )

    attachments = []
    attachment = approval.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(request),
        'recipient': approval.submitter,
        'vessel_rego_no': vessel_ownership.vessel.rego_no,
        'stickers_to_be_returned': stickers_to_be_returned,
        'due_date': due_date,
        'dashboard_external_url': get_public_url(request),
    }
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]

    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context, attachments=attachments)

    sender = request.user if request else settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender, attachments=attachments)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender)


def send_reissue_wla_after_sale_recorded_email(approval, request, vessel_ownership, stickers_to_be_returned):
    # 33 (only for WLA)
    # email to licence or waitlist holder upon automatic re-issue after date of sale is recorded (regardless of whether new vessel added at that time)
    proposal = approval.current_proposal

    sale_date = vessel_ownership.end_date
    six_months = relativedelta(months=6)
    due_date = sale_date + six_months

    email = TemplateEmailBase(
        subject='Vessel Removed from Rottnest Island Mooring Site Licence Waiting List Allocation',
        html_template='mooringlicensing/emails_2/email_33.html',
        txt_template='mooringlicensing/emails_2/email_33.txt',
    )

    attachments = []
    attachment = approval.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(request),
        'recipient': approval.submitter,
        'vessel_rego_no': vessel_ownership.vessel.rego_no,
        'stickers_to_be_returned': stickers_to_be_returned,
        'due_date': due_date,
        'dashboard_external_url': get_public_url(request),
    }
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]

    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context, attachments=attachments)

    sender = request.user if request else settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender, attachments=attachments)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender)


def send_reissue_aup_after_sale_recorded_email(approval, request, vessel_ownership, stickers_to_be_returned):
    # 34 (only for AUP)
    # email to authorised user permit holder upon automatic re-issue after date of sale is recorded (regardless of whether new vessel added at that time)
    proposal = approval.current_proposal

    # Calculate new vessle nomination due date
    sale_date = vessel_ownership.end_date
    six_months = relativedelta(months=6)
    due_date = sale_date + six_months

    email = TemplateEmailBase(
        subject='Vessel Removed from Rottnest Island Authorised User Permit - Notice to Return Sticker(s) to RIA',
        html_template='mooringlicensing/emails_2/email_34.html',
        txt_template='mooringlicensing/emails_2/email_34.txt',
    )

    attachments = []
    attachment = approval.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(request),
        'recipient': approval.submitter,
        'vessel_rego_no': vessel_ownership.vessel.rego_no,
        'stickers_to_be_returned': stickers_to_be_returned,
        'due_date': due_date,
        'dashboard_external_url': get_public_url(request),
    }
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]

    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context, attachments=attachments)

    sender = request.user if request else settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender, attachments=attachments)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender)


def send_reissue_aap_after_sale_recorded_email(approval, request, vessel_ownership, stickers_to_be_returned):
    # 35 (only for AAP)
    # email to annual admission permit holder upon automatic re-issue after date of sale is recorded (regardless of whether new vessel added at that time)
    proposal = approval.current_proposal

    # Calculate new vessle nomination due date
    sale_date = vessel_ownership.end_date
    six_months = relativedelta(months=6)
    due_date = sale_date + six_months

    email = TemplateEmailBase(
        subject='Vessel Removed from Rottnest Island Annual Admission Permit - Notice to Return Sticker to RIA',
        html_template='mooringlicensing/emails_2/email_35.html',
        txt_template='mooringlicensing/emails_2/email_35.txt',
    )

    attachments = []
    attachment = approval.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(request),
        'recipient': approval.submitter,
        'vessel_rego_no': vessel_ownership.vessel.rego_no,
        'stickers_to_be_returned': stickers_to_be_returned,
        'due_date': due_date,
        'dashboard_external_url': get_public_url(request),
    }
    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]

    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context, attachments=attachments)

    sender = request.user if request else settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender, attachments=attachments)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender)


def send_sticker_replacement_email(request, old_sticker, new_sticker, invoice):
    # 36
    # email to licence/permit holder when sticker replacement request has been submitted (with payment)
    approval = new_sticker.approval
    proposal = approval.current_proposal

    email = TemplateEmailBase(
        subject='Sticker Replacement for {} - Rottnest Island Authority'.format(approval.description),
        html_template='mooringlicensing/emails_2/email_36.html',
        txt_template='mooringlicensing/emails_2/email_36.txt',
    )

    # Attach invoice
    attachments = []
    invoice_bytes = create_invoice_pdf_bytes('invoice.pdf', invoice, )
    attachment = ('invoice#{}.pdf'.format(invoice.reference), invoice_bytes, 'application/pdf')
    attachments.append(attachment)

    context = {
        'public_url': get_public_url(request),
        'recipient': approval.submitter,
        'sticker': old_sticker,
        'dashboard_external_url': get_public_url(request),
    }

    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]

    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context, attachments=attachments)

    sender = request.user if request else settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender, attachments=attachments)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender)


def send_aup_revoked_due_to_mooring_swap_email(request, authorised_user_permit, mooring, stickers_to_be_returned):
    # 37
    # email to authorised user when mooring site authorisation revoked due to licensee mooring swap and to return sticker
    proposal = authorised_user_permit.current_proposal
    approval = authorised_user_permit

    email = TemplateEmailBase(
        subject='Authorised Use of {} Cancelled Due to Licensee Mooring Swap - Notice to Return Sticker(s) - Rottnest Island Authority'.format(mooring.name),
        html_template='mooringlicensing/emails_2/email_37.html',
        txt_template='mooringlicensing/emails_2/email_37.txt',
    )

    attachments = []
    attachment = authorised_user_permit.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(request),
        'recipient': authorised_user_permit.submitter,
        'mooring': mooring,
        'stickers_to_be_returned': stickers_to_be_returned,
        'dashboard_external_url': get_public_url(request),
    }

    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]

    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context, attachments=attachments)

    sender = request.user if request else settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender, attachments=attachments)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender)


def send_aup_revoked_due_to_relinquishment_email(request, authorised_user_permit, mooring, stickers_to_be_returned):
    # 38
    # email to authorised user when mooring site authorisation revoked due to mooring site licence relinquishment and to return sticker
    proposal = authorised_user_permit.current_proposal
    approval = authorised_user_permit

    email = TemplateEmailBase(
        subject='Authorised Use of {} Cancelled Due to Relinquishment - Notice to Return Sticker(s) - Rottnest Island Authority'.format(mooring.name),
        html_template='mooringlicensing/emails_2/email_38.html',
        txt_template='mooringlicensing/emails_2/email_38.txt',
    )

    attachments = []
    attachment = authorised_user_permit.get_licence_document_as_attachment()
    if attachment:
        attachments.append(attachment)

    context = {
        'public_url': get_public_url(request),
        'recipient': authorised_user_permit.submitter,
        'mooring': mooring,
        'stickers_to_be_returned': stickers_to_be_returned,
        'dashboard_external_url': get_public_url(request),
    }

    all_ccs = []
    if proposal.org_applicant and proposal.org_applicant.email:
        cc_list = proposal.org_applicant.email
        if cc_list:
            all_ccs = [cc_list]

    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context, attachments=attachments)

    sender = request.user if request else settings.DEFAULT_FROM_EMAIL
    _log_approval_email(msg, approval, sender=sender, attachments=attachments)
    if approval.org_applicant:
        _log_org_email(msg, approval.org_applicant, proposal.submitter, sender=sender)
    else:
        _log_user_email(msg, approval.submitter, proposal.submitter, sender=sender)

# 39
# email to account holder with authentication link to complete login process
# TODO: can we overwrite this template served by the ledger?
