import datetime
import logging
from ledger.checkout.utils import calculate_excl_gst
import pytz
import json
from ledger.settings_base import TIME_ZONE
from decimal import *
from ledger.payments.bpoint.models import BpointTransaction, BpointToken
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from mooringlicensing.components.main.models import ApplicationType
from mooringlicensing.components.payments_ml.invoice_pdf import create_invoice_pdf_bytes

import dateutil.parser
from django.db import transaction
from django.http import HttpResponse
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.views import View
from django.views.generic import TemplateView
from ledger.basket.models import Basket
from ledger.payments.invoice.models import Invoice
from ledger.payments.utils import update_payments
from oscar.apps.order.models import Order

from mooringlicensing import settings
from mooringlicensing.components.approvals.models import DcvPermit, DcvAdmission, Approval, StickerActionDetail, Sticker
from mooringlicensing.components.payments_ml.email import send_application_submit_confirmation_email
from mooringlicensing.components.approvals.email import send_dcv_permit_mail, send_dcv_admission_mail, \
    send_sticker_replacement_email
from mooringlicensing.components.payments_ml.models import ApplicationFee, DcvPermitFee, \
    DcvAdmissionFee, FeeItem, StickerActionFee, FeeItemStickerReplacement, FeeItemApplicationFee
from mooringlicensing.components.payments_ml.utils import checkout, create_fee_lines, set_session_application_invoice, \
    get_session_application_invoice, delete_session_application_invoice, set_session_dcv_permit_invoice, \
    get_session_dcv_permit_invoice, delete_session_dcv_permit_invoice, set_session_dcv_admission_invoice, \
    create_fee_lines_for_dcv_admission, get_session_dcv_admission_invoice, delete_session_dcv_admission_invoice, \
    checkout_existing_invoice, set_session_sticker_action_invoice, get_session_sticker_action_invoice, \
    delete_session_sticker_action_invoice, ItemNotSetInSessionException
from mooringlicensing.components.proposals.models import Proposal, ProposalUserAction, \
    AuthorisedUserApplication, MooringLicenceApplication, WaitingListApplication, AnnualAdmissionApplication, \
    VesselDetails
from mooringlicensing.settings import PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL, PAYMENT_SYSTEM_PREFIX

logger = logging.getLogger('mooringlicensing')


class DcvAdmissionFeeView(TemplateView):

    def get_object(self):
        return get_object_or_404(DcvAdmission, id=self.kwargs['dcv_admission_pk'])

    def post(self, request, *args, **kwargs):
        dcv_admission = self.get_object()
        dcv_admission_fee = DcvAdmissionFee.objects.create(dcv_admission=dcv_admission, created_by=dcv_admission.submitter, payment_type=DcvAdmissionFee.PAYMENT_TYPE_TEMPORARY)

        try:
            with transaction.atomic():
                set_session_dcv_admission_invoice(request.session, dcv_admission_fee)

                lines, db_processes_after_success = create_fee_lines_for_dcv_admission(dcv_admission)

                request.session['db_processes'] = db_processes_after_success
                checkout_response = checkout(
                    request,
                    dcv_admission.submitter,
                    lines,
                    return_url_ns='dcv_admission_fee_success',
                    return_preload_url_ns='dcv_admission_fee_success',
                    invoice_text='DCV Admission Fee',
                )

                logger.info('{} built payment line item {} for DcvAdmission Fee and handing over to payment gateway'.format(dcv_admission.submitter, dcv_admission.id))
                return checkout_response

        except Exception as e:
            logger.error('Error Creating DcvAdmission Fee: {}'.format(e))
            if dcv_admission_fee:
                dcv_admission_fee.delete()
            raise


class DcvPermitFeeView(TemplateView):

    def get_object(self):
        return get_object_or_404(DcvPermit, id=self.kwargs['dcv_permit_pk'])

    def post(self, request, *args, **kwargs):
        dcv_permit = self.get_object()
        created_by = None if request.user.is_anonymous() else request.user
        dcv_permit_fee = DcvPermitFee.objects.create(dcv_permit=dcv_permit, created_by=created_by, payment_type=DcvPermitFee.PAYMENT_TYPE_TEMPORARY)

        try:
            with transaction.atomic():
                set_session_dcv_permit_invoice(request.session, dcv_permit_fee)

                lines, db_processes_after_success = create_fee_lines(dcv_permit)

                request.session['db_processes'] = db_processes_after_success
                checkout_response = checkout(
                    request,
                    dcv_permit.submitter,
                    lines,
                    return_url_ns='dcv_permit_fee_success',
                    return_preload_url_ns='dcv_permit_fee_success',
                    invoice_text='DCV Permit Fee',
                )

                logger.info('{} built payment line item {} for DcvPermit Fee and handing over to payment gateway'.format(request.user, dcv_permit.id))
                return checkout_response

        except Exception as e:
            logger.error('Error Creating DcvPermit Fee: {}'.format(e))
            if dcv_permit_fee:
                dcv_permit_fee.delete()
            raise


