import os
import subprocess
import json
import datetime
from decimal import Decimal
from django.db import transaction, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from oscar.apps.address.models import Country
from ledger.accounts.models import EmailUser, Address
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


class MooringLicenceMigration(object):
    '''
        from mooringlicensing.utils.mooring_licence_migrate import MooringLicenceMigration
        MooringLicenceMigration(test=False)
    '''

    def __init__(self, path='/var/www/mooringlicensing/mooringlicensing/utils/lotus_notes', test=False):
        self.path = path
        self.test = test

        #self.waitlist = self.read_dict('Waitlist___Bay.json')
        self.auth_users = self.read_dict('Licencees___Auth_User.json')
        self.mooring_no = self.read_dict('Licencees___Mooring_No.json')
        self.surname = self.read_dict('Licencees___Surname.json')
        #self.vessel = self.read_dict('Vessel___HIN___Current.json')
        self.vessel = self.read_dict('Vessel___Details_All.json')
        self.owner = self.read_dict('Owner_Details.json')
        self.allocated = self.read_dict('Admin___Application___Pers_No.json')

        self.migrate()

    def read_dict(self, fname):
        filename = self.path + os.sep + fname if not self.path.endswith(os.sep) else self.path + fname
        with open(filename) as f:
            f_json = json.load(f)

            # make list unique
            _list = []
            for i in f_json:
                if i not in _list:
                    _list.append(i)

        #import ipdb; ipdb.set_trace()
        return _list

    def search(self, key, value, records):
        for record in records:
            if value == record.get(key):
                return record
        return None

    def migrate(self):

        #submitter = EmailUser.objects.get(email='jawaid.mushtaq@dbca.wa.gov.au')
        expiry_date = datetime.date(2022,11,30)
        start_date = datetime.date(2021,8,31)
        date_applied = '2021-08-31'

        address_list = []
        user_list = []
        vessel_list = []
        owner_list = []
        ownership_list = []
        details_list = []
        proposal_list = []
        user_action_list = []
        approval_list = []
        approval_history_list = []

        added = []
        errors = []
        count_no_mooring = 0
        with transaction.atomic():
            for idx, record in enumerate(self.mooring_no, 1):
            #for idx, record in enumerate(self.mooring_no[257:], 1):
                #if idx==258:
                #    import ipdb; ipdb.set_trace()
                try:
                    #import ipdb; ipdb.set_trace()
                    pers_no = record.get('PersNo')
                    address = record.get('_1')
                    mooring = record.get('MooringNo')
                    mooring_bay = record.get('_7')
                    username = record.get('UserName').lower()
                    rego_no = record.get('_4').split('-')[0].strip()
                    vessel_name = record.get('_4').split('-')[1].strip()

                    owner_record = self.search('PersNoL', pers_no, self.owner)
                    if owner_record:
                        vessel_name = owner_record['VesName']
                        rego_no = owner_record['VesRego']
                        licence_pc = owner_record['LicPC']

                    surname_record = self.search('PersNo', pers_no, self.surname)
                    #email = GrepSearch(pers_no, path=self.path).search('PersNo', 'EMail')
                    #email_record.get('EMail').lower().strip()
                    #H1N = GrepSearch(pers_no, path=self.path).search('PersNo', 'H1N1')
                    email = surname_record['EMail'].split(',')[0].strip().lower()
                    if email=='{ronrouwenhorst@bigpond.com} ;arthur@technitemp.com':
                        errors.append(email)
                        continue

                    HIN = surname_record['HIN1']

                    vessel_record = self.search('PersNo', pers_no, self.vessel)
                    if vessel_record:
                        vessel_dot = vessel_record.get('DoTRego1')
                        #email = GrepSearch(pers_no, path=self.path).search('PersNo', 'EMail')
                        vessel_overall_length = Decimal( vessel_record.get('RegLength1') )
                        vessel_draft = Decimal( vessel_record.get('Draft1') )
                    else:
                        vessel_dot = rego_no
                        #vessel_overall_length = Decimal( GrepSearch(pers_no, path=self.path).search('PersNo', 'RegLength1') )
                        try:
                            vessel_overall_length = Decimal( surname_record.get('RegLength1') )
                        except Exception as e:
                            vessel_overall_length = Decimal( 0.0 )
                        vessel_draft = Decimal( 0.0 )

                    vessel_type = 'other'
                    vessel_weight = Decimal( 0.0 )

                    allocated_record = self.search('PersNo', pers_no, self.allocated)
                    try:
                        date_invited = datetime.datetime.strptime(allocated_record.get('DateAllocated'), '%Y-%m-%d').date() 
                    except:
                        date_invited = None

                    #email_record = GrepSearch(pers_no).search('PersNo', 'EMail')
                    phonemobile_record = GrepSearch(pers_no, path=self.path).search('PersNo', 'PhoneMobile')
                    phonehome_record = GrepSearch(pers_no, path=self.path).search('PersNo', 'PhoneHome')

                    mobile_no = phonemobile_record.get('PhoneMobile')
                    firstname = username.split(' ')[-1].title()
                    lastname = ' '.join(username.split(' ')[:-1]).title()

                    try:
                        phone_no = phonehome_record.get('PhoneHome') if phonehome_record else ''
                        #address = address_record.get('_1')
                    except:
                        import ipdb; ipdb.set_trace()

                    #print(f'{idx}, {pers_no}, {username}')
                    #if self.test:
                    #    import ipdb; ipdb.set_trace()
                    #    continue

 
