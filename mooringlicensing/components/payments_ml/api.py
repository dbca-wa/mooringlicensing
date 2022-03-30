import logging
import traceback
import json
from decimal import *

from rest_framework import views
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from mooringlicensing import settings
from mooringlicensing.components.main.models import ApplicationType
from mooringlicensing.components.payments_ml.models import FeeConstructor
from mooringlicensing.components.payments_ml.serializers import FeeConstructorSerializer
from ledger.payments.models import Invoice, OracleAccountCode
from ledger.payments.bpoint.models import BpointTransaction, BpointToken
from ledger.checkout.utils import create_basket_session, create_checkout_session, place_order_submission, get_cookie_basket, calculate_excl_gst
from ledger.payments.utils import oracle_parser_on_invoice, update_payments
from mooringlicensing.components.proposals.models import Proposal
from mooringlicensing import mooring_booking_utils as utils

logger = logging.getLogger('mooringlicensing')


class GetSeasonsForDcvPermitDict(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        # Return current and future seasons for the DCV permit
        application_type = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_DCV_PERMIT['code'])
        fee_constructors = FeeConstructor.get_current_and_future_fee_constructors_by_application_type_and_date(application_type,)
        data = [{'id': item.fee_season.id, 'name': item.fee_season.__str__()} for item in fee_constructors]
        return Response(data)


class GetFeeConfigurations(views.APIView):
    renderer_classes = [JSONRenderer, ]

    def get(self, request, format=None):
        # Return current and future seasons for the DCV permit
        application_type = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_DCV_ADMISSION['code'])
        fee_constructors = FeeConstructor.get_current_and_future_fee_constructors_by_application_type_and_date(application_type,)
        serializer = FeeConstructorSerializer(fee_constructors, many=True)

        return Response(serializer.data)


class CheckOracleCodeView(views.APIView):
    renderer_classes = [JSONRenderer,]
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, format='json'):
        try:
           oracle_code = request.GET.get('oracle_code','')
           if OracleAccountCode.objects.filter(active_receivables_activities=oracle_code).count() > 0:
                 json_obj = {'found': True, 'code': oracle_code}
           else:
                 json_obj = {'found': False, 'code': oracle_code}
           return Response(json_obj)
        except Exception as e:
            print(traceback.print_exc())
            raise