class ConfirmationView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_submit.html'

    def get_object(self):
        return get_object_or_404(Proposal, id=self.kwargs['proposal_pk'])

    def post(self, request, *args, **kwargs):
        proposal = self.get_object()

        if proposal.application_type.code in (WaitingListApplication.code, AnnualAdmissionApplication.code,):
            self.send_confirmation_mail(proposal, request)
        else:
            pass
            # Confirmation email has been sent in the instance.process_after_submit()

        context = {
            'proposal': proposal,
            'submitter': proposal.submitter,
        }
        return render(request, self.template_name, context)

    @staticmethod
    def send_confirmation_mail(proposal, request):
        # Send invoice
        to_email_addresses = proposal.submitter.email
        email_data = send_application_submit_confirmation_email(request, proposal, [to_email_addresses, ])


class ApplicationFeeExistingView(TemplateView):
    def get_object(self):
        return get_object_or_404(Proposal, id=self.kwargs['proposal_pk'])

    def get(self, request, *args, **kwargs):
        proposal = self.get_object()
        application_fee = proposal.application_fees.first()

        try:
            with transaction.atomic():
                set_session_application_invoice(request.session, application_fee)
                invoice = Invoice.objects.get(reference=application_fee.invoice_reference)

                request.session['db_processes'] = {'payment_for_existing_invoice': True}
                checkout_response = checkout_existing_invoice(
                    request,
                    invoice,
                    return_url_ns='fee_success',
                )

                logger.info('{} built payment line item {} for Application Fee and handing over to payment gateway'.format(
                    'User {} with id {}'.format(
                        request.user.get_full_name(), request.user.id
                    ), application_fee.proposal.lodgement_number
                ))
                return checkout_response

        except Exception as e:
            logger.error('Error Creating Application Fee: {}'.format(e))
            raise


class StickerReplacementFeeView(TemplateView):
    def get_object(self):
        if 'approval_pk' in self.kwargs:
            return get_object_or_404(Approval, id=self.kwargs['approval_pk'])
        elif 'sticker_id' in self.kwargs:
            return get_object_or_404(Sticker, id=self.kwargs['sticker_id'])
        else:
            # Should not reach here
            pass

    def post(self, request, *args, **kwargs):
        # approval = self.get_object()
        data = request.POST.get('data')
        data = json.loads(data)
        ids = data['sticker_action_detail_ids']

        # 1. Validate data
        # raise forms.ValidationError('Validation error')

        # 2. Store detais in the session
        sticker_action_fee = StickerActionFee.objects.create(created_by=request.user, payment_type=StickerActionFee.PAYMENT_TYPE_TEMPORARY)
        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))

        try:
            with transaction.atomic():
                sticker_action_details = StickerActionDetail.objects.filter(id__in=ids)
                sticker_action_details.update(sticker_action_fee=sticker_action_fee)

                set_session_sticker_action_invoice(request.session, sticker_action_fee)

                target_datetime_str = current_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')
                application_type = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_REPLACEMENT_STICKER['code'])
                fee_item = FeeItemStickerReplacement.get_fee_item_by_date(current_datetime.date())

                lines = []
                for sticker_action_detail in sticker_action_details:
                    line = {
                        'ledger_description': 'Sticker Replacement Fee, sticker: {} @{}'.format(sticker_action_detail.sticker, target_datetime_str),
                        'oracle_code': application_type.get_oracle_code_by_date(current_datetime.date()),
                        'price_incl_tax': fee_item.amount,
                        'price_excl_tax': calculate_excl_gst(fee_item.amount) if fee_item.incur_gst else fee_item.amount,
                        'quantity': 1,
                    }
                    lines.append(line)

                checkout_response = checkout(
                    request,
                    request.user,
                    lines,
                    return_url_ns='sticker_replacement_fee_success',
                    return_preload_url_ns='sticker_replacement_fee_success',
                    invoice_text='{}'.format(application_type.description),
                )

                logger.info('{} built payment line item(s) {} for Sticker Replacement Fee and handing over to payment gateway'.format('User {} with id {}'.format(request.user.get_full_name(), request.user.id), sticker_action_fee))
                return checkout_response

        except Exception as e:
            logger.error('Error handling StickerActionFee: {}'.format(e))
            if sticker_action_fee:
                sticker_action_fee.delete()
            raise


