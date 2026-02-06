import os
from django.core.files.base import ContentFile
import csv
from ledger_api_client.settings_base import TIME_ZONE
from django.utils import timezone
from confy import env
import re

import requests
from requests.auth import HTTPBasicAuth
import json
import pytz
from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Q, F
from mooringlicensing.components.approvals.models import (
    Sticker, AnnualAdmissionPermit, AuthorisedUserPermit, DcvPermitDocument,
    MooringLicence, Approval, WaitingListAllocation,
    ApprovalHistory, DcvPermit, DcvAdmission, Approval, VesselOwnershipOnApproval
)
from mooringlicensing.components.compliances.models import Compliance
from mooringlicensing.components.proposals.email import send_sticker_printing_batch_email
from mooringlicensing.components.proposals.models import (
    MooringBay,
    Mooring,
    StickerPrintingBatch,
    Proposal, VesselDetails, VesselOwnership
)
from mooringlicensing.components.payments_ml.models import ApplicationFee, StickerActionFee

from ledger_api_client.ledger_models import Invoice
from ledger_api_client.managed_models import SystemUser
from rest_framework import serializers
from copy import deepcopy
import logging
from mooringlicensing.settings import MAX_NUM_ROWS_MODEL_EXPORT
from django.db.models import Case, Value, When, CharField, Count, OuterRef, Subquery
from django.contrib.postgres.fields import ArrayField
from django.db.models.functions import Concat, Cast
import csv
import xlsxwriter
import datetime
import uuid
from django.contrib.postgres.aggregates import ArrayAgg
from urllib import parse

from mooringlicensing.settings import (
    PROPOSAL_TYPE_RENEWAL, 
    PROPOSAL_TYPE_NEW,
)

logger = logging.getLogger(__name__)


def is_payment_officer(user):
    from mooringlicensing.helpers import belongs_to
    return user.is_authenticated and (belongs_to(user, settings.GROUP_MOORING_LICENSING_PAYMENT_OFFICER) or user.is_superuser)


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
    try:
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
    except Exception as e:
        logger.error(f'Error raised while getting bookings. Error: [{e}]')
        return []

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

def validate_files(approvals):
    #check if a record file exists or not - if it doesn't then update the table row to reflect that
    if len(approvals) > 0:

        #check if private-media dir exists, if not all pdf files need to be generated    
        private_media_location = settings.PRIVATE_MEDIA_STORAGE_LOCATION
        if not os.path.exists(private_media_location):
            return approvals

        missing_doc_ids = []
        if isinstance(approvals[0], DcvPermit):
            #check dcv dir exists
            if not os.path.exists(os.path.join(private_media_location,'dcv_permit')):
                return approvals

            dcv_with_file_ids = DcvPermitDocument.objects.distinct('dcv_permit_id').values_list("dcv_permit_id",flat=True)
            no_files = list(approvals.exclude(id__in=dcv_with_file_ids).values_list('id', flat=True)) #we will keep these for later
            check_files = approvals.filter(id__in=dcv_with_file_ids) #we will check if the specified files actually exist

            for i in check_files:
                if not os.path.exists(os.path.join(private_media_location,'dcv_permit/{}'.format(i.id))):
                    missing_doc_ids.append(i.id)
            DcvPermitDocument.objects.filter(dcv_permit_id__in=missing_doc_ids).delete()
            generate_pdf_ids = no_files + missing_doc_ids
            return DcvPermit.objects.filter(id__in=generate_pdf_ids)
        else:
            approval_class = approvals[0].__class__
            #check proposal dir exists
            if not os.path.exists(os.path.join(private_media_location,'proposal')):
                return approvals

            no_files = list(approvals.filter(licence_document=None).values_list('id', flat=True)) #we will keep these for later
            check_files = approvals.exclude(licence_document=None) #we will check if the specified files actually exist  

            for i in check_files:
                if not os.path.exists(os.path.join(private_media_location,'proposal/{}/approval_documents'.format(i.current_proposal.id))):
                    missing_doc_ids.append(i.id)
            Approval.objects.filter(id__in=missing_doc_ids).update(licence_document=None)
            generate_pdf_ids = no_files + missing_doc_ids
            return approval_class.objects.filter(id__in=generate_pdf_ids)

    return approvals

def create_pdf_licence(approvals):
    if len(approvals) > 0:
        permit_name = approvals[0].__class__.__name__

        errors = []
        updates = []

        for idx, a in enumerate(approvals):
            try:
                if isinstance(a, DcvPermit) and len(a.dcv_permit_documents.all())==0:
                    a.generate_dcv_permit_doc()
                elif not hasattr(a, 'licence_document') or a.licence_document is None: 
                    a.generate_doc()
                print(f'{idx}, Created PDF for {permit_name}: {a}')
                updates.append(a.lodgement_number)
            except Exception as e:
                errors.append(e)

        return errors, updates
    else:
        return [],[]

def generate_pdf_files():

    errors = []
    updates = []

    ml_qs = MooringLicence.objects.filter(Q(current_proposal__processing_status=Proposal.PROCESSING_STATUS_APPROVED)|Q(current_proposal__processing_status=Proposal.PROCESSING_STATUS_PRINTING_STICKER))
    ml_qs = validate_files(ml_qs)
    ml_e,ml_u = create_pdf_licence(ml_qs)
    errors.append(ml_e)
    updates.append(ml_u)

    aap_qs = AnnualAdmissionPermit.objects.filter(Q(current_proposal__processing_status=Proposal.PROCESSING_STATUS_APPROVED)|Q(current_proposal__processing_status=Proposal.PROCESSING_STATUS_PRINTING_STICKER))
    aap_qs = validate_files(aap_qs)
    aap_e,aap_u = create_pdf_licence(aap_qs)
    errors.append(aap_e)
    updates.append(aap_u)

    aup_qs = AuthorisedUserPermit.objects.filter(Q(current_proposal__processing_status=Proposal.PROCESSING_STATUS_APPROVED)|Q(current_proposal__processing_status=Proposal.PROCESSING_STATUS_PRINTING_STICKER))
    aup_qs = validate_files(aup_qs)
    aup_e,aup_u = create_pdf_licence(aup_qs)
    errors.append(aup_e)
    updates.append(aup_u)

    wla_qs = WaitingListAllocation.objects.filter(Q(current_proposal__processing_status=Proposal.PROCESSING_STATUS_APPROVED)|Q(current_proposal__processing_status=Proposal.PROCESSING_STATUS_PRINTING_STICKER))
    wla_qs = validate_files(wla_qs)
    wla_e,wla_u = create_pdf_licence(wla_qs)
    errors.append(wla_e)
    updates.append(wla_u)

    dcv_qs = DcvPermit.objects.filter(status=DcvPermit.DCV_PERMIT_STATUS_CURRENT)
    dcv_qs = validate_files(dcv_qs)
    dcv_e,dcv_u = create_pdf_licence(dcv_qs)
    errors.append(dcv_e)
    updates.append(dcv_u)

    return errors, updates

