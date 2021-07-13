from mooringlicensing.settings import HTTP_HOST_FOR_TEST
from mooringlicensing.tests.test_setup import APITestSetup
from mooringlicensing.components.proposals.models import MooringBay, Proposal
from datetime import datetime
import pytz
from ledger.settings_base import TIME_ZONE


class ManageVesselTests(APITestSetup):
    def test_manage_vessels(self):
        print("test_manage_vessels")
        create_vessel_data = {
                'vessel': {
                    'new_vessel': True, 
                    'rego_no': '20210503_1', 
                    'vessel_details': {
                        'read_only': False, 
                        'vessel_name': '20210503_1', 
                        'berth_mooring': 'home', 
                        'vessel_length': '23', 
                        'vessel_overall_length': '34',
                        'vessel_weight': '45', 
                        'vessel_draft': '56', 
                        'vessel_type': 'tender'
                        }, 
                    'vessel_ownership': {
                        'registered_owner': 'current_user', 
                        'individual_owner': True, 
                        'percentage': '35'
                        }
                    }
                }

        self.client.login(email=self.customer1, password='pass')
        self.client.enforce_csrf_checks=True
        create_response = self.client.post(
            '/api/vessel/',
            #self.create_proposal_data,
            create_vessel_data,
            format='json',
            HTTP_HOST=HTTP_HOST_FOR_TEST,
        )

        self.assertEqual(create_response.status_code, 200)
        vessel_id = create_response.data.get('id')
        self.assertTrue(vessel_id > 0)

        ##########################
        manage_vessel_data = {
                'vessel': {
                    #'id': 73,
                    'id': vessel_id,
                    'rego_no': 'gtukfgh', 
                    'vessel_details': {
                        #'blocking_proposal': 91, 
                        'blocking_proposal': None, 
                        'vessel_type': 'cabin_cruiser', 
                        #'vessel': 73, 
                        'vessel': vessel_id, 
                        'vessel_name': 'ererer', 
                        'vessel_overall_length': '78.00', 
                        'vessel_length': '45.00', 
                        'vessel_draft': '67.00', 
                        'vessel_beam': '0.00', 
                        'vessel_weight': '56.00', 
                        'berth_mooring': 'fghx', 
                        'created': '2021-04-19T02:17:53.516348Z', 
                        'updated': '2021-05-03T04:24:20.959310Z', 
                        'status': 'draft', 
                        'exported': False, 
                        'read_only': True
                    }, 
                    'vessel_ownership': {
                        'percentage': 100, # updates value in create_vessel_data
                        'individual_owner': True
                    }
                }
            }

        self.client.login(email=self.customer2, password='pass')
        self.client.enforce_csrf_checks=True
        manage_vessel_response = self.client.put(
            '/api/vessel/{}'.format(vessel_id),
            #self.create_proposal_data,
            manage_vessel_data,
            format='json',
            HTTP_HOST=HTTP_HOST_FOR_TEST,
        )

        self.assertEqual(manage_vessel_response.status_code, 301)
        #vessel_id = manage_vessel_response.data.get('id')
        #self.assertTrue(vessel_id > 0)

        # get vessel
        url = 'http://localhost:8071/api/vessel/{}.json'.format(vessel_id)
        get_response = self.client.get(url, HTTP_HOST=HTTP_HOST_FOR_TEST,)

        self.assertEqual(get_response.status_code, 200)
        #return vessel_id, manage_vessel_response.data.get('vessel_details').get('id')

