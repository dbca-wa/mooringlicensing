from django.core.files.storage import default_storage 
import os
from django.core.files.base import ContentFile
import traceback
#from mooringlicensing.components.main.models import TemporaryDocument
from django.conf import settings

from mooringlicensing.components.proposals.models import (
        Proposal
        )


def process_generic_document(request, instance, document_type=None, *args, **kwargs):
    print("process_generic_document")
    print(request.data)
    try:
        action = request.data.get('action')
        input_name = request.data.get('input_name')
        comms_log_id = request.data.get('comms_log_id')
        comms_instance = None

        if document_type == 'comms_log' and comms_log_id and comms_log_id != 'null':
            comms_instance = instance.comms_logs.get(id=comms_log_id)
        elif document_type == 'comms_log':
            comms_instance = instance.comms_logs.create()

        if action == 'list':
            pass
        elif action == 'delete':
            delete_document(request, instance, comms_instance, document_type, input_name)
        elif action == 'cancel':
            deleted = cancel_document(request, instance, comms_instance, document_type, input_name)
        elif action == 'save':
            save_document(request, instance, comms_instance, document_type, input_name)

        # HTTP Response varies by action and instance type
        if comms_instance and action == 'cancel' and deleted:
            return deleted
        elif comms_instance:
            returned_file_data = [dict(file=d._file.url, id=d.id, name=d.name,) for d in comms_instance.documents.all() if d._file]
            return {'filedata': returned_file_data, 'comms_instance_id': comms_instance.id}
        # example document_type
        elif input_name:
            if document_type == 'electoral_roll_document':
                documents_qs = instance.electoral_roll_documents
            elif document_type == 'vessel_registration_document':
                documents_qs = instance.vessel_registration_documents
            elif document_type == 'insurance_certificate_document':
                documents_qs = instance.insurance_certificate_documents
            elif document_type == 'hull_identification_number_document':
                documents_qs = instance.hull_identification_number_documents
            elif document_type == 'mooring_report_document':
                documents_qs = instance.mooring_report_documents
            elif document_type == 'written_proof_document':
                documents_qs = instance.written_proof_documents
            elif document_type == 'waiting_list_offer_document':
                documents_qs = instance.waiting_list_offer_documents
            returned_file_data = [dict(file=d._file.url, id=d.id, name=d.name,) for d in documents_qs.filter(input_name=input_name) if d._file]
            return { 'filedata': returned_file_data }
        else:
            returned_file_data = [dict(file=d._file.url, id=d.id, name=d.name, ) for d in instance.documents.all() if d._file]
            return {'filedata': returned_file_data}

    except Exception as e:
        print(traceback.print_exc())
        raise e


def delete_document(request, instance, comms_instance, document_type, input_name=None):
    # example document_type
    if 'document_id' in request.data:
        if document_type == 'electoral_roll_document':
            document_id = request.data.get('document_id')
            document = instance.electoral_roll_documents.get(id=document_id)
        elif document_type == 'vessel_registration_document':
            document_id = request.data.get('document_id')
            document = instance.vessel_registration_documents.get(id=document_id)
        elif document_type == 'insurance_certificate_document':
            document_id = request.data.get('document_id')
            document = instance.insurance_certificate_documents.get(id=document_id)
        elif document_type == 'hull_identification_number_document':
            document_id = request.data.get('document_id')
            document = instance.hull_identification_number_documents.get(id=document_id)
        elif document_type == 'mooring_report_document':
            document_id = request.data.get('document_id')
            document = instance.mooring_report_documents.get(id=document_id)
        elif document_type == 'written_proof_document':
            document_id = request.data.get('document_id')
            document = instance.written_proof_documents.get(id=document_id)
        elif document_type == 'waiting_list_offer_document':
            document_id = request.data.get('document_id')
            document = instance.waiting_list_offer_documents.get(id=document_id)

        #if document_type == DeedPollDocument.DOC_TYPE_NAME:
        #    document_id = request.data.get('document_id')
        #    document = instance.deed_poll_documents.get(id=document_id)
        #elif document_type == PublicLiabilityInsuranceDocument.DOC_TYPE_NAME:
        #    document_id = request.data.get('document_id')
        #    document = instance.public_liability_insurance_documents.get(id=document_id)
        #elif document_type == SupportingApplicationDocument.DOC_TYPE_NAME:
        #    document_id = request.data.get('document_id')
        #    document = instance.supporting_application_documents.get(id=document_id)

    # comms_log doc store delete
    elif comms_instance and 'document_id' in request.data:
        document_id = request.data.get('document_id')
        document = comms_instance.documents.get(id=document_id)

    # default doc store delete
    elif 'document_id' in request.data:
        document_id = request.data.get('document_id')
        document = instance.documents.get(id=document_id)

    if document._file and os.path.isfile(
            document._file.path):
        os.remove(document._file.path)

    if document:
        document.delete()