## Mooring Bookings API interactions
def retrieve_mooring_areas():
    records_updated = []
    try:
        url = settings.MOORING_BOOKINGS_API_URL + "all-mooring/" + settings.MOORING_BOOKINGS_API_KEY
        res = requests.get(url)
        res.raise_for_status()
        data = res.json().get('data')
        # update Mooring records
        with transaction.atomic():
            for mooring in data:
                # get mooring_group_id from MB admin Mooring Groups, Rottnest Is Auth and store as env var
                if not env('MOORING_GROUP_ID'):
                    raise Exception('You must set MOORING_GROUP_ID env var')
                else:
                    mooring_group_id = env('MOORING_GROUP_ID')

                if mooring.get('mooring_specification') != 2 or mooring_group_id not in mooring.get('mooring_group'):
                    continue
                mooring_qs = Mooring.objects.filter(mooring_bookings_id=mooring.get("id"))
                if mooring_qs.count() > 0:
                    mo = mooring_qs[0]
                    orig_mo = deepcopy(mo)
                    mo.mooring_bookings_id=mooring.get("id")
                    mo.name=mooring.get("name")
                    try:
                        mo.mooring_bay = MooringBay.objects.get(
                            mooring_bookings_id=mooring.get('marine_park_id'), 
                            active=True
                        )
                    except:
                        continue
                    mo.vessel_size_limit = mooring.get('vessel_size_limit')
                    mo.vessel_draft_limit = mooring.get('vessel_draft_limit')
                    mo.vessel_beam_limit = mooring.get('vessel_beam_limit')
                    mo.vessel_weight_limit = mooring.get('vessel_weight_limit')
                    mo.mooring_bookings_mooring_specification = mooring.get('mooring_specification')
                    mo.mooring_bookings_bay_id = mooring.get('marine_park_id')
                    mo.save()
                    
                    if (float(mo.vessel_size_limit) != float(orig_mo.vessel_size_limit) or
                        float(mo.vessel_draft_limit) != float(orig_mo.vessel_draft_limit) or
                        float(mo.vessel_beam_limit) != float(orig_mo.vessel_beam_limit) or
                        float(mo.vessel_weight_limit) != float(orig_mo.vessel_weight_limit) or
                        float(mo.mooring_bookings_mooring_specification) != float(orig_mo.mooring_bookings_mooring_specification) or
                        float(mo.mooring_bookings_bay_id) != float(orig_mo.mooring_bookings_bay_id)):
                        records_updated.append(str(mo.name))
                else:
                    try:
                        mooring_bay = MooringBay.objects.get(
                            mooring_bookings_id=mooring.get('marine_park_id'), 
                            active=True
                        )
                    except:
                        continue
                    
                    mooring = Mooring.objects.create(
                            mooring_bookings_id=mooring.get("id"), 
                            name=mooring.get("name"),
                            mooring_bay = mooring_bay,
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
                elif mooring_obj.mooring_bookings_id in [x.get("id") for x in data]:
                    mooring_obj.active = True
                    mooring_obj.save()
            return [], records_updated

    except Exception as e:
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
                # get mooring_group_id from MB admin Mooring Groups, Rottnest Is Auth and store as env var
                if not env('MOORING_GROUP_ID'):
                    raise Exception('You must set MOORING_GROUP_ID env var')
                else:
                    mooring_group_id = env('MOORING_GROUP_ID')

                if mooring_group_id != bay.get('mooring_group'):
                    continue
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
    """
    This function exports sticker details data as a spreadsheet file,
    and store it as a StickerPrintingBatch object.
    """
    logger = logging.getLogger('cron_tasks')

    stickers = Sticker.objects.filter(
        sticker_printing_batch__isnull=True,
        status=Sticker.STICKER_STATUS_READY,
    )

    errors = []
    updates = []
    today = timezone.localtime(timezone.now()).date()

    if stickers.count():
        try:

            data = []

            data.append([
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
                'Length Colour',
                'White info',
                'Vessel Length',
                'Season',
            ])
            for sticker in stickers:
                try:
                    # Sticker is being printed.  We assign a new number here.
                    sticker.number = '{0:07d}'.format(sticker.next_number)
                    sticker.save()

                    moorings = sticker.get_moorings()
                    mooring_names = [mooring.name for mooring in moorings]
                    mooring_names = ', '.join(mooring_names)

                    if not sticker.postal_address_line1 or not sticker.postal_address_locality or not sticker.postal_address_state or not sticker.postal_address_postcode:
                        logger.warning(f'Postal address not found for the Sticker: [{sticker}].')
                        continue

                    data.append([
                        today.strftime('%d/%m/%Y'),
                        sticker.first_name,
                        sticker.last_name,
                        sticker.postal_address_line1,
                        sticker.postal_address_line2,
                        sticker.postal_address_locality.upper(),
                        sticker.postal_address_state.upper(),
                        sticker.postal_address_postcode,
                        sticker.approval.description,
                        sticker.number,
                        sticker.vessel_registration_number.upper(),
                        mooring_names,
                        sticker.get_sticker_colour(),
                        sticker.get_white_info(),
                        sticker.vessel_applicable_length,
                        sticker.fee_season.name if sticker.fee_season and sticker.fee_season.name else ''
                    ])
                    logger.info('Sticker: {} details added to the spreadsheet'.format(sticker.number))
                    updates.append(sticker.number)

                    new_approval_history_entry = ApprovalHistory.objects.create(
                        vessel_ownership=sticker.approval.current_proposal.vessel_ownership,
                        approval=sticker.approval,
                        proposal=sticker.approval.current_proposal,
                        start_date=sticker.approval.issue_date,
                        approval_letter=sticker.approval.licence_document,
                    )
                    new_approval_history_entry.stickers.add(sticker)
                    new_approval_history_entry.save()

                except Exception as e:
                    err_msg = 'Error adding sticker: {} details to spreadsheet.'.format(sticker.number)
                    logger.error('{}\n{}'.format(err_msg, str(e)))
                    errors.append(err_msg)

            batch_obj = StickerPrintingBatch.objects.create()
            filename = 'RIA-{}.csv'.format(batch_obj.uploaded_date.astimezone(pytz.timezone(TIME_ZONE)).strftime('%Y%m%d'))

            csv_file = str(settings.BASE_DIR)+'/tmp/{}'.format(filename)
            with open(csv_file, 'w', newline='') as new_file:
                writer = csv.writer(new_file)
                for i in data:
                    writer.writerow(i)

            with open(csv_file, 'rb') as f:
                batch_obj._file.save(filename, ContentFile(f.read()), save=False)
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
    """
    Email the file generated at the sticker_export() function to the sticker company:
    """
    logger = logging.getLogger('cron_tasks')
    updates, errors = [], []

    try:
        batches = StickerPrintingBatch.objects.filter(emailed_datetime__isnull=True)
        if batches.count():
            current_datetime = timezone.localtime(timezone.now())

            # Send sticker details spreadsheet file to the printing company
            send_sticker_printing_batch_email(batches)

            for batch in batches:
                batch.emailed_datetime = current_datetime
                batch.save()
                updates.append(batch.name)

                # Update sticker status
                stickers = Sticker.objects.filter(sticker_printing_batch=batch)
                for sticker in stickers:
                    sticker.status = Sticker.STICKER_STATUS_AWAITING_PRINTING
                    sticker.save()
                    logger.info(f'Status: [{Sticker.STICKER_STATUS_AWAITING_PRINTING}] has been set to the sticker: [{sticker}]')
                    if sticker.sticker_to_replace:
                        # new sticker has the old sticker here if it's created for renewal
                        # When this sticker is created for renewal, set 'expired' status to the old sticker.
                        sticker.sticker_to_replace.status = Sticker.STICKER_STATUS_EXPIRED
                        sticker.sticker_to_replace.save()
                        logger.info(f'Status: [{Sticker.STICKER_STATUS_EXPIRED}] has been set to the sticker: [{sticker.sticker_to_replace}]')

    except Exception as e:
        err_msg = 'Error sending the sticker printing batch spreadsheet file(s): {}'.format(', '.join([batch.name for batch in batches]))
        logger.error('{}\n{}'.format(err_msg, str(e)))
        errors.append(err_msg)

    return updates, errors


## DoT vessel rego check
def get_client_ip(request):    
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    x_orignal_forwarded_for =  request.META.get('HTTP_X_ORIGINAL_FORWARDED_FOR')

    if x_orignal_forwarded_for:
       ip = x_orignal_forwarded_for.split(',')[-1].strip()
    elif x_real_ip:
       ip = x_real_ip
    elif x_forwarded_for:
       ip = x_forwarded_for.split(',')[-1].strip()
    else:
       ip = request.META.get('REMOTE_ADDR')
    return ip


def get_dot_vessel_information(request,json_string):
    DOT_URL=settings.DOT_URL
    paramGET=parse.quote(json_string.replace("\n", ""))
    client_ip = get_client_ip(request)
    auth=auth=HTTPBasicAuth(settings.DOT_USERNAME,settings.DOT_PASSWORD)
    r = requests.get(DOT_URL+"?paramGET="+paramGET+"&client_ip="+client_ip, auth=auth)
    return r.text

def get_removed_vessels_in_current_season(approval):

    #get all vessel ownership formerly on approval (identified via proposals in seasons)
    proposal_ids = []
    vessel_ownership_ids = []
    continue_loop = True

    proposal = approval.current_proposal

    while continue_loop:
        if proposal:
            if proposal.id in proposal_ids:
                continue_loop = False
                break
            
            proposal_ids.append(proposal.id)
            if proposal.vessel_ownership:
                vessel_ownership_ids.append(proposal.vessel_ownership.id)

            if proposal.proposal_type.code in [PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL]:
                # Now, 'prev_application' is the very first application for this season
                # We are not interested in any older applications
                continue_loop = False
                break
            else:
                # Assign the previous application, then perform checking above again
                proposal = proposal.previous_application
        else:
            continue_loop = False
            break

    vessel_ownership_ids = list(set(vessel_ownership_ids))

    if type(approval.child_obj) in [AnnualAdmissionPermit, AuthorisedUserPermit]:
        #if the vo has an end date OR is not the current proposal's vo, include in list
        current_vo_id = approval.current_proposal.vessel_ownership.id if approval.current_proposal.vessel_ownership else None
        return VesselOwnership.objects.filter(id__in=vessel_ownership_ids).filter(Q(end_date__isnull=False)|~Q(id=current_vo_id))
    elif type(approval.child_obj) == MooringLicence:
        #if the vo has an end date OR is not on a current vooa for the approval, include in list
        current_vooa_ids = list(approval.child_obj.get_current_vessel_ownership_on_approvals().values_list("vessel_ownership_id",flat=True))
        return VesselOwnership.objects.filter(id__in=vessel_ownership_ids).filter(Q(end_date__isnull=False)|~Q(id__in=current_vooa_ids))

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
        
        if (approval 
            and type(approval.child_obj) in [AnnualAdmissionPermit, AuthorisedUserPermit] 
            and approval.current_proposal 
            and approval.current_proposal.vessel_ownership and not approval.current_proposal.vessel_ownership.end_date and approval.current_proposal.vessel_ownership.vessel):
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

            if resp_dict.get("status") == 200:
                updates.append('approval_id: {}, vessel_id: {}'.format(approval.id, approval.current_proposal.vessel_ownership.vessel.id))
            else:
                errors.append('approval_id: {}, vessel_id: {}, error_message: {}'.format(approval.id, approval.current_proposal.vessel_ownership.vessel.id, resp.text))
        elif approval and type(approval.child_obj) == MooringLicence:
            for vessel_ownership in approval.child_obj.vessel_ownership_list:
                if vessel_ownership.vessel:
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

                    if resp_dict.get("status") == 200:
                        updates.append('approval_id: {}, vessel_id: {}'.format(approval.id, vessel_ownership.vessel.id))
                    else:
                        errors.append('approval_id: {}, vessel_id: {}, error_message: {}'.format(approval.id, vessel_ownership.vessel.id, resp.text))
        
        if approval:
            status = "cancelled"
            cancelled_vessel_ownerships = get_removed_vessels_in_current_season(approval)
            for vessel_ownership in cancelled_vessel_ownerships:
                if vessel_ownership.vessel:
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

                    if resp_dict.get("status") == 200:
                        updates.append('approval_id: {}, vessel_id: {}'.format(approval.id, vessel_ownership.vessel.id))
                    else:
                        errors.append('approval_id: {}, vessel_id: {}, error_message: {}'.format(approval.id, vessel_ownership.vessel.id, resp.text))
            
        if approval and not errors:
            approval.export_to_mooring_booking = False
            approval.save()

        return errors, updates
    except Exception as e:
        print(str(e))
        logger.error(str(e))
        raise e


def calculate_minimum_max_length(fee_items_interested, max_amount_paid):
    """
    Find out MINIMUM max-length from fee_items_interested by max_amount_paid
    """
    max_length = 0
    for fee_item in fee_items_interested:
        if fee_item.incremental_amount:
            smallest_vessel_size = float(fee_item.vessel_size_category.start_size)

            larger_category = fee_item.vessel_size_category.vessel_size_category_group.get_one_larger_category(
                fee_item.vessel_size_category
            )
            if larger_category:
                max_number_of_increment = round(
                    larger_category.start_size - fee_item.vessel_size_category.start_size
                )
            else:
                max_number_of_increment = 1000  # We probably would like to cap the number of increments

            increment = 0.0
            while increment <= max_number_of_increment:
                test_vessel_size = smallest_vessel_size + increment
                fee_amount_to_pay = fee_item.get_absolute_amount(test_vessel_size)
                if fee_amount_to_pay <= max_amount_paid:
                    if not max_length or test_vessel_size > max_length:
                        max_length = test_vessel_size
                increment += 1
        else:
            fee_amount_to_pay = fee_item.get_absolute_amount()
            if fee_amount_to_pay <= max_amount_paid:
                # Find out start size of one larger category
                larger_category = fee_item.vessel_size_category.vessel_size_category_group.get_one_larger_category(
                    fee_item.vessel_size_category
                )
                if larger_category:
                    if not max_length or larger_category.start_size > max_length:
                        if larger_category.include_start_size:
                            max_length = float(larger_category.start_size) - 0.00001
                        else:
                            max_length = float(larger_category.start_size)
                else:
                    max_length = None
            else:
                # The amount to pay is now more than the max amount paid
                # Assuming larger vessel is more expensive, the all the fee_items left are more expensive than max_amount_paid
                break
    return max_length


def calculate_max_length(fee_constructor, max_amount_paid, proposal_type):
    # All the amendment FeeItems interested
    # Ordered by 'start_size' ascending order, which means the cheapest fee_item first.
    fee_items_interested = fee_constructor.feeitem_set.filter(proposal_type=proposal_type).order_by('vessel_size_category__start_size')
    max_length = calculate_minimum_max_length(fee_items_interested, max_amount_paid)
    return max_length


def reorder_wla(target_bay):
    logger.info(f'Ordering WLAs for the bay: [{target_bay}]...')
    place = 1
    # set wla order per bay for current allocations
    for w in WaitingListAllocation.objects.filter(
        wla_queue_date__isnull=False,
        current_proposal__preferred_bay=target_bay,
        status__in=[
            Approval.APPROVAL_STATUS_CURRENT,
            Approval.APPROVAL_STATUS_SUSPENDED,
        ],
        internal_status__in=[
            Approval.INTERNAL_STATUS_WAITING,
        ]
    ).order_by('wla_queue_date','wla_order'):
        w.wla_order = place
        w.save()
        logger.info(f'Allocation order: [{w.wla_order}] has been set to the WaitingListAllocation: [{w}].')
        place += 1

def remove_html_tags(text):

    if text is None:
        return None

    HTML_TAGS_WRAPPED = re.compile(r'<[^>]+>.+</[^>]+>')
    HTML_TAGS_NO_WRAPPED = re.compile(r'<[^>]+>')

    text = HTML_TAGS_WRAPPED.sub('', text)
    text = HTML_TAGS_NO_WRAPPED.sub('', text)
    return text

def remove_script_tags(text):

    if text is None:
        return None

    SCRIPT_TAGS_WRAPPED = re.compile(r'(?i)<script[^>]+>.+</script[^>]+>')
    SCRIPT_TAGS_NO_WRAPPED = re.compile(r'(?i)<script[^>]+>')

    text = SCRIPT_TAGS_WRAPPED.sub('', text)
    text = SCRIPT_TAGS_NO_WRAPPED.sub('', text)

    ATTR_BLACKLIST = ['onresize','onvolumechange','onsuspend','onpopstate','onbeforeunload','oncontextmenu',
        'ondragstart','oncuechange','onselect','onafterprint','onmouseover','ondragleave','onstorage',
        'onbeforeprint','onhashchange','onabort','ondragover','onwaiting','onclick','onmousemove','onkeyup',
        'onmousedown','ononline','onsearch','onprogress','onfocus','onmouseup','onplaying','onstalled','oninvalid',
        'ontimeupdate','onkeypress','onseeked','onreset','onwheel','onemptied','oninput','onpagehide','onpause',
        'onloadeddata','onseeking','onunload','onpageshow','onerror','ondrop','oncanplay','oncopy','onended','oncut',
        'onsubmit','ondrag','onblur','ondragend','onplay','onratechange','onloadedmetadata','oncanplaythrough',
        'ondurationchange','onchange','ondblclick','onmousewheel','onpaste','onload','onscroll','onkeydown',
        'ontoggle','onmouseout','onoffline','onloadstart','ondragenter']
    ATTR_BLACKLIST_STR=('|').join(ATTR_BLACKLIST)

    HTML_TAGS_WITH_ATTR_WRAPPED = re.compile(r'(?i)<[^>]+('+ATTR_BLACKLIST_STR+')[\\s]*=[^>]+>.+</[^>]+>')
    HTML_TAGS_WITH_ATTR_NO_WRAPPED = re.compile(r'(?i)<[^>]+('+ATTR_BLACKLIST_STR+')[\\s]*=[^>]+>')

    text = HTML_TAGS_WITH_ATTR_WRAPPED.sub('', text)
    text = HTML_TAGS_WITH_ATTR_NO_WRAPPED.sub('', text)

    return text

def is_json(value):
    try:
        json.loads(value)
    except:
        return False
    return True

def sanitise_fields(instance, exclude=[], error_on_change=[]):
    if hasattr(instance,"__dict__"):
        for i in instance.__dict__:
            #remove html tags for all string fields not in the exclude list
            if not i in exclude and (isinstance(instance.__dict__[i], dict)):
                instance.__dict__[i] = sanitise_fields(instance.__dict__[i])
            
            elif isinstance(instance.__dict__[i], list) and not i in exclude:
                for j in range(0, len(instance.__dict__[i])):
                    check = instance.__dict__[i][j]
                    if isinstance(instance.__dict__[i][j],str):
                        instance.__dict__[i][j] = remove_html_tags(instance.__dict__[i][j])
                    elif isinstance(instance.__dict__[i][j], list) or isinstance(instance.__dict__[i][j], dict):
                        instance.__dict__[i][j] = sanitise_fields(instance.__dict__[i][j])
                    if i in error_on_change and check != instance.__dict__[i][j]:
                        raise serializers.ValidationError("html tags included in field")
            
            elif isinstance(instance.__dict__[i], str) and not i in exclude:
                check = instance.__dict__[i]
                setattr(instance, i, remove_html_tags(instance.__dict__[i]))
                if i in error_on_change and check != instance.__dict__[i]:
                    #only fields that cannot be allowed to change through sanitisation just before saving will throw an error
                    raise serializers.ValidationError("html tags included in field")
            elif isinstance(instance.__dict__[i], str) and i in exclude:
                #even though excluded, we still check to remove script tags
                setattr(instance, i, remove_script_tags(instance.__dict__[i]))
                if i in error_on_change and check != instance.__dict__[i]:
                    #only fields that cannot be allowed to change through sanitisation just before saving will throw an error
                    raise serializers.ValidationError("script tags included in field")
            elif (isinstance(instance.__dict__[i], list) or isinstance(instance.__dict__[i], dict)) and i in exclude:
                #if we have reached this point, it means we have a json object with fields that are allowed to contain tags
                #we'll use . notation to identify sub fields that should be carried over to the exclude and error on change lists
                #NOTE: to allow sub fields to be sanitised, the parent field should be included in both lists required for their respective children
                sub_exclude_list = list(filter(lambda e:e.startswith(i+"."), exclude))
                exclude_list = list(map(lambda e:e.replace(i+".","",1), sub_exclude_list))
                #NOTE: a sub error on change list will require the parent field to be in the exclude list, to reach this point (but not necessarily in the error_on_change list)
                sub_error_on_change_list = list(filter(lambda e:e.startswith(i+"."), error_on_change))
                error_on_change_list = list(map(lambda e:e.replace(i+".","",1), sub_error_on_change_list))

                if isinstance(instance.__dict__[i], dict):
                    check = instance.__dict__[i]
                    instance.__dict__[i] = sanitise_fields(instance.__dict__[i], exclude=exclude_list, error_on_change=error_on_change_list)
                    if i in error_on_change and check != instance.__dict__[i]:
                        raise serializers.ValidationError("html tags included in field")
                elif isinstance(instance.__dict__[i], list):
                    for j in range(0, len(instance.__dict__[i])):
                        check = instance.__dict__[i][j]
                        if isinstance(instance.__dict__[i][j],str):
                            #strings in an excluded list will be treated as excluded
                            instance.__dict__[i][j] = remove_script_tags(instance.__dict__[i][j])
                        elif isinstance(instance.__dict__[i][j], list) or isinstance(instance.__dict__[i][j], dict):
                            instance.__dict__[i][j] = sanitise_fields(instance.__dict__[i][j], exclude=exclude_list, error_on_change=error_on_change_list)
                        if i in error_on_change and check != instance.__dict__[i][j]:
                            raise serializers.ValidationError("html tags included in field")
    else:
        remove_keys = []
        for i in instance:
            #for dicts we also check the keys - they are removed completely if not sanitary (should not change keys)
            original_key = i
            if isinstance(original_key, str):
                sanitised_key = remove_html_tags(i)
                if original_key != sanitised_key:
                    remove_keys.append(original_key)
                    continue

            #remove html tags for all string fields not in the exclude list
            if not i in exclude and (isinstance(instance[i], dict)):
                instance[i] = sanitise_fields(instance[i])

            elif isinstance(instance[i], list) and not i in exclude:
                for j in range(0, len(instance[i])):
                    check = instance[i][j]
                    if isinstance(instance[i][j],str):
                        instance[i][j] = remove_html_tags(instance[i][j])
                    elif isinstance(instance[i][j], list) or isinstance(instance[i][j], dict):
                        instance[i][j] = sanitise_fields(instance[i][j])
                    if i in error_on_change and check != instance[i][j]:
                        raise serializers.ValidationError("html tags included in field")

            else:
                if isinstance(instance[i], str) and not i in exclude:
                    check = instance[i]
                    instance[i] = remove_html_tags(instance[i])
                    if i in error_on_change and check != instance[i]:
                        #only fields that cannot be allowed to change through sanitisation just before saving will throw an error
                        raise serializers.ValidationError("html tags included in field")
                elif isinstance(instance[i], str) and i in exclude:
                    #even though excluded, we still check to remove script tags
                    instance[i] = remove_script_tags(instance[i])
                    if i in error_on_change and check != instance[i]:
                        #only fields that cannot be allowed to change through sanitisation just before saving will throw an error
                        raise serializers.ValidationError("script tags included in field")
                elif (isinstance(instance[i], list) or isinstance(instance[i], dict)) and i in exclude:
                    #if we have reached this point, it means we have a json object with fields that are allowed to contain tags
                    #we'll use . notation to identify sub fields that should be carried over to the exclude and error on change lists
                    #NOTE: to allow sub fields to be sanitised, the parent field should be included in both lists required for their respective children
                    sub_exclude_list = list(filter(lambda e:e.startswith(i+"."), exclude))
                    exclude_list = list(map(lambda e:e.replace(i+".","",1), sub_exclude_list))
                    #NOTE: a sub error on change list will require the parent field to be in the exclude list, to reach this point (but not necessarily in the error_on_change list)
                    sub_error_on_change_list = list(filter(lambda e:e.startswith(i+"."), error_on_change))
                    error_on_change_list = list(map(lambda e:e.replace(i+".","",1), sub_error_on_change_list))

                    if isinstance(instance[i], dict):
                        check = instance[i]
                        instance[i] = sanitise_fields(instance[i], exclude=exclude_list, error_on_change=error_on_change_list)
                        if i in error_on_change and check != instance[i]:
                            raise serializers.ValidationError("script tags included in field")
                    elif isinstance(instance[i], list):                        
                        for j in range(0, len(instance[i])):
                            check = instance[i][j]
                            if isinstance(instance[i][j],str):
                                #strings in an excluded list will be treated as excluded
                                instance[i][j] = remove_script_tags(instance[i][j])
                            elif isinstance(instance[i][j], list) or isinstance(instance[i][j], dict):
                                instance[i][j] = sanitise_fields(instance[i][j], exclude=exclude_list, error_on_change=error_on_change_list)
                            if i in error_on_change and check != instance[i][j]:
                                raise serializers.ValidationError("script tags included in field")
                    
        for i in remove_keys:
            del instance[i]
    return instance

def file_extension_valid(file, whitelist, model):
    _, extension = os.path.splitext(file)
    extension = extension.replace(".", "").lower()

    check = whitelist.filter(name=extension).filter(
        Q(model="all") | Q(model__iexact=model)
    )
    valid = check.exists()

    return valid

def check_file(file, model_name):
    from mooringlicensing.components.main.models import FileExtensionWhitelist

    # check if extension in whitelist
    cache_key = settings.CACHE_KEY_FILE_EXTENSION_WHITELIST
    whitelist = cache.get(cache_key)
    if whitelist is None:
        whitelist = FileExtensionWhitelist.objects.all()
        cache.set(cache_key, whitelist, settings.CACHE_TIMEOUT_2_HOURS)

    valid = file_extension_valid(str(file), whitelist, model_name)

    if not valid:
        raise serializers.ValidationError("File type/extension not supported")
    
def getProposalExport(filters, num):

    qs = Proposal.objects.order_by("-lodgement_date")
    if filters:
        #type
        if "type" in filters and filters["type"] and not filters["type"].lower() == 'all':
            if filters["type"].lower() == 'mla':
                qs = qs.filter(lodgement_number__startswith="ML")
            if filters["type"].lower() == 'aua':
                qs = qs.filter(lodgement_number__startswith="AU")
            if filters["type"].lower() == 'aaa':
                qs = qs.filter(lodgement_number__startswith="AA")
            if filters["type"].lower() == 'wla':
                qs = qs.filter(lodgement_number__startswith="WL")
        #lodged_on_from
        if "lodged_on_from" in filters and filters["lodged_on_from"]:
            qs = qs.filter(lodgement_date__gte=filters["lodged_on_from"])
        #lodged_on_to
        if "lodged_on_to" in filters and filters["lodged_on_to"]:
            qs = qs.filter(lodgement_date__lte=filters["lodged_on_to"])
        #category
        if "category" in filters and filters["category"] and not filters["category"].lower() == 'all':
            qs = qs.filter(proposal_type__code=filters["category"])
        #status
        if "status" in filters and filters["status"] and not filters["status"].lower() == 'all':
            qs = qs.filter(processing_status=filters["status"])

    return qs[:num]
    
def getApprovalExport(filters, num):

    qs = Approval.objects.order_by("-issue_date").exclude(lodgement_number__startswith='WLA')

    if filters:
        #type
        if "type" in filters and filters["type"] and not filters["type"].lower() == 'all':
            if filters["type"].lower() == 'ml':
                qs = qs.filter(lodgement_number__startswith="MOL")
            if filters["type"].lower() == 'aup':
                qs = qs.filter(lodgement_number__startswith="AUP")
            if filters["type"].lower() == 'aap':
                qs = qs.filter(lodgement_number__startswith="AAP")
        #issued_from
        if "issued_from" in filters and filters["issued_from"]:
            qs = qs.filter(issue_date__gte=filters["issued_from"])
        #issued_to
        if "issued_to" in filters and filters["issued_to"]:
            qs = qs.filter(issue_date__lte=filters["issued_to"])
        #status
        if "status" in filters and filters["status"] and not filters["status"].lower() == 'all':
            qs = qs.filter(status=filters["status"])

    return qs[:num]
    
def getComplianceExport(filters, num):

    qs = Compliance.objects.order_by("-lodgement_date")

    if filters:
        #lodged_on_from
        if "lodged_on_from" in filters and filters["lodged_on_from"]:
            qs = qs.filter(lodgement_date__gte=filters["lodged_on_from"])
        #lodged_on_to
        if "lodged_on_to" in filters and filters["lodged_on_to"]:
            qs = qs.filter(lodgement_date__lte=filters["lodged_on_to"])
        #status
        if "status" in filters and filters["status"] and not filters["status"].lower() == 'all':
            qs = qs.filter(processing_status=filters["status"])

    return qs[:num]
    
def getWaitingListExport(filters, num):

    qs = WaitingListAllocation.objects.order_by("-issue_date")

    if filters:
        #issued_from
        if "issued_from" in filters and filters["issued_from"]:
            qs = qs.filter(issue_date__gte=filters["issued_from"])
        #issued_to
        if "issued_to" in filters and filters["issued_to"]:
            qs = qs.filter(issue_date__lte=filters["issued_to"])
        #status
        if "status" in filters and filters["status"] and not filters["status"].lower() == 'all':
            qs = qs.filter(approval__status=filters["status"])
        #bay
        if "bay" in filters and filters["bay"] and not filters["bay"].lower() == 'all':
            qs = qs.filter(current_proposal__preferred_bay__id=filters["bay"])
        #max_vessel_length
        if "max_vessel_length" in filters and filters["max_vessel_length"]:
            qs = qs.filter(current_proposal__vessel_details__vessel_length__lte=float(filters["max_vessel_length"]))
        #max_vessel_draft
        if "max_vessel_draft" in filters and filters["max_vessel_draft"]:
            qs = qs.filter(current_proposal__vessel_details__vessel_draft__lte=float(filters["max_vessel_draft"]))
        
    return qs[:num]
    
def getMooringExport(filters, num):

    qs = Mooring.objects.order_by("-id")

    if filters:
        #status
        if "status" in filters and filters["status"] and not filters["status"].lower() == 'all':
            if filters["status"] == 'Licensed':
                qs = qs.filter(mooring_licence__approval__status__in=['current','suspended'])
            elif filters["status"] == 'Licence Application':
                qs = qs.filter(~Q(ria_generated_proposal__processing_status__in=['approved', 'declined', 'discarded']) & Q(ria_generated_proposal__lodgement_number__startswith="ML"))
            elif filters["status"] == 'Unlicensed':
                qs = qs.exclude(
                    (~Q(ria_generated_proposal__processing_status__in=['approved', 'declined', 'discarded']) 
                    & Q(ria_generated_proposal__lodgement_number__startswith="ML")) | Q(mooring_licence__approval__status__in=['current','suspended'])
                )
        #bay
        if "bay" in filters and filters["bay"] and not filters["bay"].lower() == 'all':
            qs = qs.filter(mooring_bay__id=filters["bay"])

    return qs[:num]

def getDcvPermitExport(filters, num):

    qs = DcvPermit.objects.order_by("-date_created")

    if filters:
        if "season" in filters and filters["season"] and not filters["season"].lower() == 'all':
            qs = qs.filter(fee_season__id=filters["season"])
        if "organisation" in filters and filters["organisation"]:
            qs = qs.filter(dcv_organisation__name__iexact=filters["season"])

    return qs[:num]

def getDcvAdmissionExport(filters, num):

    qs = DcvAdmission.objects.order_by("-date_created")

    if filters:
        if "organisation" in filters and filters["organisation"]:
            qs = qs.filter(dcv_organisation__name__iexact=filters["season"])
        #lodged_on_from
        if "lodged_on_from" in filters and filters["lodged_on_from"]:
            qs = qs.filter(proposal__lodgement_datetime__gte=filters["lodged_on_from"])
        #lodged_on_to
        if "lodged_on_to" in filters and filters["lodged_on_to"]:
            qs = qs.filter(proposal__lodgement_datetime__lte=filters["lodged_on_to"])

    return qs[:num]

def getPrintExport(filters, num):

    qs = Sticker.objects.order_by("-date_created")

    if filters:        
        if "season" in filters and filters["season"] and not filters["season"].lower() == 'all':
            qs = qs.filter(fee_season__name=filters["season"])
        if "status" in filters and filters["status"] and not filters["status"].lower() == 'all':
            qs = qs.filter(status=filters["status"])

    return qs[:num]

def getSystemUserExport(filters, num):

    qs = SystemUser.objects.order_by("-id")

    if filters:        
        if "active" in filters and filters["active"]:
            qs = qs.filter(is_active=filters["active"])

    return qs[:num]

def getInvoiceExport(filters, num):

    qs = Invoice.objects.order_by("-id")

    application_references = list(ApplicationFee.objects.all().values_list('invoice_reference', flat=True))
    sticker_action_references = list(StickerActionFee.objects.all().values_list('invoice_reference', flat=True))
    applicable_references = []

    if filters:        
        if "fee_source_type" in filters and filters["fee_source_type"]:
            if filters["fee_source_type"] == "application":
                applicable_references = application_references
            elif filters["fee_source_type"] == "sticker_action":
                applicable_references = sticker_action_references
            else:
                applicable_references = application_references + sticker_action_references
        else:
            applicable_references = application_references + sticker_action_references
        if "status" in filters and filters["status"]:
            if filters["status"] == "settled":
                qs = qs.exclude(settlement_date=None,voided=True)
            elif filters["status"] == "not_settled":
                qs = qs.filter(settlement_date=None,voided=False)
            elif filters["status"] == "voided":
                qs = qs.filter(voided=True)
    else:
        applicable_references = application_references + sticker_action_references

    qs = qs.filter(reference__in=applicable_references)

    return qs[:num]

def exportModelData(model, filters, num_records):

    if not num_records:
        num_records = MAX_NUM_ROWS_MODEL_EXPORT
    else:
        num_records = min(num_records, MAX_NUM_ROWS_MODEL_EXPORT)

    if model == "proposal":
        return getProposalExport(filters, num_records)
    elif model == "approval": #exclude waiting list
        return getApprovalExport(filters, num_records)
    elif model == "compliance":
        return getComplianceExport(filters, num_records)
    elif model == "waiting_list":
        return getWaitingListExport(filters, num_records)
    elif model == "mooring":
        return getMooringExport(filters, num_records)
    elif model == "dcv_permit":
        return getDcvPermitExport(filters, num_records)
    elif model == "dcv_admission":
        return getDcvAdmissionExport(filters, num_records)
    elif model == "sticker":
        return getPrintExport(filters, num_records)
    elif model == "system_user":
        return getSystemUserExport(filters, num_records)
    elif model == "invoice":
        return getInvoiceExport(filters, num_records)
    else:
        return

def csvExportData(model, header, columns):
    
    csv_file = str(settings.BASE_DIR)+'/tmp/{}_{}_{}.csv'.format(model,uuid.uuid4(),int(datetime.datetime.now().timestamp()*100000))
    with open(csv_file, 'w', newline='') as new_file:
        writer = csv.writer(new_file)
        writer.writerow(header)
        for i in columns:
            writer.writerow(i)
    return csv_file

def excelExportData(model, header, columns):
    excel_file = str(settings.BASE_DIR)+'/tmp/{}_{}_{}.xlsx'.format(model,uuid.uuid4(),int(datetime.datetime.now().timestamp()*100000))
    workbook = xlsxwriter.Workbook(excel_file) 
    worksheet = workbook.add_worksheet("{} Report".format(model.capitalize()))
    format = workbook.add_format()

    col = 0 
    row = 0

    col_lens = [0]*len(header)

    for i in header:
        worksheet.write(row, col, str(i), format)
        col_lens[col] = len(str(i))+2
        worksheet.set_column(col, col, col_lens[col])
        col += 1
    col = 0 
    row += 1
    for i in columns:
        for j in i:
            worksheet.write(row, col, str(j), format)
            if len(str(j)) > col_lens[col]:
                col_lens[col] = len(str(j))+2
                worksheet.set_column(col, col, col_lens[col])
            col += 1
        col = 0
        row += 1

    workbook.close() 

    return excel_file

def getProposalExportFields(data):
    header = ["Lodgement Number", "Type", "Category" , "Applicant", "Status", "Auto Approved","Lodged On", "Application Vessel Rego No", "Application Vessel Length", "Application Vessel Draft", "Application Vessel Weight", "Invoice Properties"]

    columns = list(data.annotate(type=
        Case(
            When(
                lodgement_number__startswith='ML',
                then=Value("Mooring Site Licence Application")
            ),
            When(
                lodgement_number__startswith='WL',
                then=Value("Waiting List Application")
            ),
            When(
                lodgement_number__startswith='AA',
                then=Value("Annual Admission Application")
            ),
            When(
                lodgement_number__startswith='AU',
                then=Value("Authorised User Application")
            ),
            default=Value(''),
            output_field=CharField(),     
        )
    ).annotate(
        applicant=Concat(
            'proposal_applicant__first_name',
            Value(" "),
            'proposal_applicant__last_name'
            ),
    ).values_list(
        "lodgement_number",
        "type",
        "proposal_type__description",
        "applicant",
        "processing_status",
        "auto_approve",
        "lodgement_date",
        "rego_no",
        "vessel_length",
        "vessel_draft",
        "vessel_weight",
        "invoice_property_cache",
        )
    )
    
    return header, columns

def getApprovalExportFields(data):
    header = ["Number", "Application Number", "Type", "Sticker Number/s" , "Sticker Mailed Date/s", "Holder", "Holder Email", "Holder Mobile Number", "Holder Phone Number", "Status", "Mooring", "Issue Date", "Start Date", "Expiry Date", "Vessel Registration"]

    columns = list(data.annotate(type=
        Case(
            When(
                lodgement_number__startswith='MOL',
                then=Value("Mooring Site Licence")
            ),
            When(
                lodgement_number__startswith='AAP',
                then=Value("Annual Admission Permit")
            ),
            When(
                lodgement_number__startswith='AUP',
                then=Value("Authorised User Permit")
            ),
            default=Value(''),
            output_field=CharField(),     
        )
    ).annotate(
        holder=Concat(
            'current_proposal__proposal_applicant__first_name',
            Value(" "),
            'current_proposal__proposal_applicant__last_name'
            ),
    ).annotate(
        sticker_numbers=ArrayAgg(
            'stickers__number', 
            filter=(
                Q(stickers__status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])
            ),
            distinct=True
        ),      
    ).annotate(
        sticker_mailing_date=ArrayAgg(
            Cast('stickers__mailing_date', CharField()),
            filter=(
                Q(stickers__status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])
                & ~Q(stickers__mailing_date=None)
                ),
            distinct=True
        ), 
    ).annotate(
        mooring_number=ArrayAgg(
            'moorings__name',
            filter=(
                ~Q(moorings__name=None)
            ),
            distinct=True
        ), 
    ).annotate(
        rego_no=Case(
            When(
                Q(lodgement_number__startswith='MOL'),
                then=ArrayAgg(
                    'vesselownershiponapproval__vessel_ownership__vessel__rego_no',
                    filter=Q(vesselownershiponapproval__vessel_ownership__end_date=None),
                    distinct=True
                )
            ),
            When(
                ~Q(lodgement_number__startswith='MOL'),
                then=ArrayAgg(
                    'current_proposal__vessel_ownership__vessel__rego_no',
                    filter=Q(current_proposal__vessel_ownership__end_date=None),
                    distinct=True
                )
            ),
            output_field=ArrayField(CharField())
        )
    ).values_list(
        "lodgement_number",
        "current_proposal__lodgement_number",
        "type",
        "sticker_numbers",
        "sticker_mailing_date",
        "holder",
        "current_proposal__proposal_applicant__email",
        "current_proposal__proposal_applicant__mobile_number",
        "current_proposal__proposal_applicant__phone_number",
        "status",
        "mooring_number",
        "issue_date",
        "start_date",
        "expiry_date",
        "rego_no"
        )
    )
    
    return header, columns

