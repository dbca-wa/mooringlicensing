import traceback
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from ledger.payments.utils import oracle_parser
from django.conf import settings
from django.db import transaction
from wsgiref.util import FileWrapper
from rest_framework import viewsets, serializers, status, generics, views
from rest_framework.decorators import detail_route, list_route, renderer_classes, parser_classes
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser, BasePermission
from rest_framework.pagination import PageNumberPagination
from django.urls import reverse
from mooringlicensing.components.main.models import (#Region, District, Tenure, 
        #ApplicationType, #ActivityMatrix, AccessType, Park, Trail, ActivityCategory, Activity, 
        #RequiredDocument, 
        Question, 
        GlobalSettings
        )
from mooringlicensing.components.main.serializers import (  # RegionSerializer, DistrictSerializer, TenureSerializer,
    # ApplicationTypeSerializer, #ActivityMatrixSerializer,  AccessTypeSerializer, ParkSerializer, ParkFilterSerializer, TrailSerializer, ActivitySerializer, ActivityCategorySerializer,
    # RequiredDocumentSerializer,
    QuestionSerializer,
    GlobalSettingsSerializer,
    OracleSerializer,
    BookingSettlementReportSerializer,  # BookingSettlementReportSerializer, LandActivityTabSerializer, MarineActivityTabSerializer, EventsParkSerializer, TrailTabSerializer, FilmingParkSerializer
)
from mooringlicensing.components.main.utils import add_cache_control
from django.core.exceptions import ValidationError
from django.db.models import Q

from mooringlicensing.components.payments_ml import reports
from mooringlicensing.components.proposals.models import Proposal
from mooringlicensing.components.proposals.serializers import ProposalSerializer
#from mooringlicensing.components.bookings.utils import oracle_integration
#from mooringlicensing.components.bookings import reports
from ledger.checkout.utils import create_basket_session, create_checkout_session, place_order_submission, get_cookie_basket
from collections import namedtuple
import json
from decimal import Decimal

import logging

from mooringlicensing.settings import PAYMENT_SYSTEM_PREFIX, SYSTEM_NAME

logger = logging.getLogger('payment_checkout')


#class ApplicationTypeViewSet(viewsets.ReadOnlyModelViewSet):
#    #queryset = ApplicationType.objects.all().order_by('order')
#    queryset = ApplicationType.objects.none()
#    serializer_class = ApplicationTypeSerializer
#
#    def get_queryset(self):
#        return ApplicationType.objects.order_by('order').filter(visible=True)


class GlobalSettingsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GlobalSettings.objects.all().order_by('id')
    serializer_class = GlobalSettingsSerializer


#class RequiredDocumentViewSet(viewsets.ReadOnlyModelViewSet):
#    queryset = RequiredDocument.objects.all()
#    serializer_class = RequiredDocumentSerializer


class QuestionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    #queryset = Proposal.objects.all()
    queryset = Proposal.objects.none()
    #serializer_class = ProposalSerializer
    serializer_class = ProposalSerializer
    lookup_field = 'id'

    def create(self, request, *args, **kwargs):
        response = super(PaymentViewSet, self).create(request, *args, **kwargs)
        # here may be placed additional operations for
        # extracting id of the object and using reverse()
        fallback_url = request.build_absolute_uri('/')
        return add_cache_control(HttpResponseRedirect(redirect_to=fallback_url + '/success/'))


class BookingSettlementReportView(views.APIView):
   renderer_classes = (JSONRenderer,)

   def get(self,request,format=None):
       try:
           http_status = status.HTTP_200_OK
           #parse and validate data
           report = None
           data = {
               "date":request.GET.get('date'),
           }
           serializer = BookingSettlementReportSerializer(data=data)
           serializer.is_valid(raise_exception=True)
           filename = 'Booking Settlement Report-{}'.format(str(serializer.validated_data['date']))
           # Generate Report
           report = reports.booking_bpoint_settlement_report(serializer.validated_data['date'])
           if report:
               response = HttpResponse(FileWrapper(report), content_type='text/csv')
               response['Content-Disposition'] = 'attachment; filename="{}.csv"'.format(filename)
               return response
           else:
               raise serializers.ValidationError('No report was generated.')
       except serializers.ValidationError:
           raise
       except Exception as e:
           traceback.print_exc()

def oracle_integration(date, override):
    system = PAYMENT_SYSTEM_PREFIX
    #oracle_codes = oracle_parser(date, system, 'Commercial Operator Licensing', override=override)
    # oracle_codes = oracle_parser(date, system, 'WildlifeCompliance', override=override)
    oracle_codes = oracle_parser(date, system, SYSTEM_NAME, override=override)


class OracleJob(views.APIView):
    renderer_classes = [JSONRenderer,]
    def get(self, request, format=None):
        try:
            data = {
                "date":request.GET.get("date"),
                "override": request.GET.get("override")
            }
            serializer = OracleSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            oracle_integration(serializer.validated_data['date'].strftime('%Y-%m-%d'),serializer.validated_data['override'])
            data = {'successful':True}
            return add_cache_control(Response(data))
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            raise serializers.ValidationError(repr(e.error_dict)) if hasattr(e, 'error_dict') else serializers.ValidationError(e)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e[0]))

