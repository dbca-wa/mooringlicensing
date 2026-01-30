import datetime
import logging

import ledger_api_client.utils
import pytz
import json

from rest_framework.views import APIView

from mooringlicensing.ledger_api_utils import retrieve_email_userro, get_invoice_payment_status
from mooringlicensing.settings import TIME_ZONE
from decimal import *
from mooringlicensing.components.main.models import ApplicationType
from rest_framework.response import Response
from mooringlicensing.components.proposals.utils import save_proponent_data

import dateutil.parser
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import get_object_or_404, render, redirect
from django.views import View
from django.views.generic import TemplateView

from ledger_api_client.ledger_models import Invoice

from mooringlicensing.helpers import is_authorised_to_modify, is_applicant_address_set, is_authorised_to_pay_auto_approved
from mooringlicensing import settings
from mooringlicensing.components.approvals.models import DcvPermit, DcvAdmission, StickerActionDetail, Sticker, MooringOnApproval
from mooringlicensing.components.payments_ml.email import send_application_submit_confirmation_email
from mooringlicensing.components.approvals.email import (
    send_dcv_permit_mail, send_dcv_admission_mail,
    send_sticker_replacement_email
)
from mooringlicensing.components.payments_ml.models import (
    ApplicationFee, DcvPermitFee, 
    DcvAdmissionFee, FeeItem, StickerActionFee, 
    FeeItemStickerReplacement, FeeItemApplicationFee, FeeCalculation,
    OracleCodeItem
)
from mooringlicensing.components.payments_ml.utils import (
    checkout
)
from mooringlicensing.components.proposals.models import (
    Proposal, ProposalUserAction, 
    AuthorisedUserApplication, MooringLicenceApplication, 
    WaitingListApplication, AnnualAdmissionApplication, 
    VesselDetails
)
from mooringlicensing.settings import LEDGER_SYSTEM_ID
from rest_framework import status, serializers

from mooringlicensing.helpers import is_internal

logger = logging.getLogger(__name__)
from rest_framework.permissions import IsAuthenticated

from ledger_api_client import utils
from django.db.models import Q

class DcvAdmissionFeeView(TemplateView):

    def get_object(self):
        return get_object_or_404(DcvAdmission, id=self.kwargs['dcv_admission_pk'])

    def post(self, request, *args, **kwargs):
        dcv_admission = self.get_object()

        if dcv_admission.status == DcvAdmission.DCV_ADMISSION_STATUS_CANCELLED:
            raise serializers.ValidationError("DCV Admission cancelled") 

        dcv_admission_fee = DcvAdmissionFee.objects.create(dcv_admission=dcv_admission, 
        created_by=dcv_admission.applicant, payment_type=DcvAdmissionFee.PAYMENT_TYPE_TEMPORARY)

        #NOTE: DcvAdmission records can be created externally, so no auth-check has been provided here.

        try:
            with transaction.atomic():

                lines, db_processes = dcv_admission.create_fee_lines()

                new_fee_calculation = FeeCalculation.objects.create(uuid=dcv_admission_fee.uuid, data=db_processes)
                checkout_response = checkout(
                    request,
                    dcv_admission.applicant_obj,
                    lines,
                    return_url=request.build_absolute_uri(reverse('dcv_admission_fee_success', kwargs={"uuid": dcv_admission_fee.uuid})),
                    return_preload_url=settings.MOORING_LICENSING_EXTERNAL_URL + reverse("dcv_admission_fee_success_preload", kwargs={"uuid": dcv_admission_fee.uuid}),
                    booking_reference=str(dcv_admission_fee.uuid),
                    invoice_text='DCV Admission Fee',
                )

                request.session["payment_pk"] = dcv_admission.pk
                request.session["payment_model"] = "dcv_admission"

                logger.info('{} built payment line item {} for DcvAdmission Fee and handing over to payment gateway'.format(dcv_admission.applicant, dcv_admission.id))
                return checkout_response

        except Exception as e:
            logger.error('Error Creating DcvAdmission Fee: {}'.format(e))
            if dcv_admission_fee:
                dcv_admission_fee.delete()
            err_msg = 'Failed to create invoice'
            raise serializers.ValidationError(err_msg)


class DcvPermitFeeView(TemplateView):
    permission_classes=[IsAuthenticated]

    def get_object(self):
        return get_object_or_404(DcvPermit, id=self.kwargs['dcv_permit_pk'])

    def post(self, request, *args, **kwargs):
        dcv_permit = self.get_object()

        if dcv_permit.status == DcvPermit.DCV_PERMIT_STATUS_CANCELLED:
            raise serializers.ValidationError("DCV Permit cancelled") 

        created_by = None if request.user.is_anonymous else request.user.id
        dcv_permit_fee = DcvPermitFee.objects.create(dcv_permit=dcv_permit, created_by=created_by, payment_type=DcvPermitFee.PAYMENT_TYPE_TEMPORARY)

        if (is_internal(request) or request.user.id == dcv_permit.applicant):
            try:
                with transaction.atomic():

                    lines, db_processes = dcv_permit.create_fee_lines()

                    new_fee_calculation = FeeCalculation.objects.create(uuid=dcv_permit_fee.uuid, data=db_processes)
                    checkout_response = checkout(
                        request,
                        dcv_permit.applicant_obj,
                        lines,
                        return_url=request.build_absolute_uri(reverse('dcv_permit_fee_success', kwargs={"uuid": dcv_permit_fee.uuid})),
                        return_preload_url=settings.MOORING_LICENSING_EXTERNAL_URL + reverse("dcv_permit_fee_success_preload", kwargs={"uuid": dcv_permit_fee.uuid}),
                        booking_reference=str(dcv_permit_fee.uuid),
                        invoice_text='DCV Permit Fee',
                    )
                    
                    request.session["payment_pk"] = dcv_permit.pk
                    request.session["payment_model"] = "dcv_permit"

                    logger.info('{} built payment line item {} for DcvPermit Fee and handing over to payment gateway'.format(request.user, dcv_permit.id))
                    return checkout_response

            except Exception as e:
                logger.error('Error Creating DcvPermit Fee: {}'.format(e))
                if dcv_permit_fee:
                    dcv_permit_fee.delete()
                err_msg = 'Failed to create invoice'
                raise serializers.ValidationError(err_msg)
        else:
            raise serializers.ValidationError("User not authorised to access DCV Permit")        


