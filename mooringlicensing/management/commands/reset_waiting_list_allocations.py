from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from mooringlicensing.components.main.utils import reset_waiting_list_allocations
from mooringlicensing.components.main.models import GlobalSettings
from mooringlicensing.components.approvals.models import WaitingListAllocation
#from ledger.accounts.models import EmailUser
from datetime import date, timedelta
#from commercialoperator.components.approvals.email import (
 #   send_approval_renewal_email_notification,)

import itertools

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reset Waiting List Allocations'

    def handle(self, *args, **options):
        #print("import data")
        #import ipdb; ipdb.set_trace()

        #errors = []
        #updates = []
        #today = timezone.localtime(timezone.now()).date()
        today = timezone.localtime(timezone.now())
        #expiry_notification_date = today + timedelta(days=90)
        day_offset_str = GlobalSettings.objects.get(key="reset_waiting_list_allocation_days").value
        day_offset = int(day_offset_str.strip())
        cutoff = today - timedelta(days=day_offset)
        wla_list = WaitingListAllocation.objects.filter(wla_queue_date__lte=cutoff, status='offered')
        print("wla_list")
        print(wla_list)

        errors, updates = reset_waiting_list_allocations(wla_list)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        err_str = '<strong style="color: red;">Errors: {}</strong>'.format(len(errors)) if len(errors)>0 else '<strong style="color: green;">Errors: 0</strong>'
        msg = '<p>{} completed. Errors: {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        logger.info(msg)
        print(msg) # will redirect to cron_tasks.log file, by the parent script

