from __future__ import unicode_literals
# from ledger.accounts.models import EmailUser
from django.conf import settings

import logging

from rest_framework import serializers
logger = logging.getLogger(__name__)

def belongs_to(user, group_name):
    """
    Check if the user belongs to the given group.
    :param user:
    :param group_name:
    :return:
    """
    return user.groups.filter(name=group_name).exists()

def is_model_backend(request):
    # Return True if user logged in via single sign-on (i.e. an internal)
    return 'ModelBackend' in request.session.get('_auth_user_backend')

def is_email_auth_backend(request):
    # Return True if user logged in via social_auth (i.e. an external user signing in with a login-token)
    return 'EmailAuth' in request.session.get('_auth_user_backend')

def is_mooringlicensing_admin(request):
    return request.user.is_authenticated() and is_model_backend(request) and in_dbca_domain(request) and (belongs_to(request.user, settings.ADMIN_GROUP))

def in_dbca_domain(request):
    user = request.user
    domain = user.email.split('@')[1]
    if domain in settings.DEPT_DOMAINS:
        if not user.is_staff:
            # hack to reset department user to is_staff==True, if the user logged in externally (external departmentUser login defaults to is_staff=False)
            user.is_staff = True
            user.save()
        return True
    return False

def is_in_organisation_contacts(request, organisation):
    return request.user.email in organisation.contacts.all().values_list('email', flat=True)

def is_departmentUser(request):
    return request.user.is_authenticated() and is_model_backend(request) and in_dbca_domain(request)

def is_customer(request):
    return request.user.is_authenticated() and (is_model_backend(request) or is_email_auth_backend(request))

def is_internal(request):
    return is_departmentUser(request)

def is_authorised_to_modify(request, instance):
    authorised = True

    if is_customer(request):
        # the status of the application must be DRAFT for customer to modify
        authorised &= instance.processing_status in ['draft', 'awaiting_documents', 'printing_sticker']
        # the applicant and submitter must be the same
        authorised &= request.user.email == instance.applicant_email

    if not authorised:
        raise serializers.ValidationError('You are not authorised to modify this application.')


    # authorised = True

    # if is_internal(request):
    #     # the status must be 'with_assessor'
    #     authorised &= instance.processing_status == 'with_assessor'
    #     # the user must be an assessor for this type of application
    #     authorised &= instance.can_process()
    # elif is_customer(request):
    #     # the status of the application must be DRAFT for customer to modify
    #     authorised &= instance.processing_status == 'draft'

    #     applicantType = instance.applicant_type
    #     # Applicant is individual
    #     if applicantType == 'SUB':
    #         authorised &= instance.submitter != request.user.email
    #     # the application org and submitter org must be the same
    #     else:
    #         authorised &= is_in_organisation_contacts(request, instance.org_applicant)

    # if not authorised:
    #     raise serializers.ValidationError('You are not authorised to modify this application.')