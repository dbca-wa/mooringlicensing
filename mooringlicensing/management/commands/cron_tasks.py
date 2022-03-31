from django.core.management.base import BaseCommand
from django.conf import settings
#from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives, EmailMessage
from pathlib import Path
import subprocess

import logging
logger = logging.getLogger(__name__)

#LOGFILE = 'logs/cron_tasks.log'
LOGFILE = 'logs/run_cron_tasks.log'


class Command(BaseCommand):
    help = 'Run Mooring Licensing Cron tasks'

    def handle(self, *args, **options):
        #print("cron tasks")
        stdout_redirect = ' | tee -a {}'.format(LOGFILE)
        subprocess.call('cat /dev/null > {}'.format(LOGFILE), shell=True)  # empty the log file

        logger.info('Running command {}'.format(__name__))
        subprocess.call('python manage_ml.py update_compliance_status' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py send_compliance_reminder' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py send_endorser_reminder' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py send_vessel_nominate_reminder' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py cancel_approvals_due_to_no_vessels_nominated' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py send_waiting_list_application_submit_due_reminder' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py expire_mooring_licence_application_due_to_no_documents' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py expire_mooring_licence_application_due_to_no_submit' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py update_approval_status' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py approval_renewal_notices' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py import_mooring_bookings_data' + stdout_redirect, shell=True) 
        subprocess.call('python manage_ml.py export_and_email_sticker_data' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py import_sticker_data' + stdout_redirect, shell=True)
        subprocess.call('python manage_ml.py send_mooring_licence_application_submit_due_reminder' + stdout_redirect, shell=True)

        logger.info('Command {} completed'.format(__name__))
        self.send_email()

    def send_email(self):
        #email_instance = env('EMAIL_INSTANCE','DEV')
        email_instance = settings.EMAIL_INSTANCE
        log_txt = Path(LOGFILE).read_text()
        subject = '{} - Cronjob'.format(settings.SYSTEM_NAME_SHORT)
        body = ''
        to = settings.CRON_NOTIFICATION_EMAIL if isinstance(settings.NOTIFICATION_EMAIL, list) else [settings.CRON_NOTIFICATION_EMAIL]
        msg = EmailMultiAlternatives(subject, log_txt, settings.EMAIL_FROM, to,
                #attachments=_attachments, cc=cc, bcc=bcc, 
                #reply_to=reply_to, 
                headers={'System-Environment': email_instance}
                )
        msg.attach_alternative(log_txt, "text/html")
        msg.send()
        #send_mail(subject, body, settings.EMAIL_FROM, to, fail_silently=False, html_message=log_txt,)

