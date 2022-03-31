import datetime
import imaplib
import email
import ssl
import openpyxl
from django.utils import timezone

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

logger = logging.getLogger('cron_tasks')


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
            raise Exception('Configure email settings at .env to process sticker responses')

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

        # msg_list = []

        for num in datas[len(datas) - fetch_num::]:
            try:
                ##########
                # 2. Save the attached files into the database
                ##########
                typ, data = imapclient.fetch(num, '(RFC822)')
                # typ, data = imapclient.fetch(num, '(BODY[HEADER.FIELDS (MESSAGE-ID)])')
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

                # downloading attachments
                for part in email_message.walk():
                    try:
                        # this part comes from the snipped I don't understand yet...
                        if part.get_content_maintype() == 'multipart':
                            continue
                        if part.get('Content-Disposition') is None:
                            continue
                        fileName = part.get_filename()
                        if bool(fileName) and fileName.lower().endswith('.xlsx'):
                            now = timezone.localtime(timezone.now())

                            # Create sticker_printing_response object. File is not saved yet
                            sticker_printing_response = StickerPrintingResponse.objects.create(
                                sticker_printing_response_email=sticker_printing_response_email,
                                name=fileName,
                            )

                            # Load attachment file
                            my_bytes = part.get_payload(decode=True)
                            content_file = ContentFile(my_bytes)

                            # Save file
                            sticker_printing_response._file.save(fileName, content_file)
                    except Exception as e:
                        logger.exception('Exception has been raised when importing .xlsx file')
                        continue

                # imapclient.store(num, "+FLAGS", "\\Deleted")
                imapclient.copy(num, "Archive")
                imapclient.store(num, "+FLAGS", "\\Deleted")
            except:
                logger.exception('Exception has been raised when processing emails')
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
        # error_count = len(errors) + len(error_filenames)
        error_count = len(errors)
        err_str = '<strong style="color: red;">Errors: {}</strong>'.format(error_count) if error_count else '<strong style="color: green;">Errors: 0</strong>'
        msg = '<p>{} completed. {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        logger.info(msg)
        print(msg)  # will redirect to run_cron_tasks.log file, by the parent script


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
                batch_date_column, sticker_number_column, printing_date_column, mailing_date_column = 0, 0, 0, 0
                for row in ws.rows:
                    for cell in row:
                        if 'batch' in cell.value.lower() and 'date' in cell.value.lower():
                            batch_date_column = cell.column  # 1-based
                            header_row = cell.row  # 1-based
                        elif 'sticker' in cell.value.lower() and 'number' in cell.value.lower():
                            sticker_number_column = cell.column
                        elif 'printing' in cell.value.lower() and 'date' in cell.value.lower():
                            printing_date_column = cell.column
                        elif 'mailing' in cell.value.lower() and 'date' in cell.value.lower():
                            mailing_date_column = cell.column
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
                    batch_date_value = row[batch_date_column - 1].value  # [] is index, therefore minus 1
                    sticker_number_value = row[sticker_number_column - 1].value
                    printing_date_value = row[printing_date_column - 1].value
                    mailing_date_value = row[mailing_date_column - 1].value

                    batch_date_value = make_sure_datetime(batch_date_value)
                    sticker_number_value = make_sure_sticker_number(sticker_number_value)
                    printing_date_value = make_sure_datetime(printing_date_value)
                    mailing_date_value = make_sure_datetime(mailing_date_value)

                    # Find a sticker from the Database and change its attributes
                    sticker = Sticker.objects.get(number=sticker_number_value)
                    sticker.printing_date = printing_date_value
                    sticker.mailing_date = mailing_date_value
                    sticker.sticker_printing_response = response
                    if sticker.status in (Sticker.STICKER_STATUS_AWAITING_PRINTING, Sticker.STICKER_STATUS_READY):
                        # sticker should not be in READY status though.
                        sticker.status = Sticker.STICKER_STATUS_CURRENT
                        #if sticker.sticker_to_replace:  # new sticker has the old sticker here if it's created for renewal
                        #    # When this sticker is created for renewal, set 'expiry' status to the old sticker.
                        #    sticker.sticker_to_replace.status = Sticker.STICKER_STATUS_EXPIRED
                        #    sticker.sticker_to_replace.save()
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
        else:
            # No fild is saved in the _file field
            pass

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

