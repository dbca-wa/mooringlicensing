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


import sys
import csv

MODELS = [
    'MooringLicenceApplication',
    'Mooring',
    'MooringBay',
]

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
