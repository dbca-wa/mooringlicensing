from django.core.management.base import BaseCommand
from django.utils import timezone

from mooringlicensing import settings
from mooringlicensing.components.approvals.models import Approval, ApprovalUserAction
from mooringlicensing.components.proposals.models import ProposalUserAction
from ledger.accounts.models import EmailUser
import datetime
from mooringlicensing.components.approvals.email import (
    send_approval_cancel_email_notification,
    send_approval_suspend_email_notification,
    send_approval_surrender_email_notification
)

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Change the status of Approvals to Surrender/ Cancelled/ Suspended.'

    def handle(self, *args, **options):
        try:
            user = EmailUser.objects.get(email=settings.CRON_EMAIL)
        except:
            user = EmailUser.objects.create(email=settings.CRON_EMAIL, password = '')

        errors = []
        updates = []
        today = timezone.localtime(timezone.now()).date()
        logger.info('Running command {}'.format(__name__))

        # For debug
        # params = options.get('params')
        # debug = True if params.get('debug', 'f').lower() in ['true', 't', 'yes', 'y'] else False
        # approval_id = int(params.get('update_approval_status_id', 0))
        # approval = Approval.objects.filter(id=approval_id)

        for a in Approval.objects.filter(status=Approval.APPROVAL_STATUS_CURRENT):
            if a.suspension_details and a.set_to_suspend:
                from_date = datetime.datetime.strptime(a.suspension_details['from_date'], '%d/%m/%Y')
                from_date = from_date.date()                
                if from_date <= today:
                    try:
                        a.status = Approval.APPROVAL_STATUS_SUSPENDED
                        a.set_to_suspend = False
                        a.save()
                        send_approval_suspend_email_notification(a)

                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_SUSPEND_APPROVAL.format(a.id), user)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_SUSPEND_APPROVAL.format(proposal.lodgement_number), user)
                        logger.info('Updated Approval {} status to {}'.format(a.id, a.status))
                        updates.append(dict(suspended=a.lodgement_number))
                    except Exception as e:
                        err_msg = 'Error suspending Approval {} status'.format(a.lodgement_number)
                        logger.error('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)

            if a.cancellation_date and a.set_to_cancel:                              
                if a.cancellation_date <= today:
                    try:
                        a.status = Approval.APPROVAL_STATUS_CANCELLED
                        a.set_to_cancel = False
                        a.save()
                        send_approval_cancel_email_notification(a)

                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_CANCEL_APPROVAL.format(a.id), user)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_CANCEL_APPROVAL.format(proposal.lodgement_number), user)
                        logger.info('Updated Approval {} status to {}'.format(a.id, a.status))
                        updates.append(dict(cancelled=a.lodgement_number))
                    except Exception as e:
                        err_msg = 'Error cancelling Approval {} status'.format(a.lodgement_number)
                        logger.error('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)

            if a.surrender_details and a.set_to_surrender:
                surrender_date = datetime.datetime.strptime(a.surrender_details['surrender_date'], '%d/%m/%Y')
                surrender_date = surrender_date.date()                
                if surrender_date <= today:
                    try:
                        a.status = Approval.APPROVAL_STATUS_SURRENDERED
                        a.set_to_surrender = False
                        a.save()
                        send_approval_surrender_email_notification(a)

                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_SURRENDER_APPROVAL.format(a.id), user)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_SURRENDER_APPROVAL.format(proposal.lodgement_number), user)
                        logger.info('Updated Approval {} status to {}'.format(a.id, a.status))
                        updates.append(dict(surrendered=a.lodgement_number))
                    except Exception as e:
                        err_msg = 'Error surrendering Approval {} status'.format(a.lodgement_number)
                        logger.error('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)

        for a in Approval.objects.filter(status=Approval.APPROVAL_STATUS_SUSPENDED):
            if a.suspension_details and a.suspension_details['to_date']:               
                to_date = datetime.datetime.strptime(a.suspension_details['to_date'], '%d/%m/%Y')
                to_date = to_date.date()
                if to_date <= today < a.expiry_date:
                    try:
                        a.status = Approval.APPROVAL_STATUS_CURRENT
                        a.save()

                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_REINSTATE_APPROVAL.format(a.id), user)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_REINSTATE_APPROVAL.format(proposal.lodgement_number), user)
                        logger.info('Updated Approval {} status to {}'.format(a.id, a.status))
                        updates.append(dict(current=a.lodgement_number))
                    except Exception as e:
                        err_msg = 'Error suspending Approval {} status'.format(a.lodgement_number)
                        logger.error('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)

            if a.cancellation_date and a.set_to_cancel:                              
                if a.cancellation_date <= today:
                    try:
                        a.status = Approval.STATUS_CANCELLED
                        a.set_to_cancel = False
                        a.save()

                        send_approval_cancel_email_notification(a)
                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_CANCEL_APPROVAL.format(a.id), user)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_CANCEL_APPROVAL.format(proposal.lodgement_number), user)
                        logger.info('Updated Approval {} status to {}'.format(a.id,a.status))
                        updates.append(dict(cancelled=a.lodgement_number))
                    except Exception as e:
                        err_msg = 'Error cancelling Approval {} status'.format(a.lodgement_number)
                        logger.error('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)

            if a.surrender_details and a.set_to_surrender:
                surrender_date = datetime.datetime.strptime(a.surrender_details['surrender_date'], '%d/%m/%Y')
                surrender_date = surrender_date.date()                
                if surrender_date <= today:
                    try:
                        a.status = Approval.APPROVAL_STATUS_SURRENDERED
                        a.set_to_surrender = False
                        a.save()

                        send_approval_surrender_email_notification(a)
                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_SURRENDER_APPROVAL.format(a.id), user)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_SURRENDER_APPROVAL.format(proposal.lodgement_number), user)
                        logger.info('Updated Approval {} status to {}'.format(a.id, a.status))
                        updates.append(dict(surrendered=a.lodgement_number))
                    except Exception as e:
                        err_msg = 'Error surrendering Approval {} status'.format(a.lodgement_number)
                        logger.error('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        err_str = '<strong style="color: red;">Errors: {}</strong>'.format(len(errors)) if len(errors)>0 else '<strong style="color: green;">Errors: 0</strong>'
        msg = '<p>{} completed. {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        logger.info(msg)
        print(msg) # will redirect to cron_tasks.log file, by the parent script
