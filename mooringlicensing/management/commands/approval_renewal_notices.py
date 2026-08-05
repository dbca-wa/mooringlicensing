from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from mooringlicensing.components.approvals.models import (
    Approval,
    WaitingListAllocation,
    AnnualAdmissionPermit,
    AuthorisedUserPermit,
    MooringLicence,
    DcvPermit, ApprovalUserAction,
)
from datetime import timedelta
from mooringlicensing.components.proposals.email import send_approval_renewal_email_notification

import logging

from mooringlicensing.components.main.models import NumberOfDaysType, NumberOfDaysSetting
from mooringlicensing.management.commands.utils import construct_email_message
from mooringlicensing.settings import (
    CODE_DAYS_FOR_RENEWAL_WLA,
    CODE_DAYS_FOR_RENEWAL_AAP,
    CODE_DAYS_FOR_RENEWAL_AUP,
    CODE_DAYS_FOR_RENEWAL_ML,
    CODE_DAYS_FOR_RENEWAL_DCVP,
    MAX_RENEWAL_NOTICES_PER_RUN,
)

logger = logging.getLogger('cron_tasks')
cron_email = logging.getLogger('cron_email')


class Command(BaseCommand):
    help = 'Send Approval renewal notice when approval is due to expire in X days'

    def perform_per_type(self, number_of_days_code, approval_class, updates, errors, max_renewal_notices):
        today = timezone.localtime(timezone.now()).date()

        # Retrieve the number of days before expiry date of the approvals to email
        days_type = NumberOfDaysType.objects.filter(code=number_of_days_code).first()
        days_setting = NumberOfDaysSetting.get_setting_by_date(days_type, today)
        if not days_setting:
            err_msg = "NumberOfDays: {} is not defined for the date: {}".format(days_type.name, today)
            # No number of days found
            errors.append(err_msg)
            raise ImproperlyConfigured(err_msg)

        expiry_notification_date = today + timedelta(days=days_setting.number_of_days)

        logger.info(f'Running command {__name__} for the approval type: {approval_class.description}.')

        # Construct queries
        queries = Q()
        if number_of_days_code == CODE_DAYS_FOR_RENEWAL_DCVP:
            queries &= Q(end_date__lte=expiry_notification_date)
            queries &= Q(renewal_sent=False)
            queries &= Q(status__in=[DcvPermit.DCV_PERMIT_STATUS_CURRENT,])
        else:
            queries &= Q(expiry_date__lte=expiry_notification_date)
            queries &= Q(renewal_sent=False)
            queries &= Q(status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,])
            if number_of_days_code == CODE_DAYS_FOR_RENEWAL_AUP:
                queries &= ~Q(current_proposal__vessel_ownership=None)
                queries &= Q(current_proposal__vessel_ownership__end_date=None)

        approvals = approval_class.objects.filter(queries).order_by('issue_date')[:max_renewal_notices]
        for a in approvals:
            try:
                if not approval_class == DcvPermit:
                    approval = Approval.objects.get(id=a.id)
                    approval.generate_renewal_doc()
                    logger.info(f'Renewal document has been generated for the approval: [{approval}]')
                else:
                    approval = DcvPermit.objects.get(id=a.id)
                send_approval_renewal_email_notification(approval)
                approval.renewal_sent = True
                approval.save()

                approval.log_user_action(ApprovalUserAction.ACTION_RENEWAL_NOTICE_SENT_FOR_APPROVAL.format(approval),)
                logger.info(ApprovalUserAction.ACTION_RENEWAL_NOTICE_SENT_FOR_APPROVAL.format(approval))
                updates.append(approval.lodgement_number)
            except Exception as e:
                err_msg = 'Error sending renewal notice for Approval {} - Error {}'.format(a.lodgement_number, str(e))
                logger.error(err_msg)
                errors.append(err_msg)

    def handle(self, *args, **options):
        updates, errors = [], []

        max_renewal_notices = int(MAX_RENEWAL_NOTICES_PER_RUN)

        self.perform_per_type(CODE_DAYS_FOR_RENEWAL_WLA, WaitingListAllocation, updates, errors, max_renewal_notices)
        self.perform_per_type(CODE_DAYS_FOR_RENEWAL_AAP, AnnualAdmissionPermit, updates, errors, max_renewal_notices)
        self.perform_per_type(CODE_DAYS_FOR_RENEWAL_AUP, AuthorisedUserPermit, updates, errors, max_renewal_notices)
        self.perform_per_type(CODE_DAYS_FOR_RENEWAL_ML, MooringLicence, updates, errors, max_renewal_notices)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        msg = construct_email_message(cmd_name, errors, updates)
        logger.info(msg)
        cron_email.info(msg)
