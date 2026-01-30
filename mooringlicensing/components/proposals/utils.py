import datetime
import mimetypes
import os
from decimal import Decimal
import pytz
from ledger_api_client.settings_base import TIME_ZONE
from django.http import HttpResponse

from mooringlicensing import settings
import json
from mooringlicensing.components.main.utils import get_dot_vessel_information
from mooringlicensing.components.main.models import GlobalSettings
from mooringlicensing.components.main.process_document import save_vessel_registration_document_obj
from mooringlicensing.components.proposals.models import (
    VesselOwnershipCompanyOwnership,
    WaitingListApplication,
    AnnualAdmissionApplication,
    AuthorisedUserApplication,
    MooringLicenceApplication,
    Vessel,
    VesselOwnership,
    Owner,
    Proposal,
    Company,
    CompanyOwnership,
    Mooring, ProposalApplicant, VesselRegistrationDocument,
    ProposalSiteLicenseeMooringRequest
)
from mooringlicensing.components.proposals.serializers import (
    SaveVesselDetailsSerializer,
    SaveVesselOwnershipSerializer,
    SaveCompanyOwnershipSerializer,
    SaveDraftProposalVesselSerializer,
    SaveWaitingListApplicationSerializer,
    SaveMooringLicenceApplicationSerializer,
    SaveAuthorisedUserApplicationSerializer,
    SaveAnnualAdmissionApplicationSerializer,
    VesselDetailsSerializer,
)

from mooringlicensing.components.approvals.models import (
    MooringLicence,
    Approval
)
from mooringlicensing.components.payments_ml.models import FeeItemApplicationFee
from ledger_api_client.ledger_models import EmailUserRO
from mooringlicensing.ledger_api_utils import get_invoice_payment_status
from mooringlicensing.settings import PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_SWAP_MOORINGS
from copy import deepcopy
from rest_framework import serializers
from mooringlicensing.helpers import is_system_admin
import logging
from django.db.models import Q

logger = logging.getLogger(__name__)

def save_proponent_data(instance, request, action, being_auto_approved=False):

    if (
        (instance.proposal_applicant and 
         instance.proposal_applicant.email_user_id == request.user.id and 
         (instance.processing_status == Proposal.PROCESSING_STATUS_DRAFT) or being_auto_approved)
        or instance.has_assessor_mode(request.user)
    ):

        if instance.has_assessor_mode(request.user):    
            proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}
            if proposal_data and "no_email_notifications" in proposal_data:
                instance.no_email_notifications = proposal_data["no_email_notifications"]
                instance.save()
        
        instance.refresh_from_db()

        if action == 'submit':
            logger.info('Proposal {} has been submitted'.format(instance.lodgement_number))
        if type(instance.child_obj) == WaitingListApplication:
            save_proponent_data_wla(instance, request, action)
        elif type(instance.child_obj) == AnnualAdmissionApplication:
            save_proponent_data_aaa(instance, request, action)
        elif type(instance.child_obj) == AuthorisedUserApplication:
            save_proponent_data_aua(instance, request, action)
        elif type(instance.child_obj) == MooringLicenceApplication:
            save_proponent_data_mla(instance, request, action)        
        
    else:
        raise serializers.ValidationError("user not authorised to update applicant details")


def save_proponent_data_aaa(instance, request, action):
    logger.info(f'Saving proponent data of the proposal: [{instance}]')
    # vessel
    vessel_data = deepcopy(request.data.get("vessel"))
    if vessel_data:
        if ((action == 'submit' or (
            instance.has_assessor_mode(request.user) and 
            instance.processing_status != Proposal.PROCESSING_STATUS_DRAFT))):
            submit_vessel_data(instance, request, vessel_data=vessel_data)
        else:
            save_vessel_data(instance, request, vessel_data)
    instance.refresh_from_db()
    # proposal
    proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}
    serializer = SaveAnnualAdmissionApplicationSerializer(
            instance, 
            data=proposal_data, 
            context={
                "action": action,
                "proposal_id": instance.id
                }
    )
    serializer.is_valid(raise_exception=True)
    instance = serializer.save()
    logger.info(f'Update the Proposal: [{instance}] with the data: [{proposal_data}].')

    update_proposal_applicant(instance.child_obj, request)
    instance.refresh_from_db()
    instance.child_obj.set_auto_approve(request)
    instance.refresh_from_db()   

    if ('bypass_auto_approval' in request.data and 
        request.data.get('bypass_auto_approval') and 
        is_system_admin(request)
        ):
        instance.auto_approve = False
        instance.save()


def save_proponent_data_wla(instance, request, action):
    logger.info(f'Saving proponent data of the proposal: [{instance}]')
    # vessel
    vessel_data = deepcopy(request.data.get("vessel"))
    if vessel_data:
        if ((action == 'submit' or (
            instance.has_assessor_mode(request.user) and 
            instance.processing_status != Proposal.PROCESSING_STATUS_DRAFT))):
            submit_vessel_data(instance, request, vessel_data=vessel_data)
        else:
            save_vessel_data(instance, request, vessel_data)
    instance.refresh_from_db()
    # proposal
    proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}
    serializer = SaveWaitingListApplicationSerializer(
            instance, 
            data=proposal_data, 
            context={
                "action": action,
                "proposal_id": instance.id
                }
    )
    serializer.is_valid(raise_exception=True)
    instance = serializer.save()
    logger.info(f'Update the Proposal: [{instance}] with the data: [{proposal_data}].')

    update_proposal_applicant(instance.child_obj, request)
    instance.refresh_from_db()
    instance.child_obj.set_auto_approve(request)

    if ('bypass_auto_approval' in request.data and 
        request.data.get('bypass_auto_approval') and 
        is_system_admin(request)
        ):
        instance.auto_approve = False
        instance.save()


