from io import BytesIO

from django.core.files.base import ContentFile

from mooringlicensing.doctopdf import create_dcv_permit_pdf_tytes, create_dcv_admission_pdf_bytes, \
    create_approval_doc_bytes, create_renewal_doc_bytes


def create_dcv_permit_document(dcv_permit):
    # create bytes
    contents_as_bytes = create_dcv_permit_pdf_tytes(dcv_permit)

    filename = 'dcv_permit-{}.pdf'.format(dcv_permit.lodgement_number)
    from mooringlicensing.components.approvals.models import DcvPermitDocument
    document = DcvPermitDocument.objects.create(dcv_permit=dcv_permit, name=filename)

    # Save the bytes to the disk
    document._file.save(filename, ContentFile(contents_as_bytes), save=True)

    return document


def create_dcv_admission_document(dcv_admission_arrival):
    # create bytes
    contents_as_bytes = create_dcv_admission_pdf_bytes(dcv_admission_arrival)

    filename = 'dcv_admission-{}.pdf'.format(dcv_admission_arrival.dcv_admission.lodgement_number)
    from mooringlicensing.components.approvals.models import DcvAdmissionDocument
    document = DcvAdmissionDocument.objects.create(dcv_admission=dcv_admission_arrival.dcv_admission, name=filename)

    # Save the bytes to the disk
    document._file.save(filename, ContentFile(contents_as_bytes), save=True)

    return document


def create_approval_doc(approval):
    # create bytes
    contents_as_bytes = create_approval_doc_bytes(approval)

    filename = 'approval-{}.pdf'.format(approval.lodgement_number)
    from mooringlicensing.components.approvals.models import ApprovalDocument
    document = ApprovalDocument.objects.create(approval=approval, name=filename)

    # Save the bytes to the disk
    document._file.save(filename, ContentFile(contents_as_bytes), save=True)

    return document


def create_renewal_doc(approval, proposal):
    # create bytes
    contents_as_bytes = create_renewal_doc_bytes(approval)

    filename = 'renewal-{}-{}.pdf'.format(approval.lodgement_number, proposal.lodgement_number)
    from mooringlicensing.components.approvals.models import RenewalDocument
    document = RenewalDocument.objects.create(approval=approval, name=filename,)

    # Save the bytes to the disk
    document._file.save(filename, ContentFile(contents_as_bytes), save=True)
    return document