class StickerReplacementFeeSuccessView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_sticker_action_fee.html'
    LAST_STICKER_ACTION_FEE_ID = 'mooringlicensing_last_dcv_admission_invoice'

    def get(self, request, *args, **kwargs):

        try:
            sticker_action_fee = get_session_sticker_action_invoice(request.session)  # This raises an exception when accessed 2nd time?
            sticker_action_details = sticker_action_fee.sticker_action_details

            if self.request.user.is_authenticated():
                owner = request.user
            else:
                owner = sticker_action_details.first().sticker.approval.submitter
            basket = Basket.objects.filter(status='Submitted', owner=owner).order_by('-id')[:1]

            order = Order.objects.get(basket=basket[0])
            invoice = Invoice.objects.get(order_number=order.number)

            sticker_action_fee.invoice_reference = invoice.reference
            sticker_action_fee.save()

            if sticker_action_fee.payment_type == StickerActionFee.PAYMENT_TYPE_TEMPORARY:
                try:
                    inv = Invoice.objects.get(reference=invoice.reference)
                    order = Order.objects.get(number=inv.order_number)
                    order.user = request.user
                    order.save()
                except Invoice.DoesNotExist:
                    logger.error('{} tried paying an application fee with an incorrect invoice'.format(
                        'User {} with id {}'.format(owner.get_full_name(), owner.id)
                    ))
                    return redirect('external')
                if inv.system not in [PAYMENT_SYSTEM_PREFIX,]:
                    logger.error('{} tried paying an application fee with an invoice from another system with reference number {}'.format(
                        'User {} with id {}'.format(owner.get_full_name(), owner.id),
                        inv.reference
                    ))
                    return redirect('external')

                # if fee_inv:
                sticker_action_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                sticker_action_fee.expiry_time = None
                update_payments(invoice.reference)

                for sticker_action_detail in sticker_action_details.all():
                    old_sticker = sticker_action_detail.sticker
                    new_sticker = old_sticker.request_replacement(Sticker.STICKER_STATUS_LOST)

                sticker_action_fee.save()
                request.session[self.LAST_STICKER_ACTION_FEE_ID] = sticker_action_fee.id
                delete_session_sticker_action_invoice(request.session)  # This leads to raise an exception at the get_session_sticker_action_invoice() above

                # Send email with the invoice
                send_sticker_replacement_email(request, old_sticker, new_sticker, invoice)

                context = {
                    'submitter': owner,
                    'fee_invoice': sticker_action_fee,
                }
                print('render1')
                return render(request, self.template_name, context)

        except Exception as e:
            print('4')
            if (self.LAST_STICKER_ACTION_FEE_ID in request.session) and StickerActionFee.objects.filter(id=request.session[self.LAST_STICKER_ACTION_FEE_ID]).exists():
                sticker_action_fee = StickerActionFee.objects.get(id=request.session[self.LAST_STICKER_ACTION_FEE_ID])
                owner = sticker_action_fee.sticker_action_details.first().sticker.approval.submitter
            else:
                return redirect('home')

            context = {
                'submitter': owner,
                'fee_invoice': sticker_action_fee,
            }
            print('render2')
            return render(request, self.template_name, context)


class ApplicationFeeView(TemplateView):

    def get_object(self):
        return get_object_or_404(Proposal, id=self.kwargs['proposal_pk'])

    def post(self, request, *args, **kwargs):
        proposal = self.get_object()
        application_fee = ApplicationFee.objects.create(proposal=proposal, created_by=request.user, payment_type=ApplicationFee.PAYMENT_TYPE_TEMPORARY)
        logger.info('ApplicationFee.id: {} has been created for the Proposal: {}'.format(application_fee.id, proposal))

        try:
            with transaction.atomic():
                set_session_application_invoice(request.session, application_fee)

                lines, db_processes_after_success = proposal.child_obj.create_fee_lines()  # Accessed by WL and AA

                request.session['db_processes'] = db_processes_after_success
                #request.session['auto_approve'] = request.POST.get('auto_approve', False)
                checkout_response = checkout(
                    request,
                    proposal.submitter,
                    lines,
                    return_url_ns='fee_success',
                    return_preload_url_ns='fee_success',
                    invoice_text='{} ({})'.format(proposal.application_type.description, proposal.proposal_type.description),
                )

                logger.info('{} built payment line item {} for Application Fee and handing over to payment gateway'.format('User {} with id {}'.format(proposal.submitter.get_full_name(),proposal.submitter.id), proposal.id))
                return checkout_response

        except Exception as e:
            logger.error('Error while checking out for the proposal: {}\n{}'.format(proposal.lodgement_number, str(e)))
            if application_fee:
                application_fee.delete()
                logger.info('ApplicationFee: {} has been deleted'.format(application_fee))
            raise


