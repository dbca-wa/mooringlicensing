from django.db.models.functions import Concat
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q, CharField, Value, Max
from confy import env
import datetime
import pytz
from django.db import transaction
from django.conf import settings
from rest_framework import viewsets, serializers, views, mixins
from rest_framework.decorators import action as detail_route
from rest_framework.decorators import action as list_route
from rest_framework.decorators import renderer_classes
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from ledger_api_client.ledger_models import EmailUserRO as EmailUser
from ledger_api_client.settings_base import TIME_ZONE
from datetime import datetime
from ledger_api_client.managed_models import SystemUser
from ledger_api_client.utils import get_or_create

from django.core.cache import cache
from mooringlicensing import forms
from mooringlicensing.components.proposals.email import send_create_mooring_licence_application_email_notification
from mooringlicensing.components.main.decorators import basic_exception_handler
from mooringlicensing.components.payments_ml.api import logger

from mooringlicensing.components.main.models import ApplicationType
from mooringlicensing.components.payments_ml.models import FeePeriod, FeeSeason, FeeConstructor
from mooringlicensing.components.payments_ml.serializers import (
    DcvPermitSerializer, 
    DcvAdmissionSerializer,
    DcvAdmissionArrivalSerializer, 
    NumberOfPeopleSerializer
)
from mooringlicensing.components.proposals.models import (
    Proposal, 
    MooringLicenceApplication, 
    ProposalType, 
    Mooring, 
    ProposalApplicant
)
from mooringlicensing.components.approvals.models import (
    Approval,
    DcvPermit, DcvOrganisation, DcvVessel, DcvAdmission, DcvAdmissionArrival, AdmissionType, AgeGroup,
    WaitingListAllocation, Sticker, MooringLicence,AuthorisedUserPermit, AnnualAdmissionPermit,
    MooringOnApproval, VesselOwnershipOnApproval, ApprovalUserAction, StickerActionDetail
)
from mooringlicensing.components.approvals.utils import get_wla_allowed
from mooringlicensing.components.main.process_document import (
        process_generic_document, 
        )
from mooringlicensing.components.approvals.serializers import (
    WaitingListAllocationSerializer,
    ApprovalSerializer,
    ApprovalCancellationSerializer,
    ApprovalSuspensionSerializer,
    ApprovalExtensionSerializer,
    ApprovalSurrenderSerializer,
    ApprovalUserActionSerializer,
    ApprovalLogEntrySerializer,
    ListApprovalSerializer,
    DcvOrganisationSerializer,
    DcvVesselSerializer,
    ListDcvPermitSerializer,
    ListDcvAdmissionSerializer, StickerSerializer, StickerActionDetailSerializer,
    ApprovalHistorySerializer, StickerForDcvSaveSerializer,
    StickerPostalAddressSaveSerializer, NonExportedStickerSerializer
)
from mooringlicensing.components.users.utils import get_user_name
from mooringlicensing.helpers import is_customer, is_internal
from mooringlicensing.settings import PROPOSAL_TYPE_NEW, LOV_CACHE_TIMEOUT
from rest_framework_datatables.pagination import DatatablesPageNumberPagination
from rest_framework_datatables.filters import DatatablesFilterBackend

from rest_framework.permissions import IsAuthenticated
from mooringlicensing.components.approvals.permissions import (
    InternalApprovalPermission,
)
from mooringlicensing.components.approvals.models import private_storage

class GetDailyAdmissionUrl(views.APIView):
    #this does not require authentication
    def get(self, request, format=None):
        daily_admission_url = env('DAILY_ADMISSION_PAGE_URL', '')
        data = {'daily_admission_url': daily_admission_url}
        return Response(data)


class GetStickerStatusDict(views.APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, format=None):

        data = []
        for status in Sticker.STATUS_CHOICES:
            if status[0] in Sticker.STATUSES_FOR_FILTER:
                data.append({'id': status[0], 'display': status[1]})
        return Response(data)
    

class GetStickerNonExportedStatusDict(views.APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, format=None):

        data = []
        for status in Sticker.STATUS_CHOICES:
            if status[0] in Sticker.STATUSES_FOR_NON_EXPORTED_FILTER:
                data.append({'id': status[0], 'display': status[1]})
        return Response(data)


class GetFeeSeasonsDict(views.APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, format=None):

        application_type_codes = request.GET.get('application_type_codes', '')

        if application_type_codes:
            application_type_codes = application_type_codes.split(',')
            application_types = []
            for app_code in application_type_codes:
                application_type = ApplicationType.objects.filter(code=app_code)
                if application_type:
                    application_types.append(application_type.first())
            fee_seasons = FeeSeason.objects.filter(application_type__in=application_types)
        else:
            fee_seasons = FeeSeason.objects.all()

        handled = []
        data = []
        for fee_season in fee_seasons:
            if fee_season.start_date not in handled:
                handled.append(fee_season.start_date)
                data.append({
                    'start_date': fee_season.start_date,
                    'name': str(fee_season.start_date.year) + ' - ' + str(fee_season.start_date.year + 1)
                })
        data_sorted = sorted(data, key=lambda x: x['start_date'], reverse=True) if data else []
        return Response(data_sorted)


class GetSticker(views.APIView):
    permission_classes=[InternalApprovalPermission]
    def get(self, request, format=None):

        if is_internal(request):
            search_term = request.GET.get('search_term', '')
            page_number = request.GET.get('page_number', 1)
            items_per_page = 10

            if search_term:
                system_user_ids = list(SystemUser.objects.annotate(full_name=Concat('legal_first_name',Value(" "),'legal_last_name',output_field=CharField()))
                .filter(
                    Q(legal_first_name__icontains=search_term) | Q(legal_last_name__icontains=search_term) | Q(email__icontains=search_term) | Q(full_name__icontains=search_term)
                ).values_list("ledger_id", flat=True))

                proposal_applicant_proposals = list(ProposalApplicant.objects.annotate(full_name=Concat('first_name',Value(" "),'last_name',output_field=CharField()))
                .filter(
                    Q(first_name__icontains=search_term) | Q(last_name__icontains=search_term) | Q(email__icontains=search_term) | Q(full_name__icontains=search_term)
                ).values_list("proposal_id", flat=True))

                data = Sticker.objects.filter(Q(approval__current_proposal__id__in=proposal_applicant_proposals)|Q(approval__submitter__in=system_user_ids)|Q(vessel_ownership__vessel__rego_no__icontains=search_term)|Q(number__icontains=search_term)).exclude(number="")

                paginator = Paginator(data, items_per_page)
                try:
                    current_page = paginator.page(page_number)
                    my_objects = current_page.object_list
                except EmptyPage:
                    my_objects = []

                data_transform = []
                for sticker in my_objects:
                    approval_history = sticker.approvalhistory_set.order_by('id').first()
                    if approval_history and approval_history.approval:
                        data_transform.append({
                            'id': sticker.id,
                            'text': sticker.number,
                            'approval_id': approval_history.approval.id,
                        })
                    elif sticker.approval:
                        data_transform.append({
                            'id': sticker.id,
                            'text': sticker.number,
                            'approval_id': sticker.approval.id,
                        })

                return Response({
                    "results": data_transform,
                    "pagination": {
                        "more": current_page.has_next()
                    }
                })
        return Response()


class GetApprovalTypeDict(views.APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, format=None):
        include_codes = request.GET.get('include_codes', '')
        include_codes = include_codes.split(',')
        cache_title = 'approval_type_dict'
        for code in include_codes:
            cache_title += '_' + code
        data = cache.get(cache_title)
        if not data:
            cache.set(cache_title, Approval.approval_types_dict(include_codes), LOV_CACHE_TIMEOUT)
            data = cache.get(cache_title)
        return Response(data)


class GetApprovalStatusesDict(views.APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, format=None):
        data = cache.get('approval_statuses_dict')
        if not data:
            cache.set('approval_statuses_dict', [{'code': i[0], 'description': i[1]} for i in Approval.STATUS_CHOICES], settings.LOV_CACHE_TIMEOUT)
            data = cache.get('approval_statuses_dict')
        return Response(data)


class GetCurrentSeason(views.APIView):
    """
    Return list of current seasons
    """
    permission_classes=[IsAuthenticated]
    def get(self, request, format=None):
        cache_title = 'current_seasons'
        fee_seasons = cache.get(cache_title)
        fee_seasons = []

        if not fee_seasons:
            today = datetime.now(pytz.timezone(TIME_ZONE)).date()
            fee_constructors = FeeConstructor.get_fee_constructor_by_date(today)
            for fc in fee_constructors:
                obj = {'start_date': fc.fee_season.start_date, 'end_date': fc.fee_season.end_date}
                if obj not in fee_seasons:
                    fee_seasons.append(obj)
            cache.set(cache_title, fee_seasons, LOV_CACHE_TIMEOUT)
        return Response(fee_seasons)


class GetWlaAllowed(views.APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, format=None):
    
        applicant_id = request.user.id
        if is_internal(request):
            applicant_system_id = request.GET.get('applicant_system_id', False)
            if applicant_system_id:
                try:
                    applicant_id = SystemUser.objects.get(id=applicant_system_id).ledger_id.id
                except:
                    applicant_id = request.user.id

        wla_allowed = get_wla_allowed(applicant_id)
        return Response({"wla_allowed": wla_allowed})


