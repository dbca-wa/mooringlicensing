from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from mooringlicensing.components.main.utils import import_mooring_bookings_data
#from ledger.accounts.models import EmailUser
from datetime import date, timedelta
#from commercialoperator.components.approvals.email import (
 #   send_approval_renewal_email_notification,)

import itertools

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import Mooring Bookings data'

    def handle(self, *args, **options):
        #print("import data")
        #import ipdb; ipdb.set_trace()
        errors, updates = import_mooring_bookings_data()

        #errors = []
        #updates = []
        #today = timezone.localtime(timezone.now()).date()
        #expiry_notification_date = today + timedelta(days=90)
        #renewal_conditions = {
        #    'expiry_date__lte': expiry_notification_date,
        #    'renewal_sent': False,
        #    'replaced_by__isnull': True,
        #}
        #logger.info('Running command {}'.format(__name__))

        ## 2 month licences cannot be renewed
        #exclude_application_types=[ApplicationType.FILMING, ApplicationType.EVENT,ApplicationType.ECLASS ]
        ##qs=Approval.objects.filter(**renewal_conditions).exclude(current_proposal__other_details__preferred_licence_period='2_months').exclude(current_proposal__application_type__name='E Class')
        #qs=Approval.objects.filter(**renewal_conditions).exclude(current_proposal__other_details__preferred_licence_period='2_months').exclude(current_proposal__application_type__name__in=exclude_application_types)
        #logger.info('{}'.format(qs))
        #for a in qs:
        #    if a.status == 'current' or a.status == 'suspended':
        #        try:
        #            a.generate_renewal_doc()
        #            send_approval_renewal_email_notification(a)
        #            a.renewal_sent = True
        #            a.save()
        #            logger.info('Renewal notice sent for Approval {}'.format(a.id))
        #            updates.append(a.lodgement_number)
        #        except Exception as e:
        #            err_msg = 'Error sending renewal notice for Approval {}'.format(a.lodgement_number)
        #            logger.error('{}\n{}'.format(err_msg, str(e)))
        #            errors.append(err_msg)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        err_str = '<strong style="color: red;">Errors: {}</strong>'.format(len(errors)) if len(errors)>0 else '<strong style="color: green;">Errors: 0</strong>'
        msg = '<p>{} completed. Errors: {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        logger.info(msg)
        print(msg) # will redirect to cron_tasks.log file, by the parent script