def save_proponent_data_mla(instance, request, action):
    logger.info(f'Saving proponent data of the proposal: [{instance}]')

    # vessel
    vessel_data = deepcopy(request.data.get("vessel"))
    if vessel_data:
        if ((action == 'submit' or (
            instance.has_assessor_mode(request.user) and 
            instance.processing_status != Proposal.PROCESSING_STATUS_DRAFT))):
            submit_vessel_data(instance, request, vessel_data=vessel_data)
        else:
            save_vessel_data(instance, request, vessel_data)
    instance.refresh_from_db()
    # proposal
    proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}
    serializer = SaveMooringLicenceApplicationSerializer(
            instance, 
            data=proposal_data, 
            context={
                "action": action,
                "proposal_id": instance.id
                }
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    logger.info(f'Update the Proposal: [{instance}] with the data: [{proposal_data}].')

    update_proposal_applicant(instance.child_obj, request)
    instance.refresh_from_db()
    instance.child_obj.set_auto_approve(request)

    if ('bypass_auto_approval' in request.data and 
        request.data.get('bypass_auto_approval') and 
        is_system_admin(request)
        ):
        instance.auto_approve = False
        instance.save()
    
    if action == 'submit':
        instance.child_obj.process_after_submit(request)
        instance.refresh_from_db()


def save_proponent_data_aua(instance, request, action):
    logger.info(f'Saving proponent data of the proposal: [{instance}]')
    mooring_id = request.data.get('proposal',{}).get('mooring_id')
    # checking if the mooring licence for the mooring is active
    if(mooring_id and action == 'submit'):
        mooring_status = None
        try:
            mooring_status =  Mooring.objects.get(id=mooring_id).mooring_licence.status
        except:
            raise serializers.ValidationError('Mooring site licence for this mooring does not exist')
        if(mooring_status != 'current'):
            raise serializers.ValidationError('Mooring site licence for this mooring is not active')

    vessel_data = deepcopy(request.data.get("vessel"))
    if vessel_data:
        if ((action == 'submit' or (
            instance.has_assessor_mode(request.user) and 
            instance.processing_status != Proposal.PROCESSING_STATUS_DRAFT))):
            submit_vessel_data(instance, request, vessel_data=vessel_data)
        else:
            save_vessel_data(instance, request, vessel_data)
    instance.refresh_from_db()
    # proposal
    proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}

    if ((not proposal_data.get("keep_existing_mooring") or (instance.proposal_type and instance.proposal_type.code == 'new'))
        and proposal_data.get("mooring_authorisation_preference") == 'site_licensee'):
            site_licensee_moorings_data = proposal_data.get('site_licensee_moorings')

            if not site_licensee_moorings_data:
                raise serializers.ValidationError("No mooring site licensees have been specified - please add at least one site licensee or select Rottnest Island Authority for authorisation")

            #get all ProposalSiteLicenseeMooringRequest for proposal
            site_licensee_moorings = instance.site_licensee_mooring_request.all()
            
            current_mooring_licences = MooringLicence.objects.filter(approval__status=Approval.APPROVAL_STATUS_CURRENT)

            #for each in site_licensee_moorings_data, check if it exists
            keep_id_list = []
            for i in site_licensee_moorings_data:
                #check if email and mooring id exist together as a valid mooring license
                valid = current_mooring_licences.filter(
                    approval__current_proposal__proposal_applicant__email=i["email"],
                    mooring__id=i["mooring_id"]
                ).exists()
                if not valid:
                    raise serializers.ValidationError("Provided email and mooring are not in a current valid mooring license together")
                qs = site_licensee_moorings.filter(site_licensee_email=i["email"],mooring_id=i["mooring_id"])
                if qs.exists():
                    site_licensee_mooring = qs.first()
                    if not site_licensee_mooring.enabled:
                        #if it exists but is not enabled, enable it
                        site_licensee_mooring.enabled = True
                        site_licensee_mooring.save()
                    keep_id_list.append(site_licensee_mooring.id)
                else:
                    #if it does not exist
                    new_site_licence_mooring_request = ProposalSiteLicenseeMooringRequest.objects.create(
                        proposal=instance,
                        site_licensee_email=i["email"],
                        mooring_id=i["mooring_id"],
                        enabled=True,
                    )
                    keep_id_list.append(new_site_licence_mooring_request.pk)
            #disable any remainder records
            site_licensee_moorings.exclude(id__in=keep_id_list).update(enabled=False)
    else: #RIA preferred or no additional requests, disable all site_licensee_mooring_requests (if any)
        instance.site_licensee_mooring_request.all().update(enabled=False)
        
    serializer = SaveAuthorisedUserApplicationSerializer(
            instance, 
            data=proposal_data, 
            context={
                "action": action,
                "proposal_id": instance.id
                }
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    logger.info(f'Update the Proposal: [{instance}] with the data: [{proposal_data}].')

    update_proposal_applicant(instance.child_obj, request)
    instance.refresh_from_db()
    instance.child_obj.set_auto_approve(request)

    if ('bypass_auto_approval' in request.data and 
        request.data.get('bypass_auto_approval') and 
        is_system_admin(request)
        ):
        instance.auto_approve = False
        instance.save()

    if action == 'submit':
        instance.child_obj.process_after_submit(request)
        instance.refresh_from_db()


# draft and submit
def save_vessel_data(instance, request, vessel_data):
    logger.info(f'save_vessel_data is called with the vessel_data: {vessel_data}')

    vessel_details_data = {}
    vessel_id = vessel_data.get('id')
    vessel_details_data = vessel_data.get("vessel_details")
    
    # update vessel details to vessel_data
    for key in vessel_details_data.keys():
        vessel_data.update({key: vessel_details_data.get(key)})
    if vessel_id:
        vessel_data.update({"vessel_id": vessel_id})

    vessel_ownership_data = vessel_data.get("vessel_ownership")
    if vessel_ownership_data.get('company_ownership'):
        company_ownership_percentage = vessel_ownership_data.get('company_ownership', {}).get('percentage')
        company_ownership_name = vessel_ownership_data.get('company_ownership', {}).get('company', {}).get('name')
        vessel_data.update({"company_ownership_percentage": company_ownership_percentage})
        vessel_data.update({"company_ownership_name": company_ownership_name})
    if 'company_ownership' in vessel_ownership_data.keys():
        vessel_ownership_data.pop('company_ownership', None)

    # copy VesselOwnership fields to vessel_data
    for key in vessel_ownership_data.keys():
        vessel_data.update({key: vessel_ownership_data.get(key)})

    # overwrite vessel_data.id with correct value
    obj = instance
    if type(instance) == Proposal:
        obj = instance.child_obj

    if not (type(obj) == MooringLicenceApplication and vessel_data.get('readonly')): 
        serializer = SaveDraftProposalVesselSerializer(instance, vessel_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f'Proposal: [{instance}] has been updated with the vessel data: [{vessel_data}]')

def dot_check_wrapper(request, payload, vessel_lookup_errors, vessel_data):
    json_string = json.dumps(payload)
    dot_response_str = get_dot_vessel_information(request, json_string)
    try:
        dot_response_json = json.loads(dot_response_str)
    except Exception as e:
        raise serializers.ValidationError("Cannot load as JSON: {}".format(dot_response_str))
    try:
        logger.info("dot_response_json")
        logger.info(dot_response_json)
        logger.info(dot_response_json.get("status"))
        if dot_response_json.get("status") and not dot_response_json.get("status") == 200:
            raise serializers.ValidationError("DoT Service Unavailable")
        
        dot_response = dot_response_json.get("data")
        dot_boat_length = dot_response.get("boatLength")
        boat_found = True if dot_response.get("boatFound") == "Y" else False
        boat_owner_match = True if dot_response.get("boatOwnerMatch") else False
        ml_boat_length = vessel_data.get("vessel_details", {}).get("vessel_length")
        if not boat_found or not boat_owner_match or not dot_boat_length == float(ml_boat_length):
            vessel_lookup_errors[vessel_data.get("rego_no")] = "The provided details do not match those recorded with the Department of Transport"
    except:
        raise serializers.ValidationError("Issue verifying your DoT vessel information. Please try again later, or if the problem persists, please contact us.")

def submit_vessel_data(instance, request, vessel_data=None, approving=False):

    #if vessel data not provided, get from instance
    if not vessel_data:
        vessel_data = {
            "id": instance.vessel_id,
            "rego_no": instance.rego_no,
            "vessel_details": {
                "berth_mooring": instance.berth_mooring,
                "vessel_beam": instance.vessel_beam,
                "vessel_draft": instance.vessel_draft,
                "vessel_length": instance.vessel_length,
                "vessel_name": instance.vessel_name,
                "vessel_type": instance.vessel_type,
                "vessel_weight": instance.vessel_weight,
            },
            "vessel_ownership": {
                "individual_owner": instance.individual_owner,
                "dot_name": instance.dot_name,
            },
        }

        if instance.individual_owner:
            vessel_data["vessel_ownership"]["percentage"] = instance.percentage
        else:    
            vessel_data["vessel_ownership"]["company_ownership"] = {
                "company": {"name": instance.company_ownership_name},
                "percentage": instance.company_ownership_percentage,
            }

    logger.info(f'submit_vessel_data() is called with the vessel_data: {vessel_data}')

    #only enforce this for requests and if a rego_no has been provided
    if (request and vessel_data["rego_no"]):
        if (not vessel_data or not vessel_data["vessel_details"] or 
            not (vessel_data["vessel_details"]["vessel_draft"] and vessel_data["vessel_details"]["vessel_length"] and vessel_data["vessel_details"]["vessel_weight"])
        ):
            raise serializers.ValidationError("Submitted vessel details missing")
        else:
            try:
                if not(float(vessel_data["vessel_details"]["vessel_draft"]) and float(vessel_data["vessel_details"]["vessel_length"]) and float(vessel_data["vessel_details"]["vessel_weight"])):
                    raise serializers.ValidationError("Provided vessel details invalid")
            except:
                raise serializers.ValidationError("Provided vessel details invalid")
            
            if isinstance(instance.child_obj,WaitingListApplication):
                try:
                    minimum_length = float(GlobalSettings.objects.get(key=GlobalSettings.KEY_MINUMUM_MOORING_VESSEL_LENGTH).value)
                except:
                    minimum_length = float(GlobalSettings.default_values[GlobalSettings.KEY_MINUMUM_MOORING_VESSEL_LENGTH])
            else:
                try:
                    minimum_length = float(GlobalSettings.objects.get(key=GlobalSettings.KEY_MINIMUM_VESSEL_LENGTH).value)
                except:
                    minimum_length = float(GlobalSettings.default_values[GlobalSettings.KEY_MINIMUM_VESSEL_LENGTH])

            if float(vessel_data["vessel_details"]["vessel_length"]) < minimum_length:
                raise serializers.ValidationError(f"Vessel length must not be less than {minimum_length}m")
            
    # Dot vessel rego lookup
    logger.info('Performing DoT check...')
    vessel_lookup_errors = {}
    # Mooring Licence vessel history
    # Migrated records do not have DOT name, so only run dot check for new vessel submissions
    if (isinstance(instance.child_obj,MooringLicenceApplication) and 
        instance.approval and 
        not instance.approval.migrated
        ):
        if isinstance(instance.approval.child_obj,MooringLicence) and instance.approval.child_obj.vessel_ownership_list:
            for vo in instance.approval.child_obj.vessel_ownership_list:
                if vo.dot_name:
                    dot_name = vo.dot_name
                    owner_str = dot_name.replace(" ", "%20")
                else:
                    owner_str = ""
                if request: #if there is no request do not run DoT check (system reissue)
                    payload = {
                            "boatRegistrationNumber": vo.vessel.rego_no,
                            "owner": owner_str,
                            "userId": str(request.user.id)
                            }
                    if settings.DO_DOT_CHECK and vo.individual_owner:
                        dot_check_wrapper(request, payload, vessel_lookup_errors, vessel_data)

    # current proposal vessel check
    if vessel_data.get("rego_no"):
        dot_name = vessel_data.get("vessel_ownership", {}).get("dot_name", "")
        individual_owner = vessel_data.get("vessel_ownership", {}).get("individual_owner", True)
        if dot_name:
            owner_str = dot_name.replace(" ", "%20")
        else:
            owner_str = ""
        if request: #if there is no request do not run DoT check (system reissue)
            payload = {
                    "boatRegistrationNumber": vessel_data.get("rego_no"),
                    "owner": owner_str,
                    "userId": str(request.user.id)
                    }
            if settings.DO_DOT_CHECK and individual_owner:
                dot_check_wrapper(request, payload, vessel_lookup_errors, vessel_data)
        if vessel_lookup_errors:
            raise serializers.ValidationError(vessel_lookup_errors)

    if not vessel_data.get('rego_no'):
        #MLA and WLA do not need a vessel to be submitted
        if (
            hasattr(instance,"child_obj") and (isinstance(instance.child_obj, MooringLicenceApplication) or isinstance(instance.child_obj, WaitingListApplication))
            or 
            (isinstance(instance, MooringLicenceApplication) or isinstance(instance, WaitingListApplication))
        ):
            return
        else:
            raise serializers.ValidationError("Application cannot be submitted without a vessel listed")

    # Update Proposal obj
    save_vessel_data(instance, request, vessel_data)

    if approving:
        # Update VesselDetails obj
        vessel, vessel_details = store_vessel_data(request, vessel_data)
        # Associate the vessel_details with the proposal
        instance.vessel_details = vessel_details
        instance.save()

        # record ownership data
        vessel_ownership = store_vessel_ownership(request, vessel, instance)
        instance.vessel_ownership = vessel_ownership #TODO investigate why this would ever be None
        instance.save()

    if request:
        instance.validate_against_existing_proposals_and_approvals()

    ownership_percentage_validation(instance)


def store_vessel_data(request, vessel_data):
    logger.info(f'store_vessel_data() is called with the vessel_data: {vessel_data}')

    if not vessel_data.get('rego_no'):
        raise serializers.ValidationError({"Missing information": "You must supply a Vessel Registration Number"})
    rego_no = vessel_data.get('rego_no').replace(" ", "").strip().lower() # successfully avoiding dupes?
    vessel, created = Vessel.objects.get_or_create(rego_no=rego_no.upper())
    if created:
        logger.info(f'New Vessel: [{vessel}] has been created.')
    
    vessel_details_data = vessel_data.get("vessel_details")
    # add vessel to vessel_details_data
    vessel_details_data["vessel"] = vessel.id

    ## Vessel Details
    existing_vessel_details = vessel.latest_vessel_details
    ## we no longer use a read_only flag, so must compare incoming data to existing
    existing_vessel_details_data = VesselDetailsSerializer(existing_vessel_details).data

    create_vessel_details = False
    for key in existing_vessel_details_data.keys():
        if key in vessel_details_data and existing_vessel_details_data[key] != vessel_details_data[key]:
            # Value is different between the existing and new --> We create new vessel details rather than updating the existing
            create_vessel_details = True
            break
    
    #replace null vessel name
    if vessel_details_data["vessel_name"] == None:
        vessel_details_data["vessel_name"] = ""

    if create_vessel_details:
        serializer = SaveVesselDetailsSerializer(data=vessel_details_data)
        serializer.is_valid(raise_exception=True)
        vessel_details = serializer.save()
        logger.info(f'New VesselDetails: [{vessel_details}] has been created.')
    else:
        serializer = SaveVesselDetailsSerializer(existing_vessel_details, vessel_details_data)
        serializer.is_valid(raise_exception=True)
        vessel_details = serializer.save()
        logger.info(f'VesselDetails: [{vessel_details}] has been updated.')

    return vessel, vessel_details

def store_vessel_ownership(request, vessel, instance):
    logger.info(f'Storing vessel_ownership with the vessel: [{vessel}], proposal: [{instance}] ...')

    ## Get Vessel
    ## we cannot use vessel_data, because this dict has been modified in store_vessel_data()
    if request and hasattr(request,'data') and request.data.get('vessel'):
        vessel_ownership_data = deepcopy(request.data.get('vessel').get("vessel_ownership"))
    else:
        vessel_data = {
            "id": instance.vessel_id,
            "rego_no": instance.rego_no,
            "vessel_details": {
                "berth_mooring": instance.berth_mooring,
                "vessel_beam": instance.vessel_beam,
                "vessel_draft": instance.vessel_draft,
                "vessel_length": instance.vessel_length,
                "vessel_name": instance.vessel_name,
                "vessel_type": instance.vessel_type,
                "vessel_weight": instance.vessel_weight,
            },
            "vessel_ownership": {
                "individual_owner": instance.individual_owner,
                "dot_name": instance.dot_name,
            },
        }
        if instance.individual_owner:
            vessel_data["vessel_ownership"]["percentage"] = instance.percentage
        else:    
            vessel_data["vessel_ownership"]["company_ownership"] = {
                "company": {"name": instance.company_ownership_name},
                "percentage": instance.company_ownership_percentage,
            }
        vessel_ownership_data = vessel_data["vessel_ownership"]

    if vessel_ownership_data.get('individual_owner') is None:
        raise serializers.ValidationError({"Missing information": "You must select a Vessel Owner"})
    elif (not vessel_ownership_data.get('individual_owner') and not 
            vessel_ownership_data.get("company_ownership", {}).get("company", {}).get("name")
            ):
        raise serializers.ValidationError({"Missing information": "You must supply the company name"})

    individual_owner = vessel_ownership_data.get('individual_owner')
    company_ownership = None
    if individual_owner:
        # This proposal is for individual owner
        logger.info(f'This proposal: [{instance}] is for individual owner.')
    else:
        # This proposal is for company owner
        logger.info(f'This proposal: [{instance}] is for company owner.')

        company_name = vessel_ownership_data.get("company_ownership").get("company").get("name")
        company, created = Company.objects.get_or_create(name=company_name)
        if created:
            logger.info(f'New Company: [{company}] has been created.')

        ## CompanyOwnership
        company_ownership_data = vessel_ownership_data.get("company_ownership")
        company_ownership_data.update({"company": company.id}) # update company key from dict to pk
        company_ownership_data.update({"vessel": vessel.id}) # add vessel to company_ownership_data
        company_ownership_set = CompanyOwnership.objects.filter(
            company=company,
            vessel=vessel,
        )

        # Check if we need to create a new CO record
        create_company_ownership = False
        edit_company_ownership = True
        if company_ownership_set.count():
            company_ownership = company_ownership_set.first()
        else:
            serializer = SaveCompanyOwnershipSerializer(data=company_ownership_data)
            serializer.is_valid(raise_exception=True)
            company_ownership = serializer.save()
            logger.info(f'New CompanyOwnership: [{company_ownership}] has been created')

        if company_ownership_set.filter(vesselownershipcompanyownership__status=VesselOwnershipCompanyOwnership.COMPANY_OWNERSHIP_STATUS_DRAFT):
            company_ownership = company_ownership_set.filter(vesselownershipcompanyownership__status=VesselOwnershipCompanyOwnership.COMPANY_OWNERSHIP_STATUS_DRAFT)[0]
            ## cannot edit draft record with blocking_proposal
            if edit_company_ownership:
                if not company_ownership.blocking_proposal:
                    serializer = SaveCompanyOwnershipSerializer(company_ownership, company_ownership_data)
                    serializer.is_valid(raise_exception=True)
                    company_ownership = serializer.save()
                    logger.info(f'CompanyOwnership: [{company_ownership}] has been updated')


    ## add to vessel_ownership_data
    if company_ownership and company_ownership.id:
        if instance:
            ## set blocking_proposal
            company_ownership.blocking_proposal = instance
            company_ownership.save()

            logger.info(f'BlockingProposal: [{instance.lodgement_number}] has been set to the CompanyOwnership: [{company_ownership}]')
    vessel_ownership_data['vessel'] = vessel.id

    if instance and instance.proposal_applicant:
        owner, created = Owner.objects.get_or_create(emailuser=instance.proposal_applicant.email_user_id)
        if created:
            logger.info(f'New Owner: [{owner}] has been created.')
        else:
            logger.info(f'Existing Owner: [{owner}] has been retrieved.')

        vessel_ownership_data['owner'] = owner.id
    else:
        raise serializers.ValidationError("proposal has no applicant to be set as vessel owner")

    # Create/Retrieve vessel_ownership
    # ensure previously sold vessel_ownerships are NOT re-used
    vo_created = False
    q_for_approvals_check = Q()  # We want to check if there is a current approval which links to the vessel_ownership retrieved below
    if instance.proposal_type.code in [PROPOSAL_TYPE_NEW,]:
        vessel_ownerships = VesselOwnership.objects.filter(
            owner=owner,  # Owner is actually the accessing user (request.user) as above.
            vessel=vessel,
            company_ownerships=company_ownership,
            end_date=None
        )
        if vessel_ownerships.count():
            vessel_ownership = vessel_ownerships.first()
        else:
            vessel_ownership = VesselOwnership.objects.create(
                owner=owner,
                vessel=vessel,
            )
            if company_ownership:
                vessel_ownership.company_ownerships.add(company_ownership)
                logger.info(f'CompanyOwnership: [{company_ownership}] has been added to the company_ownerships field of the VesselOwnership: [{vessel_ownership}].')
            vo_created = True
    elif instance.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_SWAP_MOORINGS,]:
        # Retrieve a vessel_ownership from the previous proposal
        vessel_ownership = instance.vessel_ownership if instance.vessel_ownership != None else instance.get_latest_vessel_ownership_by_vessel(vessel)

        vessel_ownership_to_be_created = False
        if vessel_ownership and vessel_ownership.end_date:
            logger.info(f'Existing VesselOwnership: [{vessel_ownership}] has been retrieved, but the vessel is sold.  This vessel ownership cannot be used.')
            vessel_ownership_to_be_created = True
        
        keep_existing_vessel = False
        if (vessel_ownership and 
            vessel_ownership.vessel and 
            vessel_ownership.vessel.rego_no and 
            not vessel_ownership.end_date and
            vessel.rego_no):
            keep_existing_vessel = vessel_ownership.vessel.rego_no == vessel.rego_no

        if not keep_existing_vessel:
            if instance.application_type.code in [MooringLicenceApplication.code,]:
                logger.info(f'New vessel: [{vessel}] is going to be added to the ML application: [{instance}].')
                vessel_ownership_to_be_created = True
            if instance.application_type.code in [AuthorisedUserApplication.code,]:
                logger.info(f'New vessel: [{vessel}] is going to replace the existing vessel of the AU application: [{instance}].')
                vessel_ownership_to_be_created = True

        #set vessel_ownership_to_be_created to true if switch between individual/company ownership
        if (vessel_ownership and
            "individual_owner" in vessel_ownership_data and 
            vessel_ownership_data["individual_owner"] != vessel_ownership.individual_owner):
            vessel_ownership_to_be_created = True

        if vessel_ownership_to_be_created:
            vessel_ownership = VesselOwnership.objects.create(
                owner=owner,  # Owner is actually the accessing user (request.user) as above.
                vessel=vessel,
            )
            if company_ownership:
                vessel_ownership.company_ownerships.add(company_ownership)
                logger.info(f'CompanyOwnership: [{company_ownership}] has been added to the company_ownerships field of the VesselOwnership: [{vessel_ownership}].')
            vo_created = True

        q_for_approvals_check &= ~Q(id=instance.approval.id)  # We want to exclude the approval we are currently processing for
    else:
        msg = f'Proposal: [{instance}] does not have correct proposal type.'
        logger.error(msg)
        raise Exception(msg)

    q_for_approvals_check &= Q(current_proposal__vessel_ownership=vessel_ownership)
    q_for_approvals_check &= Q(status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED, Approval.APPROVAL_STATUS_FULFILLED,])

    # Other approvals which have the link to the vessel_ownership
    approvals = Approval.objects.filter(q_for_approvals_check)

    if vo_created:
        logger.info(f'New VesselOwnership: [{vessel_ownership}] has been created.')
    else:
        logger.info(f'Existing VesselOwnership: [{vessel_ownership}] has been retrieved.')

    if approvals.count() == 1:
        logger.warning(f'This VesselOwnership: [{vessel_ownership}] is also used with another active approval: [{approvals[0]}].')
    elif approvals:
        logger.warning(f'This VesselOwnership: [{vessel_ownership}] is also used with other active approvals: [{approvals}].')
    else:
        logger.info(f'This VesselOwnership: [{vessel_ownership}] is not used with any other active approvals.')

    # Update the vessel_ownership
    serializer = SaveVesselOwnershipSerializer(vessel_ownership, vessel_ownership_data)
    serializer.is_valid(raise_exception=True)
    vessel_ownership = serializer.save()
    logger.info(f'VesselOwnership: [{vessel_ownership}] has been updated with the data: [{vessel_ownership_data}].')

    if company_ownership:
        vessel_ownership.company_ownerships.add(company_ownership)
        logger.info(f'CompanyOwnership: [{company_ownership}] has been added to the company_ownerships field of the VesselOwnership: [{vessel_ownership}].')

    # check and set blocking_owner
    if instance and request:
        vessel.check_blocking_ownership(vessel_ownership, instance, request)

    # save temp doc if exists
    handle_vessel_registration_documents_in_limbo(instance.id, vessel_ownership)

    return vessel_ownership