class ApprovalFilterBackend(DatatablesFilterBackend):

    def filter_queryset(self, request, queryset, view):

        filter_query = Q()

        #client set form filters
        # status filter
        filter_status = request.data.get('filter_status')
        if filter_status and not filter_status.lower() == 'all':
            filter_query &= Q(status=filter_status)

        # mooring bay filter
        filter_mooring_bay_id = request.data.get('filter_mooring_bay_id')
        if filter_mooring_bay_id and not filter_mooring_bay_id.lower() == 'all':
            filter_query &= Q(current_proposal__preferred_bay__id=filter_mooring_bay_id)

        # holder id filter
        filter_holder_id = request.data.get('filter_holder_id')
        if filter_holder_id and not filter_holder_id.lower() == 'all':
            filter_query &= Q(current_proposal__proposal_applicant__email_user_id=filter_holder_id)

        # max vessel length
        max_vessel_length = request.data.get('max_vessel_length')
        if max_vessel_length:
            filter_query &= Q(current_proposal__vessel_details__vessel_length__lte=float(max_vessel_length))

        # max vessel draft
        max_vessel_draft = request.data.get('max_vessel_draft')
        if max_vessel_draft:
            filter_query &= Q(current_proposal__vessel_details__vessel_draft__lte=float(max_vessel_draft))

        filter_approval_type2 = request.data.get('filter_approval_type2')
        if filter_approval_type2 and not filter_approval_type2.lower() == 'all':
            if filter_approval_type2 == 'ml':
                filter_query &= ~Q(mooringlicence=None)
            elif filter_approval_type2 == 'aup':
                filter_query &= ~Q(authoriseduserpermit=None)
            elif filter_approval_type2 == 'aap':
                filter_query &= ~Q(annualadmissionpermit=None)
            elif filter_approval_type2 == 'wla':
                filter_query &= ~Q(waitinglistallocation=None)

        queryset = queryset.filter(filter_query)
        

        try:
            super_queryset = super(ApprovalFilterBackend, self).filter_queryset(request, queryset, view)

            # Custom search
            search_text= request.data.get('search[value]')  # This has a search term.
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

                #Search by vessel registration
                queryset = queryset.filter(
                    Q(current_proposal__id__in=proposal_applicant_proposals)|
                    Q(current_proposal__submitter__in=system_user_ids)|
                    Q(id__in=VesselOwnershipOnApproval.objects.filter(vessel_ownership__vessel__rego_no__icontains=search_text).values_list('approval__id', flat=True))|
                    Q(current_proposal__vessel_details__vessel__rego_no__icontains=search_text)
                )

                queryset = queryset.distinct() | super_queryset 
        except Exception as e:
            logger.error(e)

        fields = self.get_fields(request)
        ordering = self.get_ordering(request, view, fields)

        #special handling for ordering by holder
        special_ordering = False
        HOLDER = 'current_proposal__proposal_applicant'
        REVERSE_HOLDER = '-current_proposal__proposal_applicant'
        if HOLDER in ordering:
            special_ordering = True
            ordering.remove(HOLDER)
            queryset = queryset.annotate(current_proposal__proposal_applicant=Concat('current_proposal__proposal_applicant__first_name',Value(" "),'current_proposal__proposal_applicant__last_name'))
            queryset = queryset.order_by(HOLDER)
        if REVERSE_HOLDER in ordering:
            special_ordering = True
            ordering.remove(REVERSE_HOLDER)
            queryset = queryset.annotate(current_proposal__proposal_applicant=Concat('current_proposal__proposal_applicant__first_name',Value(" "),'current_proposal__proposal_applicant__last_name'))
            queryset = queryset.order_by(REVERSE_HOLDER)

        if len(ordering):
            queryset = queryset.order_by(*ordering)
        elif not special_ordering:
            queryset = queryset.order_by('-id')

        total_count = queryset.count()
        setattr(view, '_datatables_filtered_count', total_count)
        return queryset


