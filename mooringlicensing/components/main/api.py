import traceback
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
# from ledger.payments.utils import oracle_parser_on_invoice
from django.db import transaction
from wsgiref.util import FileWrapper
from rest_framework import viewsets, serializers, status, generics, views
# from rest_framework.decorators import detail_route, list_route, renderer_classes, parser_classes
from rest_framework.decorators import action as detail_route
from rest_framework.decorators import renderer_classes
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from mooringlicensing.components.main.models import (
        GlobalSettings,
        TemporaryDocumentCollection,
        )
from mooringlicensing.components.main.serializers import (
    GlobalSettingsSerializer,
    OracleSerializer,
    TemporaryDocumentCollectionSerializer,
    BookingSettlementReportSerializer,
)
from mooringlicensing.components.main.process_document import save_document, cancel_document, delete_document
from django.core.exceptions import ValidationError
# from django.db.models import Q

from mooringlicensing.components.payments_ml import reports
from mooringlicensing.components.proposals.models import Proposal
from mooringlicensing.components.proposals.serializers import ProposalSerializer
# from ledger.checkout.utils import create_basket_session, create_checkout_session, place_order_submission, get_cookie_basket
# from collections import namedtuple
# import json
# from decimal import Decimal

import logging

from mooringlicensing.settings import PAYMENT_SYSTEM_PREFIX, SYSTEM_NAME

logger = logging.getLogger('mooringlicensing')


class GlobalSettingsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GlobalSettings.objects.all().order_by('id')
    serializer_class = GlobalSettingsSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Proposal.objects.none()
    serializer_class = ProposalSerializer
    lookup_field = 'id'

    def create(self, request, *args, **kwargs):
        response = super(PaymentViewSet, self).create(request, *args, **kwargs)
        # here may be placed additional operations for
        # extracting id of the object and using reverse()
        fallback_url = request.build_absolute_uri('/')
        return HttpResponseRedirect(redirect_to=fallback_url + '/success/')


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

    # TODO: implement oracle_parser_on_invoice
    # oracle_codes = oracle_parser_on_invoice(date, system, SYSTEM_NAME, override=override)


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
            return Response(data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            raise serializers.ValidationError(repr(e.error_dict)) if hasattr(e, 'error_dict') else serializers.ValidationError(e)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e[0]))

class TemporaryDocumentCollectionViewSet(viewsets.ModelViewSet):
    queryset = TemporaryDocumentCollection.objects.all()
    serializer_class = TemporaryDocumentCollectionSerializer

    def create(self, request, *args, **kwargs):
        print("create temp doc coll")
        print(request.data)
        try:
            with transaction.atomic():
                serializer = TemporaryDocumentCollectionSerializer(
                        data=request.data, 
                        )
                serializer.is_valid(raise_exception=True)
                if serializer.is_valid():
                    instance = serializer.save()
                    save_document(request, instance, comms_instance=None, document_type=None)

                    return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            if hasattr(e, 'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            else:
                raise serializers.ValidationError(repr(e[0]))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST'], detail=True)
    @renderer_classes((JSONRenderer,))
    def process_temp_document(self, request, *args, **kwargs):
        print("process_temp_document")
        print(request.data)
        try:
            instance = self.get_object()
            action = request.data.get('action')

            if action == 'list':
                pass

            elif action == 'delete':
                delete_document(request, instance, comms_instance=None, document_type='temp_document')

            elif action == 'cancel':
                cancel_document(request, instance, comms_instance=None, document_type='temp_document')

            elif action == 'save':
                save_document(request, instance, comms_instance=None, document_type='temp_document')

            returned_file_data = [dict(
                        file=d._file.url,
                        id=d.id,
                        name=d.name,
                        ) for d in instance.documents.all() if d._file]
            return Response({'filedata': returned_file_data})

        except Exception as e:
            print(traceback.print_exc())
            raise e