def handle_vessel_registration_documents_in_limbo(proposal_id, vessel_ownership):
    # VesselRegistrationDocument object with proposal is the documents stored for the draft proposal
    documents_in_limbo = VesselRegistrationDocument.objects.filter(proposal_id=proposal_id)

    for doc in documents_in_limbo:
        doc.vessel_ownership = vessel_ownership  # Link to the vessel_ownership
        doc.can_delete = False
        doc.save()

        logger.info(f'VesselRegistrationFile: {doc} has had a link to the vessel_ownership: {vessel_ownership}')


def handle_document(instance, vessel_ownership, request_data, *args, **kwargs):
    temporary_document_collection_id = request_data.get('proposal', {}).get('temporary_document_collection_id')
    if temporary_document_collection_id:
        temp_doc_collection = None
        if temp_doc_collection:
            for doc in temp_doc_collection.documents.all():
                save_vessel_registration_document_obj(vessel_ownership, doc)
            temp_doc_collection.delete()
            instance.temporary_document_collection_id = None
            instance.save()

def ownership_percentage_validation(proposal):
    logger.info(f'Calculating the total vessel ownership percentage of the draft vessel: [{proposal.rego_no}]...')

    company_ownership_id = None
    min_percent_fail = False
    vessel_ownership_percentage = 0
    ## First ensure applicable % >= 25
    if not proposal.individual_owner and proposal.company_ownership_name and proposal.company_ownership_percentage:
        if proposal.company_ownership_percentage < 25:
            min_percent_fail = True
        else:
            vessel_ownership_percentage = proposal.company_ownership_percentage   
    elif not proposal.percentage:
        if not proposal.migrated: #we make an exception for migrated proposals as old data does not always have the percentage available
            raise serializers.ValidationError({
                "Ownership Percentage": "You must specify a percentage"
            })
    else:
        if proposal.percentage < 25 and not proposal.migrated:
            min_percent_fail = True
        else:
            vessel_ownership_percentage = proposal.percentage
    if min_percent_fail:
        raise serializers.ValidationError({
            "Ownership Percentage": "Minimum of 25 percent"
            })

    ## Calc total existing
    previous_vessel_ownerships = proposal.get_previous_vessel_ownerships()
    logger.info(f'Vessel ownerships to be excluded from the calculation: {previous_vessel_ownerships}')

    total_percent = vessel_ownership_percentage
    today = datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()
    if proposal.vessel_ownership and (proposal.vessel_ownership.end_date and proposal.vessel_ownership.end_date <= today):
        vessel = None
    else:
        vessel = Vessel.objects.filter(rego_no__exact=proposal.rego_no).last()

    if vessel:
        for vo in vessel.filtered_vesselownership_set.exclude(
                owner__emailuser=proposal.proposal_applicant.email_user_id
            ).distinct('owner'):
            if proposal.vessel_ownership and vo ==  proposal.vessel_ownership:
                continue
            if vo in previous_vessel_ownerships:
                # We don't want to count the percentage in the previous vessel ownerships
                continue
            if vo.company_ownerships.count():
                company_ownership = vo.get_latest_company_ownership()
                if company_ownership:
                    if (company_ownership.id != company_ownership_id and 
                            company_ownership.percentage and
                            company_ownership.blocking_proposal
                    ):
                        total_percent += company_ownership.percentage
                        logger.info(f'Vessel ownership to be taken into account in the calculation: {company_ownership}')
            elif vo.percentage:
                total_percent += vo.percentage
                logger.info(f'Vessel ownership to be taken into account in the calculation: {vo}')

        logger.info(f'Total ownership percentage of the vessel: [{vessel}] is {total_percent}%')

    if total_percent > 100:
        raise serializers.ValidationError({
            "Ownership Percentage": "Total of 100 percent exceeded"
            })