class DcvAdmissionFeeSuccessView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_dcv_admission_fee.html'
    LAST_DCV_ADMISSION_FEE_ID = 'mooringlicensing_last_dcv_admission_invoice'

    def get(self, request, *args, **kwargs):
        proposal = None
        submitter = None
        invoice = None

        try:
            dcv_admission_fee = get_session_dcv_admission_invoice(request.session)  # This raises an exception when accessed 2nd time?

            # Retrieve db processes stored when calculating the fee, and delete the session
            db_operations = request.session['db_processes']
            del request.session['db_processes']

            dcv_admission = dcv_admission_fee.dcv_admission
            # recipient = dcv_permit.applicant_email
            submitter = dcv_admission.submitter

            if self.request.user.is_authenticated():
                basket = Basket.objects.filter(status='Submitted', owner=request.user).order_by('-id')[:1]
            else:
                basket = Basket.objects.filter(status='Submitted', owner=dcv_admission.submitter).order_by('-id')[:1]

            order = Order.objects.get(basket=basket[0])
            invoice = Invoice.objects.get(order_number=order.number)
            invoice_ref = invoice.reference

            # Update the application_fee object
            dcv_admission_fee.invoice_reference = invoice_ref
            dcv_admission_fee.save()

            if dcv_admission_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY:
                try:
                    inv = Invoice.objects.get(reference=invoice_ref)
                    order = Order.objects.get(number=inv.order_number)
                    order.user = submitter
                    order.save()
                except Invoice.DoesNotExist:
                    logger.error('{} tried paying an dcv_admission fee with an incorrect invoice'.format('User {} with id {}'.format(dcv_admission.submitter.get_full_name(), dcv_admission.submitter.id) if dcv_admission.submitter else 'An anonymous user'))
                    return redirect('external-dcv_admission-detail', args=(dcv_admission.id,))
                if inv.system not in [PAYMENT_SYSTEM_PREFIX,]:
                    logger.error('{} tried paying an dcv_admission fee with an invoice from another system with reference number {}'.format('User {} with id {}'.format(dcv_admission.submitter.get_full_name(), dcv_admission.submitter.id) if dcv_admission.submitter else 'An anonymous user',inv.reference))
                    return redirect('external-dcv_admission-detail', args=(dcv_admission.id,))

                dcv_admission_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                dcv_admission_fee.expiry_time = None
                update_payments(invoice_ref)

                if dcv_admission and invoice.payment_status in ('paid', 'over_paid',):
                    self.adjust_db_operations(dcv_admission, db_operations)
                    dcv_admission.generate_dcv_admission_doc()
                else:
                    logger.error('Invoice payment status is {}'.format(invoice.payment_status))
                    raise

                dcv_admission_fee.save()
                request.session[self.LAST_DCV_ADMISSION_FEE_ID] = dcv_admission_fee.id
                delete_session_dcv_admission_invoice(request.session)

                email_data = send_dcv_admission_mail(dcv_admission, invoice, request)
                context = {
                    'dcv_admission': dcv_admission,
                    'submitter': submitter,
                    'fee_invoice': dcv_admission_fee,
                    'invoice': invoice,
                }
                return render(request, self.template_name, context)

        except Exception as e:
            if (self.LAST_DCV_ADMISSION_FEE_ID in request.session) and DcvAdmissionFee.objects.filter(id=request.session[self.LAST_DCV_ADMISSION_FEE_ID]).exists():
                dcv_admission_fee = DcvAdmissionFee.objects.get(id=request.session[self.LAST_DCV_ADMISSION_FEE_ID])
                dcv_admission = dcv_admission_fee.dcv_admission
                submitter = dcv_admission.submitter

            else:
                return redirect('home')

        invoice = Invoice.objects.get(reference=dcv_admission_fee.invoice_reference)
        context = {
            'dcv_admission': dcv_admission,
            'submitter': submitter,
            'fee_invoice': dcv_admission_fee,
            'invoice': invoice,
        }
        return render(request, self.template_name, context)

    @staticmethod
    def adjust_db_operations(dcv_admission, db_operations):
        dcv_admission.lodgement_datetime = dateutil.parser.parse(db_operations['datetime_for_calculating_fee'])
        dcv_admission.save()


