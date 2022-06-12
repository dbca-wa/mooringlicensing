from mooringlicensing.components.proposals.models import (
    Proposal,
    Vessel,
    Owner,
    VesselOwnership,
    VesselDetails,
    MooringLicenceApplication,
    ProposalUserAction,
    Mooring,
    MooringBay,
)
from mooringlicensing.components.approvals.models import Approval, ApprovalHistory, MooringLicence, VesselOwnershipOnApproval
from mooringlicensing.components.organisations.models import Organisation
from ledger.accounts.models import Organisation as ledger_org

import sys
import csv
import pandas as pd

MODELS = [
    'MooringLicenceApplication',
    'Mooring',
    'MooringBay',
]

PROPOSAL_FIELDS = [
    'id',
    #'proposal_type__code',
    #'assessor_data',
    #'comment_data',
    #'proposed_issuance_approval',
    'customer_status',
    'lodgement_number',
    #'lodgement_sequence',
    'lodgement_date',
    'processing_status',
    #'prev_processing_status',
    #'proposed_decline_status',
    'title',
    'approval_level',
    #'approval_comment',
    'migrated',
    'rego_no',
    'vessel_id',
    'vessel_type',
    'vessel_name',
    'vessel_length',
    'vessel_draft',
    'vessel_beam',
    'vessel_weight',
    'berth_mooring',
    'dot_name',
    'percentage',
    'individual_owner',
    'company_ownership_percentage',
    'company_ownership_name',
    #'insurance_choice',
    #'silent_elector',
    'mooring_authorisation_preference',
    'bay_preferences_numbered',
    #'site_licensee_email',
    #'endorser_reminder_sent',
    #'date_invited',
    #'invitee_reminder_sent',
    #'temporary_document_collection_id',
    #'keep_existing_mooring',
    #'keep_existing_vessel',
    #'auto_approve',
    #'null_vessel_on_create',
    'proposal',
    #'uuid',
]

ORGANISATION_FIELDS = [
    #'org_applicant__'
    'org_applicant__organisation__id',
    #'org_applicant__name',
    'org_applicant__organisation__abn',
    'org_applicant__organisation__identification',
    'org_applicant__organisation__email',
    'org_applicant__organisation__trading_name',
]