def get_fee_amount_adjusted(proposal, fee_item_being_applied, vessel_length):
    # Retrieve all the fee_items for this vessel

    if fee_item_being_applied:
        logger.info('Adjusting the fee amount for proposal: [{}], fee_item: [{}], vessel_length: [{}]'.format(
            proposal.lodgement_number, fee_item_being_applied, vessel_length
        ))

        fee_amount_adjusted = fee_item_being_applied.get_absolute_amount(vessel_length)

        # Retrieve all the fee items paid for this vessel (through proposal.vessel_ownership)
        fee_items_already_paid = proposal.vessel_ownership.get_fee_items_paid()
        if proposal.approval and proposal.approval.status in (Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,):
            # Retrieve all the fee items paid for the approval this proposal is for (through proposal.approval)
            for item in proposal.approval.get_fee_items():
                if item not in fee_items_already_paid:
                    fee_items_already_paid.append(item)

        if fee_item_being_applied in fee_items_already_paid:
            # Fee item being applied has been paid already
            # We don't charge this fee_item_being_applied
            return Decimal('0.0')
        else:
            for fee_item in fee_items_already_paid:
                if fee_item.fee_period.fee_season == fee_item_being_applied.fee_period.fee_season and \
                        fee_item.fee_constructor.application_type == fee_item_being_applied.fee_constructor.application_type:
                    # Found fee_item which has the same fee_season and the same application_type of fee_item_being_applied
                    # This fee_item's fee_period and vessel_size_category might be different from those of the fee_item_being_applied

                    if fee_item.fee_period.start_date <= fee_item_being_applied.fee_period.start_date:
                        # Find the fee_item which can be considered as already paid for this period
                        target_fee_period = fee_item_being_applied.fee_period
                        target_proposal_type = fee_item_being_applied.proposal_type
                        target_vessel_size_category = fee_item.vessel_size_category

                        target_fee_constructor = fee_item_being_applied.fee_constructor
                        fee_item_considered_paid = target_fee_constructor.get_fee_item_for_adjustment(
                            target_vessel_size_category,
                            target_fee_period,
                            proposal_type=target_proposal_type,  # Find the fee_item with same proposal type (always 'amendment')
                            age_group=None,
                            admission_type=None
                        )

                        # Applicant already partially paid for this fee item.  Deduct it.
                        if fee_item_considered_paid:
                            logger.info(f'Deduct fee item: [{fee_item_considered_paid}] from [{fee_amount_adjusted}].')
                            fee_amount_adjusted -= fee_item_considered_paid.get_absolute_amount(vessel_length)
                            logger.info(f'Result amount: $[{fee_amount_adjusted}].')

        fee_amount_adjusted = 0 if fee_amount_adjusted <= 0 else fee_amount_adjusted
    else:
        if proposal.does_accept_null_vessel:
            fee_amount_adjusted = 0
        else:
            msg = 'The application fee admin data might have not been set up correctly.  Please contact the Rottnest Island Authority.'
            raise Exception(msg)

    return fee_amount_adjusted


