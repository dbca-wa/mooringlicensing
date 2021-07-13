from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from ledger.accounts.models import EmailUser

from mooringlicensing.components.approvals.models import Approval
from mooringlicensing.components.compliances.models import Compliance, ComplianceUserAction
from mooringlicensing.components.main.models import NumberOfDaysSetting
import datetime

import logging


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Change the status of Compliances from future to due when they are close to due date'

    def handle(self, *args, **options):
        today = timezone.localtime(timezone.now()).date()
        number_of_days = NumberOfDaysSetting.get_setting_by_date(today)
        compare_date = today + datetime.timedelta(days=number_of_days)

        try:
            user = EmailUser.objects.get(email=settings.CRON_EMAIL)
        except:
            user = EmailUser.objects.create(email=settings.CRON_EMAIL, password='')

        errors = []
        updates = []
        logger.info('Running command {}'.format(__name__))
        for c in Compliance.objects.filter(processing_status=Compliance.PROCESSING_STATUS_FUTURE):
            if(c.due_date <= compare_date) and (c.due_date <= c.approval.expiry_date) and c.approval.status == Approval.APPROVAL_STATUS_CURRENT:
                try:
                    c.processing_status = Compliance.PROCESSING_STATUS_DUE
                    c.customer_status = Compliance.CUSTOMER_STATUS_DUE
                    c.save()
                    ComplianceUserAction.log_action(c, ComplianceUserAction.ACTION_STATUS_CHANGE.format(c.id), user)
                    logger.info('updated Compliance {} status to {}'.format(c.id, c.processing_status))
                    updates.append(c.lodgement_number)
                except Exception as e:
                    err_msg = 'Error updating Compliance {} status'.format(c.lodgement_number)
                    logger.error('{}\n{}'.format(err_msg, str(e)))
                    errors.append(err_msg)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        err_str = '<strong style="color: red;">Errors: {}</strong>'.format(len(errors)) if len(errors) > 0 else '<strong style="color: green;">Errors: 0</strong>'
        msg = '<p>{} completed. {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        logger.info(msg)
        print(msg)  # will redirect to cron_tasks.log file, by the parent script