class DcvPermitFeeSuccessView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_dcv_permit_fee.html'
    LAST_DCV_PERMIT_FEE_ID = 'mooringlicensing_last_dcv_permit_invoice'

    def get(self, request, *args, **kwargs):
        proposal = None
        submitter = None
        invoice = None

        try:
            dcv_permit_fee = get_session_dcv_permit_invoice(request.session)  # This raises an exception when accessed 2nd time?

            # Retrieve db processes stored when calculating the fee, and delete the session
            db_operations = request.session['db_processes']
            del request.session['db_processes']

            dcv_permit = dcv_permit_fee.dcv_permit
            submitter = dcv_permit.submitter

            if self.request.user.is_authenticated():
                basket = Basket.objects.filter(status='Submitted', owner=request.user).order_by('-id')[:1]
            else:
                basket = Basket.objects.filter(status='Submitted', owner=dcv_permit.submitter).order_by('-id')[:1]

            order = Order.objects.get(basket=basket[0])
            invoice = Invoice.objects.get(order_number=order.number)
            invoice_ref = invoice.reference

            fee_item = FeeItem.objects.get(id=db_operations['fee_item_id'])
            try:
                fee_item_additional = FeeItem.objects.get(id=db_operations['fee_item_additional_id'])
            except:
                fee_item_additional = None

            # Update the application_fee object
            dcv_permit_fee.invoice_reference = invoice_ref
            dcv_permit_fee.save()
            dcv_permit_fee.fee_items.add(fee_item)
            if fee_item_additional:
                dcv_permit_fee.fee_items.add(fee_item_additional)

            if dcv_permit_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY:
                try:
                    inv = Invoice.objects.get(reference=invoice_ref)
                    order = Order.objects.get(number=inv.order_number)
                    order.user = request.user
                    order.save()
                except Invoice.DoesNotExist:
                    logger.error('{} tried paying an dcv_permit fee with an incorrect invoice'.format('User {} with id {}'.format(dcv_permit.submitter.get_full_name(), dcv_permit.submitter.id) if dcv_permit.submitter else 'An anonymous user'))
                    return redirect('external-dcv_permit-detail', args=(dcv_permit.id,))
                if inv.system not in [PAYMENT_SYSTEM_PREFIX,]:
                    logger.error('{} tried paying an dcv_permit fee with an invoice from another system with reference number {}'.format('User {} with id {}'.format(dcv_permit.submitter.get_full_name(), dcv_permit.submitter.id) if dcv_permit.submitter else 'An anonymous user',inv.reference))
                    return redirect('external-dcv_permit-detail', args=(dcv_permit.id,))

                dcv_permit_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                dcv_permit_fee.expiry_time = None
                update_payments(invoice_ref)

                if dcv_permit and invoice.payment_status in ('paid', 'over_paid',):
                    self.adjust_db_operations(dcv_permit, db_operations)
                    dcv_permit.generate_dcv_permit_doc()
                else:
                    logger.error('Invoice payment status is {}'.format(invoice.payment_status))
                    raise

                dcv_permit_fee.save()
                request.session[self.LAST_DCV_PERMIT_FEE_ID] = dcv_permit_fee.id
                delete_session_dcv_permit_invoice(request.session)

                send_dcv_permit_mail(dcv_permit, invoice, request)

                context = {
                    'dcv_permit': dcv_permit,
                    'submitter': submitter,
                    'fee_invoice': dcv_permit_fee,
                }
                return render(request, self.template_name, context)

        except Exception as e:
            print('in DcvPermitFeeSuccessView.get() Exception')
            print(e)
            if (self.LAST_DCV_PERMIT_FEE_ID in request.session) and DcvPermitFee.objects.filter(id=request.session[self.LAST_DCV_PERMIT_FEE_ID]).exists():
                dcv_permit_fee = DcvPermitFee.objects.get(id=request.session[self.LAST_DCV_PERMIT_FEE_ID])
                dcv_permit = dcv_permit_fee.dcv_permit
                submitter = dcv_permit.submitter

            else:
                return redirect('home')

        context = {
            'dcv_permit': dcv_permit,
            'submitter': submitter,
            'fee_invoice': dcv_permit_fee,
        }
        return render(request, self.template_name, context)

    @staticmethod
    def adjust_db_operations(dcv_permit, db_operations):
        dcv_permit.start_date = datetime.datetime.strptime(db_operations['season_start_date'], '%Y-%m-%d').date()
        dcv_permit.end_date = datetime.datetime.strptime(db_operations['season_end_date'], '%Y-%m-%d').date()
        dcv_permit.lodgement_datetime = dateutil.parser.parse(db_operations['datetime_for_calculating_fee'])
        dcv_permit.save()