#                    mooring_record = self.search('_1', username, self.moorings)
#                    try:
#                        mooring = mooring_record['MooringNo']
#                        vessel_name = mooring_record['VesName']
#                        rego_no = mooring_record['VesRego']
#                    except:
#                        count_no_mooring += 1
#                        print(f'*************** {idx}, {pers_no}, {username}, {count_no_mooring}')
#                        continue
#                        #vessel_name = record.get('_11').split('-')[1].strip()
#                        #rego_no = record.get('_11').split('-')[0].strip()


                    # see mooringlicensing/utils/tests/mooring_names.txt
                    if Mooring.objects.filter(name=mooring).count()>0:
                        mooring = Mooring.objects.filter(name=mooring)[0]
                    else:
                        #import ipdb; ipdb.set_trace()
                        print(f'Mooring not found: {mooring}')
                        errors.append(dict(idx=idx, record=record))
                        continue

                        #mooring_bay = MooringBay.objects.get(name='Rottnest Island')
                        #mooring_bay = MooringBay.objects.get(name='Thomson Bay')

                    # needed ??
                    #date_applied = record.get('DateApplied')
                    #position_no = int(record.get('BayPosNo'))
                    #trim_no = record.get('TrimNo')
                    percentage = None # force user to set at renewal time


                    items = address.split(',')
                    line1 = items[0].strip()
                    line2 = items[1].strip() if len(items) > 3 else ''
                    line3 = items[2].strip() if len(items) > 4 else ''
                    state = items[-2].strip()
                    postcode = items[-1].strip()

                    #import ipdb; ipdb.set_trace()
                    print(f'{idx}, {pers_no}, {username}, {state}, {postcode}')
                    if self.test:
                        continue

                    try:
                        user = EmailUser.objects.get(email=email)
                    except:
                        user = EmailUser.objects.create(email=email, first_name=firstname, last_name=lastname, mobile_number=mobile_no, phone_number=phone_no)

                    country = Country.objects.get(printable_name='Australia')
                    address, address_created = Address.objects.get_or_create(line1=line1, line2=line2, line3=line3, postcode=postcode, state=state, country=country, user=user)
                    user.residential_address = address
                    user.postal_address = address
                    user.save()

                    try:
                        vessel = Vessel.objects.get(rego_no=rego_no)
                    except ObjectDoesNotExist:
                        vessel = Vessel.objects.create(rego_no=rego_no)


                    try:
                        owner = Owner.objects.get(emailuser=user)
                    except ObjectDoesNotExist:
                        owner = Owner.objects.create(emailuser=user)


                    try:
                        vessel_ownership = VesselOwnership.objects.get(owner=owner, vessel=vessel)
                    except ObjectDoesNotExist:
                        vessel_ownership = VesselOwnership.objects.create(owner=owner, vessel=vessel, percentage=percentage)

                    try:
                        vessel_details = VesselDetails.objects.get(vessel=vessel)
                    except MultipleObjectsReturned:
                        vessel_details = VesselDetails.objects.filter(vessel=vessel)[0]
                    except ObjectDoesNotExist:
                        vessel_details = VesselDetails.objects.create(
                        vessel_type=vessel_type,
                        vessel=vessel,
                        vessel_name=vessel_name,
                        vessel_length=vessel_overall_length,
                        vessel_draft=vessel_draft,
                        vessel_weight= vessel_weight,
                        berth_mooring='home'
                    )

                    proposal=MooringLicenceApplication.objects.create(
                        proposal_type_id=1, # new application
                        submitter=user,
                        migrated=True,
                        vessel_details=vessel_details,
                        vessel_ownership=vessel_ownership,
                        rego_no=rego_no,
                        vessel_type=vessel_type,
                        vessel_name=vessel_name,
                        vessel_length=vessel_overall_length,
                        vessel_draft=vessel_draft,
                        #vessel_beam='',
                        vessel_weight=vessel_weight,
                        berth_mooring='home',
                        preferred_bay= mooring.mooring_bay,
                        percentage=percentage,
                        individual_owner=True,
                        #proposed_issuance_approval={},
                        processing_status='approved',
                        customer_status='approved',
                        allocated_mooring=mooring,
                        proposed_issuance_approval={
                            "start_date": start_date.strftime('%d/%m/%Y'),
                            "expiry_date": expiry_date.strftime('%d/%m/%Y'),
                            "details": None,
                            "cc_email": None,
                            "mooring_id": mooring.id,
                            "ria_mooring_name": mooring.name,
                            "mooring_bay_id": mooring.mooring_bay.id,
                            "vessel_ownership": [{
                                    "dot_name": vessel_dot
                                }],
                            "mooring_on_approval": []
                        },
                        date_invited=date_invited,
                        dot_name=vessel_dot,
                    )
