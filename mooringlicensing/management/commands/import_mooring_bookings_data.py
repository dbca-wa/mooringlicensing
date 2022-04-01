from django.core.management.base import BaseCommand
from mooringlicensing.components.main.utils import import_mooring_bookings_data
import logging

logger = logging.getLogger('cron_tasks')
cron_email = logging.getLogger('cron_email')


class Command(BaseCommand):
    help = 'Import Mooring Bookings data'

    def handle(self, *args, **options):
        errors, updates = import_mooring_bookings_data()

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        err_str = '<strong style="color: red;">Errors: {}</strong>'.format(len(errors)) if len(errors)>0 else '<strong style="color: green;">Errors: 0</strong>'
        msg = '<p>{} completed. Errors: {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        logger.info(msg)
        cron_email.info(msg)

