from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from ledger.accounts.models import EmailUser

import logging

from mooringlicensing.components.proposals.email import send_invitee_reminder_email
from mooringlicensing.components.main.models import NumberOfDaysType, NumberOfDaysSetting
from mooringlicensing.components.proposals.models import Proposal, MooringLicenceApplication
from mooringlicensing.settings import CODE_DAYS_IN_PERIOD_WLA, CODE_DAYS_BEFORE_PERIOD_WLA

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send email to waiting list allocation holder invited to apply for a mooring licence configurable number of days before end of configurable period in which the mooring licence application needs to be submitted'

    def handle(self, *args, **options):
        try:
            user = EmailUser.objects.get(email=settings.CRON_EMAIL)
        except:
            user = EmailUser.objects.create(email=settings.CRON_EMAIL, password='')

        errors = []
        updates = []
        today = timezone.localtime(timezone.now()).date()

        # Retrieve the number of days before expiry date of the approvals to email
        days_type_period = NumberOfDaysType.objects.get(code=CODE_DAYS_IN_PERIOD_WLA)
        days_setting_period = NumberOfDaysSetting.get_setting_by_date(days_type_period, today)
        if not days_setting_period:
            raise ImproperlyConfigured("NumberOfDays: {} is not defined for the date: {}".format(days_type_period.name, today))

        days_type_before = NumberOfDaysType.objects.get(code=CODE_DAYS_BEFORE_PERIOD_WLA)
        days_setting_before = NumberOfDaysSetting.get_setting_by_date(days_type_before, today)
        if not days_setting_before:
            raise ImproperlyConfigured("NumberOfDays: {} is not defined for the date: {}".format(days_type_before.name, today))

        boundary_date = today - timedelta(days=days_setting_period.number_of_days) + timedelta(days=days_setting_before.number_of_days)

        logger.info('Running command {}'.format(__name__))

        # Construct queries
        queries = Q()
        queries &= Q(processing_status=Proposal.PROCESSING_STATUS_DRAFT)
        queries &= Q(lodgement_date__lt=boundary_date)
        queries &= Q(invitee_reminder_sent=False)

        # For debug
        params = options.get('params')
        debug = True if params.get('debug', 'f').lower() in ['true', 't', 'yes', 'y'] else False
        approval_lodgement_number = params.get('send_mooring_licence_application_submit_due_reminder_lodgement_number', 'no-lodgement-number')
        if debug:
            queries = queries | Q(lodgement_number__iexact=approval_lodgement_number)

        for a in MooringLicenceApplication.objects.filter(queries):
            try:
                send_invitee_reminder_email(a)
                a.invitee_reminder_sent = True
                a.save()
                logger.info('Reminder to invitee sent for Proposal {}'.format(a.lodgement_number))
                updates.append(a.lodgement_number)
            except Exception as e:
                err_msg = 'Error sending reminder to invitee for Proposal {}'.format(a.lodgement_number)
                logger.error('{}\n{}'.format(err_msg, str(e)))
                errors.append(err_msg)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        err_str = '<strong style="color: red;">Errors: {}</strong>'.format(len(errors)) if len(errors) > 0 else '<strong style="color: green;">Errors: 0</strong>'
        msg = '<p>{} completed. {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        logger.info(msg)
        print(msg)  # will redirect to cron_tasks.log file, by the parent script
