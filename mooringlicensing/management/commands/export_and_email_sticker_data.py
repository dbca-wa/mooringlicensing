from django.core.management.base import BaseCommand

from mooringlicensing.components.main.utils import sticker_export, email_stickers_document

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Export and email sticker data'

    def handle(self, *args, **options):
        errors = []
        updates = []

        updates, errors = sticker_export()
        success_filenames, error_filenames = email_stickers_document()

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        error_count = len(errors) + len(error_filenames)
        err_str = '<strong style="color: red;">Errors: {}</strong>'.format(error_count) if error_count else '<strong style="color: green;">Errors: 0</strong>'
        msg = '<p>{} completed. {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        logger.info(msg)
        print(msg)  # will redirect to cron_tasks.log file, by the parent script
