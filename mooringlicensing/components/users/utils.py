from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.utils.encoding import smart_str

from mooringlicensing.components.users.models import EmailUserLogEntry, private_storage
from ledger_api_client.managed_models import SystemUser, SystemUserAddress
from ledger_api_client.ledger_models import EmailUserRO
from ledger_api_client.utils import get_or_create

from datetime import date

def get_or_create_system_user_system_user():
    """
    get the system user (model record) of the system user (the user for the system)
    """
    su_qs = SystemUser.objects.filter(email=settings.SYSTEM_EMAIL).order_by('-id')
    if su_qs.exists():
        return su_qs.first()
    else:
        eur_qs = EmailUserRO.objects.filter(email__iexact=settings.SYSTEM_EMAIL, is_active=True).order_by('-id')
        if eur_qs.exists():
            eur_qs = eur_qs.first()
            return create_system_user(eur_qs.id, settings.SYSTEM_EMAIL, "system", "system", date.today())
        else:
            new_email_user = get_or_create(settings.SYSTEM_EMAIL)
            return create_system_user(new_email_user.id, settings.SYSTEM_EMAIL, "system", "system", date.today())
        

def create_system_user(email_user_id, email, first_name, last_name, dob, phone=None, mobile=None):

    if email != settings.SYSTEM_EMAIL:
        system_user_system_user = get_or_create_system_user_system_user()

    system_user = SystemUser(
        ledger_id_id=email_user_id,
        email=email,
        legal_first_name=first_name,
        legal_last_name=last_name,
        legal_dob=dob,
        phone_number=phone,
        mobile_number=mobile,
    )
    if email != settings.SYSTEM_EMAIL:
        system_user.change_by_user_id = system_user_system_user.id   
    system_user.save()

    return system_user


def get_or_create_system_user_address(system_user, system_address_dict, use_for_postal=False, address_type='residential_address'):
    """
        takes SystemUser object and SystemUserAddress dict, 
        checks if a corresponding SystemUserAddress records exists, 
        and create that SystemUserAddress record if it does not exist
    """
    qs = SystemUserAddress.objects.filter(system_user=system_user, **system_address_dict)

    system_user_system_user = get_or_create_system_user_system_user()
 
    if not qs.exists():
        sua = SystemUserAddress(system_user=system_user, **system_address_dict, use_for_postal=use_for_postal)
        sua.address_type = address_type
        sua.change_by_user_id=system_user_system_user.id
        sua.save()
    elif use_for_postal and not qs.filter(use_for_postal=use_for_postal).exists():
        for i in qs:
            i.use_for_postal=True
            i.change_by_user_id = system_user_system_user.id
            i.save()
        

def get_or_create_system_user(email_user_id, email, first_name, last_name, dob, phone=None, mobile=None, update=False):
    qs = SystemUser.objects.filter(ledger_id_id=email_user_id)
    if qs.exists():
        system_user = qs.first()
        if update:    

            system_user_system_user = get_or_create_system_user_system_user()

            system_user.change_by_user_id = system_user_system_user.id       
            system_user.email = email
            system_user.legal_first_name = first_name
            system_user.legal_last_name = last_name
            system_user.legal_dob = dob
            system_user.phone_number = phone
            system_user.mobile_number = mobile
            system_user.save()
        return system_user, False 
    else:
        if EmailUserRO.objects.filter(id=email_user_id, is_active=True).order_by('-id').exists():
            try:
                system_user = create_system_user(email_user_id, email, first_name, last_name, dob, phone=phone, mobile=mobile)
                return system_user, True
            except:
                #update the existing record with the correct ledger id
                system_user_system_user = get_or_create_system_user_system_user()

                existing = SystemUser.objects.get(email=email)
                existing.change_by_user_id = system_user_system_user.id
                existing.ledger_id_id = email_user_id
                existing.save()
                return existing, False 
        else:
            raise Exception("Ledger Email User not Active")

def get_user_name(user):
    """
        return legal first name and legal last name over first name and last name if they exist
    """
    try:
        names = {"first_name":user.first_name,"last_name":user.last_name}
        if user.legal_first_name:
            names["first_name"] = user.legal_first_name
        if user.legal_last_name:
            names["last_name"] = user.legal_last_name
        names["full_name"] = names["first_name"] + " " + names["last_name"] 
    except:
        names = {"first_name":"unavailable","last_name":"unavailable","full_name":"unavailable"}

    return names

def _log_user_email(email_message, target_email_user, customer, sender=None, attachments=[]):
    if isinstance(email_message, (EmailMultiAlternatives, EmailMessage,)):
        text = email_message.body
        subject = email_message.subject
        fromm = smart_str(sender) if sender else smart_str(email_message.from_email)
        # the to email is normally a list
        if isinstance(email_message.to, list):
            to = ','.join(email_message.to)
        else:
            to = smart_str(email_message.to)
        # we log the cc and bcc in the same cc field of the log entry as a ',' comma separated string
        all_ccs = []
        if email_message.cc:
            all_ccs += list(email_message.cc)
        if email_message.bcc:
            all_ccs += list(email_message.bcc)
        all_ccs = ','.join(all_ccs)

    else:
        text = smart_str(email_message)
        subject = ''
        to = customer
        fromm = smart_str(sender) if sender else settings.SYSTEM_NAME_SHORT + ' Automated Message'
        all_ccs = ''

    customer = customer

    staff = sender

    kwargs = {
        'subject': subject,
        'text': text,
        'email_user_id': target_email_user if target_email_user else customer,
        'customer': customer,
        #'staff': staff,
        'to': to,
        'fromm': fromm,
        'cc': all_ccs
    }

    email_entry = EmailUserLogEntry.objects.create(**kwargs)

    for attachment in attachments:
        check = attachment[0].split(".")
        filename = attachment[0]
        if len(check) < 2 or check[len(check)-1] != "pdf":
            filename = attachment[0] + ".pdf"
        email_entry_document = email_entry.documents.create(name=filename)
        email_entry_document._file.save(filename, ContentFile(attachment[1]), save=False)
        email_entry_document.save()

    return None
