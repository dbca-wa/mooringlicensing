import traceback
import datetime
import pytz
from rest_framework_datatables.renderers import DatatablesRenderer
from django.db.models import Q
from django.db import transaction
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.conf import settings
from rest_framework import viewsets, serializers, generics, views
from rest_framework.decorators import detail_route, list_route, renderer_classes
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from ledger.accounts.models import EmailUser
from ledger.settings_base import TIME_ZONE
from datetime import datetime

from mooringlicensing.components.approvals.email import send_create_mooring_licence_application_email_notification
from mooringlicensing.components.main.decorators import basic_exception_handler
from mooringlicensing.components.main.utils import add_cache_control
from mooringlicensing.components.payments_ml.api import logger
from mooringlicensing.components.payments_ml.models import FeeSeason
from mooringlicensing.components.payments_ml.serializers import DcvPermitSerializer, DcvAdmissionSerializer, \
    DcvAdmissionArrivalSerializer, NumberOfPeopleSerializer
from mooringlicensing.components.proposals.models import Proposal, MooringLicenceApplication, ProposalType, Mooring#, ApplicationType
from mooringlicensing.components.approvals.models import (
    Approval,
    ApprovalDocument, DcvPermit, DcvOrganisation, DcvVessel, DcvAdmission, AdmissionType, AgeGroup,
    WaitingListAllocation, Sticker, MooringLicence,
)
from mooringlicensing.components.main.process_document import (
        process_generic_document, 
        )
from mooringlicensing.components.approvals.serializers import (
    ApprovalSerializer,
    ApprovalCancellationSerializer,
    ApprovalExtendSerializer,
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
)
from mooringlicensing.components.organisations.models import Organisation, OrganisationContact
from mooringlicensing.helpers import is_customer, is_internal
from mooringlicensing.settings import PROPOSAL_TYPE_NEW
from rest_framework_datatables.pagination import DatatablesPageNumberPagination
from rest_framework_datatables.filters import DatatablesFilterBackend
from rest_framework import filters


class GetFeeSeasonsDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        data = [{'id': season.id, 'name': season.name} for season in FeeSeason.objects.all()]
        return Response(data)


class GetApprovalTypeDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        include_codes = request.GET.get('include_codes', '')
        include_codes = include_codes.split(',')
        types = Approval.approval_types_dict(include_codes)
        return Response(types)


class GetApprovalStatusesDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        data = [{'code': i[0], 'description': i[1]} for i in Approval.STATUS_CHOICES]
        return Response(data)


class ApprovalPaymentFilterViewSet(generics.ListAPIView):
    """ https://cop-internal.dbca.wa.gov.au/api/filtered_organisations?search=Org1
    """
    queryset = Approval.objects.none()
    serializer_class = ApprovalPaymentSerializer
    filter_backends = (filters.SearchFilter,)
    #search_fields = ('applicant', 'applicant_id',)
    search_fields = ('id',)

    def get_queryset(self):
        """
        Return All approvals associated with user (proxy_applicant and org_applicant)
        """
        #return Approval.objects.filter(proxy_applicant=self.request.user)
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
        #return Response(self.get_queryset().values_list('lodgement_number','current_proposal_id'))


class ApprovalFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        total_count = queryset.count()
        # status filter
        filter_status = request.GET.get('filter_status')
        if filter_status and not filter_status.lower() == 'all':
            queryset = queryset.filter(status=filter_status)
        # mooring bay filter
        filter_mooring_bay_id = request.GET.get('filter_mooring_bay_id')
        if filter_mooring_bay_id and not filter_mooring_bay_id.lower() == 'all':
            queryset = queryset.filter(current_proposal__preferred_bay__id=filter_mooring_bay_id)
        # holder id filter
        filter_holder_id = request.GET.get('filter_holder_id')
        if filter_holder_id and not filter_holder_id.lower() == 'all':
            queryset = queryset.filter(submitter__id=filter_holder_id)
        # max vessel length
        max_vessel_length = request.GET.get('max_vessel_length')
        if max_vessel_length:
            filtered_ids = [a.id for a in Approval.objects.all() if a.current_proposal.vessel_details.vessel_applicable_length <= float(max_vessel_length)]
            queryset = queryset.filter(id__in=filtered_ids)
        # max vessel draft
        max_vessel_draft = request.GET.get('max_vessel_draft')
        if max_vessel_draft:
            queryset = queryset.filter(current_proposal__vessel_details__vessel_draft__lte=float(max_vessel_draft))
            #filtered_ids = [a.id for a in Approval.objects.all() if a.current_proposal.vessel_details.vessel_draft <= max_vessel_draft]
            #queryset = queryset.filter(id__in=filtered_ids)

        # Filter by approval types (wla, aap, aup, ml)
        filter_approval_type = request.GET.get('filter_approval_type')
        #import ipdb; ipdb.set_trace()
        if filter_approval_type and not filter_approval_type.lower() == 'all':
            filter_approval_type_list = filter_approval_type.split(',')
            filtered_ids = [a.id for a in Approval.objects.all() if a.child_obj.code in filter_approval_type_list]
            queryset = queryset.filter(id__in=filtered_ids)
        print(queryset)
        # Show/Hide expired and/or surrendered
        show_expired_surrendered = request.GET.get('show_expired_surrendered', 'true')
        show_expired_surrendered = True if show_expired_surrendered.lower() in ['true', 'yes', 't', 'y',] else False
        if not show_expired_surrendered:
            #queryset = queryset.exclude(status__in=(Approval.APPROVAL_STATUS_EXPIRED, Approval.APPROVAL_STATUS_SURRENDERED))
            queryset = queryset.filter(status__in=(Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_OFFERED))

        # approval types filter2 - Licences dash only (excludes wla)
        filter_approval_type2 = request.GET.get('filter_approval_type2')
        #import ipdb; ipdb.set_trace()
        if filter_approval_type2 and not filter_approval_type2.lower() == 'all':
            #filter_approval_type_list = filter_approval_type.split(',')
            filtered_ids = [a.id for a in Approval.objects.all() if a.child_obj.code == filter_approval_type2]
            queryset = queryset.filter(id__in=filtered_ids)

        ## Filter by status
        #filter_approval_status = request.GET.get('filter_approval_status')
        #if filter_approval_status and not filter_approval_status.lower() == 'all':
        #    queryset = queryset.filter(status=filter_approval_status)

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

        if is_internal(self.request):
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
        # on the internal organisations dashboard, filter the Proposal/Approval/Compliance datatables by applicant/organisation
        # applicant_id = request.GET.get('org_id')
        # if applicant_id:
        #     qs = qs.filter(applicant_id=applicant_id)

        self.paginator.page_size = qs.count()
        result_page = self.paginator.paginate_queryset(qs.order_by('-id'), request)
        serializer = ListApprovalSerializer(result_page, context={'request': request}, many=True)
        return self.paginator.get_paginated_response(serializer.data)

    # def get_queryset(self):
    #     request_user = self.request.user
    #
    #     # Filter by Type(s) according to the tables
    #     filter_approval_types = self.request.GET.get('filter_approval_types', '')
    #     filter_approval_types = filter_approval_types.split(',')
    #     q = Q()
    #     for filter_approval_type in filter_approval_types:
    #         if filter_approval_type:
    #             for item in Approval.__subclasses__():
    #                 if hasattr(item, 'code') and item.code == filter_approval_type:
    #                     lookup = "{}__isnull".format(item._meta.model_name)
    #                     q |= Q(**{lookup: False})
    #     qs = Approval.objects.all()
    #     qs = qs.filter(q).order_by('-id') if q else Approval.objects.none()
    #
    #     if is_internal(self.request):
    #         return qs.all()
    #     elif is_customer(self.request):
    #         # Filter by to_be_endorsed
    #         filter_by_endorsement = self.request.GET.get('filter_by_endorsement', 'false')
    #         filter_by_endorsement = True if filter_by_endorsement.lower() in ['true', 'yes', 't', 'y',] else False
    #         if filter_by_endorsement:
    #             #
    #             qs = qs.filter(authoriseduserpermit__endorsed_by=request_user)
    #         else:
    #             qs = qs.filter(Q(submitter=request_user))  # Not sure if the submitter is the licence holder
    #         return qs
    #     return qs
    #
    # # @list_route(methods=['GET',])
    # def list(self, request, *args, **kwargs):
    #     """
    #     User is accessing /external/ page
    #     """
    #     qs = self.get_queryset()
    #     qs = self.filter_queryset(qs)
    #     # on the internal organisations dashboard, filter the Proposal/Approval/Compliance datatables by applicant/organisation
    #     # applicant_id = request.GET.get('org_id')
    #     # if applicant_id:
    #     #     qs = qs.filter(applicant_id=applicant_id)
    #
    #     self.paginator.page_size = qs.count()
    #     result_page = self.paginator.paginate_queryset(qs, request)
    #     serializer = ListApprovalSerializer(result_page, context={'request': request}, many=True)
    #     return self.paginator.get_paginated_response(serializer.data)


