import traceback
import base64
import geojson
from six.moves.urllib.parse import urlparse
from wsgiref.util import FileWrapper
from django.db.models import Q, Min
from django.db import transaction
from django.http import HttpResponse
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework import viewsets, serializers, status, generics, views
from rest_framework.decorators import detail_route, list_route,renderer_classes
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser, BasePermission
from rest_framework.pagination import PageNumberPagination
from datetime import datetime, timedelta
from collections import OrderedDict
from django.core.cache import cache
from ledger.accounts.models import EmailUser,Address, Profile, EmailIdentity, EmailUserAction
from ledger.address.models import Country
from datetime import datetime,timedelta, date
from mooringlicensing.components.main.decorators import (
        basic_exception_handler, 
        timeit, 
        query_debugger
        )
from mooringlicensing.components.organisations.models import  (
                                    Organisation,
                                )

from mooringlicensing.components.users.serializers import   (
                                                UserSerializer,
                                                UserFilterSerializer,
                                                UserAddressSerializer,
                                                PersonalSerializer,
                                                ContactSerializer,
                                                EmailUserActionSerializer,
                                                EmailUserCommsSerializer,
                                                EmailUserLogEntrySerializer,
                                                UserSystemSettingsSerializer,
                                            )
from mooringlicensing.components.organisations.serializers import (
    OrganisationRequestDTSerializer,
)
from mooringlicensing.components.main.utils import retrieve_department_users, add_cache_control
from mooringlicensing.components.main.models import UserSystemSettings
from mooringlicensing.components.main.process_document import (
        process_generic_document, 
        )

import logging
logger = logging.getLogger('mooringlicensing')


class DepartmentUserList(views.APIView):
    renderer_classes = [JSONRenderer,]
    def get(self, request, format=None):
        data = cache.get('department_users')
        if not data:
            retrieve_department_users()
            data = cache.get('department_users')
        return add_cache_control(Response(data))

        serializer  = UserSerializer(request.user)

class GetProfile(views.APIView):
    renderer_classes = [JSONRenderer,]
    def get(self, request, format=None):
        #logger.info('request user: {}'.format(request.user))
        serializer  = UserSerializer(request.user, context={'request':request})
        #logger.info('user serializer data: {}'.format(serializer.data))
        response = Response(serializer.data)
        return add_cache_control(response)

class GetSubmitterProfile(views.APIView):
    renderer_classes = [JSONRenderer,]
    def get(self, request, format=None):
        #import ipdb; ipdb.set_trace()
        submitter_id = request.GET.get('submitter_id')
        submitter = EmailUser.objects.get(id=submitter_id)
        serializer  = UserSerializer(submitter, context={'request':request})
        response = Response(serializer.data)
        return add_cache_control(response)

from rest_framework import filters
class UserListFilterView(generics.ListAPIView):
    """ https://cop-internal.dbca.wa.gov.au/api/filtered_users?search=russell
    """
    queryset = EmailUser.objects.all()
    serializer_class = UserFilterSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('email', 'first_name', 'last_name')

class UserViewSet(viewsets.ModelViewSet):
    queryset = EmailUser.objects.all()
    serializer_class = UserSerializer

    @detail_route(methods=['POST',])
    def update_personal(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = PersonalSerializer(instance,data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            serializer = UserSerializer(instance)
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
    def update_contact(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = ContactSerializer(instance,data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            serializer = UserSerializer(instance)
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
    def update_address(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            # residential address
            residential_serializer = UserAddressSerializer(data=request.data.get('residential_address'))
            residential_serializer.is_valid(raise_exception=True)
            residential_address, created = Address.objects.get_or_create(
                line1 = residential_serializer.validated_data['line1'],
                locality = residential_serializer.validated_data['locality'],
                state = residential_serializer.validated_data['state'],
                country = residential_serializer.validated_data['country'],
                postcode = residential_serializer.validated_data['postcode'],
                user = instance
            )
            instance.residential_address = residential_address
            #import ipdb; ipdb.set_trace()
            # postal address
            postal_address_data = request.data.get('postal_address')
            if request.data.get('postal_same_as_residential'):
                instance.postal_same_as_residential = True
                instance.postal_address = residential_address
            elif postal_address_data:
                postal_serializer = UserAddressSerializer(data=postal_address_data)
                postal_serializer.is_valid(raise_exception=True)
                postal_address, created = Address.objects.get_or_create(
                    line1 = postal_serializer.validated_data['line1'],
                    locality = postal_serializer.validated_data['locality'],
                    state = postal_serializer.validated_data['state'],
                    country = postal_serializer.validated_data['country'],
                    postcode = postal_serializer.validated_data['postcode'],
                    user = instance
                )
                instance.postal_address = postal_address

            instance.save()
            serializer = UserSerializer(instance)
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
    def update_system_settings(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            # serializer = UserSystemSettingsSerializer(data=request.data)
            # serializer.is_valid(raise_exception=True)
            user_setting, created = UserSystemSettings.objects.get_or_create(
                user = instance
            )
            serializer = UserSystemSettingsSerializer(user_setting, data=request.data)
            serializer.is_valid(raise_exception=True)
            #instance.residential_address = address
            serializer.save()
            instance = self.get_object()
            serializer = UserSerializer(instance)
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
    def upload_id(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.upload_identification(request)
            with transaction.atomic():
                instance.save()
                instance.log_user_action(EmailUserAction.ACTION_ID_UPDATE.format(
                '{} {} ({})'.format(instance.first_name, instance.last_name, instance.email)), request)
            serializer = UserSerializer(instance, partial=True)
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

    @detail_route(methods=['GET', ])
    def pending_org_requests(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrganisationRequestDTSerializer(
                instance.organisationrequest_set.filter(
                    status='with_assessor'),
                many=True,
                context={'request': request})
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

    @detail_route(methods=['GET', ])
    def action_log(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            qs = instance.action_logs.all()
            serializer = EmailUserActionSerializer(qs, many=True)
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
            serializer = EmailUserCommsSerializer(qs,many=True)
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
                request.data['emailuser'] = u'{}'.format(instance.id)
                request.data['staff'] = u'{}'.format(request.user.id)
                request.data._mutable=mutable
                serializer = EmailUserLogEntrySerializer(data=request.data)
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

