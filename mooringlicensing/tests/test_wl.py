from mooringlicensing.settings import HTTP_HOST_FOR_TEST
from mooringlicensing.tests.test_setup import APITestSetup
from mooringlicensing.components.proposals.models import MooringBay, Proposal, Vessel
from datetime import datetime
import pytz
from ledger.settings_base import TIME_ZONE


class WaitingListTests(APITestSetup):

    def test_create_bare_vessel_add_to_proposal(self):
        create_vessel_data = {
                "vessel": {
                    "new_vessel": True,
                    "rego_no":"20210517_2",
                    "vessel_details": {
                        "vessel_name":"gfhj ijuhiuh",
                        "berth_mooring":"fghx",
                        "vessel_length":"45",
                        "vessel_overall_length":"56",
                        "vessel_weight":"67",
                        "vessel_draft":"78",
                        "vessel_type":"tender"
                        },
                    "vessel_ownership": {
                        "company_ownership": {
                            "company": {
                                "name":"20210517_2"
                                },
                            "percentage":"25"
                            },
                        "individual_owner": False
                        }
                    },
                #"create_vessel": True
                }

        self.client.login(email=self.customer1, password='pass')
        self.client.enforce_csrf_checks=True
        create_response = self.client.post(
            '/api/vessel/',
            create_vessel_data,
            format='json',
            HTTP_HOST=HTTP_HOST_FOR_TEST,
        )

        vessel_id_1 = create_response.data.get('id')
        vessel = Vessel.objects.get(id=vessel_id_1)
        vessel_details_id_1 = vessel.latest_vessel_details.id

        ## Proposal 2 - add vessel from Proposal
        create_response_2 = self.client.post(
            '/api/waitinglistapplication/',
            format='json',
            HTTP_HOST=HTTP_HOST_FOR_TEST,
        )

        self.assertEqual(create_response_2.status_code, 200)
        self.assertTrue(create_response_2.data.get('id') > 0)

        proposal_2_id = create_response_2.data.get('id')
        # get proposal
        url2 = 'http://localhost:8071/api/proposal/{}.json'.format(proposal_2_id)
        get_response_2 = self.client.get(url2, HTTP_HOST=HTTP_HOST_FOR_TEST,)

        self.assertEqual(get_response_2.status_code, 200)
        # save Proposal2
        draft_proposal_2_data = {
                "proposal": {
                    "dot_name": "something",
                    },
                "vessel": {
                    "new_vessel": True,
                    "rego_no":"20210517_2",
                    "vessel_details": {
                        "vessel_name":"gfhj ijuhiuh",
                        "berth_mooring":"fghx",
                        "vessel_length":"45",
                        "vessel_overall_length":"56",
                        "vessel_weight":"67",
                        "vessel_draft":"78",
                        "vessel_type":"tender"
                        },
                    "vessel_ownership": {
                        "company_ownership": {
                            "company": {
                                "name":"20210517_2"
                                },
                            "percentage":"25"
                            },
                        "individual_owner": False
                        }
                    },
                #"create_vessel": True
                }

        draft_response = self.client.post(
                '/api/proposal/{}/draft/'.format(proposal_2_id),
                draft_proposal_2_data, 
                format='json',
                HTTP_HOST=HTTP_HOST_FOR_TEST,
        )
        self.assertEqual(draft_response.status_code, 302)
        

        ## add DoT rego papers
        rego_papers_response = self.client.post(
                '/api/proposal/{}/process_vessel_registration_document/'.format(proposal_2_id),
                self.rego_papers_data, 
                #format='json',
                HTTP_HOST=HTTP_HOST_FOR_TEST,
        )
        self.assertEqual(rego_papers_response.status_code, 200)

        # submit Proposal2
        # submit api endpoint
        submit_proposal_2_data = {
                "proposal": {
                    "silent_elector": False,
                    "preferred_bay_id": MooringBay.objects.last().id,
                    "dot_name": "something",
                    },
                "vessel": {
                    "vessel_details": {
                        "id":128,
                        "vessel_type":"cabin_cruiser",
                        "vessel":116,
                        "vessel_name":"gfhj ijuhiuh",
                        "vessel_overall_length":"45.00",
                        "vessel_length":"34.00",
                        "vessel_draft":"67.00",
                        "vessel_beam":"0.00",
                        "vessel_weight":"56.00",
                        "berth_mooring":"fghx asdffd",
                        "created":"2021-05-17T02:53:14.146946Z",
                        "updated":"2021-05-17T03:12:12.968954Z",
                        "exported": False,
                        },
                    "vessel_ownership": {
                        "percentage": None,
                        "individual_owner": False,
                        "company_ownership": {
                            "id":13,
                            "blocking_proposal":152,
                            "status":"draft",
                            "vessel":116,
                            "company": {
                                "id":11,
                                "name":"20210517_1"
                                },
                            "percentage":25,
                            "start_date":"2021-05-17T02:53:14.157933Z",
                            "end_date": None,
                            "created":"2021-05-17T02:53:14.157953Z",
                            "updated":"2021-05-17T03:12:13.010817Z"
                            }
                        },
                    "rego_no":"20210517_1",
                    "id":116
                    }
                }
        submit_2_response = self.client.post(
                '/api/proposal/{}/submit/'.format(proposal_2_id),
                submit_proposal_2_data, 
                format='json',
                HTTP_HOST=HTTP_HOST_FOR_TEST,
        )
        self.assertEqual(submit_2_response.status_code, 200)

    def test_proposal_wla_vessel_logic(self):
        print("test_proposal_wla_vessel_logic")
        self.client.login(email=self.customer, password='pass')
        self.client.enforce_csrf_checks=True
        create_response = self.client.post(
            '/api/waitinglistapplication/',
            format='json',
            HTTP_HOST=HTTP_HOST_FOR_TEST,
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertTrue(create_response.data.get('id') > 0)

        proposal_id = create_response.data.get('id')
        # get proposal
        url = 'http://localhost:8071/api/proposal/{}.json'.format(proposal_id)
        get_response = self.client.get(url, HTTP_HOST=HTTP_HOST_FOR_TEST,)

        self.assertEqual(get_response.status_code, 200)
        #######################
        draft_proposal_data = {
                "vessel": {
                    "new_vessel": True,
                    "rego_no":"20210517_2",
                    "vessel_details": {
                        "vessel_name":"gfhj ijuhiuh",
                        "berth_mooring":"fghx",
                        "vessel_length":"45",
                        "vessel_overall_length":"56",
                        "vessel_weight":"67",
                        "vessel_draft":"78",
                        "vessel_type":"tender"
                        },
                    "vessel_ownership": {
                        "company_ownership": {
                            "company": {
                                "name":"20210517_2"
                                },
                            "percentage":"25"
                            },
                        "individual_owner": False
                        }
                    },
                #"create_vessel": True
                }

        draft_response = self.client.post(
                '/api/proposal/{}/draft/'.format(proposal_id),
                draft_proposal_data, 
                format='json',
                HTTP_HOST=HTTP_HOST_FOR_TEST,
        )
        self.assertEqual(draft_response.status_code, 302)

        ## add DoT rego papers
        rego_papers_response = self.client.post(
                '/api/proposal/{}/process_vessel_registration_document/'.format(proposal_id),
                self.rego_papers_data, 
                #format='json',
                HTTP_HOST=HTTP_HOST_FOR_TEST,
        )
        self.assertEqual(rego_papers_response.status_code, 200)

        ## add Silent Elector papers
        electoral_roll_doc_response = self.client.post(
                '/api/proposal/{}/process_electoral_roll_document/'.format(proposal_id),
                self.electoral_roll_doc_data, 
                #format='json',
                HTTP_HOST=HTTP_HOST_FOR_TEST,
        )
        self.assertEqual(electoral_roll_doc_response.status_code, 200)

        submit_proposal_data = {
                "proposal": {
                    "silent_elector": False,
                    "preferred_bay_id": MooringBay.objects.last().id,
                    "dot_name": "something",
                    },
                "vessel": {
                    "vessel_details": {
                        "id":128,
                        "vessel_type":"cabin_cruiser",
                        "vessel":116,
                        "vessel_name":"gfhj ijuhiuh",
                        "vessel_overall_length":"45.00",
                        "vessel_length":"34.00",
                        "vessel_draft":"67.00",
                        "vessel_beam":"0.00",
                        "vessel_weight":"56.00",
                        "berth_mooring":"fghx asdffd",
                        "created":"2021-05-17T02:53:14.146946Z",
                        "updated":"2021-05-17T03:12:12.968954Z",
                        "exported": False,
                        },
                    "vessel_ownership": {
                        "percentage": None,
                        "individual_owner": False,
                        "company_ownership": {
                            "id":13,
                            "blocking_proposal":152,
                            "status":"draft",
                            "vessel":116,
                            "company": {
                                "id":11,
                                "name":"20210517_1"
                                },
                            "percentage":25,
                            "start_date":"2021-05-17T02:53:14.157933Z",
                            "end_date": None,
                            "created":"2021-05-17T02:53:14.157953Z",
                            "updated":"2021-05-17T03:12:13.010817Z"
                            }
                        },
                    "rego_no":"20210517_1",
                    "id":116
                    }
                }

        submit_response = self.client.post(
                '/api/proposal/{}/submit/'.format(proposal_id),
                submit_proposal_data, 
                format='json',
                HTTP_HOST=HTTP_HOST_FOR_TEST,
        )
        self.assertEqual(submit_response.status_code, 200)

        ## proposal_submit(instance, request) - need a request obj, so we just make changes manually here
        proposal = Proposal.objects.get(id=proposal_id)
        proposal.lodgement_date = datetime.now(pytz.timezone(TIME_ZONE))
        proposal.processing_status = 'with_assessor'
        proposal.customer_status = 'with_assessor'
        proposal.save()

