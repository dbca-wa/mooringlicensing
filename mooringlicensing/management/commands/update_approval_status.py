from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from mooringlicensing.components.approvals.models import (
    Approval,
    ApprovalUserAction, WaitingListAllocation,
    MooringLicence, AuthorisedUserPermit
)
from mooringlicensing.components.proposals.models import ProposalUserAction
import datetime
from mooringlicensing.components.approvals.email import (
    send_approval_cancel_email_notification,
    send_approval_suspend_email_notification,
    send_approval_surrender_email_notification
)

import logging

from mooringlicensing.management.commands.utils import construct_email_message

logger = logging.getLogger('cron_tasks')
cron_email = logging.getLogger('cron_email')


class Command(BaseCommand):
    help = 'Change the status of Approvals to Expired / Surrender/ Cancelled/ Suspended.'

    def handle(self, *args, **options):
        errors = []
        updates = []
        today = timezone.localtime(timezone.now()).date()
        logger.info('Running command {}'.format(__name__))

        # Expiry
        queries = Q()
        queries &= (Q(status=Approval.APPROVAL_STATUS_CURRENT))
        queries &= Q(expiry_date__lt=today)

        approvals = Approval.objects.filter(queries)
        for approval in approvals:
            try:
                approval.expire_approval()
                logger.info('Updated Approval {} status to {}'.format(approval.id, approval.status))
                updates.append(approval.lodgement_number)
            except Exception as e:
                err_msg = 'Error updating Approval {} status'.format(approval.lodgement_number)
                logger.error('{}\n{}'.format(err_msg, str(e)))
                errors.append(err_msg)

        # Current --> suspend, cancel, surrender
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
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_SUSPEND_APPROVAL.format(a.id), None)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_SUSPEND_APPROVAL.format(proposal.lodgement_number), None)
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

                        if hasattr(a, 'child_obj') and (
                            type(a.child_obj) == WaitingListAllocation or
                            type(a.child_obj) == AuthorisedUserPermit or
                            type(a.child_obj) == MooringLicence                            
                        ):
                            a.child_obj.processes_after_cancel()

                        send_approval_cancel_email_notification(a)

                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_CANCEL_APPROVAL.format(a.id), None)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_CANCEL_APPROVAL.format(proposal.lodgement_number), None)
                        logger.info('Updated Approval {} status to {}'.format(a.id, a.status))
                        updates.append(dict(cancelled=a.lodgement_number))
                    except Exception as e:
                        err_msg = 'Error cancelling Approval {} status'.format(a.lodgement_number)
                        logger.error('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)

            if a.surrender_details and a.set_to_surrender:
                surrender_date = datetime.datetime.strptime(a.surrender_details['surrender_date'], '%d/%m/%Y')
                surrender_date = surrender_date.date()
                stickers_to_be_returned = a._process_stickers()          
                if surrender_date <= today:
                    try:
                        a.status = Approval.APPROVAL_STATUS_SURRENDERED
                        a.set_to_surrender = False
                        a.save()

                        if hasattr(a, 'child_obj') and (
                            type(a.child_obj) == WaitingListAllocation
                        ):
                            a.child_obj.processes_after_surrender()
                        
                        if hasattr(a, 'child_obj') and (
                            type(a.child_obj) == AuthorisedUserPermit or
                            type(a.child_obj) == MooringLicence                            
                        ):
                            a.child_obj.processes_after_cancel()

                        send_approval_surrender_email_notification(a, stickers_to_be_returned=stickers_to_be_returned)

                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_SURRENDER_APPROVAL.format(a.id), None)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_SURRENDER_APPROVAL.format(proposal.lodgement_number), None)
                        logger.info('Updated Approval {} status to {}'.format(a.id, a.status))
                        updates.append(dict(surrendered=a.lodgement_number))
                    except Exception as e:
                        err_msg = 'Error surrendering Approval {} status'.format(a.lodgement_number)
                        logger.error('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)

        # Suspended --> current, cancel, surrender
        for a in Approval.objects.filter(status=Approval.APPROVAL_STATUS_SUSPENDED):
            if a.suspension_details and a.suspension_details['to_date']:               
                to_date = datetime.datetime.strptime(a.suspension_details['to_date'], '%d/%m/%Y')
                to_date = to_date.date()
                if to_date <= today < a.expiry_date:
                    try:
                        a.status = Approval.APPROVAL_STATUS_CURRENT
                        a.save()

                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_REINSTATE_APPROVAL.format(a.id), None)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_REINSTATE_APPROVAL.format(proposal.lodgement_number), None)
                        logger.info('Updated Approval {} status to {}'.format(a.id, a.status))
                        updates.append(dict(current=a.lodgement_number))
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

                        if hasattr(a, 'child_obj') and (
                            type(a.child_obj) == WaitingListAllocation or
                            type(a.child_obj) == AuthorisedUserPermit or
                            type(a.child_obj) == MooringLicence                            
                        ):
                            a.child_obj.processes_after_cancel()

                        send_approval_cancel_email_notification(a)

                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_CANCEL_APPROVAL.format(a.id), None)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_CANCEL_APPROVAL.format(proposal.lodgement_number), None)
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

                        if hasattr(a, 'child_obj') and (
                            type(a.child_obj) == WaitingListAllocation
                        ):
                            a.child_obj.processes_after_surrender()
                        
                        if hasattr(a, 'child_obj') and (
                            type(a.child_obj) == AuthorisedUserPermit or
                            type(a.child_obj) == MooringLicence                            
                        ):
                            a.child_obj.processes_after_cancel()

                        send_approval_surrender_email_notification(a)
                        proposal = a.current_proposal
                        ApprovalUserAction.log_action(a, ApprovalUserAction.ACTION_SURRENDER_APPROVAL.format(a.id), None)
                        ProposalUserAction.log_action(proposal, ProposalUserAction.ACTION_SURRENDER_APPROVAL.format(proposal.lodgement_number), None)
                        logger.info('Updated Approval {} status to {}'.format(a.id, a.status))
                        updates.append(dict(surrendered=a.lodgement_number))
                    except Exception as e:
                        err_msg = 'Error surrendering Approval {} status'.format(a.lodgement_number)
                        logger.error('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        msg = construct_email_message(cmd_name, errors, updates)
        logger.info(msg)
        cron_email.info(msg)