class ConfirmationView(TemplateView):
    permission_classes=[IsAuthenticated]
    template_name = 'mooringlicensing/payments_ml/success_submit.html'

    def get_object(self):
        return get_object_or_404(Proposal, id=self.kwargs['proposal_pk'])

    def post(self, request, *args, **kwargs):
        
        proposal = self.get_object()
        if is_internal(request) or (proposal.proposal_applicant.email_user_id == request.user.id):

            if proposal.application_type.code in (WaitingListApplication.code, AnnualAdmissionApplication.code,):
                self.send_confirmation_mail(proposal, request)

            context = {
                'proposal': proposal,
                'applicant': proposal.applicant_obj,
            }
            return render(request, self.template_name, context)
        else:
            raise serializers.ValidationError("User not authorised to view Proposal details")

    @staticmethod
    def send_confirmation_mail(proposal, request):
        # Send invoice
        to_email_addresses = proposal.applicant_obj.email
        email_data = send_application_submit_confirmation_email(request, proposal, [to_email_addresses, ])


class ApplicationFeeExistingView(APIView):
    #permission_classes=[IsAuthenticated]

    def get_object(self):
        return get_object_or_404(Invoice, reference=self.kwargs['invoice_reference'])

    def get(self, request, *args, **kwargs):

        if not bool(request.user and request.user.is_authenticated):
            return HttpResponseRedirect("/sso/auth_local?next={}".format(request.build_absolute_uri()))

        invoice = self.get_object()
        logger.info(f'Getting payment screen for the future invoice: [{invoice}] ...')

        if is_internal(request) or invoice.owner.id == request.user.id:
            application_fee = ApplicationFee.objects.filter(invoice_reference=invoice.reference).last()
            proposal = application_fee.proposal
            if not proposal:
                raise serializers.ValidationError("Fee proposal does not exist")
            if proposal and proposal.processing_status == "expired":
                raise serializers.ValidationError("The application has expired")

            if get_invoice_payment_status(invoice.id) in ['paid', 'over_paid',]:
                return redirect('application_fee_already_paid', proposal_pk=application_fee.proposal.id)

            try:
                with transaction.atomic():
                    db_processes = {
                        'for_existing_invoice': True,
                        'fee_item_application_fee_ids': [],
                    }
                    fee_item_application_fees = FeeItemApplicationFee.objects.filter(application_fee=application_fee)
                    for fee_item_application_fee in fee_item_application_fees:
                        db_processes['fee_item_application_fee_ids'].append(fee_item_application_fee.id)

                    new_fee_calculation = FeeCalculation.objects.create(uuid=application_fee.uuid, data=db_processes)

                    return_url = request.build_absolute_uri(reverse('fee_success', kwargs={"uuid": application_fee.uuid}))
                    fallback_url = request.build_absolute_uri(reverse("external"))
                    payment_session = ledger_api_client.utils.generate_payment_session(request, invoice.reference, return_url, fallback_url)

                    request.session["payment_pk"] = proposal.pk
                    request.session["payment_model"] = "proposal"
                    return HttpResponseRedirect(payment_session['payment_url'])


            except Exception as e:
                logger.error('Error Creating Application Fee: {}'.format(e))
                raise
        else:
            raise serializers.ValidationError("User not authorised to pay for application")


class StickerReplacementFeeView(TemplateView):
    permission_classes=[IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.POST.get('data')
        data = json.loads(data)
        ids = data['sticker_action_detail_ids']

        sticker_action_fee = StickerActionFee.objects.create(created_by=request.user.id, payment_type=StickerActionFee.PAYMENT_TYPE_TEMPORARY)
        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))

        try:
            with transaction.atomic():
                sticker_action_details = StickerActionDetail.objects.filter(id__in=ids)
                sticker_action_details.update(sticker_action_fee=sticker_action_fee)

                target_datetime_str = current_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')
                application_type = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_REPLACEMENT_STICKER['code'])
                fee_item = FeeItemStickerReplacement.get_fee_item_by_date(current_datetime.date())

                lines = []
                applicant = None
                approval = None
                for sticker_action_detail in sticker_action_details:
                    if settings.ROUND_FEE_ITEMS:
                        total_amount = 0 if sticker_action_detail.waive_the_fee else round(float(fee_item.amount))
                        total_amount_excl_tax = 0 if sticker_action_detail.waive_the_fee else round(float(ledger_api_client.utils.calculate_excl_gst(fee_item.amount))) if fee_item.incur_gst else round(float(fee_item.amount))
                    else:
                        total_amount = 0 if sticker_action_detail.waive_the_fee else fee_item.amount
                        total_amount_excl_tax = 0 if sticker_action_detail.waive_the_fee else ledger_api_client.utils.calculate_excl_gst(fee_item.amount) if fee_item.incur_gst else fee_item.amount

                    line = {
                        'ledger_description': 'Sticker Replacement Fee, sticker: {} @{}'.format(sticker_action_detail.sticker, target_datetime_str),
                        'oracle_code': application_type.get_oracle_code_by_date(current_datetime.date()),
                        'price_incl_tax': total_amount,
                        'price_excl_tax': total_amount_excl_tax,
                        'quantity': 1,
                    }
                    if not applicant and sticker_action_detail and sticker_action_detail.sticker and sticker_action_detail.sticker.approval:
                        applicant = sticker_action_detail.sticker.approval.applicant_obj
                        approval = sticker_action_detail.sticker.approval
                    lines.append(line)


                if is_internal(request) or (applicant and applicant.id == request.user.id): 
                    checkout_response = checkout(
                        request,
                        applicant,
                        lines,
                        return_url=request.build_absolute_uri(reverse('sticker_replacement_fee_success', kwargs={"uuid": sticker_action_fee.uuid})),
                        return_preload_url=settings.MOORING_LICENSING_EXTERNAL_URL + reverse("sticker_replacement_fee_success_preload", kwargs={"uuid": sticker_action_fee.uuid}),
                        booking_reference=approval.lodgement_number if approval else "NoApproval", #TODO adjust handling for when DCV stickers are supported
                        invoice_text='{}'.format(application_type.description),
                    )

                    request.session["payment_pk"] = sticker_action_detail.pk
                    request.session["payment_model"] = "sticker"

                    logger.info('{} built payment line item(s) {} for Sticker Replacement Fee and handing over to payment gateway'.format('User {} with id {}'.format(request.user.get_full_name(), request.user.id), sticker_action_fee))
                    return checkout_response
                else:
                    raise serializers.ValidationError("User not authorised to pay for sticker replacement")        

        except Exception as e:
            logger.error('Error handling StickerActionFee: {}'.format(e))
            if sticker_action_fee:
                sticker_action_fee.delete()
            err_msg = 'Failed to create invoice'
            raise serializers.ValidationError(err_msg)