#>         "proposed_issuance_approval": {
#>             "details": "dd",
#>             "cc_email": null,
#>             "mooring_id": 127,
#>             "mooring_bay_id": 7,
#>             "ria_mooring_name": "CB005",
#>             "vessel_ownership": [],
#>             "mooring_on_approval": []
#>         },
#
#>         "berth_mooring": "home",
#>         "dot_name": "abc",
#>         "insurance_choice": "over_ten",
#>         "preferred_bay": null,
#>         "silent_elector": null,
#>         "mooring_authorisation_preference": "ria",
#>         "bay_preferences_numbered": "[\"1\", \"2\", \"3\", \"4\", \"5\", \"6\", \"7\"]",

                    ua=ProposalUserAction.objects.create(
                        proposal=proposal,
                        who=user,
                        what='Mooring Licence - Migrated Application',
                    )

                    #approval = WaitingListAllocation.objects.create(
                    approval = MooringLicence.objects.create(
                        status='current',
                        #internal_status=None,
                        current_proposal=proposal,
                        issue_date = datetime.datetime.now(datetime.timezone.utc),
                        #start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d %H:%M:%S').date(),
                        start_date = start_date,
                        expiry_date = expiry_date,
                        submitter=user,
                        migrated=True,
                        export_to_mooring_booking=True,
                    )
                    #print(f'wla_order: {position_no}')

                    proposal.approval = approval
                    proposal.save()
                    proposal.allocated_mooring.mooring_licence = approval
                    proposal.allocated_mooring.save()

                    vooa = VesselOwnershipOnApproval.objects.create(
                        approval=approval,
                        vessel_ownership=vessel_ownership,
                    )
