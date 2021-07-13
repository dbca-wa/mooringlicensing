import traceback
import json
from django.db.models import Q, Min
from django.db import transaction, connection
from django.core.exceptions import ValidationError
from rest_framework import viewsets, serializers, status, generics, views
from rest_framework.decorators import detail_route, list_route, renderer_classes, parser_classes
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from datetime import datetime, date
# from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser, BasePermission
# from rest_framework.pagination import PageNumberPagination
# from collections import OrderedDict
# from django.core.cache import cache
from ledger.accounts.models import EmailUser, Address
# from ledger.address.models import Country
# from datetime import datetime, timedelta, date
from mooringlicensing.components.proposals.utils import (
        save_proponent_data,
        save_assessor_data, 
        # proposal_submit,
        save_bare_vessel_data
        )
from mooringlicensing.components.proposals.models import searchKeyWords, search_reference, ProposalUserAction, \
    ProposalType
#from mooringlicensing.utils import missing_required_fields
from mooringlicensing.components.main.utils import (
        check_db_connection, 
        add_cache_control,
        get_bookings,
        )

from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from mooringlicensing.components.main.models import (
        Document, #Region, District, Tenure, 
        #ApplicationType, 
        )
from mooringlicensing.components.proposals.models import (
    #ProposalType,
    Proposal,
    ProposalDocument,
    ProposalRequirement,
    ProposalStandardRequirement,
    AmendmentRequest,
    AmendmentReason,
    VesselDetails,
    ChecklistQuestion,
    ProposalAssessment,
    ProposalAssessmentAnswer,
    RequirementDocument,
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
    ProposalSerializer,
    InternalProposalSerializer,
    SaveProposalSerializer,
    ProposalUserActionSerializer,
    ProposalLogEntrySerializer,
    VesselLogEntrySerializer,
    MooringLogEntrySerializer,
    ProposalRequirementSerializer,
    ProposalStandardRequirementSerializer,
    ProposedApprovalSerializer,
    # PropedDeclineSerializer,
    AmendmentRequestSerializer,
    # SearchReferenceSerializer,
    # SearchKeywordSerializer,
    # ListProposalSerializer,
    # AmendmentRequestDisplaySerializer,
    # VesselSerializer,
    # OnHoldSerializer,
    # ProposalOtherDetailsSerializer,
    # SaveProposalOtherDetailsSerializer,
    ChecklistQuestionSerializer,
    ProposalAssessmentSerializer,
    ProposalAssessmentAnswerSerializer,
    ListProposalSerializer,
    ListVesselDetailsSerializer,
    ListVesselOwnershipSerializer,
    VesselSerializer,
    VesselDetailsSerializer,
    VesselOwnershipSerializer,
    MooringBaySerializer, EmailUserSerializer, ProposedDeclineSerializer,
    CompanyOwnershipSerializer,
    CompanySerializer,
    SaveVesselOwnershipSaleDateSerializer,
    VesselOwnershipSaleDateSerializer,
    MooringSerializer,
    VesselFullSerializer,
    VesselFullOwnershipSerializer,
    ListMooringSerializer,
)

#from mooringlicensing.components.bookings.models import Booking, ParkBooking, BookingInvoice
from mooringlicensing.components.approvals.models import Approval, DcvVessel, WaitingListAllocation
from mooringlicensing.components.approvals.email import send_vessel_nomination_notification_main
from mooringlicensing.components.approvals.serializers import (
        ApprovalSerializer, 
        LookupApprovalSerializer,
        )
from mooringlicensing.components.compliances.models import Compliance
from mooringlicensing.components.compliances.serializers import ComplianceSerializer
from ledger.payments.invoice.models import Invoice
from mooringlicensing.components.main.process_document import (
        process_generic_document, 
        )
from mooringlicensing.components.main.decorators import (
        basic_exception_handler, 
        timeit, 
        query_debugger
        )
from mooringlicensing.helpers import is_customer, is_internal
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from rest_framework_datatables.pagination import DatatablesPageNumberPagination
from rest_framework_datatables.filters import DatatablesFilterBackend
from rest_framework_datatables.renderers import DatatablesRenderer
from rest_framework.filters import BaseFilterBackend
import reversion
from reversion.models import Version
from copy import deepcopy

import logging

from mooringlicensing.settings import PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL

logger = logging.getLogger(__name__)


#class GetProposalType(views.APIView):
#    renderer_classes = [JSONRenderer, ]
#
#    def get(self, request, format=None):
#        _type = ProposalType.objects.first()
#        if _type:
#            serializer = ProposalTypeSerializer(_type)
#            return Response(serializer.data)
#        else:
#            return Response({'error': 'There is currently no application type.'}, status=status.HTTP_404_NOT_FOUND)