def getComplianceExportFields(data):
    header = ["Lodgement Number", "Type", "Approval Number", "Holder", "Holder Email", "Holder Mobile Number", "Holder Phone Number", "Status", "Due Date"]

    columns = list(data.annotate(type=
        Case(
            When(
                approval__lodgement_number__startswith='MOL',
                then=Value("Mooring Site Licence")
            ),
            When(
                approval__lodgement_number__startswith='AAP',
                then=Value("Annual Admission Permit")
            ),
            When(
                approval__lodgement_number__startswith='AUP',
                then=Value("Authorised User Permit")
            ),
            default=Value(''),
            output_field=CharField(),     
        )
    ).annotate(
        holder=Concat(
            'proposal__proposal_applicant__first_name',
            Value(" "),
            'proposal__proposal_applicant__last_name'
            ),
    ).values_list(
        "lodgement_number",
        "type",
        "approval__lodgement_number",
        "holder",
        "proposal__proposal_applicant__email",
        "proposal__proposal_applicant__mobile_number",
        "proposal__proposal_applicant__phone_number",
        "processing_status",
        "due_date",
        )
    )

    return header, columns

def getWaitingListExportFields(data):
    header = ["Lodgement Number", "Holder", "Holder Email", "Holder Mobile Number", "Holder Phone Number", "Status", "Bay", "Issue Date", "Start Date", "Expiry Date", "Vessel Registration"]

    columns = list(data.annotate(
        holder=Concat(
            'current_proposal__proposal_applicant__first_name',
            Value(" "),
            'current_proposal__proposal_applicant__last_name'
            ),
    ).annotate(
        rego_no=Case(
            When(
                Q(current_proposal__vessel_ownership__end_date=None),
                then='current_proposal__vessel_ownership__vessel__rego_no',
            ),
            default=Value(''),
            output_field=CharField()
        ),
    ).values_list(
        "lodgement_number",
        "holder",
        "current_proposal__proposal_applicant__email",
        "current_proposal__proposal_applicant__mobile_number",
        "current_proposal__proposal_applicant__phone_number",
        "status",
        "current_proposal__preferred_bay__name",
        "issue_date",
        "start_date",
        "expiry_date",
        "rego_no",
        )
    )

    return header, columns

