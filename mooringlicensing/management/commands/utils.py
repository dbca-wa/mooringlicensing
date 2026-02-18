from django.db.models import F, CharField, Q, Value
from django.db.models.functions import Cast, Concat

from ledger_api_client.settings_base import TIME_ZONE

from mooringlicensing.components.main.models import GlobalSettings

from mooringlicensing.components.approvals.models import (
    Approval, Sticker, MooringOnApproval
)

from mooringlicensing.components.proposals.models import (
    Proposal, VesselOwnership
)

from mooringlicensing.components.payments_ml.models import (
    FeeConstructor, FeeItemApplicationFee
)

import pytz
import datetime

def get_stickers_missing_vessel(stickers):

    stickers = stickers.filter(status__in=[Sticker.STICKER_STATUS_CURRENT,Sticker.STICKER_STATUS_AWAITING_PRINTING,Sticker.STICKER_STATUS_NOT_READY_YET,Sticker.STICKER_STATUS_READY])
    stickers_missing_vessel = list(stickers.filter(vessel_ownership=None).values_list('number',flat=True))

    return ("Stickers that are missing a vessel ownership record (and by extension, vessel registration):", stickers_missing_vessel)


def get_proposals_with_fee_records_missing_vessel_details(proposals):
    """
    Get proposal payment records that are missing vessel detail records

    These can affect future deductions
    """

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
    
    bad_proposal_numbers = proposals.filter(id__in=proposal_ids).values_list('lodgement_number',flat=True)

    return ("Proposals with payment records that are missing vessel details (which may affected future deductions):", bad_proposal_numbers)

def get_invalid_stickers_still_current(stickers):
    
    stickers = stickers.filter(status=Sticker.STICKER_STATUS_CURRENT)

    #identify current stickers that:
    #have been replaced by other stickers
    #are no longer attached to a valid approval
    current_stickers_with_non_current_approval = stickers.exclude(approval__status__in=Approval.APPROVED_STATUSES)

    #are attached to a no longer valid vessel? 
    current_stickers_with_sold_vessel = stickers.exclude(vessel_ownership__end_date=None)

    #For non-AUPs, there should only be one sticker per vessel per approval 
    aup_stickers = stickers.filter(approval__lodgement_number__startswith="AUP")
    non_aup_stickers = stickers.exclude(approval__lodgement_number__startswith="AUP")

    latest_distinct_stickers = list(non_aup_stickers.order_by("approval_id","vessel_ownership__vessel__rego_no","-proposal_initiated__id","-number").distinct("approval_id","vessel_ownership__vessel__rego_no").values_list('id',flat=True))
    replaced_stickers = non_aup_stickers.exclude(id__in=latest_distinct_stickers)

    #For AUPs check if they are on an MOA
    moa_sticker_ids = list(MooringOnApproval.objects.filter(sticker_id__in=list(aup_stickers.values_list('id',flat=True))).values_list('sticker_id',flat=True))
    aup_stickers_without_moa = aup_stickers.exclude(id__in=moa_sticker_ids)

    bad_sticker_numbers = list(set(
        list(current_stickers_with_non_current_approval.annotate(reason=Concat(F("number"),Value(" Reason: Approval Non-Current"))).values_list("reason",flat=True))+
        list(current_stickers_with_sold_vessel.annotate(reason=Concat(F("number"),Value(" Reason: Vessel Sold"))).values_list("reason",flat=True))+
        list(replaced_stickers.annotate(reason=Concat(F("number"),Value(" Reason: Replaced or Duplicate"))).values_list("reason",flat=True))+
        list(aup_stickers_without_moa.annotate(reason=Concat(F("number"),Value(" Reason: Replaced or Incorrect MOA"))).values_list("reason",flat=True))
    ))

    return ("Stickers with invalid current status (due to being replaced, duplicated, or otherwise invalidated). Some numbers may appear in \"Stickers that are not properly assigned to Mooring on Approval records\":", bad_sticker_numbers)

