from datetime import timedelta
from ledger.accounts.models import EmailUser

from django.utils import timezone
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

import logging

from mooringlicensing.components.proposals.email import send_expire_mooring_licence_application_email
from mooringlicensing.components.main.models import NumberOfDaysType, NumberOfDaysSetting
from mooringlicensing.components.proposals.models import Proposal, MooringLicenceApplication
from mooringlicensing.settings import CODE_DAYS_IN_PERIOD_WLA

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'expire mooring licence application if not submitted within configurable number of days after being invited to apply for a mooring licence and send email to inform waiting list allocation holder'

    def handle(self, *args, **options):
        try:
            user = EmailUser.objects.get(email=settings.CRON_EMAIL)
        except:
            user = EmailUser.objects.create(email=settings.CRON_EMAIL, password='')

        errors = []
        updates = []
        today = timezone.localtime(timezone.now()).date()

        # Retrieve the number of days before expiry date of the approvals to email
        days_type = NumberOfDaysType.objects.get(code=CODE_DAYS_IN_PERIOD_WLA)
        days_setting = NumberOfDaysSetting.get_setting_by_date(days_type, today)
        if not days_setting:
            # No number of days found
            raise ImproperlyConfigured("NumberOfDays: {} is not defined for the date: {}".format(days_type.name, today))
        boundary_date = today - timedelta(days=days_setting.number_of_days)

        logger.info('Running command {}'.format(__name__))

        # Construct queries
        queries = Q()
        queries &= Q(processing_status=Proposal.PROCESSING_STATUS_DRAFT)
        queries &= Q(date_invited__lt=boundary_date)

        # For debug
        params = options.get('params')
        debug = True if params.get('debug', 'f').lower() in ['true', 't', 'yes', 'y'] else False
        approval_lodgement_number = params.get('expire_mooring_licence_application_due_to_no_submit_lodgement_number', 'no-lodgement-number')
        if debug:
            queries = queries | Q(lodgement_number__iexact=approval_lodgement_number)

        for a in MooringLicenceApplication.objects.filter(queries):
            try:
                a.processing_status = Proposal.PROCESSING_STATUS_EXPIRED
                a.customer_status = Proposal.CUSTOMER_STATUS_EXPIRED
                a.save()
                send_expire_mooring_licence_application_email(a, MooringLicenceApplication.REASON_FOR_EXPIRY_NOT_SUBMITTED)
                logger.info('Expired notification sent for Proposal {}'.format(a.lodgement_number))
                updates.append(a.lodgement_number)
            except Exception as e:
                err_msg = 'Error sending expired notification for Proposal {}'.format(a.lodgement_number)
                logger.error('{}\n{}'.format(err_msg, str(e)))
                errors.append(err_msg)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        err_str = '<strong style="color: red;">Errors: {}</strong>'.format(len(errors)) if len(errors) > 0 else '<strong style="color: green;">Errors: 0</strong>'
        msg = '<p>{} completed. {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        logger.info(msg)
        print(msg)  # will redirect to cron_tasks.log file, by the parent script
