import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q
from mooringlicensing.components.approvals.models import Sticker, ApprovalHistory
from mooringlicensing.components.proposals.models import Proposal

logger = logging.getLogger('mooringlicensing')


class StickerListener(object):

    @staticmethod
    @receiver(post_save, sender=Sticker)
    def _post_save(sender, instance, **kwargs):
        sticker_saved = instance
        if sticker_saved.status == Sticker.STICKER_STATUS_CURRENT:
            if sticker_saved.proposal_initiated and sticker_saved.proposal_initiated.processing_status == Proposal.PROCESSING_STATUS_PRINTING_STICKER:
                stickers_being_printed = Sticker.objects.filter(
                    proposal_initiated=sticker_saved.proposal_initiated,
                    status__in=[
                        Sticker.STICKER_STATUS_READY,
                        Sticker.STICKER_STATUS_NOT_READY_YET,
                        Sticker.STICKER_STATUS_AWAITING_PRINTING,
                        Sticker.STICKER_STATUS_TO_BE_RETURNED,
                    ])
                if not stickers_being_printed:
                    # When a sticker gets 'current' status and there are no stickers with being-printed statuses, update related proposal.status
                    sticker_saved.proposal_initiated.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                    sticker_saved.proposal_initiated.save()
        elif sticker_saved.status in [Sticker.STICKER_STATUS_LOST, Sticker.STICKER_STATUS_RETURNED,]:
            stickers_to_be_returned = sticker_saved.approval.stickers.filter(status=Sticker.STICKER_STATUS_TO_BE_RETURNED)
            proposals_initiated = []

            if stickers_to_be_returned:
                # There is still a sticker to be returned
                # Make sure current proposal with 'sticker_to_be_returned'. However, it should be already with 'sticker_to_be_returned' status set at the final approval.
                sticker_saved.approval.current_proposal.processing_status = Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED
                sticker_saved.approval.current_proposal.save()
            else:
                # There are no stickers to be returned
                stickers_not_ready_yet = sticker_saved.approval.stickers.filter(status=Sticker.STICKER_STATUS_NOT_READY_YET)
                for sticker in stickers_not_ready_yet:
                    # change 'Not ready yet' stickers to 'Ready' so that it is picked up for exporting.
                    sticker.status = Sticker.STICKER_STATUS_READY
                    sticker.save()  # This could make infinite loop
                    proposals_initiated.append(sticker.proposal_initiated)
                    proposals_initiated = list(set(proposals_initiated))

                stickers_being_printed = sticker_saved.approval.stickers.filter(
                    status__in=[
                        Sticker.STICKER_STATUS_READY,
                        Sticker.STICKER_STATUS_AWAITING_PRINTING, ]
                )

                # Update current proposal's status if needed
                if stickers_being_printed:
                    # There is a sticker being printed
                    if sticker_saved.approval.current_proposal.processing_status in [Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED,]:
                        sticker_saved.approval.current_proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                        sticker_saved.approval.current_proposal.save()
                else:
                    # There are not stickers to be printed
                    if sticker_saved.approval.current_proposal.processing_status in [Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED,]:
                        sticker_saved.approval.current_proposal.processing_status = Proposal.PROCESSING_STATUS_APPROVED
                        sticker_saved.approval.current_proposal.save()

                # Update initiated proposal's status if needed.  initiated proposal may not be the current proposal now.
                for proposal in proposals_initiated:
                    if proposal.processing_status == Proposal.PROCESSING_STATUS_STICKER_TO_BE_RETURNED:
                        stickers_to_be_returned = Sticker.objects.filter(status=Sticker.STICKER_STATUS_TO_BE_RETURNED, proposal_initiated=proposal)
                        if not stickers_to_be_returned.count() and stickers_being_printed:
                            # If proposal is in 'Sticker to be Returned' status and there are no stickers with 'To be returned' status,
                            # this proposal should get the status 'Printing Sticker'
                            proposal.processing_status = Proposal.PROCESSING_STATUS_PRINTING_STICKER
                            proposal.save()

        # Update the latest approval history for the approval this sticker is for
        latest_approval_history = ApprovalHistory.objects.filter(approval=sticker_saved.approval, end_date__isnull=True).order_by('-start_date')
        if latest_approval_history:
            latest_approval_history = latest_approval_history.first()
            # There is an active approval_history for the approval this sticker is for.
            if sticker_saved in latest_approval_history.stickers.all():
                # This sticker is already included in the approval history.  Do nothing
                pass
            else:
                # Approval history object doesn't include this sticker.  We have to think about if this sticker is to be included or not.
                if sticker_saved.status in [Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING,]:
                    # Remove all the stickers with 'Expired' status from this approval history just in case there is.
                    expired_stickers = latest_approval_history.stickers.filter(status=Sticker.EXPOSED_STATUS)
                    for expired_sticker in expired_stickers:
                        latest_approval_history.stickers.remove(expired_sticker)
                    # Add this sticker to the history
                    latest_approval_history.stickers.add(sticker_saved)
                elif sticker_saved.status in [Sticker.STICKER_STATUS_EXPIRED,]:
                    if latest_approval_history.stickers.filter(~Q(status=Sticker.STICKER_STATUS_EXPIRED)):
                        # There is at lease one sticker with the status other than 'Expired'
                        # We don't want to add Expired sticker to such an approval history
                        pass
                    else:
                        latest_approval_history.stickers.add(sticker_saved)
        else:
            # Somehow there is no approval history object
            logger.warning('Active ApprovalHistory object for the sticker: {} not found'.format(sticker_saved))