def get_approvals_due_for_renewal_without_notice(approvals):
    #get approvals with latest applied season in the last season

    #get current season and prior season
    today = datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()
    fee_seasons = []
    current_season = None
    fee_constructors = FeeConstructor.get_fee_constructor_by_date(today)
    for fc in fee_constructors:
        try:
            obj = {'start_date': fc.fee_season.start_date, 'end_date': fc.fee_season.end_date}
            if obj not in fee_seasons:
                fee_seasons.append(obj)
        except:
            continue

    #NOTE: as of writing there is typically only one current fee season at a time
    #If that is ever no longer the case, this function will need to be refactored
    if fee_seasons:
        current_season = fee_seasons[0]
    else:
        return ("There is no current fee season set up.",[])

    try:
        prior_date = current_season['start_date'] - datetime.timedelta(days=1)
    except:
        return ("Current fee season improperly set up.",[])

    #filter out approvals with renewal sent
    approvals = approvals.filter(renewal_sent=False)

    #filter out any approvals where the proposal was lodged after the last season
    approvals = approvals.exclude(current_proposal__lodgement_date__gt=prior_date)

    #filter out any approvals where the proposal was not accepted
    approvals = approvals.filter(
        current_proposal__processing_status__in=[
            Proposal.PROCESSING_STATUS_APPROVED,
            Proposal.PROCESSING_STATUS_PRINTING_STICKER
        ])

    #filter out non-current approvals
    approvals = approvals.filter(
        status__in=Approval.APPROVED_STATUSES,
    )

    #check remaining approvals - if from last season without a renewal sent it needs to be reported
    unrenewed_approvals = []
    for approval in approvals:
        season = approval.latest_applied_season
        if season and season.end_date <= prior_date:
            unrenewed_approvals.append(approval.lodgement_number)

    return ("Approvals from the prior season that have not been sent renewal notices:", unrenewed_approvals)

def get_stickers_not_on_MOAs(stickers):

    stickers = stickers.filter(approval__lodgement_number__startswith="AUP",status__in=Sticker.STATUSES_AS_CURRENT)
    moas = MooringOnApproval.objects.filter(sticker_id__in=list(stickers.values_list('id', flat=True)))
    moa_stickers = list(moas.values_list('sticker_id',flat=True))

    missing_moa = list(stickers.exclude(id__in=moa_stickers).values_list('number',flat=True))

    return ("Stickers that are not properly assigned to Mooring on Approval records:", missing_moa)

def get_incorrect_sticker_seasons(stickers):
    """Get stickers that have a fee season that does not match the approval they are on (or is missing a fee season)"""

    stickers = stickers.filter(status__in=Sticker.STATUSES_AS_CURRENT)

    missing_fee_season = list(stickers.filter(fee_season=None).values_list('id',flat=True))
    mismatched_fee_season = []

    for i in stickers.exclude(fee_season=None):
        #NOTE originally compared ids here, but that does not account for when fee seasons application types mismatch due to annual admission payments
        #comparing names should be adequate so long as naming conventions are adhered to
        latest_applied_season = i.approval.latest_applied_season
        if latest_applied_season and i.fee_season.name != latest_applied_season.name:
            mismatched_fee_season.append(i.id)     

    bad_fee_seasons = list(stickers.filter(id__in=mismatched_fee_season+missing_fee_season).values_list('number',flat=True))

    return ("Stickers that have a fee season that does not match their approval or are missing a fee season:", bad_fee_seasons)

def convert_and_check_late_date_str(date_str, current_time):
    """attempts to convert date_str from "%d/%m/%Y" (including quotes) format and then checks if date has elapsed"""
    try:
        date_value = datetime.datetime.strptime(date_str,'"%d/%m/%Y"')
    except Exception as e:
        print(e)
        return False
    
    return current_time > date_value

def get_late_resuming_approvals(approvals):
    current_time = datetime.datetime.now()
    current_approvals_to_suspend = approvals.annotate(
        suspension_date_str=Cast('suspension_details__to_date', output_field=CharField())
    ).filter(status__in=[Approval.APPROVAL_STATUS_CURRENT],set_to_suspend=True)

    current_approvals_late_to_suspension = list(map(lambda i: i.lodgement_number,list(filter(lambda i: convert_and_check_late_date_str(i.suspension_date_str,current_time),current_approvals_to_suspend))))

    return ("Approvals that have a suspension end date and are late to being resumed:", current_approvals_late_to_suspension)

