import logging
from _pydecimal import Decimal
from datetime import datetime

import pytz
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
# from ledger.checkout.utils import create_basket_session, create_checkout_session, calculate_excl_gst, use_existing_basket_from_invoice
from ledger_api_client.utils import create_basket_session, create_checkout_session, calculate_excl_gst, use_existing_basket_from_invoice
# from ledger.settings_base import TIME_ZONE
from ledger_api_client.settings_base import *
from mooringlicensing import settings
from mooringlicensing.components.approvals.models import DcvPermit, AgeGroup, AdmissionType
from mooringlicensing.components.main.models import ApplicationType
from mooringlicensing.components.payments_ml.models import ApplicationFee, FeeConstructor, DcvPermitFee, \
    DcvAdmissionFee, StickerActionFee

#test
from mooringlicensing.components.proposals.models import Proposal, AuthorisedUserApplication, MooringLicenceApplication, \
    AnnualAdmissionApplication, ProposalType

logger = logging.getLogger('mooringlicensing')


def checkout(request, email_user, lines, return_url_ns='public_payment_success', return_preload_url_ns='public_payment_success', invoice_text=None, vouchers=[], proxy=False):
    basket_params = {
        'products': lines,
        'vouchers': vouchers,
        'system': settings.PAYMENT_SYSTEM_ID,
        'custom_basket': True,
    }

    basket, basket_hash = create_basket_session(request, basket_params)
    checkout_params = {
        'system': settings.PAYMENT_SYSTEM_ID,
        'fallback_url': request.build_absolute_uri('/'),                                      # 'http://mooring-ria-jm.dbca.wa.gov.au/'
        'return_url': request.build_absolute_uri(reverse(return_url_ns)),          # 'http://mooring-ria-jm.dbca.wa.gov.au/success/'
        'return_preload_url': request.build_absolute_uri(reverse(return_url_ns)),  # 'http://mooring-ria-jm.dbca.wa.gov.au/success/'
        'force_redirect': True,
        'invoice_text': invoice_text,                                                         # 'Reservation for Jawaid Mushtaq from 2019-05-17 to 2019-05-19 at RIA 005'
    }
    if proxy or request.user.is_anonymous():
        checkout_params['basket_owner'] = email_user.id


    create_checkout_session(request, checkout_params)

    response = HttpResponseRedirect(reverse('checkout:index'))
    # inject the current basket into the redirect response cookies
    # or else, anonymous users will be directionless
    response.set_cookie(
        settings.OSCAR_BASKET_COOKIE_OPEN, basket_hash,
        max_age=settings.OSCAR_BASKET_COOKIE_LIFETIME,
        secure=settings.OSCAR_BASKET_COOKIE_SECURE, httponly=True
    )

    return response


def create_fee_lines_for_dcv_admission(dcv_admission, invoice_text=None, vouchers=[], internal=False):
    db_processes_after_success = {}

    target_datetime = datetime.now(pytz.timezone(TIME_ZONE))
    target_date = target_datetime.date()
    target_datetime_str = target_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')

    db_processes_after_success['datetime_for_calculating_fee'] = target_datetime.__str__()

    application_type = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_DCV_ADMISSION['code'])
    vessel_length = 1  # any number greater than 0
    proposal_type = None
    oracle_code = application_type.get_oracle_code_by_date(target_date=target_date)

    line_items = []
    for dcv_admission_arrival in dcv_admission.dcv_admission_arrivals.all():
        fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_date(application_type, dcv_admission_arrival.arrival_date)

        if not fee_constructor:
            raise Exception('FeeConstructor object for the ApplicationType: {} and the Season: {}'.format(application_type, dcv_admission_arrival.arrival_date))

        fee_items = []
        number_of_people_str = []
        total_amount = 0

        for number_of_people in dcv_admission_arrival.numberofpeople_set.all():
            if number_of_people.number:
                # When more than 1 people,
                fee_item = fee_constructor.get_fee_item(vessel_length, proposal_type, dcv_admission_arrival.arrival_date, number_of_people.age_group, number_of_people.admission_type)
                fee_item.number_of_people = number_of_people.number
                fee_items.append(fee_item)
                number_of_people_str.append('[{}-{}: {}]'.format(number_of_people.age_group, number_of_people.admission_type, number_of_people.number))
                total_amount += fee_item.get_absolute_amount() * number_of_people.number

        line_item = {
            'ledger_description': '{} Fee: {} (Arrival: {}, Private: {}, {})'.format(
                fee_constructor.application_type.description,
                dcv_admission.lodgement_number,
                dcv_admission_arrival.arrival_date,
                dcv_admission_arrival.private_visit,
                ', '.join(number_of_people_str),
            ),
            'oracle_code': oracle_code,
            'price_incl_tax': total_amount,
            'price_excl_tax': calculate_excl_gst(total_amount) if fee_constructor.incur_gst else total_amount,
            'quantity': 1,
        }
        line_items.append(line_item)

    logger.info('{}'.format(line_items))

    return line_items, db_processes_after_success


