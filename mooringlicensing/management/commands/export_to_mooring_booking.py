from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from mooringlicensing.components.main.utils import export_to_mooring_booking
from mooringlicensing.components.approvals.models import Approval
from datetime import date, timedelta

import itertools

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Export to Mooring Bookings VesselLicence'

    def handle(self, *args, **options):
        #errors, updates = import_mooring_bookings_data()
        approvals_to_export = Approval.objects.filter(export_to_mooring_booking=True)
        if approvals_to_export:
            errors = []
            updates = []
            updates.append('Approvals remaining to export: {}'.format(str(Approval.objects.filter(export_to_mooring_booking=True).count())))
            approvals_to_process = approvals_to_export[:30]
            for approval in approvals_to_process:
                approval_errors, approval_updates = export_to_mooring_booking(approval.id)
                errors.extend(approval_errors)
                updates.extend(approval_updates)
            updates.append('Approvals remaining to export: {}'.format(str(Approval.objects.filter(export_to_mooring_booking=True).count())))
            # write email
            cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
            err_str = '<strong style="color: red;">Errors: {}</strong>'.format(len(errors)) if len(errors)>0 else '<strong style="color: green;">Errors: 0</strong>'
            msg = '<p>{} completed. Total Errors: {}:{}. IDs updated: {}.</p>'.format(cmd_name, err_str, errors, updates)
            #logger.info(msg)
            print(msg)  # will redirect to run_cron_tasks.log file, by the parent script