def cancel_document(request, instance, comms_instance, document_type, input_name=None):
        if document_type in [
                'electoral_roll_document', 
                'vessel_registration_document',
                'insurance_certificate_document',
                'hull_identification_number_document',
                'mooring_report_document',
                'written_proof_document',
                'waiting_list_offer_document',
                ]:
            document_id = request.data.get('document_id')
        #if document_type == DeedPollDocument.DOC_TYPE_NAME:
        #    document_list = instance.deed_poll_documents.all()
        #elif document_type == PublicLiabilityInsuranceDocument.DOC_TYPE_NAME:
        #    document_list = instance.public_liability_insurance_documents.all()
        #elif document_type == SupportingApplicationDocument.DOC_TYPE_NAME:
        #    document_list = instance.supporting_application_documents.all()
        if comms_instance:
            document_list = comms_instance.documents.all()
        else:
            document_list = instance.documents.all()

        for document in document_list:
            if document._file and os.path.isfile(document._file.path):
                os.remove(document._file.path)
            document.delete()

        if comms_instance:
            return comms_instance.delete()


def save_document(request, instance, comms_instance, document_type, input_name=None):
    #import ipdb; ipdb.set_trace()
    # Match model related_name to instance or comms_instance, eg.
    # sanction_outcome = models.ForeignKey(SanctionOutcome, related_name='documents')..
    # this document can be accessed or created by 'instance.documents'

    # example document_type
    if 'filename' in request.data and input_name:
        filename = request.data.get('filename')
        _file = request.data.get('_file')

        if document_type == 'electoral_roll_document':
            document = instance.electoral_roll_documents.get_or_create(input_name=input_name, name=filename)[0]
            path_format_string = '{}/proposals/{}/electoral_roll_documents/{}'
        if document_type == 'vessel_registration_document':
            document = instance.vessel_registration_documents.get_or_create(input_name=input_name, name=filename)[0]
            path_format_string = '{}/proposals/{}/vessel_registration_documents/{}'
        if document_type == 'insurance_certificate_document':
            document = instance.insurance_certificate_documents.get_or_create(input_name=input_name, name=filename)[0]
            path_format_string = '{}/proposals/{}/insurance_certificate_documents/{}'
        if document_type == 'hull_identification_number_document':
            document = instance.hull_identification_number_documents.get_or_create(input_name=input_name, name=filename)[0]
            path_format_string = '{}/proposals/{}/hull_identification_number_documents/{}'
        if document_type == 'mooring_report_document':
            document = instance.mooring_report_documents.get_or_create(input_name=input_name, name=filename)[0]
            path_format_string = '{}/proposals/{}/mooring_report_documents/{}'
        if document_type == 'written_proof_document':
            document = instance.written_proof_documents.get_or_create(input_name=input_name, name=filename)[0]
            path_format_string = '{}/proposals/{}/written_proof_documents/{}'
        if document_type == 'waiting_list_offer_document':
            document = instance.waiting_list_offer_documents.get_or_create(input_name=input_name, name=filename)[0]
            path_format_string = '{}/approvals/{}/waiting_list_offer_documents/{}'
        #if document_type == DeedPollDocument.DOC_TYPE_NAME:
        #    document = instance.deed_poll_documents.get_or_create(input_name=input_name, name=filename)[0]
        #    path_format_string = '{}/proposals/{}/deed_poll_documents/{}'
        #elif document_type == PublicLiabilityInsuranceDocument.DOC_TYPE_NAME:
        #    document = instance.public_liability_insurance_documents.get_or_create(input_name=input_name, name=filename)[0]
        #    path_format_string = '{}/proposals/{}/public_liability_insurance_documents/{}'
        #elif document_type == SupportingApplicationDocument.DOC_TYPE_NAME:
        #    document = instance.supporting_application_documents.get_or_create(input_name=input_name, name=filename)[0]
        #    path_format_string = '{}/proposals/{}/supporting_application_documents/{}'
        path = default_storage.save(path_format_string.format(settings.MEDIA_APP_DIR, instance.id, filename), ContentFile(_file.read()))
        document._file = path
        document.save()

    # comms_log doc store save
    elif comms_instance and 'filename' in request.data:
        filename = request.data.get('filename')
        _file = request.data.get('_file')

        document = comms_instance.documents.get_or_create(
            name=filename)[0]
        path = default_storage.save(
            '{}/{}/communications/{}/documents/{}'.format(
                instance._meta.model_name, instance.id, comms_instance.id, filename), ContentFile(
                _file.read()))

        document._file = path
        document.save()

    # default doc store save
    elif 'filename' in request.data:
        filename = request.data.get('filename')
        _file = request.data.get('_file')

        document = instance.documents.get_or_create(
            name=filename)[0]
        path = default_storage.save(
            '{}/{}/documents/{}'.format(
                instance._meta.model_name, instance.id, filename), ContentFile(
                _file.read()))

        document._file = path
        document.save()

