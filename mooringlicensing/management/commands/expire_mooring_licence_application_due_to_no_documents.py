from datetime import timedelta
from django.utils import timezone

from django.core.management.base import BaseCommand
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

import logging

from mooringlicensing.components.proposals.email import send_expire_mla_notification_to_assessor, send_expire_mooring_licence_by_no_documents_email
from mooringlicensing.components.main.models import NumberOfDaysType, NumberOfDaysSetting
from mooringlicensing.components.proposals.models import Proposal, MooringLicenceApplication
from mooringlicensing.management.commands.utils import construct_email_message
from mooringlicensing.settings import CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA

logger = logging.getLogger('cron_tasks')
cron_email = logging.getLogger('cron_email')


class Command(BaseCommand):
    help = 'Expire mooring site licence application if additional documents are not submitted within a configurable number of days from the initial submit of the mooring licence application and email to inform the applicant'

    def handle(self, *args, **options):
        errors = []
        updates = []
        today = timezone.localtime(timezone.now()).date()

        # Retrieve the number of days before expiry date of the approvals to email
        days_type = NumberOfDaysType.objects.filter(code=CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA).first()
        days_setting = NumberOfDaysSetting.get_setting_by_date(days_type, today)
        if not days_setting:
            # No number of days found
            raise ImproperlyConfigured("NumberOfDays: {} is not defined for the date: {}".format(days_type.name, today))

        # Condition to expire
        #   lodgement_date + number_of_days < today
        #   Transform the formula in order to directly use this conditional in query
        #   lodgement_date < today - number_of_days
        boundary_date = today - timedelta(days=days_setting.number_of_days)

        logger.info('Running command {}'.format(__name__))

        # Construct queries
        queries = Q()
        queries &= Q(processing_status=Proposal.PROCESSING_STATUS_AWAITING_DOCUMENTS)
        queries &= Q(lodgement_date__lt=boundary_date)

        for a in MooringLicenceApplication.objects.filter(queries):
            try:
                a.processing_status = Proposal.PROCESSING_STATUS_EXPIRED
                a.save()
                # reset Waiting List order
                due_date = a.lodgement_date + timedelta(days=days_setting.number_of_days)
                send_expire_mooring_licence_by_no_documents_email(a, MooringLicenceApplication.REASON_FOR_EXPIRY_NO_DOCUMENTS, due_date)
                send_expire_mla_notification_to_assessor(a, MooringLicenceApplication.REASON_FOR_EXPIRY_NO_DOCUMENTS, due_date)
                logger.info('Expired notification sent for Proposal {}'.format(a.lodgement_number))
                updates.append(a.lodgement_number)
            except Exception as e:
                err_msg = 'Error sending expired notification for Proposal {}'.format(a.lodgement_number)
                logger.error('{}\n{}'.format(err_msg, str(e)))
                errors.append(err_msg)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        msg = construct_email_message(cmd_name, errors, updates)
        logger.info(msg)
        cron_email.info(msg)
