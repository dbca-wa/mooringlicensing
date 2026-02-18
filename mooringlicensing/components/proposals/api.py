from django.db.models.functions import Concat
from django.core.paginator import Paginator, EmptyPage
import os
import traceback
import pathlib
import uuid
from django.core.files.base import ContentFile
import pytz
from django.db.models import Q, CharField, Value
from django.db import transaction
from django.core.exceptions import ValidationError
from rest_framework import viewsets, serializers, views, mixins
from rest_framework.decorators import action as detail_route
from rest_framework.decorators import action as list_route
from rest_framework.response import Response
from datetime import datetime
from ledger_api_client.settings_base import TIME_ZONE
from ledger_api_client.ledger_models import EmailUserRO as EmailUser
from mooringlicensing import settings
from mooringlicensing.components.main.models import GlobalSettings
from mooringlicensing.components.proposals.utils import (
    construct_dict_from_docs, 
    save_proponent_data, 
    create_proposal_applicant, 
    change_proposal_applicant, 
    get_max_vessel_length_for_main_component,
)
from mooringlicensing.components.proposals.models import (
    ElectoralRollDocument, HullIdentificationNumberDocument, InsuranceCertificateDocument, 
    MooringReportDocument, VesselOwnershipCompanyOwnership,
    ProposalType, ProposalApplicant, VesselRegistrationDocument, ProposalSiteLicenseeMooringRequest
)
from mooringlicensing.components.main.utils import (
    get_bookings, calculate_max_length,
)
from ledger_api_client.managed_models import SystemUser

from django.core.cache import cache
from mooringlicensing.components.proposals.models import (
    Proposal,
    ProposalRequirement,
    ProposalStandardRequirement,
    AmendmentRequest,
    AmendmentReason,
    VesselDetails,
    WaitingListApplication,
    AnnualAdmissionApplication,
    AuthorisedUserApplication,
    MooringLicenceApplication,
    VESSEL_TYPES,
    INSURANCE_CHOICES,
    Vessel,
    VesselOwnership,
    MooringBay,
    Owner,
    Company,
    CompanyOwnership,
    Mooring,
)
from mooringlicensing.components.proposals.serializers import (
    ProposalForEndorserSerializer,
    ProposalSerializer,
    InternalProposalSerializer,
    ProposalUserActionSerializer,
    MooringUserActionSerializer,
    ProposalLogEntrySerializer,
    VesselLogEntrySerializer,
    MooringLogEntrySerializer,
    ProposalRequirementSerializer,
    ProposalStandardRequirementSerializer,
    ProposedApprovalSerializer,
    AmendmentRequestSerializer,
    ListProposalSerializer,
    ListProposalSiteLicenseeMooringRequestSerializer,
    ListVesselOwnershipSerializer,
    VesselSerializer,
    VesselDetailsSerializer,
    VesselOwnershipSerializer,
    MooringBaySerializer, ProposedDeclineSerializer,
    CompanyOwnershipSerializer,
    CompanySerializer,
    SaveVesselOwnershipSaleDateSerializer,
    VesselOwnershipSaleDateSerializer,
    MooringSerializer,
    VesselFullSerializer,
    VesselFullOwnershipSerializer,
    ListMooringSerializer,
    AmendmentRequestDisplaySerializer
)
from mooringlicensing.components.approvals.models import (
    Approval, DcvVessel, WaitingListAllocation, Sticker, 
    DcvOrganisation, AnnualAdmissionPermit, AuthorisedUserPermit,
    MooringLicence, VesselOwnershipOnApproval, MooringOnApproval, 
    DcvPermit, DcvAdmission, DcvAdmissionArrival
)
from mooringlicensing.components.main.models import ApplicationType
from mooringlicensing.components.payments_ml.models import FeeConstructor
from mooringlicensing.components.approvals.email import (
    send_reissue_ml_after_sale_recorded_email, send_reissue_wla_after_sale_recorded_email, 
    send_reissue_aap_after_sale_recorded_email, send_reissue_aup_after_sale_recorded_email
)
from mooringlicensing.components.approvals.serializers import (
    LookupApprovalSerializer,
)
from mooringlicensing.components.main.process_document import (
    process_generic_document
)
from mooringlicensing.components.main.decorators import (
    basic_exception_handler
)
from mooringlicensing.components.approvals.utils import get_wla_allowed
from mooringlicensing.helpers import (
    is_authorised_to_modify, is_customer, is_internal, 
    is_applicant_address_set, is_authorised_to_submit_documents, is_system_admin
)
from rest_framework_datatables.pagination import DatatablesPageNumberPagination
from rest_framework_datatables.filters import DatatablesFilterBackend
from copy import deepcopy
from django.core.exceptions import ObjectDoesNotExist

import logging

from mooringlicensing.settings import (
    PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,
    PAYMENT_SYSTEM_ID, MAKE_PRIVATE_MEDIA_FILENAME_NON_GUESSABLE
)
from mooringlicensing.components.payments_ml.models import FeeItemStickerReplacement

from rest_framework.permissions import IsAuthenticated
from mooringlicensing.components.proposals.permissions import (
    InternalProposalPermission,
    ProposalAssessorPermission,
    ProposalApproverPermission,
)

logger = logging.getLogger(__name__)

class GetDcvOrganisations(views.APIView):
    permission_classes = [InternalProposalPermission]
    def get(self, request, format=None):
        search_term = request.GET.get('search_term', '')
        if is_internal(request): #currently only used internally, but may be acceptable for external access
            if search_term:
                data = DcvOrganisation.objects.filter(name__icontains=search_term)[:10]
                data_transform = [{'id': org.id, 'name': org.name} for org in data]
                return Response({"results": data_transform})
            return Response()
        
class GetDcvVesselRegoNos(views.APIView):
    #this can be accessed without authentication
    def get(self, request, format=None):
        search_term = request.GET.get('term', '')
        if search_term:
            current_date = datetime.now()
            dcv_admission_ids = DcvAdmissionArrival.objects.filter(
                dcv_admission__status=DcvAdmission.DCV_ADMISSION_STATUS_PAID
            ).filter(
                departure_date__gte=current_date
            ).values_list('dcv_admission__id', flat=True)
            data = DcvVessel.objects.filter(
                Q(dcv_permits__in=DcvPermit.objects.exclude(end_date=None).filter(end_date__gte=current_date)) |
                Q(dcv_admissions__in=DcvAdmission.objects.filter(id__in=dcv_admission_ids))
            ).filter(rego_no__icontains=search_term).values('id', 'rego_no', 'dcv_permits')[:10]
            data_transform = [{'id': rego['id'], 'text': rego['rego_no'], 'dcv_permits': rego['dcv_permits']} for rego in data]
            return Response({"results": data_transform})
        return Response()


