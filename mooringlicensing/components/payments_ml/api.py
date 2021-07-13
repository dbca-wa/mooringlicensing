import logging

from rest_framework import views
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from mooringlicensing import settings
from mooringlicensing.components.main.models import ApplicationType
from mooringlicensing.components.main.utils import add_cache_control
from mooringlicensing.components.payments_ml.models import FeeConstructor
from mooringlicensing.components.payments_ml.serializers import FeeConstructorSerializer

logger = logging.getLogger('log')


class GetSeasonsForDcvPermitDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        # Return current and future seasons for the DCV permit
        application_type = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_DCV_PERMIT['code'])
        fee_constructors = FeeConstructor.get_current_and_future_fee_constructors_by_application_type_and_date(application_type,)
        data = [{'id': item.fee_season.id, 'name': item.fee_season.__str__()} for item in fee_constructors]
        return add_cache_control(Response(data))


class GetFeeConfigurations(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        # Return current and future seasons for the DCV permit
        application_type = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_DCV_ADMISSION['code'])
        fee_constructors = FeeConstructor.get_current_and_future_fee_constructors_by_application_type_and_date(application_type,)
        serializer = FeeConstructorSerializer(fee_constructors, many=True)

        return add_cache_control(Response(serializer.data))
        # search_term = request.GET.get('term', '')
        # if search_term:
        #     data = DcvVessel.objects.filter(rego_no__icontains=search_term).values('id', 'rego_no')[:10]
        #     data_transform = [{'id': rego['id'], 'text': rego['rego_no']} for rego in data]
        #     return Response({"results": data_transform})
        # return add_cache_control(Response())