class ApplicationFeeSuccessView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_application_fee.html'
    LAST_APPLICATION_FEE_ID = 'mooringlicensing_last_app_invoice'

    def get(self, request, *args, **kwargs):
        print('in ApplicationFeeSuccessView.get()')

        proposal = None
        submitter = None
        invoice = None

        try:
            application_fee = get_session_application_invoice(request.session)  # This raises an exception when accessed 2nd time?

            # Retrieve db processes stored when calculating the fee, and delete the session
            db_operations = request.session['db_processes']
            del request.session['db_processes']
            #print("request.session.keys()")
            #print(request.session.keys())
            # Retrieve auto_approve stored when calculating the fee, and delete
            #auto_approve = request.session.get('auto_approve')
            #if 'auto_approve' in request.session.keys():
             #   del request.session['auto_approve']

            proposal = application_fee.proposal
            recipient = proposal.applicant_email
            submitter = proposal.submitter

            try:
                # For the existing invoice, invoice can be retrieved from the application_fee object
                invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            except Exception as e:
                # For the non-existing invoice, invoice can be retrieved from the basket
                if self.request.user.is_authenticated():
                    basket = Basket.objects.filter(status='Submitted', owner=request.user).order_by('-id')[:1]
                else:
                    basket = Basket.objects.filter(status='Submitted', owner=proposal.submitter).order_by('-id')[:1]
                order = Order.objects.get(basket=basket[0])
                invoice = Invoice.objects.get(order_number=order.number)

            invoice_ref = invoice.reference

            # Update the application_fee object
            # For the AUA and MLA's new/amendment application, the application_fee already has relations to fee_item(s) created after creating lines.
            # In that case, there are no 'fee_item_id' and/or 'fee_item_additional_id' keys in the db_operations
            if 'fee_item_id' in db_operations:
                fee_items = FeeItem.objects.filter(id=db_operations['fee_item_id'])
                if fee_items:
                    FeeItemApplicationFee.objects.create(
                        fee_item=fee_items.first(),
                        application_fee=application_fee,
                        vessel_details=proposal.vessel_details,
                    )
            if 'fee_item_additional_id' in db_operations:
                fee_item_additionals = FeeItem.objects.filter(id=db_operations['fee_item_additional_id'])
                if fee_item_additionals:
                    FeeItemApplicationFee.objects.create(
                        fee_item=fee_item_additionals.first(),
                        application_fee=application_fee,
                        vessel_details=proposal.vessel_details,
                    )
            if isinstance(db_operations, list):
                # This is used for AU/ML's auto renewal
                for item in db_operations:
                    fee_item = FeeItem.objects.get(id=item['fee_item_id'])
                    vessel_details = VesselDetails.objects.get(id=item['vessel_details_id'])
                    FeeItemApplicationFee.objects.create(
                        fee_item=fee_item,
                        application_fee=application_fee,
                        vessel_details=vessel_details,
                    )

            application_fee.invoice_reference = invoice_ref
            application_fee.save()

            if application_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY:
                try:
                    inv = Invoice.objects.get(reference=invoice_ref)
                    order = Order.objects.get(number=inv.order_number)
                    order.user = request.user
                    order.save()
                except Invoice.DoesNotExist:
                    logger.error('{} tried paying an application fee with an incorrect invoice'.format('User {} with id {}'.format(proposal.submitter.get_full_name(), proposal.submitter.id) if proposal.submitter else 'An anonymous user'))
                    return redirect('external-proposal-detail', args=(proposal.id,))
                if inv.system not in [PAYMENT_SYSTEM_PREFIX,]:
                    logger.error('{} tried paying an application fee with an invoice from another system with reference number {}'.format('User {} with id {}'.format(proposal.submitter.get_full_name(), proposal.submitter.id) if proposal.submitter else 'An anonymous user',inv.reference))
                    return redirect('external-proposal-detail', args=(proposal.id,))

                application_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                application_fee.expiry_time = None
                update_payments(invoice_ref)

                if proposal and invoice.payment_status in ('paid', 'over_paid',):
                    logger.info('The fee for the proposal: {} has been fully paid'.format(proposal.lodgement_number))

                    if proposal.application_type.code in (AuthorisedUserApplication.code, MooringLicenceApplication.code):
                        # For AUA or MLA, as payment has been done, create approval
                        approval, created = proposal.child_obj.update_or_create_approval(datetime.datetime.now(pytz.timezone(TIME_ZONE)), request)
                    else:
                        # When WLA / AAA
                        if proposal.application_type.code in [WaitingListApplication.code, AnnualAdmissionApplication.code]:
                            proposal.lodgement_date = datetime.datetime.now(pytz.timezone(TIME_ZONE))
                            proposal.log_user_action(ProposalUserAction.ACTION_LODGE_APPLICATION.format(proposal.id), request)

                            ret1 = proposal.child_obj.send_emails_after_payment_success(request)
                            if not ret1:
                                raise ValidationError('An error occurred while submitting proposal (Submit email notifications failed)')
                            proposal.save()

                        proposal.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
                        proposal.customer_status = Proposal.CUSTOMER_STATUS_WITH_ASSESSOR
                        proposal.save()

                else:
                    msg = 'Invoice: {} payment status is {}.  It should be either paid or over_paid'.format(invoice.reference, invoice.payment_status)
                    logger.error(msg)
                    raise Exception(msg)

                application_fee.save()
                request.session[self.LAST_APPLICATION_FEE_ID] = application_fee.id
                delete_session_application_invoice(request.session)

                wla_or_aaa = True if proposal.application_type.code in [WaitingListApplication.code, AnnualAdmissionApplication.code,] else False
                context = {
                    'proposal': proposal,
                    'submitter': submitter,
                    'fee_invoice': application_fee,
                    'is_wla_or_aaa': wla_or_aaa,
                    'invoice': invoice,
                }
                return render(request, self.template_name, context)

        except ItemNotSetInSessionException as e:
            if self.LAST_APPLICATION_FEE_ID in request.session:
                if ApplicationFee.objects.filter(id=request.session[self.LAST_APPLICATION_FEE_ID]).exists():
                    application_fee = ApplicationFee.objects.get(id=request.session[self.LAST_APPLICATION_FEE_ID])
                    proposal = application_fee.proposal
                    submitter = proposal.submitter
                    if type(proposal.child_obj) in [WaitingListApplication, AnnualAdmissionApplication]:
                        proposal.auto_approve_check(request)
                else:
                    msg = 'ApplicationFee with id: {} does not exist in the database'.format(str(request.session[self.LAST_APPLICATION_FEE_ID]))
                    logger.error(msg)
                    return redirect('home')  # Should be 'raise' rather than redirect?
            else:
                msg = '{} is not set in session'.format(self.LAST_APPLICATION_FEE_ID)
                logger.error(msg)
                return redirect('home')  # Should be 'raise' rather than redirect?
        except Exception as e:
            # Should not reach here
            msg = 'Failed to process the payment. {}'.format(str(e))
            logger.error(msg)
            raise Exception(msg)

        wla_or_aaa = True if proposal.application_type.code in [WaitingListApplication.code, AnnualAdmissionApplication.code,] else False
        invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
        context = {
            'proposal': proposal,
            'submitter': submitter,
            'fee_invoice': application_fee,
            'is_wla_or_aaa': wla_or_aaa,
            'invoice': invoice,
        }
        return render(request, self.template_name, context)


class DcvAdmissionPDFView(View):
    def get(self, request, *args, **kwargs):
        try:
            dcv_admission = get_object_or_404(DcvAdmission, id=self.kwargs['id'])
            response = HttpResponse(content_type='application/pdf')
            if dcv_admission.admissions.count() < 1:
                logger.warn('DcvAdmission: {} does not have any admission document.'.format(dcv_admission))
                return response
            elif dcv_admission.admissions.count() == 1:
                response.write(dcv_admission.admissions.first()._file.read())
                return response
            else:
                logger.warn('DcvAdmission: {} has more than one admissions.'.format(dcv_admission))
                return response
        except DcvAdmission.DoesNotExist:
            raise
        except Exception as e:
            logger.error('Error accessing the DcvAdmission :{}'.format(e))
            raise