class GetVessel(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        search_term = request.GET.get('search_term', '')
        page_number = request.GET.get('page_number', 1)
        items_per_page = 10

        if search_term:
            data_transform = []
            ### VesselDetails
            ml_data = VesselDetails.filtered_objects.filter(
                Q(vessel__rego_no__icontains=search_term) | 
                Q(vessel_name__icontains=search_term)
            ).values(
                'vessel__id', 
                'vessel__rego_no',
                'vessel_name'
            )
            paginator = Paginator(ml_data, items_per_page)
            try:
                current_page = paginator.page(page_number)
                my_objects = current_page.object_list
            except EmptyPage:
                logger.debug(f'VesselDetails empty')
                my_objects = []

            for vd in my_objects:
                data_transform.append({
                    'id': vd.get('vessel__id'), 
                    'rego_no': vd.get('vessel__rego_no'),
                    'text': vd.get('vessel__rego_no') + ' - ' + vd.get('vessel_name'),
                    'entity_type': 'ml',
                })

            ### DcvVessel
            dcv_data = DcvVessel.objects.filter(
                Q(rego_no__icontains=search_term) | 
                Q(vessel_name__icontains=search_term)
            ).values(
                'id', 
                'rego_no',
                'vessel_name'
            )
            paginator2 = Paginator(dcv_data, items_per_page)
            try:
                current_page2 = paginator2.page(page_number)
                my_objects2 = current_page2.object_list
            except EmptyPage:
                logger.debug(f'DcvVessel empty')
                my_objects2 = []

            for dcv in my_objects2:
                data_transform.append({
                    'id': dcv.get('id'), 
                    'rego_no': dcv.get('rego_no'),
                    'text': dcv.get('rego_no') + ' - ' + dcv.get('vessel_name'),
                    'entity_type': 'dcv',
                })

            ## order results
            data_transform.sort(key=lambda item: item.get("id"))

            return Response({
                "results": data_transform,
                "pagination": {
                    "more": current_page.has_next() or current_page2.has_next()
                }
            })
        return Response()


class GetMooring(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        search_term = request.GET.get('search_term', '')
        page_number = request.GET.get('page_number', 1)
        items_per_page = 10
        private_moorings = request.GET.get('private_moorings')

        if search_term:
            if private_moorings:
                data = Mooring.private_moorings.filter(name__icontains=search_term).values('id', 'name')
            else:
                data = Mooring.objects.filter(name__icontains=search_term).values('id', 'name')
            paginator = Paginator(data, items_per_page)
            try:
                current_page = paginator.page(page_number)
                my_objects = current_page.object_list
            except EmptyPage:
                my_objects = []
            
            data_transform = [{'id': mooring['id'], 'text': mooring['name']} for mooring in my_objects]

            return Response({
                "results": data_transform,
                "pagination": {
                    "more": current_page.has_next()
                }
            })
        return Response()


class GetMooringBySiteLicensee(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        search_term = request.GET.get('search_term', '')
        site_licensee_email = request.GET.get('site_licensee_email', '')
        page_number = request.GET.get('page_number', 1)
        items_per_page = 10
        private_moorings = request.GET.get('private_moorings')

        if search_term:
            if private_moorings:
                data = Mooring.private_moorings.filter(
                    name__icontains=search_term,
                    mooring_licence__approval__current_proposal__proposal_applicant__email=site_licensee_email
                ).values('id', 'name')
            else:
                data = Mooring.objects.filter(
                    name__icontains=search_term,
                    mooring_licence__approval__current_proposal__proposal_applicant__email=site_licensee_email
                ).values('id', 'name')
            paginator = Paginator(data, items_per_page)
            try:
                current_page = paginator.page(page_number)
                my_objects = current_page.object_list
            except EmptyPage:
                my_objects = []
            
            data_transform = [{'id': mooring['id'], 'text': mooring['name']} for mooring in my_objects]

            return Response({
                "results": data_transform,
                "pagination": {
                    "more": current_page.has_next()
                }
            })
        return Response()


class GetMooringPerBay(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        
        available_moorings = request.GET.get('available_moorings')
        vessel_details = {}
        vessel_details["vessel_length"] = request.GET.get('vessel_length')
        vessel_details["vessel_draft"] = request.GET.get('vessel_draft')
        wla_id = request.GET.get('wla_id')
        aup_id = request.GET.get('aup_id')
        search_term = request.GET.get('term', '')
        num_of_moorings_to_return = int(GlobalSettings.objects.get(key=GlobalSettings.KEY_NUMBER_OF_MOORINGS_TO_RETURN_FOR_LOOKUP).value)

        if search_term:
            if available_moorings:
                # WLA offer
                if wla_id:
                    try:
                        wla = WaitingListAllocation.objects.get(id=int(wla_id))
                    except:
                        logger.error("wla_id {} is not an integer".format(wla_id))
                        raise serializers.ValidationError("wla_id is not an integer")
                    ## restrict search results to suitable vessels
                    mooring_filter = Q(
                        Q(name__icontains=search_term) &
                        Q(vessel_size_limit__gte=wla.current_proposal.vessel_length) &
                        Q(vessel_draft_limit__gte=wla.current_proposal.vessel_draft)
                    )
                    data = Mooring.available_moorings.filter(mooring_filter, active=True).values('id', 'name', 'mooring_licence', "vessel_size_limit", "vessel_draft_limit", "vessel_weight_limit")[:num_of_moorings_to_return]
                else:
                    data = Mooring.available_moorings.filter(name__icontains=search_term, active=True).values('id', 'name', 'mooring_licence')[:num_of_moorings_to_return]

            else:
                # aup
                aup_mooring_ids = []
                if aup_id:
                    aup_mooring_ids = [moa.mooring.id for moa in AuthorisedUserPermit.objects.get(id=aup_id).mooringonapproval_set.filter(active=True)]
                if vessel_details:
                    ## restrict search results to suitable vessels
                    mooring_filter = Q(
                        Q(name__icontains=search_term) &
                        Q(vessel_size_limit__gte=vessel_details["vessel_length"]) &
                        Q(vessel_draft_limit__gte=vessel_details["vessel_draft"]) &
                        ~Q(id__in=aup_mooring_ids) &
                        Q(active=True) &
                        Q(mooring_licence__status__in=MooringLicence.STATUSES_AS_CURRENT)  # Make sure this mooring is licensed because an unlicensed mooring would never be allocated to an AU permit.
                    )
                    data = Mooring.authorised_user_moorings.filter(mooring_filter).values('id', 'name', 'mooring_licence', "vessel_size_limit", "vessel_draft_limit", "vessel_weight_limit")[:num_of_moorings_to_return]
                else:
                    data = []

            data_transform = []
            ml_qs = MooringLicence.objects
            for mooring in data:
                qs = ml_qs.none()
                if 'mooring_licence' in mooring and mooring['mooring_licence']:
                    qs = MooringLicence.objects.filter(id=mooring['mooring_licence'], status="current")

                if qs.exists() and not available_moorings:
                    data_transform.append({'id': mooring['id'], 'text': mooring['name'] + ' (licensed)'
                    , "vessel_size_limit":mooring['vessel_size_limit']
                    , "vessel_draft_limit":mooring['vessel_draft_limit']
                    , "vessel_weight_limit":mooring['vessel_weight_limit']
                    })
                elif available_moorings:
                    data_transform.append({'id': mooring['id'], 'text': mooring['name'] + ' (unlicensed)'
                    , "vessel_size_limit":mooring['vessel_size_limit']
                    , "vessel_draft_limit":mooring['vessel_draft_limit']
                    , "vessel_weight_limit":mooring['vessel_weight_limit']
                    })
            return Response({"results": data_transform})
        return Response()


class GetVesselRegoNos(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        search_term = request.GET.get('term', '')
        allow_add_new_vessel = request.GET.get('allow_add_new_vessel', 'true')
        allow_add_new_vessel = True if allow_add_new_vessel.lower() == 'true' else False
        proposal_id = request.GET.get('proposal_id', 0)
        proposal = Proposal.objects.filter(id=proposal_id).first()

        if not search_term or not proposal:
            return Response()

        if proposal.proposal_type.code == PROPOSAL_TYPE_NEW:
            # Make sure 'allow_add_new_vessel' is True when new application
            allow_add_new_vessel = True
            data = Vessel.objects.filter(rego_no__icontains=search_term).values('id', 'rego_no')[:10]
        else:
            # Amendment/Renewal
            if proposal.approval:
                existing_vessel_ids = []  # Store id of the vessel that belongs to the proposal.approval
                if proposal.approval.child_obj.code == 'ml':
                    vooas = proposal.approval.child_obj.get_current_vessel_ownership_on_approvals()
                    for vessel_ownership_on_approval in vooas:
                        existing_vessel_ids.append(vessel_ownership_on_approval.vessel_ownership.vessel.id)
                else:
                    v_details = proposal.approval.child_obj.current_proposal.latest_vessel_details
                    v_ownership = proposal.approval.child_obj.current_proposal.vessel_ownership
                    if v_details and not v_ownership.end_date:
                        existing_vessel_ids.append(v_details.vessel.id)

                if allow_add_new_vessel:
                    # Customer wants to add a new vessel
                    # Return all the vessels except existing vessels that belongs to the proposal.approval
                    data = Vessel.objects.filter(rego_no__icontains=search_term).exclude(id__in=existing_vessel_ids).values('id', 'rego_no')[:10]
                else:
                    # Customer wants to edit an existing vessel which belongs to the proposal.approval
                    # Return only existing vessels that belong to the proposal.approval
                    data = Vessel.objects.filter(rego_no__icontains=search_term, id__in=existing_vessel_ids).values('id', 'rego_no')[:10]
            else:
                data = []

        data_transform = [{'id': rego['id'], 'text': rego['rego_no']} for rego in data]
        return Response({"results": data_transform})


class GetCompanyNames(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        search_term = request.GET.get('term', '')
        if search_term:
            data = Company.objects.filter(name__icontains=search_term).values('id', 'name')[:10]
            data_transform = []
            data_transform = [{'id': company['id'], 'text': company['name']} for company in data] 
            return Response({"results": data_transform})
        return Response()


class GetApplicationTypeDescriptions(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        data = cache.get('application_type_descriptions')
        if not data:
            cache.set('application_type_descriptions',Proposal.application_type_descriptions(), settings.LOV_CACHE_TIMEOUT)
            data = cache.get('application_type_descriptions')
        return Response(data)


class GetStickerReplacementFeeItem(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        
        current_datetime = datetime.now(pytz.timezone(TIME_ZONE))
        fee_item = FeeItemStickerReplacement.get_fee_item_by_date(current_datetime.date())

        return Response({'amount': fee_item.amount, 'incur_gst': fee_item.incur_gst})


class GetPaymentSystemId(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        return Response({'payment_system_id': PAYMENT_SYSTEM_ID})


class GetApplicationTypeDict(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        apply_page = request.GET.get('apply_page', 'false')
        apply_page = True if apply_page.lower() in ['true', 'yes', 'y', ] else False
        data = cache.get('application_type_dict')
        if not data:
            cache.set('application_type_dict',Proposal.application_types_dict(apply_page=apply_page), settings.LOV_CACHE_TIMEOUT)
            data = cache.get('application_type_dict')
        return Response(data)


class GetApplicationCategoryDict(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        apply_page = request.GET.get('apply_page', 'false')
        apply_page = True if apply_page.lower() in ['true', 'yes', 'y', ] else False
        data = cache.get('application_category_dict')
        if not data:
            cache.set('application_category_dict',Proposal.application_categories_dict(apply_page=apply_page), settings.LOV_CACHE_TIMEOUT)
            data = cache.get('application_category_dict')
        return Response(data)


class GetApplicationStatusesDict(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        data = {}
        if not cache.get('application_internal_statuses_dict') or not cache.get('application_external_statuses_dict'):
            cache.set('application_internal_statuses_dict',[{'code': i[0], 'description': i[1]} 
                for i in Proposal.PROCESSING_STATUS_CHOICES], settings.LOV_CACHE_TIMEOUT)
            cache.set('application_external_statuses_dict',[{'code': i[0], 'description': i[1]} 
                for i in Proposal.CUSTOMER_STATUS_CHOICES if i[0] != 'discarded'], settings.LOV_CACHE_TIMEOUT)
        data['external_statuses'] = cache.get('application_external_statuses_dict')
        data['internal_statuses'] = cache.get('application_internal_statuses_dict')
        return Response(data)


class GetVesselTypesDict(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        data = cache.get('vessel_type_dict')
        if not data:
            cache.set('vessel_type_dict',[{'code': i[0], 'description': i[1]} for i in VESSEL_TYPES], settings.LOV_CACHE_TIMEOUT)
            data = cache.get('vessel_type_dict')
        return Response(data)


class GetInsuranceChoicesDict(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        data = cache.get('insurance_choice_dict')
        if not data:
            cache.set('insurance_choice_dict',[{'code': i[0], 'description': i[1]} for i in INSURANCE_CHOICES], settings.LOV_CACHE_TIMEOUT)
            data = cache.get('insurance_choice_dict')
        return Response(data)


class GetMooringStatusesDict(views.APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response(['Unlicensed', 'Licensed', 'Licence application'])
    

class ProposalFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):

        total_count = queryset.count()
        level = request.GET.get('level', 'external')  # Check where the request comes from
        filter_query = Q()

        try:
            super_queryset = super(ProposalFilterBackend, self).filter_queryset(request, queryset, view).distinct()
        except Exception as e:
            logger.exception(f'Failed to filter the queryset.  Error: [{e}]')

        search_text = request.GET.get('search[value]')
        if search_text:
            #the search conducted by the superclass only accomodates the ProposalApplicant users
            #this misses any new draft proposals, which do not yet have a ProposalApplicant record assigned - so we will do that here
            system_user_ids = list(SystemUser.objects.annotate(full_name=Concat('legal_first_name',Value(" "),'legal_last_name',output_field=CharField()))
            .filter(
                Q(legal_first_name__icontains=search_text) | Q(legal_last_name__icontains=search_text) | Q(email__icontains=search_text) | Q(full_name__icontains=search_text)
            ).values_list("ledger_id", flat=True))
            #the search also does not accomodate combining first names and last names even with ProposalApplicant - so we will also do that here
            proposal_applicant_proposals = list(ProposalApplicant.objects.annotate(full_name=Concat('first_name',Value(" "),'last_name',output_field=CharField()))
            .filter(
                Q(first_name__icontains=search_text) | Q(last_name__icontains=search_text) | Q(email__icontains=search_text) | Q(full_name__icontains=search_text)
            ).values_list("proposal_id", flat=True))
            queryset = queryset.filter(Q(id__in=proposal_applicant_proposals)|Q(submitter__in=system_user_ids))
            queryset = queryset.distinct() | super_queryset    

        mla_list = MooringLicenceApplication.objects.all()
        aua_list = AuthorisedUserApplication.objects.all()
        aaa_list = AnnualAdmissionApplication.objects.all()
        wla_list = WaitingListApplication.objects.all()

        filter_application_type = request.GET.get('filter_application_type')
        if filter_application_type and not filter_application_type.lower() == 'all':
            if filter_application_type == 'mla':
                filter_query &= Q(id__in=mla_list)
            elif filter_application_type == 'aua':
                filter_query &= Q(id__in=aua_list)
            elif filter_application_type == 'aaa':
                filter_query &= Q(id__in=aaa_list)
            elif filter_application_type == 'wla':
                filter_query &= Q(id__in=wla_list)

        filter_application_category = request.GET.get('filter_application_category')
        if filter_application_category and not filter_application_category.lower() == 'all':
            if filter_application_category == 'new':
                filter_query &= Q(proposal_type__code=settings.PROPOSAL_TYPE_NEW)
            elif filter_application_category == 'amendment':
                filter_query &= Q(proposal_type__code=settings.PROPOSAL_TYPE_AMENDMENT)
            elif filter_application_category == 'renewal':
                filter_query &= Q(proposal_type__code=settings.PROPOSAL_TYPE_RENEWAL)
            elif filter_application_category == 'swap_moorings':
                filter_query &= Q(proposal_type__code=settings.PROPOSAL_TYPE_SWAP_MOORINGS)            

        filter_application_status = request.GET.get('filter_application_status')
        if filter_application_status and not filter_application_status.lower() == 'all':
            if level == 'internal':
                filter_query &= Q(processing_status=filter_application_status)
            else:
                filter_query &= Q(customer_status=filter_application_status)

        filter_applicant_id = request.GET.get('filter_applicant')
        if filter_applicant_id and not filter_applicant_id.lower() == 'all':
            filter_query &= Q(proposal_applicant__email_user_id=filter_applicant_id)

        # Filter by endorsement
        filter_by_endorsement = request.GET.get('filter_by_endorsement', 'false')
        filter_by_endorsement = True if filter_by_endorsement.lower() in ['true', 'yes', 't', 'y',] else False
        if filter_by_endorsement:
            filter_query &= (Q(site_licensee_mooring_request__site_licensee_email__iexact=request.user.email,site_licensee_mooring_request__enabled=True))

        queryset = queryset.filter(filter_query)

        fields = self.get_fields(request)
        ordering = self.get_ordering(request, view, fields)
        
        #special handling for ordering by applicant
        special_ordering = False
        APPLICANT = 'proposal_applicant'
        REVERSE_APPLICANT = '-proposal_applicant'
        if APPLICANT in ordering:
            special_ordering = True
            ordering.remove(APPLICANT)
            queryset = queryset.annotate(proposal_applicant_full_name=Concat('proposal_applicant__first_name',Value(" "),'proposal_applicant__last_name'))
            queryset = queryset.order_by(APPLICANT+"_full_name")
        if REVERSE_APPLICANT in ordering:
            special_ordering = True
            ordering.remove(REVERSE_APPLICANT)
            queryset = queryset.annotate(proposal_applicant_full_name=Concat('proposal_applicant__first_name',Value(" "),'proposal_applicant__last_name'))
            queryset = queryset.order_by(REVERSE_APPLICANT+"_full_name")

        if len(ordering):
            queryset = queryset.order_by(*ordering)
        elif not special_ordering:
            queryset = queryset.order_by('-id')
        
        total_count = queryset.count()
        setattr(view, '_datatables_filtered_count', total_count)
        return queryset

class ProposalSiteLicenseeMooringRequestFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):

        total_count = queryset.count()
        filter_query = Q()

        try:
            super_queryset = super(ProposalSiteLicenseeMooringRequestFilterBackend, self).filter_queryset(request, queryset, view).distinct()
        except Exception as e:
            logger.exception(f'Failed to filter the queryset.  Error: [{e}]')

        search_text = request.GET.get('search[value]')
        if search_text:

            system_user_ids = list(SystemUser.objects.annotate(full_name=Concat('legal_first_name',Value(" "),'legal_last_name',output_field=CharField()))
            .filter(
                Q(legal_first_name__icontains=search_text) | Q(legal_last_name__icontains=search_text) | Q(email__icontains=search_text) | Q(full_name__icontains=search_text)
            ).values_list("ledger_id", flat=True))

            proposal_applicant_proposals = list(ProposalApplicant.objects.annotate(full_name=Concat('first_name',Value(" "),'last_name',output_field=CharField()))
            .filter(
                Q(first_name__icontains=search_text) | Q(last_name__icontains=search_text) | Q(email__icontains=search_text) | Q(full_name__icontains=search_text)
            ).values_list("proposal_id", flat=True))

            queryset = queryset.filter(Q(proposal__id__in=proposal_applicant_proposals)|Q(proposal__submitter__in=system_user_ids))
            queryset = queryset.distinct() | super_queryset    

        queryset = queryset.filter(filter_query)

        fields = self.get_fields(request)
        ordering = self.get_ordering(request, view, fields)
        
        #special handling for ordering by applicant
        special_ordering = False
        APPLICANT = 'proposal__proposal_applicant'
        REVERSE_APPLICANT = '-proposal__proposal_applicant'
        if APPLICANT in ordering:
            special_ordering = True
            ordering.remove(APPLICANT)
            queryset = queryset.annotate(proposal__proposal_applicant_full_name=Concat('proposal__proposal_applicant__first_name',Value(" "),'proposal__proposal_applicant__last_name'))
            queryset = queryset.order_by(APPLICANT+"_full_name")
        if REVERSE_APPLICANT in ordering:
            special_ordering = True
            ordering.remove(REVERSE_APPLICANT)
            queryset = queryset.annotate(proposal__proposal_applicant_full_name=Concat('proposal__proposal_applicant__first_name',Value(" "),'proposal__proposal_applicant__last_name'))
            queryset = queryset.order_by(REVERSE_APPLICANT+"_full_name")

        if len(ordering):
            queryset = queryset.order_by(*ordering)
        elif not special_ordering:
            queryset = queryset.order_by('-id')
        
        total_count = queryset.count()
        setattr(view, '_datatables_filtered_count', total_count)
        return queryset

class SiteLicenseeMooringRequestPaginatedViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = (ProposalSiteLicenseeMooringRequestFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    queryset = ProposalSiteLicenseeMooringRequest.objects.none()
    serializer_class = ListProposalSiteLicenseeMooringRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        request_user = self.request.user
        if is_internal(self.request):
            return ProposalSiteLicenseeMooringRequest.objects.all()
        elif is_customer(self.request):
            return ProposalSiteLicenseeMooringRequest.objects.filter(
                site_licensee_email=request_user.email, 
                mooring__mooring_licence__approval__status="current",
                mooring__mooring_licence__approval__current_proposal__proposal_applicant__email=request_user.email,
                enabled=True)
        return ProposalSiteLicenseeMooringRequest.objects.none()
         

class ProposalPaginatedViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = (ProposalFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    queryset = Proposal.objects.none()
    serializer_class = ListProposalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        request_user = self.request.user
        all = Proposal.objects.all()

        target_email_user_id = int(self.request.GET.get('target_email_user_id', 0))

        if is_internal(self.request):
            if target_email_user_id:
                # Internal user may be accessing here via search person result. 
                target_user = EmailUser.objects.get(id=target_email_user_id)

                #de-duplicate ids with distinct, but rebuild qs so there are no issues with alternative order by statements provided by filter backend
                all_ids = all.filter(Q(proposal_applicant__email_user_id=target_user.id) | 
                        Q(site_licensee_mooring_request__site_licensee_email=target_user.email,site_licensee_mooring_request__enabled=True)).distinct("id").values_list("id",flat=True)
                all = all.filter(id__in=list(all_ids))
            return all
        elif is_customer(self.request):
            qs = all.filter(Q(proposal_applicant__email_user_id=request_user.id)).exclude(customer_status='discarded')
            return qs
        return Proposal.objects.none()


class AnnualAdmissionApplicationViewSet(viewsets.GenericViewSet):
    queryset = AnnualAdmissionApplication.objects.none()
    serializer_class = ProposalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = AnnualAdmissionApplication.objects.all()
            return qs
        elif is_customer(self.request):
            queryset = AnnualAdmissionApplication.objects.filter(proposal_applicant__email_user_id=user.id)
            return queryset
        return AnnualAdmissionApplication.objects.none()

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            try:
                system_user = SystemUser.objects.get(ledger_id=request.user)
            except:
                raise serializers.ValidationError("system user does not exist")
            
            try:
                proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)
            except:
                raise serializers.ValidationError("proposal type does not exist")

            obj = AnnualAdmissionApplication.objects.create(
                submitter=request.user.id,
                proposal_type=proposal_type
            )
            logger.info(f'Annual Admission Application: [{obj}] has been created by the user: [{request.user}].')
            obj.log_user_action(f'Annual Admission Application: {obj.lodgement_number} has been created.', request)

            serialized_obj = ProposalSerializer(obj.proposal)
            
            create_proposal_applicant(obj, system_user)

            return Response(serialized_obj.data)


class InternalAnnualAdmissionApplicationViewSet(viewsets.GenericViewSet):
    queryset = AnnualAdmissionApplication.objects.none()
    serializer_class = ProposalSerializer
    permission_classes = [InternalProposalPermission]

    def get_queryset(self):
        if is_internal(self.request):
            qs = AnnualAdmissionApplication.objects.all()
            return qs
        return AnnualAdmissionApplication.objects.none()

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            if is_internal(request):

                applicant_system_id = request.data.get("applicant_system_id")
                no_email_notifications = request.data.get("no_emails", False)
                if not applicant_system_id:
                    raise serializers.ValidationError("no system user id provided")

                try:
                    system_user = SystemUser.objects.get(id=applicant_system_id)
                except:
                    raise serializers.ValidationError("system user does not exist")

                try:
                    proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)
                except:
                    raise serializers.ValidationError("proposal type does not exist")

                obj = AnnualAdmissionApplication.objects.create(
                    submitter=request.user.id,
                    no_email_notifications=no_email_notifications,
                    proposal_type=proposal_type
                )

                logger.info(f'Annual Admission Application: [{obj}] has been created by the user: [{request.user}].')

                obj.log_user_action(f'Annual Admission Application: {obj.lodgement_number} has been created.', request)

                serialized_obj = ProposalSerializer(obj.proposal)

                create_proposal_applicant(obj, system_user)

                return Response(serialized_obj.data)
            raise serializers.ValidationError("not authorised to create application as an internal user")
        

class AuthorisedUserApplicationViewSet(viewsets.GenericViewSet):
    queryset = AuthorisedUserApplication.objects.none()
    serializer_class = ProposalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = AuthorisedUserApplication.objects.all()
            return qs
        elif is_customer(self.request):
            queryset = AuthorisedUserApplication.objects.filter(proposal_applicant__email_user_id=user.id)
            return queryset
        logger.warn("User is neither customer nor internal user: {} <{}>".format(user.get_full_name(), user.email))
        return AuthorisedUserApplication.objects.none()

    def create(self, request, *args, **kwargs):
        try:
            system_user = SystemUser.objects.get(ledger_id=request.user)
        except:
            raise serializers.ValidationError("system user does not exist")
        
        try:
            proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)
        except:
            raise serializers.ValidationError("proposal type does not exist")

        obj = AuthorisedUserApplication.objects.create(
                submitter=request.user.id,
                proposal_type=proposal_type
                )
        logger.info(f'Authorised User Permit Application: [{obj}] has been created by the user: [{request.user}].')
        obj.log_user_action(f'Authorised User Permit Application: {obj.lodgement_number} has been created.', request)

        create_proposal_applicant(obj, system_user)

        serialized_obj = ProposalSerializer(obj.proposal)
        return Response(serialized_obj.data)
    
        
class InternalAuthorisedUserApplicationViewSet(viewsets.GenericViewSet):
    queryset = AuthorisedUserApplication.objects.none()
    serializer_class = ProposalSerializer
    permission_classes = [InternalProposalPermission]

    def get_queryset(self):
        if is_internal(self.request):
            qs = AuthorisedUserApplication.objects.all()
            return qs
        return AuthorisedUserApplication.objects.none()

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            if is_internal(request):

                applicant_system_id = request.data.get("applicant_system_id")
                no_email_notifications = request.data.get("no_emails", False)
                if not applicant_system_id:
                    raise serializers.ValidationError("no system user id provided")

                try:
                    system_user = SystemUser.objects.get(id=applicant_system_id)
                except:
                    raise serializers.ValidationError("system user does not exist")
                
                try:
                    proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)
                except:
                    raise serializers.ValidationError("proposal type does not exist")

                obj = AuthorisedUserApplication.objects.create(
                    submitter=request.user.id,
                    no_email_notifications=no_email_notifications,
                    proposal_type=proposal_type
                )
                logger.info(f'Authorised User Permit Application: [{obj}] has been created by the user: [{request.user}].')
                obj.log_user_action(f'Authorised User Permit Application: {obj.lodgement_number} has been created.', request)

                create_proposal_applicant(obj, system_user)

                serialized_obj = ProposalSerializer(obj.proposal)
                return Response(serialized_obj.data)
            raise serializers.ValidationError("not authorised to create application as an internal user")


class MooringLicenceApplicationViewSet(viewsets.GenericViewSet):
    queryset = MooringLicenceApplication.objects.none()
    serializer_class = ProposalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = MooringLicenceApplication.objects.all()
            return qs
        elif is_customer(self.request):
            queryset = MooringLicenceApplication.objects.filter(proposal_applicant__email_user_id=user.id)
            return queryset
        return MooringLicenceApplication.objects.none()


class WaitingListApplicationViewSet(viewsets.GenericViewSet):
    queryset = WaitingListApplication.objects.none()
    serializer_class = ProposalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = WaitingListApplication.objects.all()
            return qs
        elif is_customer(self.request):
            queryset = WaitingListApplication.objects.filter(proposal_applicant__email_user_id=user.id)
            return queryset
        return WaitingListApplication.objects.none()

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            try:
                system_user = SystemUser.objects.get(ledger_id=request.user)
            except:
                raise serializers.ValidationError("system user does not exist")
            
            try:
                proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)
            except:
                raise serializers.ValidationError("proposal type does not exist")

            wla_allowed = get_wla_allowed(request.user.id)
            if not wla_allowed:
                raise serializers.ValidationError("user not permitted to create WLA at this time")

            obj = WaitingListApplication.objects.create(
                    submitter=request.user.id,
                    proposal_type=proposal_type
                    )

            logger.info(f'Waiting List Application: [{obj}] has been created by the user: [{request.user}].')
            obj.log_user_action(f'Waiting List Application: {obj.lodgement_number} has been created.', request)

            create_proposal_applicant(obj, system_user)

            serialized_obj = ProposalSerializer(obj.proposal)
            return Response(serialized_obj.data)


class InternalWaitingListApplicationViewSet(viewsets.GenericViewSet):
    queryset = WaitingListApplication.objects.none()
    serializer_class = ProposalSerializer
    lookup_field = 'id'
    permission_classes = [InternalProposalPermission]

    def get_queryset(self):
        if is_internal(self.request):
            qs = WaitingListApplication.objects.all()
            return qs
        return WaitingListApplication.objects.none()

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            if is_internal(request):

                applicant_system_id = request.data.get("applicant_system_id")
                no_email_notifications = request.data.get("no_emails", False)
                if not applicant_system_id:
                    raise serializers.ValidationError("no system user id provided")

                try:
                    system_user = SystemUser.objects.get(id=applicant_system_id)
                except:
                    raise serializers.ValidationError("system user does not exist")
                
                try:
                    proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)
                except:
                    raise serializers.ValidationError("proposal type does not exist")

                if not system_user.ledger_id:
                    raise serializers.ValidationError("system user does not have valid corresponding email user")

                wla_allowed = get_wla_allowed(system_user.ledger_id.id)
                if not wla_allowed:
                    raise serializers.ValidationError("user not permitted to create WLA at this time")

                obj = WaitingListApplication.objects.create(
                    submitter=request.user.id,
                    no_email_notifications=no_email_notifications,
                    proposal_type=proposal_type
                )

                logger.info(f'Waiting List Application: [{obj}] has been created by the user: [{request.user}].')
                obj.log_user_action(f'Waiting List Application: {obj.lodgement_number} has been created.', request)

                create_proposal_applicant(obj, system_user)

                serialized_obj = ProposalSerializer(obj.proposal)
                return Response(serialized_obj.data)
            raise serializers.ValidationError("not authorised to create application as an internal user")


class ProposalByUuidViewSet(viewsets.GenericViewSet):
    queryset = Proposal.objects.none()
    permission_classes = [IsAuthenticated]

    def get_object(self):
        uuid = self.kwargs.get('pk')
        if is_internal(self.request):
            qs = MooringLicenceApplication.objects.distinct('id')
            return qs.get(uuid=uuid)
        else:
            qs = MooringLicenceApplication.objects.filter(proposal_applicant__email_user_id=self.request.user.id).distinct('id')
            return qs.get(uuid=uuid)

    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def mooring_report_document(self, request, *args, **kwargs):
        instance = self.get_object()
        
        if ((
            instance.processing_status == Proposal.PROCESSING_STATUS_DRAFT or
            instance.processing_status == Proposal.PROCESSING_STATUS_AWAITING_DOCUMENTS
            ) or is_internal(request)):
            action = request.data.get('action')
            if action == 'delete':
                document_id = request.data.get('document_id')
                document = MooringReportDocument.objects.filter(
                    proposalmooringreportdocument__proposal=instance,
                    id=document_id,
                )
                if document.first()._file and os.path.isfile(document.first()._file.path):
                    os.remove(document.first()._file.path)
                if document.first():
                    original_file_name = document.first().name
                    document.first().delete()
                    logger.info(f'MooringReportDocument file: {original_file_name} has been deleted.')
                    instance.log_user_action(f'Mooring report document file deleted.', request)

            elif action == 'save':
                filename = request.data.get('filename')
                _file = request.data.get('_file')
                filepath = pathlib.Path(filename)
                document = MooringReportDocument.objects.create(
                    name=filepath.stem + filepath.suffix
                )
                instance.mooring_report_documents.add(document)
                document._file = _file
                document.save()
                
                logger.info(f'MooringReportDocument file: {filename} has been saved as {document._file.url}')
                instance.log_user_action(f'Mooring report document file saved.', request)

        docs_in_limbo = instance.mooring_report_documents.all()  # Files uploaded when vessel_ownership is unknown
        all_the_docs = docs_in_limbo

        returned_file_data = construct_dict_from_docs(all_the_docs)

        return Response({'filedata': returned_file_data})

    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def process_written_proof_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='written_proof_document')
        if returned_data:
            return Response(returned_data)
        else:
            return Response()

    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def process_signed_licence_agreement_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='signed_licence_agreement_document')
        if returned_data:
            return Response(returned_data)
        else:
            return Response()

    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def process_proof_of_identity_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='proof_of_identity_document')
        if returned_data:
            return Response(returned_data)
        else:
            return Response()

    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def submit(self, request, *args, **kwargs):
        instance = self.get_object()
        logger.info(f'Proposal: [{instance}] has been submitted with UUID...')

        is_authorised_to_submit_documents(request, instance)

        errors = []
        if not instance.mooring_report_documents.count():
            errors.append('Copy of current mooring report')
        if not instance.written_proof_documents.count():
            errors.append('Proof of finalised ownership of mooring apparatus')
        if not instance.signed_licence_agreement_documents.count():
            errors.append('Signed licence agreement')
        if not instance.proof_of_identity_documents.count():
            errors.append('Proof of identity')

        if errors:
            errors.insert(0, 'Please attach:')
            raise serializers.ValidationError(errors)

        instance.process_after_submit_other_documents(request)

        return Response({"internal_submission":is_internal(request)})


class ProposalViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = Proposal.objects.none()
    serializer_class = ProposalSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if not self.kwargs.get('id').isnumeric():
            # Endorser is accessing this proposal.  We don't want to send all the proposal data.
            return ProposalForEndorserSerializer
        return super(ProposalViewSet, self).get_serializer_class()

    def get_object(self):
        id = self.kwargs.get('id')
        logger.info(f'Getting proposal in the ProposalViewSet by the ID: [{id}]...')

        if id.isnumeric():
            obj = super(ProposalViewSet, self).get_object()
        else:
            # When AUP holder accesses this proposal for endorsement 
            uuid = self.kwargs.get('id')
            obj = AuthorisedUserApplication.objects.get(uuid=uuid)
            obj = obj.proposal
        return obj

    def get_queryset(self):
        request_user = self.request.user
        if is_internal(self.request):
            qs = Proposal.objects.all()
            return qs
        elif is_customer(self.request):
            queryset = Proposal.objects.filter(
                Q(proposal_applicant__email_user_id=request_user.id)
            )
            # For the endoser to view the endorsee's proposal
            if 'uuid' in self.request.query_params:
                uuid = self.request.query_params.get('uuid', '')
                if uuid:
                    au_obj = AuthorisedUserApplication.objects.filter(uuid=uuid)  # ML also has a uuid field.
                    if au_obj:
                        pro = Proposal.objects.filter(id=au_obj.first().id)
                        # Add the above proposal to the queryset the accessing user can access to
                        queryset = queryset | pro
            return queryset
        return Proposal.objects.none()

    def internal_serializer_class(self):
       try:
           return InternalProposalSerializer
       except serializers.ValidationError:
           print(traceback.print_exc())
           raise
       except ValidationError as e:
           if hasattr(e,'error_dict'):
               raise serializers.ValidationError(repr(e.error_dict))
           else:
               if hasattr(e,'message'):
                   raise serializers.ValidationError(e.message)
       except Exception as e:
           print(traceback.print_exc())
           raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def bypass_payment(self, request, *args, **kwargs):
        if is_internal(request) and is_system_admin(request):
            instance = self.get_object()
            
            instance.bypass_payment(request)

            return Response()
        else:
            raise serializers.ValidationError("User not authorised to bypass payment")

    @detail_route(methods=['PUT'], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def reinstate_wl_allocation(self, request, *args, **kwargs):
        instance = self.get_object()
        if is_internal(request) and instance.child_obj.code == MooringLicenceApplication.code and instance.processing_status in [Proposal.PROCESSING_STATUS_DISCARDED,]:
            # Internal user is accessing
            # Proposal is ML application and the status of it is 'discarded'
            wlallocation = instance.child_obj.reinstate_wl_allocation(request)
            return Response({'lodgement_number': wlallocation.lodgement_number})
        else:
            msg = f'This application: [{instance}] does not meet the conditions to put the original WLAllocation to the waiting list queue.'
            raise serializers.ValidationError(msg)

    @detail_route(methods=['POST'], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def change_applicant(self, request, *args, **kwargs):
        if is_internal(request):

            applicant_system_id = request.data.get("applicant_system_id")
            if not applicant_system_id:
                raise serializers.ValidationError("no system user id provided")

            instance = self.get_object()
            try:
                applicant = instance.proposal_applicant
            except:
                raise serializers.ValidationError("proposal has no applicant")
            
            try:
                system_user = SystemUser.objects.get(id=applicant_system_id)
            except:
                raise serializers.ValidationError("system user does not exist")
            
            if (system_user.ledger_id and applicant.email_user_id == system_user.ledger_id.id):
                raise serializers.ValidationError("provided system user id already applicant of this proposal")

            #check proposal processing status - only proposals in draft can have the applicant changed
            if instance.processing_status != Proposal.PROCESSING_STATUS_DRAFT:
                raise serializers.ValidationError("only proposals in draft can have the applicant changed")

            #check proposal type - only new proposals can have the applicant changed
            if instance.proposal_type and instance.proposal_type.code != "new":
                raise serializers.ValidationError("amendments and renewals cannot have the applicant changed")

            #check application type - MLA proposals cannot have the applicant changed
            if instance.application_type_code == "mla":
                raise serializers.ValidationError("mooring license applications cannot have the applicant changed")

            #if the proposal is a WLA check the user - users cannot have multiple new WLAs
            if instance.application_type_code == "wla" and not get_wla_allowed(system_user.ledger_id.id):
                raise serializers.ValidationError("selected applicant cannot be assigned to waiting list application")

            #run the applicant change
            change_proposal_applicant(applicant, system_user)

            instance.log_user_action(f'Proposal: {instance} applicant changed to {instance.proposal_applicant.get_full_name()}.', request)

            return Response({"applicant_system_id": applicant_system_id})
        else:
            raise serializers.ValidationError("user not authorised to change applicant")
        
    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def vessel_rego_document(self, request, *args, **kwargs):
        instance = self.get_object()

        if (instance.processing_status == Proposal.PROCESSING_STATUS_DRAFT or instance.has_assessor_mode(request.user)):
            action = request.data.get('action')
            if action == 'delete':
                document_id = request.data.get('document_id')
                try:
                    document = VesselRegistrationDocument.objects.get(
                            proposal=instance,
                            id=document_id,
                            can_delete=True,
                    )
                except:
                    raise serializers.ValidationError("Vessel Registration Document can't be deleted")
                if document._file and os.path.isfile(document._file.path):
                    os.remove(document._file.path)
                if document:
                    original_file_name = document.original_file_name
                    original_file_ext = document.original_file_ext
                    document.delete()
                    logger.info(f'VesselRegistrationDocument file: {original_file_name}{original_file_ext} has been deleted.')
                    instance.log_user_action(f'Vessel registration document file deleted.', request)
            elif action == 'save':
                filename = request.data.get('filename')
                _file = request.data.get('_file')

                filepath = pathlib.Path(filename)
                original_file_name = filepath.stem
                original_file_ext = filepath.suffix

                # Calculate a new unique filename
                if MAKE_PRIVATE_MEDIA_FILENAME_NON_GUESSABLE:
                    unique_id = uuid.uuid4()
                    new_filename = unique_id.hex + original_file_ext
                else:
                    new_filename = original_file_name + original_file_ext

                document = VesselRegistrationDocument.objects.create(
                    proposal=instance,
                    name=filepath.stem + filepath.suffix,
                    original_file_name=original_file_name,
                    original_file_ext=original_file_ext,
                )
                document._file.save(new_filename, ContentFile(_file.read()), save=False)
                document.save()

                logger.info(f'VesselRegistrationDocument file: {filename} has been saved as {document._file.url}')
                instance.log_user_action(f'Vessel registration document file saved.', request)

        docs_in_limbo = instance.temp_vessel_registration_documents.all()  # Files uploaded when vessel_ownership is unknown
        docs = instance.vessel_ownership.vessel_registration_documents.all() if instance.vessel_ownership else VesselRegistrationDocument.objects.none()
        all_the_docs = docs_in_limbo | docs  # Merge two querysets

        returned_file_data = construct_dict_from_docs(all_the_docs)

        return Response({'filedata': returned_file_data})


    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def electoral_roll_document(self, request, *args, **kwargs):
        instance = self.get_object()

        if (instance.processing_status == Proposal.PROCESSING_STATUS_DRAFT or instance.has_assessor_mode(request.user)):
            action = request.data.get('action')
            if action == 'delete':
                document_id = request.data.get('document_id')
                document = ElectoralRollDocument.objects.get(
                    proposal=instance,
                    id=document_id,
                )
                if document._file and os.path.isfile(document._file.path):
                    os.remove(document._file.path)
                if document:
                    original_file_name = document.name
                    document.delete()
                    logger.info(f'ElectoralRollDocument file: {original_file_name} has been deleted.')
                    instance.log_user_action(f'Electoral roll document file deleted.', request)
            elif action == 'save':
                filename = request.data.get('filename')
                _file = request.data.get('_file')

                filepath = pathlib.Path(filename)

                # Calculate a new unique filename
                if MAKE_PRIVATE_MEDIA_FILENAME_NON_GUESSABLE:
                    unique_id = uuid.uuid4()
                    new_filename = unique_id.hex + filepath.suffix
                else:
                    new_filename = filepath.stem + filepath.suffix

                document = ElectoralRollDocument.objects.create(
                    proposal=instance,
                    name=filepath.stem + filepath.suffix
                )
                document._file.save(new_filename, ContentFile(_file.read()), save=False)
                document.save()

                logger.info(f'ElectoralRollDocument file: {filename} has been saved as {document._file.url}')
                instance.log_user_action(f'Electoral roll document file saved.', request)

        docs_in_limbo = instance.electoral_roll_documents.all()  # Files uploaded when vessel_ownership is unknown
        all_the_docs = docs_in_limbo

        returned_file_data = construct_dict_from_docs(all_the_docs)

        return Response({'filedata': returned_file_data})

    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def hull_identification_number_document(self, request, *args, **kwargs):
        instance = self.get_object()

        if (instance.processing_status == Proposal.PROCESSING_STATUS_DRAFT or instance.has_assessor_mode(request.user)):
            action = request.data.get('action')
            if action == 'delete':
                document_id = request.data.get('document_id')
                try:
                    document = HullIdentificationNumberDocument.objects.get(
                            proposal=instance,
                            id=document_id,
                            can_delete=True,
                    )
                except:
                    raise serializers.ValidationError("Hull Identification Number Document can't be deleted")
                
                if document._file and os.path.isfile(document._file.path):
                    os.remove(document._file.path)
                if document:
                    original_file_name = document.name
                    document.delete()
                    logger.info(f'HullIdentificationNumberDocument file: {original_file_name} has been deleted.')
                    instance.log_user_action(f'Hull identification number document file deleted.', request)
            elif action == 'save':
                filename = request.data.get('filename')
                _file = request.data.get('_file')

                filepath = pathlib.Path(filename)

                # Calculate a new unique filename
                if MAKE_PRIVATE_MEDIA_FILENAME_NON_GUESSABLE:
                    unique_id = uuid.uuid4()
                    new_filename = unique_id.hex + filepath.suffix
                else:
                    new_filename = filepath.stem + filepath.suffix

                document = HullIdentificationNumberDocument.objects.create(
                    proposal=instance,
                    name=filepath.stem + filepath.suffix
                )

                document._file.save(new_filename, ContentFile(_file.read()), save=False)
                document.save()
                instance.log_user_action(f'Hull identification number document file saved.', request)

                logger.info(f'HullIdentificationNumberDocument file: {filename} has been saved as {document._file.url}')

        # retrieve temporarily uploaded documents when the proposal is 'draft'
        docs_in_limbo = instance.hull_identification_number_documents.all()  # Files uploaded when vessel_ownership is unknown
        all_the_docs = docs_in_limbo

        returned_file_data = construct_dict_from_docs(all_the_docs)

        return Response({'filedata': returned_file_data})

    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def insurance_certificate_document(self, request, *args, **kwargs):
        instance = self.get_object()

        if (instance.processing_status == Proposal.PROCESSING_STATUS_DRAFT or instance.has_assessor_mode(request.user)):
            action = request.data.get('action')
            if action == 'delete':
                document_id = request.data.get('document_id')
                document = InsuranceCertificateDocument.objects.get(
                    proposal=instance,
                    id=document_id,
                )
                if document._file and os.path.isfile(document._file.path):
                    os.remove(document._file.path)
                if document:
                    original_file_name = document.name
                    document.delete()
                    logger.info(f'InsuranceCertificateDocument file: {original_file_name} has been deleted.')
                    instance.log_user_action(f'Insurance certificate document file deleted.', request)
            elif action == 'save':
                filename = request.data.get('filename')
                _file = request.data.get('_file')

                filepath = pathlib.Path(filename)

                # Calculate a new unique filename
                if MAKE_PRIVATE_MEDIA_FILENAME_NON_GUESSABLE:
                    unique_id = uuid.uuid4()
                    new_filename = unique_id.hex + filepath.suffix
                else:
                    new_filename = filepath.stem + filepath.suffix

                document = InsuranceCertificateDocument.objects.create(
                    proposal=instance,
                    name=filepath.stem + filepath.suffix
                )
                document._file.save(new_filename, ContentFile(_file.read()), save=False)
                document.save()

                logger.info(f'InsuranceCertificateDocument file: {filename} has been saved as {document._file.url}')
                instance.log_user_action(f'Insurance certificate document file saved.', request)

        # retrieve temporarily uploaded documents when the proposal is 'draft'
        docs_in_limbo = instance.insurance_certificate_documents.all()  # Files uploaded when vessel_ownership is unknown
        all_the_docs = docs_in_limbo

        returned_file_data = construct_dict_from_docs(all_the_docs)

        return Response({'filedata': returned_file_data})

    @detail_route(methods=['GET',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def action_log(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            qs = instance.action_logs.all()
            serializer = ProposalUserActionSerializer(qs,many=True)
            return Response(serializer.data)
        return Response()

    @detail_route(methods=['GET',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def comms_log(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            qs = instance.comms_logs.all()
            serializer = ProposalLogEntrySerializer(qs,many=True)
            return Response(serializer.data)
        return Response()

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def add_comms_log(self, request, *args, **kwargs):
        if is_internal(request):
            with transaction.atomic():
                instance = self.get_object()
                mutable=request.data._mutable
                request.data._mutable=True
                request.data['proposal'] = u'{}'.format(instance.id)
                request.data['staff'] = u'{}'.format(request.user.id)
                request.data._mutable=mutable
                serializer = ProposalLogEntrySerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                comms = serializer.save()
                # Save the files
                for f in request.FILES:
                    document = comms.documents.create(
                        name = str(request.FILES[f]),
                        _file = request.FILES[f]
                    )
                # End Save Documents
                instance.log_user_action(f'User added comms log.', request)
                return Response(serializer.data)
        raise serializers.ValidationError("User not authorised to add comms log")

    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def requirements(self, request, *args, **kwargs):
        instance = self.get_object()
        qs = instance.requirements.all().exclude(is_deleted=True)
        qs=qs.order_by('order')
        serializer = ProposalRequirementSerializer(qs,many=True, context={'request':request})
        return Response(serializer.data)

    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def amendment_request(self, request, *args, **kwargs):
        instance = self.get_object()
        qs = instance.amendment_requests
        qs = qs.filter(status = 'requested')
        serializer = AmendmentRequestDisplaySerializer(qs,many=True)
        return Response(serializer.data)

    @detail_route(methods=['GET',], detail=True, permission_classes=[InternalProposalPermission])
    def internal_proposal(self, request, *args, **kwargs):
        if (is_internal(request)):
            instance = self.get_object()
            serializer = InternalProposalSerializer(instance, context={'request': request})
            return Response(serializer.data)
        return Response()
    
    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalAssessorPermission])
    def internal_endorse(self, request, *args, **kwargs):
        if (is_internal(request)):
            #get id of slmr
            id = request.data.get('site_licensee_mooring_request_id',None)
            #get slmr (only continue if enabled)
            try:
                slmr_instance = ProposalSiteLicenseeMooringRequest.objects.get(id=id)
            except:
                return serializers.ValidationError("Site Licensee Mooring Request does now exist")
            
            if slmr_instance.enabled:
                #set declined to false
                if slmr_instance.declined_by_endorser:
                    slmr_instance.declined_by_endorser = False
                    slmr_instance.save()

                #run endorse function
                slmr_instance.endorse_approved(request)

            else:
                return serializers.ValidationError("Site Licensee Mooring Request not listed on Proposal")

            instance = self.get_object()
            serializer = InternalProposalSerializer(instance, context={'request': request})
            instance.log_user_action(f'Proposal {instance} endorsed by RIA staff on endorser\'s behalf', request)
            return Response(serializer.data)
        return Response()

    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalAssessorPermission])
    def internal_decline(self, request, *args, **kwargs):
        if (is_internal(request)):
            #get id of slmr
            id = request.data.get('site_licensee_mooring_request_id',None)
            #get slmr (only continue if enabled)
            try:
                slmr_instance = ProposalSiteLicenseeMooringRequest.objects.get(id=id)
            except:
                return serializers.ValidationError("Site Licensee Mooring Request does now exist")
            
            if slmr_instance.enabled:
                #set endorsed/approved to false
                if slmr_instance.approved_by_endorser:
                    slmr_instance.approved_by_endorser = False
                    slmr_instance.save()

                #run decline function
                slmr_instance.endorse_declined(request)

            else:
                return serializers.ValidationError("Site Licensee Mooring Request not listed on Proposal")

            instance = self.get_object()
            serializer = InternalProposalSerializer(instance, context={'request': request})
            instance.log_user_action(f'Proposal {instance} declined by RIA staff on endorser\'s behalf', request)
            return Response(serializer.data)
        return Response()

    @detail_route(methods=['GET',], detail=True, permission_classes=[ProposalAssessorPermission|ProposalAssessorPermission])
    @basic_exception_handler
    def assign_request_user(self, request, *args, **kwargs):
        if (is_internal(request)):
            instance = self.get_object()
            instance.assign_officer(request, request.user)
            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance,context={'request':request})
            return Response(serializer.data)
        return Response()

    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalAssessorPermission|ProposalApproverPermission])
    @basic_exception_handler
    def assign_to(self, request, *args, **kwargs):
        if (is_internal(request)):
            instance = self.get_object()
            user_id = request.data.get('assessor_id',None)
            user = None
            if not user_id:
                raise serializers.ValidationError('An assessor id is required')
            try:
                user = EmailUser.objects.get(id=user_id)
            except EmailUser.DoesNotExist:
                raise serializers.ValidationError('A user with the id passed in does not exist')
            instance.assign_officer(request,user)
            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance,context={'request':request})
            return Response(serializer.data)
        raise serializers.ValidationError('User cannot assign proposal')

    @detail_route(methods=['GET',], detail=True, permission_classes=[ProposalAssessorPermission|ProposalApproverPermission])
    @basic_exception_handler
    def unassign(self, request, *args, **kwargs):
        if (is_internal(request)):
            instance = self.get_object()
            instance.unassign(request)
            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance,context={'request':request})
            return Response(serializer.data)
        raise serializers.ValidationError('User cannot unassign proposal')

    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalAssessorPermission|ProposalApproverPermission])
    @basic_exception_handler
    def switch_status(self, request, *args, **kwargs):
        if (is_internal(request)):
            instance = self.get_object()
            status = request.data.get('status')
            approver_comment = request.data.get('approver_comment')
            instance.move_to_status(request, status, approver_comment)
            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance,context={'request':request})
            return Response(serializer.data)
        raise serializers.ValidationError('User cannot change proposal status')

    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalAssessorPermission])
    @basic_exception_handler
    def bypass_endorsement(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            #check if an AUA awaiting endorsement
            if instance.application_type_code == 'aua' and instance.processing_status == Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT:
                #run function to move to with_assessor (include auth check in model func)
                instance.bypass_endorsement(request)
                instance.log_user_action(f'Proposal {instance} endorsement bypassed by RIA', request)
            else:
                serializers.ValidationError("Invalid application type")

            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance,context={'request':request})
            return Response(serializer.data)
        else:
            serializers.ValidationError("User not authorised to bypass endorsement")
    
    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalAssessorPermission])
    @basic_exception_handler
    def request_endorsement(self, request, *args, **kwargs):
        instance = self.get_object()
        if is_internal(request):
            #check if an AUA with site licensee mooring requests, that have not been actioned, with assessor
            if instance.application_type_code == 'aua' and instance.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR:
                if instance.site_licensee_mooring_request.filter(enabled=True,declined_by_endorser=False,approved_by_endorser=False).exists():
                    #run function to move to awaiting_endorsement (include auth check in model func)
                    instance.request_endorsement(request)
                    instance.log_user_action(f'Proposal {instance} reverted to awaiting endorsement status by RIA', request)
                else:
                    serializers.ValidationError("No site licensee moorings requests that require action")
            else:
                serializers.ValidationError("Invalid application type")

            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance,context={'request':request})
            return Response(serializer.data)
        else:
            serializers.ValidationError("User not authorised to request endorsement")

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def reissue_approval(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            status = request.data.get('status')
            if not status:
                raise serializers.ValidationError('Status is required')
            else:
                if not status in [Proposal.PROCESSING_STATUS_WITH_ASSESSOR,]:
                    raise serializers.ValidationError('The status provided is not allowed')
            instance.reissue_approval(request)
            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance,context={'request':request})
            return Response(serializer.data)
        else:
            serializers.ValidationError("User not authorised to reissue approval")

    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def renew_amend_approval_wrapper(self, request, *args, **kwargs):
        instance = self.get_object()
        approval = instance.approval
        ## validation
        renew_amend_conditions = {
            'previous_application': instance,
        }
        existing_proposal_qs=Proposal.objects.filter(**renew_amend_conditions)
        if (existing_proposal_qs and 
            existing_proposal_qs[0].customer_status in [Proposal.CUSTOMER_STATUS_WITH_ASSESSOR, Proposal.CUSTOMER_STATUS_DRAFT,] and
            existing_proposal_qs[0].proposal_type in ProposalType.objects.filter(code__in=[PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,])
        ):
            raise ValidationError('A renewal/amendment for this licence has already been lodged.')
        elif not approval or not approval.amend_or_renew:
            raise ValidationError('No licence available for renewal/amendment.')
        ## create renewal or amendment
        if approval and approval.amend_or_renew == 'renew':
            instance = instance.renew_approval(request)
        elif approval and approval.amend_or_renew == 'amend':
            instance = instance.amend_approval(request)

        return Response({"id":instance.id})

    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalAssessorPermission])
    @basic_exception_handler
    def proposed_approval(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            serializer = ProposedApprovalSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.proposed_approval(request, serializer.validated_data)
            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance,context={'request':request})
            return Response(serializer.data)
        else:
            raise serializers.ValidationError("not authorised to assess proposal")
        
    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalApproverPermission])
    @basic_exception_handler
    def final_approval(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            serializer = ProposedApprovalSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.final_approval(request, serializer.validated_data)
            return Response()
        else:
            raise serializers.ValidationError("not authorised to approve proposal")

    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalAssessorPermission])
    @basic_exception_handler
    def proposed_decline(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            serializer = ProposedDeclineSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.proposed_decline(request,serializer.validated_data)
            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance,context={'request':request})
            return Response(serializer.data)
        else:
            raise serializers.ValidationError("not authorised to decline proposal")

    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalApproverPermission])
    @basic_exception_handler
    def final_decline(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            serializer = ProposedDeclineSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.final_decline(request,serializer.validated_data)
            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance, context={'request':request})
            return Response(serializer.data)
        else:
            raise serializers.ValidationError("not authorised to decline proposal")

    @detail_route(methods=['post'], detail=True)
    @basic_exception_handler
    def draft(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            is_authorised_to_modify(request, instance)
            save_proponent_data(instance,request,self.action)
            instance = self.get_object()
            serializer = self.serializer_class(instance, context={'request':request})

            instance.log_user_action(f'Proposal {instance} draft saved.', request)
            return Response(serializer.data)
        
    @detail_route(methods=['post'], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def internal_save(self, request, *args, **kwargs):
        if (is_internal(request)):
            with transaction.atomic():
                instance = self.get_object()
                save_proponent_data(instance,request,self.action)
                instance = self.get_object()
                serializer_class = self.internal_serializer_class()
                serializer = serializer_class(instance, context={'request':request})

                instance.log_user_action(f'Proposal {instance} saved by RIA.', request)
                return Response(serializer.data)

    @detail_route(methods=['post'], detail=True)
    @basic_exception_handler
    def submit(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()

            logger.info(f'Proposal: [{instance}] has been submitted by the user: [{request.user}].')

            is_authorised_to_modify(request, instance)
            save_proponent_data(instance, request, self.action)

            instance = self.get_object()
            is_applicant_address_set(instance)

            serializer = self.serializer_class(instance, context={'request':request})
            return Response(serializer.data)

    @detail_route(methods=['GET',], detail=True)
    def get_max_vessel_length_for_main_component(self, request, *args, **kwargs):
        try:
            proposal = self.get_object()
            logger.info(f'Calculating the max vessel length for the main component without any additional cost for the Proposal: [{proposal}]...')

            max_vessel_length = get_max_vessel_length_for_main_component(proposal)

            res = {'max_length': max_vessel_length[0], 'include_max_length': max_vessel_length[1]}
            logger.info(f'Max vessel length for the main component without any additional cost is [{res}].')

            return Response(res)

        except Exception as e:
            print(traceback.print_exc())
            if hasattr(e,'message'):
                raise serializers.ValidationError(e.message)

    @detail_route(methods=['GET',], detail=True)
    def get_max_vessel_length_for_aa_component(self, request, *args, **kwargs):
        try:
            proposal = self.get_object()
            logger.info(f'Calculating the max vessel length for the AA component without any additional cost for the Proposal: [{proposal}]...')

            current_datetime = datetime.now(pytz.timezone(TIME_ZONE))
            target_date = proposal.get_target_date(current_datetime.date())

            # Retrieve vessel
            vid = request.GET.get('vid', None)
            vessel = Vessel.objects.get(id=int(vid)) if vid else None
            max_amount_paid = proposal.get_max_amount_paid_for_aa_component(target_date, vessel)
            application_type_aa = ApplicationType.objects.get(code=AnnualAdmissionApplication.code)
            fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_date(application_type_aa, target_date)
            max_length = calculate_max_length(fee_constructor, max_amount_paid, proposal.proposal_type)
            res = {'max_length': max_length}

            logger.info(f'Max vessel length for the AA component without any additional cost is [{res}].')

            return Response(res)

        except Exception as e:
            print(traceback.print_exc())
            if hasattr(e,'message'):
                raise serializers.ValidationError(e.message)
            raise serializers.ValidationError("Unable to obtain Max Vessel Length for AA component")

    @detail_route(methods=['GET',], detail=True)
    def fetch_vessel(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.vessel_ownership and not instance.vessel_ownership.end_date:
                vessel_details = instance.vessel_details.vessel.latest_vessel_details
                vessel_details_serializer = VesselDetailsSerializer(vessel_details, context={'request': request})
                vessel = vessel_details.vessel
                vessel_serializer = VesselSerializer(vessel)
                vessel_data = vessel_serializer.data
                vessel_ownership_data = {}
                vessel_data["rego_no"] = vessel.rego_no

                vessel_ownership_data = {}
                if instance.vessel_ownership:
                    vessel_ownership_serializer = VesselOwnershipSerializer(instance.vessel_ownership)
                    vessel_ownership_data = deepcopy(vessel_ownership_serializer.data)
                    vessel_ownership_data["individual_owner"] = False if instance.vessel_ownership.individual_owner else True
                else:
                    vessel_ownership_data["percentage"] = instance.percentage
                    vessel_ownership_data["individual_owner"] = instance.individual_owner
                vessel_data["vessel_details"] = vessel_details_serializer.data
                vessel_data["vessel_ownership"] = vessel_ownership_data
                return Response(vessel_data)
            else:
                return Response()
        except Exception as e:
            print(traceback.print_exc())
            if hasattr(e,'message'):
                raise serializers.ValidationError(e.message)

    @basic_exception_handler
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        logger.info(f'Proposal: [{instance}] is being destroyed by the user: [{request.user}].')

        if (instance.child_obj.application_type_code == MooringLicenceApplication.code and 
            request.query_params.get('action', '') in ['withdraw',] and
            is_internal(request)):
            instance.withdraw(request, *args, **kwargs)
        else:
            if instance.processing_status == Proposal.PROCESSING_STATUS_AWAITING_PAYMENT or instance.processing_status == Proposal.PROCESSING_STATUS_EXPIRED:
                instance.cancel_payment(request)
            else:
                instance.destroy(request, *args, **kwargs)

        return Response()


class ProposalRequirementViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.ListModelMixin):
    queryset = ProposalRequirement.objects.none()
    serializer_class = ProposalRequirementSerializer
    permission_classes=[ProposalAssessorPermission]

    def get_queryset(self):
        queryset = ProposalRequirement.objects.none()
        if is_internal(self.request):
            queryset = ProposalRequirement.objects.all().exclude(is_deleted=True)
        return queryset

    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def move_up(self, request, *args, **kwargs):
        instance = self.get_object()
        if (instance.proposal.has_assessor_mode(request.user)):
            instance.up()
            instance.save()
            instance.proposal.log_user_action(f'Proposal {instance.proposal} conditions rearranged.', request)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def move_down(self, request, *args, **kwargs):
        instance = self.get_object()
        if (instance.proposal.has_assessor_mode(request.user)):
            instance.down()
            instance.save()
            instance.proposal.log_user_action(f'Proposal {instance.proposal} conditions rearranged.', request)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def discard(self, request, *args, **kwargs):
        instance = self.get_object()
        if (instance.proposal.has_assessor_mode(request.user)):
            instance.is_deleted = True
            instance.save()
            instance.proposal.log_user_action(f'Proposal {instance.proposal} {instance.requirement} condition discarded.', request)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @basic_exception_handler
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        if (instance.proposal.has_assessor_mode(request.user)):
            serializer.save()
            instance.proposal.log_user_action(f'Proposal {instance.proposal} {instance.requirement} condition updated.', request)
        return Response(serializer.data)

    @basic_exception_handler
    def create(self, request, *args, **kwargs):
        if is_internal(request):
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception = True)
            try:
                proposal = Proposal.objects.get(id=request.data["proposal"])
                if (proposal.has_assessor_mode(request.user)):
                    serializer.save()
                    proposal.log_user_action(f'Proposal {proposal} {serializer.instance.requirement} condition added.', request)
                return Response(serializer.data)
            except Exception as e:
                print(e)
                raise serializers.ValidationError("Proposal does not exist")
        else:
            raise serializers.ValidationError("User not authorised to create proposal requirement")


class ProposalStandardRequirementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProposalStandardRequirement.objects.all()
    serializer_class = ProposalStandardRequirementSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        qs = ProposalStandardRequirement.objects.none()
        user = self.request.user
        if is_internal(self.request) or is_customer(self.request):
            application_type_code = self.request.query_params.get('application_type_code', '')
            queries = Q(application_type__isnull=True)
            if application_type_code:
                application_type = ApplicationType.objects.get(code=application_type_code)
                queries |= Q(application_type=application_type)
            qs = ProposalStandardRequirement.objects.exclude(obsolete=True).filter(queries)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(text__icontains=search)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    

class AmendmentRequestViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = AmendmentRequest.objects.all()
    serializer_class = AmendmentRequestSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        queryset = AmendmentRequest.objects.none()
        user = self.request.user
        if is_internal(self.request):
            queryset = AmendmentRequest.objects.all()
        elif is_customer(self.request):
            queryset = AmendmentRequest.objects.filter(
                Q(proposal_applicant__email_user_id=user.id)
            )
        return queryset

    @basic_exception_handler
    def create(self, request, *args, **kwargs):

        proposal = request.data.get('proposal')
        try:
            instance = Proposal.objects.get(id=proposal['id'])
        except:
            raise serializers.ValidationError("Invalid proposal id")
        
        if instance.has_assessor_mode(request.user):
            data = request.data
            reason_id = request.data.get('reason_id')
            
            data['reason'] = reason_id
            data['proposal'] = proposal['id']

            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception = True)
            instance = serializer.save()
            logger.info(f'New AmendmentRequest: [{instance}] has been created.')

            instance.generate_amendment(request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        else:
            raise serializers.ValidationError("user not authorised to make an amendment request")


class AmendmentRequestReasonChoicesView(views.APIView):
    permission_classes=[InternalProposalPermission]

    def get(self,request, format=None):
        if is_internal(request):
            choices_list = []
            choices=AmendmentReason.objects.all()
            if choices:
                for c in choices:
                    choices_list.append({'key': c.id,'value': c.reason})
            return Response(choices_list)
        else:
            return Response()


class VesselOwnershipViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = VesselOwnership.objects.all().order_by('id')
    serializer_class = VesselOwnershipSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = VesselOwnership.objects.all().order_by('id')
            return qs
        elif is_customer(self.request):
            queryset = VesselOwnership.objects.filter(Q(owner__in=Owner.objects.filter(Q(emailuser=user.id))))
            return queryset
        return VesselOwnership.objects.none()

    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    #TODO check if this is in use, remove if not
    def process_vessel_registration_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='vessel_registration_document')
        if returned_data:
            return Response(returned_data)
        else:
            return Response()

    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def lookup_vessel_ownership(self, request, *args, **kwargs):
        vo = self.get_object()
        vessel_details = vo.vessel.latest_vessel_details
        vessel_details_serializer = VesselDetailsSerializer(vessel_details, context={'request': request})
        vessel = vo.vessel
        vessel_serializer = VesselSerializer(vessel)
        vessel_data = vessel_serializer.data
        vessel_data["vessel_details"] = vessel_details_serializer.data

        # vessel_ownership
        vessel_ownership_data = {}
        vessel_ownership_serializer = VesselOwnershipSerializer(vo)
        vessel_ownership_data = deepcopy(vessel_ownership_serializer.data)
        vessel_ownership_data["individual_owner"] = True if vo.individual_owner else False

        try:
            if vessel_ownership_data["individual_owner"] and vessel_ownership_data["owner"]:
                vessel_ownership_data["owner_name"] = Owner.objects.get(id=vessel_ownership_data["owner"]).__str__()
            else:
                vessel_ownership_data["owner_name"] = ""
        except:
            vessel_ownership_data["owner_name"] = ""

        vessel_data["vessel_ownership"] = vessel_ownership_data
        return Response(vessel_data)

    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def record_sale(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            sale_date = request.data.get('sale_date')

            logger.info(f'Recording vessel sale of the vessel_ownership: [{instance}] with the sale_date: {sale_date}')
            if sale_date:
                if not instance.end_date:
                    # proposals with instance copied to listed_vessels
                    for proposal in instance.listed_on_proposals.all():
                        if proposal.processing_status not in [Proposal.PROCESSING_STATUS_DISCARDED, Proposal.PROCESSING_STATUS_APPROVED, Proposal.PROCESSING_STATUS_DECLINED, Proposal.PROCESSING_STATUS_EXPIRED]:
                            raise serializers.ValidationError(
                                    "You cannot record the sale of this vessel at this time as application {} that lists this vessel is still in progress.".format(proposal.lodgement_number)
                                    )
                    for proposal in instance.proposal_set.all():
                        if proposal.processing_status not in [Proposal.PROCESSING_STATUS_DISCARDED, Proposal.PROCESSING_STATUS_APPROVED, Proposal.PROCESSING_STATUS_DECLINED, Proposal.PROCESSING_STATUS_EXPIRED]:
                            raise serializers.ValidationError(
                                    "You cannot record the sale of this vessel at this time as application {} that lists this vessel is still in progress.".format(proposal.lodgement_number)
                                    )

                #apply sale date to vessel ownerships owned by the same Owner with the same rego no without an end date
                rego_no = instance.vessel.rego_no if instance.vessel else None
                owner = instance.owner

                affected_vessel_ownerships = VesselOwnership.objects.filter(vessel__rego_no=rego_no, owner=owner, end_date=None)
                affected_vessel_ownership_ids = list(affected_vessel_ownerships.values_list('id',flat=True))

                ## setting the end_date "removes" the vessel from current Approval records
                for vessel_ownership in affected_vessel_ownerships:
                    try:
                        vessel_ownership.end_date = datetime.strptime(sale_date,"%d/%m/%Y")
                        vessel_ownership.save()
                    except:
                        raise serializers.ValidationError("Invalid sale date provided.")
                    logger.info(f'Vessel sold: VesselOwnership: [{vessel_ownership}] has been updated with the end_date: [{sale_date}].')

                ## collect impacted Approvals
                approval_list = []
                for prop in Proposal.objects.filter(vessel_ownership_id__in=affected_vessel_ownership_ids,approval__status__in=Approval.APPROVED_STATUSES):
                    if (type(prop.approval.child_obj) in [WaitingListAllocation, AnnualAdmissionPermit, AuthorisedUserPermit] and
                            prop.approval not in approval_list):
                        approval_list.append(prop.approval)

                ## collect ML
                for voa in VesselOwnershipOnApproval.objects.filter(vessel_ownership=instance):
                    if voa.approval not in approval_list:
                        approval_list.append(voa.approval)

                ## change Sticker status
                stickers_to_be_returned = []
                for approval in approval_list:
                    # Generate a new licence/permit document
                    approval.generate_doc(False)

                    # Update sticker status - only for vessel ownerships with rego no of vessel sold
                    stickers_updated = []
                    for a_sticker in approval.stickers.filter(status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING]).filter(vessel_ownership__vessel__rego_no=rego_no):
                        a_sticker.status = Sticker.STICKER_STATUS_TO_BE_RETURNED
                        a_sticker.save()
                        logger.info(f'Status of the sticker: {a_sticker} has been changed to {Sticker.STICKER_STATUS_TO_BE_RETURNED}')

                        stickers_to_be_returned.append(a_sticker)
                        stickers_updated.append(a_sticker)
                    for a_sticker in approval.stickers.filter(status__in=[Sticker.STICKER_STATUS_READY, Sticker.STICKER_STATUS_NOT_READY_YET]).filter(vessel_ownership__vessel__rego_no=rego_no):
                        # vessel sold before the sticker is picked up by cron for export (very rarely happens)
                        a_sticker.status = Sticker.STICKER_STATUS_CANCELLED
                        a_sticker.save()
                        logger.info(f'Status of the sticker: {a_sticker} has been changed to {Sticker.STICKER_STATUS_CANCELLED}')

                        stickers_updated.append(a_sticker)

                    # Update MooringOnApproval
                    moas = MooringOnApproval.objects.filter(sticker__in=stickers_updated)
                    for moa in moas:
                        moa.sticker = None
                        moa.save()
                        logger.info(f'Sticker:None is set to the MooringOnApproval: {moa}')

                    # write approval history
                    approval.write_approval_history('Vessel sold by owner')

                    no_email = False
                    if is_internal(request):
                        no_email = request.data.get('no_email', False)

                    instance.refresh_from_db()

                    if not no_email:
                        if approval.code == WaitingListAllocation.code:
                            send_reissue_wla_after_sale_recorded_email(approval, request, instance, stickers_to_be_returned)
                        elif approval.code == AnnualAdmissionPermit.code:
                            send_reissue_aap_after_sale_recorded_email(approval, request, instance, stickers_to_be_returned)
                        elif approval.code == AuthorisedUserPermit.code:
                            send_reissue_aup_after_sale_recorded_email(approval, request, instance, stickers_to_be_returned)
                        elif approval.code == MooringLicence.code:
                            send_reissue_ml_after_sale_recorded_email(approval, request, instance, stickers_to_be_returned)

                    approval.log_user_action(f'Vessel {instance.vessel.rego_no} on Approval {approval} marked sold on {sale_date}.', request)
                    approval.export_to_mooring_booking = True
                    approval.save()

            else:
                raise serializers.ValidationError("Missing information: You must specify a sale date")
            return Response()

    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def fetch_sale_date(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = VesselOwnershipSaleDateSerializer(instance)
        return Response(serializer.data)


class CompanyViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = Company.objects.all().order_by('id')
    serializer_class = CompanySerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        qs = Company.objects.all().order_by('id')
        return qs

    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def lookup_company_ownership(self, request, *args, **kwargs):
        company = self.get_object()
        ## discover common vessel ownership
        vessel_id = request.data.get('vessel_id')
        co_list = []
        company_data = CompanySerializer(company).data
        empty_co = {"company": company_data}
        if vessel_id:
            co_qs = CompanyOwnership.objects.filter(vessel=Vessel.objects.get(id=vessel_id), company=company)
            # add business rules
            for co in co_qs.order_by('updated'):
                co_list.append(co)
            if co_list:
                co = co_list[0]
                serializer = CompanyOwnershipSerializer(co)
                return Response(serializer.data)
            else:
                return Response(empty_co)
        return Response(empty_co)


class CompanyOwnershipViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = CompanyOwnership.objects.all().order_by('id')
    serializer_class = CompanyOwnershipSerializer
    permission_classes=[IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = CompanyOwnership.objects.all().order_by('id')
            return qs
        elif is_customer(self.request):
            queryset = CompanyOwnership.objects.filter(Q(vessel_ownerships__in=VesselOwnership.objects.filter(Q(owner__in=Owner.objects.filter(Q(emailuser=user.id))))))
            return queryset
        return CompanyOwnership.objects.none()


class VesselViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.ListModelMixin):
    queryset = Vessel.objects.all().order_by('id')
    serializer_class = VesselSerializer
    permission_classes=[IsAuthenticated]

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def find_related_bookings(self, request, *args, **kwargs):
        if is_internal(request):
            vessel = self.get_object()
            booking_date_str = request.data.get("selected_date")
            booking_date = None
            if booking_date_str:
                booking_date = datetime.strptime(booking_date_str, '%d/%m/%Y').date()
                booking_date = booking_date.strftime('%Y-%m-%d')
            else:
                booking_date = datetime.now().strftime('%Y-%m-%d')
            data = get_bookings(booking_date, vessel.rego_no.upper())
            data = get_bookings(booking_date=booking_date, rego_no=vessel.rego_no.upper(), mooring_id=None)
            return Response(data)
        raise serializers.ValidationError("not authorised to view related bookings")

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def find_related_approvals(self, request, *args, **kwargs):
        if is_internal(request):
            vessel = self.get_object()
            selected_date_str = request.data.get("selected_date")
            selected_date = None
            if selected_date_str:
                selected_date = datetime.strptime(selected_date_str, '%d/%m/%Y').date()
            approval_list = []
            vd_set = VesselDetails.objects.filter(vessel=vessel)
            if selected_date:
                for vd in vd_set:
                    for prop in vd.proposal_set.all():
                        if (
                            prop.approval and 
                            selected_date >= prop.approval.start_date and
                            selected_date <= prop.approval.expiry_date and
                            # ensure vessel has not been sold
                            prop.vessel_ownership and not prop.vessel_ownership.end_date
                        ):
                            if prop.approval not in approval_list:
                                approval_list.append(prop.approval)
            else:
                for vd in vd_set:
                    for prop in vd.proposal_set.all():
                        if (
                            prop.approval and 
                            prop.approval.status == 'current' and
                            # ensure vessel has not been sold
                            prop.vessel_ownership and not prop.vessel_ownership.end_date
                        ):
                            if prop.approval not in approval_list:
                                approval_list.append(prop.approval)

            serializer = LookupApprovalSerializer(approval_list, many=True)
            return Response(serializer.data)
        raise serializers.ValidationError("not authorised to view related approvals")

    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def lookup_vessel_ownership(self, request, *args, **kwargs):
        vessel = self.get_object()
        if is_internal(request):
            serializer = VesselFullOwnershipSerializer(vessel.filtered_vesselownership_set.order_by("owner","-updated").distinct("owner"), many=True)
        else:
            serializer = VesselFullOwnershipSerializer(vessel.filtered_vesselownership_set.filter(owner__emailuser=request.user.id).order_by("owner","-updated").distinct("owner"), many=True)
        return Response(serializer.data)

    @detail_route(methods=['GET',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def comms_log(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            qs = instance.comms_logs.all()
            serializer = VesselLogEntrySerializer(qs,many=True)
            return Response(serializer.data)
        return Response()

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def add_comms_log(self, request, *args, **kwargs):
        if is_internal(request):
            with transaction.atomic():
                instance = self.get_object()
                mutable=request.data._mutable
                request.data._mutable=True
                request.data['vessel'] = u'{}'.format(instance.id)
                request.data._mutable=mutable
                serializer = VesselLogEntrySerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                comms = serializer.save()
                # Save the files
                for f in request.FILES:
                    document = comms.documents.create(
                        name = str(request.FILES[f]),
                        _file = request.FILES[f]
                    )
                # End Save Documents
                return Response(serializer.data)
        raise serializers.ValidationError("User not authorised to add comms log")

    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def lookup_individual_ownership(self, request, *args, **kwargs):
        vessel = self.get_object()
        owner_set = Owner.objects.filter(emailuser=request.user.id)
        if owner_set:
            vo_set = vessel.filtered_vesselownership_set.filter(owner=owner_set[0], vessel=vessel).exclude(company_ownerships__vesselownershipcompanyownership__status=VesselOwnershipCompanyOwnership.COMPANY_OWNERSHIP_STATUS_APPROVED)
            if vo_set:
                serializer = VesselOwnershipSerializer(vo_set[0])
                return Response(serializer.data)
            else:
                return Response()
        return Response()

    @detail_route(methods=['GET',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def full_details(self, request, *args, **kwargs):
        if is_internal(request):
            vessel = self.get_object()
            return Response(VesselFullSerializer(vessel).data)
 
    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def lookup_vessel(self, request, *args, **kwargs):
        vessel = self.get_object()
        vessel_details = vessel.latest_vessel_details
        vessel_details_serializer = VesselDetailsSerializer(vessel_details, context={'request': request})
        vessel_serializer = VesselSerializer(vessel)
        vessel_data = vessel_serializer.data
        vessel_data["vessel_details"] = vessel_details_serializer.data

        # vessel_ownership
        vessel_ownership_data = {}
        # check if this emailuser has a matching record for this vessel
        owner_qs = Owner.objects.filter(emailuser=request.user.id)
        if owner_qs:
            owner = owner_qs[0]
            vo_qs = vessel.vesselownership_set.filter(owner=owner)
            if vo_qs:
                vessel_ownership = vo_qs[0]
                vessel_ownership_serializer = VesselOwnershipSerializer(vessel_ownership)
                vessel_ownership_data = deepcopy(vessel_ownership_serializer.data)
                vessel_ownership_data["individual_owner"] = True if vessel_ownership.individual_owner else False
        vessel_data["vessel_ownership"] = vessel_ownership_data
        return Response(vessel_data)

    @list_route(methods=['GET',], detail=False, permission_classes=[InternalProposalPermission])
    def list_internal(self, request, *args, **kwargs):
        if is_internal(request):
            search_text = request.GET.get('search[value]', '')
            target_email_user_id = int(self.request.GET.get('target_email_user_id', 0))
            if target_email_user_id:
                try:
                    owner = Owner.objects.get(emailuser=target_email_user_id)
                except ObjectDoesNotExist:
                    return Response([])
                except:
                    raise serializers.ValidationError("error")
            else:
                raise serializers.ValidationError("no email user id provided")
            vessel_ownership_list = owner.vesselownership_set.order_by("vessel","-updated").distinct("vessel")

            if search_text:
                search_text = search_text.lower()
                search_text_vessel_ownership_ids = []
                matching_vessel_type_choices = [choice[0] for choice in VESSEL_TYPES if search_text in choice[1].lower()]
                for vo in vessel_ownership_list:
                    vd = vo.vessel.latest_vessel_details
                    if (search_text in (vd.vessel_name.lower() if vd.vessel_name else '') or
                            search_text in (vd.vessel.rego_no.lower() if vd.vessel.rego_no.lower() else '') or
                            vd.vessel_type in matching_vessel_type_choices or
                            search_text in vo.end_date.strftime('%d/%m/%Y')
                    ):
                        search_text_vessel_ownership_ids.append(vo.id)
                vessel_ownership_list = [vo for vo in vessel_ownership_list if vo.id in search_text_vessel_ownership_ids]

            serializer = ListVesselOwnershipSerializer(vessel_ownership_list, context={'request': request}, many=True)
            return Response(serializer.data)
        else:
            raise serializers.ValidationError("user not authorised")

    @list_route(methods=['GET',], detail=False)
    def list_external(self, request, *args, **kwargs):
        search_text = request.GET.get('search[value]', '')
        owner_qs = Owner.objects.filter(emailuser=request.user.id)
        if owner_qs:
            owner = owner_qs[0]
            vessel_ownership_list = owner.vesselownership_set.order_by("vessel","-updated").distinct("vessel")

            # rewrite following for vessel_ownership_list
            if search_text:
                search_text = search_text.lower()
                search_text_vessel_ownership_ids = []
                matching_vessel_type_choices = [choice[0] for choice in VESSEL_TYPES if search_text in choice[1].lower()]
                for vo in vessel_ownership_list:
                    vd = vo.vessel.latest_vessel_details
                    if (search_text in (vd.vessel_name.lower() if vd.vessel_name else '') or
                        search_text in (vd.vessel.rego_no.lower() if vd.vessel.rego_no.lower() else '') or
                        vd.vessel_type in matching_vessel_type_choices or
                        search_text in vo.end_date.strftime('%d/%m/%Y')
                        ):
                        search_text_vessel_ownership_ids.append(vo.id)
                vessel_ownership_list = [vo for vo in vessel_ownership_list if vo.id in search_text_vessel_ownership_ids]
            
            index = 0
            for vo in vessel_ownership_list:
                logger.debug(f'vessel_ownership [{index}]: [{vo}].')
                index += 1

            serializer = ListVesselOwnershipSerializer(vessel_ownership_list, context={'request': request}, many=True)
            return Response(serializer.data)
        else:
            return Response([])


class MooringBayViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MooringBay.objects.none()
    serializer_class = MooringBaySerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        queryset = MooringBay.objects.none()
        if is_internal(self.request) or is_customer(self.request):
            queryset = MooringBay.objects.filter(active=True)
        return queryset

    @list_route(methods=['GET',], detail=False)
    def lookup(self, request, *args, **kwargs):
        qs = self.get_queryset()
        response_data = [{"id":None,"name":"","mooring_bookings_id":None}]
        for mooring in qs:
            response_data.append(MooringBaySerializer(mooring).data)
        return Response(response_data)


class MooringFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        
        # filter_mooring_status
        filter_mooring_status = request.GET.get('filter_mooring_status')
        if filter_mooring_status and not filter_mooring_status.lower() == 'all':
            filtered_ids = [m.id for m in Mooring.objects.all() if m.status.lower() == filter_mooring_status.lower()]
            queryset = queryset.filter(id__in=filtered_ids)

        filter_mooring_bay = request.GET.get('filter_mooring_bay')
        if filter_mooring_bay and not filter_mooring_bay.lower() == 'all':
            queryset = queryset.filter(mooring_bay_id=filter_mooring_bay)

        fields = self.get_fields(request)
        ordering = self.get_ordering(request, view, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)

        try:
            super_queryset = super(MooringFilterBackend, self).filter_queryset(request, queryset, view)

            # Custom search
            search_text = request.GET.get('search[value]')  # This has a search term.
            if search_text:
                # User can search by a fullname, too
                system_user_ids = list(SystemUser.objects.annotate(full_name=Concat('legal_first_name',Value(" "),'legal_last_name',output_field=CharField()))
                .filter(
                    Q(legal_first_name__icontains=search_text) | Q(legal_last_name__icontains=search_text) | Q(email__icontains=search_text) | Q(full_name__icontains=search_text)
                ).values_list("ledger_id", flat=True))
                proposal_applicant_proposals = list(ProposalApplicant.objects.annotate(full_name=Concat('first_name',Value(" "),'last_name',output_field=CharField()))
                .filter(
                    Q(first_name__icontains=search_text) | Q(last_name__icontains=search_text) | Q(email__icontains=search_text) | Q(full_name__icontains=search_text)
                ).values_list("proposal_id", flat=True))

                q_set = queryset.filter(Q(mooring_licence__approval__current_proposal__id__in=proposal_applicant_proposals)|Q(mooring_licence__submitter__in=system_user_ids))

                queryset = super_queryset.union(q_set)

        except Exception as e:
            print(e)
        total_count = queryset.count()
        setattr(view, '_datatables_filtered_count', total_count)
        return queryset


class MooringPaginatedViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = (MooringFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    queryset = Mooring.objects.none()
    serializer_class = ListMooringSerializer
    permission_classes=[InternalProposalPermission]

    def get_queryset(self):
        qs = Mooring.objects.none()
        if is_internal(self.request):
            qs = Mooring.private_moorings.filter(active=True)
        return qs


class MooringViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = Mooring.objects.none()
    serializer_class = MooringSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        queryset = Mooring.objects.none()
        if is_internal(self.request) or is_customer(self.request):
            queryset = Mooring.objects.filter(active=True)
        return queryset

    @detail_route(methods=['POST',], detail=True, permission_classes=[ProposalAssessorPermission|ProposalApproverPermission])
    def removeAUPFromMooring(self, request, *args, **kwargs):
        if is_internal(request):
            with transaction.atomic():
                try:
                    mooring = self.get_object()
                    approval_id = request.data.get('approval_id')
                    try:
                        moa = MooringOnApproval.objects.get(mooring=mooring, approval_id=approval_id)
                        approval = Approval.objects.get(id=approval_id)
                    except:
                        raise serializers.ValidationError("Mooring and AUP relationship does not exist")
                    today=datetime.now(pytz.timezone(TIME_ZONE)).date()
                    # removing the link between Approval and MSL
                    moa.active = False
                    moa.end_date = today         
                    moa.save()
                    # regenerating Authorised User Permit after mooring has been removed
                    moa.approval.generate_doc()
                    # send_aup_revoked email if required
                    moas = MooringOnApproval.objects.filter(mooring=mooring, active=True)
                    mls = MooringLicence.objects.filter(mooring=mooring)
                    if moas.count() > 0:
                        for ml in mls:
                            # regenerating the List of Authorised Users document for the mooring Licence and sending email to the user
                            ml.generate_au_summary_doc()
                            #send email to mooring licence owner if with the above attachement if required
                    elif mooring.mooring_licence:
                        # removing the List of Authorised Users document if there is no more AUPs remaining 
                        mooring.mooring_licence.authorised_user_summary_document = None

                    approval.manage_stickers()

                    approval.log_user_action(f'AUP {approval} removed from Mooring {mooring}.', request)
                    mooring.log_user_action(f'AUP {approval} removed from Mooring {mooring}.', request)
                    return Response({"results": "Success"})
                except Exception as e:
                    logger.error(str(e))
                    raise serializers.ValidationError("Error removing AUP from Mooring")

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def find_related_bookings(self, request, *args, **kwargs):
        if is_internal(request):
            mooring = self.get_object()
            booking_date_str = request.data.get("selected_date")
            booking_date = None
            if booking_date_str:
                booking_date = datetime.strptime(booking_date_str, '%d/%m/%Y').date()
                booking_date = booking_date.strftime('%Y-%m-%d')
            else:
                booking_date = datetime.now().strftime('%Y-%m-%d')
            data = get_bookings(booking_date=booking_date, rego_no=None, mooring_id=mooring.mooring_bookings_id)
            return Response(data)
        raise serializers.ValidationError("not authorised to view related bookings")

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def find_related_approvals(self, request, *args, **kwargs):
        if is_internal(request):
            mooring = self.get_object()
            selected_date_str = request.data.get("selected_date")
            selected_date = None
            if selected_date_str:
                selected_date = datetime.strptime(selected_date_str, '%d/%m/%Y').date()
            if selected_date:
                approval_list = [approval for approval in mooring.approval_set.filter(start_date__lte=selected_date, expiry_date__gte=selected_date)]
            else:
                approval_list = [approval for approval in mooring.approval_set.filter(status=Approval.APPROVAL_STATUS_CURRENT)]
            if mooring.mooring_licence and mooring.mooring_licence.status == Approval.APPROVAL_STATUS_CURRENT:
                approval_list.append(mooring.mooring_licence.approval)

        if len(approval_list) > 0:
            for approval in reversed(range(len(approval_list))):
                if approval_list[approval].lodgement_number.startswith('AUP'):
                    approval_id = approval_list[approval].pk
                    try:
                        moa = MooringOnApproval.objects.get(mooring_id=mooring.pk, approval_id=approval_id)
                    except ObjectDoesNotExist:
                        moa = None
                    if moa is None or moa.active is False:
                        approval_list.pop(approval)
        serializer = LookupApprovalSerializer(list(set(approval_list)), many=True, context={'mooring': mooring})
        return Response(serializer.data)

    @detail_route(methods=['GET',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def comms_log(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            qs = instance.comms_logs.all()
            serializer = MooringLogEntrySerializer(qs,many=True)
            return Response(serializer.data)
        return Response()
    
    @detail_route(methods=['GET',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def action_log(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            qs = instance.action_logs.all()
            serializer = MooringUserActionSerializer(qs,many=True)
            return Response(serializer.data)
        return Response()

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalProposalPermission])
    @basic_exception_handler
    def add_comms_log(self, request, *args, **kwargs):
        if is_internal(request):
            with transaction.atomic():
                instance = self.get_object()
                mutable=request.data._mutable
                request.data._mutable=True
                request.data['mooring'] = u'{}'.format(instance.id)
                request.data._mutable=mutable
                serializer = MooringLogEntrySerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                comms = serializer.save()
                # Save the files
                for f in request.FILES:
                    document = comms.documents.create(
                        name = str(request.FILES[f]),
                        _file = request.FILES[f]
                    )
                # End Save Documents
                instance.log_user_action(f'User added comms log.', request)
                return Response(serializer.data)
        raise serializers.ValidationError("User not authorised to add comms log")

    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def fetch_mooring_name(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response({"name": instance.name})