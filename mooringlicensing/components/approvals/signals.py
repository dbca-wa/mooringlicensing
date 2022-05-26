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
        if sticker_saved.status == Sticker.STICKER_STATUS_CURRENT and \
                sticker_saved.proposal_initiated and \
                sticker_saved.proposal_initiated.processing_status == Proposal.PROCESSING_STATUS_PRINTING_STICKER:
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
                # sticker_saved.proposal_initiated.customer_status = Proposal.CUSTOMER_STATUS_APPROVED
                sticker_saved.proposal_initiated.save()

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

