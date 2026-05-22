import datetime
import imaplib
import email
import ssl
import openpyxl
from django.utils import timezone
import csv

from confy import env
from django.core.management.base import BaseCommand
from email.header import decode_header, make_header
from django.core.files.base import ContentFile

from mooringlicensing.components.approvals.models import Sticker

import logging

from mooringlicensing.components.emails.emails import TemplateEmailBase
from mooringlicensing.components.emails.utils import get_public_url
from mooringlicensing.components.proposals.models import StickerPrintingResponse, StickerPrintingResponseEmail, \
    StickerPrintedContact
from mooringlicensing.management.commands.utils import construct_email_message

logger = logging.getLogger('cron_tasks')
cron_email = logging.getLogger('cron_email')


class Command(BaseCommand):
    help = 'Import emails and process sticker data'

    def handle(self, *args, **options):
        ##########
        # 1. Save the email-attachment file to the django model (database)
        ##########
        sticker_email_host = env('STICKER_EMAIL_HOST', '')
        sticker_email_port = env('STICKER_EMAIL_PORT', '')
        sticker_email_username = env('STICKER_EMAIL_USERNAME', '')
        sticker_email_password = env('STICKER_EMAIL_PASSWORD', '')

        if not sticker_email_host or not sticker_email_port or not sticker_email_username or not sticker_email_password:
            msg = 'Configure email settings at .env to process sticker responses'
            logger.error(msg)
            cron_email.info(msg)
            raise Exception(msg)

        context = ssl.create_default_context()
        imapclient = imaplib.IMAP4_SSL(sticker_email_host, sticker_email_port, ssl_context=context)

        # login
        imapclient.login(sticker_email_username, sticker_email_password)

        """
        Retrieve messages
        """
        imapclient.select('INBOX')  # Select mail box
        typ, data = imapclient.search(None, "ALL")  # data = [b"1 2 3 4 ..."]
        datas = data[0].split()
        fetch_num = 5000  # The number of messages to fetch

        if (len(datas) - fetch_num) < 0:
            fetch_num = len(datas)

        for num in datas[len(datas) - fetch_num::]:
            try:
                ##########
                # 2. Save the attached files into the database
                ##########
                typ, data = imapclient.fetch(num, '(RFC822)')
                raw_email = data[0][1]

                # converts byte literal to string removing b''
                raw_email_string = raw_email.decode('utf-8')
                email_message = email.message_from_string(raw_email_string)

                email_message_id = str(make_header(decode_header(email_message["Message-ID"])))
                if StickerPrintingResponseEmail.objects.filter(email_message_id=email_message_id):
                    # This email has been saved in the database already.  Skip this email
                    continue

                email_subject = str(make_header(decode_header(email_message["Subject"])))
                email_from = email_message['From']
                body = get_text(email_message)
                email_body = body.decode()
                email_date = email_message['Date']

                sticker_printing_response_email = StickerPrintingResponseEmail.objects.create(
                    email_subject=email_subject,
                    email_from=email_from,
                    email_body=email_body,
                    email_date=email_date,
                    email_message_id=email_message_id,
                )
                logger.info(f'StickerPrintingResponseEmail object: {sticker_printing_response_email} has been created')

                # downloading attachments
                for part in email_message.walk():
                    try:
                        # this part comes from the snipped I don't understand yet...
                        if part.get_content_maintype() == 'multipart':
                            continue
                        if part.get('Content-Disposition') is None:
                            continue
                        fileName = part.get_filename()

                        if bool(fileName) and (fileName.lower().endswith('.xlsx') or (fileName.lower().endswith('.csv'))):
                            now = timezone.localtime(timezone.now())

                            # Create sticker_printing_response object. File is not saved yet
                            sticker_printing_response = StickerPrintingResponse.objects.create(
                                sticker_printing_response_email=sticker_printing_response_email,
                                name=fileName,
                            )
                            logger.info(f'StickerPrintingResponse object: {sticker_printing_response} has been created')

                            # Load attachment file
                            my_bytes = part.get_payload(decode=True)
                            content_file = ContentFile(my_bytes)

                            # Save file
                            sticker_printing_response._file.save(fileName, content_file, save=False)
                            sticker_printing_response.save()
                    except Exception as e:
                        logger.exception('Exception has been raised when importing .xlsx file')
                        continue

                imapclient.copy(num, "Archive")
                imapclient.store(num, "+FLAGS", "\\Deleted")
            except:
                if email_subject:
                    logger.exception(f'Exception has been raised when processing email: subject {email_subject}')
                else:
                    logger.exception(f'Exception has been raised when processing email')

                continue

        imapclient.close()
        imapclient.logout()

        ##########
        # 3. Process xlsx file saved in django model
        ##########
        process_summary = {'stickers': [], 'errors': [], 'sticker_printing_responses': []}  # To be used for sticker processed email
        updates, errors = process_sticker_printing_response(process_summary)

        # Send sticker import batch emails
        send_sticker_import_batch_email(process_summary)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        msg = construct_email_message(cmd_name, errors, updates)
        logger.info(msg)
        cron_email.info(msg)


