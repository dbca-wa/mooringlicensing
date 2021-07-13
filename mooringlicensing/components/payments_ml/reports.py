import csv
import pytz
from six.moves import StringIO
from django.utils import timezone
from django.db.models.query_utils import Q
from ledger.payments.models import CashTransaction, BpointTransaction, BpayTransaction,Invoice
from ledger.settings_base import TIME_ZONE

from mooringlicensing import settings
from mooringlicensing.components.main.models import ApplicationType
from mooringlicensing.components.payments_ml.models import ApplicationFee, DcvAdmissionFee, DcvPermitFee
from mooringlicensing.components.compliances.models import Compliance
from mooringlicensing.components.proposals.models import Proposal


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

        # Retrieve all the oracle codes used in this app
        oracle_codes = []
        app_type_dcv_admission = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_DCV_ADMISSION['code'])
        app_type_dcv_permit = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_DCV_PERMIT['code'])
        oracle_codes.append(app_type_dcv_admission.oracle_code)
        oracle_codes.append(app_type_dcv_permit.oracle_code)
        for item in Proposal.__subclasses__():
            if hasattr(item, 'code'):
                app_type = ApplicationType.objects.get(code=item.code)
                oracle_codes.append(app_type.oracle_code)
        oracle_codes = list(set(oracle_codes))  # Remove duplication

        # crn1 starts with one of the oracle codes retrieved
        queries = Q()
        for oracle_code in oracle_codes:
            queries |= Q(crn1__startswith=oracle_code)

        bpoint = []
        bpoint.extend([x for x in BpointTransaction.objects.filter(
            Q(created__date=_date),
            Q(response_code=0),
            queries  # crn1__startswith='0517'
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

#        bpay = []
#        bpay.extend([x for x in BpayTransaction.objects.filter(
#            p_date__date=_date,
#            crn__startswith='0517'
#        ).exclude(crn__endswith='_test')])
#
#        for b in bpay:
#            booking, invoice = None, None
#            try:
#                invoice = Invoice.objects.get(reference=b.crn)
#                try:
#                    booking = AnnualRentalFee.objects.get(invoice_reference=invoice.reference).booking
#                except AnnualRentalFee.DoesNotExist:
#                    pass
#
#                if booking:
#                    b_name = u'{}'.format(booking.proposal.applicant)
#                    created = timezone.localtime(b.created, pytz.timezone('Australia/Perth'))
#                    settlement_date = b.p_date.strftime('%d/%m/%Y')
#                    writer.writerow([created.strftime('%d/%m/%Y %H:%M:%S'),settlement_date,booking.admission_number,b_name,invoice.get_payment_method_display(),invoice.amount,invoice.reference])
#                else:
#                    writer.writerow([b.created.strftime('%d/%m/%Y %H:%M:%S'),b.settlement_date.strftime('%d/%m/%Y'),'','',str(b.action),b.amount,invoice.reference])
#            except Invoice.DoesNotExist:
#                pass
#
#        cash = CashTransaction.objects.filter(
#            created__date=_date,
#            invoice__reference__startswith='0517'
#        ).exclude(type__in=['move_out', 'move_in'])
#
#        for b in cash:
#            booking, invoice = None, None
#            try:
#                invoice = b.invoice
#                try:
#                    booking = AnnualRentalFee.objects.get(invoice_reference=invoice.reference).booking
#                except AnnualRentalFee.DoesNotExist:
#                    pass
#
#                if booking:
#                    b_name = u'{} {}'.format(booking.details.get('first_name',''),booking.details.get('last_name',''))
#                    created = timezone.localtime(b.created, pytz.timezone('Australia/Perth'))
#                    writer.writerow([created.strftime('%d/%m/%Y %H:%M:%S'),b.created.strftime('%d/%m/%Y'),booking.confirmation_number,b_name,str(b.type),b.amount,invoice.reference])
#                else:
#                    writer.writerow([b.created.strftime('%d/%m/%Y %H:%M:%S'),b.created.strftime('%d/%m/%Y'),'','',str(b.type),b.amount,invoice.reference])
#            except Invoice.DoesNotExist:
#                pass

        strIO.flush()
        strIO.seek(0)
        return strIO
    except:
        raise


#def bookings_report(_date):
#    try:
#        bpoint, cash = [], []
#        bookings = Booking.objects.filter(created__date=_date).exclude(booking_type=3)
#        admission_bookings = AdmissionsBooking.objects.filter(created__date=_date).exclude(booking_type=3)
#
#        history_bookings = BookingHistory.objects.filter(created__date=_date).exclude(booking__booking_type=3)
#
#        strIO = StringIO()
#        fieldnames = ['Date','Confirmation Number','Name','Invoice Total','Override Price','Override Reason','Override Details','Invoice','Booking Type','Created By']
#        writer = csv.writer(strIO)
#        writer.writerow(fieldnames)
#
#        types = dict(Booking.BOOKING_TYPE_CHOICES)
#        types_admissions = dict(AdmissionsBooking.BOOKING_TYPE_CHOICES)
#        for b in bookings:
#            b_name = 'No Name'
#            if b.details:
#                b_name = u'{} {}'.format(b.details.get('first_name',''),b.details.get('last_name',''))
#            created = timezone.localtime(b.created, pytz.timezone('Australia/Perth'))
#            created_by =''
#            if b.created_by is not None:
#                 created_by = b.created_by
#
#            writer.writerow([created.strftime('%d/%m/%Y %H:%M:%S'),b.confirmation_number,b_name.encode('utf-8'),b.active_invoice.amount if b.active_invoice else '',b.override_price,b.override_reason,b.override_reason_info,b.active_invoice.reference if b.active_invoice else '', types[b.booking_type] if b.booking_type in types else b.booking_type, created_by])
#
#        for b in admission_bookings:
#            b_name = 'No Name'
#            if b.customer:
#                b_name = u'{}'.format(b.customer)
#            created = timezone.localtime(b.created, pytz.timezone('Australia/Perth'))
#            created_by =''
#            if b.created_by is not None:
#                 created_by = b.created_by
#
#            writer.writerow([created.strftime('%d/%m/%Y %H:%M:%S'),b.confirmation_number,b_name.encode('utf-8'),b.active_invoice.amount if b.active_invoice else '','','','',b.active_invoice.reference if b.active_invoice else '', types_admissions[b.booking_type] if b.booking_type in types_admissions else b.booking_type, created_by])
#
#
#        #for b in history_bookings:
#        #    b_name = '{} {}'.format(b.details.get('first_name',''),b.details.get('last_name',''))
#        #    writer.writerow([b.created.strftime('%d/%m/%Y %H:%M:%S'),b.booking.confirmation_number,b_name,b.invoice.amount,b.invoice.reference,'Yes'])
#
#        strIO.flush()
#        strIO.seek(0)
#        return strIO
#    except:
#        raise
#