class StickerReplacementFeeSuccessViewPreload(APIView):

    def get(self, request, uuid, format=None):
        logger.info(f'{StickerReplacementFeeSuccessViewPreload.__name__} get method is called.')
        error_message = ""
        try:
            with transaction.atomic():
                if uuid:
                    if not StickerActionFee.objects.filter(uuid=uuid).exists():
                        logger.info(f'StickerActionFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                        return redirect(reverse('external'))
                    else:
                        logger.info(f'StickerActionFee with uuid: {uuid} exists.')
                    sticker_action_fee = StickerActionFee.objects.get(uuid=uuid)
                    sticker_action_details = sticker_action_fee.sticker_action_details

                    invoice_reference = request.GET.get("invoice", "")
                    logger.info(f"Invoice reference: {invoice_reference} and uuid: {uuid}.",)
                    if not Invoice.objects.filter(reference=invoice_reference).exists():
                        logger.info(f'Invoice with invoice_reference: {invoice_reference} does not exist.  Redirecting user to dashboard page.')
                        return redirect(reverse('external'))
                    else:
                        logger.info(f'Invoice with invoice_reference: {invoice_reference} exist.')
                    invoice = Invoice.objects.get(reference=invoice_reference)

                    sticker_action_fee.invoice_reference = invoice.reference
                    sticker_action_fee.save()
                    
                    if sticker_action_fee.payment_type == StickerActionFee.PAYMENT_TYPE_TEMPORARY:

                        #check if payment has been complete
                        invoice_payment_status = get_invoice_payment_status(invoice.id)
                        if not invoice_payment_status in ('paid', 'over_paid',):
                            raise serializers.ValidationError("Invoice has not been fully paid. Invoice: {invoice_reference}")

                        sticker_action_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                        sticker_action_fee.expiry_time = None
                        sticker_action_fee.save() 

                        old_sticker_numbers = []
                        for sticker_action_detail in sticker_action_details.all():
                            if sticker_action_detail.sticker:
                                old_sticker = sticker_action_detail.sticker
                                new_sticker = old_sticker.request_replacement(Sticker.STICKER_STATUS_LOST, sticker_action_detail)
                                old_sticker_numbers.append(old_sticker.number)
                            else:
                                #If here, no sticker has been specified for replacement
                                #we should try to identify what stickers are missing and replace one of them
                                #if no stickers are missing, raise an error - we should not blindly replace whatever happens to be the latest sticker if it is current
                                if sticker_action_detail.approval:
                                    if sticker_action_detail.change_sticker_address:
                                        # Create replacement sticker
                                        new_sticker = Sticker.objects.create(
                                            approval=sticker_action_detail.approval,
                                            vessel_ownership=sticker_action_detail.approval.current_proposal.vessel_ownership if sticker_action_detail.approval.current_proposal else None,
                                            fee_constructor=sticker_action_detail.approval.current_proposal.fee_constructor if sticker_action_detail.approval.current_proposal else None,
                                            fee_season=sticker_action_detail.approval.latest_applied_season,
                                            postal_address_line1 = sticker_action_detail.new_postal_address_line1,
                                            postal_address_line2 = sticker_action_detail.new_postal_address_line2,
                                            postal_address_line3 = sticker_action_detail.new_postal_address_line3,
                                            postal_address_locality = sticker_action_detail.new_postal_address_locality,
                                            postal_address_state = sticker_action_detail.new_postal_address_state,
                                            postal_address_country = sticker_action_detail.new_postal_address_country,
                                            postal_address_postcode = sticker_action_detail.new_postal_address_postcode,
                                        )
                                        logger.info(f'New Sticker: [{new_sticker}] has been created for the approval with a new postal address: [{sticker_action_detail.approval}].')
                                    else:
                                        # Create replacement sticker
                                        new_sticker = Sticker.objects.create(
                                            approval=sticker_action_detail.approval,
                                            vessel_ownership=sticker_action_detail.approval.current_proposal.vessel_ownership if sticker_action_detail.approval.current_proposal else None,
                                            fee_constructor=sticker_action_detail.approval.current_proposal.fee_constructor if sticker_action_detail.approval.current_proposal else None,
                                            fee_season=sticker_action_detail.approval.latest_applied_season,
                                            postal_address_line1 = sticker_action_detail.approval.postal_address_line1,
                                            postal_address_line2 = sticker_action_detail.approval.postal_address_line2,
                                            postal_address_line3 = sticker_action_detail.approval.postal_address_line3,
                                            postal_address_locality = sticker_action_detail.approval.postal_address_suburb,
                                            postal_address_state = sticker_action_detail.approval.postal_address_state,
                                            postal_address_country = sticker_action_detail.approval.postal_address_country,
                                            postal_address_postcode = sticker_action_detail.approval.postal_address_postcode,
                                        )
                                        logger.info(f'New Sticker: [{new_sticker}] has been created for the approval: [{sticker_action_detail.approval}].')

                                    if new_sticker:
                                        season = sticker_action_detail.approval.latest_applied_season
                                        from mooringlicensing.components.approvals.models import (
                                            MooringLicence, AuthorisedUserPermit, AnnualAdmissionPermit,
                                        )

                                        if type(sticker_action_detail.approval.child_obj) == AnnualAdmissionPermit:
                                            #vessel ownership should be whatever is on the current proposal
                                            #raise an error if there is not one
                                            if not sticker_action_detail.approval.current_proposal or not sticker_action_detail.approval.current_proposal.vessel_ownership or sticker_action_detail.approval.current_proposal.vessel_ownership.end_date:
                                                raise serializers.ValidationError(f"Annual Admission Permit missing valid vessel ownership. If payment has been taken for sticker replacement, it should be refunded. Invoice: {invoice_reference}")
                                            
                                            #identify pre-existing sticker - if it is valid (not lost or cancelled), raise an error (if it is expired, this is not the place to replace it)
                                            if Sticker.objects.filter(fee_season=season).filter(
                                                approval=sticker_action_detail.approval,vessel_ownership=sticker_action_detail.approval.current_proposal.vessel_ownership
                                            ).exclude(id=new_sticker.id).exclude(
                                                status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST,Sticker.STICKER_STATUS_RETURNED]
                                            ).exists():
                                                raise serializers.ValidationError(f"Valid sticker already exists. If payment has been taken for sticker replacement, it should be refunded. Invoice: {invoice_reference}")

                                        elif type(sticker_action_detail.approval.child_obj) == MooringLicence:
                                            #vessel ownership in vessel ownership on approval table
                                            #raise an error is none exist
                                            vooa = sticker_action_detail.approval.child_obj.get_current_vessel_ownership_on_approvals()
                                            if not vooa.exists():
                                                raise serializers.ValidationError(f"Mooring Site Licence missing valid vessel ownership. If payment has been taken for sticker replacement, it should be refunded. Invoice: {invoice_reference}")

                                            #identify if any of those vessel ownerships have non-current stickers (cancelled, lost) or no sticker at all
                                            vessel_ownership_on_approvals = vooa.values_list("vessel_ownership_id",flat=True)
                                            stickers_qs = Sticker.objects.filter(fee_season=season).filter(
                                                approval=sticker_action_detail.approval,vessel_ownership_id__in=list(vessel_ownership_on_approvals)
                                            ).exclude(id=new_sticker.id).exclude(
                                                status=Sticker.STICKER_STATUS_RETURNED #if only returned stickers exist, we want to treat as though no sticker exists (new sticker, but not a replacement)
                                            )
  
                                            vo_missing_stickers = []
                                            for vo in vessel_ownership_on_approvals:
                                                sticker_with_vo = stickers_qs.filter(vessel_ownership_id=vo)
                                                if sticker_with_vo.exists():
                                                    if not sticker_with_vo.exclude(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST]).exists():
                                                        vo_missing_stickers.append(vo)
                                                else:
                                                    vo_missing_stickers.append(vo)
                                            print(vo_missing_stickers)
                                            #if none of the vo's are missing valid stickers, raise an error
                                            if not vo_missing_stickers:
                                                raise serializers.ValidationError(f"All vessels on license already have valid stickers. If payment has been taken for sticker replacement, it should be refunded. Invoice: {invoice_reference}")

                                            #replace the first of them (change the vo on the new sticker)
                                            if new_sticker.vessel_ownership_id != vo_missing_stickers[0]:
                                                new_sticker.vessel_ownership_id = vo_missing_stickers[0]
                                                proposal = Proposal.objects.filter(approval=sticker_action_detail.approval,vessel_ownership_id=vo_missing_stickers[0]).order_by("-id").first()
                                                new_sticker.fee_constructor = proposal.fee_constructor
                                                new_sticker.save()
                                        
                                        elif type(sticker_action_detail.approval.child_obj) == AuthorisedUserPermit:
                                            #vessel ownership should be whatever is on the current proposal
                                            #raise an error if there is not one
                                            if not sticker_action_detail.approval.current_proposal or not sticker_action_detail.approval.current_proposal.vessel_ownership or sticker_action_detail.approval.current_proposal.vessel_ownership.end_date:
                                                raise serializers.ValidationError(f"Authorised User Permit missing valid vessel ownership. If payment has been taken for sticker replacement, it should be refunded. Invoice: {invoice_reference}")

                                            #identify related MOAs with invalid stickers (cancelled, lost) or missing stickers
                                            active_moa_with_invalid_sticker_or_no_sticker = MooringOnApproval.objects.filter(
                                                approval=sticker_action_detail.approval,active=True
                                            ).filter(
                                                Q(sticker__isnull=True)|(Q(sticker__status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST,Sticker.STICKER_STATUS_RETURNED])&Q(sticker__fee_season=season))
                                            ).order_by('-id')
                                            
                                            #if all MOAs have a valid sticker raise an error - AUP stickers cannot be reliably identified for replacement via the current proposal alone 
                                            if not active_moa_with_invalid_sticker_or_no_sticker.exists():
                                                raise serializers.ValidationError(f"Authorised User Permit Moorings all have valid stickers. If payment has been taken for sticker replacement, it should be refunded. Invoice: {invoice_reference}")

                                            #take care of those with (invalid) stickers first
                                            with_stickers = active_moa_with_invalid_sticker_or_no_sticker.filter(sticker__isnull=False).exclude(sticker__status=Sticker.STICKER_STATUS_RETURNED).filter(sticker__fee_season=season)
                                            if with_stickers.exists():
                                                #replace the first of the identified stickers (or lack thereof) - by updating the moas to the new sticker
                                                bad_sticker = with_stickers.first().sticker
                                                update_moas = with_stickers.filter(sticker=bad_sticker)
                                                for moa in update_moas:
                                                    moa.sticker = new_sticker
                                                    moa.save()

                                            #if there are only moas with null stickers, update up to four of them with the new sticker
                                            without_stickers = active_moa_with_invalid_sticker_or_no_sticker.filter(Q(sticker__isnull=True)|~Q(sticker__fee_season=season)|Q(sticker__status=Sticker.STICKER_STATUS_RETURNED))
                                            if not with_stickers.exists() and without_stickers.exists():
                                                for i in range(0,min(4,len(without_stickers))): #NOTE the 4 should really be an env var (other functions would need a refactor as well)
                                                    without_stickers[i].sticker = new_sticker
                                                    without_stickers[i].save()
                            if new_sticker:
                                # Send email with the invoice
                                send_sticker_replacement_email(request, old_sticker_numbers, new_sticker.approval, invoice.reference)
        except Exception as e:
            logger.error(e)
            if error_message:
                logger.error(error_message)
            return redirect(reverse('external'))

        logger.info(
            "Returning status.HTTP_200_OK. Order created successfully.",
        )
        return Response(status=status.HTTP_200_OK)