def create_proposal_applicant(proposal, system_user):
    proposal_applicant = ProposalApplicant.objects.create(proposal=proposal)
    logger.info(f'ProposalApplicant: [{proposal_applicant}] has been created for the proposal: [{proposal}].')
    if (system_user.ledger_id):
        proposal_applicant.email_user_id = system_user.ledger_id.id
    else:
        serializers.ValidationError("system user does not have a valid email user account")

    if (not system_user.legal_first_name or
        not system_user.legal_last_name or 
        not system_user.legal_dob or 
        not system_user.mobile_number):
        serializers.ValidationError("system user profile is missing required details - please ensure they have provided all required personal/contact details")

    proposal_applicant.first_name = system_user.legal_first_name
    proposal_applicant.last_name = system_user.legal_last_name
    proposal_applicant.email = system_user.email
    proposal_applicant.phone_number = system_user.phone_number
    proposal_applicant.mobile_number = system_user.mobile_number
    proposal_applicant.dob = system_user.legal_dob
    proposal_applicant.save()

def change_proposal_applicant(proposal_applicant, system_user):
    if (system_user.ledger_id):
        proposal_applicant.email_user_id = system_user.ledger_id.id
    else:
        serializers.ValidationError("system user does not have a valid email user account")

    if (not system_user.legal_first_name or
        not system_user.legal_last_name or 
        not system_user.legal_dob or 
        not system_user.mobile_number):
        serializers.ValidationError("system user profile is missing required details - please ensure they have provided all required personal/contact details")

    proposal_applicant.first_name = system_user.legal_first_name
    proposal_applicant.last_name = system_user.legal_last_name
    proposal_applicant.email = system_user.email
    proposal_applicant.phone_number = system_user.phone_number
    proposal_applicant.mobile_number = system_user.mobile_number
    proposal_applicant.dob = system_user.legal_dob

    # Residential address
    proposal_applicant.residential_address_line1 = None
    proposal_applicant.residential_address_line2 = None
    proposal_applicant.residential_address_line3 = None
    proposal_applicant.residential_address_locality = None
    proposal_applicant.residential_address_state = None
    proposal_applicant.residential_address_country = None
    proposal_applicant.residential_address_postcode = None

    # Postal address
    proposal_applicant.postal_address_line1 = None
    proposal_applicant.postal_address_line2 = None
    proposal_applicant.postal_address_line3 = None
    proposal_applicant.postal_address_locality = None
    proposal_applicant.postal_address_state = None
    proposal_applicant.postal_address_country = None
    proposal_applicant.postal_address_postcode = None
    
    proposal_applicant.save()