def get_late_cancelled_approvals(approvals):
    current_time = datetime.datetime.now()
    current_approvals = list(approvals.filter(status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED],cancellation_date__lt=current_time).values_list('lodgement_number',flat=True))
    return ("Approvals that have a cancellation date and are late to being cancelled:", current_approvals)

def get_late_suspended_approvals(approvals):
    current_time = datetime.datetime.now()
    current_approvals_to_suspend = approvals.annotate(
        suspension_date_str=Cast('suspension_details__from_date', output_field=CharField())
    ).filter(status__in=[Approval.APPROVAL_STATUS_CURRENT],set_to_suspend=True)

    current_approvals_late_to_suspension = list(map(lambda i: i.lodgement_number,list(filter(lambda i: convert_and_check_late_date_str(i.suspension_date_str,current_time),current_approvals_to_suspend))))

    return ("Approvals that have a suspension date and are late to being suspended:", current_approvals_late_to_suspension)

def get_late_surrendered_approvals(approvals):
    current_time = datetime.datetime.now()
    current_approvals_to_surrender = approvals.annotate(
        surrender_date_str=Cast('surrender_details__surrender_date', output_field=CharField())
    ).filter(status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED],set_to_surrender=True)

    current_approvals_late_to_surrender = list(map(lambda i: i.lodgement_number,list(filter(lambda i: convert_and_check_late_date_str(i.surrender_date_str,current_time),current_approvals_to_surrender))))

    return ("Approvals that have a surrender date and are late to being surrendered:", current_approvals_late_to_surrender)

def get_late_expired_approvals(approvals):
    current_time = datetime.datetime.now()
    current_approvals = list(approvals.filter(status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED],expiry_date__lt=current_time).values_list('lodgement_number',flat=True))
    return ("Approvals that have an expiry date and are late to being expired:", current_approvals)

def get_unaccounted_sold_vessel_ownerships(proposals):
    """Get vessel ownerships for vessels that have been sold but have no end date, excluding records created after the latest sold vessel ownership record"""
    proposals_with_vo = proposals.exclude(vessel_ownership=None)
    proposal_vo_ids = list(proposals_with_vo.values_list("vessel_ownership_id", flat=True))
    vessel_ownerships = VesselOwnership.objects.filter(id__in=proposal_vo_ids)

    sold_vessel_ownerships = vessel_ownerships.exclude(end_date=None)
    unsold_vessel_ownerships = vessel_ownerships.filter(end_date=None)
    rego_nos = []
    for svo in sold_vessel_ownerships:
        if svo.vessel:
            if unsold_vessel_ownerships.filter(created__lt=svo.created,owner=svo.owner,vessel__rego_no=svo.vessel.rego_no).exists():
                rego_nos.append(svo.vessel.rego_no)
    return ("Vessels that have been marked as sold have unaccounted for vessel ownership records and possibly related records that have not been marked as sold:", rego_nos)

#NOTE: with changes to sales handling this particular report is no longer required but may be useful for debugging
def check_duplicate_vessel_ownerships_among_proposals(proposals):
    """reporting function for checking for multiple vessel ownerships among proposals (pertaining to different current approvals) that have not ended (should only be one)"""
    proposals_with_vo = proposals.exclude(vessel_ownership=None).filter(approval__current_proposal_id=F('id')).filter(approval__status__in=Approval.APPROVED_STATUSES)
    proposal_vo_ids = list(proposals_with_vo.values_list("vessel_ownership_id", flat=True))
    vessel_ownerships = VesselOwnership.objects.filter(id__in=proposal_vo_ids, end_date=None)

    accounted_for = []
    multiples = []
    #records here are in-date and assigned to the provided proposals - so if multiple have the same rego no something is wrong
    for vo in vessel_ownerships:
        if vo.vessel:
            if vo.vessel.rego_no in accounted_for and not vo in multiples:
                multiples.append(vo.vessel.rego_no)
            else:
                accounted_for.append(vo.vessel.rego_no)

    multiples_with_proposals = []
    for rego_no in multiples:
        multiples_with_proposals.append(f'{rego_no} ({",".join(list(proposals_with_vo.filter(vessel_ownership__vessel__rego_no=rego_no).values_list("lodgement_number",flat=True)))})')

    return ("Vessels with multiple ongoing vessel ownerships on multiple proposal records that pertain to different current approvals) (only should be one at a time):", multiples_with_proposals)

