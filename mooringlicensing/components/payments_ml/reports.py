import csv
import pytz
# from six.moves import StringIO
from django.utils import timezone
from django.db.models.query_utils import Q
# from ledger.payments.models import CashTransaction, BpointTransaction, BpayTransaction,Invoice
# from ledger.settings_base import TIME_ZONE
from ledger_api_client.settings_base import TIME_ZONE

from mooringlicensing.components.main.models import ApplicationType
from mooringlicensing.components.payments_ml.models import ApplicationFee, DcvAdmissionFee, DcvPermitFee
from mooringlicensing.components.compliances.models import Compliance
from mooringlicensing.settings import PAYMENT_SYSTEM_PREFIX


def booking_bpoint_settlement_report(_date):
    try:
        # Start writing the headers
        strIO = StringIO()
        fieldnames = [
            'Payment Date',
            'Settlement Date',
            'Confirmation Number',
            'Name',
            'Type',
            'Amount',
            'Invoice',
        ]
        writer = csv.writer(strIO)
        writer.writerow(fieldnames)

        bpoint = []
        bpoint.extend([x for x in BpointTransaction.objects.filter(
            Q(created__date=_date),
            Q(response_code=0),
            Q(crn1__startswith=PAYMENT_SYSTEM_PREFIX),
        ).exclude(crn1__endswith='_test')])

        for b in bpoint:
            dcv_permit_fee, dcv_admission_fee, app_type_dcv_permit, compliance = None, None, None, None
            try:
                invoice = Invoice.objects.get(reference=b.crn1)

                try:
                    dcv_permit_fee = DcvPermitFee.objects.get(invoice_reference=invoice.reference)
                except DcvPermitFee.DoesNotExist:
                    pass

                try:
                    dcv_admission_fee = DcvAdmissionFee.objects.get(invoice_reference=invoice.reference)
                except DcvAdmissionFee.DoesNotExist:
                    pass

                try:
                    application_fee = ApplicationFee.objects.get(invoice_reference=invoice.reference)
                except ApplicationFee.DoesNotExist:
                    pass

                try:
                    compliance = Compliance.objects.get(fee_invoice_reference=invoice.reference)
                except Compliance.DoesNotExist:
                    pass

                if dcv_permit_fee:
                    b_name = u'{}'.format(dcv_permit_fee.created_by)
                    created = timezone.localtime(dcv_permit_fee.created, pytz.timezone(TIME_ZONE))
                    settlement_date = b.settlement_date.strftime('%d/%m/%Y') if b.settlement_date else ''
                    writer.writerow([created.strftime('%d/%m/%Y %H:%M:%S'),
                                     settlement_date,
                                     dcv_permit_fee.dcv_permit.lodgement_number,
                                     b_name,
                                     invoice.get_payment_method_display(),
                                     invoice.amount,
                                     invoice.reference])
                elif dcv_admission_fee:
                    b_name = u'{}'.format(dcv_admission_fee.created_by)
                    created = timezone.localtime(dcv_admission_fee.created, pytz.timezone(TIME_ZONE))
                    settlement_date = b.settlement_date.strftime('%d/%m/%Y') if b.settlement_date else ''
                    writer.writerow([created.strftime('%d/%m/%Y %H:%M:%S'),
                                     settlement_date,
                                     dcv_admission_fee.dcv_admission.lodgement_number,
                                     b_name,
                                     invoice.get_payment_method_display(),
                                     invoice.amount,
                                     invoice.reference])
                elif application_fee:
                    b_name = u'{}'.format(application_fee.proposal.applicant)
                    created = timezone.localtime(application_fee.created, pytz.timezone('Australia/Perth'))
                    settlement_date = b.settlement_date.strftime('%d/%m/%Y') if b.settlement_date else ''
                    writer.writerow([created.strftime('%d/%m/%Y %H:%M:%S'),
                                     settlement_date,
                                     application_fee.proposal.lodgement_number,
                                     b_name,
                                     invoice.get_payment_method_display(),
                                     invoice.amount,
                                     invoice.reference])
                elif compliance:
                    submitter = compliance.approval.submitter if compliance.approval else compliance.proposal.submitter
                    b_name = u'{}'.format(submitter)
                    created = timezone.localtime(b.created, pytz.timezone('Australia/Perth'))
                    settlement_date = b.settlement_date.strftime('%d/%m/%Y') if b.settlement_date else ''
                    writer.writerow([created.strftime('%d/%m/%Y %H:%M:%S'),
                                     settlement_date,
                                     compliance.lodgement_number,
                                     b_name,
                                     invoice.get_payment_method_display(),
                                     invoice.amount,
                                     invoice.reference])
                else:
                    writer.writerow([b.created.strftime('%d/%m/%Y %H:%M:%S'),
                                     b.settlement_date.strftime('%d/%m/%Y'),
                                     '',
                                     '',
                                     str(b.action),
                                     b.amount,
                                     invoice.reference])
            except Invoice.DoesNotExist:
                pass

        strIO.flush()
        strIO.seek(0)
        return strIO
    except:
        raise

