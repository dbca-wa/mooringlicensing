from io import BytesIO
from ledger.settings_base import TIME_ZONE
from django.utils import timezone

import requests
from requests.auth import HTTPBasicAuth
import json
import pytz
from django.conf import settings
from django.db import connection, transaction

from mooringlicensing.components.approvals.models import Sticker, AnnualAdmissionPermit, AuthorisedUserPermit, \
    MooringLicence, Approval, ApprovalHistory
from mooringlicensing.components.approvals.serializers import ListApprovalSerializer
from mooringlicensing.components.proposals.email import send_sticker_printing_batch_email
from mooringlicensing.components.proposals.models import (
        MooringBay, 
        Mooring,
        StickerPrintingBatch
)
from mooringlicensing.components.main.decorators import basic_exception_handler, query_debugger
from rest_framework import serializers
from openpyxl import Workbook
from copy import deepcopy
import logging
logger = logging.getLogger('mooringlicensing')

def belongs_to(user, group_name):
    """
    Check if the user belongs to the given group.
    :param user:
    :param group_name:
    :return:
    """
    return user.groups.filter(name=group_name).exists()


def is_payment_officer(user):
    return user.is_authenticated() and (belongs_to(user, settings.GROUP_MOORING_LICENSING_PAYMENT_OFFICER) or user.is_superuser)


def to_local_tz(_date):
    local_tz = pytz.timezone(settings.TIME_ZONE)
    return _date.astimezone(local_tz)


def check_db_connection():
    """  check connection to DB exists, connect if no connection exists """
    try:
        if not connection.is_usable():
            connection.connect()
    except Exception as e:
        connection.connect()

def get_bookings(booking_date, rego_no=None, mooring_id=None):
    url = settings.MOORING_BOOKINGS_API_URL + "bookings/" + settings.MOORING_BOOKINGS_API_KEY + '/' 
    myobj = {
            'date': booking_date,
            }
    if rego_no:
        myobj.update({'rego_no': rego_no})
    if mooring_id:
        myobj.update({'mooring_id': mooring_id})
    res = requests.post(url, data=myobj)
    res.raise_for_status()
    data = res.json().get('data')
    updated_data = []
    # phone number
    for booking in data:
        customer_phone_number = ''
        if booking.get("booking_phone_number"):
            customer_phone_number = booking.get("booking_phone_number")
        elif booking.get("customer_account_phone_number"):
            customer_phone_number = booking.get("customer_account_phone_number")
        booking.update({"customer_phone_number": customer_phone_number})
        updated_data.append(booking)
    return updated_data

def import_mooring_bookings_data():
    errors = []
    updates = []
    parks_errors, parks_updates = retrieve_marine_parks()
    mooring_errors, mooring_updates = retrieve_mooring_areas()
    errors.extend(parks_errors)
    errors.extend(mooring_errors)
    updates.extend(parks_updates)
    updates.extend(mooring_updates)
    return errors, updates