def getMooringExportFields(data):
    header = ["Mooring", "Bay", "Status", "Holder", "Holder Email", "Holder Mobile Number", "Holder Phone Number", "Authorised User Permits (RIA)", "Authorised User Permits (LIC)", "Max Vessel Length (M)", "Max Vessel Draft (M)"]

    columns = list(data.annotate(
        holder=Concat(
            'mooring_licence__current_proposal__proposal_applicant__first_name',
            Value(" "),
            'mooring_licence__current_proposal__proposal_applicant__last_name'
            ),
    ).annotate(
        status=Case(
            When(
                mooring_licence__status__in=['current', 'suspended'],
                then=Value("Licensed")
            ),
            When(
                ~Q(ria_generated_proposal__processing_status__in=['current', 'suspended'])
                & Q(ria_generated_proposal__lodgement_number__startswith='ML'),
                then=Value("Licence Application")
            ),
            default=Value('Unlicensed'),
            output_field=CharField(),     
        )
    ).annotate(
        preference_count_ria=Count(
            Q(mooring_on_approval__approval__status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,])
            &
            Q(mooring_on_approval__end_date__gt=datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()) | Q(mooring_on_approval__end_date__isnull=True)
            &
            Q(mooring_on_approval__site_licensee=False) & Q(mooring_on_approval__active=True)
        )
    ).annotate(
        preference_count_site_licensee=Count(
            Q(mooring_on_approval__approval__status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,])
            &
            Q(mooring_on_approval__end_date__gt=datetime.datetime.now(pytz.timezone(TIME_ZONE)).date()) | Q(mooring_on_approval__end_date__isnull=True)
            &
            Q(mooring_on_approval__site_licensee=False) & Q(mooring_on_approval__active=True)
        )
    ).values_list(
        "name",
        "mooring_bay__name",
        "status",
        "holder",
        "mooring_licence__current_proposal__proposal_applicant__email",
        "mooring_licence__current_proposal__proposal_applicant__mobile_number",
        "mooring_licence__current_proposal__proposal_applicant__phone_number",
        "preference_count_ria",
        "preference_count_site_licensee",
        "vessel_size_limit",
        "vessel_draft_limit",
        )
    )

    return header, columns

