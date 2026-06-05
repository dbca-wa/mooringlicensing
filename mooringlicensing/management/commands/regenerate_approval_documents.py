from django.core.management.base import BaseCommand
from mooringlicensing.components.approvals.models import Approval, MooringLicence, Mooring, Sticker
from mooringlicensing.components.proposals.models import Proposal
from mooringlicensing.components.proposals.email import (
    send_au_summary_to_ml_holder
)
from mooringlicensing.components.approvals.email import send_aup_revoked_due_to_mooring_swap_email

import logging

logger = logging.getLogger('cron_tasks')
cron_email = logging.getLogger('cron_email')


class Command(BaseCommand):
    help = 'Runs document generation functions for any approvals where regenerate documents flag is True.'

    def handle(self, *args, **options):
        logger.info("Running regenerate_approval_documents")
        #check approvals that need document regen (requires bool field)
        regen_approvals = Approval.objects.filter(regenerate_documents=True)

        #regen docs
        for approval in regen_approvals:

            approval.refresh_from_db() #in case the cron job run crosses over so we avoid doing this more than once (not critical but preferable)
            if approval.regenerate_documents:
                approval.generate_doc()
                approval.refresh_from_db()
                if approval.child_obj and approval.child_obj.code == 'ml':
                    #ML regen authorised user summary as as approval doc
                    approval.child_obj.generate_au_summary_doc()
                    approval.refresh_from_db()

                #create history record
                approval.write_approval_history("Documents Regenerated")

                #create action log
                approval.log_user_action("Document Regenerated")

                approval.regenerate_documents = False
                approval.save()

            #Check if email notifications need to sent out after the document has been regenerated
            if approval.regenerate_document_email_notification and "func" in approval.regenerate_document_email_notification:

                if (
                    approval.regenerate_document_email_notification["func"] == "send_au_summary_to_ml_holder" and
                    "params" in approval.regenerate_document_email_notification
                ):
                    params = approval.regenerate_document_email_notification["params"]
                    try:
                        #param [0] mooring_licence_id (mooring_licence obj)
                        mooring_license = MooringLicence.objects.get(id=int(params[0]))
                        #param [1] proposal_id (approval obj)
                        proposal = Proposal.objects.get(id=int(params[1]))

                        send_au_summary_to_ml_holder(mooring_license, proposal)
                    except Exception as e:
                        logger.error(f"regenerate_document_email_notification failed for {approval.lodgement_number}: {e}")
                
                if (
                    approval.regenerate_document_email_notification["func"] == "send_aup_revoked_due_to_mooring_swap_email" and
                    "params" in approval.regenerate_document_email_notification
                ):
                    params = approval.regenerate_document_email_notification["params"]
                    try:
                        #param [0] approval_id (approval child_obj)
                        notification_approval = Approval.objects.get(id=int(params[0])).child_obj
                        #param [1] mooring_id (mooring obj)
                        mooring = Mooring.objects.get(id=int(params[1]))
                        #param [2] sticker_id (sticker obj in [])
                        sticker = Sticker.objects.get(id=int(params[2]))
                        send_aup_revoked_due_to_mooring_swap_email(notification_approval, mooring, [sticker,])
                    except Exception as e:
                        logger.error(f"regenerate_document_email_notification failed for {approval.lodgement_number}: {e}")
                    
                approval.regenerate_document_email_notification = None
                approval.save()