#                    moa = MooringOnApproval.objects.create(
#                        approval=approval,
#                        mooring=mooring,
#                        sticker=None,
#                        site_licensee=True, # ???
#                        end_date=expiry_date
#                    )

                    try:
                        start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d %H:%M:%S').astimezone(datetime.timezone.utc)
                    except:
                        start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d').astimezone(datetime.timezone.utc)

                    approval_history = ApprovalHistory.objects.create(
                        reason='new',
                        approval=approval,
                        vessel_ownership = vessel_ownership,
                        proposal = proposal,
                        #start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d %H:%M:%S').astimezone(datetime.timezone.utc)
                        start_date = start_date,
                    )

                    added.append(proposal.id)

                    address_list.append(address.id)
                    user_list.append(user.id)
                    vessel_list.append(vessel.id)
                    owner_list.append(owner.id)
                    ownership_list.append(vessel_ownership.id)
                    details_list.append(vessel_details.id)
                    proposal_list.append(proposal.proposal.id)
                    user_action_list.append(ua.id)
                    approval_list.append(approval.id)
                    approval_history_list.append(approval_history.id)

#                except IntegrityError as e:
#                    errors.append(repr(e))
#                    continue
                except Exception as e:
                    #errors.append(str(e))
                    import ipdb; ipdb.set_trace()
                    raise Exception(str(e))

#        print(f'Address.objects.get(id__in={address_list}).delete()')
#        print(f'EmailUser.objects.get(id__in={user_list}).delete()')
#        print(f'Vessel.objects.get(id__in={vessel_list}).delete()')
#        print(f'Owner.objects.get(id__in={owner_list}).delete()')
#        print(f'VesselOwnership.objects.get(id__in={ownership_list}).delete()')
#        print(f'VesselDetails.objects.get(id__in={details_list}).delete()')
#        print(f'ProposalUserAction.objects.get(id__in={user_action_list}).delete()')
#        print(f'WaitingListAllocation.objects.get(id__in={approval_list}).delete()')
#        print(f'ApprovalHistory.objects.get(id__in={approval_history_list}).delete()')
        print(f'errors: {errors}')

def clear_record():
    Address.objects.last().delete()
    EmailUser.objects.last().delete()
    Vessel.objects.last().delete()
    Owner.objects.last().delete()
    VesselOwnership.objects.last().delete()
    VesselDetails.objects.last().delete()
    WaitingListApplication.objects.last().delete()
    ProposalUserAction.objects.last().delete()
    WaitingListAllocation.objects.last().delete()
    ApprovalHistory.objects.last().delete()

class GrepSearch(object):
    '''
    from mooringlicensing.utils.waiting_list_migrate import WaitingListMigration, GrepSearch

    GrepSearch('123').search('key', '_1')     --> Search for string key='123' in all files. The result record/dict must also have key '_1'
    '''

    def __init__(self, search_str1, path='mooringlicensing/utils/lotus_notes'):
        self.path = path
        self.search_str1 = search_str1
        #self.search()

    def get_files(self, search_str):
        ''' Read all files in directory '''
        r=subprocess.check_output(['grep', '-rl', search_str, self.path])
        files = [i for i in r.decode('UTF-8').split('\n') if i.endswith(".json") ]
        return files

    def search(self, key1, key2):
        ''' Iteratively search for key:value pair in grep'd files '''

        def find(key, value, records):
            for record in records:
                if value == record.get(key):
                    return record
            return None

        #import ipdb; ipdb.set_trace()
        # Get all files that contains string 'self.search_str1'
        #_files = self.get_files(self.search_str1)
        files=[
            self.path + os.sep + 'Vessel___Rego___Current.json',
            self.path + os.sep + 'PeopleNo.json',
            self.path + os.sep + 'People___Trim_File.json',
            self.path + os.sep + 'Admin___EContacts___5_Licencee.json',
            self.path + os.sep + 'Admin___Labels___Postal.json',
        ]

        for fname in files:
            with open(fname) as f:
                f_json = json.load(f)
                #import ipdb; ipdb.set_trace()
                # check the files (json) also has the key2
                if key2 in f_json[0]:
                    # find record in json that contains key1:search_str1
                    record = find(key1, self.search_str1, f_json)
                    if record:
                        #import ipdb; ipdb.set_trace()
                        if key2=='_1' and len(record['_1'].split(',')) <= 1:
                            continue
                        #print(f'fname: {fname}, key2: {key2}')
                        return record


