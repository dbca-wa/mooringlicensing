from django.db.models import Q, CharField, Value
from django.db.models.functions import Concat
from django.db import transaction
from django.conf import settings
from django_countries import countries
from rest_framework import viewsets, serializers, views
from rest_framework.decorators import action as detail_route
from rest_framework.response import Response
from django.core.cache import cache
from ledger_api_client.managed_models import SystemUser
from django.core.paginator import Paginator, EmptyPage
from django.core.exceptions import ObjectDoesNotExist
from mooringlicensing.components.proposals.models import Proposal
                              
from mooringlicensing.components.users.models import EmailUserLogEntry
from mooringlicensing.components.users.utils import get_user_name
from mooringlicensing.components.users.serializers import (
    UserForEndorserSerializer,
    UserSerializer,
    EmailUserCommsSerializer,
)
import logging

from mooringlicensing.helpers import is_customer, is_internal
from mooringlicensing.ledger_api_utils import retrieve_system_user
logger = logging.getLogger(__name__)

from rest_framework.permissions import IsAuthenticated
from mooringlicensing.components.proposals.permissions import (
    InternalProposalPermission,
)
from mooringlicensing.components.approvals.permissions import (
    InternalApprovalPermission,
)


class GetCountries(views.APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request):
        data = cache.get('country_list')
        if not data:
            country_list = []
            for country in list(countries):
                country_list.append({"name": country.name, "code": country.code})
            cache.set('country_list',country_list, settings.LOV_CACHE_TIMEOUT)
            data = cache.get('country_list')
        return Response(data)


class GetProposalApplicantUser(views.APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, proposal_pk, format=None):
        try: 
            proposal = Proposal.objects.get(id=proposal_pk)
            if proposal.proposal_applicant:
                applicant = retrieve_system_user(proposal.proposal_applicant.email_user_id)
                if (is_customer(self.request) and proposal.proposal_applicant.email_user_id == request.user.id) or is_internal(self.request):
                    # Holder of this proposal is accessing OR internal user is accessing.                   
                    serializer = UserSerializer(applicant)
                    return Response(serializer.data)
                elif is_customer(self.request) and proposal.site_licensee_mooring_request.filter(site_licensee_email__iexact=request.user.email).exists():
                    # ML holder is accessing the proposal as an endorser
                    serializer = UserForEndorserSerializer(applicant)
                    return Response(serializer.data)
                raise serializers.ValidationError("not authorised to view this user")
            raise serializers.ValidationError("proposal applicant does not exist")
        except ObjectDoesNotExist:
            raise serializers.ValidationError("proposal does not exist")


class GetProfile(views.APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request):
        if request.user.is_authenticated:
            try:
                system_user = SystemUser.objects.get(ledger_id=request.user)
                serializer = UserSerializer(system_user, context={'request':request})
                response = Response(serializer.data)
                return response
            except ObjectDoesNotExist:
                raise serializers.ValidationError("system user does not exists")
            except Exception as e:
                print(e)
                raise serializers.ValidationError("error")
        raise serializers.ValidationError("user not authenticated")


class GetPerson(views.APIView):
    permission_classes=[InternalProposalPermission|InternalApprovalPermission]
    def get(self, request):
        if is_internal(request): 
            search_term = request.GET.get('search_term', '')
            page_number = request.GET.get('page_number', 1)
            display_email = request.GET.get('display_email',False)
            items_per_page = 10

            if search_term:
                my_queryset = SystemUser.objects.annotate(
                    custom_term=Concat(
                        "first_name",
                        Value(" "),
                        "last_name",
                        Value(" "),
                        "email",
                        Value(" "),
                        "legal_first_name",
                        Value(" "),
                        "legal_last_name",
                        output_field=CharField(),
                        )
                    ).distinct("custom_term").order_by("custom_term").filter(custom_term__icontains=search_term)
                paginator = Paginator(my_queryset, items_per_page)

                try:
                    current_page = paginator.page(page_number)
                    my_objects = current_page.object_list
                except EmptyPage:
                    my_objects = []

                data_transform = []
                for user in my_objects:
                    user_name = get_user_name(user)
                    if(display_email):
                        text = user.email
                    else:
                        if user.legal_dob:
                            text = '{} {} (DOB: {})'.format(user_name["first_name"], user_name["last_name"], user.legal_dob.strftime('%d/%m/%Y'))
                        else:
                            text = '{} {}'.format(user_name["first_name"], user_name["last_name"])

                    serializer = UserSerializer(user)
                    user_data = serializer.data
                    user_data['text'] = text
                    data_transform.append(user_data)
                return Response({
                    "results": data_transform,
                    "pagination": {
                        "more": current_page.has_next()
                    }
                })
        else:
            raise serializers.ValidationError("unauthorised")

        return Response()


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SystemUser.objects.none()
    serializer_class = UserSerializer
    lookup_field = "ledger_id"
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        if is_internal(self.request):
            return SystemUser.objects.all()
        elif is_customer(self.request):
            user = self.request.user
            return SystemUser.objects.filter(Q(ledger_id=user.id))
        return SystemUser.objects.none()

    @detail_route(methods=['GET',], detail=True, permission_classes=[InternalProposalPermission|InternalApprovalPermission])
    def comms_log(self, request, *args, **kwargs):
        try:
            if is_internal(request):
                instance = self.get_object()
                qs = EmailUserLogEntry.objects.filter(email_user_id=instance.id)
                serializer = EmailUserCommsSerializer(qs, many=True)
                return Response(serializer.data)
            return Response()
        except Exception as e:
            print(e)
            raise serializers.ValidationError("error")

    @detail_route(methods=['POST',], detail=True, permission_classes=[InternalProposalPermission|InternalApprovalPermission])
    def add_comms_log(self, request, *args, **kwargs):
        if is_internal(request):
            try:                
                with transaction.atomic():
                    instance = self.get_object()
                    kwargs = {
                        'subject': request.data.get('subject', ''),
                        'text': request.data.get('text', ''),
                        'email_user_id': instance.id,
                        'customer': instance.id,
                        'staff': request.data.get('staff', request.user.id),
                        'to': request.data.get('to', ''),
                        'fromm': request.data.get('fromm', ''),
                        'cc': '',
                    }
                    eu_entry = EmailUserLogEntry.objects.create(**kwargs)

                    for f in request.FILES:
                        document = eu_entry.documents.create(
                        name = str(request.FILES[f]),
                        _file = request.FILES[f]
                        )
                    return Response({})                
            except Exception as e:
                print(e)
                raise serializers.ValidationError("error")
        else:
            raise serializers.ValidationError("user not authorised to add comms log")