class ApprovalPaginatedViewSet(viewsets.ReadOnlyModelViewSet):

    filter_backends = (ApprovalFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    queryset = Approval.objects.none()
    serializer_class = ListApprovalSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        request_user = self.request.user
        all = Approval.objects.all()

        if is_internal(self.request):
            target_email_user_id = int(self.request.GET.get('target_email_user_id', 0))
            if target_email_user_id:
                target_user = EmailUser.objects.get(id=target_email_user_id)
                all = all.filter(
                    Q(current_proposal__proposal_applicant__email_user_id=target_user.id)
                )

            for_swap_moorings_modal = self.request.GET.get('for_swap_moorings_modal', 'false')
            for_swap_moorings_modal = True if for_swap_moorings_modal.lower() in ['true', 'yes', 'y', ] else False
            if for_swap_moorings_modal:
                all = all.filter(
                    Q(current_proposal__processing_status__in=[Proposal.PROCESSING_STATUS_APPROVED,Proposal.PROCESSING_STATUS_DISCARDED,Proposal.PROCESSING_STATUS_DECLINED, Proposal.PROCESSING_STATUS_EXPIRED]) & 
                    Q(status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,])
                )
            return all
        elif is_customer(self.request):
            qs = all.filter(
                Q(current_proposal__proposal_applicant__email_user_id=request_user.id)
            )
            return qs
        return Approval.objects.none()
    
    #POST list route for handling certain filters 
    @list_route(methods=['POST',], detail=False)
    def list2(self, request, *args, **kwargs):

        queryset = self.get_queryset()

        #Default filters - i.e. not specified by client-side filters
        filter_query = Q()
        # Show/Hide expired and/or surrendered
        show_expired_surrendered = request.data.get('show_expired_surrendered', 'true')
        show_expired_surrendered = True if show_expired_surrendered.lower() in ['true', 'yes', 't', 'y',] else False
        external_waiting_list = request.data.get('external_waiting_list', 'false')
        external_waiting_list = True if external_waiting_list.lower() in ['true', 'yes', 't', 'y',] else False
        if external_waiting_list and not show_expired_surrendered:
            filter_query &= Q(status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.INTERNAL_STATUS_OFFERED))
        
        # Filter by approval types (wla, aap, aup, ml)
        filter_approval_type = request.data.get('filter_approval_type')
        if filter_approval_type and not filter_approval_type.lower() == 'all':
            filter_approval_type_list = filter_approval_type.split(',')
            if 'wla' in filter_approval_type_list:
                filter_query &= ~Q(waitinglistallocation=None)
            else:
                filter_query &= Q(
                    ~Q(authoriseduserpermit=None) |
                    ~Q(mooringlicence=None) |
                    ~Q(annualadmissionpermit=None)
                )
        queryset = queryset.exclude(current_proposal__processing_status=Proposal.PROCESSING_STATUS_DECLINED).filter(filter_query)
        total_count = queryset.count()
        #set total count attr here
        setattr(self, '_datatables_total_count', total_count)
        queryset = self.filter_queryset(queryset)
        setattr(self, '_datatables_total_count', total_count)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ApprovalViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = Approval.objects.none()
    serializer_class = ApprovalSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        if is_internal(self.request):
            return Approval.objects.all()
        elif is_customer(self.request):
            queryset =  Approval.objects.filter(
                Q(current_proposal__proposal_applicant__email_user_id=self.request.user.id)
                )
            return queryset
        return Approval.objects.none()

    @list_route(methods=['GET',], detail=False)
    @basic_exception_handler
    def existing_licences(self, request, *args, **kwargs):
        existing_licences = []

        applicant_id = request.user.id
        if is_internal(request): 
            applicant_system_id = request.GET.get('applicant_system_id', False)
            if applicant_system_id:
                try:
                    applicant_id = SystemUser.objects.get(id=applicant_system_id).ledger_id.id
                except:
                    applicant_id = request.user.id

        l_list = Approval.objects.filter(
            current_proposal__proposal_applicant__email_user_id=applicant_id,
            status__in=[Approval.APPROVAL_STATUS_CURRENT,],
        )
        for l in l_list:
            lchild = l.child_obj
            if type(lchild) == MooringLicence:
                if Mooring.objects.filter(mooring_licence=lchild):
                    mooring = Mooring.objects.filter(mooring_licence=lchild)[0]
                    existing_licences.append({
                        "approval_id": lchild.id,
                        "current_proposal_id": lchild.current_proposal.id,
                        "lodgement_number": lchild.lodgement_number,
                        "mooring_id": mooring.id,
                        "code": lchild.code,
                        "description": lchild.description,
                        "new_application_text": "I want to amend or renew my current mooring site licence {}".format(lchild.lodgement_number),
                        "new_application_text_add_vessel": "I want to add another vessel to my current mooring site licence {}".format(lchild.lodgement_number),
                        })
            else:
                if type(lchild) == WaitingListAllocation:
                    if lchild.internal_status not in [Approval.INTERNAL_STATUS_WAITING,]:
                        continue
                if lchild.approval.amend_or_renew:
                    existing_licences.append({
                        "approval_id": lchild.id,
                        "lodgement_number": lchild.lodgement_number,
                        "current_proposal_id": lchild.current_proposal.id,
                        "code": lchild.code,
                        "description": lchild.description,
                        "new_application_text": "I want to amend or renew my current {} {}".format(lchild.description.lower(), lchild.lodgement_number)
                        })
        return Response(existing_licences)

    @detail_route(methods=['POST'], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def removeMooringFromApproval(self, request, *args, **kwargs):
        
        if is_internal(request):
            with transaction.atomic():
                try:
                    approval = self.get_object()
                    mooring_name = request.data.get('mooring_name')
                    mooring = Mooring.objects.filter(name=mooring_name).first()
                    if not mooring:
                        raise serializers.ValidationError("Mooring does not exist")
                    moa = MooringOnApproval.objects.filter(mooring=mooring, approval=approval).first()
                    if not moa:
                        raise serializers.ValidationError("Mooring and AUP relationship does not exist")
                    today=datetime.now(pytz.timezone(TIME_ZONE)).date()
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
                            # regenerating the List of Authorised Users document for the mooring Licence and sending emal to the user
                            ml.generate_au_summary_doc()
                            #send email to mooring licence owner if with the above attachement if required
                    else:
                        # removing the List of Authorised Users document if there is no more AUPs remaining             
                        mooring.mooring_licence.authorised_user_summary_document = None
                    mooring.save()
                    mooring.mooring_licence.save()

                    approval.manage_stickers()

                    approval.log_user_action(f'Mooring {mooring} removed from AUP {approval}.', request)
                    mooring.log_user_action(f'Mooring {mooring} removed from AUP {approval}.', request)
                    return Response({"results": "Success"})
                except Exception as e:
                    logger.error(str(e))
                    raise serializers.ValidationError("Error removing Mooring from AUP")

    @detail_route(methods=['GET'], detail=True)
    @basic_exception_handler
    def get_moorings(self, request, *args, **kwargs):
        instance = self.get_object()
        moorings = []
        for moa in instance.mooringonapproval_set.filter(active='True'):
            try:
                licence_holder_data = SystemUser.objects.get(
                    ledger_id=moa.mooring.mooring_licence.current_proposal.proposal_applicant.email_user_id
                )
                if licence_holder_data:
                    user_details = get_user_name(licence_holder_data)
                    moorings.append({
                        "id": moa.id,
                        "mooring_name": moa.mooring.name,
                        "licensee": user_details["full_name"],
                        "mobile": licence_holder_data.mobile_number,
                        "email": licence_holder_data.email,
                        })
            except:
                continue
        return Response(moorings)

    @detail_route(methods=['POST'], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def swap_moorings(self, request, *args, **kwargs):
        with transaction.atomic():
            if is_internal(request):
                originated_approval = self.get_object()
                target_approval_id = request.data.get('target_approval_id')
                target_approval = Approval.objects.get(id=target_approval_id)
                originated_approval.child_obj.swap_moorings(request, target_approval.child_obj)
            return Response()


    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def create_new_sticker(self, request, *args, **kwargs):
        # internal only
        if is_internal(self.request):
            approval = self.get_object()
            season = approval.latest_applied_season
            if not approval.status in Approval.APPROVED_STATUSES:
                raise serializers.ValidationError("Approval is not valid for sticker replacement (Must be Current or Suspended).")

            details = request.data['details']

            replace_sticker = None
            sticker_action_details = []

            #First we check if there are missing valid stickers
            #Then we check if there is an invalid sticker that can be directly replaced
            #If there is not, we continue anyway and the sticker purpose will be established after payment
            #But we must not allow this to continue if there are no missing stickers

            #Annual Admissions can only have one sticker
            if type(approval.child_obj) == AnnualAdmissionPermit:
                if Sticker.objects.filter(approval=approval).filter(fee_season=season).exclude(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST,Sticker.STICKER_STATUS_RETURNED]).exists():
                    raise serializers.ValidationError("This approval already has an active sticker record.")
                #if the approval is current but has no sticker that is current or printing (or awaiting export) then replace then latest sticker (set replace sticker) if it exists
                vessel_ownership = approval.current_proposal.vessel_ownership if approval.current_proposal else None
                if not vessel_ownership or vessel_ownership.end_date:
                    raise serializers.ValidationError("Approval does not have a valid vessel ownership.")
                stickers_qs = Sticker.objects.filter(approval=approval,vessel_ownership=vessel_ownership).filter(fee_season=season).filter(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST]).order_by('-id')
                if stickers_qs.exists():
                    replace_sticker = stickers_qs.first()
                #if none, replace blindly (handled after payment)
    
            #MLA - one sticker per vessel
            elif type(approval.child_obj) == MooringLicence:
                #identify missing stickers (any VOOA VO that is not on a valid sticker with this approval assigned)
                vessel_ownership_on_approvals = approval.child_obj.get_current_vessel_ownership_on_approvals().values_list("vessel_ownership_id",flat=True)

                if not vessel_ownership_on_approvals:
                    raise serializers.ValidationError("Approval does not have a valid vessel ownership.")

                stickers_qs = Sticker.objects.filter(approval=approval,vessel_ownership_id__in=list(vessel_ownership_on_approvals)).filter(fee_season=season).exclude(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST,Sticker.STICKER_STATUS_RETURNED])
                vo_missing_sticker = []

                missing = False
                for vo in vessel_ownership_on_approvals:
                    if not stickers_qs.filter(vessel_ownership_id=vo).exists():
                        missing = True
                        vo_missing_sticker.append(vo)
                
                #if none are missing raise error
                if not missing:
                    raise serializers.ValidationError("This approval has active stickers for all relevant vessels.")

                #otherwise then find any cancelled or lost stickers that can be replaced for those missing stickers (the latest sticker with the VO and approval)
                stickers_qs = Sticker.objects.filter(approval=approval,vessel_ownership__in=vo_missing_sticker).filter(fee_season=season).filter(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST]).order_by('-id')
                #replace first that comes up
                if stickers_qs.exists():
                    replace_sticker = stickers_qs.first()
                #if none, replace blindly (handled after payment)
                
            #AUP - one sticker for every four moorings, each mooring must have a sticker
            elif type(approval.child_obj) == AuthorisedUserPermit:
                #identify missing stickers (any MOA with a null sticker OR a sticker that is cancelled or lost)
                active_moa_with_invalid_sticker_or_no_sticker = MooringOnApproval.objects.filter(
                    approval=approval,active=True
                ).filter(
                    Q(sticker__isnull=True)|(Q(sticker__status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST,Sticker.STICKER_STATUS_RETURNED])&Q(fee_season=season))
                )
                #if none are missing raise error
                if not active_moa_with_invalid_sticker_or_no_sticker.exists():
                    raise serializers.ValidationError("This approval has active stickers for all relevant moorings.")

                #otherwise then find any cancelled or lost stickers that can be replaced for those missing stickers (whatever is on the MOA)
                active_moa_with_invalid_sticker = active_moa_with_invalid_sticker_or_no_sticker.exclude(sticker=None).exclude(sticker__status=Sticker.STICKER_STATUS_RETURNED).filter(sticker__fee_season=season).filter(sticker__status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST]).order_by('-id')
                #replace first that comes up
                if active_moa_with_invalid_sticker.exists():
                    replace_sticker = active_moa_with_invalid_sticker.first().sticker
                #if none, replace blindly (handled after payment)
            
            data = {}
            # include the sticker (to be replaced) in the action detail - if available
            if replace_sticker:
                data['sticker'] = replace_sticker.id

            data['action'] = 'Create new sticker'
            data['user'] = request.user.id
            data['reason'] = details['reason']
            if is_internal(request):
                data['waive_the_fee'] = request.data.get('waive_the_fee', False) 
            else:
                data['waive_the_fee'] = False
            #new address checkbox
            data['change_sticker_address'] = request.data.get('change_sticker_address', False)
            #address change (only applied if above True)
            data['new_postal_address_line1'] = request.data.get('postal_address_line1','')
            data['new_postal_address_line2'] = request.data.get('postal_address_line2','')
            data['new_postal_address_line3'] = request.data.get('postal_address_line3','')
            data['new_postal_address_locality'] = request.data.get('postal_address_locality','')
            data['new_postal_address_state'] = request.data.get('postal_address_state','')
            data['new_postal_address_country'] = request.data.get('postal_address_country','AU')
            data['new_postal_address_postcode'] = request.data.get('postal_address_postcode','')
            if data['change_sticker_address'] and '' in [
                    data['new_postal_address_line1'],
                    data['new_postal_address_locality'],
                    data['new_postal_address_state'],
                    data['new_postal_address_country'],
                    data['new_postal_address_postcode']
                ]:
                raise serializers.ValidationError("Required address details not provided")                

            serializer = StickerActionDetailSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            new_sticker_action_detail = serializer.save()
            new_sticker_action_detail.approval = approval
            new_sticker_action_detail.save()
            sticker_action_details.append(new_sticker_action_detail.id)

            approval.log_user_action(f"New sticker created for Approval {approval}", request)

            return Response({'sticker_action_detail_ids': sticker_action_details})

    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def request_new_stickers(self, request, *args, **kwargs):
        # external
        approval = self.get_object()
        details = request.data['details']
        sticker_ids = []
        for sticker in request.data['stickers']:
            if sticker['checked'] == True:
                sticker_ids.append(sticker['id'])

        if approval.current_proposal:
            v_details = approval.current_proposal.latest_vessel_details
            v_ownership = approval.current_proposal.vessel_ownership

        if v_details and not v_ownership.end_date:
            # Licence/Permit has a vessel
            sticker_action_details = []
            stickers = Sticker.objects.filter(
                approval=approval, id__in=sticker_ids, 
                status__in=(Sticker.STICKER_STATUS_CURRENT, 
                Sticker.STICKER_STATUS_AWAITING_PRINTING,)
            )
            printed_stickers = stickers.filter(status=Sticker.STICKER_STATUS_CURRENT)
            if not printed_stickers.exists():
                raise serializers.ValidationError("Unable to request new sticker - existing stickers must be printed first before a new sticker is requested")
            data = {}
            today = datetime.now(pytz.timezone(settings.TIME_ZONE)).date()
            for sticker in stickers:
                data['action'] = 'Request new sticker'
                data['user'] = request.user.id
                data['reason'] = details['reason']
                data['date_of_lost_sticker'] = today.strftime('%d/%m/%Y')
                
                if is_internal(request):
                    data['waive_the_fee'] = request.data.get('waive_the_fee', False) 
                else:
                    data['waive_the_fee'] = False

                #new address checkbox
                data['change_sticker_address'] = request.data.get('change_sticker_address', False)
                #address change (only applied if above True)
                data['new_postal_address_line1'] = request.data.get('new_postal_address_line1','')
                data['new_postal_address_line2'] = request.data.get('new_postal_address_line2','')
                data['new_postal_address_line3'] = request.data.get('new_postal_address_line3','')
                data['new_postal_address_locality'] = request.data.get('new_postal_address_locality','')
                data['new_postal_address_state'] = request.data.get('new_postal_address_state','')
                data['new_postal_address_country'] = request.data.get('new_postal_address_country','AU')
                data['new_postal_address_postcode'] = request.data.get('new_postal_address_postcode','')
                if data['change_sticker_address'] and '' in [
                      data['new_postal_address_line1'],
                      data['new_postal_address_locality'],
                      data['new_postal_address_state'],
                      data['new_postal_address_country'],
                      data['new_postal_address_postcode']
                    ]:
                    raise serializers.ValidationError("Required address details not provided")                

                serializer = StickerActionDetailSerializer(data=data)
                serializer.is_valid(raise_exception=True)
                new_sticker_action_detail = serializer.save()
                new_sticker_action_detail.approval = approval
                new_sticker_action_detail.sticker = sticker
                new_sticker_action_detail.save()
                sticker_action_details.append(new_sticker_action_detail.id)

                approval.log_user_action(f"New sticker requested for Approval {approval}", request)

            return Response({'sticker_action_detail_ids': sticker_action_details})
        else:
            raise Exception('You cannot request a new sticker for the licence/permit without a vessel.')

    @detail_route(methods=['POST'], detail=True)
    @basic_exception_handler
    def change_sticker_addresses(self, request, *args, **kwargs):
        # external
        approval = self.get_object()
        sticker_ids = []
        for sticker in request.data['stickers']:
            if sticker['checked'] == True:
                sticker_ids.append(sticker['id'])

        stickers = Sticker.objects.filter(approval=approval, id__in=sticker_ids, 
            status__in=(
                Sticker.STICKER_STATUS_READY, 
                Sticker.STICKER_STATUS_NOT_READY_YET,))
        if not stickers.exists():
            raise serializers.ValidationError("Unable to change address of sticker - already in process of being printed/mailed")
        data = {}
        for sticker in stickers:
            data['id'] = sticker.id
            data['postal_address_line1'] = request.data.get('new_postal_address_line1','')
            data['postal_address_line2'] = request.data.get('new_postal_address_line2','')
            data['postal_address_line3'] = request.data.get('new_postal_address_line3','')
            data['postal_address_locality'] = request.data.get('new_postal_address_locality','')
            data['postal_address_state'] = request.data.get('new_postal_address_state','')
            data['postal_address_country'] = request.data.get('new_postal_address_country','AU')
            data['postal_address_postcode'] = request.data.get('new_postal_address_postcode','')
            if '' in [data['postal_address_line1'],
                      data['postal_address_locality'],
                      data['postal_address_state'],
                      data['postal_address_country'],
                      data['postal_address_postcode']
                    ]:
                raise serializers.ValidationError("Required address details not provided")
            
            serializer = StickerPostalAddressSaveSerializer(sticker,data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            
            ApprovalUserAction.log_action(sticker.approval,ApprovalUserAction.ACTION_UPDATE_STICKER_ADDRESS.format(sticker.number),request.user)

        return Response()

    @detail_route(methods=['GET'], detail=True)
    @basic_exception_handler
    def stickers(self, request, *args, **kwargs):
        instance = self.get_object()
        stickers = instance.stickers.filter(
            status__in=[
            Sticker.STICKER_STATUS_READY, 
            Sticker.STICKER_STATUS_NOT_READY_YET, 
            Sticker.STICKER_STATUS_CURRENT, 
            Sticker.STICKER_STATUS_AWAITING_PRINTING])
        serializer = StickerSerializer(stickers, many=True)
        return Response({'stickers': serializer.data})

    @detail_route(methods=['GET'], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def approval_history(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            serializer = ApprovalHistorySerializer(instance.approvalhistory_set.all(), many=True)
            return Response(serializer.data)
        else:
            raise serializers.ValidationError("User not authorised to view approval history")

    @detail_route(methods=['GET'], detail=True)
    @basic_exception_handler
    def lookup_approval(self, request, *args, **kwargs):
        instance = self.get_object()
        approval_details = {
                "approvalType": instance.child_obj.description,
                "approvalLodgementNumber": instance.lodgement_number,
                }
        return Response(approval_details)

    @detail_route(methods=['POST'], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def process_waiting_list_offer_document(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            returned_data = process_generic_document(request, instance, document_type='waiting_list_offer_document')
            if returned_data:
                return Response(returned_data)
            else:
                return Response()
        else:
            raise serializers.ValidationError("User not authorised to process waiting list offer document")

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def approval_cancellation(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            serializer = ApprovalCancellationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.approval_cancellation(request, serializer.validated_data)
            return Response()
        else:
            raise serializers.ValidationError("User not authorised to cancel approval")

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def approval_suspension(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            serializer = ApprovalSuspensionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.approval_suspension(request,serializer.validated_data)
            return Response()
        else:
            raise serializers.ValidationError("User not authorised to suspend approval")
        
    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def approval_extension(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            serializer = ApprovalExtensionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.approval_extension(request,serializer.validated_data)
            return Response()
        else:
            raise serializers.ValidationError("User not authorised to suspend approval")

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def approval_reinstate(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            instance.reinstate_approval(request)
            return Response()
        else:
            raise serializers.ValidationError("User not authorised to reinstate approval")

    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def approval_surrender(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ApprovalSurrenderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.approval_surrender(request,serializer.validated_data)
        return Response()

    @detail_route(methods=['GET',], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def action_log(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            qs = instance.action_logs.all()
            serializer = ApprovalUserActionSerializer(qs,many=True)
            return Response(serializer.data)
        return Response()

    @detail_route(methods=['GET',], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def comms_log(self, request, *args, **kwargs):
        if is_internal(request):
            instance = self.get_object()
            qs = instance.comms_logs.all()
            serializer = ApprovalLogEntrySerializer(qs,many=True)
            return Response(serializer.data)
        return Response()

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalApprovalPermission])
    @basic_exception_handler
    def add_comms_log(self, request, *args, **kwargs):
        if is_internal(request):
            with transaction.atomic():
                instance = self.get_object()
                mutable=request.data._mutable
                request.data._mutable=True
                request.data['approval'] = u'{}'.format(instance.id)
                request.data['staff'] = u'{}'.format(request.user.id)
                request.data._mutable=mutable
                serializer = ApprovalLogEntrySerializer(data=request.data)
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


class DcvAdmissionViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = DcvAdmission.objects.all().order_by('id')
    serializer_class = DcvAdmissionSerializer

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = DcvAdmission.objects.all().order_by('id')
            return qs
        elif is_customer(self.request):
            queryset = DcvAdmission.objects.filter(Q(applicant=user.id))
            return queryset
        return DcvAdmission.objects.none()


    @staticmethod
    def _handle_dcv_vessel(user, dcv_vessel): 
        if not dcv_vessel:
            raise serializers.ValidationError("Please specify vessel Rego No.")
        data = dcv_vessel
        rego_no_requested = data.get('rego_no', '')
        vessel_name_requested = data.get('vessel_name', '')

        current_date = datetime.now()
        dcv_admission_ids = DcvAdmissionArrival.objects.filter(
            departure_date__gte=current_date
        ).values_list('dcv_admission__id', flat=True)

        dcv_vessel = DcvVessel.objects.filter(rego_no=rego_no_requested)
        dcv_vessel_usage = dcv_vessel.filter(
            Q(dcv_permits__in=DcvPermit.objects.exclude(status=DcvPermit.DCV_PERMIT_STATUS_CANCELLED).filter(end_date__gte=current_date)) |
            Q(dcv_admissions__in=DcvAdmission.objects.exclude(status=DcvAdmission.DCV_ADMISSION_STATUS_CANCELLED).filter(id__in=dcv_admission_ids))
        )
        if not dcv_vessel.exists():
            data['rego_no'] = rego_no_requested
            data['vessel_name'] = vessel_name_requested
            serializer = DcvVesselSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            dcv_vessel = serializer.save()
        elif dcv_vessel_usage.exists():
            dcv_vessel = dcv_vessel.filter(
                Q(dcv_permits__in=DcvPermit.objects.filter(Q(applicant=user.id))) |
                Q(dcv_admissions__in=DcvAdmission.objects.filter(Q(applicant=user.id)))
            )
            if not dcv_vessel.exists():
                raise serializers.ValidationError("Vessel listed under another Owner")
            else:
                return dcv_vessel.first()
        else:
            dcv_vessel = dcv_vessel.first()

        return dcv_vessel

    def create(self, request, *args, **kwargs):
        data = request.data
        dcv_vessel = self._handle_dcv_vessel(request.user, request.data.get('dcv_vessel'))
        dcv_organisation = None

        if request.user.is_authenticated:
            # Logged in user
            # 1. DcvPermit exists
            # 2. DcvPermit doesn't exist

            submitter = request.user
            if not dcv_vessel.dcv_permits.count():
                # No DcvPermit found, create DcvOrganisation and link it to DcvVessel
                my_data = {}
                my_data['organisation'] = request.data.get('organisation_name')
                my_data['abn_acn'] = request.data.get('organisation_abn')
                dcv_organisation, created = DcvPermitViewSet.handle_dcv_organisation(my_data, False)
                orgs = dcv_vessel.dcv_organisations.filter(id=dcv_organisation.id)
                if not orgs:
                    dcv_vessel.dcv_organisations.add(dcv_organisation)

        else:
            # Anonymous user
            # 1. DcvPermit exists
            # 2. DcvPermit doesn't exist
            if dcv_vessel.dcv_permits.count():
                # DcvPermit exists
                submitter = dcv_vessel.dcv_permits.first().applicant
            else:
                # DcvPermit doesn't exist
                email_address = request.data.get('email_address')
                email_address_confirmation = request.data.get('email_address_confirmation')
                skipper = request.data.get('skipper')
                if email_address and email_address_confirmation:
                    if email_address == email_address_confirmation:
                        if skipper:
                            this_user = EmailUser.objects.filter(email__iexact=email_address, is_active=True).order_by('-id')
                            if this_user:
                                new_user = this_user.first()
                            else:
                                new_user = get_or_create(email_address)
                            submitter = new_user
                        else:
                            raise forms.ValidationError('Please fill the skipper field')
                    else:
                        raise forms.ValidationError('Email addresses do not match')
                else:
                    raise forms.ValidationError('Please fill the email address fields')

                # No DcvPermit found, create DcvOrganisation and link it to DcvVessel
                my_data = {}
                my_data['organisation'] = request.data.get('organisation_name')
                my_data['abn_acn'] = request.data.get('organisation_abn')
                dcv_organisation, created = DcvPermitViewSet.handle_dcv_organisation(my_data, False)
                orgs = dcv_vessel.dcv_organisations.filter(id=dcv_organisation.id)
                if not orgs:
                    dcv_vessel.dcv_organisations.add(dcv_organisation)
        try:
            submitter_id = submitter.id
        except:
            submitter_id = submitter['data']['emailuser_id']
        data['submitter'] = submitter_id
        data['applicant'] = submitter_id
        data['date_created'] = datetime.now(pytz.timezone(TIME_ZONE))
        data['status'] = DcvAdmission.DCV_ADMISSION_STATUS_UNPAID
        data['dcv_vessel_id'] = dcv_vessel.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        dcv_admission = serializer.save()
        logger.info(f'Create DcvAdmission: [{dcv_admission}].')
        if dcv_organisation:
            dcv_admission.dcv_organisation = dcv_organisation
            dcv_admission.save()

        for arrival in data.get('arrivals', None):
            arrival['dcv_admission'] = dcv_admission.id
            serializer_arrival = DcvAdmissionArrivalSerializer(data=arrival)
            serializer_arrival.is_valid(raise_exception=True)
            dcv_admission_arrival = serializer_arrival.save()

            # Adults
            age_group_obj = AgeGroup.objects.get(code=AgeGroup.AGE_GROUP_ADULT)
            for admission_type, number in arrival.get('adults').items():
                number = 0 if dcv_admission_arrival.private_visit else number  # When private visit, we don't care the number of people
                admission_type_obj = AdmissionType.objects.get(code=admission_type)
                serializer_num = NumberOfPeopleSerializer(data={
                    'number': number if number else 0,  # when number is blank, set to 0
                    'dcv_admission_arrival': dcv_admission_arrival.id,
                    'age_group': age_group_obj.id,
                    'admission_type': admission_type_obj.id
                })
                serializer_num.is_valid(raise_exception=True)
                number_of_people = serializer_num.save()

            # Children
            age_group_obj = AgeGroup.objects.get(code=AgeGroup.AGE_GROUP_CHILD)
            for admission_type, number in arrival.get('children').items():
                number = 0 if dcv_admission_arrival.private_visit else number  # When private visit, we don't care the number of people
                admission_type_obj = AdmissionType.objects.get(code=admission_type)
                serializer_num = NumberOfPeopleSerializer(data={
                    'number': number if number else 0,  # when number is blank, set to 0
                    'dcv_admission_arrival': dcv_admission_arrival.id,
                    'age_group': age_group_obj.id,
                    'admission_type': admission_type_obj.id
                })
                serializer_num.is_valid(raise_exception=True)
                number_of_people = serializer_num.save()

        return Response(serializer.data)
    
class InternalDcvAdmissionViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = DcvAdmission.objects.all().order_by('id')
    serializer_class = DcvAdmissionSerializer
    permission_classes=[InternalApprovalPermission]

    def get_queryset(self):
        if is_internal(self.request):
            qs = DcvAdmission.objects.all().order_by('id')
            return qs
        return DcvAdmission.objects.none()

    @staticmethod
    def _handle_dcv_vessel(user, dcv_vessel):
        if not dcv_vessel:
            raise serializers.ValidationError("Please specify vessel Rego No.")
        data = dcv_vessel
        rego_no_requested = data.get('rego_no', '')
        vessel_name_requested = data.get('vessel_name', '')

        current_date = datetime.now()
        dcv_admission_ids = DcvAdmissionArrival.objects.filter(
            departure_date__gte=current_date
        ).values_list('dcv_admission__id', flat=True)

        dcv_vessel = DcvVessel.objects.filter(rego_no=rego_no_requested)
        dcv_vessel_usage = dcv_vessel.filter(
            Q(dcv_permits__in=DcvPermit.objects.exclude(status=DcvPermit.DCV_PERMIT_STATUS_CANCELLED).filter(end_date__gte=current_date)) |
            Q(dcv_admissions__in=DcvAdmission.objects.exclude(status=DcvAdmission.DCV_ADMISSION_STATUS_CANCELLED).filter(id__in=dcv_admission_ids))
        )
        if not dcv_vessel.exists():
            data['rego_no'] = rego_no_requested
            data['vessel_name'] = vessel_name_requested
            serializer = DcvVesselSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            dcv_vessel = serializer.save()
        elif dcv_vessel_usage.exists():
            dcv_vessel = dcv_vessel.filter(
                Q(dcv_permits__in=DcvPermit.objects.filter(Q(applicant=user.id))) |
                Q(dcv_admissions__in=DcvAdmission.objects.filter(Q(applicant=user.id)))
            )
            if not dcv_vessel.exists():
                raise serializers.ValidationError("Vessel listed under another Owner")
            else:
                return dcv_vessel.first()
        else:
            dcv_vessel = dcv_vessel.first()
            
        return dcv_vessel

    def create(self, request, *args, **kwargs):
        if is_internal(self.request):
            data = request.data
            
            submitter = request.user
            email_address = request.data.get('email_address')
            email_address_confirmation = request.data.get('email_address_confirmation')
            skipper = request.data.get('skipper')
            if email_address and email_address_confirmation:
                if email_address == email_address_confirmation:
                    if skipper:
                        this_user = EmailUser.objects.filter(email__iexact=email_address, is_active=True).order_by('-id')
                        if this_user:
                            new_user = this_user.first()
                        else:
                            new_user = get_or_create(email_address)
                        applicant = new_user
                    else:
                        raise forms.ValidationError('Please fill the skipper field')
                else:
                    raise forms.ValidationError('Email addresses do not match')
            else:
                raise forms.ValidationError('Please fill the email address fields')
            
            dcv_vessel = self._handle_dcv_vessel(applicant, request.data.get('dcv_vessel'))
            dcv_organisation = None

            # create DcvOrganisation and link it to DcvVessel
            my_data = {}
            my_data['organisation'] = request.data.get('organisation_name')
            my_data['abn_acn'] = request.data.get('organisation_abn')
            dcv_organisation, created = DcvPermitViewSet.handle_dcv_organisation(my_data, False)
            orgs = dcv_vessel.dcv_organisations.filter(id=dcv_organisation.id)
            if not orgs:
                dcv_vessel.dcv_organisations.add(dcv_organisation)
                dcv_vessel.save()

            data['submitter'] = submitter.id
            try:
                applicant_id = applicant.id
            except:
                applicant_id = applicant['data']['emailuser_id']
            data['applicant'] = applicant_id
            data['dcv_vessel_id'] = dcv_vessel.id
            data['date_created'] = datetime.now(pytz.timezone(TIME_ZONE))
            data['status'] = DcvAdmission.DCV_ADMISSION_STATUS_UNPAID
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            dcv_admission = serializer.save()
            logger.info(f'Create DcvAdmission: [{dcv_admission}].')
            if dcv_organisation:
                dcv_admission.dcv_organisation = dcv_organisation
                dcv_admission.save()

            for arrival in data.get('arrivals', None):
                arrival['dcv_admission'] = dcv_admission.id
                serializer_arrival = DcvAdmissionArrivalSerializer(data=arrival)
                serializer_arrival.is_valid(raise_exception=True)
                dcv_admission_arrival = serializer_arrival.save()

                # Adults
                age_group_obj = AgeGroup.objects.get(code=AgeGroup.AGE_GROUP_ADULT)
                for admission_type, number in arrival.get('adults').items():
                    number = 0 if dcv_admission_arrival.private_visit else number  # When private visit, we don't care the number of people
                    admission_type_obj = AdmissionType.objects.get(code=admission_type)
                    serializer_num = NumberOfPeopleSerializer(data={
                        'number': number if number else 0,  # when number is blank, set to 0
                        'dcv_admission_arrival': dcv_admission_arrival.id,
                        'age_group': age_group_obj.id,
                        'admission_type': admission_type_obj.id
                    })
                    serializer_num.is_valid(raise_exception=True)
                    number_of_people = serializer_num.save()

                # Children
                age_group_obj = AgeGroup.objects.get(code=AgeGroup.AGE_GROUP_CHILD)
                for admission_type, number in arrival.get('children').items():
                    number = 0 if dcv_admission_arrival.private_visit else number  # When private visit, we don't care the number of people
                    admission_type_obj = AdmissionType.objects.get(code=admission_type)
                    serializer_num = NumberOfPeopleSerializer(data={
                        'number': number if number else 0,  # when number is blank, set to 0
                        'dcv_admission_arrival': dcv_admission_arrival.id,
                        'age_group': age_group_obj.id,
                        'admission_type': admission_type_obj.id
                    })
                    serializer_num.is_valid(raise_exception=True)
                    number_of_people = serializer_num.save()
            return Response(serializer.data)
        raise serializers.ValidationError("not authorised to create application as an internal user")


class DcvPermitViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = DcvPermit.objects.all().order_by('id')
    serializer_class = DcvPermitSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = DcvPermit.objects.all().order_by('id')
            return qs
        elif is_customer(self.request):
            queryset = DcvPermit.objects.filter(Q(applicant=user.id))
            return queryset
        return DcvPermit.objects.none()

    @staticmethod
    def handle_dcv_organisation(data, abn_required=True):
        abn_requested = data.get('abn_acn', '')
        name_requested = data.get('organisation', '')
        created = False
        try:
            if abn_required:
                dcv_organisation = DcvOrganisation.objects.get(abn=abn_requested)
            else:
                data['name'] = name_requested
                serializer = DcvOrganisationSerializer(data=data, context={'abn_required': abn_required})
                serializer.is_valid(raise_exception=True)
                dcv_organisation = serializer.save()
                created = True
                logger.info(f'Create DcvOrganisation: [{dcv_organisation}].')
        except DcvOrganisation.DoesNotExist:
            data['name'] = name_requested
            data['abn'] = abn_requested
            serializer = DcvOrganisationSerializer(data=data, context={'abn_required': abn_required})
            serializer.is_valid(raise_exception=True)
            dcv_organisation = serializer.save()
            created = True
            logger.info(f'Create DcvOrganisation: [{dcv_organisation}].')
        except Exception as e:
            logger.error(e)
            raise

        return dcv_organisation, created


    @staticmethod
    def _handle_dcv_vessel(user, dcv_vessel, org_id=None): 
        if not dcv_vessel:
            raise serializers.ValidationError("Please specify vessel Rego No.")
        data = dcv_vessel
        rego_no_requested = data.get('rego_no', '')
        vessel_name_requested = data.get('vessel_name', '')

        current_date = datetime.now()
        dcv_admission_ids = DcvAdmissionArrival.objects.filter(
            departure_date__gte=current_date
        ).values_list('dcv_admission__id', flat=True)
        
        dcv_vessel = DcvVessel.objects.filter(rego_no=rego_no_requested)
        
        dcv_vessel_usage = dcv_vessel.filter(
            Q(dcv_permits__in=DcvPermit.objects.exclude(status=DcvPermit.DCV_PERMIT_STATUS_CANCELLED).filter(end_date__gte=current_date)) |
            Q(dcv_admissions__in=DcvAdmission.objects.exclude(status=DcvAdmission.DCV_ADMISSION_STATUS_CANCELLED).filter(id__in=dcv_admission_ids))
        )
        if not dcv_vessel.exists():
            data['rego_no'] = rego_no_requested
            data['vessel_name'] = vessel_name_requested
            serializer = DcvVesselSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            dcv_vessel = serializer.save()
        elif dcv_vessel_usage.exists():
            dcv_vessel = dcv_vessel.filter(
                Q(dcv_permits__in=DcvPermit.objects.filter(Q(applicant=user.id))) |
                Q(dcv_admissions__in=DcvAdmission.objects.filter(Q(applicant=user.id)))
            )
            if not dcv_vessel.exists():
                raise serializers.ValidationError("Vessel listed under another Owner")
            else:
                orgs = dcv_vessel.first().dcv_organisations.filter(id=org_id)
                if not orgs:
                    dcv_vessel.first().dcv_organisations.add(DcvOrganisation.objects.get(id=org_id))
                return dcv_vessel.first()
        else:
            dcv_vessel = dcv_vessel.first()

        orgs = dcv_vessel.dcv_organisations.filter(id=org_id)
        if not orgs:
            dcv_vessel.dcv_organisations.add(DcvOrganisation.objects.get(id=org_id))

        return dcv_vessel


    def create(self, request, *args, **kwargs):
        data = request.data
        dcv_organisation, created = self.handle_dcv_organisation(request.data)
        dcv_vessel = self._handle_dcv_vessel(request.user, request.data.get('dcv_vessel'), dcv_organisation.id)
        fee_season_requested = data.get('season') if data.get('season') else {'id': 0, 'name': ''}

        data['submitter'] = request.user.id
        data['applicant'] = request.user.id
        data['dcv_vessel_id'] = dcv_vessel.id
        data['dcv_organisation_id'] = dcv_organisation.id
        data['fee_season_id'] = fee_season_requested.get('id')
        data['postal_address_line1'] = data.get('postal_address')['line1']
        data['postal_address_line2'] = data.get('postal_address')['line2']
        data['postal_address_line3'] = data.get('postal_address')['line2']
        data['postal_address_suburb'] = data.get('postal_address')['locality']
        data['postal_address_postcode'] = data.get('postal_address')['postcode']
        data['postal_address_state'] = data.get('postal_address')['state']
        data['postal_address_country'] = data.get('postal_address')['country']
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        dcv_permit = serializer.save()
        logger.info(f'Create DcvPermit: [{dcv_permit}].')
        return Response(serializer.data)
    
class InternalDcvPermitViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = DcvPermit.objects.all().order_by('id')
    serializer_class = DcvPermitSerializer
    permission_classes=[InternalApprovalPermission]

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = DcvPermit.objects.all().order_by('id')
            return qs
        elif is_customer(self.request):
            queryset = DcvPermit.objects.filter(Q(applicant=user.id))
            return queryset
        return DcvPermit.objects.none()

    @staticmethod
    def handle_dcv_organisation(data, abn_required=True):
        abn_requested = data.get('abn_acn', '')
        name_requested = data.get('organisation', '')
        created = False
        try:
            if abn_required:
                dcv_organisation = DcvOrganisation.objects.get(abn=abn_requested)
            else:
                data['name'] = name_requested
                serializer = DcvOrganisationSerializer(data=data, context={'abn_required': abn_required})
                serializer.is_valid(raise_exception=True)
                dcv_organisation = serializer.save()
                created = True
                logger.info(f'Create DcvOrganisation: [{dcv_organisation}].')
        except DcvOrganisation.DoesNotExist:
            data['name'] = name_requested
            data['abn'] = abn_requested
            serializer = DcvOrganisationSerializer(data=data, context={'abn_required': abn_required})
            serializer.is_valid(raise_exception=True)
            dcv_organisation = serializer.save()
            created = True
            logger.info(f'Create DcvOrganisation: [{dcv_organisation}].')
        except Exception as e:
            logger.error(e)
            raise

        return dcv_organisation, created

    @staticmethod
    def _handle_dcv_vessel(user, dcv_vessel, org_id=None): 
        if not dcv_vessel:
            raise serializers.ValidationError("Please specify vessel Rego No.")
        data = dcv_vessel
        rego_no_requested = data.get('rego_no', '')
        vessel_name_requested = data.get('vessel_name', '')

        current_date = datetime.now()
        dcv_admission_ids = DcvAdmissionArrival.objects.filter(
            dcv_admission__status=DcvAdmission.DCV_ADMISSION_STATUS_PAID
        ).filter(
            departure_date__gte=current_date
        ).values_list('dcv_admission__id', flat=True)
        dcv_vessel = DcvVessel.objects.filter(rego_no=rego_no_requested)
        
        dcv_vessel_usage = dcv_vessel.filter(
            Q(dcv_permits__in=DcvPermit.objects.exclude(end_date=None).filter(end_date__gte=current_date)) |
            Q(dcv_admissions__in=DcvAdmission.objects.filter(id__in=dcv_admission_ids))
        )
        if not dcv_vessel.exists():
            data['rego_no'] = rego_no_requested
            data['vessel_name'] = vessel_name_requested
            serializer = DcvVesselSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            dcv_vessel = serializer.save()
        elif dcv_vessel_usage.exists():
            dcv_vessel = dcv_vessel.filter(
                Q(dcv_permits__in=DcvPermit.objects.filter(Q(applicant=user.id))) |
                Q(dcv_admissions__in=DcvAdmission.objects.filter(Q(applicant=user.id)))
            )
            if not dcv_vessel.exists():
                raise serializers.ValidationError("Vessel listed under another Owner")
            else:
                orgs = dcv_vessel.first().dcv_organisations.filter(id=org_id)
                if not orgs:
                    dcv_vessel.first().dcv_organisations.add(DcvOrganisation.objects.get(id=org_id))
                return dcv_vessel.first()
        else:
            dcv_vessel = dcv_vessel.first()

        orgs = dcv_vessel.dcv_organisations.filter(id=org_id)
        if not orgs:
            dcv_vessel.dcv_organisations.add(DcvOrganisation.objects.get(id=org_id))

        return dcv_vessel
    
    @detail_route(methods=['GET'], detail=True)
    @basic_exception_handler   
    def stickers(self, request, *args, **kwargs):
        instance = self.get_object()
        stickers = instance.stickers.filter(
            status__in=[
            Sticker.STICKER_STATUS_READY, 
            Sticker.STICKER_STATUS_NOT_READY_YET, 
            Sticker.STICKER_STATUS_CURRENT, 
            Sticker.STICKER_STATUS_AWAITING_PRINTING])
        serializer = StickerSerializer(stickers, many=True)
        return Response({'stickers': serializer.data})

    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def create_new_sticker(self, request, *args, **kwargs):
        if is_internal(self.request):
            instance = self.get_object()

            mailed_date = None
            if request.data['mailed_date']:
                mailed_date = datetime.strptime(request.data['mailed_date'], '%d/%m/%Y').date()
            try:
                max_sticker_num = int(Sticker.objects.all().aggregate(Max('number'))['number__max'])
            except:
                max_sticker_num = 0
            
            sticker_number = max_sticker_num + 1
            sticker_number = '{0:07d}'.format(sticker_number)
            data = {}
            data['number'] = sticker_number
            data['mailing_date'] = mailed_date
            data['dcv_permit'] = instance.id
            data['status'] = Sticker.STICKER_STATUS_CURRENT
            change_sticker_address = request.data.get('change_sticker_address', False)
            #address change (only applied if above True)
            data['postal_address_line1'] = request.data.get('postal_address_line1','')
            data['postal_address_line2'] = request.data.get('postal_address_line2','')
            data['postal_address_line3'] = request.data.get('postal_address_line3','')
            data['postal_address_locality'] = request.data.get('postal_address_locality','')
            data['postal_address_state'] = request.data.get('postal_address_state','')
            data['postal_address_country'] = request.data.get('postal_address_country','AU')
            data['postal_address_postcode'] = request.data.get('postal_address_postcode','')
            if change_sticker_address and '' in [
                    data['postal_address_line1'],
                    data['postal_address_locality'],
                    data['postal_address_state'],
                    data['postal_address_country'],
                    data['postal_address_postcode']
                ]:
                raise serializers.ValidationError("Required address details not provided")  
            elif not change_sticker_address:
                dcv_permit_obj = DcvPermit.objects.get(id=instance.id)
                data['postal_address_line1'] = dcv_permit_obj.postal_address_line1
                data['postal_address_line2'] = dcv_permit_obj.postal_address_line2
                data['postal_address_line3'] = dcv_permit_obj.postal_address_line3
                data['postal_address_locality'] = dcv_permit_obj.postal_address_suburb
                data['postal_address_state'] = dcv_permit_obj.postal_address_state
                data['postal_address_country'] = dcv_permit_obj.postal_address_country
                data['postal_address_postcode'] = dcv_permit_obj.postal_address_postcode         

            serializer = StickerForDcvSaveSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            sticker = serializer.save()
            logger.info(f'Create Sticker: [{sticker}].')

            return Response(serializer.data)
        else:
            raise serializers.ValidationError("not authorised to create stickers")
        
    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def request_new_stickers(self, request, *args, **kwargs):
        if is_internal(self.request):
            #internal
            dcv_permit = self.get_object()
            details = request.data['details']
            sticker_ids = []
            for sticker in request.data['stickers']:
                if sticker['checked'] == True:
                    sticker_ids.append(sticker['id'])

            sticker_action_details = []
            stickers = Sticker.objects.filter(dcv_permit=dcv_permit, id__in=sticker_ids, status__in=(Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING,))
            printed_stickers = stickers.filter(status=Sticker.STICKER_STATUS_CURRENT)
            if not printed_stickers.exists():
                raise serializers.ValidationError("Unable to request new sticker - existing stickers must be printed first before a new sticker is requested")
            data = {}
            today = datetime.now(pytz.timezone(settings.TIME_ZONE)).date()
            for sticker in stickers:
                data['action'] = 'Request new sticker'
                data['user'] = request.user.id
                data['reason'] = details['reason']
                data['date_of_lost_sticker'] = today.strftime('%d/%m/%Y')

                #new address checkbox
                data['change_sticker_address'] = request.data.get('change_sticker_address', False)
                #address change (only applied if above True)
                data['new_postal_address_line1'] = request.data.get('postal_address_line1','')
                data['new_postal_address_line2'] = request.data.get('postal_address_line2','')
                data['new_postal_address_line3'] = request.data.get('postal_address_line3','')
                data['new_postal_address_locality'] = request.data.get('postal_address_locality','')
                data['new_postal_address_state'] = request.data.get('postal_address_state','')
                data['new_postal_address_country'] = request.data.get('postal_address_country','AU')
                data['new_postal_address_postcode'] = request.data.get('postal_address_postcode','')
                if data['change_sticker_address'] and '' in [
                        data['new_postal_address_line1'],
                        data['new_postal_address_locality'],
                        data['new_postal_address_state'],
                        data['new_postal_address_country'],
                        data['new_postal_address_postcode']
                    ]:
                    raise serializers.ValidationError("Required address details not provided")  
                elif not data['change_sticker_address']:
                    data['new_postal_address_line1'] = sticker.postal_address_line1
                    data['new_postal_address_line2'] = sticker.postal_address_line2
                    data['new_postal_address_line3'] = sticker.postal_address_line3
                    data['new_postal_address_locality'] = sticker.postal_address_locality
                    data['new_postal_address_state'] = sticker.postal_address_state
                    data['new_postal_address_country'] = sticker.postal_address_country
                    data['new_postal_address_postcode'] = sticker.postal_address_postcode
                    data['sticker'] = sticker.id                    

                serializer = StickerActionDetailSerializer(data=data)
                serializer.is_valid(raise_exception=True)
                new_sticker_action_detail = serializer.save()
                sticker_action_details.append(new_sticker_action_detail.id)
            return Response({'sticker_action_detail_ids': sticker_action_details})
        else:
            raise serializers.ValidationError("not authorised to request new sticker")
        
    @detail_route(methods=['POST'], detail=True)
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def change_sticker_addresses(self, request, *args, **kwargs):
        if is_internal(self.request):
            #internal
            dcv_permit = self.get_object()
            sticker_ids = []
            for sticker in request.data['stickers']:
                if sticker['checked'] == True:
                    sticker_ids.append(sticker['id'])

            stickers = Sticker.objects.filter(dcv_permit=dcv_permit, id__in=sticker_ids, 
                status__in=(
                    Sticker.STICKER_STATUS_READY, 
                    Sticker.STICKER_STATUS_NOT_READY_YET,))
            if not stickers.exists():
                raise serializers.ValidationError("Unable to change address of sticker - already in process of being printed/mailed")
            data = {}
            for sticker in stickers:
                data['id'] = sticker.id
                data['postal_address_line1'] = request.data.get('new_postal_address_line1','')
                data['postal_address_line2'] = request.data.get('new_postal_address_line2','')
                data['postal_address_line3'] = request.data.get('new_postal_address_line3','')
                data['postal_address_locality'] = request.data.get('new_postal_address_locality','')
                data['postal_address_state'] = request.data.get('new_postal_address_state','')
                data['postal_address_country'] = request.data.get('new_postal_address_country','AU')
                data['postal_address_postcode'] = request.data.get('new_postal_address_postcode','')
                if '' in [data['postal_address_line1'],
                        data['postal_address_locality'],
                        data['postal_address_state'],
                        data['postal_address_country'],
                        data['postal_address_postcode']
                        ]:
                    raise serializers.ValidationError("Required address details not provided")
                
                serializer = StickerPostalAddressSaveSerializer(sticker,data=data)
                serializer.is_valid(raise_exception=True)
                serializer.save()
            return Response()
        else:
            raise serializers.ValidationError("not authorised to change address")
        

    def create(self, request, *args, **kwargs):    
        if is_internal(self.request):
            data = request.data
            dcv_organisation, created = self.handle_dcv_organisation(request.data)
            try:
                applicant = EmailUser.objects.get(id=data.get('applicant'))
            except:
                raise serializers.ValidationError("valid applicant not specified")
            dcv_vessel = self._handle_dcv_vessel(applicant, request.data.get('dcv_vessel'), dcv_organisation.id)
            fee_season_requested = data.get('season') if data.get('season') else {'id': 0, 'name': ''}

            data['submitter'] = request.user.id
            data['applicant'] = data.get('applicant')
            data['dcv_vessel_id'] = dcv_vessel.id
            data['dcv_organisation_id'] = dcv_organisation.id
            data['fee_season_id'] = fee_season_requested.get('id')
            data['line1'] = data.get('postal_address')['line1']
            data['line2'] = data.get('postal_address')['line2']
            data['line3'] = data.get('postal_address')['line2']
            data['locality'] = data.get('postal_address')['locality']
            data['postcode'] = data.get('postal_address')['postcode']
            data['state'] = data.get('postal_address')['state']
            data['country'] = data.get('postal_address')['country']
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            dcv_permit = serializer.save()
            logger.info(f'Create DcvPermit: [{dcv_permit}].')
            return Response(serializer.data)
        else:
            raise serializers.ValidationError("not authorised to create permit as an internal user")
            

class DcvPermitFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        search_text = request.GET.get('search[value]', '')
        total_count = queryset.count()

        # filter by dcv_organisation
        filter_organisation_id = request.GET.get('filter_dcv_organisation_id')
        if filter_organisation_id and not filter_organisation_id.lower() == 'all':
            queryset = queryset.filter(dcv_organisation__id=filter_organisation_id)
        # filter by season
        filter_fee_season_id = request.GET.get('filter_fee_season_id')
        if filter_fee_season_id and not filter_fee_season_id.lower() == 'all':
            queryset = queryset.filter(fee_season__id=filter_fee_season_id)

        # status property
        status = None
        target_date=datetime.now(pytz.timezone(TIME_ZONE)).date()
        if search_text.strip().lower() in DcvPermit.DCV_PERMIT_STATUS_CURRENT:
            status = DcvPermit.DCV_PERMIT_STATUS_CURRENT
            queryset = queryset.filter(status=status)
        elif search_text.strip().lower() in DcvPermit.DCV_PERMIT_STATUS_EXPIRED:
            status = DcvPermit.DCV_PERMIT_STATUS_EXPIRED
            queryset = queryset.filter(status=status)
        
        fields = self.get_fields(request)
        ordering = self.get_ordering(request, view, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)
        else:
            queryset = queryset.order_by('-lodgement_number')

        try:
           queryset = super(DcvPermitFilterBackend, self).filter_queryset(request, queryset, view)
        except Exception as e:
           logger.exception(f'Failed to filter the queryset.  Error: [{e}].')
        setattr(view, '_datatables_total_count', total_count)
        return queryset


class DcvPermitPaginatedViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = (DcvPermitFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    queryset = DcvPermit.objects.none()
    serializer_class = ListDcvPermitSerializer
    permission_classes=[InternalApprovalPermission]

    def get_queryset(self):
        qs = DcvPermit.objects.none()

        if is_internal(self.request):
            qs = DcvPermit.objects.exclude(lodgement_number__isnull=True)

        return qs


class DcvVesselViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = DcvVessel.objects.all().order_by('id')
    serializer_class = DcvVesselSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = DcvVessel.objects.all().order_by('id')
            return qs
        elif is_customer(self.request):
            queryset = DcvVessel.objects.filter(
                Q(dcv_permits__applicant=user.id) |
                Q(dcv_admissions__applicant=user.id)
            ).distinct('id')
            return queryset
        return DcvVessel.objects.none()

    @detail_route(methods=['GET',], detail=True)
    @basic_exception_handler
    def lookup_dcv_vessel(self, request, *args, **kwargs):
        dcv_vessel = self.get_object()
        serializer = DcvVesselSerializer(dcv_vessel)
        dcv_vessel_data = serializer.data
        return Response(dcv_vessel_data)


class DcvAdmissionFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        total_count = queryset.count()

        # filter by dcv_organisation
        filter_organisation_id = request.GET.get('filter_dcv_organisation_id')
        if filter_organisation_id and not filter_organisation_id.lower() == 'all':
            queryset = queryset.filter(dcv_organisation__id=filter_organisation_id)

        queries = Q()
        # filter by date from
        filter_date_from = request.GET.get('filter_date_from')
        if filter_date_from and not filter_date_from.lower() == 'all':
            filter_date_from = datetime.strptime(filter_date_from, '%d/%m/%Y')
            queries &= Q(dcv_admission_arrivals__arrival_date__gte=filter_date_from)
        # filter by date to
        filter_date_to = request.GET.get('filter_date_to')
        if filter_date_to and not filter_date_to.lower() == 'all':
            filter_date_to = datetime.strptime(filter_date_to, '%d/%m/%Y')
            queries &= Q(dcv_admission_arrivals__arrival_date__lte=filter_date_to) 
              
        # remove cancelled
        queries &= ~Q(status=DcvAdmission.DCV_ADMISSION_STATUS_CANCELLED)
        queryset = queryset.filter(queries)

        fields = self.get_fields(request)
        ordering = self.get_ordering(request, view, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)
        else:
            queryset = queryset.order_by('-lodgement_number')

        try:
            queryset = super(DcvAdmissionFilterBackend, self).filter_queryset(request, queryset, view)
        except Exception as e:
            print(e)
        setattr(view, '_datatables_total_count', total_count)
        return queryset
    

class StickerFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        total_count = queryset.count()
        search_text= request.GET.get('search[value]', '') 

        # Filter by approval types (wla, aap, aup, ml)
        filter_approval_type = request.GET.get('filter_approval_type')
        if filter_approval_type and not filter_approval_type.lower() == 'all':
            if filter_approval_type == 'wla':
                queryset = queryset.filter(approval__in=Approval.objects.filter(waitinglistallocation__in=WaitingListAllocation.objects.all()))
            elif filter_approval_type == 'aap':
                queryset = queryset.filter(approval__in=Approval.objects.filter(annualadmissionpermit__in=AnnualAdmissionPermit.objects.all()))
            elif filter_approval_type == 'aup':
                queryset = queryset.filter(approval__in=Approval.objects.filter(authoriseduserpermit__in=AuthorisedUserPermit.objects.all()))
            elif filter_approval_type == 'ml':
                queryset = queryset.filter(approval__in=Approval.objects.filter(mooringlicence__in=MooringLicence.objects.all()))

        # Filter Year (FeeSeason)
        filter_year = request.GET.get('filter_year')
        if filter_year and not filter_year.lower() == 'all':
            filter_year = datetime.strptime(filter_year, '%Y-%m-%d').date()
            fee_seasons = FeePeriod.objects.filter(start_date=filter_year).values_list('fee_season')
            queryset = queryset.filter(fee_constructor__fee_season__in=fee_seasons)

        # Filter sticker status
        filter_sticker_status_id = request.GET.get('filter_sticker_status')
        if filter_sticker_status_id and not filter_sticker_status_id.lower() == 'all':
            queryset = queryset.filter(status=filter_sticker_status_id)

        #re-arranged filter so that: 
        #1) if the records in ledger and local are different they do not cancel each other out
        #2) other filters DO override the custom search
        try:
            super_queryset = super(StickerFilterBackend, self).filter_queryset(request, queryset, view)

            if search_text:

                system_user_ids = list(SystemUser.objects.annotate(full_name=Concat('legal_first_name',Value(" "),'legal_last_name',output_field=CharField()))
                .filter(
                    Q(legal_first_name__icontains=search_text) | Q(legal_last_name__icontains=search_text) | Q(email__icontains=search_text) | Q(full_name__icontains=search_text)
                ).values_list("ledger_id", flat=True))

                proposal_applicant_proposals = list(ProposalApplicant.objects.annotate(full_name=Concat('first_name',Value(" "),'last_name',output_field=CharField()))
                .filter(
                    Q(first_name__icontains=search_text) | Q(last_name__icontains=search_text) | Q(email__icontains=search_text) | Q(full_name__icontains=search_text)
                ).values_list("proposal_id", flat=True))

                q_set = queryset.filter(Q(approval__current_proposal__id__in=proposal_applicant_proposals)|Q(approval__submitter__in=system_user_ids)|Q(vessel_ownership__vessel__rego_no__icontains=search_text))
                queryset = super_queryset.union(q_set)
        except Exception as e:
            print(e)

        fields = self.get_fields(request)
        ordering = self.get_ordering(request, view, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)

        total_count = queryset.count()
        setattr(view, '_datatables_filtered_count', total_count)

        return queryset


class StickerViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = Sticker.objects.none()
    serializer_class = StickerSerializer
    permission_classes=[InternalApprovalPermission]

    def get_queryset(self):
        qs = Sticker.objects.none()
        if is_internal(self.request):
            qs = Sticker.objects.all()
        return qs

    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def record_returned(self, request, *args, **kwargs):
        sticker = self.get_object()
        data = request.data

        if not sticker.printing_date or not (sticker.status == "to_be_returned"):
            raise serializers.ValidationError("cannot return a sticker that has not yet been printed")

        # Update Sticker action
        data['sticker'] = sticker.id
        data['action'] = 'Record returned'
        data['user'] = request.user.id
        serializer = StickerActionDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Update Sticker
        sticker.record_returned()
        serializer = StickerSerializer(sticker)

        ApprovalUserAction.log_action(sticker.approval,ApprovalUserAction.ACTION_STICKER_RETURNED.format(sticker.number),request.user)

        return Response({'sticker': serializer.data})

    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def record_lost(self, request, *args, **kwargs):
        sticker = self.get_object()
        data = request.data

        if not sticker.printing_date or not (sticker.status == "current" or sticker.status == "to_be_returned"):
            raise serializers.ValidationError("cannot lose a sticker that has not yet been printed")

        # Update Sticker action
        data['sticker'] = sticker.id
        data['action'] = 'Record lost'
        data['user'] = request.user.id
        serializer = StickerActionDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        details = serializer.save()

        # Update Sticker
        sticker.record_lost()
        serializer = StickerSerializer(sticker)

        ApprovalUserAction.log_action(sticker.approval,ApprovalUserAction.ACTION_STICKER_LOST.format(sticker.number),request.user)

        return Response({'sticker': serializer.data})

    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def request_replacement(self, request, *args, **kwargs):
        # internal
        sticker = self.get_object()
        data = {}

        if not sticker.printing_date or not (sticker.status == "current"):
            raise serializers.ValidationError("cannot replace a sticker that has not yet been printed")

        # Update Sticker action
        data['waive_the_fee'] = request.data.get('waive_the_fee', False)
        data['sticker'] = sticker.id
        data['action'] = 'Request replacement'
        data['user'] = request.user.id
        data['reason'] = request.data.get('details', {}).get('reason', '')
        serializer = StickerActionDetailSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        details = serializer.save()

        ApprovalUserAction.log_action(sticker.approval,ApprovalUserAction.ACTION_REQUEST_NEW_STICKER.format(sticker.number),request.user)

        return Response({'sticker_action_detail_ids': [details.id,]})

    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def cancel(self, request, *args, **kwargs):
        # internal
        sticker = self.get_object()
        data = {}

        if not sticker.status in [Sticker.STICKER_STATUS_READY,Sticker.STICKER_STATUS_NOT_READY_YET]:
            raise serializers.ValidationError("cannot cancel a sticker that has already been exported")

        # Update Sticker action
        data['sticker'] = sticker.id
        data['action'] = 'Cancel sticker'
        data['user'] = request.user.id
        if is_internal(request):
            data['waive_the_fee'] = request.data.get('waive_the_fee', False) 
        else:
            data['waive_the_fee'] = False
        data['reason'] = request.data.get('details', {}).get('reason', '')
        serializer = StickerActionDetailSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        details = serializer.save()

        ApprovalUserAction.log_action(sticker.approval,ApprovalUserAction.ACTION_REQUEST_NEW_STICKER.format(sticker.number),request.user)

        # Update Sticker
        sticker.cancel()
        serializer = StickerSerializer(sticker)

        return Response({'sticker': serializer.data})


class StickerPaginatedViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = (StickerFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    queryset = Sticker.objects.none()
    serializer_class = StickerSerializer
    permission_classes=[InternalApprovalPermission]

    def get_queryset(self):
        qs = Sticker.objects.none()
        if is_internal(self.request):
            qs = Sticker.objects.filter(status__in=Sticker.EXPOSED_STATUS).order_by('-date_updated', '-date_created')
        return qs

class NonExportedStickerPaginatedViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = (StickerFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    queryset = Sticker.objects.none()
    serializer_class = NonExportedStickerSerializer
    permission_classes=[InternalApprovalPermission]

    def get_queryset(self):
        qs = Sticker.objects.none()
        if is_internal(self.request):
            qs = Sticker.objects.exclude(status__in=Sticker.EXPOSED_STATUS).order_by('-date_updated', '-date_created')
        return qs

class DcvAdmissionPaginatedViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = (DcvAdmissionFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    queryset = DcvAdmission.objects.none()
    serializer_class = ListDcvAdmissionSerializer
    permission_classes=[InternalApprovalPermission]

    def get_queryset(self):
        qs = DcvAdmission.objects.none()
        if is_internal(self.request):
            qs = DcvAdmission.objects.all()

        return qs


class WaitingListAllocationViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = WaitingListAllocation.objects.all().order_by('id')
    serializer_class = WaitingListAllocationSerializer
    permission_classes=[InternalApprovalPermission]

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            qs = WaitingListAllocation.objects.all()
            return qs
        return WaitingListAllocation.objects.none()


    @detail_route(methods=['POST',], detail=True)
    @basic_exception_handler
    def create_mooring_licence_application(self, request, *args, **kwargs):
        with transaction.atomic():
            if is_internal(request):
                waiting_list_allocation = self.get_object()
                proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)
                selected_mooring_id = request.data.get("selected_mooring_id")
                no_email_notifications = request.data.get("no_emails")
                allocated_mooring = Mooring.objects.get(id=selected_mooring_id)

                current_date = datetime.now(pytz.timezone(TIME_ZONE)).date()

                #get all waiting list allocation proposals, check their status
                #if any are a status other than approved, declined, discarded, or expired - block 
                related_wla = Proposal.objects.filter(approval_id=waiting_list_allocation.id).exclude(
                    Q(processing_status=Proposal.PROCESSING_STATUS_APPROVED)|
                    Q(processing_status=Proposal.PROCESSING_STATUS_DECLINED)|
                    Q(processing_status=Proposal.PROCESSING_STATUS_DISCARDED)|
                    Q(processing_status=Proposal.PROCESSING_STATUS_EXPIRED)
                )

                if related_wla.exists():
                    raise serializers.ValidationError("an offer cannot be made while the waiting list allocation has an ongoing amendment/renewal application")

                new_proposal = None
                if allocated_mooring:
                    new_proposal = MooringLicenceApplication.objects.create(
                        submitter=request.user.id, #the user that had created the application, not the applicant
                        proposal_type=proposal_type,
                        allocated_mooring=allocated_mooring,
                        waiting_list_allocation=waiting_list_allocation,
                        date_invited=current_date,
                        no_email_notifications=no_email_notifications,
                    )
                    waiting_list_allocation.proposal_applicant.copy_self_to_proposal(new_proposal)
                    logger.info(f'Offering new Mooring Site Licence application: [{new_proposal}], which has been created from the waiting list allocation: [{waiting_list_allocation}].')

                    # Copy vessel details to the new proposal
                    waiting_list_allocation.current_proposal.copy_vessel_details(new_proposal)
                    logger.info(f'Vessel details have been copied from the proposal: [{waiting_list_allocation.current_proposal}] to the mooring site licence application: [{new_proposal}].')

                    new_proposal.null_vessel_on_create = False
                    new_proposal.save()

                    waiting_list_allocation.log_user_action(f'Offer new Mooring Site Licence application: {new_proposal.lodgement_number}.', request)

                    #proposal creation action log
                    new_proposal.log_user_action(f'Proposal: {new_proposal} created as offer from {waiting_list_allocation}.', request)

                if new_proposal:
                    # send email
                    send_create_mooring_licence_application_email_notification(request, waiting_list_allocation, new_proposal)
                    # update waiting_list_allocation
                    waiting_list_allocation.internal_status = Approval.INTERNAL_STATUS_OFFERED
                    waiting_list_allocation.wla_order = None
                    waiting_list_allocation.save()
                    waiting_list_allocation.set_wla_order()

                return Response({"proposal_created": new_proposal.lodgement_number})
            else:
                raise serializers.ValidationError("user not authorised to create mooring licence application")