## Mooring Bookings API interactions
def retrieve_mooring_areas():
    records_updated = []
    try:
        url = settings.MOORING_BOOKINGS_API_URL + "all-mooring/" + settings.MOORING_BOOKINGS_API_KEY
        res = requests.get(url)
        res.raise_for_status()
        data = res.json().get('data')
        #return data
        # update Mooring records
        with transaction.atomic():
            for mooring in data:
                mooring_qs = Mooring.objects.filter(mooring_bookings_id=mooring.get("id"))
                if mooring_qs.count() > 0:
                    mo = mooring_qs[0]
                    orig_mo = deepcopy(mo)
                    mo.mooring_bookings_id=mooring.get("id")
                    mo.name=mooring.get("name")
                    mo.mooring_bay = MooringBay.objects.get(
                        mooring_bookings_id=mooring.get('marine_park_id'), 
                            active=True
                            )
                    mo.vessel_size_limit = mooring.get('vessel_size_limit')
                    mo.vessel_draft_limit = mooring.get('vessel_draft_limit')
                    mo.vessel_beam_limit = mooring.get('vessel_beam_limit')
                    mo.vessel_weight_limit = mooring.get('vessel_weight_limit')
                    mo.mooring_bookings_mooring_specification = mooring.get('mooring_specification')
                    mo.mooring_bookings_bay_id = mooring.get('marine_park_id')
                    mo.save()
                    if orig_mo != mo:
                        records_updated.append(str(mo.name))
                else:
                    mooring = Mooring.objects.create(
                            mooring_bookings_id=mooring.get("id"), 
                            name=mooring.get("name"),
                            mooring_bay = MooringBay.objects.get(
                                mooring_bookings_id=mooring.get('marine_park_id'), 
                                    active=True
                                    ),
                            vessel_size_limit = mooring.get('vessel_size_limit'),
                            vessel_draft_limit = mooring.get('vessel_draft_limit'),
                            vessel_beam_limit = mooring.get('vessel_beam_limit'),
                            vessel_weight_limit = mooring.get('vessel_weight_limit'),
                            mooring_bookings_mooring_specification = mooring.get('mooring_specification'),
                            mooring_bookings_bay_id = mooring.get('marine_park_id')
                            )
                    logger.info("Mooring created: {}".format(str(mooring)))
                    records_updated.append(str(mooring.name))

            logger.info("Moorings updated: {}".format(str(records_updated)))
            # update active status of any MooringBay records not found in api data
            for mooring_obj in Mooring.objects.all():
                if mooring_obj.mooring_bookings_id not in [x.get("id") for x in data]:
                    mooring_obj.active = False
                    mooring_obj.save()
            return [], records_updated

    except Exception as e:
        #raise e
        logger.error('retrieve_mooring_areas() error', exc_info=True)
        # email only prints len() of error list
        return ['check log',], records_updated

def retrieve_marine_parks():
    records_updated = []
    try:
        # CRON (every night?)  Plus management button for manual control.
        url = settings.MOORING_BOOKINGS_API_URL + "marine-parks/" + settings.MOORING_BOOKINGS_API_KEY
        res = requests.get(url)
        res.raise_for_status()
        data = res.json().get('data')
        # update MooringBay records
        with transaction.atomic():
            for bay in data:
                mooring_bay_qs = MooringBay.objects.filter(mooring_bookings_id=bay.get("id"))
                if mooring_bay_qs.count() > 0:
                    mb = mooring_bay_qs[0]
                    if mb.name != bay.get("name"):
                        mb.name=bay.get("name")
                        mb.save()
                        records_updated.append(str(mb.name))
                else:
                    mooring_bay = MooringBay.objects.create(mooring_bookings_id=bay.get("id"), name=bay.get("name"))
                    logger.info("Mooring Bay created: {}".format(str(mooring_bay)))
                    records_updated.append(str(mooring_bay.name))

            # update active status of any MooringBay records not found in api data
            for mooring_bay in MooringBay.objects.all():
                if mooring_bay.mooring_bookings_id not in [x.get("id") for x in data]:
                    mooring_bay.active = False
                    mooring_bay.save()
            return [], records_updated
    except Exception as e:
        logger.error('retrieve_marine_parks() error', exc_info=True)
        return ['check log',], records_updated

def handle_validation_error(e):
    if hasattr(e, 'error_dict'):
        raise serializers.ValidationError(repr(e.error_dict))
    else:
        if hasattr(e, 'message'):
            raise serializers.ValidationError(e.message)
        else:
            raise


