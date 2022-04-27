import traceback
from confy import env
import datetime
import pytz
from rest_framework_datatables.renderers import DatatablesRenderer
from django.db.models import Q
from django.db import transaction
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.conf import settings
from rest_framework import viewsets, serializers, generics, views, status
from rest_framework.decorators import detail_route, list_route, renderer_classes
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from ledger.accounts.models import EmailUser
from ledger.settings_base import TIME_ZONE
from datetime import datetime
from collections import OrderedDict

from django.core.cache import cache
from mooringlicensing import forms
from mooringlicensing.components.proposals.email import send_create_mooring_licence_application_email_notification
from mooringlicensing.components.main.decorators import basic_exception_handler, query_debugger
from mooringlicensing.components.payments_ml.api import logger
from mooringlicensing.components.payments_ml.models import FeeSeason
from mooringlicensing.components.payments_ml.serializers import DcvPermitSerializer, DcvAdmissionSerializer, \
    DcvAdmissionArrivalSerializer, NumberOfPeopleSerializer
from mooringlicensing.components.proposals.models import Proposal, MooringLicenceApplication, ProposalType, Mooring#, ApplicationType
from mooringlicensing.components.approvals.models import (
    Approval,
    DcvPermit, DcvOrganisation, DcvVessel, DcvAdmission, AdmissionType, AgeGroup,
    WaitingListAllocation, Sticker, MooringLicence,AuthorisedUserPermit, AnnualAdmissionPermit
)
from mooringlicensing.components.main.process_document import (
        process_generic_document, 
        )
from mooringlicensing.components.approvals.serializers import (
    WaitingListAllocationSerializer,
    ApprovalSerializer,
    ApprovalCancellationSerializer,
    ApprovalSuspensionSerializer,
    ApprovalSurrenderSerializer,
    ApprovalUserActionSerializer,
    ApprovalLogEntrySerializer,
    ApprovalPaymentSerializer,
    ListApprovalSerializer,
    DcvOrganisationSerializer,
    DcvVesselSerializer,
    ListDcvPermitSerializer,
    ListDcvAdmissionSerializer,
    EmailUserSerializer, StickerSerializer, StickerActionDetailSerializer,
    ApprovalHistorySerializer, LookupDcvAdmissionSerializer, LookupDcvPermitSerializer, StickerForDcvSaveSerializer,
)
from mooringlicensing.components.users.serializers import UserSerializer
from mooringlicensing.components.organisations.models import Organisation, OrganisationContact
from mooringlicensing.helpers import is_customer, is_internal
from mooringlicensing.settings import PROPOSAL_TYPE_NEW
from rest_framework_datatables.pagination import DatatablesPageNumberPagination
from rest_framework_datatables.filters import DatatablesFilterBackend
from rest_framework import filters


