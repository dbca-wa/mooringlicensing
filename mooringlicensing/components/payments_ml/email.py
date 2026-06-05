from mooringlicensing import settings
from mooringlicensing.components.emails.emails import TemplateEmailBase, _extract_email_headers
from mooringlicensing.components.emails.utils import get_public_url


class ApplicationSubmitConfirmationEmail(TemplateEmailBase):
    subject = 'Your application has been successfully submitted.'
    html_template = 'mooringlicensing/emails/application_submit_confirmation_email.html'
    txt_template = 'mooringlicensing/emails/application_submit_confirmation_email.txt'


def send_application_submit_confirmation_email(request, proposal, to_email_addresses):
    email = ApplicationSubmitConfirmationEmail()

    context = {
        'public_url': get_public_url(),
        'proposal': proposal,
    }

    attachments = []
    to_address = to_email_addresses
    cc = []
    bcc = []

    msg = email.send(
        to_address,
        context=context,
        attachments=attachments,
        cc=cc,
        bcc=bcc,
    )

    if msg:
        sender = settings.DEFAULT_FROM_EMAIL
        email_data = _extract_email_headers(msg, sender=sender)
        return email_data

