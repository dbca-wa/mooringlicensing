from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from pathlib import Path
import subprocess
import logging

from mooringlicensing.settings import CRON_EMAIL_FILE_NAME

logger = logging.getLogger('cron_tasks')
cron_email = logging.getLogger('cron_email')
LOGFILE = 'logs/' + CRON_EMAIL_FILE_NAME  # This file is used temporarily.  It's cleared whenever this cron starts, then at the end the contents of this file is emailed.


class Command(BaseCommand):
    help = 'Run Mooring Licensing Cron tasks'

    def handle(self, *args, **options):
        # Empty the cron email log file because this file is used only for the contents of the nightly cron email
        # We don't want to accumulate the contents
        self.clear_cron_email_log()

        logger.info('===== Running command: {} ====='.format(__name__))
        cron_email.info('<div><strong>Running command: {}</strong></div>'.format(__name__))
        cron_email.info('<div style="margin-left: 1em;">')

        subprocess.call('python manage_ml.py update_compliance_status', shell=True)
        subprocess.call('python manage_ml.py send_compliance_reminder', shell=True)
        subprocess.call('python manage_ml.py send_endorser_reminder', shell=True)
        subprocess.call('python manage_ml.py send_vessel_nominate_reminder', shell=True)
        subprocess.call('python manage_ml.py cancel_approvals_due_to_no_vessels_nominated', shell=True)
        subprocess.call('python manage_ml.py expire_mooring_licence_application_due_to_no_documents', shell=True)
        subprocess.call('python manage_ml.py expire_mooring_licence_application_due_to_no_submit', shell=True)
        subprocess.call('python manage_ml.py update_approval_status', shell=True)
        subprocess.call('python manage_ml.py approval_renewal_notices', shell=True)
        subprocess.call('python manage_ml.py import_mooring_bookings_data', shell=True)
        subprocess.call('python manage_ml.py export_and_email_sticker_data', shell=True)
        subprocess.call('python manage_ml.py import_sticker_data', shell=True)
        subprocess.call('python manage_ml.py send_mooring_licence_application_submit_due_reminder', shell=True)

        logger.info('===== Completed command: {} ====='.format(__name__))
        cron_email.info('</div>')
        cron_email.info('<div><strong>Completed command: {}</strong></div>'.format(__name__))

        self.send_email()

    def send_email(self):
        email_instance = settings.EMAIL_INSTANCE
        contents_of_cron_email = Path(LOGFILE).read_text()
        subject = '{} - Cronjob'.format(settings.SYSTEM_NAME_SHORT)
        to = settings.CRON_NOTIFICATION_EMAIL if isinstance(settings.NOTIFICATION_EMAIL, list) else [settings.CRON_NOTIFICATION_EMAIL]
        msg = EmailMultiAlternatives(subject, contents_of_cron_email, settings.EMAIL_FROM, to,
            headers={'System-Environment': email_instance}
        )
        msg.attach_alternative(contents_of_cron_email, "text/html")
        msg.send()

    def clear_cron_email_log(self):
        with open(LOGFILE, 'w'):
            pass
