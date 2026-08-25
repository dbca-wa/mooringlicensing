from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

import logging

from mooringlicensing.components.approvals.email import send_approval_cancelled_due_to_no_vessels_nominated_mail
from mooringlicensing.components.approvals.models import Approval, WaitingListAllocation, MooringLicence
from mooringlicensing.management.commands.utils import ml_meet_vessel_requirement, construct_email_message
from mooringlicensing.settings import AUTO_CANCEL_APPROVAL_WHEN_GRACE_PERIOD_EXPIRED

logger = logging.getLogger('cron_tasks')
cron_email = logging.getLogger('cron_email')


class Command(BaseCommand):
    help = 'Send email to WL/ML holder configurable number of days before end of six month period in which a new vessel is to be nominated'

    def handle(self, *args, **options):
        today = timezone.localtime(timezone.now()).date()

        self.perform(WaitingListAllocation.code, today, **options)
        self.perform(MooringLicence.code, today, **options)

    def perform(self, approval_type, today, **options):
        errors = []
        updates = []

        # Retrieve the number of days before expiry date of the approvals to email
        if approval_type == WaitingListAllocation.code:
            approval_class = WaitingListAllocation
        elif approval_type == MooringLicence.code:
            approval_class = MooringLicence
        else:
            # Do nothing
            return

        # NOTE: When sending the reminder:
        #       sold_date + 6months < today
        #       sold_date < today - 6months
        boundary_date = today - relativedelta(months=+6)

        logger.info('Running command {}'.format(__name__))

        # Get approvals
        if approval_type == WaitingListAllocation.code:
            queries = Q()
            queries &= Q(status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED))
            queries &= Q(current_proposal__vessel_ownership__end_date__isnull=False)
            queries &= Q(current_proposal__vessel_ownership__end_date__lt=boundary_date)
            queries &= Q(vessel_nomination_reminder_sent=False)  # Is this correct?  SHould be True?
            approvals = approval_class.objects.filter(queries)
        elif approval_type == MooringLicence.code:
            queries = Q()
            queries &= Q(status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED))
            queries &= Q(vessel_nomination_reminder_sent=False)  # Is this correct?  SHould be True?
            possible_approvals = approval_class.objects.filter(queries)

            approvals = []
            for approval in possible_approvals:
                # Check if there is at least one vessel which meets the ML vessel requirement
                if not ml_meet_vessel_requirement(approval, boundary_date):
                    approvals.append(approval)

        for a in approvals:
            try:
                if AUTO_CANCEL_APPROVAL_WHEN_GRACE_PERIOD_EXPIRED:
                    send_approval_cancelled_due_to_no_vessels_nominated_mail(a)
                    a.status = Approval.APPROVAL_STATUS_CANCELLED
                    a.export_to_mooring_booking = True
                    a.save()
                    logger.info(f'Grace period of the Approval: [{a}] has been expired.  The approval has been cancelled.')
                    logger.info('Cancel notification to permission holder sent for Approval {}'.format(a.lodgement_number))
                    updates.append(a.lodgement_number)
                else:
                    logger.info(f'Grace period of the Approval: [{a}] has been expired.  However no automated processes have been triggered.')
            except Exception as e:
                err_msg = 'Error sending cancel notification to permission holder for Approval {}'.format(a.lodgement_number)
                logger.error('{}\n{}'.format(err_msg, str(e)))
                errors.append(err_msg)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        msg = construct_email_message(cmd_name, errors, updates)
        logger.info(msg)
        cron_email.info(msg)