class RefundOracleView(views.APIView):
    renderer_classes = [JSONRenderer,]
    permission_classes = [IsAuthenticatedOrReadOnly]

    def post(self, request, *args, **kwargs):

    #def get(self, request, format='json'):
        
        try:
           if request.user.is_superuser or request.user.groups.filter(name__in=['Mooring Licensing - Payment Officers']).exists():
 
                money_from = request.POST.get('money_from',[])
                money_to = request.POST.get('money_to',[])
                bpoint_trans_split= request.POST.get('bpoint_trans_split',[])
                refund_method = request.POST.get('refund_method', None)
                booking_id = request.POST.get('booking_id',None)
                newest_booking_id = request.POST.get('newest_booking_id',None)
                booking = Proposal.objects.get(pk=newest_booking_id)
                money_from_json = json.loads(money_from)
                money_to_json = json.loads(money_to)
                bpoint_trans_split_json = json.loads(bpoint_trans_split)
                failed_refund = False
     
                json_obj = {'found': False, 'code': money_from, 'money_to': money_to, 'failed_refund': failed_refund}
    
                lines = []
                if int(refund_method) == 1:
                    lines = []
                    for mf in money_from_json:
                        if Decimal(mf['line-amount']) > 0: 
                            money_from_total = (Decimal(mf['line-amount']) - Decimal(mf['line-amount']) - Decimal(mf['line-amount']))
                            lines.append({
                                'ledger_description':str(mf['line-text']),
                                "quantity":1,
                                "price_incl_tax":money_from_total,
                                "price_excl_tax":calculate_excl_gst(money_from_total),
                                "oracle_code":str(mf['oracle-code']), 
                                "line_status": 3
                                })

                    for bp_txn in bpoint_trans_split_json:
                        bpoint_id = BpointTransaction.objects.get(txn_number=bp_txn['txn_number'])
                        info = {'amount': Decimal('{:.2f}'.format(float(bp_txn['line-amount']))), 'details' : 'Refund via system'}
                        if info['amount'] > 0:
                             lines.append({
                                 'ledger_description':str("Temp fund transfer "+bp_txn['txn_number']),
                                 "quantity":1,
                                 "price_incl_tax":Decimal('{:.2f}'.format(float(bp_txn['line-amount']))),
                                 "price_excl_tax":calculate_excl_gst(Decimal('{:.2f}'.format(float(bp_txn['line-amount'])))),
                                 "oracle_code":str(settings.UNALLOCATED_ORACLE_CODE), 
                                 'line_status': 1
                                 })


                    order = utils.allocate_refund_to_invoice(request, booking, lines, invoice_text=None, internal=False, order_total='0.00',user=booking.submitter)
                    new_invoice = Invoice.objects.get(order_number=order.number)
                    update_payments(new_invoice.reference) 
                    #order = utils.allocate_refund_to_invoice(request, booking, lines, invoice_text=None, internal=False, order_total='0.00',user=booking.customer)
                    #new_order = Order.objects.get(basket=basket)
                    #new_invoice = Invoice.objects.get(order_number=order.number)
                    
                    for bp_txn in bpoint_trans_split_json:
                        bpoint_id = None
                        try:
                             bpoint_id = BpointTransaction.objects.get(txn_number=bp_txn['txn_number'])
                             info = {'amount': Decimal('{:.2f}'.format(float(bp_txn['line-amount']))), 'details' : 'Refund via system'}
                        except Exception as e:
                             print (e)
                             info = {'amount': Decimal('{:.2f}'.format('0.00')), 'details' : 'Refund via system'}

                        refund = None
                        lines = []
                        if info['amount'] > 0:
                            lines = []
                            #lines.append({'ledger_description':str("Temp fund transfer "+bp_txn['txn_number']),"quantity":1,"price_incl_tax":Decimal('{:.2f}'.format(float(bp_txn['line-amount']))),"oracle_code":str(settings.UNALLOCATED_ORACLE_CODE), 'line_status': 1}) 


                            try:

                                bpoint_money_to = (Decimal('{:.2f}'.format(float(bp_txn['line-amount']))) - Decimal('{:.2f}'.format(float(bp_txn['line-amount']))) - Decimal('{:.2f}'.format(float(bp_txn['line-amount']))))
                                lines.append({
                                    'ledger_description':str("Payment Gateway Refund to "+bp_txn['txn_number']),
                                    "quantity":1,
                                    "price_incl_tax": bpoint_money_to,
                                    "price_excl_tax": calculate_excl_gst(bpoint_money_to),
                                    "oracle_code":str(settings.UNALLOCATED_ORACLE_CODE), 
                                    'line_status': 3
                                    })
                                bpoint = BpointTransaction.objects.get(txn_number=bp_txn['txn_number'])
                                refund = bpoint.refund(info,request.user)
                            except Exception as e:
                                failed_refund = True
                                bpoint_failed_amount = Decimal(bp_txn['line-amount'])
                                lines = []
                                lines.append({
                                    'ledger_description':str("Refund failed for txn "+bp_txn['txn_number']),
                                    "quantity":1,
                                    "price_incl_tax":'0.00',
                                    "price_excl_tax":'0.00',
                                    "oracle_code":str(settings.UNALLOCATED_ORACLE_CODE), 
                                    'line_status': 1
                                    })
                            order = utils.allocate_refund_to_invoice(request, booking, lines, invoice_text=None, internal=False, order_total='0.00',user=booking.submitter)
                            new_invoice = Invoice.objects.get(order_number=order.number)

                            if refund:
                               bpoint_refund = BpointTransaction.objects.get(txn_number=refund.txn_number)
                               bpoint_refund.crn1 = new_invoice.reference
                               bpoint_refund.save()
                               new_invoice.settlement_date = None
                               new_invoice.save()
                               update_payments(new_invoice.reference)
         
     
                else:
                    lines = []
                    for mf in money_from_json:
                        if Decimal(mf['line-amount']) > 0:
                            money_from_total = (Decimal(mf['line-amount']) - Decimal(mf['line-amount']) - Decimal(mf['line-amount']))
                            lines.append({
                                'ledger_description':str(mf['line-text']),
                                "quantity":1,
                                "price_incl_tax":money_from_total,
                                "price_excl_tax":calculate_excl_gst(money_from_total),
                                "oracle_code":str(mf['oracle-code']), 
                                'line_status': 3
                                })
    

                    for mt in money_to_json:
                        lines.append({
                            'ledger_description':mt['line-text'],
                            "quantity":1,
                            "price_incl_tax":mt['line-amount'],
                            "price_excl_tax":calculate_excl_gst(mt['line-amount']),
                            "oracle_code":mt['oracle-code'], 
                            'line_status': 1
                            })
                    order = utils.allocate_refund_to_invoice(request, booking, lines, invoice_text=None, internal=False, order_total='0.00',user=booking.submitter)
                    new_invoice = Invoice.objects.get(order_number=order.number)
                    update_payments(new_invoice.reference)

                json_obj['failed_refund'] = failed_refund
            
                return Response(json_obj)
           else:
                raise serializers.ValidationError('Permission Denied.') 
               
        except Exception as e:
           print(traceback.print_exc())
           raise