class StickerReplacementFeeSuccessView(TemplateView):
    permission_classes=[IsAuthenticated]
    template_name = 'mooringlicensing/payments_ml/success_sticker_action_fee.html'
    LAST_STICKER_ACTION_FEE_ID = 'mooringlicensing_last_dcv_admission_invoice'

    def get(self, request, uuid):
        logger.info(f'{StickerReplacementFeeSuccessView.__name__} get method is called.')

        try:
            sticker_action_fee = StickerActionFee.objects.get(uuid=uuid)
            invoice = Invoice.objects.get(reference=sticker_action_fee.invoice_reference)

            if is_internal(request) or invoice.owner.id == request.user.id:
                invoice_url = f'/ledger-toolkit-api/invoice-pdf/{invoice.reference}/'
                applicant = retrieve_email_userro(sticker_action_fee.created_by) if sticker_action_fee.created_by else ''
                context = {
                    'applicant': applicant,
                    'fee_invoice': sticker_action_fee,
                    'invoice': invoice,
                    'invoice_url': invoice_url,
                }
                return render(request, self.template_name, context)
            else:
                raise serializers.ValidationError("User not authorised to view payment details")

        except Exception as e:
            # Should not reach here
            msg = 'Failed to process the payment. {}'.format(str(e))
            logger.error(msg)
            raise serializers.ValidationError('Failed to process the payment.')


