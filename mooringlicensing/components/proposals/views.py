from django.core.exceptions import ValidationError
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
from mooringlicensing import settings
from mooringlicensing.helpers import is_internal

from mooringlicensing.components.proposals.models import (
    Proposal,
    AuthorisedUserApplication, Mooring, 
    MooringLicenceApplication, 
    ProposalSiteLicenseeMooringRequest,
)

from rest_framework.permissions import IsAuthenticated

import logging
logger = logging.getLogger(__name__)

class MooringLicenceApplicationDocumentsUploadView(TemplateView):
    template_name = 'mooringlicensing/proposals/mooring_licence_application_documents_upload.html'
    permission_classes=[IsAuthenticated]

    def get_object(self):
        return get_object_or_404(MooringLicenceApplication, uuid=self.kwargs['uuid_str'])

    def get(self, request, *args, **kwargs):
        proposal = self.get_object()

        if is_internal(request) or proposal.proposal_applicant.email_user_id == request.user.id:

            if not (proposal.processing_status == Proposal.PROCESSING_STATUS_AWAITING_DOCUMENTS or
                proposal.processing_status == Proposal.PROCESSING_STATUS_DRAFT):
                raise ValidationError('You cannot upload documents for the application when it is not in awaiting-documents status')

            context = {
                'proposal': proposal,
                'dev': settings.DEV_STATIC,
                'dev_url': settings.DEV_STATIC_URL
            }

            if hasattr(settings, 'DEV_APP_BUILD_URL') and settings.DEV_APP_BUILD_URL:
                context['app_build_url'] = settings.DEV_APP_BUILD_URL

            return render(request, self.template_name, context)
        else:
            raise ValidationError('User not authorised to upload documents for mooring licence application')


class AuthorisedUserApplicationEndorseView(TemplateView):
    permission_classes=[IsAuthenticated]

    def get_object(self):
        return get_object_or_404(AuthorisedUserApplication, uuid=self.kwargs['uuid_str'])

    def get(self, request, *args, **kwargs):
        proposal = self.get_object()
        mooring_name = request.GET.get("mooring_name","")
        
        if not proposal.processing_status == Proposal.PROCESSING_STATUS_AWAITING_ENDORSEMENT:
            raise ValidationError('You cannot endorse/decline the application not in awaiting-endorsement status')
        
        # checking if the user holds an active mooring licence for the specified mooring
        try:
            mooring_status =  Mooring.objects.filter(
                mooring_licence__approval__current_proposal__proposal_applicant__email_user_id=request.user.id, 
                name=mooring_name,
                mooring_licence__status="current")
        except Exception as e:
            raise ValidationError('There is no mooring licence for this mooring')
        if(not mooring_status.exists()):
            raise ValidationError('You do not hold an active mooring site licence to endorse/decline the application')
        
        #get ProposalSiteLicenseeMooringRequest
        site_licensee_mooring_request = ProposalSiteLicenseeMooringRequest.objects.filter(proposal=proposal,
            mooring__name=mooring_name,
            site_licensee_email__iexact=request.user.email,
            enabled=True)
        if not site_licensee_mooring_request.exists():
            raise ValidationError('No valid site licensee mooring request for site licensee, mooring, and proposal set')

        action = self.kwargs['action']
        if action == 'endorse':
            self.template_name = 'mooringlicensing/proposals/authorised_user_application_endorsed.html'
            site_licensee_mooring_request.first().endorse_approved(request)
        elif action == 'decline':
            self.template_name = 'mooringlicensing/proposals/authorised_user_application_declined.html'
            site_licensee_mooring_request.first().endorse_declined(request)
        proposal.refresh_from_db()

        context = {
            'proposal': proposal,
        }

        return render(request, self.template_name, context)