def create_fee_lines(instance, invoice_text=None, vouchers=[], internal=False):
    """ Create the ledger lines - line item for application fee sent to payment system """

    # Any changes to the DB should be made after the success of payment process
    db_processes_after_success = {}

    if isinstance(instance, Proposal):
        application_type = instance.application_type
        vessel_length = instance.vessel_details.vessel_applicable_length
        proposal_type = instance.proposal_type
    elif isinstance(instance, DcvPermit):
        application_type = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_DCV_PERMIT['code'])
        vessel_length = 1  # any number greater than 0
        proposal_type = None

    target_datetime = datetime.now(pytz.timezone(TIME_ZONE))
    target_date = target_datetime.date()
    target_datetime_str = target_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')

    # Retrieve FeeItem object from FeeConstructor object
    if isinstance(instance, Proposal):
        fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_date(application_type, target_date)
        if not fee_constructor:
            # Fees have not been configured for this application type and date
            raise Exception('FeeConstructor object for the ApplicationType: {} not found for the date: {}'.format(application_type, target_date))
    elif isinstance(instance, DcvPermit):
        fee_constructor = FeeConstructor.get_fee_constructor_by_application_type_and_season(application_type, instance.fee_season)
        if not fee_constructor:
            # Fees have not been configured for this application type and date
            raise Exception('FeeConstructor object for the ApplicationType: {} and the Season: {}'.format(application_type, instance.fee_season))
    else:
        raise Exception('Something went wrong when calculating the fee')

    fee_item = fee_constructor.get_fee_item(vessel_length, proposal_type, target_date)

    db_processes_after_success['fee_item_id'] = fee_item.id
    db_processes_after_success['fee_constructor_id'] = fee_constructor.id
    db_processes_after_success['season_start_date'] = fee_constructor.fee_season.start_date.__str__()
    db_processes_after_success['season_end_date'] = fee_constructor.fee_season.end_date.__str__()
    db_processes_after_success['datetime_for_calculating_fee'] = target_datetime.__str__()

    line_items = [
        {
            'ledger_description': '{} Fee: {} (Season: {} to {}) @{}'.format(
                fee_constructor.application_type.description,
                instance.lodgement_number,
                fee_constructor.fee_season.start_date.strftime('%d/%m/%Y'),
                fee_constructor.fee_season.end_date.strftime('%d/%m/%Y'),
                target_datetime_str,
            ),
            # 'oracle_code': application_type.oracle_code,
            'oracle_code': ApplicationType.get_current_oracle_code_by_application(application_type.code),
            'price_incl_tax':  fee_item.amount,
            'price_excl_tax':  calculate_excl_gst(fee_item.amount) if fee_constructor.incur_gst else fee_item.amount,
            'quantity': 1,
        },
    ]

    logger.info('{}'.format(line_items))

    return line_items, db_processes_after_success


