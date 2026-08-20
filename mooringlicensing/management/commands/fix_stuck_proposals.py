
from django.core.management.base import BaseCommand
from mooringlicensing.components.approvals.models import Sticker, Approval
from mooringlicensing.components.proposals.models import Proposal
from mooringlicensing.management.commands.utils import update_missing_vessel_details
from django.db.models import Q

class Command(BaseCommand):
    help = 'Fix proposals stuck in draft or with assessor status when they have already put sticker through to print'

    def handle(self, *args, **options):
        # This script provides mitigation for a bug that we have not yet been able to determine the cause for
        # The bug will keep/revert a proposal's status in/to draft or with assessor after approval processes have complete
        # A proposal that has been completed should either go to printing sticker, sticker to be returned, or to approved

        # If a proposal is stuck with assessor there is a risk that an assessor may not realise the application was already approved and re-approve it causing some issue
        # If a propoal is stuck in draft there is a risk that an applicant may not realise the application was already approved and re-submit it
        # In both cases this can lead to extra payments, communications, and sticker records

        # This script will run periodically every ~5 minutes (configurable via cron) to check for affected proposals
        # The script may not catch all instances of this problem but should allow the overall issue to become more manageable until we can uncover the underlying cause
        # This script will not fix WLAs affected by this bug, however WLAs are overall less affected by this issue as they are designed to handle post-payment resubmits and do not have stickers

        # get all stickers that have an originating proposal with incorrect status (all except printing sticker, sticker to be returned, or approved) unless the approval has been reissued (in which case we only correct if stuck in draft or discarded, we cancel the reissue if that does happen)
        # a reissue could potentially be declined or expire - those are the only circumstance where sticker records may exist for such proposals
        # a reissue should never result in a new invoice so we operate on the assumption that if a proposal is in awaiting payment but has a sticker record - that needs to be fixed

        # we also need to check for and potential restore vessel_ownership and vessel_details on affected records
        # get latest VO for submitted rego_no
        # get appropriate VD record that corresponds with relevant vessel details
        # get FeeItemApplicationFee record tied to proposal (only if invoice is paid)

        stickers_with_stuck_proposals = Sticker.objects.exclude(
            proposal_initiated__processing_status__in=[
                Proposal.PROCESSING_STATUS_APPROVED, 
                Proposal.PROCESSING_STATUS_PRINTING_STICKER,
                Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED,
                Proposal.PROCESSING_STATUS_DECLINED, #in case it was reissued and then declined
                Proposal.PROCESSING_STATUS_EXPIRED, #in case it was reissued and then expired
            ]
        )
        stuck_proposals = Proposal.objects.filter(id__in=list(stickers_with_stuck_proposals.values_list('proposal_initiated__id',flat=True)))
        stuck_proposals = stuck_proposals.exclude((Q(approval__reissued=True)&~Q(processing_status__in=[Proposal.PROCESSING_STATUS_DRAFT, Proposal.PROCESSING_STATUS_DISCARDED]))) #we exclude reissued approvals if the proposal is not in draft or discarded

        #if after filtering out reissued approvals some still remain, reverse the reissue
        if stuck_proposals.filter(approval__reissued=True).exists():
            approvals = Approval.objects.filter(id__in=list(stuck_proposals.filter(approval__reissued=True).values_list("approval_id", flat=True)))
            for approval in approvals:
                approval.reissued = False
                approval.save()
                approval.log_user_action(f"Approval {approval} reissue reversed while fixing proposal stuck in incorrect status. Reissue can be attempted again if needed.")

        for proposal in stuck_proposals:
            # determine the correct status for that proposal (dependent on status of all relevant stickers)
            proposal_stickers = stickers_with_stuck_proposals.filter(proposal_initiated=proposal)
            incorrect_status = proposal.processing_status
            # any proposals stickers in status not_ready_yet -> sticker_to_be_returned
            if proposal_stickers.filter(status=Sticker.STICKER_STATUS_NOT_READY_YET).exists():
                proposal.processing_status = Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED
                proposal.save()
                proposal.log_user_action(f'Proposal: {proposal} status corrected from {incorrect_status} to {proposal.processing_status}')
                update_missing_vessel_details(proposal)
                continue

            # any check approval stickers, any in to_be_returned -> sticker_to_be_returned (unless proposal already approved, though that won't reach here)
            if Sticker.objects.filter(approval=proposal.approval).filter(status=Sticker.STICKER_STATUS_TO_BE_RETURNED):
                proposal.processing_status = Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED
                proposal.save()
                proposal.log_user_action(f'Proposal: {proposal} status corrected from {incorrect_status} to {proposal.processing_status}')
                update_missing_vessel_details(proposal)
                continue

            # any proposal stickers in status ready or awaiting_printing and none above -> printing_sticker
            if proposal_stickers.filter(status=Sticker.STICKER_STATUS_READY).exists() or proposal_stickers.filter(status=Sticker.STICKER_STATUS_AWAITING_PRINTING).exists():
                proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                proposal.save()
                proposal.log_user_action(f'Proposal: {proposal} status corrected from {incorrect_status} to {proposal.processing_status}')
                update_missing_vessel_details(proposal)
                continue

            # all stickers cancelled -> printing_sticker
            if proposal_stickers.count() == proposal_stickers.filter(status=Sticker.STICKER_STATUS_CANCELLED).count():
                proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                proposal.save()
                proposal.log_user_action(f'Proposal: {proposal} status corrected from {incorrect_status} to {proposal.processing_status}')
                update_missing_vessel_details(proposal)
                continue

            # all proposal stickers in status printed, lost, or returned even if some cancelled -> approved (some cancelled stickers may still need to be replaced but this can be fixed)
            proposal.processing_status = Proposal.PROCESSING_STATUS_APPROVED #we default to approved 
            proposal.log_user_action(f'Proposal: {proposal} status corrected from {incorrect_status} to {proposal.processing_status}')
            update_missing_vessel_details(proposal)
            proposal.save()