def sticker_export():
    logger = logging.getLogger('cron_tasks')
    # TODO: Implement below
    # Note: if the user wants to apply for e.g. three new authorisations,
    # then the user needs to submit three applications. The system will
    # combine them onto one sticker if payment is received on one day
    # (applicant is notified to pay once RIA staff approve the application)
    stickers = Sticker.objects.filter(
        sticker_printing_batch__isnull=True,
        status=Sticker.STICKER_STATUS_READY,
    )

    errors = []
    updates = []
    today = timezone.localtime(timezone.now()).date()

    if stickers.count():
        try:
            wb = Workbook()
            virtual_workbook = BytesIO()
            ws1 = wb.create_sheet(title="Info", index=0)

            ws1.append([
                'Date',
                'First Name',
                'Last Name',
                'Address Line 1',
                'Address Line 2',
                'Suburb',
                'State',
                'Postcode',
                'Sticker Type',
                'Sticker Number',
                'Vessel Registration Number',
                'Moorings',
                'Colour',
                'White info',
            ])
            for sticker in stickers:
                try:
                    moorings = sticker.get_moorings()
                    mooring_names = [mooring.name for mooring in moorings]
                    mooring_names = ', '.join(mooring_names)

                    ws1.append([
                        today.strftime('%d/%m/%Y'),
                        sticker.first_name,
                        sticker.last_name,
                        sticker.postal_address_line1,
                        sticker.postal_address_line2,
                        sticker.postal_address_suburb,
                        sticker.postal_address_state,
                        sticker.postal_address_postcode,
                        sticker.approval.description,
                        sticker.number,
                        sticker.vessel_registration_number,
                        mooring_names,
                        sticker.get_sticker_colour(),
                        sticker.get_white_info(),
                    ])
                    logger.info('Sticker: {} details added to the spreadsheet'.format(sticker.number))
                    updates.append(sticker.number)
                except Exception as e:
                    err_msg = 'Error adding sticker: {} details to spreadsheet.'.format(sticker.number)
                    logger.error('{}\n{}'.format(err_msg, str(e)))
                    errors.append(err_msg)

            wb.save(virtual_workbook)

            batch_obj = StickerPrintingBatch.objects.create()
            filename = 'RIA-{}.xlsx'.format(batch_obj.uploaded_date.astimezone(pytz.timezone(TIME_ZONE)).strftime('%Y%m%d'))
            batch_obj._file.save(filename, virtual_workbook)
            batch_obj.name = filename
            batch_obj.save()
            logger.info('Sticker printing batch file {} generated successfully.'.format(batch_obj.name))

            # Update sticker objects
            stickers.update(
                sticker_printing_batch=batch_obj,  # Keep status 'printing' because we still have to wait for the sticker printed.
            )
        except Exception as e:
            err_msg = 'Error generating the sticker printing batch spreadsheet file for the stickers: {}'.format(', '.join([sticker.number for sticker in stickers]))
            logger.error('{}\n{}'.format(err_msg, str(e)))
            errors.append(err_msg)
    return updates, errors


def email_stickers_document():
    logger = logging.getLogger('cron_tasks')
    updates, errors = [], []

    try:
        batches = StickerPrintingBatch.objects.filter(emailed_datetime__isnull=True)
        if batches.count():
            current_datetime = timezone.localtime(timezone.now())
            send_sticker_printing_batch_email(batches)
            for batch in batches:
                batch.emailed_datetime = current_datetime
                batch.save()
                updates.append(batch.name)

                # Update sticker status
                stickers = Sticker.objects.filter(sticker_printing_batch=batch)
                # stickers.update(status=Sticker.STICKER_STATUS_AWAITING_PRINTING)
                for sticker in stickers:
                    sticker.status=Sticker.STICKER_STATUS_AWAITING_PRINTING
                    sticker.save()
                    if sticker.sticker_to_replace:
                        # new sticker has the old sticker here if it's created for renewal
                        # When this sticker is created for renewal, set 'expiry' status to the old sticker.
                        sticker.sticker_to_replace.status = Sticker.STICKER_STATUS_EXPIRED
                        sticker.sticker_to_replace.save()

                    # Update approval history with this sticker
                    # latest_approval_history = ApprovalHistory.objects.filter(approval=sticker.approval, end_data__isnull=True).order_by('-start_date').first()
                    # latest_approval_history.stickers.add(sticker)

    except Exception as e:
        err_msg = 'Error sending the sticker printing batch spreadsheet file(s): {}'.format(', '.join([batch.name for batch in batches]))
        logger.error('{}\n{}'.format(err_msg, str(e)))
        errors.append(err_msg)

    return updates, errors