def generate_line_item(application_type, fee_amount_adjusted, fee_constructor, instance, target_datetime, v_rego_no=''):
    target_datetime_str = target_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')
    application_type_display = fee_constructor.application_type.description
    application_type_display = application_type_display.replace('Application', '')
    application_type_display = application_type_display.replace('fees', '')
    application_type_display = application_type_display.strip()
    vessel_rego_no = v_rego_no
    if not vessel_rego_no and instance.vessel_details and instance.vessel_details.vessel:
        vessel_rego_no = instance.vessel_details.vessel.rego_no
    if not vessel_rego_no:
        # We want to show something rather than empty string
        vessel_rego_no = 'no vessel'

    proposal_type_text = '{}'.format(instance.proposal_type.description) if hasattr(instance, 'proposal_type') else ''
    return {
        'ledger_description': '{} fee ({}, {}): {} (Season: {} to {}) @{}'.format(
            # fee_constructor.application_type.description,
            application_type_display,
            proposal_type_text,
            vessel_rego_no,
            instance.lodgement_number,
            fee_constructor.fee_season.start_date.strftime('%d/%m/%Y'),
            fee_constructor.fee_season.end_date.strftime('%d/%m/%Y'),
            target_datetime_str,
        ),
        'oracle_code': application_type.get_oracle_code_by_date(target_datetime.date()),
        'price_incl_tax': fee_amount_adjusted,
        'price_excl_tax': calculate_excl_gst(fee_amount_adjusted) if fee_constructor.incur_gst else fee_amount_adjusted,
        'quantity': 1,
    }


NAME_SESSION_APPLICATION_INVOICE = 'mooringlicensing_app_invoice'
NAME_SESSION_DCV_PERMIT_INVOICE = 'mooringlicensing_dcv_permit_invoice'
NAME_SESSION_DCV_ADMISSION_INVOICE = 'mooringlicensing_dcv_admission_invoice'
NAME_SESSION_STICKER_ACTION_INVOICE = 'mooringlicensing_sticker_action_invoice'


def set_session_sticker_action_invoice(session, application_fee):
    """ Application Fee session ID """
    session[NAME_SESSION_STICKER_ACTION_INVOICE] = application_fee.id
    session.modified = True


def get_session_sticker_action_invoice(session):
    """ Application Fee session ID """
    if NAME_SESSION_STICKER_ACTION_INVOICE in session:
        application_fee_id = session[NAME_SESSION_STICKER_ACTION_INVOICE]
    else:
        raise Exception('Application not in Session')

    try:
        return StickerActionFee.objects.get(id=application_fee_id)
    except StickerActionFee.DoesNotExist:
        raise Exception('StickerActionFee not found for id: {}'.format(application_fee_id))


def delete_session_sticker_action_invoice(session):
    """ Application Fee session ID """
    if NAME_SESSION_STICKER_ACTION_INVOICE in session:
        del session[NAME_SESSION_STICKER_ACTION_INVOICE]
        session.modified = True


def set_session_application_invoice(session, application_fee):
    print('in set_session_application_invoice')

    """ Application Fee session ID """
    session[NAME_SESSION_APPLICATION_INVOICE] = application_fee.id
    session.modified = True


class ItemNotSetInSessionException(Exception):
    pass


def get_session_application_invoice(session):
    print('in get_session_application_invoice')

    """ Application Fee session ID """
    if NAME_SESSION_APPLICATION_INVOICE in session:
        application_fee_id = session[NAME_SESSION_APPLICATION_INVOICE]
    else:
        # Reach here when the ApplicationFeeSuccessView is accessed 2nd time.  Which is correct.
        raise ItemNotSetInSessionException('Application not in Session')

    try:
        return ApplicationFee.objects.get(id=application_fee_id)
    except ApplicationFee.DoesNotExist:
        raise


def delete_session_application_invoice(session):
    print('in delete_session_application_invoice')

    """ Application Fee session ID """
    if NAME_SESSION_APPLICATION_INVOICE in session:
        del session[NAME_SESSION_APPLICATION_INVOICE]
        session.modified = True


def set_session_dcv_permit_invoice(session, dcv_permit_fee):
    session[NAME_SESSION_DCV_PERMIT_INVOICE] = dcv_permit_fee.id
    session.modified = True


