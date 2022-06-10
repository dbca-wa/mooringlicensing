import os
import subprocess
import json
import csv
import datetime
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from oscar.apps.address.models import Country
from ledger.accounts.models import EmailUser, Address
from mooringlicensing.components.proposals.models import (
    Proposal,
    Vessel,
    Owner,
    VesselOwnership,
    VesselDetails,
    AnnualAdmissionApplication,
    ProposalUserAction,
)
from mooringlicensing.components.approvals.models import Approval, ApprovalHistory, AnnualAdmissionPermit


class AnnualAdmissionMigration(object):
    '''
        from mooringlicensing.utils.annual_admission_migrate import AnnualAdmissionMigration
        AnnualAdmissionMigration(test=False)
    '''

    def __init__(self, filename='mooringlicensing/utils/tests/AA/annual_admissions_booking_report_20210928.csv', test=False):
        """
        NOTE:
            filename='mooringlicensing/utils/tests/AA/annual_admissions_booking_report_20210928.csv' comes from Moorings RIA system (??)
            (https://mooring-ria-internal.dbca.wa.gov.au/dashboard/bookings/annual-admissions/)
        """
        self.filename = filename
        self.test = test

        self.migrate()

    def migrate(self):

        expiry_date = datetime.date(2022,11,30)
        start_date = datetime.date(2021,8,31)

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
        idx = -1
        with transaction.atomic():
            with open(self.filename) as csvfile:
                reader = csv.reader(csvfile, delimiter=str(','))
                header = next(reader) # skip header
                for row in reader:
                    if not row[0].startswith('#'):
                        idx += 1

                        ID = row[0]
                        firstname = row[1].strip()
                        lastname = row[2].strip()
                        email = row[3].lower().strip()
                        mobile_no = row[4].strip()
                        phone_no = row[5].strip()
                        vessel_name = row[6].strip()
                        rego_no = row[7].strip()
                        length = row[8].strip()
                        sticker_no = row[9].strip()
                        year = row[10].strip()
                        status = row[11].strip()
                        booking_period = row[12].strip()
                        address1 = row[13].strip()
                        address2 = row[14].strip()
                        suburb = row[15].strip()
                        postcode = row[16].strip()
                        state = row[17].strip()
                        country = row[18].strip()

                        if status != 'expired':
                            # ignore everything, except 'expired' records
                            continue
                        elif idx % 50 == 0:
                            print(f"{idx} {status}")

                        if self.test:
                            continue

                        try:
                            #import ipdb; ipdb.set_trace()

                            vessel_type = 'other'
                            vessel_weight = Decimal( 0.0 )
                            vessel_draft = Decimal( 0.0 )
                            percentage = None # force user to set at renewal time

                            address = None
                            try:
                                user = EmailUser.objects.get(email=email)
                            except:
                                user = EmailUser.objects.create(email=email, first_name=firstname, last_name=lastname, mobile_number=mobile_no, phone_number=phone_no)

                                country = Country.objects.get(printable_name='Australia')
                                address, address_created = Address.objects.get_or_create(line1=address1, line2=address2, line3=suburb, postcode=postcode, state=state, country=country, user=user)

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
                            except ObjectDoesNotExist:
                                vessel_details = VesselDetails.objects.create(
                                vessel_type=vessel_type,
                                vessel=vessel,
                                vessel_name=vessel_name,
                                vessel_length=length,
                                vessel_draft=vessel_draft,
                                vessel_weight= vessel_weight,
                                berth_mooring='home'
                            )

                            proposal=AnnualAdmissionApplication.objects.create(
                                proposal_type_id=1, # new application
                                submitter=user,
                                migrated=True,
                                vessel_details=vessel_details,
                                vessel_ownership=vessel_ownership,
                                rego_no=rego_no,
                                vessel_type=vessel_type,
                                vessel_name=vessel_name,
                                vessel_length=length,
                                vessel_draft=vessel_draft,
                                vessel_weight=vessel_weight,
                                berth_mooring='home',
                                percentage=percentage,
                                individual_owner=True,
                                processing_status='approved',
                                customer_status='approved',
                                proposed_issuance_approval={
                                    "start_date": start_date.strftime('%d/%m/%Y'),
                                    "expiry_date": expiry_date.strftime('%d/%m/%Y'),
                                    "details": None,
                                    "cc_email": None,
                                },
                            )

                            ua=ProposalUserAction.objects.create(
                                proposal=proposal,
                                who=user,
                                what='Annual Admission - Migrated Application',
                            )

                            #approval = WaitingListAllocation.objects.create(
                            approval = AnnualAdmissionPermit.objects.create(
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
                            #proposal.allocated_mooring.mooring_licence = approval
                            #proposal.allocated_mooring.save()

                            approval_history = ApprovalHistory.objects.create(
                                reason='new',
                                approval=approval,
                                vessel_ownership = vessel_ownership,
                                proposal = proposal,
                                #start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d %H:%M:%S').astimezone(datetime.timezone.utc)
                                start_date = start_date,
                            )

                            added.append(proposal.id)

                            if address:
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

                        except Exception as e:
                            errors.append(e)
                            #import ipdb; ipdb.set_trace()
                            #raise Exception(str(e))
                            print(f'{e}')
                            continue

        print(f'Address.objects.get(id__in={address_list}).delete()')
        print(f'EmailUser.objects.get(id__in={user_list}).delete()')
        print(f'Vessel.objects.get(id__in={vessel_list}).delete()')
        print(f'Owner.objects.get(id__in={owner_list}).delete()')
        print(f'VesselOwnership.objects.get(id__in={ownership_list}).delete()')
        print(f'VesselDetails.objects.get(id__in={details_list}).delete()')
        print(f'ProposalUserAction.objects.get(id__in={user_action_list}).delete()')
        print(f'WaitingListAllocation.objects.get(id__in={approval_list}).delete()')
        print(f'ApprovalHistory.objects.get(id__in={approval_history_list}).delete()')
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