class ApplicationFeeView(TemplateView):
    permission_classes=[IsAuthenticated]

    def get_object(self):
        return get_object_or_404(Proposal, id=self.kwargs['proposal_pk'])

    def get(self, request, *args, **kwargs):
        self.template_name = 'mooringlicensing/payments_ml/fee_calculation_error.html'
        context = {
            'error_message': 'invalid fee request',
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        proposal = self.get_object()
        try:
            #check for auto approval
            auto_approved = is_authorised_to_pay_auto_approved(request,proposal)
            if not auto_approved:
                is_authorised_to_modify(request, proposal)
            post_data_pre = request.POST
            post_data = {}
            for i in post_data_pre:
                try:
                    post_data[i] = json.loads(post_data_pre.get(i))
                except ValueError as e:
                    continue

            setattr(request,"data",post_data)
            #auth checked in save_proponent_data func
            save_proponent_data(proposal, request, "submit", auto_approved)

            proposal = self.get_object()
            is_applicant_address_set(proposal)
        except Exception as e:
            self.template_name = 'mooringlicensing/payments_ml/fee_calculation_error.html'
            context = {
                'error_message': str(e),
            }
            return render(request, self.template_name, context)

        application_fee = ApplicationFee.objects.create(proposal=proposal, created_by=request.user.id, payment_type=ApplicationFee.PAYMENT_TYPE_TEMPORARY)
        logger.info(f'ApplicationFee: [{application_fee}] has been created for the Proposal: [{proposal}].')

        try:
            with transaction.atomic():
                try:
                    lines, db_processes_after_success = proposal.child_obj.create_fee_lines()  # Accessed by WL and AA (and auto-approved MLs)
                except Exception as e:
                    self.template_name = 'mooringlicensing/payments_ml/fee_calculation_error.html'
                    context = {
                        'error_message': str(e),
                    }
                    return render(request, self.template_name, context)

                new_fee_calculation = FeeCalculation.objects.create(uuid=application_fee.uuid, data=db_processes_after_success)

                #adjust if there is a previous payment
                previous_application_fees = ApplicationFee.objects.filter(proposal=proposal, cancelled=False).filter(Q(payment_status='paid')|Q(payment_status='over_paid')).order_by("handled_in_preload")
                previous_application_fee = previous_application_fees.last()

                if previous_application_fee:
                    previous_application_fee_items = previous_application_fee.fee_items.all().distinct('id')

                    for previous_application_fee_item in previous_application_fee_items:
                        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))
                        fee_amount = previous_application_fee_item.amount
                        fee_constructor = previous_application_fee_item.fee_constructor

                        if settings.ROUND_FEE_ITEMS:
                            # In debug environment, we want to avoid decimal number which may cause some kind of error.
                            total_amount = 0 - round(float(fee_amount))
                            total_amount_excl_tax = 0 - round(float(ledger_api_client.utils.calculate_excl_gst(fee_amount)) if fee_constructor and fee_constructor.incur_gst else fee_amount)
                        else:
                            total_amount = 0 - float(fee_amount)
                            total_amount_excl_tax = 0 - float(ledger_api_client.utils.calculate_excl_gst(fee_amount) if fee_constructor and fee_constructor.incur_gst else fee_amount)

                        oracle_code = previous_application_fee_item.fee_constructor.application_type.get_oracle_code_by_date(current_datetime.date())
                        if previous_application_fee_item.fee_constructor.application_type.code == 'mla' and proposal.proposal_type.code == 'swap_moorings':
                            target_date = datetime.now(pytz.timezone(settings.TIME_ZONE))
                            oracle_code = OracleCodeItem.objects.filter(date_of_enforcement__lte=target_date, application_type__code='mooring_swap').last().value

                        if total_amount != 0:
                            lines.append({
                                'ledger_description': settings.PREVIOUS_PAYMENT_REASON,
                                'oracle_code': oracle_code,
                                'price_incl_tax': total_amount,
                                'price_excl_tax': total_amount_excl_tax,
                                'quantity': 1,
                            })             

                return_url = request.build_absolute_uri(reverse('fee_success', kwargs={"uuid": application_fee.uuid}))
                return_preload_url = settings.MOORING_LICENSING_EXTERNAL_URL + reverse("ledger-api-success-callback", kwargs={"uuid": application_fee.uuid})
                reference = proposal.previous_application.lodgement_number if proposal.previous_application else proposal.lodgement_number
                checkout_response = checkout(
                    request,
                    proposal.applicant_obj,
                    lines,
                    return_url,
                    return_preload_url,
                    booking_reference=reference,
                    invoice_text='{} ({})'.format(proposal.application_type.description, proposal.proposal_type.description),
                )

                user = proposal.applicant_obj
                request.session["payment_pk"] = proposal.pk
                request.session["payment_model"] = "proposal"

                logger.info('{} built payment line item {} for Application Fee and handing over to payment gateway'.format('User {} with id {}'.format(user.get_full_name(), user.id), proposal.id))
                return checkout_response

        except Exception as e:
            logger.error('Error while checking out for the proposal: {}\n{}'.format(proposal.lodgement_number, str(e)))
            if application_fee:
                application_fee.delete()
                logger.info('ApplicationFee: {} has been deleted'.format(application_fee))
            err_msg = 'Failed to go to checkout'
            raise serializers.ValidationError(err_msg)


