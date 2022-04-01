from datetime import timedelta
from ledger.accounts.models import EmailUser

from django.utils import timezone
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

import logging

from mooringlicensing.components.proposals.email import send_expire_mooring_licence_application_email, \
    send_expire_mla_notification_to_assessor
from mooringlicensing.components.main.models import NumberOfDaysType, NumberOfDaysSetting
from mooringlicensing.components.proposals.models import Proposal, MooringLicenceApplication
from mooringlicensing.management.commands.utils import construct_email_message
from mooringlicensing.settings import CODE_DAYS_IN_PERIOD_MLA

logger = logging.getLogger('cron_tasks')
cron_email = logging.getLogger('cron_email')


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
        days_type = NumberOfDaysType.objects.get(code=CODE_DAYS_IN_PERIOD_MLA)
        days_setting = NumberOfDaysSetting.get_setting_by_date(days_type, today)
        if not days_setting:
            # No number of days found
            raise ImproperlyConfigured("NumberOfDays: {} is not defined for the date: {}".format(days_type.name, today))
        boundary_date = today - timedelta(days=days_setting.number_of_days)

        logger.info('Running command {}'.format(__name__))

        # Construct queries
        # MLA and associated documents must be submitted within X days period after invitation
        queries = Q()
        queries &= Q(processing_status__in=(Proposal.PROCESSING_STATUS_DRAFT, Proposal.PROCESSING_STATUS_AWAITING_DOCUMENTS))
        queries &= Q(date_invited__lt=boundary_date)

        # For debug
        # params = options.get('params')
        # debug = True if params.get('debug', 'f').lower() in ['true', 't', 'yes', 'y'] else False
        # approval_lodgement_number = params.get('expire_mooring_licence_application_due_to_no_submit_lodgement_number', 'no-lodgement-number')
        # if debug:
        #     queries = queries | Q(lodgement_number__iexact=approval_lodgement_number)

        for a in MooringLicenceApplication.objects.filter(queries):
            try:
                a.processing_status = Proposal.PROCESSING_STATUS_EXPIRED
                a.customer_status = Proposal.CUSTOMER_STATUS_EXPIRED
                a.save()
                # update WLA internal_status and queue date
                a.waiting_list_allocation.internal_status = 'waiting'
                a.waiting_list_allocation.wla_queue_date = today
                a.waiting_list_allocation.save()
                # reset Waiting List order
                a.waiting_list_allocation.set_wla_order()

                due_date = a.date_invited + timedelta(days=days_setting.number_of_days)
                send_expire_mooring_licence_application_email(a, MooringLicenceApplication.REASON_FOR_EXPIRY_NOT_SUBMITTED, due_date)
                send_expire_mla_notification_to_assessor(a, MooringLicenceApplication.REASON_FOR_EXPIRY_NO_DOCUMENTS, due_date)
                logger.info('Expired notification sent for Proposal {}'.format(a.lodgement_number))
                updates.append(a.lodgement_number)
            except Exception as e:
                err_msg = 'Error sending expired notification for Proposal {}'.format(a.lodgement_number)
                logger.error('{}\n{}'.format(err_msg, str(e)))
                errors.append(err_msg)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        # err_str = '<strong style="color: red;">Errors: {}</strong>'.format(len(errors)) if len(errors) > 0 else '<strong style="color: green;">Errors: 0</strong>'
        # msg = '<p>{} completed. {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        msg = construct_email_message(cmd_name, errors, updates)
        logger.info(msg)
        cron_email.info(msg)