class GetDcvVesselRegoNos(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        search_term = request.GET.get('term', '')
        #data = Vessel.objects.filter(rego_no__icontains=search_term).values_list('rego_no', flat=True)[:10]
        if search_term:
            data = DcvVessel.objects.filter(rego_no__icontains=search_term).values('id', 'rego_no')[:10]
            data_transform = [{'id': rego['id'], 'text': rego['rego_no']} for rego in data]
            return Response({"results": data_transform})
        return add_cache_control(Response())


class GetVessel(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        search_term = request.GET.get('term', '')
        if search_term:
            data = VesselDetails.filtered_objects.filter(
                    Q(vessel__rego_no__icontains=search_term) | 
                    Q(vessel_name__icontains=search_term)
                    )[:10]
            data_transform = []
            for vd in data:
                data_transform.append({
                    'id': vd.vessel.id, 
                    'text': vd.vessel.rego_no + ' - ' + vd.vessel.latest_vessel_details.vessel_name,
                    })
            return Response({"results": data_transform})
        return Response()


class GetMooring(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        private_moorings = request.GET.get('private_moorings')
        search_term = request.GET.get('term', '')
        #data = Vessel.objects.filter(rego_no__icontains=search_term).values_list('rego_no', flat=True)[:10]
        if search_term:
            if private_moorings:
                data = Mooring.private_moorings.filter(name__icontains=search_term).values('id', 'name')[:10]
            else:
                data = Mooring.objects.filter(name__icontains=search_term).values('id', 'name')[:10]
            data_transform = [{'id': mooring['id'], 'text': mooring['name']} for mooring in data]
            return Response({"results": data_transform})
        return Response()


class GetMooringPerBay(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        mooring_bay_id = request.GET.get('mooring_bay_id')
        available_moorings = request.GET.get('available_moorings')
        search_term = request.GET.get('term', '')
        #data = Vessel.objects.filter(rego_no__icontains=search_term).values_list('rego_no', flat=True)[:10]
        if search_term:
            if available_moorings:
                if mooring_bay_id:
                    data = Mooring.available_moorings.filter(name__icontains=search_term, mooring_bay__id=mooring_bay_id).values('id', 'name')[:10]
                else:
                    data = Mooring.available_moorings.filter(name__icontains=search_term).values('id', 'name')[:10]
            else:
                if mooring_bay_id:
                    data = Mooring.private_moorings.filter(name__icontains=search_term, mooring_bay__id=mooring_bay_id).values('id', 'name')[:10]
                else:
                    data = Mooring.private_moorings.filter(name__icontains=search_term).values('id', 'name')[:10]
            data_transform = [{'id': mooring['id'], 'text': mooring['name']} for mooring in data]
            return Response({"results": data_transform})
        return Response()


#class GetVesselRegoNos(views.APIView):
#    renderer_classes = [JSONRenderer, ]
#
#    def get(self, request, format=None):
#        #import ipdb; ipdb.set_trace()
#        search_term = request.GET.get('term', '')
#        create_vessel = True if request.GET.get('create_vessel') == 'true' else False
#        org_name = request.GET.get('org_name', '')
#        #data = Vessel.objects.filter(rego_no__icontains=search_term).values_list('rego_no', flat=True)[:10]
#        if search_term:
#            data = Vessel.objects.filter(rego_no__icontains=search_term).values('id', 'rego_no')[:10]
#            data_transform = []
#            owner_set = Owner.objects.filter(emailuser=request.user)
#            if create_vessel and owner_set:
#                for rego in data:
#                    vessel = Vessel.objects.get(rego_no=rego.get('rego_no'))
#                    vessel_ownership_set = VesselOwnership.objects.filter(
#                        owner=owner_set[0], 
#                        vessel=vessel, 
#                        org_name=org_name if org_name else None
#                        )
#                    # request.user owns vessel
#                    if not vessel_ownership_set:
#                        data_transform.append({'id': rego.get('id'), 'text': rego.get('rego_no')})
#            else:
#                data_transform = [{'id': rego['id'], 'text': rego['rego_no']} for rego in data] 
#            return Response({"results": data_transform})
#        return add_cache_control(Response())

class GetVesselRegoNos(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        #import ipdb; ipdb.set_trace()
        search_term = request.GET.get('term', '')
        create_vessel = True if request.GET.get('create_vessel') == 'true' else False
        company_name = request.GET.get('company_name')
        #org_name = request.GET.get('org_name', '')
        #data = Vessel.objects.filter(rego_no__icontains=search_term).values_list('rego_no', flat=True)[:10]
        if search_term:
            data = Vessel.objects.filter(rego_no__icontains=search_term).values('id', 'rego_no')[:10]
            data_transform = []
            owner_set = Owner.objects.filter(emailuser=request.user)
            if create_vessel and owner_set:
                for rego in data:
                    vessel = Vessel.objects.get(rego_no=rego.get('rego_no'))
                    vessel_ownership_set = None
                    if company_name:
                        company_ownership_set = CompanyOwnership.objects.filter(
                                vessel=vessel,
                                company__name=company_name)
                        vessel_ownership_set = VesselOwnership.objects.filter(
                            owner=owner_set[0], 
                            vessel=vessel, 
                            company_ownership__in=company_ownership_set
                            )
                    else:
                        vessel_ownership_set = VesselOwnership.objects.filter(
                            owner=owner_set[0],
                            vessel=vessel
                            )
                    # request.user owns vessel
                    if not vessel_ownership_set:
                        data_transform.append({'id': rego.get('id'), 'text': rego.get('rego_no')})
            else:
                data_transform = [{'id': rego['id'], 'text': rego['rego_no']} for rego in data]
            return Response({"results": data_transform})
        return Response()


class GetCompanyNames(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        #import ipdb; ipdb.set_trace()
        search_term = request.GET.get('term', '')
        #create_vessel = True if request.GET.get('create_vessel') == 'true' else False
        #org_name = request.GET.get('org_name', '')
        #data = Vessel.objects.filter(rego_no__icontains=search_term).values_list('rego_no', flat=True)[:10]
        if search_term:
            data = Company.objects.filter(name__icontains=search_term).values('id', 'name')[:10]
            data_transform = []
            data_transform = [{'id': company['id'], 'text': company['name']} for company in data] 
            return Response({"results": data_transform})
        return add_cache_control(Response())


class GetApplicationTypeDescriptions(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        return add_cache_control(Response(Proposal.application_type_descriptions()))


class GetApplicantsDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        applicants = EmailUser.objects.filter(mooringlicensing_proposals__in=Proposal.objects.all()).order_by('first_name', 'last_name').distinct()
        return add_cache_control(Response(EmailUserSerializer(applicants, many=True).data))


class GetApplicationTypeDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        apply_page = request.GET.get('apply_page', 'false')
        apply_page = True if apply_page.lower() in ['true', 'yes', 'y', ] else False
        return add_cache_control(Response(Proposal.application_types_dict(apply_page=apply_page)))


class GetApplicationStatusesDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        data_ext = [{'code': i[0], 'description': i[1]} for i in Proposal.CUSTOMER_STATUS_CHOICES]
        data_int = [{'code': i[0], 'description': i[1]} for i in Proposal.PROCESSING_STATUS_CHOICES]
        data = {'internal_statuses': data_int, 'external_statuses': data_ext}
        return add_cache_control(Response(data))


class GetVesselTypesDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        data = [{'code': i[0], 'description': i[1]} for i in VESSEL_TYPES]
        return add_cache_control(Response(data))


class GetInsuranceChoicesDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        data = [{'code': i[0], 'description': i[1]} for i in INSURANCE_CHOICES]
        return add_cache_control(Response(data))


class GetMooringStatusesDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    #def get(self, request, format=None):
     #   data = [{'code': i[0], 'description': i[1]} for i in Mooring.MOORING_SPECIFICATION]
      #  return Response(data)
    def get(self, request):
        #data = [{'code': i[0], 'description': i[1]} for i in Mooring.MOORING_SPECIFICATION]
        return Response(['Licenced', 'Licence application'])


class GetEmptyList(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        return add_cache_control(Response([]))


class VersionableModelViewSetMixin(viewsets.ModelViewSet):
    @detail_route(methods=['GET',])
    def history(self, request, *args, **kwargs):
        _object = self.get_object()
        #_versions = reversion.get_for_object(_object)
        _versions = Version.objects.get_for_object(_object)

        _context = {
            'request': request
        }

        #_version_serializer = VersionSerializer(_versions, many=True, context=_context)
        _version_serializer = ProposalSerializer([v.object for v in _versions], many=True, context=_context)
        # TODO
        # check pagination
        return add_cache_control(Response(_version_serializer.data))


class ProposalFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        total_count = queryset.count()

        level = request.GET.get('level', 'external')  # Check where the request comes from

        filter_application_type = request.GET.get('filter_application_type')
        if filter_application_type and not filter_application_type.lower() == 'all':
            q = None
            for item in Proposal.__subclasses__():
                if hasattr(item, 'code') and item.code == filter_application_type:
                    lookup = "{}__isnull".format(item._meta.model_name)
                    q = Q(**{lookup: False})
                    break
            queryset = queryset.filter(q) if q else queryset

        filter_application_status = request.GET.get('filter_application_status')
        if filter_application_status and not filter_application_status.lower() == 'all':
            if level == 'internal':
                queryset = queryset.filter(processing_status=filter_application_status)
            else:
                queryset = queryset.filter(customer_status=filter_application_status)

        filter_applicant_id = request.GET.get('filter_applicant')
        if filter_applicant_id and not filter_applicant_id.lower() == 'all':
            queryset = queryset.filter(submitter__id=filter_applicant_id)

        # Filter by endorsement
        filter_by_endorsement = request.GET.get('filter_by_endorsement', 'false')
        filter_by_endorsement = True if filter_by_endorsement.lower() in ['true', 'yes', 't', 'y',] else False
        if filter_by_endorsement:
            queryset = queryset.filter(site_licensee_email=request.user.email)
        else:
            queryset = queryset.exclude(site_licensee_email=request.user.email)

        getter = request.query_params.get
        fields = self.get_fields(getter)
        ordering = self.get_ordering(getter, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)

        try:
            queryset = super(ProposalFilterBackend, self).filter_queryset(request, queryset, view)
        except Exception as e:
            print(e)
        setattr(view, '_datatables_total_count', total_count)
        return queryset


class ProposalRenderer(DatatablesRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if 'view' in renderer_context and hasattr(renderer_context['view'], '_datatables_total_count'):
            data['recordsTotal'] = renderer_context['view']._datatables_total_count
        return super(ProposalRenderer, self).render(data, accepted_media_type, renderer_context)


class ProposalPaginatedViewSet(viewsets.ModelViewSet):
    filter_backends = (ProposalFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    renderer_classes = (ProposalRenderer,)
    queryset = Proposal.objects.none()
    serializer_class = ListProposalSerializer
    search_fields = ['lodgement_number', ]
    page_size = 10

    def get_queryset(self):
        request_user = self.request.user
        all = Proposal.objects.all()

        if is_internal(self.request):
            return all
        elif is_customer(self.request):
            user_orgs = [org.id for org in request_user.mooringlicensing_organisations.all()]
            qs = all.filter(Q(org_applicant_id__in=user_orgs) | Q(submitter=request_user) | Q(site_licensee_email=request_user.email))
            return qs
        return Proposal.objects.none()

    def list(self, request, *args, **kwargs):
        """
        User is accessing /external/ page
        """
        qs = self.get_queryset()
        qs = self.filter_queryset(qs)
        # on the internal organisations dashboard, filter the Proposal/Approval/Compliance datatables by applicant/organisation
        # applicant_id = request.GET.get('org_id')
        # if applicant_id:
        #     qs = qs.filter(applicant_id=applicant_id)

        self.paginator.page_size = qs.count()
        result_page = self.paginator.paginate_queryset(qs.order_by('-id'), request)
        serializer = ListProposalSerializer(result_page, context={'request': request}, many=True)
        return add_cache_control(self.paginator.get_paginated_response(serializer.data))


class AnnualAdmissionApplicationViewSet(viewsets.ModelViewSet):
    queryset = AnnualAdmissionApplication.objects.none()
    serializer_class = ProposalSerializer
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = AnnualAdmissionApplication.objects.all()
            return qs
        elif is_customer(self.request):
            #user_orgs = [org.id for org in user.mooringlicensing_organisations.all()]
            queryset = AnnualAdmissionApplication.objects.filter(Q(proxy_applicant_id=user.id) | Q(submitter=user))
            return queryset
        logger.warn("User is neither customer nor internal user: {} <{}>".format(user.get_full_name(), user.email))
        return AnnualAdmissionApplication.objects.none()

    def create(self, request, *args, **kwargs):
        proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)

        obj = AnnualAdmissionApplication.objects.create(
                submitter=request.user,
                proposal_type=proposal_type
                )
        serialized_obj = ProposalSerializer(obj)
        return add_cache_control(Response(serialized_obj.data))


class AuthorisedUserApplicationViewSet(viewsets.ModelViewSet):
    queryset = AuthorisedUserApplication.objects.none()
    serializer_class = ProposalSerializer
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = AuthorisedUserApplication.objects.all()
            return qs
        elif is_customer(self.request):
            #user_orgs = [org.id for org in user.mooringlicensing_organisations.all()]
            queryset = AuthorisedUserApplication.objects.filter(Q(proxy_applicant_id=user.id) | Q(submitter=user))
            return queryset
        logger.warn("User is neither customer nor internal user: {} <{}>".format(user.get_full_name(), user.email))
        return AuthorisedUserApplication.objects.none()

    def create(self, request, *args, **kwargs):
        proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)

        obj = AuthorisedUserApplication.objects.create(
                submitter=request.user,
                proposal_type=proposal_type
                )
        serialized_obj = ProposalSerializer(obj)
        return add_cache_control(Response(serialized_obj.data))


class MooringLicenceApplicationViewSet(viewsets.ModelViewSet):
    queryset = MooringLicenceApplication.objects.none()
    serializer_class = ProposalSerializer
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = MooringLicenceApplication.objects.all()
            return qs
        elif is_customer(self.request):
            #user_orgs = [org.id for org in user.mooringlicensing_organisations.all()]
            queryset = MooringLicenceApplication.objects.filter(Q(proxy_applicant_id=user.id) | Q(submitter=user))
            return queryset
        logger.warn("User is neither customer nor internal user: {} <{}>".format(user.get_full_name(), user.email))
        return MooringLicenceApplication.objects.none()

    def create(self, request, *args, **kwargs):
        #import ipdb; ipdb.set_trace()
        proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)
        mooring_id = request.data.get('mooring_id')
        mooring=None
        if mooring_id:
            mooring = Mooring.objects.get(id=mooring_id)
        #approval_id = request.data.get('approval_id')
        #approval=None
        #if approval_id:
        #    approval = Approval.objects.get(id=approval_id)

        obj = MooringLicenceApplication.objects.create(
                submitter=request.user,
                proposal_type=proposal_type,
                allocated_mooring=mooring,
                #approval=approval
                )
        serialized_obj = ProposalSerializer(obj)
        return Response(serialized_obj.data)


class WaitingListApplicationViewSet(viewsets.ModelViewSet):
    queryset = WaitingListApplication.objects.none()
    serializer_class = ProposalSerializer
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = WaitingListApplication.objects.all()
            return qs
        elif is_customer(self.request):
            #user_orgs = [org.id for org in user.mooringlicensing_organisations.all()]
            queryset = WaitingListApplication.objects.filter(Q(proxy_applicant_id=user.id) | Q(submitter=user))
            return queryset
        logger.warn("User is neither customer nor internal user: {} <{}>".format(user.get_full_name(), user.email))
        return WaitingListApplication.objects.none()

    def create(self, request, *args, **kwargs):
        proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)

        obj = WaitingListApplication.objects.create(
                submitter=request.user,
                proposal_type=proposal_type
                )
        serialized_obj = ProposalSerializer(obj)
        return add_cache_control(Response(serialized_obj.data))


class ProposalByUuidViewSet(viewsets.ModelViewSet):
    queryset = Proposal.objects.none()

    def get_object(self):
        uuid = self.kwargs.get('pk')
        return MooringLicenceApplication.objects.get(uuid=uuid)

    @detail_route(methods=['POST'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def process_mooring_report_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='mooring_report_document')
        if returned_data:
            return add_cache_control(Response(returned_data))
        else:
            return add_cache_control(Response())

    @detail_route(methods=['POST'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def process_written_proof_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='written_proof_document')
        if returned_data:
            return add_cache_control(Response(returned_data))
        else:
            return add_cache_control(Response())

    @detail_route(methods=['POST'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def submit(self, request, *args, **kwargs):
        instance = self.get_object()

        if not instance.mooring_report_documents.count() or not instance.written_proof_documents.count():
            # Documents missing
            raise

        instance.process_after_uploading_other_documents(request)
        return add_cache_control(Response())


class ProposalViewSet(viewsets.ModelViewSet):
    # filter_backends = (ProposalFilterBackend,)
    queryset = Proposal.objects.none()
    serializer_class = ProposalSerializer
    lookup_field = 'id'

    def get_queryset(self):
        request_user = self.request.user
        if is_internal(self.request):
            qs = Proposal.objects.all()
            return qs
        elif is_customer(self.request):
            user_orgs = [org.id for org in request_user.mooringlicensing_organisations.all()]
            queryset = Proposal.objects.filter(Q(org_applicant_id__in=user_orgs) | Q(submitter=request_user) | Q(site_licensee_email=request_user.email))
            return queryset
        logger.warn("User is neither customer nor internal user: {} <{}>".format(request_user.get_full_name(), request_user.email))
        return Proposal.objects.none()

    #def get_object(self):

    #    check_db_connection()
    #    try:
    #        obj = super(ProposalViewSet, self).get_object()
    #    except Exception as e:
    #        # because current queryset excludes migrated licences
    #        obj = get_object_or_404(Proposal, id=self.kwargs['id'])
    #    return obj

    #def get_serializer_class(self):
    #    try:
    #        application_type = Proposal.objects.get(id=self.kwargs.get('id')).application_type.name
    #        if application_type == ApplicationType.TCLASS:
    #            return ProposalSerializer
    #        elif application_type == ApplicationType.FILMING:
    #            return ProposalFilmingSerializer
    #        elif application_type == ApplicationType.EVENT:
    #            return ProposalEventSerializer
    #    except serializers.ValidationError:
    #        print(traceback.print_exc())
    #        raise
    #    except ValidationError as e:
    #        if hasattr(e,'error_dict'):
    #            raise serializers.ValidationError(repr(e.error_dict))
    #        else:
    #            if hasattr(e,'message'):
    #                raise serializers.ValidationError(e.message)
    #    except Exception as e:
    #        print(traceback.print_exc())
    #        raise serializers.ValidationError(str(e))

    def internal_serializer_class(self):
       try:
           return InternalProposalSerializer
           # application_type = Proposal.objects.get(id=self.kwargs.get('id')).application_type.code
           # if application_type == ApplicationType.TCLASS:
           #     return InternalProposalSerializer
           # elif application_type == ApplicationType.FILMING:
           #     return InternalFilmingProposalSerializer
           # elif application_type == ApplicationType.EVENT:
           #     return InternalEventProposalSerializer
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


    #@list_route(methods=['GET',])
    #def filter_list(self, request, *args, **kwargs):
    #    """ Used by the internal/external dashboard filters """
    #    region_qs =  self.get_queryset().filter(region__isnull=False).values_list('region__name', flat=True).distinct()
    #    #district_qs =  self.get_queryset().filter(district__isnull=False).values_list('district__name', flat=True).distinct()
    #    activity_qs =  self.get_queryset().filter(activity__isnull=False).values_list('activity', flat=True).distinct()
    #    submitter_qs = self.get_queryset().filter(submitter__isnull=False).distinct('submitter__email').values_list('submitter__first_name','submitter__last_name','submitter__email')
    #    submitters = [dict(email=i[2], search_term='{} {} ({})'.format(i[0], i[1], i[2])) for i in submitter_qs]
    #    application_types=ApplicationType.objects.filter(visible=True).values_list('name', flat=True)
    #    data = dict(
    #        regions=region_qs,
    #        #districts=district_qs,
    #        activities=activity_qs,
    #        submitters=submitters,
    #        application_types=application_types,
    #        #processing_status_choices = [i[1] for i in Proposal.PROCESSING_STATUS_CHOICES],
    #        #processing_status_id_choices = [i[0] for i in Proposal.PROCESSING_STATUS_CHOICES],
    #        #customer_status_choices = [i[1] for i in Proposal.CUSTOMER_STATUS_CHOICES],
    #        approval_status_choices = [i[1] for i in Approval.STATUS_CHOICES],
    #    )
    #    return Response(data)

    @detail_route(methods=['POST'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def process_electoral_roll_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='electoral_roll_document')
        if returned_data:
            return add_cache_control(Response(returned_data))
        else:
            return add_cache_control(Response())

    @detail_route(methods=['POST'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def process_vessel_registration_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='vessel_registration_document')
        if returned_data:
            return add_cache_control(Response(returned_data))
        else:
            return add_cache_control(Response())

    @detail_route(methods=['POST'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def process_hull_identification_number_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='hull_identification_number_document')
        if returned_data:
            return add_cache_control(Response(returned_data))
        else:
            return add_cache_control(Response())

    @detail_route(methods=['POST'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def process_insurance_certificate_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='insurance_certificate_document')
        if returned_data:
            return add_cache_control(Response(returned_data))
        else:
            return add_cache_control(Response())

    @detail_route(methods=['GET',])
    def compare_list(self, request, *args, **kwargs):
        """ Returns the reversion-compare urls --> list"""
        current_revision_id = Version.objects.get_for_object(self.get_object()).first().revision_id
        versions = Version.objects.get_for_object(self.get_object()).select_related("revision__user").filter(Q(revision__comment__icontains='status') | Q(revision_id=current_revision_id))
        version_ids = [i.id for i in versions]
        urls = ['?version_id2={}&version_id1={}'.format(version_ids[0], version_ids[i+1]) for i in range(len(version_ids)-1)]
        return add_cache_control(Response(urls))

    @detail_route(methods=['GET',])
    def action_log(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            qs = instance.action_logs.all()
            serializer = ProposalUserActionSerializer(qs,many=True)
            return add_cache_control(Response(serializer.data))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',])
    def comms_log(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            qs = instance.comms_logs.all()
            serializer = ProposalLogEntrySerializer(qs,many=True)
            return add_cache_control(Response(serializer.data))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',])
    @renderer_classes((JSONRenderer,))
    def add_comms_log(self, request, *args, **kwargs):
        try:
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
                    document = comms.documents.create()
                    document.name = str(request.FILES[f])
                    document._file = request.FILES[f]
                    document.save()
                # End Save Documents

                return add_cache_control(Response(serializer.data))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',])
    def requirements(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            #qs = instance.requirements.all()
            qs = instance.requirements.all().exclude(is_deleted=True)
            qs=qs.order_by('order')
            serializer = ProposalRequirementSerializer(qs,many=True, context={'request':request})
            return add_cache_control(Response(serializer.data))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',])
    def amendment_request(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            qs = instance.amendment_requests
            qs = qs.filter(status = 'requested')
            serializer = AmendmentRequestDisplaySerializer(qs,many=True)
            return add_cache_control(Response(serializer.data))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @list_route(methods=['GET',])
    def user_list(self, request, *args, **kwargs):
        qs = self.get_queryset().exclude(processing_status='discarded')
        #serializer = DTProposalSerializer(qs, many=True)
        serializer = ListProposalSerializer(qs,context={'request':request}, many=True)
        return add_cache_control(Response(serializer.data))

    @list_route(methods=['GET',])
    def user_list_paginated(self, request, *args, **kwargs):
        """
        Placing Paginator class here (instead of settings.py) allows specific method for desired behaviour),
        otherwise all serializers will use the default pagination class

        https://stackoverflow.com/questions/29128225/django-rest-framework-3-1-breaks-pagination-paginationserializer
        """
        proposals = self.get_queryset().exclude(processing_status='discarded')
        paginator = DatatablesPageNumberPagination()
        paginator.page_size = proposals.count()
        result_page = paginator.paginate_queryset(proposals, request)
        serializer = ListProposalSerializer(result_page, context={'request':request}, many=True)
        return add_cache_control(paginator.get_paginated_response(serializer.data))

    @detail_route(methods=['GET',])
    def internal_proposal(self, request, *args, **kwargs):
        instance = self.get_object()
        # serializer = InternalProposalSerializer(instance,context={'request':request})
        # if instance.application_type.name==ApplicationType.TCLASS:
        #     serializer = InternalProposalSerializer(instance,context={'request':request})
        # elif instance.application_type.name==ApplicationType.FILMING:
        #     serializer = InternalFilmingProposalSerializer(instance,context={'request':request})
        # elif instance.application_type.name==ApplicationType.EVENT:
        #     serializer = InternalEventProposalSerializer(instance,context={'request':request})
        serializer = InternalProposalSerializer(instance, context={'request': request})
        return add_cache_control(Response(serializer.data))

    #@detail_route(methods=['post'])
    #@renderer_classes((JSONRenderer,))
    #def submit(self, request, *args, **kwargs):
    #    try:
    #        instance = self.get_object()
    #        #instance.submit(request,self)
    #        proposal_submit(instance, request)
    #        instance.save()
    #        serializer = self.get_serializer(instance)
    #        return Response(serializer.data)
    #        #return redirect(reverse('external'))
    #    except serializers.ValidationError:
    #        print(traceback.print_exc())
    #        raise
    #    except ValidationError as e:
    #        if hasattr(e,'error_dict'):
    #            raise serializers.ValidationError(repr(e.error_dict))
    #        else:
    #            if hasattr(e,'message'):
    #                raise serializers.ValidationError(e.message)
    #    except Exception as e:
    #        print(traceback.print_exc())
    #        raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def assign_request_user(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.assign_officer(request, request.user)
        #serializer = InternalProposalSerializer(instance,context={'request':request})
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance,context={'request':request})
        return add_cache_control(Response(serializer.data))
        raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def assign_to(self, request, *args, **kwargs):
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
        #serializer = InternalProposalSerializer(instance,context={'request':request})
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance,context={'request':request})
        return add_cache_control(Response(serializer.data))

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def unassign(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.unassign(request)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance,context={'request':request})
        return add_cache_control(Response(serializer.data))

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def switch_status(self, request, *args, **kwargs):
        instance = self.get_object()
        status = request.data.get('status')
        approver_comment = request.data.get('approver_comment')
        instance.move_to_status(request, status, approver_comment)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance,context={'request':request})
        return add_cache_control(Response(serializer.data))

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def reissue_approval(self, request, *args, **kwargs):
        instance = self.get_object()
        status = request.data.get('status')
        if not status:
            raise serializers.ValidationError('Status is required')
        else:
            if instance.application_type.name==ApplicationType.FILMING and instance.filming_approval_type=='lawful_authority':
                status='with_assessor'
            else:
                if not status in ['with_approver']:
                    raise serializers.ValidationError('The status provided is not allowed')
        instance.reissue_approval(request,status)
        serializer = InternalProposalSerializer(instance,context={'request':request})
        return add_cache_control(Response(serializer.data))

    # TODO: should be post?
    @detail_route(methods=['GET',])
    @basic_exception_handler
    def renew_amend_approval_wrapper(self, request, *args, **kwargs):
        instance = self.get_object()
        approval = instance.approval
        ## validation
        renew_amend_conditions = {
        'previous_application': instance,
        #'proposal_type': ProposalType.objects.get(code=PROPOSAL_TYPE_AMENDMENT)
        }
        existing_proposal_qs=Proposal.objects.filter(**renew_amend_conditions)
        if (existing_proposal_qs and 
                existing_proposal_qs[0].customer_status in ['under_review', 'with_assessor', 'draft'] and
                existing_proposal_qs[0].proposal_type in ProposalType.objects.filter(code__in=[PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL])
                ):
            #raise ValidationError('A renewal/amendment for this licence has already been lodged and is awaiting review.')
            raise ValidationError('A renewal/amendment for this licence has already been lodged.')
        ## create renewal or amendment
        if approval and approval.renewal_document and approval.renewal_sent: # and approval.can_renew:
            instance = instance.renew_approval(request)
        else:
            instance = instance.amend_approval(request)
        ## return new application
        serializer = SaveProposalSerializer(instance,context={'request':request})
        return Response(serializer.data)

    ## TODO: should be post?
    #@detail_route(methods=['GET',])
    #@basic_exception_handler
    #def renew_approval(self, request, *args, **kwargs):
    #    instance = self.get_object()
    #    instance = instance.renew_approval(request)
    #    serializer = SaveProposalSerializer(instance,context={'request':request})
    #    return Response(serializer.data)

    #@detail_route(methods=['GET',])
    #@basic_exception_handler
    #def amend_approval(self, request, *args, **kwargs):
    #    instance = self.get_object()
    #    instance = instance.amend_approval(request)
    #    serializer = SaveProposalSerializer(instance,context={'request':request})
    #    return Response(serializer.data)

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def proposed_approval(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ProposedApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.proposed_approval(request, serializer.validated_data)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance,context={'request':request})
        return add_cache_control(Response(serializer.data))

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def approval_level_document(self, request, *args, **kwargs):
        instance = self.get_object()
        instance = instance.assing_approval_level_document(request)
        serializer = InternalProposalSerializer(instance,context={'request':request})
        return add_cache_control(Response(serializer.data))

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def final_approval(self, request, *args, **kwargs):
        print('final_approval() in ProposalViewSet')
        instance = self.get_object()
        serializer = ProposedApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.final_approval(request, serializer.validated_data)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={'request': request})
        print(serializer.data)
        return add_cache_control(Response(serializer.data))

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def proposed_decline(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ProposedDeclineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.proposed_decline(request,serializer.validated_data)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance,context={'request':request})
        return add_cache_control(Response(serializer.data))

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def final_decline(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ProposedDeclineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.final_decline(request,serializer.validated_data)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={'request':request})
        return add_cache_control(Response(serializer.data))

    #@detail_route(methods=['POST',])
    #@renderer_classes((JSONRenderer,))
    #def on_hold(self, request, *args, **kwargs):
    #    try:
    #        with transaction.atomic():
    #            instance = self.get_object()
    #            is_onhold =  eval(request.data.get('onhold'))
    #            data = {}
    #            if is_onhold:
    #                data['type'] = u'onhold'
    #                instance.on_hold(request)
    #            else:
    #                data['type'] = u'onhold_remove'
    #                instance.on_hold_remove(request)

    #            data['proposal'] = u'{}'.format(instance.id)
    #            data['staff'] = u'{}'.format(request.user.id)
    #            data['text'] = request.user.get_full_name() + u': {}'.format(request.data['text'])
    #            data['subject'] = request.user.get_full_name() + u': {}'.format(request.data['text'])
    #            serializer = ProposalLogEntrySerializer(data=data)
    #            serializer.is_valid(raise_exception=True)
    #            comms = serializer.save()

    #            # save the files
    #            documents_qs = instance.onhold_documents.filter(input_name='on_hold_file', visible=True)
    #            for f in documents_qs:
    #                document = comms.documents.create(_file=f._file, name=f.name)
    #                #document = comms.documents.create()
    #                #document.name = f.name
    #                #document._file = f._file #.strip('/media')
    #                document.input_name = f.input_name
    #                document.can_delete = True
    #                document.save()
    #            # end save documents

    #            return Response(serializer.data)
    #    except serializers.ValidationError:
    #        print(traceback.print_exc())
    #        raise
    #    except ValidationError as e:
    #        print(traceback.print_exc())
    #        raise serializers.ValidationError(repr(e.error_dict))
    #    except Exception as e:
    #        print(traceback.print_exc())
    #        raise serializers.ValidationError(str(e))

    @detail_route(methods=['post'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def draft(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            save_proponent_data(instance,request,self)
            return add_cache_control(redirect(reverse('external')))

    @detail_route(methods=['post'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def submit(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            save_proponent_data(instance,request,self)
            #proposal_submit(instance, request)
            #return redirect(reverse('external'))
            #return Response(status_code=status.HTTP_200_OK)
            return add_cache_control(Response())

    @detail_route(methods=['GET',])
    def fetch_vessel(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            vessel_details = instance.vessel_details
            vessel_details_serializer = VesselDetailsSerializer(vessel_details, context={'request': request})
            vessel = vessel_details.vessel
            vessel_serializer = VesselSerializer(vessel)
            vessel_data = vessel_serializer.data
            vessel_ownership_data = {}
            if not instance.editable_vessel_details:
                ## 20210419 - we no longer do this
                #vessel_ownership = vessel_details.blocking_proposal.vessel_ownership
                #vessel_ownership_serializer = VesselOwnershipSerializer(vessel_ownership)
                #vessel_ownership_data = deepcopy(vessel_ownership_serializer.data)
                #vessel_ownership_data["registered_owner"] = vessel_ownership.org_name if vessel_ownership.org_name else str(vessel_ownership.owner)
                # lookup vessels must be marked as read-only
                #vessel_data["read_only"] = True
                vessel_data["rego_no"] = vessel.rego_no
            #else:
            vessel_ownership_data = {}
            vessel_ownership = instance.vessel_ownership
            if vessel_ownership:
                vessel_ownership_serializer = VesselOwnershipSerializer(vessel_ownership)
                vessel_ownership_data = deepcopy(vessel_ownership_serializer.data)
                vessel_ownership_data["individual_owner"] = False if vessel_ownership.company_ownership else True
            else:
                vessel_ownership_data["percentage"] = instance.percentage
                vessel_ownership_data["individual_owner"] = instance.individual_owner
                #if instance.company_ownership:
                 #   vessel_ownership_data["company_ownership"] = CompanyOwnershipSerializer(instance.company_ownership).data
            vessel_data["vessel_details"] = vessel_details_serializer.data
            vessel_data["vessel_ownership"] = vessel_ownership_data
            return add_cache_control(Response(vessel_data))
        except Exception as e:
            print(traceback.print_exc())
            if hasattr(e,'message'):
                raise serializers.ValidationError(e.message)

    @detail_route(methods=['post'])
    @renderer_classes((JSONRenderer,))
    def assessor_save(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            save_assessor_data(instance,request,self)
            return add_cache_control(redirect(reverse('external')))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    def create(self, request, *args, **kwargs):
        raise NotImplementedError("Parent objects should not be created directly")

    def update(self, request, *args, **kwargs):
        try:
            http_status = status.HTTP_200_OK
            instance = self.get_object()
            #if application_name==ApplicationType.TCLASS:
            #    serializer = SaveProposalSerializer(instance,data=request.data)
            #elif application_name==ApationType.FILMING:
            #    serializer=ProposalFilmingOtherDetailsSerializer(data=other_details_data)
            #elif application_name==ApplicationType.EVENT:
            #    serializer=ProposalEventOtherDetailsSerializer(data=other_details_data)

            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return add_cache_control(Response(serializer.data))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    #def destroy(self, request, *args, **kwargs):
    def bak_destroy(self, request, *args, **kwargs):
        try:
            http_status = status.HTTP_200_OK
            instance = self.get_object()
            if instance.is_submitted:
                # This proposal has been submitted at least once.  Therefore we update its status to 'discarded' rather than deleting it.
                serializer = SaveProposalSerializer(instance, {
                    'processing_status': Proposal.PROCESSING_STATUS_DISCARDED,
                    'previous_application': None
                }, partial=True)
                serializer.is_valid(raise_exception=True)
                self.perform_update(serializer)
                return Response(serializer.data, status=http_status)
            else:
                # This proposal has not been submitted yet, we can delete it from the database
                instance.delete()
                return Response({})

        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    #@detail_route(methods=['post'])
    #@renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def destroy(self, request, *args, **kwargs):
        #import ipdb; ipdb.set_trace()
        instance = self.get_object()
        instance.processing_status = Proposal.PROCESSING_STATUS_DISCARDED
        instance.customer_status = Proposal.CUSTOMER_STATUS_DISCARDED
        # TODO: why do we need this?
        instance.previous_application = None
        instance.save()
        return Response()


class ProposalRequirementViewSet(viewsets.ModelViewSet):
    #queryset = ProposalRequirement.objects.all()
    queryset = ProposalRequirement.objects.none()
    serializer_class = ProposalRequirementSerializer

    def get_queryset(self):
        qs = ProposalRequirement.objects.all().exclude(is_deleted=True)
        return qs

    @detail_route(methods=['GET',])
    def move_up(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.up()
            instance.save()
            serializer = self.get_serializer(instance)
            return add_cache_control(Response(serializer.data))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',])
    def move_down(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.down()
            instance.save()
            serializer = self.get_serializer(instance)
            return add_cache_control(Response(serializer.data))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',])
    def discard(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.is_deleted = True
            instance.save()
            serializer = self.get_serializer(instance)
            return add_cache_control(Response(serializer.data))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',])
    @renderer_classes((JSONRenderer,))
    def delete_document(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            RequirementDocument.objects.get(id=request.data.get('id')).delete()
            return add_cache_control(Response([dict(id=i.id, name=i.name,_file=i._file.url) for i in instance.requirement_documents.all()]))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            #import ipdb; ipdb.set_trace()
            #serializer = self.get_serializer(instance, data=json.loads(request.data.get('data')))
            serializer = self.get_serializer(instance, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            #instance.add_documents(request)
            return Response(serializer.data)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    def create(self, request, *args, **kwargs):
        try:
#            data = {
#                'due_date': request.data.get('due_date'),
#                'standard': request.data.get('standard'),
#                'recurrence': reqeust.data.get('recurrence'),
#                'recurrence_pattern': request.data.get('recurrence_pattern'),
#                'proposal': request.data.get('proposal'),
#                'referral_group': request.data.get('referral_group'),
#            }
            #import ipdb; ipdb.set_trace()
            serializer = self.get_serializer(data= request.data)
            #serializer = self.get_serializer(data=json.loads(request.data.get('data')))
            #serializer = self.get_serializer(data=data)
            #serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception = True)
            instance = serializer.save()
            #instance.add_documents(request)
            #serializer = self.get_serializer(instance)
            return add_cache_control(Response(serializer.data))
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


class ProposalStandardRequirementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProposalStandardRequirement.objects.all()
    serializer_class = ProposalStandardRequirementSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(text__icontains=search)
        serializer = self.get_serializer(queryset, many=True)
        return add_cache_control(Response(serializer.data))


class AmendmentRequestViewSet(viewsets.ModelViewSet):
    queryset = AmendmentRequest.objects.all()
    serializer_class = AmendmentRequestSerializer

    @basic_exception_handler
    def create(self, request, *args, **kwargs):
        data = request.data
        reason_id = request.data.get('reason_id')
        proposal = request.data.get('proposal', None)
        data['reason'] = reason_id
        data['proposal'] = proposal['id']
        # data = {
        #     #'schema': qs_proposal_type.order_by('-version').first().schema,
        #     'text': request.data.get('text'),
        #     'proposal': request.data.get('proposal'),
        #     'reason': AmendmentReason.objects.get(id=reason_id) if reason_id else None,
        # }
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception = True)
        instance = serializer.save()
        instance.generate_amendment(request)
        serializer = self.get_serializer(instance)
        return add_cache_control(Response(serializer.data))


#class AccreditationTypeView(views.APIView):
#
#    renderer_classes = [JSONRenderer,]
#    def get(self,request, format=None):
#        choices_list = []
#        #choices = ProposalOtherDetails.ACCREDITATION_TYPE_CHOICES
#        choices=ProposalAccreditation.ACCREDITATION_TYPE_CHOICES
#        if choices:
#            for c in choices:
#                choices_list.append({'key': c[0],'value': c[1]})
#        return Response(choices_list)
#
#class LicencePeriodChoicesView(views.APIView):
#
#    renderer_classes = [JSONRenderer,]
#    def get(self,request, format=None):
#        choices_list = []
#        choices = ProposalOtherDetails.LICENCE_PERIOD_CHOICES
#        if choices:
#            for c in choices:
#                choices_list.append({'key': c[0],'value': c[1]})
#        return Response(choices_list)


class AmendmentRequestReasonChoicesView(views.APIView):

    renderer_classes = [JSONRenderer,]
    def get(self,request, format=None):
        choices_list = []
        #choices = AmendmentRequest.REASON_CHOICES
        choices=AmendmentReason.objects.all()
        if choices:
            for c in choices:
                #choices_list.append({'key': c[0],'value': c[1]})
                choices_list.append({'key': c.id,'value': c.reason})
        return add_cache_control(Response(choices_list))


class SearchKeywordsView(views.APIView):
    renderer_classes = [JSONRenderer,]
    def post(self,request, format=None):
        qs = []
        searchWords = request.data.get('searchKeywords')
        searchProposal = request.data.get('searchProposal')
        searchApproval = request.data.get('searchApproval')
        searchCompliance = request.data.get('searchCompliance')
        if searchWords:
            qs= searchKeyWords(searchWords, searchProposal, searchApproval, searchCompliance)
        #queryset = list(set(qs))
        serializer = SearchKeywordSerializer(qs, many=True)
        return add_cache_control(Response(serializer.data))

class SearchReferenceView(views.APIView):
    renderer_classes = [JSONRenderer,]
    def post(self,request, format=None):
        try:
            qs = []
            reference_number = request.data.get('reference_number')
            if reference_number:
                qs= search_reference(reference_number)
            #queryset = list(set(qs))
            serializer = SearchReferenceSerializer(qs)
            return add_cache_control(Response(serializer.data))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            if hasattr(e,'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            else:
                print(e)
                if hasattr(e,'message'):
                    raise serializers.ValidationError(e.message)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))


class VesselOwnershipViewSet(viewsets.ModelViewSet):
    queryset = VesselOwnership.objects.all().order_by('id')
    serializer_class = VesselOwnershipSerializer

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def lookup_vessel_ownership(self, request, *args, **kwargs):
        vo = self.get_object()
        vessel_details = vo.vessel.latest_vessel_details
        #vessel_details_serializer = VesselDetailsSerializer(vessel_details)
        vessel_details_serializer = VesselDetailsSerializer(vessel_details, context={'request': request})
        vessel = vo.vessel
        vessel_serializer = VesselSerializer(vessel)
        vessel_data = vessel_serializer.data
        vessel_data["vessel_details"] = vessel_details_serializer.data

        # vessel_ownership
        vessel_ownership_data = {}
        vessel_ownership_serializer = VesselOwnershipSerializer(vo)
        vessel_ownership_data = deepcopy(vessel_ownership_serializer.data)
        #vessel_ownership_data["registered_owner"] = vessel_ownership.org_name if vessel_ownership.org_name else str(vessel_ownership.owner)
        #vessel_ownership_data["individual_owner"] = False if vo.org_name else True
        vessel_ownership_data["individual_owner"] = False if vo.company_ownership else True
        #vessel_data["read_only"] = True
        vessel_data["vessel_ownership"] = vessel_ownership_data
        return add_cache_control(Response(vessel_data))

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def record_sale(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            sale_date = request.data.get('sale_date')
            if sale_date:
                ## setting the end_date "removes" the vessel from current Approval records
                serializer = SaveVesselOwnershipSaleDateSerializer(instance, {"end_date": sale_date})
                serializer.is_valid(raise_exception=True)
                serializer.save()
                ## collect impacted Approvals
                approval_list = []
                for prop in instance.proposal_set.all():
                    if (
                            prop.approval and 
                            prop.approval.status == 'current'
                            ):
                        if prop.approval not in approval_list:
                            approval_list.append(prop.approval)
                ## change Sticker status
                stickers = []
                for approval in approval_list:
                    ## send notification email
                    send_vessel_nomination_notification_main(approval)
                    # add to stickers list
                    #stickers.append(approval.stickers.filter(status='current'))
                    for a_sticker in approval.stickers.filter(status='current'):
                        stickers.append(a_sticker)
                for sticker in stickers:
                    sticker.status = 'to_be_returned'
                    sticker.save()
            else:
                raise serializers.ValidationError("Missing information: You must specify a sale date")
            return Response()

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def fetch_sale_date(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = VesselOwnershipSaleDateSerializer(instance)
        return Response(serializer.data)


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all().order_by('id')
    serializer_class = CompanySerializer

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def lookup_company_ownership(self, request, *args, **kwargs):
        company = self.get_object()
        #serializer = CompanySerializer(company)
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
            #co = co_list.order_by(updated)[0]
            if co_list:
                co = co_list[0]
                serializer = CompanyOwnershipSerializer(co)
                return add_cache_control(Response(serializer.data))
            else:
                return add_cache_control(Response(empty_co))
        return add_cache_control(Response(empty_co))


class CompanyOwnershipViewSet(viewsets.ModelViewSet):
    queryset = CompanyOwnership.objects.all().order_by('id')
    serializer_class = CompanyOwnershipSerializer

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def lookup_company_ownership(self, request, *args, **kwargs):
        vessel = self.get_object()
        vessel_details = vessel.latest_vessel_details
        #vessel_details_serializer = VesselDetailsSerializer(vessel_details)
        vessel_details_serializer = VesselDetailsSerializer(vessel_details, context={'request': request})
        vessel_serializer = VesselSerializer(vessel)
        vessel_data = vessel_serializer.data
        vessel_data["vessel_details"] = vessel_details_serializer.data
        #vessel_ownership_data = {}
        #if vessel_details.blocking_proposal:
            #vessel_ownership = vessel_details.blocking_proposal.vessel_ownership
            #vessel_ownership_serializer = VesselOwnershipSerializer(vessel_ownership)
            #vessel_ownership_data = deepcopy(vessel_ownership_serializer.data)
            #vessel_ownership_data["registered_owner"] = vessel_ownership.org_name if vessel_ownership.org_name else str(vessel_ownership.owner)

        #vessel_data["vessel_ownership"] = vessel_ownership_data
        # lookup vessels must be marked as read-only

        # vessel_ownership
        vessel_ownership_data = {}
        # check if this emailuser has a matching record for this vessel
        owner_qs = Owner.objects.filter(emailuser=request.user)
        if owner_qs:
            owner = owner_qs[0]
            vo_qs = vessel.vesselownership_set.filter(owner=owner)
            if vo_qs:
                vessel_ownership = vo_qs[0]
                vessel_ownership_serializer = VesselOwnershipSerializer(vessel_ownership)
                vessel_ownership_data = deepcopy(vessel_ownership_serializer.data)
                #vessel_ownership_data["individual_owner"] = False if vessel_ownership.org_name else True
                vessel_ownership_data["individual_owner"] = False if vessel_ownership.company_ownership else True
        #vessel_data["read_only"] = True
        vessel_data["vessel_ownership"] = vessel_ownership_data
        return add_cache_control(Response(vessel_data))

    ##@renderer_classes((JSONRenderer,))
    #@basic_exception_handler
    #def create(self, request, *args, **kwargs):
    #    #import ipdb; ipdb.set_trace()
    #    with transaction.atomic():
    #        #save_bare_vessel_data(request)
    #        vessel_data = save_bare_vessel_data(request)
    #        return add_cache_control(Response(vessel_data))
    #        #return add_cache_control(redirect(reverse('external')))

    ##@renderer_classes((JSONRenderer,))
    #@basic_exception_handler
    #def update(self, request, *args, **kwargs):
    #    #import ipdb; ipdb.set_trace()
    #    with transaction.atomic():
    #        instance = self.get_object()
    #        vessel_data = save_bare_vessel_data(request, instance)
    #        return add_cache_control(Response(vessel_data))


class VesselViewSet(viewsets.ModelViewSet):
    queryset = Vessel.objects.all().order_by('id')
    serializer_class = VesselSerializer

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def find_related_bookings(self, request, *args, **kwargs):
        vessel = self.get_object()
        #import ipdb; ipdb.set_trace()
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

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def find_related_approvals(self, request, *args, **kwargs):
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
        #return Response()

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def lookup_vessel_ownership(self, request, *args, **kwargs):
        vessel = self.get_object()
        serializer = VesselFullOwnershipSerializer(vessel.filtered_vesselownership_set.all(), many=True)
        return Response(serializer.data)

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def comms_log(self, request, *args, **kwargs):
        instance = self.get_object()
        qs = instance.comms_logs.all()
        serializer = VesselLogEntrySerializer(qs,many=True)
        return Response(serializer.data)

    @detail_route(methods=['POST',])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def add_comms_log(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            mutable=request.data._mutable
            request.data._mutable=True
            #request.data['proposal'] = u'{}'.format(instance.id)
            #request.data['staff'] = u'{}'.format(request.user.id)
            request.data['vessel'] = u'{}'.format(instance.id)
            request.data._mutable=mutable
            serializer = VesselLogEntrySerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            comms = serializer.save()
            # Save the files
            for f in request.FILES:
                document = comms.documents.create()
                document.name = str(request.FILES[f])
                document._file = request.FILES[f]
                document.save()
            # End Save Documents

            return Response(serializer.data)


    @detail_route(methods=['GET',])
    @basic_exception_handler
    def action_log(self, request, *args, **kwargs):
        #instance = self.get_object()
        #qs = instance.action_logs.all()
        #serializer = ProposalUserActionSerializer(qs,many=True)
        #return add_cache_control(Response(serializer.data))
        return Response([])

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def lookup_individual_ownership(self, request, *args, **kwargs):
        vessel = self.get_object()
        owner_set = Owner.objects.filter(emailuser=request.user)
        if owner_set:
            vo_set = vessel.filtered_vesselownership_set.filter(owner=owner_set[0], vessel=vessel, company_ownership=None)
            if vo_set:
                serializer = VesselOwnershipSerializer(vo_set[0])
                return add_cache_control(Response(serializer.data))
            else:
                return add_cache_control(Response())
        return add_cache_control(Response())

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def full_details(self, request, *args, **kwargs):
        vessel = self.get_object()
        return Response(VesselFullSerializer(vessel).data)
 
    @detail_route(methods=['GET',])
    @basic_exception_handler
    def lookup_vessel(self, request, *args, **kwargs):
        vessel = self.get_object()
        vessel_details = vessel.latest_vessel_details
        #vessel_details_serializer = VesselDetailsSerializer(vessel_details)
        vessel_details_serializer = VesselDetailsSerializer(vessel_details, context={'request': request})
        vessel_serializer = VesselSerializer(vessel)
        vessel_data = vessel_serializer.data
        vessel_data["vessel_details"] = vessel_details_serializer.data
        #vessel_ownership_data = {}
        #if vessel_details.blocking_proposal:
            #vessel_ownership = vessel_details.blocking_proposal.vessel_ownership
            #vessel_ownership_serializer = VesselOwnershipSerializer(vessel_ownership)
            #vessel_ownership_data = deepcopy(vessel_ownership_serializer.data)
            #vessel_ownership_data["registered_owner"] = vessel_ownership.org_name if vessel_ownership.org_name else str(vessel_ownership.owner)

        #vessel_data["vessel_ownership"] = vessel_ownership_data
        # lookup vessels must be marked as read-only

        # vessel_ownership
        vessel_ownership_data = {}
        # check if this emailuser has a matching record for this vessel
        owner_qs = Owner.objects.filter(emailuser=request.user)
        if owner_qs:
            owner = owner_qs[0]
            vo_qs = vessel.vesselownership_set.filter(owner=owner)
            if vo_qs:
                vessel_ownership = vo_qs[0]
                vessel_ownership_serializer = VesselOwnershipSerializer(vessel_ownership)
                vessel_ownership_data = deepcopy(vessel_ownership_serializer.data)
                #vessel_ownership_data["individual_owner"] = False if vessel_ownership.org_name else True
                vessel_ownership_data["individual_owner"] = False if vessel_ownership.company_ownership else True
        #vessel_data["read_only"] = True
        vessel_data["vessel_ownership"] = vessel_ownership_data
        return add_cache_control(Response(vessel_data))

    #@renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def create(self, request, *args, **kwargs):
        #import ipdb; ipdb.set_trace()
        with transaction.atomic():
            #save_bare_vessel_data(request)
            vessel_data = save_bare_vessel_data(request)
            return add_cache_control(Response(vessel_data))
            #return add_cache_control(redirect(reverse('external')))

    #@renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def update(self, request, *args, **kwargs):
        #import ipdb; ipdb.set_trace()
        with transaction.atomic():
            instance = self.get_object()
            vessel_data = save_bare_vessel_data(request, instance)
            return add_cache_control(Response(vessel_data))

    #@list_route(methods=['GET',])
    #def list_external(self, request, *args, **kwargs):
    #    search_text = request.GET.get('search[value]', '')
    #    owner_qs = Owner.objects.filter(emailuser=request.user)
    #    if owner_qs:
    #        owner = owner_qs[0]
    #        # rewrite following to include VesselOwnership
    #        vessel_details_list = [vessel.latest_vessel_details for vessel in owner.vessels.all()]

    #        if search_text:
    #            search_text = search_text.lower()
    #            search_text_vessel_detail_ids = []
    #            matching_vessel_type_choices = [choice[0] for choice in VESSEL_TYPES if search_text in choice[1].lower()]
    #            for vd in vessel_details_list:
    #                if (search_text in (vd.vessel_name.lower() if vd.vessel_name else '')
    #                    or search_text in (vd.vessel.rego_no.lower() if vd.vessel.rego_no.lower() else '')
    #                    or vd.vessel_type in matching_vessel_type_choices
    #                    ):
    #                    search_text_vessel_detail_ids.append(vd.id)
    #            vessel_details_list = [vd for vd in vessel_details_list if vd.id in search_text_vessel_detail_ids]

    #        serializer = ListVesselSerializer(vessel_details_list, context={'request': request}, many=True)
    #        return add_cache_control(Response(serializer.data))
    #    else:
    #        return Response([])

    @list_route(methods=['GET',])
    def list_external(self, request, *args, **kwargs):
        search_text = request.GET.get('search[value]', '')
        owner_qs = Owner.objects.filter(emailuser=request.user)
        if owner_qs:
            owner = owner_qs[0]
            #vessel_details_list = [vessel.latest_vessel_details for vessel in owner.vessels.all()]
            vessel_ownership_list = owner.vesselownership_set.all()

            # rewrite following for vessel_ownership_list
            if search_text:
                search_text = search_text.lower()
                #search_text_vessel_detail_ids = []
                search_text_vessel_ownership_ids = []
                matching_vessel_type_choices = [choice[0] for choice in VESSEL_TYPES if search_text in choice[1].lower()]
                for vo in vessel_ownership_list:
                    vd = vo.vessel.latest_vessel_details
                    if (search_text in (vd.vessel_name.lower() if vd.vessel_name else '') or
                        search_text in (vd.vessel.rego_no.lower() if vd.vessel.rego_no.lower() else '') or
                        vd.vessel_type in matching_vessel_type_choices or
                        search_text in vo.end_date.strftime('%d/%m/%Y')
                        #or search_text in (vo.org_name.lower() or str(vo.owner).lower())
                        ):
                        search_text_vessel_ownership_ids.append(vo.id)
                #vessel_details_list = [vd for vd in vessel_details_list if vd.id in search_text_vessel_detail_ids]
                vessel_ownership_list = [vo for vo in vessel_ownership_list if vo.id in search_text_vessel_ownership_ids]

            serializer = ListVesselOwnershipSerializer(vessel_ownership_list, context={'request': request}, many=True)
            return add_cache_control(Response(serializer.data))
        else:
            return Response([])


class AssessorChecklistViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ChecklistQuestion.objects.none()
    serializer_class = ChecklistQuestionSerializer

    def get_queryset(self):
        qs=ChecklistQuestion.objects.filter(Q(list_type = 'assessor_list')& Q(obsolete=False))
        return qs


class MooringBayViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MooringBay.objects.none()
    serializer_class = MooringBaySerializer

    def get_queryset(self):
        return MooringBay.objects.filter(active=True)



class MooringFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        total_count = queryset.count()

        #filter_mooring_status = request.GET.get('filter_mooring_status')
        #if filter_mooring_status and not filter_mooring_status.lower() == 'all':
            ##queryset = queryset.filter(customer_status=filter_compliance_status)

        filter_mooring_bay = request.GET.get('filter_mooring_bay')
        if filter_mooring_bay and not filter_mooring_bay.lower() == 'all':
            queryset = queryset.filter(mooring_bay_id=filter_mooring_bay)

        getter = request.query_params.get
        fields = self.get_fields(getter)
        ordering = self.get_ordering(getter, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)

        try:
            queryset = super(MooringFilterBackend, self).filter_queryset(request, queryset, view)
        except Exception as e:
            print(e)
        setattr(view, '_datatables_total_count', total_count)
        return queryset


class MooringRenderer(DatatablesRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if 'view' in renderer_context and hasattr(renderer_context['view'], '_datatables_total_count'):
            data['recordsTotal'] = renderer_context['view']._datatables_total_count
        return super(MooringRenderer, self).render(data, accepted_media_type, renderer_context)


class MooringPaginatedViewSet(viewsets.ModelViewSet):
    filter_backends = (MooringFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    renderer_classes = (MooringRenderer,)
    queryset = Mooring.objects.none()
    serializer_class = ListMooringSerializer
    #search_fields = ['lodgement_number', ]
    page_size = 10

    def get_queryset(self):
        request_user = self.request.user
        qs = Mooring.objects.none()

        if is_internal(self.request):
            qs = Mooring.private_moorings.filter(active=True)

        return qs

    @list_route(methods=['GET',])
    def list_internal(self, request, *args, **kwargs):
        """
        User is accessing /external/ page
        """
        qs = self.get_queryset()
        qs = self.filter_queryset(qs)

        self.paginator.page_size = qs.count()
        result_page = self.paginator.paginate_queryset(qs, request)
        serializer = ListMooringSerializer(result_page, context={'request': request}, many=True)
        return self.paginator.get_paginated_response(serializer.data)


class MooringViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Mooring.objects.none()
    serializer_class = MooringSerializer

    def get_queryset(self):
        return Mooring.objects.filter(active=True)

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def find_related_bookings(self, request, *args, **kwargs):
        mooring = self.get_object()
        #import ipdb; ipdb.set_trace()
        booking_date_str = request.data.get("selected_date")
        booking_date = None
        if booking_date_str:
            booking_date = datetime.strptime(booking_date_str, '%d/%m/%Y').date()
            booking_date = booking_date.strftime('%Y-%m-%d')
        else:
            booking_date = datetime.now().strftime('%Y-%m-%d')
        data = get_bookings(booking_date=booking_date, rego_no=None, mooring_id=mooring.mooring_bookings_id)
        return Response(data)

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def find_related_approvals(self, request, *args, **kwargs):
        mooring = self.get_object()
        selected_date_str = request.data.get("selected_date")
        selected_date = None
        if selected_date_str:
            selected_date = datetime.strptime(selected_date_str, '%d/%m/%Y').date()
        #print(selected_date)
        #vd_set = VesselDetails.filtered_objects.filter(vessel=vessel)
        if selected_date:
            approval_list = mooring.approval_set.filter(start_date__lte=selected_date, expiry_date__gte=selected_date)
        else:
            approval_list = mooring.approval_set.filter(status='current')

        serializer = LookupApprovalSerializer(approval_list, many=True)
        return Response(serializer.data)
        #return Response()

    #@detail_route(methods=['POST',])
    #@basic_exception_handler
    #def find_related_approvals_bak(self, request, *args, **kwargs):
    #    mooring = self.get_object()
    #    selected_date_str = request.data.get("selected_date")
    #    selected_date = None
    #    if selected_date_str:
    #        selected_date = datetime.strptime(selected_date_str, '%d/%m/%Y').date()
    #    #print(selected_date)
    #    #vd_set = VesselDetails.filtered_objects.filter(vessel=vessel)
    #    approval_list = []
    #    prop_set = mooring.proposal_set.filter(Q(processing_status=Proposal.PROCESSING_STATUS_APPROVED) | Q(processing_status=Proposal.PROCESSING_STATUS_PRINTING_STICKER))
    #    if selected_date:
    #        for prop in prop_set:
    #            if (
    #                    prop.approval and 
    #                    #prop.approval.status == 'current'
    #                    prop.approval.start_date >= selected_date and
    #                    selected_date <= prop.approval.expiry_date
    #                    ):
    #                if prop.approval not in approval_list:
    #                    approval_list.append(prop.approval)
    #    else:
    #        for prop in prop_set:
    #            if (
    #                    prop.approval and 
    #                    prop.approval.status == 'current'
    #                    #prop.approval.start_date >= selected_date and
    #                    #selected_date <= prop.approval.expiry_date
    #                    ):
    #                if prop.approval not in approval_list:
    #                    approval_list.append(prop.approval)

    #    serializer = LookupApprovalSerializer(approval_list, many=True)
    #    return Response(serializer.data)
    #    #return Response()

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def comms_log(self, request, *args, **kwargs):
        instance = self.get_object()
        qs = instance.comms_logs.all()
        serializer = MooringLogEntrySerializer(qs,many=True)
        return Response(serializer.data)

    @detail_route(methods=['POST',])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def add_comms_log(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            mutable=request.data._mutable
            request.data._mutable=True
            #request.data['proposal'] = u'{}'.format(instance.id)
            #request.data['staff'] = u'{}'.format(request.user.id)
            request.data['mooring'] = u'{}'.format(instance.id)
            request.data._mutable=mutable
            serializer = MooringLogEntrySerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            comms = serializer.save()
            # Save the files
            for f in request.FILES:
                document = comms.documents.create()
                document.name = str(request.FILES[f])
                document._file = request.FILES[f]
                document.save()
            # End Save Documents

            return Response(serializer.data)

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def action_log(self, request, *args, **kwargs):
        #instance = self.get_object()
        #qs = instance.action_logs.all()
        #serializer = ProposalUserActionSerializer(qs,many=True)
        #return add_cache_control(Response(serializer.data))
        return Response([])

    @list_route(methods=['GET',])
    @basic_exception_handler
    def internal_list(self, request, *args, **kwargs):
        # add security
        mooring_qs = Mooring.private_moorings.filter(active=True)
        #import ipdb; ipdb.set_trace()
        serializer = ListMooringSerializer(mooring_qs, many=True)
        return Response(serializer.data)

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def fetch_mooring_name(self, request, *args, **kwargs):
        # add security
        instance = self.get_object()
        return Response({"name": instance.name})


class ProposalAssessmentViewSet(viewsets.ModelViewSet):
    #queryset = ProposalRequirement.objects.all()
    queryset = ProposalAssessment.objects.all()
    serializer_class = ProposalAssessmentSerializer

    @detail_route(methods=['post'])
    def update_assessment(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            request.data['submitter']= request.user.id
            serializer = ProposalAssessmentSerializer(instance, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            checklist=request.data['checklist']
            if checklist:
                for chk in checklist:
                    try:
                        chk_instance=ProposalAssessmentAnswer.objects.get(id=chk['id'])
                        serializer_chk = ProposalAssessmentAnswerSerializer(chk_instance, data=chk)
                        serializer_chk.is_valid(raise_exception=True)
                        serializer_chk.save()
                    except:
                        raise
            #instance.proposal.log_user_action(ProposalUserAction.ACTION_EDIT_VESSEL.format(instance.id),request)
            return add_cache_control(Response(serializer.data))
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