class DcvPermitPDFView(View):
    def get(self, request, *args, **kwargs):
        try:
            dcv_permit = get_object_or_404(DcvPermit, id=self.kwargs['id'])
            response = HttpResponse(content_type='application/pdf')
            if dcv_permit.permits.count() < 1:
                logger.warn('DcvPermit: {} does not have any permit document.'.format(dcv_permit))
                return response
            elif dcv_permit.permits.count() == 1:
                response.write(dcv_permit.permits.first()._file.read())
                return response
            else:
                logger.warn('DcvPermit: {} has more than one permits.'.format(dcv_permit))
                return response
        except DcvPermit.DoesNotExist:
            raise
        except Exception as e:
            logger.error('Error accessing the DcvPermit :{}'.format(e))
            raise


class InvoicePDFView(View):
    def get(self, request, *args, **kwargs):
        try:
            invoice = get_object_or_404(Invoice, reference=self.kwargs['reference'])

            response = HttpResponse(content_type='application/pdf')
            response.write(create_invoice_pdf_bytes('invoice.pdf', invoice,))
            return response
        except Invoice.DoesNotExist:
            raise
        except Exception as e:
            logger.error('Error accessing the Invoice :{}'.format(e))
            raise

    def get_object(self):
        return get_object_or_404(Invoice, reference=self.kwargs['reference'])


class RefundProposalHistoryView(LoginRequiredMixin, TemplateView):
#class RefundProposalHistory(LoginRequiredMixin, TemplateView):
    template_name = 'mooringlicensing/payments_ml/proposal_refund_history.html'

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None
        print ("LOADED")
        if request.user.is_superuser or request.user.groups.filter(name__in=['Mooring Licensing - Payment Officers']).exists():
#            booking = Proposal.objects.get(customer=request.user, booking_type__in=(0, 1), is_canceled=False, pk=booking_id)
             booking = Proposal.objects.get(pk=booking_id)
             newest_booking = booking_id #self.get_newest_booking(booking_id)
             booking_history = self.get_history(newest_booking, booking_array=[])
             invoice_line_items = self.get_history_line_items(booking_history)
             context = {
                'booking_id': booking_id,
                'booking': booking,
                'newest_booking': newest_booking,
                'booking_history' : booking_history,
                'invoice_line_items' : invoice_line_items,
                'oracle_code_refund_allocation_pool': settings.UNALLOCATED_ORACLE_CODE,
                'GIT_COMMIT_DATE' : settings.GIT_COMMIT_DATE,
                'GIT_COMMIT_HASH' : settings.GIT_COMMIT_HASH,
                'API_URL' : '/api/refund_oracle',
                'booking_class_type' : booking.__class__.__name__

             }
             return render(request, self.template_name,context)
        else:
             messages.error(self.request, 'Permission denied.')
             return HttpResponseRedirect(reverse('home')) 

    #def get_newest_booking(self, booking_id):
    #    latest_id = booking_id
    #    if Proposal.objects.filter(old_booking=booking_id).exclude(booking_type=3).count() > 0:
    #        booking = Proposal.objects.filter(old_booking=booking_id)[0]
    #        latest_id = self.get_newest_booking(booking.id)
    #    return latest_id

    def get_history_line_items(self, booking_history):

        invoice_line_items = []
        invoice_line_items_array = []
        invoice_bpoint = []
        rolling_total = Decimal('0.00')
        bpoint_trans_totals = {}
        unique_oracle_code_on_booking = {}
        total_booking_allocation_pool = Decimal('0.00')
        total_bpoint_amount_available = Decimal('0.00')
        entry_count = 0
        for bi in booking_history:
            booking = Proposal.objects.get(pk=bi['booking'].id)
            booking.invoices =()
            #booking.invoices = ApplicationFee.objects.filter(booking=booking)

            booking_invoices= ApplicationFee.objects.filter(proposal=booking)
            for i in booking_invoices:
                 bp = BpointTransaction.objects.filter(crn1=i.invoice_reference)
                 for trans in bp:
                     if trans.action == 'payment':
                            if trans.txn_number not in bpoint_trans_totals:
                                   bpoint_trans_totals[trans.txn_number] = {'crn1': '', 'amount': Decimal('0.00')}
                             
                            total_bpoint_amount_available = total_bpoint_amount_available + trans.amount
                            bpoint_trans_totals[trans.txn_number]['amount'] = bpoint_trans_totals[trans.txn_number]['amount'] + trans.amount 
                            bpoint_trans_totals[trans.txn_number]['crn1'] = trans.crn1
                     if trans.action == 'refund':
                            if trans.original_txn not in bpoint_trans_totals:
                                   bpoint_trans_totals[trans.original_txn] = {'crn': '', 'amount': Decimal('0.00')}
                            bpoint_trans_totals[trans.original_txn]['amount'] = bpoint_trans_totals[trans.original_txn]['amount'] - trans.amount
                            total_bpoint_amount_available = total_bpoint_amount_available - trans.amount
                     invoice_bpoint.append(trans)

                 iv = Invoice.objects.filter(reference=i.invoice_reference)
                 for b in iv:
                    o = Order.objects.get(number=b.order_number)
                    for ol in o.lines.all():
                        if ol.oracle_code == settings.UNALLOCATED_ORACLE_CODE:
                             total_booking_allocation_pool = total_booking_allocation_pool + ol.line_price_incl_tax
                        #rolling_total = rolling_total + ol.line_price_incl_tax
                        entry_count = entry_count + 1
                        invoice_line_items_array.append({'line_id': ol.id, 'order_number': ol.order.number, 'title': ol.title, 'oracle_code': ol.oracle_code, 'line_price_incl_tax': ol.line_price_incl_tax, 'order_date_placed': ol.order.date_placed, 'rolling_total': '0.00' ,'entry_count': entry_count })
                        invoice_line_items.append(ol)

                        if ol.oracle_code == settings.UNALLOCATED_ORACLE_CODE:
                             pass
                        else:
                             if ol.oracle_code not in unique_oracle_code_on_booking:
                                 unique_oracle_code_on_booking[ol.oracle_code] = Decimal('0.00') 

                             unique_oracle_code_on_booking[ol.oracle_code] = unique_oracle_code_on_booking[ol.oracle_code] + Decimal(ol.line_price_incl_tax)
