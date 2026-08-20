
from django.core.management.base import BaseCommand

from mooringlicensing.components.proposals.models import Proposal
from mooringlicensing.management.commands.utils import update_fee_item_application_fee_record

from mooringlicensing.components.payments_ml.models import (
    FeeItemApplicationFee
)

class Command(BaseCommand):
    help = 'Fix Fee Item Application Fee records for Paid Proposals that are missing Vessel Details'

    def handle(self, *args, **options):

        all_missing_vessels =  FeeItemApplicationFee.objects.filter(
            vessel_details=None
        ).exclude(
            amount_paid=0 #if nothing has been paid then there is no problem, we only care if potential deductions are affected
        ).exclude(
            application_fee__proposal__rego_no=None #can't have vessel details without a vessel
        ).filter(
            application_fee__proposal__processing_status__in=[Proposal.PROCESSING_STATUS_APPROVED,Proposal.PROCESSING_STATUS_PRINTING_STICKER] #some records are only updated with vessel details once the resulting approval is created
        )

        #Some fee records will never be assigned vessel details because they are not the final transaction RE that vessel - such as when amendments are requested for an application
        #So we filter out records missing vessel details when another record for that proposal and vessel has it covered
        not_missing_vessels_proposals = list(FeeItemApplicationFee.objects.exclude(vessel_details=None).values_list('application_fee__proposal_id',flat=True))
        proposal_ids = all_missing_vessels.exclude(application_fee__proposal_id__in=not_missing_vessels_proposals).values_list('application_fee__proposal_id',flat=True)

        proposals = Proposal.objects.filter(id__in=proposal_ids)

        for proposal in proposals:
            if proposal.vessel_details:
                update_fee_item_application_fee_record(proposal,proposal.vessel_details)