class DcvAdmissionFeeSuccessView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_dcv_admission_fee.html'
    LAST_DCV_ADMISSION_FEE_ID = 'mooringlicensing_last_dcv_admission_invoice'

    def get(self, request, uuid, *args, **kwargs):
        logger.info(f'{DcvAdmissionFeeSuccessView.__name__} get method is called.')

        if uuid:
            if not DcvAdmissionFee.objects.filter(uuid=uuid).exists():
                logger.info(f'DcvAdmissionFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'DcvAdmissionFee with uuid: {uuid} exists.')
            dcv_admission_fee = DcvAdmissionFee.objects.get(uuid=uuid)
            dcv_admission = dcv_admission_fee.dcv_admission
            invoice_url = f'/ledger-toolkit-api/invoice-pdf/{dcv_admission_fee.invoice_reference}/'
            context = {
                'dcv_admission': dcv_admission,
                'applicant': dcv_admission.applicant_obj,
                'fee_invoice': dcv_admission_fee,
                'invoice_url': invoice_url,
                'admission_urls': dcv_admission.get_admission_urls(),
            }
            return render(request, self.template_name, context)


class DcvAdmissionFeeSuccessViewPreload(APIView):

    @staticmethod
    def adjust_db_operations(dcv_admission, db_operations):
        dcv_admission.lodgement_datetime = dateutil.parser.parse(db_operations['datetime_for_calculating_fee'])
        dcv_admission.status = DcvAdmission.DCV_ADMISSION_STATUS_PAID
        dcv_admission.save()

    def get(self, request, uuid, format=None):
        logger.info(f'{DcvAdmissionFeeSuccessViewPreload.__name__} get method is called.')

        if uuid:
            if not DcvAdmissionFee.objects.filter(uuid=uuid).exists():
                logger.info(f'DcvAdmissionFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'DcvAdmissionFee with uuid: {uuid} exists.')
            dcv_admission_fee = DcvAdmissionFee.objects.get(uuid=uuid)
            dcv_admission = dcv_admission_fee.dcv_admission

            invoice_reference = request.GET.get("invoice", "")
            logger.info(f"Invoice reference: {invoice_reference} and uuid: {uuid}.",)
            if not Invoice.objects.filter(reference=invoice_reference).exists():
                logger.info(f'Invoice with invoice_reference: {invoice_reference} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'Invoice with invoice_reference: {invoice_reference} exist.')
            invoice = Invoice.objects.get(reference=invoice_reference)

            if not FeeCalculation.objects.filter(uuid=uuid).exists():
                logger.info(f'FeeCalculation with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'FeeCalculation with uuid: {uuid} exist.')
            fee_calculation = FeeCalculation.objects.get(uuid=uuid)
            db_operations = fee_calculation.data
            logger.info(dcv_admission_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY)
            if dcv_admission_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY:
                if invoice.system not in [LEDGER_SYSTEM_ID, ]:
                    logger.error('{} tried paying an dcv_admission fee with an invoice from another system with reference number {}'.format('User {} with id {}'.format(dcv_admission.applicant_obj.get_full_name(), dcv_admission.applicant_obj.id) if dcv_admission.applicant else 'Anonymous user'))
                    return redirect('external-dcv_admission-detail', args=(dcv_admission.id,))

                dcv_admission_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                dcv_admission_fee.expiry_time = None

                if 'fee_item_ids' in db_operations:
                    for item_id in db_operations['fee_item_ids']:
                        fee_item = FeeItem.objects.get(id=item_id)
                        dcv_admission_fee.fee_items.add(fee_item)

                if dcv_admission and get_invoice_payment_status(invoice.id) in ('paid', 'over_paid',):
                    self.adjust_db_operations(dcv_admission, db_operations)
                    dcv_admission.generate_dcv_admission_doc()
                else:
                    logger.error('Invoice payment status is {}'.format(get_invoice_payment_status(invoice.id)))
                    raise

                dcv_admission_fee.invoice_reference = invoice_reference
                dcv_admission_fee.save()

                email = send_dcv_admission_mail(dcv_admission, invoice, request)
            logger.info(
                "Returning status.HTTP_200_OK. Order created successfully.",
            )
            return Response(status=status.HTTP_200_OK)


class DcvPermitFeeSuccessView(TemplateView):
    permission_classes=[IsAuthenticated]
    template_name = 'mooringlicensing/payments_ml/success_dcv_permit_fee.html'
    LAST_DCV_PERMIT_FEE_ID = 'mooringlicensing_last_dcv_permit_invoice'

    def get(self, request, uuid, *args, **kwargs):
        logger.info(f'{DcvPermitFeeSuccessView.__name__} get method is called.')

        if uuid:
            if not DcvPermitFee.objects.filter(uuid=uuid).exists():
                logger.info(f'DcvPermitFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'DcvPermitFee with uuid: {uuid} exists.')
            dcv_permit_fee = DcvPermitFee.objects.get(uuid=uuid)

            dcv_permit = dcv_permit_fee.dcv_permit

            invoice_url = f'/ledger-toolkit-api/invoice-pdf/{dcv_permit_fee.invoice_reference}/'

            context = {
                'dcv_permit': dcv_permit,
                'applicant': dcv_permit.applicant_obj,
                'fee_invoice': dcv_permit_fee,
                'invoice_url': invoice_url,
            }
            return render(request, self.template_name, context)


class DcvPermitFeeSuccessViewPreload(APIView):

    @staticmethod
    def adjust_db_operations(dcv_permit, db_operations):
        dcv_permit.start_date = datetime.datetime.strptime(db_operations['season_start_date'], '%Y-%m-%d').date()
        dcv_permit.end_date = datetime.datetime.strptime(db_operations['season_end_date'], '%Y-%m-%d').date()
        dcv_permit.lodgement_datetime = dateutil.parser.parse(db_operations['datetime_for_calculating_fee'])
        dcv_permit.save()

    def get(self, request, uuid, format=None):
        logger.info(f'{DcvPermitFeeSuccessViewPreload.__name__} get method is called.')

        if uuid:
            if not DcvPermitFee.objects.filter(uuid=uuid).exists():
                logger.info(f'DcvPermitFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'DcvPermitFee with uuid: {uuid} exists.')
            dcv_permit_fee = DcvPermitFee.objects.get(uuid=uuid)

            invoice_reference = request.GET.get("invoice", "")
            logger.info(f"Invoice reference: {invoice_reference} and uuid: {uuid}.",)
            if not Invoice.objects.filter(reference=invoice_reference).exists():
                logger.info(f'Invoice with invoice_reference: {invoice_reference} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'Invoice with invoice_reference: {invoice_reference} exist.')
            invoice = Invoice.objects.get(reference=invoice_reference)

            if not FeeCalculation.objects.filter(uuid=uuid).exists():
                logger.info(f'FeeCalculation with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'FeeCalculation with uuid: {uuid} exist.')
            fee_calculation = FeeCalculation.objects.get(uuid=uuid)
            db_operations = fee_calculation.data

            fee_item = FeeItem.objects.get(id=db_operations['fee_item_id'])
            try:
                fee_item_additional = FeeItem.objects.get(id=db_operations['fee_item_additional_id'])
            except:
                fee_item_additional = None

            # Update the application_fee object
            dcv_permit = dcv_permit_fee.dcv_permit
            dcv_permit.status = DcvPermit.DCV_PERMIT_STATUS_CURRENT
            dcv_permit.save()
            dcv_permit_fee.invoice_reference = invoice_reference
            dcv_permit_fee.save()
            dcv_permit_fee.fee_items.add(fee_item)
            if fee_item_additional:
                dcv_permit_fee.fee_items.add(fee_item_additional)

            if dcv_permit_fee.payment_type == DcvPermitFee.PAYMENT_TYPE_TEMPORARY:

                dcv_permit_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                dcv_permit_fee.expiry_time = None

                if dcv_permit and get_invoice_payment_status(invoice.id):
                    self.adjust_db_operations(dcv_permit, db_operations)
                    dcv_permit.generate_dcv_permit_doc()
                else:
                    logger.error('Invoice payment status is {}'.format(get_invoice_payment_status(invoice.id)))
                    raise

                dcv_permit_fee.save()

                send_dcv_permit_mail(dcv_permit, invoice, request)

            logger.info(
                "Returning status.HTTP_200_OK. Order created successfully.",
            )
            return Response(status=status.HTTP_200_OK)


class ApplicationFeeAlreadyPaid(TemplateView):
    permission_classes=[IsAuthenticated]
    template_name = 'mooringlicensing/payments_ml/application_fee_already_paid.html'

    def get(self, request, *args, **kwargs):
        proposal = get_object_or_404(Proposal, id=self.kwargs['proposal_pk'])
        if is_internal(request) or (proposal.proposal_applicant.email_user_id == request.user.id):
            application_fee = proposal.get_main_application_fee()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)

            context = {
                'proposal': proposal,
                'applicant': proposal.applicant_obj,
                'application_fee': application_fee,
                'invoice': invoice,
            }
            return render(request, self.template_name, context)
        else:
            raise serializers.ValidationError("User not authorised to view proposal details")


class ApplicationFeeSuccessViewPreload(APIView):
    
    def get(self, request, uuid, format=None):
        logger.info(f'{ApplicationFeeSuccessViewPreload.__name__} get method is called.')
        with transaction.atomic(): #will prevent handled_in_preload being saved if an error occurs
            if uuid:
                if not ApplicationFee.objects.filter(uuid=uuid).exists():
                    logger.info(f'ApplicationFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                    return redirect(reverse('external'))
                else:
                    logger.info(f'ApplicationFee with uuid: {uuid} exist.')
                application_fee = ApplicationFee.objects.get(uuid=uuid)

                #NOTE should prevent some instances of repeat request issues, but not enough on its own
                if application_fee.handled_in_preload:
                    logger.info(f'ApplicationFee already handled in preload.')
                    return Response(status=status.HTTP_200_OK)

                # invoice_reference is set in the URL when normal invoice,
                # invoice_reference is not set in the URL when future invoice, but it is set in the application_fee on creation.
                invoice_reference = request.GET.get("invoice", "")
                invoice_reference = application_fee.invoice_reference if not invoice_reference else invoice_reference
                logger.info(f"Invoice reference: {invoice_reference} and uuid: {uuid}.",)
                if not Invoice.objects.filter(reference=invoice_reference).exists():
                    logger.info(f'Invoice with invoice_reference: {invoice_reference} does not exist.  Redirecting user to dashboard page.')
                    return redirect(reverse('external'))
                else:
                    logger.info(f'Invoice with invoice_reference: {invoice_reference} exist.')
                invoice = Invoice.objects.get(reference=invoice_reference)

                if not FeeCalculation.objects.filter(uuid=uuid).exists():
                    logger.info(f'FeeCalculation with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                    return redirect(reverse('external'))
                else:
                    logger.info(f'FeeCalculation with uuid: {uuid} exist.')
                fee_calculation = FeeCalculation.objects.order_by("id").filter(uuid=uuid).last()

                db_operations = fee_calculation.data
                proposal = application_fee.proposal

                
                #NOTE first changes made here fee item application fees are updated or created here
                #check application fee again - if is already has a preload return 200
                check_application_fee = ApplicationFee.objects.get(uuid=uuid)
                if check_application_fee.handled_in_preload:
                    logger.info(f'ApplicationFee already handled in preload.')
                    return Response(status=status.HTTP_200_OK)

                if 'for_existing_invoice' in db_operations and db_operations['for_existing_invoice']:
                    # For existing invoices, fee_item_application_fee.amount_paid should be updated, once paid
                    for idx in db_operations['fee_item_application_fee_ids']:
                        fee_item_application_fee = FeeItemApplicationFee.objects.get(id=int(idx))
                        fee_item_application_fee.amount_paid = fee_item_application_fee.amount_to_be_paid
                        fee_item_application_fee.save()
                else:
                    # Update the application_fee object
                    # For the AUA and MLA's new/amendment application, the application_fee already has relations to fee_item(s) created after creating lines.
                    # In that case, there are no 'fee_item_id' and/or 'fee_item_additional_id' keys in the db_operations
                    if 'fee_item_id' in db_operations:
                        fee_items = FeeItem.objects.filter(id=db_operations['fee_item_id'])
                        if fee_items:
                            amount_paid = None
                            amount_to_be_paid = None
                            if 'fee_amount_adjusted' in db_operations:
                                # Because of business rules, fee_item.amount is not always the same as the actual amount paid.
                                # Therefore we want to store the amount paid too as well as fee_item.
                                fee_amount_adjusted = db_operations['fee_amount_adjusted']
                                amount_to_be_paid = Decimal(fee_amount_adjusted)
                                amount_paid = amount_to_be_paid
                                fee_item = fee_items.first()
                            fee_item_application_fee = FeeItemApplicationFee.objects.create(
                                fee_item=fee_item,
                                application_fee=application_fee,
                                amount_to_be_paid=amount_to_be_paid,
                                amount_paid=amount_paid,
                            )
                            logger.info(f'FeeItemApplicationFee: [{fee_item_application_fee}] created.')
                    if isinstance(db_operations, list):
                        # This is used for AU/ML's auto renewal
                        for item in db_operations:
                            fee_item = FeeItem.objects.get(id=item['fee_item_id'])
                            fee_amount_adjusted = item['fee_amount_adjusted']
                            amount_to_be_paid = Decimal(fee_amount_adjusted)
                            amount_paid = amount_to_be_paid

                            fee_item_application_fee = FeeItemApplicationFee.objects.create(
                                fee_item=fee_item,
                                application_fee=application_fee,
                                amount_to_be_paid=amount_to_be_paid,
                                amount_paid=amount_paid,
                            )
                            logger.info(f'FeeItemApplicationFee: [{fee_item_application_fee}] has been created.')

                application_fee.invoice_reference = invoice_reference
                application_fee.handled_in_preload = datetime.datetime.now()

                #get invoice properties
                inv_props = utils.get_invoice_properties(invoice.id)

                #record cost and payment status in ApplicationFee model
                if 'data' in inv_props and 'invoice' in inv_props['data']:
                    payment_status = inv_props['data']['invoice']["payment_status"] if "payment_status" in inv_props['data']['invoice'] else ""
                    amount = inv_props['data']['invoice']['amount'] if "amount" in inv_props['data']['invoice'] else ""

                    previous_application_fees = ApplicationFee.objects.filter(proposal=proposal, cancelled=False).filter(Q(payment_status='paid')|Q(payment_status='over_paid')).order_by("handled_in_preload")
                    previous_application_fee_cost = previous_application_fees.last().cost if previous_application_fees.last() else 0.0

                    application_fee.payment_status = payment_status
                    application_fee.cost = float(amount) + float(previous_application_fee_cost)

                #prior to saving application_fee for the first time, check if a fee already exists - if it does return an error
                check_application_fee = ApplicationFee.objects.get(uuid=uuid)
                if check_application_fee.handled_in_preload:
                    logger.error(f'ApplicationFee already handled in preload. Returning error.')
                    raise serializers.ValidationError("Application already handled in preload")
                #NOTE first point where application fee is save with handled_in_preload is set
                application_fee.save()

                if application_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY:
                    try:
                        inv = Invoice.objects.get(reference=invoice_reference)
                    except Invoice.DoesNotExist:
                        logger.error('{} tried paying an application fee with an incorrect invoice'.format('User {} with id {}'.format(proposal.applicant_obj.get_full_name(), proposal.applicant_obj.id) if proposal.submitter else 'An anonymous user'))
                        return redirect('external-proposal-detail', args=(proposal.id,))
                    
                    if inv.system not in [LEDGER_SYSTEM_ID, ]:
                        logger.error('{} tried paying an application fee with an invoice from another system with reference number {}'.format('User {} with id {}'.format(proposal.applicant_obj.get_full_name(), proposal.applicant_obj.id) if proposal.submitter else 'An anonymous user',inv.reference))
                        return redirect('external-proposal-detail', args=(proposal.id,))

                    application_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                    application_fee.expiry_time = None

                    invoice_payment_status = get_invoice_payment_status(inv.id)
                    if proposal and invoice_payment_status in ('paid', 'over_paid',):
                        logger.info('The fee for the proposal: {} has been fully paid'.format(proposal.lodgement_number))

                        if proposal.application_type.code in (AuthorisedUserApplication.code, MooringLicenceApplication.code):
                            # For AUA or MLA, as payment has been done, create approval
                            proposal.child_obj.update_or_create_approval(datetime.datetime.now(pytz.timezone(TIME_ZONE)), request)
                        else:
                            # When WLA / AAA
                            if proposal.application_type.code in [WaitingListApplication.code, AnnualAdmissionApplication.code]:
                                proposal.lodgement_date = datetime.datetime.now(pytz.timezone(TIME_ZONE))
                                proposal.log_user_action(ProposalUserAction.ACTION_LODGE_APPLICATION.format(proposal.lodgement_number), request)

                                proposal.child_obj.send_emails_after_payment_success(request)
                                proposal.save()

                            proposal.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
                            proposal.save()
                            logger.info(f'Processing status: [{Proposal.PROCESSING_STATUS_WITH_ASSESSOR}] has been set to the proposal: [{proposal}]')

                    else:
                        msg = 'Invoice: {} payment status is {}.  It should be either paid or over_paid'.format(invoice.reference, get_invoice_payment_status(invoice.id))
                        logger.error(msg)
                        raise Exception(msg)

                    application_fee.handled_in_preload = datetime.datetime.now()
                    application_fee.save()

                logger.info(
                    "Returning status.HTTP_200_OK. Order created successfully.",
                )

            return Response(status=status.HTTP_200_OK)


class ApplicationFeeSuccessView(TemplateView):
    permission_classes=[IsAuthenticated]
    template_name = 'mooringlicensing/payments_ml/success_application_fee.html'
    LAST_APPLICATION_FEE_ID = 'mooringlicensing_last_app_invoice'

    def get(self, request, uuid, *args, **kwargs):
        logger.info(f'{ApplicationFeeSuccessView.__name__} get method is called.')

        try:
            application_fee = ApplicationFee.objects.get(uuid=uuid)
            proposal = application_fee.proposal
            applicant = proposal.applicant_obj

            if (is_internal(request) or applicant.id == request.user.id):
                if type(proposal.child_obj) in [WaitingListApplication, AnnualAdmissionApplication]:
                    if proposal.auto_approve:
                        proposal.final_approval_for_WLA_AAA(request, details={})

                proposal.refresh_from_db()

                #update FeeItemApplicationFee with vessel details
                fee_item_application_fees = FeeItemApplicationFee.objects.filter(application_fee=application_fee)
                fee_item_application_fees.update(vessel_details=proposal.vessel_details)

                wla_or_aaa = True if proposal.application_type.code in [WaitingListApplication.code, AnnualAdmissionApplication.code,] else False
                invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
                invoice_url = f'/ledger-toolkit-api/invoice-pdf/{invoice.reference}/'
                context = {
                    'proposal': proposal,
                    'applicant': applicant,
                    'fee_invoice': application_fee,
                    'is_wla_or_aaa': wla_or_aaa,
                    'invoice': invoice,
                    'invoice_url': invoice_url,
                }
                return render(request, self.template_name, context)
            else:
                raise serializers.ValidationError("User not authorised to view Proposal details")

        except Exception as e:
            # Should not reach here
            msg = f'Failed to process the payment. {str(e)}'
            logger.error(msg)
            logger.error('Check if the preload_url is configured correctly.')
            raise Exception(msg)


class DcvAdmissionPDFView(View):
    permission_classes=[IsAuthenticated]
    def get(self, request, *args, **kwargs):
        try:
            dcv_admission = get_object_or_404(DcvAdmission, id=self.kwargs['id'])

            #even though it can be created without auth, this view should still be restricted
            if (is_internal(request) or dcv_admission.applicant == request.user.id):
                response = HttpResponse(content_type='application/pdf')
                if dcv_admission.dcv_admission_documents.count() < 1:
                    logger.warning('DcvAdmission: {} does not have any admission document.'.format(dcv_admission))
                    return response
                elif dcv_admission.dcv_admission_documents.count() == 1:
                    response.write(dcv_admission.dcv_admission_documents.first()._file.read())
                    return response
                else:
                    logger.warning('DcvAdmission: {} has more than one admissions.'.format(dcv_admission))
                    return response
            else:
                raise serializers.ValidationError("User not authorised to view DCV Admission Document")
        except DcvAdmission.DoesNotExist:
            raise
        except Exception as e:
            logger.error('Error accessing the DcvAdmission :{}'.format(e))
            raise


class DcvPermitPDFView(View):
    permission_classes=[IsAuthenticated]
    def get(self, request, *args, **kwargs):
        try:
            dcv_permit = get_object_or_404(DcvPermit, id=self.kwargs['id'])

            if (is_internal(request) or dcv_permit.applicant == request.user.id):
                response = HttpResponse(content_type='application/pdf')
                if dcv_permit.dcv_permit_documents.count() < 1:
                    logger.warning('DcvPermit: {} does not have any permit document.'.format(dcv_permit))
                    return response
                elif dcv_permit.dcv_permit_documents.count() == 1:
                    response.write(dcv_permit.dcv_permit_documents.first()._file.read())
                    return response
                else:
                    logger.warning('DcvPermit: {} has more than one permits.'.format(dcv_permit))
                    return response
            else:
                raise serializers.ValidationError("User not authorised to view DCV Permit Document")
        except DcvPermit.DoesNotExist:
            raise
        except Exception as e:
            logger.error('Error accessing the DcvPermit :{}'.format(e))
            raise