def getDcvPermitExportFields(data):
    header = ["Lodgement Number", "Organisation", "Status", "Invoice Properties", "Season", "Sticker", "Vessel Registration"]

    columns = list(data.annotate(
        sticker_numbers=ArrayAgg(
            'stickers__number', 
            filter=(
                Q(stickers__status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])
            ),
            distinct=True
        ),      
    ).values_list(
        "lodgement_number",
        "dcv_organisation__name",
        "status",
        "invoice_property_cache",
        "fee_season__name",
        "sticker_numbers",
        "dcv_vessel__rego_no",
        )
    )

    return header, columns

def getDcvAdmissionExportFields(data):
    header = ["Lodgement Number", "Invoice Properties", "Arrival Dates", "Lodgement Date"]

    columns = list(data.annotate(
        arrival_dates=ArrayAgg(
            Cast('dcv_admission_arrivals__arrival_date', CharField()),
            distinct=True
        ),      
    ).values_list(
        "lodgement_number",
        "invoice_property_cache",
        "arrival_dates",
        "lodgement_datetime",
        )
    )

    return header, columns

def getStickerExportFields(data):
    header = [
        "Sticker Number", 
        "Status",
        "Permit or Licence", 
        "Vessel Registration", 
        "Moorings",
        "Holder", 
        "Holder Email", 
        "Holder Mobile Number", 
        "Holder Phone Number", 
        "Address Line 1",
        "Address Line 2",
        "Address Suburb",
        "Address State",
        "Address Postcode",
        "Date Sent", 
        "Date Printed", 
        "Date Mailed", 
        "Season", 
        "Colour",
        "White Info",
        "Invoice Properties" 
    ]

    vessel_length_sq = Subquery(
        VesselDetails.objects.filter(
            vessel__rego_no=OuterRef('vessel_ownership__vessel__rego_no')  
        ).values('vessel_length')[:1]
    )

    columns = list(
    data.annotate(
        holder=Concat(
            'approval__current_proposal__proposal_applicant__first_name',
            Value(" "),
            'approval__current_proposal__proposal_applicant__last_name'
        ),
    ).annotate(
        moorings=Case(
            When(
                approval__lodgement_number__startswith='AUP',
                then=ArrayAgg(
                    "mooringonapproval__mooring__name",
                    filter = Q(mooringonapproval__end_date__isnull=True),
                    distinct=True,
                ),
            ),
            When(
                approval__lodgement_number__startswith='MOL',
                then=ArrayAgg("approval__mooringlicence__mooring__name",distinct=True),
            ),
            default=Value([]),
            output_field=ArrayField(base_field=CharField()) 
        )
    ).annotate(
        latest_vessel_length=vessel_length_sq
    ).annotate(
        colour=Case(
            When(
                (Q(approval__lodgement_number__startswith='AUP') | Q(approval__lodgement_number__startswith='MOL'))&
                Q(latest_vessel_length__lte=Sticker.colour_matrix_dict['Green']),
                then=Value("Green")
            ),
            When(
                (Q(approval__lodgement_number__startswith='AUP') | Q(approval__lodgement_number__startswith='MOL'))&
                Q(latest_vessel_length__lte=Sticker.colour_matrix_dict['Grey'])&
                Q(latest_vessel_length__gt=Sticker.colour_matrix_dict['Green']),
                then=Value("Grey")
            ),
            When(
                (Q(approval__lodgement_number__startswith='AUP') | Q(approval__lodgement_number__startswith='MOL'))&
                Q(latest_vessel_length__lte=Sticker.colour_matrix_dict['Purple'])&
                Q(latest_vessel_length__gt=Sticker.colour_matrix_dict['Grey']),
                then=Value("Purple")
            ),
            When(
                (Q(approval__lodgement_number__startswith='AUP') | Q(approval__lodgement_number__startswith='MOL'))&
                Q(latest_vessel_length__lte=Sticker.colour_matrix_dict['Blue'])&
                Q(latest_vessel_length__gt=Sticker.colour_matrix_dict['Purple']),
                then=Value("Blue")
            ),
            When(
                (Q(approval__lodgement_number__startswith='AUP') | Q(approval__lodgement_number__startswith='MOL'))&
                Q(latest_vessel_length__gt=Sticker.colour_matrix_dict['Blue']),
                then=Value("White")
            ),
            default=Value(""),
        )
    ).annotate(
        white_info=Case(
            When(
                colour="White",
                latest_vessel_length__gt=26,
                then=Cast("latest_vessel_length",CharField())
            ),
            When(
                colour="White",
                latest_vessel_length__gt=24,
                then=Value('26')
            ),
            When(
                colour="White",
                latest_vessel_length__gt=22,
                then=Value('24')
            ),
            When(
                colour="White",
                latest_vessel_length__gt=20,
                then=Value('22')
            ),
            When(
                colour="White",
                latest_vessel_length__gt=18,
                then=Value('20')
            ),
            When(
                colour="White",
                latest_vessel_length__gt=16,
                then=Value('18')
            ),
            default=Value(""),
        )
    ).values_list(
        "number",
        "status",
        "approval__lodgement_number",
        "vessel_ownership__vessel__rego_no",
        "moorings",
        "holder",
        "approval__current_proposal__proposal_applicant__email",
        "approval__current_proposal__proposal_applicant__mobile_number",
        "approval__current_proposal__proposal_applicant__phone_number",
        "postal_address_line1",
        "postal_address_line2",
        "postal_address_locality",
        "postal_address_state",
        "postal_address_postcode",
        "sticker_printing_batch__emailed_datetime",
        "printing_date",
        "mailing_date",
        "fee_season__name",
        "colour",
        "white_info",
        "invoice_property_cache",
        )
    )

    return header, columns