def get_session_dcv_permit_invoice(session):
    if NAME_SESSION_DCV_PERMIT_INVOICE in session:
        dcv_permit_fee_id = session[NAME_SESSION_DCV_PERMIT_INVOICE]
    else:
        raise Exception('DcvPermit not in Session')

    try:
        return DcvPermitFee.objects.get(id=dcv_permit_fee_id)
    except DcvPermitFee.DoesNotExist:
        raise Exception('DcvPermit not found for application {}'.format(dcv_permit_fee_id))


def delete_session_dcv_permit_invoice(session):
    if NAME_SESSION_DCV_PERMIT_INVOICE in session:
        del session[NAME_SESSION_DCV_PERMIT_INVOICE]
        session.modified = True


def set_session_dcv_admission_invoice(session, dcv_admission_fee):
    session[NAME_SESSION_DCV_ADMISSION_INVOICE] = dcv_admission_fee.id
    session.modified = True


def get_session_dcv_admission_invoice(session):
    if NAME_SESSION_DCV_ADMISSION_INVOICE in session:
        dcv_admission_fee_id = session[NAME_SESSION_DCV_ADMISSION_INVOICE]
    else:
        raise Exception('DcvAdmission not in Session')

    try:
        return DcvAdmissionFee.objects.get(id=dcv_admission_fee_id)
    except DcvAdmissionFee.DoesNotExist:
        raise Exception('DcvAdmission not found for application {}'.format(dcv_admission_fee_id))


def delete_session_dcv_admission_invoice(session):
    if NAME_SESSION_DCV_ADMISSION_INVOICE in session:
        del session[NAME_SESSION_DCV_ADMISSION_INVOICE]
        session.modified = True


def make_serializable(line_items):
    for line in line_items:
        for key in line:
            if isinstance(line[key], Decimal):
                # Convert Decimal to str
                line[key] = str(line[key])
    return line_items


def checkout_existing_invoice(request, invoice, return_url_ns='public_booking_success'):

    basket, basket_hash = use_existing_basket_from_invoice(invoice.reference)
    checkout_params = {
        'system': settings.PAYMENT_SYSTEM_ID,
        'fallback_url': request.build_absolute_uri('/'),
        'return_url': request.build_absolute_uri(reverse(return_url_ns)),
        'return_preload_url': request.build_absolute_uri(reverse(return_url_ns)),
        'force_redirect': True,
        'invoice_text': invoice.text,
    }

    if request.user.is_anonymous():
        # We need to determine the basket owner and set it to the checkout_params to proceed the payment
        application_fee = ApplicationFee.objects.filter(invoice_reference=invoice.reference)
        if application_fee:
            application_fee = application_fee[0]
            # checkout_params['basket_owner'] = application_fee.approval.relevant_applicant_email_user.id
            checkout_params['basket_owner'] = application_fee.proposal.applicant_id
        else:
            # Should not reach here
            # At the moment, there should be only the 'annual rental fee' invoices for anonymous user
            pass

    create_checkout_session(request, checkout_params)

    # use HttpResponse instead of HttpResponseRedirect - HttpResonseRedirect does not pass cookies which is important for ledger to get the correct basket
    response = HttpResponse(
        "<script> window.location='" + reverse('checkout:index') + "';</script> <a href='" + reverse(
            'checkout:index') + "'> Redirecting please wait: " + reverse('checkout:index') + "</a>")

    # inject the current basket into the redirect response cookies
    # or else, anonymous users will be directionless
    response.set_cookie(
        settings.OSCAR_BASKET_COOKIE_OPEN, basket_hash,
        max_age=settings.OSCAR_BASKET_COOKIE_LIFETIME,
        secure=settings.OSCAR_BASKET_COOKIE_SECURE, httponly=True
    )
    return response


def oracle_integration(date,override):
    #system = '0517'
    oracle_codes = oracle_parser(date, settings.PAYMENT_SYSTEM_ID, 'Disturbance Approval System', override=override)

