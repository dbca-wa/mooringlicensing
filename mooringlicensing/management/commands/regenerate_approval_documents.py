from django.core.management.base import BaseCommand
from mooringlicensing.components.approvals.models import Approval

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

            #NOTE: may need to add email notifications for instances where an approval document needs to be sent out - further discussion and design will be required, for now aiming for what we have functionally