class GetDailyAdmissionUrl(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        daily_admission_url = env('DAILY_ADMISSION_PAGE_URL', '')
        data = {'daily_admission_url': daily_admission_url}
        return Response(data)


class GetStickerStatusDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        from mooringlicensing.components.main.models import ApplicationType
        data = []
        for status in Sticker.STATUS_CHOICES:
            if status[0] in Sticker.STATUSES_FOR_FILTER:
                data.append({'id': status[0], 'display': status[1]})
        return Response(data)


class GetFeeSeasonsDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        from mooringlicensing.components.main.models import ApplicationType

        application_type_codes = request.GET.get('application_type_codes', '')

        if application_type_codes:
            application_type_codes = application_type_codes.split(',')
            application_types = []
            for app_code in application_type_codes:
                application_type = ApplicationType.objects.filter(code=app_code)
                if application_type:
                    application_types.append(application_type.first())
            data = [{'id': season.id, 'name': season.name} for season in FeeSeason.objects.filter(application_type__in=application_types)]
        else:
            data = [{'id': season.id, 'name': season.name} for season in FeeSeason.objects.all()]
        return Response(data)


class GetSticker(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        search_term = request.GET.get('term', '')
        if search_term:
            data = Sticker.objects.filter(number__icontains=search_term)[:10]
            data_transform = []
            for sticker in data:
                approval_history = sticker.approvalhistory_set.order_by('id').first()  # Should not be None, but could be None for the data generated at the early stage of development.
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
                else:
                    # Should not reach here
                    pass

            return Response({"results": data_transform})
        return Response()


class GetApprovalTypeDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        include_codes = request.GET.get('include_codes', '')
        include_codes = include_codes.split(',')
        cache_title = 'approval_type_dict'
        for code in include_codes:
            cache_title += '_' + code
        data = cache.get(cache_title)
        if not data:
            cache.set(cache_title, Approval.approval_types_dict(include_codes), settings.LOV_CACHE_TIMEOUT)
            data = cache.get(cache_title)
        return Response(data)


class GetApprovalStatusesDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        data = cache.get('approval_statuses_dict')
        if not data:
            cache.set('approval_statuses_dict',[{'code': i[0], 'description': i[1]} for i in Approval.STATUS_CHOICES], settings.LOV_CACHE_TIMEOUT)
            data = cache.get('approval_statuses_dict')
        return Response(data)


class GetWlaAllowed(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        from mooringlicensing.components.proposals.models import WaitingListApplication
        wla_allowed = True
        # Person can have only one WLA, Waiting Liast application, Mooring Licence and Mooring Licence application
        if (WaitingListApplication.objects.filter(submitter=request.user).exclude(processing_status__in=['approved', 'declined', 'discarded']) or
            WaitingListAllocation.objects.filter(submitter=request.user).exclude(status__in=['cancelled', 'expired', 'surrendered']) or
            MooringLicenceApplication.objects.filter(submitter=request.user).exclude(processing_status__in=['approved', 'declined', 'discarded']) or
            MooringLicence.objects.filter(submitter=request.user).filter(status__in=['current', 'suspended'])):
            wla_allowed = False
        return Response({"wla_allowed": wla_allowed})


class ApprovalPaymentFilterViewSet(generics.ListAPIView):
    """ https://cop-internal.dbca.wa.gov.au/api/filtered_organisations?search=Org1
    """
    queryset = Approval.objects.none()
    serializer_class = ApprovalPaymentSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('id',)

    def get_queryset(self):
        """
        Return All approvals associated with user (proxy_applicant and org_applicant)
        """
        user = self.request.user

        # get all orgs associated with user
        user_org_ids = OrganisationContact.objects.filter(email=user.email).values_list('organisation_id', flat=True)

        now = datetime.now().date()
        approval_qs =  Approval.objects.filter(Q(proxy_applicant=user) | Q(org_applicant_id__in=user_org_ids) | Q(submitter_id=user))
        approval_qs =  approval_qs.exclude(current_proposal__application_type__name='E Class')
        approval_qs =  approval_qs.exclude(expiry_date__lt=now)
        approval_qs =  approval_qs.exclude(replaced_by__isnull=False) # get lastest licence, ignore the amended
        return approval_qs

    @list_route(methods=['GET',])
    def _list(self, request, *args, **kwargs):
        data =  []
        for approval in self.get_queryset():
            data.append(dict(lodgement_number=approval.lodgement_number, current_proposal=approval.current_proposal_id))
        return Response(data)


class ApprovalFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        total_count = queryset.count()
        filter_query = Q()
        # status filter
        filter_status = request.GET.get('filter_status')
        if filter_status and not filter_status.lower() == 'all':
            filter_query &= Q(status=filter_status)
        # mooring bay filter
        filter_mooring_bay_id = request.GET.get('filter_mooring_bay_id')
        if filter_mooring_bay_id and not filter_mooring_bay_id.lower() == 'all':
            filter_query &= Q(current_proposal__preferred_bay__id=filter_mooring_bay_id)
        # holder id filter
        filter_holder_id = request.GET.get('filter_holder_id')
        if filter_holder_id and not filter_holder_id.lower() == 'all':
            filter_query &= Q(submitter__id=filter_holder_id)
        # max vessel length
        max_vessel_length = request.GET.get('max_vessel_length')
        if max_vessel_length:
            filtered_ids = [a.id for a in Approval.objects.all() if a.current_proposal.vessel_details.vessel_applicable_length <= float(max_vessel_length)]
            filter_query &= Q(id__in=filtered_ids)
        # max vessel draft
        max_vessel_draft = request.GET.get('max_vessel_draft')
        if max_vessel_draft:
            filter_query &= Q(current_proposal__vessel_details__vessel_draft__lte=float(max_vessel_draft))

        ml_list = MooringLicence.objects.all()
        aup_list = AuthorisedUserPermit.objects.all()
        aap_list = AnnualAdmissionPermit.objects.all()
        wla_list = WaitingListAllocation.objects.all()
        # Filter by approval types (wla, aap, aup, ml)
        filter_approval_type = request.GET.get('filter_approval_type')
        if filter_approval_type and not filter_approval_type.lower() == 'all':
            filter_approval_type_list = filter_approval_type.split(',')
            if 'wla' in filter_approval_type_list:
                filter_query &= Q(id__in=wla_list)
            else:
                filter_query &= Q(
                        Q(annualadmissionpermit__in=aap_list) |
                        Q(authoriseduserpermit__in=aup_list) |
                        Q(mooringlicence__in=ml_list)
                        )
        # Show/Hide expired and/or surrendered
        show_expired_surrendered = request.GET.get('show_expired_surrendered', 'true')
        show_expired_surrendered = True if show_expired_surrendered.lower() in ['true', 'yes', 't', 'y',] else False
        external_waiting_list = request.GET.get('external_waiting_list')
        external_waiting_list = True if external_waiting_list.lower() in ['true', 'yes', 't', 'y',] else False
        if external_waiting_list and not show_expired_surrendered:
                filter_query &= Q(status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.INTERNAL_STATUS_OFFERED))

        # approval types filter2 - Licences dash only (excludes wla)
        filter_approval_type2 = request.GET.get('filter_approval_type2')
        if filter_approval_type2 and not filter_approval_type2.lower() == 'all':
            if filter_approval_type2 == 'ml':
                filter_query &= Q(id__in=ml_list)
            elif filter_approval_type2 == 'aup':
                filter_query &= Q(id__in=aup_list)
            elif filter_approval_type2 == 'aap':
                filter_query &= Q(id__in=aap_list)
            elif filter_approval_type2 == 'wla':
                filter_query &= Q(id__in=wla_list)

        queryset = queryset.filter(filter_query)
        getter = request.query_params.get
        fields = self.get_fields(getter)
        ordering = self.get_ordering(getter, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)
        try:
            queryset = super(ApprovalFilterBackend, self).filter_queryset(request, queryset, view)
        except Exception as e:
            print(e)
        setattr(view, '_datatables_total_count', total_count)
        return queryset


class ApprovalRenderer(DatatablesRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if 'view' in renderer_context and hasattr(renderer_context['view'], '_datatables_total_count'):
            data['recordsTotal'] = renderer_context['view']._datatables_total_count
        return super(ApprovalRenderer, self).render(data, accepted_media_type, renderer_context)


class ApprovalPaginatedViewSet(viewsets.ModelViewSet):
    filter_backends = (ApprovalFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    renderer_classes = (ApprovalRenderer,)
    queryset = Approval.objects.none()
    serializer_class = ListApprovalSerializer
    search_fields = ['lodgement_number', ]
    page_size = 10

    def get_queryset(self):
        request_user = self.request.user
        all = Approval.objects.all()  # We may need to exclude the approvals created from the Waiting List Application

        target_email_user_id = int(self.request.GET.get('target_email_user_id', 0))

        if is_internal(self.request):
            if target_email_user_id:
                target_user = EmailUser.objects.get(id=target_email_user_id)
                all = all.filter(Q(submitter=target_user))
            return all
        elif is_customer(self.request):
            qs = all.filter(Q(submitter=request_user))
            return qs
        return Approval.objects.none()

    def list(self, request, *args, **kwargs):
        """
        User is accessing /external/ page
        """
        qs = self.get_queryset()
        qs = self.filter_queryset(qs)

        self.paginator.page_size = qs.count()
        result_page = self.paginator.paginate_queryset(qs.order_by('-id'), request)
        serializer = ListApprovalSerializer(result_page, context={'request': request}, many=True)
        return self.paginator.get_paginated_response(serializer.data)


class ApprovalViewSet(viewsets.ModelViewSet):
    queryset = Approval.objects.none()
    serializer_class = ApprovalSerializer

    def get_queryset(self):
        if is_internal(self.request):
            return Approval.objects.all()
        elif is_customer(self.request):
            user_orgs = [org.id for org in self.request.user.mooringlicensing_organisations.all()]
            queryset =  Approval.objects.filter(Q(org_applicant_id__in = user_orgs) | Q(submitter = self.request.user))
            return queryset
        return Approval.objects.none()

    def list(self, request, *args, **kwargs):
        draw = request.GET.get('draw') if request.GET.get('draw') else None
        start = request.GET.get('start') if request.GET.get('draw') else 1
        length = request.GET.get('length') if request.GET.get('draw') else 'all'
        recordFilteredCount = 0
        rowcount = 0
        rowcountend = 0
        if length != 'all': 
            rowcountend = int(start) + int(length)
        queryset = self.get_queryset()
        queryset = self.filter_queryset(request, queryset)
        serializer = ListApprovalSerializer(queryset, many=True)
        return Response(OrderedDict([
            ('recordsTotal', 1),
            ('recordsFiltered',1),
            ('data',serializer.data)
        ]),status=status.HTTP_200_OK)

    @list_route(methods=['GET',])
    @basic_exception_handler
    def existing_licences(self, request, *args, **kwargs):
        existing_licences = []
        l_list = Approval.objects.filter(
                submitter=request.user,
                #status__in=['current', 'fulfilled'],
                status__in=['current'],
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
                        "new_application_text": "I want to amend or renew my current mooring licence {}".format(lchild.lodgement_number)
                        })
            else:
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

    @list_route(methods=['GET'])
    def holder_list(self, request, *args, **kwargs):
        holder_list = self.get_queryset().values_list('submitter__id', flat=True)
        print(holder_list)
        distinct_holder_list = list(dict.fromkeys(holder_list))
        print(distinct_holder_list)
        serializer = EmailUserSerializer(EmailUser.objects.filter(id__in=distinct_holder_list), many=True)
        return Response(serializer.data)

    @detail_route(methods=['GET'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def get_moorings(self, request, *args, **kwargs):
        instance = self.get_object()
        moorings = []
        for moa in instance.mooringonapproval_set.all():
            licence_holder_data = {}
            if moa.mooring.mooring_licence:
                licence_holder_data = UserSerializer(moa.mooring.mooring_licence.submitter).data
            moorings.append({
                "id": moa.id,
                "mooring_name": moa.mooring.name,
                "licensee": licence_holder_data.get('full_name') if licensee else '',
                "mobile": licence_holder_data.get('mobile_number') if licensee else '',
                "email": licence_holder_data.get('email') if licensee else '',
                })
        return Response(moorings)

    @detail_route(methods=['POST'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def request_new_stickers(self, request, *args, **kwargs):
        # external
        approval = self.get_object()
        details = request.data['details']
        # sticker_ids = [sticker['id'] for sticker in request.data['stickers']]
        sticker_ids = []
        for sticker in request.data['stickers']:
            if sticker['checked'] == True:
                sticker_ids.append(sticker['id'])

        # TODO: Validation

        sticker_action_details = []
        stickers = Sticker.objects.filter(approval=approval, id__in=sticker_ids, status__in=(Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING,))
        data = {}
        today = datetime.now(pytz.timezone(settings.TIME_ZONE)).date()
        for sticker in stickers:
            data['action'] = 'Request new sticker'
            data['user'] = request.user.id
            data['reason'] = details['reason']
            data['date_of_lost_sticker'] = today.strftime('%d/%m/%Y')
            serializer = StickerActionDetailSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            new_sticker_action_detail = serializer.save()
            new_sticker_action_detail.sticker = sticker
            new_sticker_action_detail.save()
            sticker_action_details.append(new_sticker_action_detail.id)

        return Response({'sticker_action_detail_ids': sticker_action_details})

    @detail_route(methods=['GET'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def stickers(self, request, *args, **kwargs):
        instance = self.get_object()
        stickers = instance.stickers.filter(status__in=[Sticker.STICKER_STATUS_CURRENT,])
        serializer = StickerSerializer(stickers, many=True)
        return Response({'stickers': serializer.data})

    @detail_route(methods=['GET'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def approval_history(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ApprovalHistorySerializer(instance.approvalhistory_set.all(), many=True)
        return Response(serializer.data)

    @detail_route(methods=['GET'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def lookup_approval(self, request, *args, **kwargs):
        instance = self.get_object()
        approval_details = {
                "approvalType": instance.child_obj.description,
                "approvalLodgementNumber": instance.lodgement_number,
                }
        return Response(approval_details)

    @detail_route(methods=['POST'])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def process_waiting_list_offer_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = process_generic_document(request, instance, document_type='waiting_list_offer_document')
        if returned_data:
            return Response(returned_data)
        else:
            return Response()

    @detail_route(methods=['POST'])
    @renderer_classes((JSONRenderer,))
    def process_document(self, request, *args, **kwargs):
            instance = self.get_object()
            action = request.POST.get('action')
            section = request.POST.get('input_name')
            if action == 'list' and 'input_name' in request.POST:
                pass

            elif action == 'delete' and 'document_id' in request.POST:
                document_id = request.POST.get('document_id')
                document = instance.qaofficer_documents.get(id=document_id)

                document.visible = False
                document.save()
                instance.save(version_comment='Licence ({}): {}'.format(section, document.name)) # to allow revision to be added to reversion history

            elif action == 'save' and 'input_name' in request.POST and 'filename' in request.POST:
                proposal_id = request.POST.get('proposal_id')
                filename = request.POST.get('filename')
                _file = request.POST.get('_file')
                if not _file:
                    _file = request.FILES.get('_file')

                document = instance.qaofficer_documents.get_or_create(input_name=section, name=filename)[0]
                path = default_storage.save('{}/proposals/{}/approvals/{}'.format(settings.MEDIA_APP_DIR, proposal_id, filename), ContentFile(_file.read()))

                document._file = path
                document.save()
                instance.save(version_comment='Licence ({}): {}'.format(section, filename)) # to allow revision to be added to reversion history

            return  Response( [dict(input_name=d.input_name, name=d.name,file=d._file.url, id=d.id, can_delete=d.can_delete) for d in instance.qaofficer_documents.filter(input_name=section, visible=True) if d._file] )

    @detail_route(methods=['POST',])
    def approval_cancellation(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = ApprovalCancellationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.approval_cancellation(request,serializer.validated_data)
            return Response()
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

    @detail_route(methods=['POST',])
    def approval_suspension(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = ApprovalSuspensionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.approval_suspension(request,serializer.validated_data)
            return Response()
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


    @detail_route(methods=['POST',])
    def approval_reinstate(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.reinstate_approval(request)
            return Response()
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

    @detail_route(methods=['POST',])
    def approval_surrender(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = ApprovalSurrenderSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.approval_surrender(request,serializer.validated_data)
            return Response()
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

    @detail_route(methods=['GET',])
    def action_log(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            qs = instance.action_logs.all()
            serializer = ApprovalUserActionSerializer(qs,many=True)
            return Response(serializer.data)
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
            serializer = ApprovalLogEntrySerializer(qs,many=True)
            return Response(serializer.data)
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
                request.data['approval'] = u'{}'.format(instance.id)
                request.data['staff'] = u'{}'.format(request.user.id)
                request.data._mutable=mutable
                serializer = ApprovalLogEntrySerializer(data=request.data)
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
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))


class DcvAdmissionViewSet(viewsets.ModelViewSet):
    queryset = DcvAdmission.objects.all().order_by('id')
    serializer_class = DcvAdmissionSerializer

    @staticmethod
    def _handle_dcv_vessel(dcv_vessel, org_id=None):
        data = dcv_vessel
        rego_no_requested = data.get('rego_no', '')
        vessel_name_requested = data.get('vessel_name', '')
        try:
            dcv_vessel = DcvVessel.objects.get(rego_no=rego_no_requested)
        except DcvVessel.DoesNotExist:
            data['rego_no'] = rego_no_requested
            data['vessel_name'] = vessel_name_requested
            serializer = DcvVesselSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            dcv_vessel = serializer.save()
        except Exception as e:
            logger.error(e)
            raise

        return dcv_vessel

    def create(self, request, *args, **kwargs):
        data = request.data
        dcv_vessel = self._handle_dcv_vessel(request.data.get('dcv_vessel'), None)

        if request.user.is_authenticated():
            # Logged in user
            # 1. DcvPermit exists
            # 2. DcvPermit doesn't exist

            submitter = request.user
            if not dcv_vessel.dcv_permits.count():
                # No DcvPermit found, create DcvOrganisation and link it to DcvVessel
                my_data = {}
                my_data['organisation'] = request.data.get('organisation_name')
                my_data['abn_acn'] = request.data.get('organisation_abn')
                dcv_organisation = DcvPermitViewSet.handle_dcv_organisation(my_data)
                dcv_vessel.dcv_organisation = dcv_organisation
                dcv_vessel.save()

        else:
            # Anonymous user
            # 1. DcvPermit exists
            # 2. DcvPermit doesn't exist
            if dcv_vessel.dcv_permits.count():
                # DcvPermit exists
                submitter = dcv_vessel.dcv_permits.first().submitter
            else:
                # DcvPermit doesn't exist
                email_address = request.data.get('email_address')
                email_address_confirmation = request.data.get('email_address_confirmation')
                skipper = request.data.get('skipper')
                if email_address and email_address_confirmation:
                    if email_address == email_address_confirmation:
                        if skipper:
                            this_user = EmailUser.objects.filter(email=email_address)
                            if this_user:
                                new_user = this_user.first()
                            else:
                                new_user = EmailUser.objects.create(email=email_address, first_name=skipper)
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
                dcv_organisation = DcvPermitViewSet.handle_dcv_organisation(my_data)
                dcv_vessel.dcv_organisation = dcv_organisation
                dcv_vessel.save()

        data['submitter'] = submitter.id
        data['dcv_vessel_id'] = dcv_vessel.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        dcv_admission = serializer.save()

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


class DcvPermitViewSet(viewsets.ModelViewSet):
    queryset = DcvPermit.objects.all().order_by('id')
    serializer_class = DcvPermitSerializer

    @staticmethod
    def handle_dcv_organisation(data):
        abn_requested = data.get('abn_acn', '')
        name_requested = data.get('organisation', '')
        try:
            dcv_organisation = DcvOrganisation.objects.get(abn=abn_requested)
        except DcvOrganisation.DoesNotExist:
            data['name'] = name_requested
            data['abn'] = abn_requested
            serializer = DcvOrganisationSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            dcv_organisation = serializer.save()
        except Exception as e:
            logger.error(e)
            raise

        return dcv_organisation

    @staticmethod
    def _handle_dcv_vessel(request, org_id=None):
        data = request.data
        rego_no_requested = request.data.get('dcv_vessel').get('rego_no', '')
        vessel_name_requested = request.data.get('dcv_vessel').get('vessel_name', '')
        try:
            dcv_vessel = DcvVessel.objects.get(rego_no=rego_no_requested)
        except DcvVessel.DoesNotExist:
            data['rego_no'] = rego_no_requested
            data['vessel_name'] = vessel_name_requested
            data['dcv_organisation_id'] = org_id
            serializer = DcvVesselSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            dcv_vessel = serializer.save()
        except Exception as e:
            logger.error(e)
            raise

        return dcv_vessel

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def create_new_sticker(self, request, *args, **kwargs):
        instance = self.get_object()

        mailed_date = None
        if request.data['mailed_date']:
            mailed_date = datetime.strptime(request.data['mailed_date'], '%d/%m/%Y').date()

        sticker_number = request.data['sticker_number']
        sticker_number = int(sticker_number)

        data = {}
        data['number'] = sticker_number
        data['mailing_date'] = mailed_date
        data['dcv_permit'] = instance.id
        data['status'] = Sticker.STICKER_STATUS_CURRENT

        serializer = StickerForDcvSaveSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        sticker = serializer.save()

        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        data = request.data

        dcv_organisation = self.handle_dcv_organisation(request.data)
        dcv_vessel = self._handle_dcv_vessel(request, dcv_organisation.id)
        fee_season_requested = data.get('season') if data.get('season') else {'id': 0, 'name': ''}

        data['submitter'] = request.user.id
        data['dcv_vessel_id'] = dcv_vessel.id
        data['dcv_organisation_id'] = dcv_organisation.id
        data['fee_season_id'] = fee_season_requested.get('id')
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        dcv_permit = serializer.save()

        return Response(serializer.data)


class DcvPermitFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        total_count = queryset.count()

        # filter by dcv_organisation
        filter_organisation_id = request.GET.get('filter_dcv_organisation_id')
        if filter_organisation_id and not filter_organisation_id.lower() == 'all':
            queryset = queryset.filter(dcv_organisation__id=filter_organisation_id)
        # filter by season
        filter_fee_season_id = request.GET.get('filter_fee_season_id')
        if filter_fee_season_id and not filter_fee_season_id.lower() == 'all':
            queryset = queryset.filter(fee_season__id=filter_fee_season_id)

        getter = request.query_params.get
        fields = self.get_fields(getter)
        ordering = self.get_ordering(getter, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)
        else:
            queryset = queryset.order_by('-lodgement_number')

        try:
            queryset = super(DcvPermitFilterBackend, self).filter_queryset(request, queryset, view)
        except Exception as e:
            print(e)
        setattr(view, '_datatables_total_count', total_count)
        return queryset


class DcvPermitRenderer(DatatablesRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if 'view' in renderer_context and hasattr(renderer_context['view'], '_datatables_total_count'):
            data['recordsTotal'] = renderer_context['view']._datatables_total_count
        return super(DcvPermitRenderer, self).render(data, accepted_media_type, renderer_context)


class DcvPermitPaginatedViewSet(viewsets.ModelViewSet):
    filter_backends = (DcvPermitFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    renderer_classes = (DcvPermitRenderer,)
    queryset = DcvPermit.objects.none()
    serializer_class = ListDcvPermitSerializer
    search_fields = ['lodgement_number', ]
    page_size = 10
    ordering = ['-id']

    def get_queryset(self):
        request_user = self.request.user
        qs = DcvPermit.objects.none()

        if is_internal(self.request):
            qs = DcvPermit.objects.all()

        return qs

    @list_route(methods=['GET',])
    def list_external(self, request, *args, **kwargs):
        """
        User is accessing /external/ page
        """
        qs = self.get_queryset()
        qs = self.filter_queryset(qs)

        self.paginator.page_size = qs.count()
        result_page = self.paginator.paginate_queryset(qs, request)
        serializer = ListDcvPermitSerializer(result_page, context={'request': request}, many=True)
        return self.paginator.get_paginated_response(serializer.data)


class DcvVesselViewSet(viewsets.ModelViewSet):
    queryset = DcvVessel.objects.all().order_by('id')
    serializer_class = DcvVesselSerializer

    @detail_route(methods=['GET',])
    @basic_exception_handler
    def lookup_dcv_vessel(self, request, *args, **kwargs):
        dcv_vessel = self.get_object()
        serializer = DcvVesselSerializer(dcv_vessel)

        dcv_vessel_data = serializer.data
        dcv_vessel_data['annual_admission_permits'] = []  # TODO: retrieve the permits
        dcv_vessel_data['authorised_user_permits'] = []  # TODO: retrieve the permits
        dcv_vessel_data['mooring_licence'] = []  # TODO: retrieve the licences

        return Response(dcv_vessel_data)

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def find_related_admissions(self, request, *args, **kwargs):
        vessel = self.get_object()
        selected_date_str = request.data.get("selected_date")
        selected_date = None
        if selected_date_str:
            selected_date = datetime.strptime(selected_date_str, '%d/%m/%Y').date()
        admissions = DcvAdmission.objects.filter(dcv_vessel=vessel)
        serializer = LookupDcvAdmissionSerializer(admissions, many=True)
        return Response(serializer.data)

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def find_related_permits(self, request, *args, **kwargs):
        vessel = self.get_object()
        selected_date_str = request.data.get("selected_date")
        selected_date = None
        if selected_date_str:
            selected_date = datetime.strptime(selected_date_str, '%d/%m/%Y').date()
        admissions = DcvPermit.objects.filter(dcv_vessel=vessel)
        serializer = LookupDcvPermitSerializer(admissions, many=True)
        return Response(serializer.data)


class DcvAdmissionFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        total_count = queryset.count()

        # filter by dcv_organisation
        filter_organisation_id = request.GET.get('filter_dcv_organisation_id')
        if filter_organisation_id and not filter_organisation_id.lower() == 'all':
            queryset = queryset.filter(dcv_vessel__dcv_organisation__id=filter_organisation_id)

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
        queryset = queryset.filter(queries)

        getter = request.query_params.get
        fields = self.get_fields(getter)
        ordering = self.get_ordering(getter, fields)
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


class DcvAdmissionRenderer(DatatablesRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if 'view' in renderer_context and hasattr(renderer_context['view'], '_datatables_total_count'):
            data['recordsTotal'] = renderer_context['view']._datatables_total_count
        return super(DcvAdmissionRenderer, self).render(data, accepted_media_type, renderer_context)


class StickerRenderer(DatatablesRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if 'view' in renderer_context and hasattr(renderer_context['view'], '_datatables_total_count'):
            data['recordsTotal'] = renderer_context['view']._datatables_total_count
        return super(StickerRenderer, self).render(data, accepted_media_type, renderer_context)


class StickerFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        total_count = queryset.count()

        # Filter by approval types (wla, aap, aup, ml)
        filter_approval_type = request.GET.get('filter_approval_type')
        #import ipdb; ipdb.set_trace()
        if filter_approval_type and not filter_approval_type.lower() == 'all':
            filter_approval_type_list = filter_approval_type.split(',')
            filtered_ids = [a.id for a in Approval.objects.all() if a.child_obj.code in filter_approval_type_list]
            queryset = queryset.filter(approval__id__in=filtered_ids)

        # Filter Year (FeeSeason)
        filter_fee_season_id = request.GET.get('filter_year')
        if filter_fee_season_id and not filter_fee_season_id.lower() == 'all':
            fee_season = FeeSeason.objects.get(id=filter_fee_season_id)
            queryset = queryset.filter(fee_constructor__fee_season=fee_season)

        # Filter sticker status
        filter_sticker_status_id = request.GET.get('filter_sticker_status')
        if filter_sticker_status_id and not filter_sticker_status_id.lower() == 'all':
            queryset = queryset.filter(status=filter_sticker_status_id)

        getter = request.query_params.get
        fields = self.get_fields(getter)
        ordering = self.get_ordering(getter, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)

        try:
            queryset = super(StickerFilterBackend, self).filter_queryset(request, queryset, view)
        except Exception as e:
            print(e)
        setattr(view, '_datatables_total_count', total_count)
        return queryset


class StickerViewSet(viewsets.ModelViewSet):
    queryset = Sticker.objects.none()
    serializer_class = StickerSerializer

    def get_queryset(self):
        qs = Sticker.objects.none()
        if is_internal(self.request):
            qs = Sticker.objects.all()
        return qs

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def record_returned(self, request, *args, **kwargs):
        sticker = self.get_object()
        data = request.data

        # Update Sticker action
        data['sticker'] = sticker.id
        data['action'] = 'Record returned'
        data['user'] = request.user.id
        serializer = StickerActionDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        details = serializer.save()

        # Update Sticker
        sticker.record_returned()
        serializer = StickerSerializer(sticker)
        return Response({'sticker': serializer.data})

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def record_lost(self, request, *args, **kwargs):
        sticker = self.get_object()
        data = request.data

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

        # Write approval history
        # sticker.approval.write_approval_history()

        return Response({'sticker': serializer.data})

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def request_replacement(self, request, *args, **kwargs):
        # internal
        sticker = self.get_object()
        data = request.data

        # Update Sticker action
        data['sticker'] = sticker.id
        data['action'] = 'Request replacement'
        data['user'] = request.user.id
        serializer = StickerActionDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        details = serializer.save()

        return Response({'sticker_action_detail_ids': [details.id,]})


class StickerPaginatedViewSet(viewsets.ModelViewSet):
    filter_backends = (StickerFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    renderer_classes = (StickerRenderer,)
    queryset = Sticker.objects.none()
    serializer_class = StickerSerializer
    search_fields = ['id', ]
    page_size = 10

    def get_queryset(self):
        debug = self.request.GET.get('debug', 'f')
        if debug.lower() in ['true', 't', 'yes', 'y']:
            debug = True
        else:
            debug = False

        qs = Sticker.objects.none()
        if is_internal(self.request):
            if debug:
                qs = Sticker.objects.all()
            else:
                qs = Sticker.objects.filter(status__in=Sticker.EXPOSED_STATUS)
        return qs


class DcvAdmissionPaginatedViewSet(viewsets.ModelViewSet):
    filter_backends = (DcvAdmissionFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    renderer_classes = (DcvAdmissionRenderer,)
    queryset = DcvAdmission.objects.none()
    serializer_class = ListDcvAdmissionSerializer
    search_fields = ['lodgement_number', ]
    page_size = 10

    def get_queryset(self):
        request_user = self.request.user
        qs = DcvAdmission.objects.none()

        if is_internal(self.request):
            qs = DcvAdmission.objects.all()

        return qs

    @list_route(methods=['GET',])
    def list_external(self, request, *args, **kwargs):
        """
        User is accessing /external/ page
        """
        qs = self.get_queryset()
        qs = self.filter_queryset(qs)

        self.paginator.page_size = qs.count()
        result_page = self.paginator.paginate_queryset(qs, request)
        serializer = ListDcvAdmissionSerializer(result_page, context={'request': request}, many=True)
        return self.paginator.get_paginated_response(serializer.data)


class WaitingListAllocationViewSet(viewsets.ModelViewSet):
    queryset = WaitingListAllocation.objects.all().order_by('id')
    serializer_class = WaitingListAllocationSerializer

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def create_mooring_licence_application(self, request, *args, **kwargs):
        with transaction.atomic():
            waiting_list_allocation = self.get_object()
            proposal_type = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)
            selected_mooring_id = request.data.get("selected_mooring_id")
            allocated_mooring = Mooring.objects.get(id=selected_mooring_id)

            current_date = datetime.now(pytz.timezone(TIME_ZONE)).date()

            new_proposal = None
            if allocated_mooring:
                new_proposal = MooringLicenceApplication.objects.create(
                        submitter=waiting_list_allocation.submitter,
                        proposal_type=proposal_type,
                        allocated_mooring=allocated_mooring,
                        waiting_list_allocation=waiting_list_allocation,
                        date_invited=current_date,
                        )
            if new_proposal:
                # send email
                send_create_mooring_licence_application_email_notification(request, waiting_list_allocation, new_proposal)
                # update waiting_list_allocation
                waiting_list_allocation.internal_status = 'offered'
                waiting_list_allocation.save()
            return Response({"proposal_created": new_proposal.lodgement_number})


class MooringLicenceViewSet(viewsets.ModelViewSet):
    queryset = MooringLicence.objects.all().order_by('id')
    serializer_class = ApprovalSerializer