def check_proposal_stuck_at_printing(proposals):
    """reporting function for checking proposals stuck in printing sticker despite no sticker records awaiting printing or export"""
    printing = proposals.filter(processing_status=Proposal.PROCESSING_STATUS_PRINTING_STICKER)
    stickers = Sticker.objects.filter(proposal_initiated_id__in=list(printing.values_list('id',flat=True)))
    non_printing_stickers = stickers.exclude(status__in=[Sticker.STICKER_STATUS_AWAITING_PRINTING, Sticker.STICKER_STATUS_READY, Sticker.STICKER_STATUS_NOT_READY_YET])
    non_printing_proposal_ids = list(non_printing_stickers.values_list('proposal_initiated__id', flat=True))
    #account for when a non-printing sticker has been replaced by another before the print has completed
    replacement_stickers = stickers = Sticker.objects.filter(proposal_initiated_id__in=non_printing_proposal_ids).filter(status__in=[Sticker.STICKER_STATUS_AWAITING_PRINTING, Sticker.STICKER_STATUS_READY, Sticker.STICKER_STATUS_NOT_READY_YET])
    replacement_stickers_proposal_ids = list(replacement_stickers.values_list('proposal_initiated__id', flat=True))

    non_printing_stuck = list(printing.filter(id__in=non_printing_proposal_ids).exclude(id__in=replacement_stickers_proposal_ids).values_list('lodgement_number',flat=True))

    return ("Proposals with a Printing Sticker status but with no Sticker records awaiting printing or awaiting export.", non_printing_stuck)

def check_invalid_expired_approval(approvals):
    """reporting function to get all expired approvals that have a later expiry date"""
    current_time = datetime.datetime.now()
    expired_approvals_bad_dates = approvals.filter(status=Approval.APPROVAL_STATUS_EXPIRED, expiry_date__gt=current_time)
    numbers = list(expired_approvals_bad_dates.values_list("lodgement_number",flat=True))
    return ("Approvals with an Expired status but still in date:", numbers)

def ml_meet_vessel_requirement(mooring_licence, boundary_date):
    min_length_setting = GlobalSettings.objects.get(key=GlobalSettings.KEY_MINUMUM_MOORING_VESSEL_LENGTH)
    min_length = float(min_length_setting.value)

    # Return True when mooring_licence has at least one vessel whoose size is more than 6.4m and not sold or sold after the boundary_date
    for proposal in mooring_licence.proposal_set.all():
        if proposal.vessel_details and proposal.vessel_details.vessel and proposal.vessel_details.vessel.latest_vessel_details and proposal.vessel_details.vessel.latest_vessel_details.vessel_applicable_length >= min_length:
            # Vessel meets the length requirements
            if proposal.vessel_ownership.end_date is None or proposal.vessel_ownership.end_date > boundary_date:
                # At least one vessel has not been sold or sold recently
                return True

    # All the vessels have been sold more than X months ago
    return False

def construct_email_message(cmd_name, errors, updates):
    cmd_str = '<div>{} completed.</div>'.format(cmd_name)

    if len(errors) > 0:
        err_str = '<div><strong style="color: red;">Errors: {}</strong></div>'.format(len(errors))
        err_str += '<ul>'
        for error in errors:
            err_str += '<li>{}</li>'.format(error)
        err_str += '</ul>'
    else:
        err_str = '<div><strong style="color: green;">Errors: 0</strong></div>'

    updates_str = '<div>IDs updated: {}</div>'.format(updates)

    msg = '<div style="margin: 0 0 1em 0;">' + cmd_str + '<div style="margin:0 0 0 1em;">' + err_str + updates_str + '</div></div>'
    return msg