def update_proposal_applicant(proposal, request):

    proposal_applicant, created = ProposalApplicant.objects.get_or_create(proposal=proposal)
    if created:
        logger.info(f'ProposalApplicant: [{proposal_applicant}] has been created for the proposal: [{proposal}].')

    # Retrieve proposal applicant data from the application
    proposal_applicant_data = request.data.get('profile') if request.data.get('profile') else {}

    # Copy data from the application
    if proposal_applicant_data:
        proposal_applicant.first_name = proposal_applicant_data['legal_first_name']
        proposal_applicant.last_name = proposal_applicant_data['legal_last_name']
        try:
            correct_date = datetime.datetime.strptime(proposal_applicant_data['legal_dob'], '%d/%m/%Y').date()
        except:
            raise serializers.ValidationError("Incorrect date format for legal date of birth - please update this user's profile")
        proposal_applicant.dob = correct_date
 
        if 'residential_address' in proposal_applicant_data:
            proposal_applicant.residential_address_line1 = proposal_applicant_data['residential_address']['line1']
            proposal_applicant.residential_address_line2 = proposal_applicant_data['residential_address']['line2']
            proposal_applicant.residential_address_line3 = proposal_applicant_data['residential_address']['line3']
            proposal_applicant.residential_address_locality = proposal_applicant_data['residential_address']['locality']
            proposal_applicant.residential_address_state = proposal_applicant_data['residential_address']['state']
            proposal_applicant.residential_address_country = proposal_applicant_data['residential_address']['country']
            proposal_applicant.residential_address_postcode = proposal_applicant_data['residential_address']['postcode']

        if 'postal_address' in proposal_applicant_data:
            proposal_applicant.postal_address_line1 = proposal_applicant_data['postal_address']['line1']
            proposal_applicant.postal_address_line2 = proposal_applicant_data['postal_address']['line2']
            proposal_applicant.postal_address_line3 = proposal_applicant_data['postal_address']['line3']
            proposal_applicant.postal_address_locality = proposal_applicant_data['postal_address']['locality']
            proposal_applicant.postal_address_state = proposal_applicant_data['postal_address']['state']
            proposal_applicant.postal_address_country = proposal_applicant_data['postal_address']['country']
            proposal_applicant.postal_address_postcode = proposal_applicant_data['postal_address']['postcode']

        proposal_applicant.email = proposal_applicant_data['email']
        try:
            if proposal_applicant.email:
                email_user = EmailUserRO.objects.filter(email__iexact=proposal_applicant.email, is_active=True).order_by('-id').first()
                proposal_applicant.email_user_id = email_user.id
        except:
            proposal_applicant.email_user_id = None
        
        proposal_applicant.phone_number = proposal_applicant_data['phone_number']
        proposal_applicant.mobile_number = proposal_applicant_data['mobile_number']

        proposal_applicant.save()
        logger.info(f'ProposalApplicant: [{proposal_applicant}] has been updated.')


