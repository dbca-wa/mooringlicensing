from mooringlicensing.components.proposals.models import (
    Proposal,
    Vessel,
    Owner,
    VesselOwnership,
    VesselDetails,
    WaitingListApplication,
    ProposalUserAction,
    Mooring,
    MooringBay,
)
from mooringlicensing.components.approvals.models import Approval, ApprovalHistory

import pandas as pd


PROPOSAL_FIELDS = [
    #proposal_type_id
    #submitter
    'lodgement_number',
    'lodgement_date',
    'migrated',
    #vessel_details
    #vessel_ownership
    'rego_no',
    'vessel_type',
    'vessel_name',
    'vessel_length',
    'vessel_draft',
    #vessel_beam='',
    'vessel_weight',
    'berth_mooring',
    #preferred_bay
    'percentage',
    'individual_owner',
    'processing_status',
    'customer_status',
    #allocated_mooring
    #'date_invited',
    #'dot_name',
]


SUBMITTER_FIELDS = [
#   #'submitter__'
    'submitter__id',
    'submitter__email',
    'submitter__first_name',
    'submitter__last_name',
    'submitter__dob',
    'submitter__phone_number',
    'submitter__mobile_number',
    'submitter__fax_number',
]

SUBMITTER_RESIDENTIAL_ADDRESS_FIELDS = [
    'submitter__residential_address__line1',
    'submitter__residential_address__line2',
    'submitter__residential_address__line3',
    'submitter__residential_address__locality',
    'submitter__residential_address__state',
    'submitter__residential_address__postcode',
    'submitter__residential_address__country',
]

SUBMITTER_POSTAL_ADDRESS_FIELDS = [
    'submitter__postal_address__line1',
    'submitter__postal_address__line2',
    'submitter__postal_address__line3',
    'submitter__postal_address__locality',
    'submitter__postal_address__state',
    'submitter__postal_address__postcode',
    'submitter__postal_address__country',
]


APPROVAL_FIELDS = [
    'approval__id',
    'approval__lodgement_number',
    'approval__status',
    'approval__internal_status',
    'approval__issue_date',
    'approval__start_date',
    'approval__expiry_date',
    'approval__wla_queue_date',
    'approval__wla_order',
]

VESSEL_DETAILS_FIELDS = [
#        'vessel_details__'
    'vessel_details__id',
    'vessel_details__vessel_type',
    'vessel_details__vessel_name',
    'vessel_details__vessel_length',
    'vessel_details__vessel_draft',
    'vessel_details__vessel_beam',
    'vessel_details__vessel_weight',
    'vessel_details__berth_mooring',
    #'vessel_details__created',
    #'vessel_details__updated',
    'vessel_details__exported',
    'vessel_details__vessel__rego_no',
    #'vessel_details__vessel__blocking_owner__'
]

VESSEL_OWNER_FIELDS = [
    'vessel_details__vessel__blocking_owner__id',
    'vessel_details__vessel__blocking_owner__percentage',
    'vessel_details__vessel__blocking_owner__dot_name',
    'vessel_details__vessel__blocking_owner__owner__emailuser__email',
]

VESSEL_PREFERRED_BAY_FIELDS = [
    'preferred_bay__name',
]

VESSEL_MOORING_FIELDS = [
    'mooring__name',
    #'allocated_mooring__name',
]

def write():
    """
        from mooringlicensing.utils.excel_export.wla_to_excel import write
        df = write()
    """
    fields = PROPOSAL_FIELDS
    fields += SUBMITTER_FIELDS
    fields += SUBMITTER_POSTAL_ADDRESS_FIELDS
    fields += SUBMITTER_RESIDENTIAL_ADDRESS_FIELDS
    fields += APPROVAL_FIELDS
    fields += VESSEL_DETAILS_FIELDS
    fields += VESSEL_OWNER_FIELDS
    fields += VESSEL_PREFERRED_BAY_FIELDS
    fields += VESSEL_MOORING_FIELDS
    #fields += FEESEASON_FIELDS

    #import ipdb; ipdb.set_trace()
    wla_qs = WaitingListApplication.objects.filter(migrated=True).values_list(*fields)
    #print(fields)

    df = pd.DataFrame(wla_qs, columns=fields)
    if not df['lodgement_date'].empty:
        df['lodgement_date'] = df['lodgement_date'].dt.tz_localize(None) # remove timezone for excel output
    df.to_excel('wla.xlsx', index=0)
    return df


def get_fields(model):
    """
        from mooringlicensing.utils.excel_export.wla_to_excel import get_fields
        get_fields(MooringLicence)
    """
    fk=[]
    #for field in MooringLicenceApplication._meta.concrete_fields:
    for field in model._meta.concrete_fields:
        if field.get_internal_type() == 'ForeignKey':
            #print(f'{field.name}__')
            fk.append(f'\'{field.name}__\'',)
        else:
            print(f'\'{field.name}\',')

    for field in fk:
        print(field)