#                             unique_oracle_code_on_booking[ol.oracle_code] = float("%.2f".format(str(unique_oracle_code_on_booking[ol.oracle_code])))
#                            unique_oracle_code_on_booking.append(ol.oracle_code)
        for ocb in unique_oracle_code_on_booking:
                unique_oracle_code_on_booking[ocb] = str(unique_oracle_code_on_booking[ocb])

        for btt in bpoint_trans_totals:
             bpoint_trans_totals[btt]['amount'] = str(bpoint_trans_totals[btt]['amount'])
        #UNALLOCATED_ORACLE_CODE

        invoice_line_items_array.sort(key=lambda item:item['order_date_placed'], reverse=False)
       
        for il in invoice_line_items_array:
            rolling_total = Decimal(rolling_total) + Decimal(il['line_price_incl_tax'])
            il['rolling_total'] = rolling_total
        
        booking_balance_issue = False
        if rolling_total < 0:
            booking_balance_issue = True

        return {'invoice_line_items': invoice_line_items, 'invoice_line_items_array':  invoice_line_items_array, 'booking_balance_issue': booking_balance_issue,'total_booking_allocation_pool': total_booking_allocation_pool, 'invoice_bpoint': invoice_bpoint,'total_bpoint_amount_available': total_bpoint_amount_available, 'unique_oracle_code_on_booking': json.dumps(unique_oracle_code_on_booking),'bpoint_trans_totals': json.dumps(bpoint_trans_totals)}

    def get_history(self, booking_id, booking_array=[]):
        booking = Proposal.objects.get(pk=booking_id)
        booking.invoices =()
        booking_invoices= ApplicationFee.objects.filter(proposal=booking)
        booking_array.append({'booking': booking, 'invoices': booking_invoices})
 
        #if booking.old_booking:
         #    self.get_history(booking.old_booking.id, booking_array)
        return booking_array

# include LoginRequiredMixin
class ProposalPaymentHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'mooringlicensing/payments_ml/proposal_payments_history.html'

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None

        if request.user.is_staff or request.user.is_superuser or Proposal.objects.filter(submitter=request.user,pk=booking_id).count() == 1:
             booking = Proposal.objects.get(pk=booking_id)
             #newest_booking = self.get_newest_booking(booking_id)
             newest_booking = booking_id
             booking_history = self.get_history(newest_booking, booking_array=[])
             #print vars(booking_history['bookings'])

        context = {
           'booking_id': booking_id,
           'booking': booking,
           'booking_history' : booking_history,
           'GIT_COMMIT_DATE' : settings.GIT_COMMIT_DATE,
           'GIT_COMMIT_HASH' : settings.GIT_COMMIT_HASH,
        }

        return render(request, self.template_name,context)

    #def get_newest_booking(self, booking_id):
    #    latest_id = booking_id
    #    if Booking.objects.filter(old_booking=booking_id).exclude(booking_type=3).count() > 0:
    #        booking = Booking.objects.filter(old_booking=booking_id)[0]   
    #        latest_id = self.get_newest_booking(booking.id)
    #    return latest_id

    def get_history(self, booking_id, booking_array=[]):
        booking = Proposal.objects.get(pk=booking_id)
        booking.invoices =()
        #booking.invoices = BookingInvoice.objects.filter(booking=booking)
        booking_invoices= ApplicationFee.objects.filter(proposal=booking) 
#        for bi in booking_invoices:
#            print bi
#            booking.invoices.add(bi)

        booking_array.append({'booking': booking, 'invoices': booking_invoices})
        #if booking.old_booking:
         #    self.get_history(booking.old_booking.id, booking_array)
        return booking_array