#TODO this does not appear to be in user - investigate and remove if not required
def make_ownership_ready(proposal, request):
    vessel_ownership = VesselOwnership.objects.create()
    proposal.vessel_ownership = vessel_ownership
    proposal.save()
    logger.info(f'New vessel_ownership {vessel_ownership} has been created and linked to {proposal}')


def construct_dict_from_docs(documents):
    data_to_be_returned = []

    for d in documents:
        try:
            if d._file:
                data_to_be_returned.append({
                    'file': d._file.url,
                    'id': d.id,
                    'name': d.name,
                })
        except Exception as e:
            logger.error(f'Error raised when returning uploaded file data: ({str(e)})')

    return data_to_be_returned
    

def get_file_content_http_response(file_path):
    with open(file_path, 'rb') as f:
        mimetypes.init()
        f_name = os.path.basename(file_path)
        mime_type_guess = mimetypes.guess_type(f_name)
        if mime_type_guess is not None:
            response = HttpResponse(f, content_type=mime_type_guess[0])
        response['Content-Disposition'] = 'inline;filename={}'.format(f_name)
        return response
    
def get_vessel_length_category(target_date, vessel_length, proposal_type, application_type):
    from mooringlicensing.components.payments_ml.models import FeeConstructor
    
    fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_date(application_type, target_date)
    fee_item = fee_constructor.get_fee_item(vessel_length, proposal_type, target_date)

    return fee_item.id