def get_text(msg):
    if msg.is_multipart():
        return get_text(msg.get_payload(0))
    else:
        return msg.get_payload(None, True)


def make_sure_datetime(dt_obj):
    if dt_obj:
        if isinstance(dt_obj, datetime.datetime):
            return dt_obj
        else:
            return datetime.datetime.strptime(dt_obj, '%d/%m/%Y')
    else:
        return None


def make_sure_sticker_number(sticker_number):
    if isinstance(sticker_number, int):
        return '{0:07d}'.format(sticker_number)
    else:
        return sticker_number


def is_empty(cell):
    return cell.value is None or not str(cell.value).strip()


def process_sticker_printing_response(process_summary):
    errors = []
    updates = []

    responses = StickerPrintingResponse.objects.filter(processed=False)
    for response in responses:
        process_summary['sticker_printing_responses'].append(response)
        if response._file:
            response.no_errors_when_process = True
            # Load file
            if response._file.name:
                filename = response._file.name
            else:
                continue

            if filename.lower().endswith('.csv'):
                try:
                    with open(response._file.path) as csvfile:
                        rows = csv.reader(csvfile)

                        temp_rows = []
                        for row in rows:
                            temp_rows.append(row)
                        rows = temp_rows

                        header_row = None
                        sticker_number_column, printing_date_column, mailing_date_column = 0, 0, 0
                        status_column = 0

                        #determine header row (if it's not the first row for some reason) and cell column positions (batch date, sticker number, printing date, mailing date)
                        for i in range(len(rows)):

                            for j in range(len(rows[i])):

                                if not rows[i][j]:
                                    continue

                                if 'sticker' in rows[i][j].strip().lower() and 'number' in rows[i][j].strip().lower():
                                    sticker_number_column = j
                                    header_row = i # 1-based
                                elif ('printing' in rows[i][j].strip().lower() or 'printed' in rows[i][j].strip().lower()) and 'date' in rows[i][j].strip().lower():
                                    printing_date_column = j
                                elif ('mailing' in rows[i][j].strip().lower() or 'mailed' in rows[i][j].strip().lower()) and 'date' in rows[i][j].strip().lower():
                                    mailing_date_column = j

                                elif ('status' in rows[i][j].strip().lower() or 'status' in rows[i][j].strip().lower()):
                                    status_column = j

                            if header_row != None:
                                break

                        for i in range(len(rows)):
                            if i == header_row:
                                continue

                            try:
                                if not rows[i][sticker_number_column]:
                                    continue

                                sticker_number_value = int(rows[i][sticker_number_column])
                                printing_date_value = rows[i][printing_date_column] if printing_date_column else None
                                mailing_date_value = rows[i][mailing_date_column] if mailing_date_column else None

                                status_value = rows[i][status_column] if status_column else None

                                sticker_number_value = make_sure_sticker_number(sticker_number_value)
                                printing_date_value = make_sure_datetime(printing_date_value)
                                mailing_date_value = make_sure_datetime(mailing_date_value)

                                if printing_date_value and mailing_date_value and (not status_column or not status_value or status_value.lower() != "cancelled"):
                                    # Find a sticker from the Database and change its attributes
                                    sticker = Sticker.objects.get(number=sticker_number_value)
                                    sticker.printing_date = printing_date_value
                                    sticker.mailing_date = mailing_date_value
                                    sticker.sticker_printing_response = response
                                    if sticker.status in (Sticker.STICKER_STATUS_AWAITING_PRINTING, Sticker.STICKER_STATUS_READY):
                                        # sticker should not be in READY status though.
                                        sticker.status = Sticker.STICKER_STATUS_CURRENT
                                    sticker.save()
                                elif status_column and status_value and status_value.lower() == "cancelled":
                                    sticker = Sticker.objects.get(number=sticker_number_value)
                                    sticker.sticker_printing_response = response
                                    if sticker.status in (Sticker.STICKER_STATUS_AWAITING_PRINTING, Sticker.STICKER_STATUS_READY, Sticker.STICKER_STATUS_EXPIRED, Sticker.STICKER_STATUS_LOST):
                                        sticker.status = Sticker.STICKER_STATUS_CANCELLED
                                    sticker.save()
                                
                                process_summary['stickers'].append(sticker)

                                updates.append(sticker.number)
                            except Sticker.DoesNotExist as e:
                                err_msg = 'Error sticker {} not found to update'.format(sticker_number_value)
                                logger.exception('{}\n{}'.format(err_msg, str(e)))
                                errors.append(err_msg)
                                response.no_errors_when_process = False
                                process_summary['errors'].append(err_msg)
                                response.processed = True  # Update response obj not to process again.  But from no_errors_when_process flag tells admin that there was an error.
                                response.save()
                                continue
                            except Exception as e:
                                err_msg = 'Error updating the sticker {}'.format(sticker_number_value)
                                logger.exception('{}\n{}'.format(err_msg, str(e)))
                                errors.append(err_msg)
                                response.no_errors_when_process = False
                                process_summary['errors'].append(err_msg)
                                response.processed = True  # Update response obj not to process again.  But from no_errors_when_process flag tells admin that there was an error.
                                response.save()
                                continue

                except Exception as e:
                    err_msg = 'Error loading the file/worksheet: {}'.format(response._file.name)
                    logger.exception('{}\n{}'.format(err_msg, str(e)))
                    errors.append(err_msg)
                    response.no_errors_when_process = False
                    continue

                response.processed = True  # Update response obj not to process again
                response.save()

            elif filename.lower().endswith('.xlsx'):
                try:
                    wb = openpyxl.load_workbook(response._file)

                    # Retrieve the first worksheet
                    ws = wb.worksheets[0]
                except IndexError as e:
                    logger.warning('No worksheet found in the file: {}'.format(response._file.name))
                    continue
                except Exception as e:
                    err_msg = 'Error loading the file/worksheet: {}'.format(response._file.name)
                    logger.exception('{}\n{}'.format(err_msg, str(e)))
                    errors.append(err_msg)
                    response.no_errors_when_process = False
                    continue

                try:
                    # Loop rows in order to determine which column is what
                    header_row = 0
                    sticker_number_column, printing_date_column, mailing_date_column = 0, 0, 0
                    status_column = 0

                    for row in ws.rows:

                        for cell in row:
                            
                            if not cell.value:
                                continue

                            if 'sticker' in cell.value.lower() and 'number' in cell.value.lower():
                                sticker_number_column = cell.column
                                header_row = cell.row  # 1-based
                            elif ('printing' in cell.value.lower() or 'printed' in cell.value.lower()) and 'date' in cell.value.lower():
                                printing_date_column = cell.column
                            elif ('mailing' in cell.value.lower() or 'mailed' in cell.value.lower()) and 'date' in cell.value.lower():
                                mailing_date_column = cell.column

                            elif ('status' in cell.value.lower() or 'status' in cell.value.lower()):
                                status_column = cell.column
                        if header_row > 0:
                            break

                except Exception as e:
                    err_msg = 'Error loading the table headers {}'.format(response._file.name)
                    logger.exception('{}\n{}'.format(err_msg, str(e)))
                    errors.append(err_msg)
                    response.no_errors_when_process = False
                    continue

                # Loop rows after the header row and retrieve values
                for row in ws.iter_rows(min_row=header_row + 1):
                    if all(is_empty(c) for c in row):
                        # Found empty row, finish processing rows
                        break
                    try:
                        
                        if not row[sticker_number_column - 1].value:
                            continue
                        
                        sticker_number_value = row[sticker_number_column - 1].value
                        printing_date_value = row[printing_date_column - 1].value if printing_date_column else None
                        mailing_date_value = row[mailing_date_column - 1].value if mailing_date_column else None

                        status_value = row[status_column - 1].value if status_column else None

                        sticker_number_value = make_sure_sticker_number(sticker_number_value)
                        printing_date_value = make_sure_datetime(printing_date_value)
                        mailing_date_value = make_sure_datetime(mailing_date_value)

                        if printing_date_value and mailing_date_value and (not status_column or not status_value or status_value.lower() != "cancelled"):
                            # Find a sticker from the Database and change its attributes
                            sticker = Sticker.objects.get(number=sticker_number_value)
                            sticker.printing_date = printing_date_value
                            sticker.mailing_date = mailing_date_value
                            sticker.sticker_printing_response = response
                            if sticker.status in (Sticker.STICKER_STATUS_AWAITING_PRINTING, Sticker.STICKER_STATUS_READY):
                                # sticker should not be in READY status though.
                                sticker.status = Sticker.STICKER_STATUS_CURRENT
                            sticker.save()
                        elif status_column and status_value and status_value.lower() == "cancelled":
                            sticker = Sticker.objects.get(number=sticker_number_value)
                            sticker.sticker_printing_response = response
                            if sticker.status in (Sticker.STICKER_STATUS_AWAITING_PRINTING, Sticker.STICKER_STATUS_READY, Sticker.STICKER_STATUS_EXPIRED, Sticker.STICKER_STATUS_LOST):
                                sticker.status = Sticker.STICKER_STATUS_CANCELLED
                            sticker.save()
                        process_summary['stickers'].append(sticker)

                        updates.append(sticker.number)
                    except Sticker.DoesNotExist as e:
                        err_msg = 'Error sticker {} not found to update'.format(sticker_number_value)
                        logger.exception('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)
                        response.no_errors_when_process = False
                        process_summary['errors'].append(err_msg)
                        response.processed = True  # Update response obj not to process again.  But from no_errors_when_process flag tells admin that there was an error.
                        response.save()
                        continue
                    except Exception as e:
                        err_msg = 'Error updating the sticker {}'.format(sticker_number_value)
                        logger.exception('{}\n{}'.format(err_msg, str(e)))
                        errors.append(err_msg)
                        response.no_errors_when_process = False
                        process_summary['errors'].append(err_msg)
                        response.processed = True  # Update response obj not to process again.  But from no_errors_when_process flag tells admin that there was an error.
                        response.save()
                        continue

                response.processed = True  # Update response obj not to process again
                response.save()

    return updates, errors


def send_sticker_import_batch_email(process_summary):
    try:
        email = TemplateEmailBase(
            subject='Sticker Import Batch',
            html_template='mooringlicensing/emails/send_sticker_import_batch.html',
            txt_template='mooringlicensing/emails/send_sticker_import_batch.txt',
        )

        attachments = []
        context = {
            'public_url': get_public_url(),
            'process_summary': process_summary,
        }

        from mooringlicensing.components.proposals.models import StickerPrintingContact
        tos = StickerPrintedContact.objects.filter(type=StickerPrintingContact.TYPE_EMIAL_TO, enabled=True)
        ccs = StickerPrintedContact.objects.filter(type=StickerPrintingContact.TYPE_EMAIL_CC, enabled=True)
        bccs = StickerPrintedContact.objects.filter(type=StickerPrintingContact.TYPE_EMAIL_BCC, enabled=True)

        if tos:
            to_address = [contact.email for contact in tos]
            cc = [contact.email for contact in ccs]
            bcc = [contact.email for contact in bccs]

            # Send email
            msg = email.send(to_address, context=context, attachments=attachments, cc=cc, bcc=bcc,)
            return msg

    except Exception as e:
        err_msg = 'Error sending sticker import email'
        logger.exception('{}\n{}'.format(err_msg, str(e)))