def getSystemUserExportFields(data):
    header = ["Ledger ID", "Account Name", "Legal Name", "Legal DOB", "Email"]

    columns = list(data.annotate(
        account_name=Concat(
            'first_name',
            Value(" "),
            'last_name'
            ),
    ).annotate(
        legal_name=Concat(
            'legal_first_name',
            Value(" "),
            'legal_last_name'
            ),
    ).values_list(
        "ledger_id",
        "account_name",
        "legal_name",
        "legal_dob",
        "email"
        )
    )

    return header, columns

def getInvoiceExportFields(data):
    header = ["Invoice Reference", "Fee Source", "Fee Source Type", "Status", "Created At", "Settled At", "Amount", "Description"]

    application_references = list(ApplicationFee.objects.all().values('invoice_reference', 'proposal__lodgement_number'))
    sticker_action_references = list(StickerActionFee.objects.all().values('invoice_reference', 'sticker_action_details__approval__lodgement_number'))

    application_references_dict = {}
    for i in application_references:
        application_references_dict[i["invoice_reference"]] = i["proposal__lodgement_number"] 
    sticker_action_references_dict = {}
    for i in sticker_action_references:
        sticker_action_references_dict[i["invoice_reference"]] = i["sticker_action_details__approval__lodgement_number"] 

    columns = list(data.annotate(
        fee_source_type=Case(
            When(
                reference__in=application_references_dict,
                then=Value("Application")
            ),
            When(
                reference__in=sticker_action_references_dict,
                then=Value("Sticker Action")
            ),
            default=Value(""),
        )
    ).annotate(
        fee_source=F("reference")
    ).annotate(
        status=Case(
            When(
                (Q(settlement_date=None)&Q(voided=False)),
                then=Value("Not Settled"),
            ),
            When(
                (~Q(settlement_date=None)&Q(voided=False)),
                then=Value("Settled"),
            ),
            When(
                voided=True,
                then=Value("Voided"),
            ),
            default=Value(""),
        )
    ).values_list(
        "reference",
        "fee_source", 
        "fee_source_type", 
        "status", 
        "created", 
        "settlement_date", 
        "amount", 
        "text"
        )
    )

    for i in range(len(columns)):
        values = list(columns[i])
        if values[2] == "Application":
            values[1] = application_references_dict[values[1]]
        if values[2] == "Sticker Action":
            values[1] = sticker_action_references_dict[values[1]]
        columns[i] = tuple(values)

    return header, columns