def get_max_vessel_length_for_main_component(proposal):
    #get the max vessel allowed before payment change is required
    max_vessel_length = (0, True)  # (length, include_length)

    proposal_application_type = proposal.application_type    
    proposal_id_list = []
    continue_loop = True
    first = True

    #populate the proposal id list with all previous applications, up to the latest renewal or new application
    #include the latest renewal (if any) but stop checking previous applications after that
    #if the current application is a renewal, still check the previous applications until another renewal/new is found
    while continue_loop:
        if proposal.id in proposal_id_list:
            continue_loop = False
            break
        proposal_id_list.append(proposal.id)
        if (proposal.previous_application and 
            proposal.proposal_type and 
            (not proposal.proposal_type.code in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL,] or first)):
            proposal = proposal.previous_application
        else:
            continue_loop = False
        if first:
            first = False

    fee_item_application_fees = FeeItemApplicationFee.objects.filter(application_fee__proposal_id__in=proposal_id_list).filter(fee_item__fee_constructor__application_type=proposal_application_type)
    for fee_item_application_fee in fee_item_application_fees:     
        length_tuple = fee_item_application_fee.get_max_allowed_length()
        if max_vessel_length[0] < length_tuple[0] or (max_vessel_length[0] == length_tuple[0] and length_tuple[1] == True):
            max_vessel_length = length_tuple

    return max_vessel_length