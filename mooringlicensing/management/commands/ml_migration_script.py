from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from pathlib import Path
from mooringlicensing.utils.excel_export import mla_to_excel
from mooringlicensing.utils.excel_export import authusers_to_excel
from mooringlicensing.utils.excel_export import dcvpermits_to_excel
from mooringlicensing.utils.excel_export import wla_to_excel
from mooringlicensing.utils.excel_export import annualadmission_to_excel
import time

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Run the MooringLicensing Migration Script \n' \
           'python manage_ml.py ml_migration_script --filename /var/www/mooringlicensing/mooringlicensing/utils/excel_export/annual_admissions_booking_report_20220612150512.csv'

    def add_arguments(self, parser):
        parser.add_argument('--filename', type=str)

    def handle(self, *args, **options):
        filename = options['filename']
        t_start = time.time()

        logger.info('Writing ML to Excel')
        mla_to_excel.write()

        logger.info('Writing AuthUsers to Excel')
        authusers_to_excel.write()

        logger.info('Writing DCV Permits to Excel')
        dcvpermits_to_excel.write()

        logger.info('Writing WLA to Excel')
        wla_to_excel.write()

        logger.info('Writing Annual Admissions to Excel')
        annualadmission_to_excel.write(filename)

        t_end = time.time()
        logger.info('TIME TAKEN: {}'.format(t_end - t_start))