def formatExportData(model, data, format):

    if model == "proposal":
        header, columns = getProposalExportFields(data)
    elif model == "approval": #exclude waiting list
        header, columns = getApprovalExportFields(data)
    elif model == "compliance":
        header, columns = getComplianceExportFields(data)
    elif model == "waiting_list":
        header, columns = getWaitingListExportFields(data)
    elif model == "mooring":
        header, columns = getMooringExportFields(data)
    elif model == "dcv_permit":
        header, columns = getDcvPermitExportFields(data)
    elif model == "dcv_admission":
        header, columns = getDcvAdmissionExportFields(data)
    elif model == "sticker":
        header, columns = getStickerExportFields(data)
    elif model == "system_user":
        header, columns = getSystemUserExportFields(data)
    elif model == "invoice":
        header, columns = getInvoiceExportFields(data)
    else:
        return

    if os.path.isdir(str(settings.BASE_DIR)+'/tmp/') is False:
        os.makedirs(str(settings.BASE_DIR)+'/tmp/')

    if format == "excel":
        file_name = excelExportData(model, header, columns)
        file_buffer = None
        with open(file_name, 'rb') as f:
            file_buffer = f.read()    
        return ('Mooring Licensing - {} Report.xlsx'.format(model.capitalize()), file_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        file_name =  csvExportData(model, header, columns)
        file_buffer = None
        with open(file_name, 'rb') as f:
            file_buffer = f.read()    
        return ('Mooring Licensing - {} Report.csv'.format(model.capitalize()), file_buffer, 'application/csv')