class ApprovalViewSet(viewsets.ModelViewSet):
    #queryset = Approval.objects.all()
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
        #queryset = self.get_queryset()
        queryset = self.get_queryset().order_by('lodgement_number', '-issue_date').distinct('lodgement_number')
        # Filter by org
        org_id = request.GET.get('org_id',None)
        if org_id:
            queryset = queryset.filter(org_applicant_id=org_id)
        submitter_id = request.GET.get('submitter_id', None)
        if submitter_id:
            qs = qs.filter(submitter_id=submitter_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @list_route(methods=['GET',])
    @basic_exception_handler
    def existing_licences(self, request, *args, **kwargs):
        # TODO: still required?
        existing_licences = []
        l_list = Approval.objects.filter(
                submitter=request.user,
                status='current',
                )
        for l in l_list:
            lchild = l.child_obj
            # mooring text required?
            if type(lchild) == MooringLicence:
                if Mooring.objects.filter(mooring_licence=lchild):
                    mooring = Mooring.objects.filter(mooring_licence=lchild)[0]
                    existing_licences.append({
                        "approval_id": lchild.id,
                        "current_proposal_id": lchild.current_proposal.id,
                        "lodgement_number": lchild.lodgement_number,
                        #"mooring": mooring.name,
                        "mooring_id": mooring.id,
                        #"app_type_code": lchild.code,
                        #"code": 'ml_{}'.format(lchild.id),
                        "code": lchild.code,
                        "description": lchild.description,
                        #"new_application_text": "I want to add a vessel to Mooring Licence {} on mooring {}".format(lchild.lodgement_number, mooring.name)
                        "new_application_text": "I want to (amend/renew) my current mooring licence {}".format(lchild.lodgement_number)
                        })
            else:
                existing_licences.append({
                    "approval_id": lchild.id,
                    "lodgement_number": lchild.lodgement_number,
                    "current_proposal_id": lchild.current_proposal.id,
                    #"lodgement_number": ml.lodgement_number,
                    "code": lchild.code,
                    "description": lchild.description,
                    "new_application_text": "I want to (amend/renew) my current {} {}".format(lchild.description.lower(), lchild.lodgement_number)
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
        #return Response()

    # @list_route(methods=['GET',])
    # def filter_list(self, request, *args, **kwargs):
    #     """ Used by the external dashboard filters """
    #     region_qs =  self.get_queryset().filter(current_proposal__region__isnull=False).values_list('current_proposal__region__name', flat=True).distinct()
    #     activity_qs =  self.get_queryset().filter(current_proposal__activity__isnull=False).values_list('current_proposal__activity', flat=True).distinct()
    #     application_types=ApplicationType.objects.all().values_list('name', flat=True)
    #     data = dict(
    #         regions=region_qs,
    #         activities=activity_qs,
    #         approval_status_choices = [i[1] for i in Approval.STATUS_CHOICES],
    #         application_types=application_types,
    #     )
    #     return Response(data)

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
                #instance.current_proposal.save(version_comment='File Added: {}'.format(filename)) # to allow revision to be added to reversion history

            return  Response( [dict(input_name=d.input_name, name=d.name,file=d._file.url, id=d.id, can_delete=d.can_delete) for d in instance.qaofficer_documents.filter(input_name=section, visible=True) if d._file] )

    @detail_route(methods=['POST',])
    @renderer_classes((JSONRenderer,))
    def add_eclass_licence(self, request, *args, **kwargs):

        def raiser(exception): raise serializers.ValidationError(exception)

        try:
            with transaction.atomic():
                #keys = request.data.keys()
                #file_keys = [key for key in keys if 'file-upload' in i]
                org_applicant = None
                proxy_applicant = None

                _file = request.data.get('file-upload-0') if request.data.get('file-upload-0') else raiser('Licence File is required')
                try:
                    if request.data.get('applicant_type') == 'org':
                        org_applicant = Organisation.objects.get(organisation_id=request.data.get('holder-selected'))
                        #org_applicant = ledger_org.objects.get(id=request.data.get('holder-selected'))
                    else:
                        proxy_applicant = EmailUser.objects.get(id=request.data.get('holder-selected'))
                except:
                    raise serializers.ValidationError('Licence holder is required')

                start_date = datetime.strptime(request.data.get('start_date'), '%d/%m/%Y') if request.data.get('start_date') else raiser('Start Date is required')
                issue_date = datetime.strptime(request.data.get('issue_date'), '%d/%m/%Y') if request.data.get('issue_date') else raiser('Issue Date is required')
                expiry_date = datetime.strptime(request.data.get('expiry_date'), '%d/%m/%Y') if request.data.get('expiry_date') else raiser('Expiry Date is required')

                application_type, app_type_created = ApplicationType.objects.get_or_create(
                    name='E Class',
                    defaults={'visible':False, 'max_renewals':1, 'max_renewal_period':5}
                )

                proposal, proposal_created = Proposal.objects.get_or_create( # Dummy 'E Class' proposal
                    id=0,
                    defaults={'application_type':application_type, 'submitter':request.user, 'schema':[]}
                )

                approval = Approval.objects.create(
                    issue_date=issue_date,
                    expiry_date=expiry_date,
                    start_date=start_date,
                    org_applicant=org_applicant,
                    proxy_applicant=proxy_applicant,
                    current_proposal=proposal
                )

                doc = ApprovalDocument.objects.create(approval=approval, _file=_file)
                approval.licence_document=doc
                approval.save()

                return Response({'approval': approval.lodgement_number})

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
    def approval_extend(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = ApprovalExtendSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.approval_extend(request,serializer.validated_data)
            serializer = ApprovalSerializer(instance,context={'request':request})
            return Response(serializer.data)
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
    def approval_cancellation(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = ApprovalCancellationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.approval_cancellation(request,serializer.validated_data)
            serializer = ApprovalSerializer(instance,context={'request':request})
            return Response(serializer.data)
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
            serializer = ApprovalSerializer(instance,context={'request':request})
            return Response(serializer.data)
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
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
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
            serializer = ApprovalSerializer(instance,context={'request':request})
            return Response(serializer.data)
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
        uvi_requested = data.get('uvi_vessel_identifier', '')
        vessel_name_requested = data.get('vessel_name', '')
        try:
            dcv_vessel = DcvVessel.objects.get(uvi_vessel_identifier=uvi_requested)
        except DcvVessel.DoesNotExist:
            data['rego_no'] = rego_no_requested
            data['uvi_vessel_identifier'] = uvi_requested
            data['vessel_name'] = vessel_name_requested
            # data['dcv_organisation_id'] = org_id
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

        data['submitter'] = request.user.id
        # data['fee_sid'] = fee_season_requested.get('id')
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
    def _handle_dcv_organisation(request):
        data = request.data
        abn_requested = request.data.get('abn_acn', '')
        name_requested = request.data.get('organisation', '')
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
        uvi_requested = request.data.get('dcv_vessel').get('uvi_vessel_identifier', '')
        vessel_name_requested = request.data.get('dcv_vessel').get('vessel_name', '')
        try:
            dcv_vessel = DcvVessel.objects.get(uvi_vessel_identifier=uvi_requested)
        except DcvVessel.DoesNotExist:
            data['rego_no'] = rego_no_requested
            data['uvi_vessel_identifier'] = uvi_requested
            data['vessel_name'] = vessel_name_requested
            data['dcv_organisation_id'] = org_id
            serializer = DcvVesselSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            dcv_vessel = serializer.save()
        except Exception as e:
            logger.error(e)
            raise

        return dcv_vessel

    def create(self, request, *args, **kwargs):
        data = request.data

        dcv_organisation = self._handle_dcv_organisation(request)
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

        #filter_compliance_status = request.GET.get('filter_compliance_status')
        #if filter_compliance_status and not filter_compliance_status.lower() == 'all':
         #   queryset = queryset.filter(customer_status=filter_compliance_status)

        getter = request.query_params.get
        fields = self.get_fields(getter)
        ordering = self.get_ordering(getter, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)

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

    def get_queryset(self):
        request_user = self.request.user
        qs = DcvPermit.objects.none()

        if is_internal(self.request):
            qs = DcvPermit.objects.all()
        #elif is_customer(self.request):
         #   qs = e.objects.filter(Q(approval__submitter=request_user))

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

        return add_cache_control(Response(dcv_vessel_data))


class DcvAdmissionFilterBackend(DatatablesFilterBackend):
    def filter_queryset(self, request, queryset, view):
        total_count = queryset.count()

        #filter_compliance_status = request.GET.get('filter_compliance_status')
        #if filter_compliance_status and not filter_compliance_status.lower() == 'all':
         #   queryset = queryset.filter(customer_status=filter_compliance_status)

        getter = request.query_params.get
        fields = self.get_fields(getter)
        ordering = self.get_ordering(getter, fields)
        queryset = queryset.order_by(*ordering)
        if len(ordering):
            queryset = queryset.order_by(*ordering)

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
        return Response({'sticker': serializer.data})

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def request_replacement(self, request, *args, **kwargs):
        sticker = self.get_object()
        data = request.data

        # Update Sticker action
        data['sticker'] = sticker.id
        data['action'] = 'Request replacement'
        data['user'] = request.user.id
        serializer = StickerActionDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        details = serializer.save()

        # Sticker
        sticker.request_replacement()
        serializer = StickerSerializer(sticker)
        return Response({'sticker': serializer.data})


class StickerPaginatedViewSet(viewsets.ModelViewSet):
    filter_backends = (StickerFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    renderer_classes = (StickerRenderer,)
    queryset = Sticker.objects.none()
    serializer_class = StickerSerializer
    search_fields = ['id', ]
    page_size = 10

    def get_queryset(self):
        # debug = self.request.GET.get('debug', False)
        # debug = debug.lower() in ['true', 't', 'yes', 'y', True]
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
        #elif is_customer(self.request):
         #   qs = e.objects.filter(Q(approval__submitter=request_user))

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
    serializer_class = ApprovalSerializer

    @detail_route(methods=['POST',])
    @basic_exception_handler
    def create_mooring_licence_application(self, request, *args, **kwargs):
        with transaction.atomic():
            waiting_list_allocation = self.get_object()
            #print("create_mooring_licence_application")
            #print(request.data)
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
                send_create_mooring_licence_application_email_notification(request, waiting_list_allocation)
                # update waiting_list_allocation
                waiting_list_allocation.status = 'offered'
                ## BB 20210609 - we no longer reset wla_queue_date
                #waiting_list_allocation.wla_queue_date = None
                waiting_list_allocation.wla_order = None
                waiting_list_allocation.save()
                waiting_list_allocation.set_wla_order()
            return Response({"proposal_created": new_proposal.lodgement_number})


class MooringLicenceViewSet(viewsets.ModelViewSet):
    queryset = MooringLicence.objects.all().order_by('id')
    serializer_class = ApprovalSerializer

    @list_route(methods=['GET',])
    @basic_exception_handler
    def existing_mooring_licences(self, request, *args, **kwargs):
        # TODO: still required?
        existing_licences = []
        ml_list = MooringLicence.objects.filter(
                submitter=request.user,
                status='current',
                )
        for ml in ml_list:
            if Mooring.objects.filter(mooring_licence=ml):
                mooring = Mooring.objects.filter(mooring_licence=ml)[0]
                existing_licences.append({
                    "approval_id": ml.id,
                    "current_proposal_id": ml.current_proposal.id,
                    #"lodgement_number": ml.lodgement_number,
                    #"mooring": mooring.name,
                    "mooring_id": mooring.id,
                    "app_type_code": ml.code,
                    "code": 'ml_{}'.format(ml.id),
                    "description": ml.description,
                    "new_application_text": "to add a vessel to Mooring Licence {} on mooring {}".format(ml.lodgement_number, mooring.name)
                    })
        return Response(existing_licences)