ORGANISATION_POSTAL_ADDRESS_FIELDS = [
#   #'org_applicant__postal_address__'
#   #'org_applicant__billing_address__'
    'org_applicant__organisation__postal_address__id',
    'org_applicant__organisation__postal_address__line1',
    'org_applicant__organisation__postal_address__line2',
    'org_applicant__organisation__postal_address__line3',
    'org_applicant__organisation__postal_address__locality',
    'org_applicant__organisation__postal_address__state',
    'org_applicant__organisation__postal_address__country',
    'org_applicant__organisation__postal_address__postcode',
    #'org_applicant__postal_address__search_text',
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
    'approval__migrated',
    'approval__submitter__email',
    'approval__org_applicant__organisation__name',

#    'approval__proxy_applicant__',
#    'replaced_by',
#    'renewal_sent',
#    'original_issue_date',
#    'surrender_details',
#    'suspension_details',
#    'extracted_fields',
#    'cancellation_details',
#    'extend_details',
#    'cancellation_date',
#    'set_to_cancel',
#    'set_to_suspend',
#    'set_to_surrender',
#    'renewal_count',
#    'vessel_nomination_reminder_sent',
#    'reissued',
#    'export_to_mooring_booking',
#    'licence_document__',
#    'authorised_user_summary_document__',
#    'cover_letter_document__',
#    'current_proposal__',
#    'renewal_document__',

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

VESSEL_COMPANY_OWNER_FIELDS = [
    'vessel_details__vessel__blocking_owner__company_ownership__company__name',
    #'vessel_details__vessel__blocking_owner__company_ownership__company__percentage',

#    'company_ownership__'
#    'vessel_details__vessel__blocking_owner__start_date',
#    'vessel_details__vessel__blocking_owner__end_date',
#    'vessel_details__vessel__blocking_owner__created',
#    'vessel_details__vessel__blocking_owner__updated',
#    'vessel_details__vessel__blocking_owner__exported',
]

VESSEL_PREFERRED_BAY_FIELDS = [
    'preferred_bay__name',
]

VESSEL_MOORING_FIELDS = [
    'mooring__name',
]

FEESEASON_FIELDS = [
    'fee_season__name',
]

#        'mooring__'
#        'allocated_mooring__'
#        'waiting_list_allocation__'
#        'fee_season__'

#        'proxy_applicant__'
#        'assigned_officer__'
#        'assigned_approver__'
#        'previous_application__'
#        'approval_level_document__'


def write_csv3():
    """
        from mooringlicensing.utils.mooring_licence_migrate_write_csv import get_fields, write_csv3

    """
    fields = PROPOSAL_FIELDS
    fields += ORGANISATION_FIELDS
    fields += ORGANISATION_POSTAL_ADDRESS_FIELDS
    fields += SUBMITTER_POSTAL_ADDRESS_FIELDS
    fields += SUBMITTER_RESIDENTIAL_ADDRESS_FIELDS
    fields += APPROVAL_FIELDS
    fields += VESSEL_DETAILS_FIELDS
    fields += VESSEL_OWNER_FIELDS
    fields += VESSEL_COMPANY_OWNER_FIELDS
    fields += VESSEL_PREFERRED_BAY_FIELDS
    fields += VESSEL_MOORING_FIELDS
    fields += FEESEASON_FIELDS

    mla_qs = MooringLicenceApplication.objects.filter()[:10].values_list(*fields)
    #data = [fields].append(list(mla_qs))
    #import ipdb; ipdb.set_trace()
    print(fields)
    #return fields, mla_qs

#    with open("mla.csv", "w") as f:
#            writer = csv.writer(f)
#            #writer.writerows(fields)
#            writer.writerows([fields])
#            writer.writerows(mla_qs)
#    import ipdb; ipdb.set_trace()

    df = pd.DataFrame(mla_qs, columns=fields)
    df['lodgement_date'] = df['lodgement_date'].dt.tz_localize(None) # remove timezone for excel output
    df.to_excel('mla.xlsx', index=0)
    return df


def write_csv(filename):
    model_fields = []
    model_hdrs = []
    import ipdb; ipdb.set_trace()
    for model in MODELS:
        model_fields += [x.name for x in getattr(sys.modules[__name__], model)._meta.concrete_fields]
        model_hdrs += [x.name + f' ({model})' for x in getattr(sys.modules[__name__], model)._meta.concrete_fields]
        #model_fields += ['']
        #model_hdrs += ['']

        model_fields_list = list(MooringLicenceApplication.objects.values_list(*model_fields))

        with open(filename, 'w', newline='') as myfile:
            for _list in model_fields_list:
                wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
                wr.writerow(_list)


from rest_framework.renderers import JSONRenderer
from mooringlicensing.components.proposals.serializers import VesselOwnershipSerializer, InternalProposalSerializer, MooringLicenceApplicationSerializer
import json

def serialize(model, serializer):
    """
        serialize('VesselOwnership', 'VesselOwnershipSerializer')
    """
    #qs = VesselOwnership.objects.all()
    #serializer = VesselOwnershipSerializer(qs, many=True)
    qs = getattr(sys.modules[__name__], model).objects.all()[:2]
    #serializer = getattr(sys.modules[__name__], serializer)(qs, many=True)
    serializer = getattr(sys.modules[__name__], serializer)(qs, many=True)
    #serializer.data
    renderer = JSONRenderer()
    rendered = renderer.render(serializer.data)
    rendered = rendered.decode('utf-8')
    #rendered

    return json.loads(rendered)

def get_fields(model):
    fk=[]
    #for field in MooringLicenceApplication._meta.concrete_fields:
    for field in model._meta.concrete_fields:
        if field.get_internal_type() == 'ForeignKey':
            #print(f'{field.name}__')
            fk.append(f'\'{field.name}__\'',)
        else:
            print(f'\'{field.name}\',')

#    fk_fields = get_fields(ledger_org)
#    for field in fk_fields:
#        print(f'org_applicant__{field}')



    for field in fk:
        print(field)


def write_csv2():
    fields = PROPOSAL_FIELDS
    mla_qs = MooringLicenceApplication.objects.filter()[:1]
#    for mla in mla_qs:
#        if mla.org_applicant:
#            fields += ORGANISATION_FIELDS
#            if mla.org_applicant and mla.org_applicant.organisation.postal_address:
#                fields += ORGANISATION_POSTAL_ADDRESS_FIELDS
#        if mla.submitter:
#            fields += SUBMITTER_FIELDS
#            if mla.submitter and mla.submitter.postal_address:
#                fields += SUBMITTER_POSTAL_ADDRESS_FIELDS
#            if mla.submitter and mla.submitter.residential_address:
#                fields += SUBMITTER_RESIDENTIAL_ADDRESS_FIELDS


    fields += ORGANISATION_FIELDS
    fields += ORGANISATION_POSTAL_ADDRESS_FIELDS
    fields += SUBMITTER_POSTAL_ADDRESS_FIELDS
    fields += SUBMITTER_RESIDENTIAL_ADDRESS_FIELDS
    mla = MooringLicenceApplication.objects.filter()[:1].values_list(*fields)
        #mla = .values_list(*fields)
    print(mla)


