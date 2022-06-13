from mooringlicensing.components.proposals.models import (
    Proposal
)
from mooringlicensing.components.approvals.models import DcvPermit, DcvVessel, DcvOrganisation

import pandas as pd


DCV_PERMIT_FIELDS = [
    'id',
    'lodgement_number',
    'lodgement_datetime',
    'start_date',
    'end_date',
    'migrated',
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

DCV_VESSEL_FIELDS = [
    'dcv_vessel__vessel_name',
    'dcv_vessel__rego_no',
]

DCV_ORGANISATION_FIELDS = [
    'dcv_organisation__name',
    'dcv_organisation__abn',
]

FEESEASON_FIELDS = [
    'fee_season__name',
]

def write():
    """
        from mooringlicensing.utils.excel_export.dvcpermits_to_excel import write
        df = write()
    """
    fields = DCV_PERMIT_FIELDS
    fields += SUBMITTER_FIELDS
    fields += SUBMITTER_POSTAL_ADDRESS_FIELDS
    fields += SUBMITTER_RESIDENTIAL_ADDRESS_FIELDS
    fields += DCV_VESSEL_FIELDS
    fields += DCV_ORGANISATION_FIELDS
    fields += FEESEASON_FIELDS

    #import ipdb; ipdb.set_trace()
    dcvp_qs = DcvPermit.objects.filter(migrated=True).values_list(*fields)
    #print(fields)

    df = pd.DataFrame(dcvp_qs, columns=fields)
    if not df['lodgement_datetime'].empty:
        df['lodgement_datetime'] = df['lodgement_datetime'].dt.tz_localize(None) # remove timezone for excel output
    df.to_excel('dcv.xlsx', index=0)
    return df


def get_fields(model):
    """
        from mooringlicensing.utils.excel_export.dvcpermits_to_excel import get_fields
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