## DoT vessel rego check
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_dot_vessel_information(request,json_string):
    DOT_URL=settings.DOT_URL
    paramGET=json_string.replace("\n", "")
    client_ip = get_client_ip(request)
    auth=auth=HTTPBasicAuth(settings.DOT_USERNAME,settings.DOT_PASSWORD)
    r = requests.get(DOT_URL+"?paramGET="+paramGET+"&client_ip="+client_ip, auth=auth)
    return r.text

def export_to_mooring_booking(approval_id):
    try:
        url = settings.MOORING_BOOKINGS_API_URL + "licence-create-update/" + settings.MOORING_BOOKINGS_API_KEY + '/' 
        approval = Approval.objects.get(id=approval_id)
        status = 'active' if approval.status == 'current' else 'cancelled'
        licence_type = None
        if type(approval.child_obj) == MooringLicence:
            licence_type = 1
        elif type(approval.child_obj) == AuthorisedUserPermit:
            licence_type = 2
        elif type(approval.child_obj) == AnnualAdmissionPermit:
            licence_type = 3
        errors = []
        updates = []
        if approval and type(approval.child_obj) in [AnnualAdmissionPermit, AuthorisedUserPermit]:
            myobj = {
                    'vessel_rego': approval.current_proposal.vessel_ownership.vessel.rego_no,
                    'licence_id': approval.id,
                    'licence_type': licence_type,
                    'start_date': approval.start_date.strftime('%Y-%m-%d') if approval.start_date else '',
                    'expiry_date' : approval.expiry_date.strftime('%Y-%m-%d') if approval.expiry_date else '',
                    'status' : status,
                    }
            resp = requests.post(url, data = myobj)
            if not resp or not resp.text:
                print("Server unavailable")
                raise Exception("Server unavailable")
            resp_dict = json.loads(resp.text)
            #logger.info('Export status for approval_id {}: {}'.format(approval_id, resp.text))
            if resp_dict.get("status") == 200:
                updates.append('approval_id: {}, vessel_id: {}'.format(approval.id, approval.current_proposal.vessel_ownership.vessel.id))
                approval.export_to_mooring_booking = False
                approval.save()
            else:
                errors.append('approval_id: {}, vessel_id: {}, error_message: {}'.format(approval.id, approval.current_proposal.vessel_ownership.vessel.id, resp.text))
        elif approval and type(approval.child_obj) == MooringLicence:
            for vessel_ownership in approval.child_obj.vessel_ownership_list:
                myobj = {
                        'vessel_rego': vessel_ownership.vessel.rego_no,
                        'licence_id': approval.id,
                        'licence_type': licence_type,
                        'start_date': approval.start_date.strftime('%Y-%m-%d') if approval.start_date else '',
                        'expiry_date' : approval.expiry_date.strftime('%Y-%m-%d') if approval.expiry_date else '',
                        'status' : status,
                        }
                resp = requests.post(url, data = myobj)
                if not resp or not resp.text:
                    print("Server unavailable")
                    raise Exception("Server unavailable")
                resp_dict = json.loads(resp.text)
                #logger.info('Export status for approval_id {}: {}'.format(approval_id, resp.text))
                if resp_dict.get("status") == 200:
                    updates.append('approval_id: {}, vessel_id: {}'.format(approval.id, vessel_ownership.vessel.id))
                else:
                    errors.append('approval_id: {}, vessel_id: {}, error_message: {}'.format(approval.id, vessel_ownership.vessel.id, resp.text))
            # do not mark mooring licences without vessels as exported
            if not errors and approval.child_obj.vessel_ownership_list:
                approval.export_to_mooring_booking = False
                approval.save()
        return errors, updates
    except Exception as e:
        print(str(e))
        logger.error(str(e))
        raise e

@query_debugger
def test_list_approval_serializer(approval_id):
    approval = Approval.objects.get(id=approval_id)
    serializer = ListApprovalSerializer(approval)
    return serializer.data

