import logging
from confy import env
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.generic import DetailView
from django.views.generic.base import TemplateView
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin

from mooringlicensing import settings
from mooringlicensing.helpers import is_internal, is_customer
from mooringlicensing.forms import *
from mooringlicensing.components.approvals.models import Approval, DcvAdmission, DcvPermit, Sticker
from mooringlicensing.components.proposals.models import Proposal, MooringBay
from mooringlicensing.components.compliances.models import Compliance
from mooringlicensing.components.main.models import JobQueue
from mooringlicensing.components.payments_ml.models import FeeSeason
from django.core.management import call_command
from django.db.models import Q
import os
import mimetypes
import json

logger = logging.getLogger(__name__)

class InternalView(UserPassesTestMixin, TemplateView):
    template_name = 'mooringlicensing/dash/index.html'

    def test_func(self):
        return is_internal(self.request)

    def get_context_data(self, **kwargs):
        context = super(InternalView, self).get_context_data(**kwargs)
        context['dev'] = settings.DEV_STATIC
        context['dev_url'] = settings.DEV_STATIC_URL
        if hasattr(settings, 'DEV_APP_BUILD_URL') and settings.DEV_APP_BUILD_URL:
            context['app_build_url'] = settings.DEV_APP_BUILD_URL
        return context


class ExternalView(LoginRequiredMixin, TemplateView):
    template_name = 'mooringlicensing/dash/index.html'

    def get_context_data(self, **kwargs):
        logger.info(f'Getting context in the ExternalView...')
        context = super(ExternalView, self).get_context_data(**kwargs)
        context['dev'] = settings.DEV_STATIC
        context['dev_url'] = settings.DEV_STATIC_URL
        if hasattr(settings, 'DEV_APP_BUILD_URL') and settings.DEV_APP_BUILD_URL:
            context['app_build_url'] = settings.DEV_APP_BUILD_URL
        return context


class ExternalProposalView(DetailView):
    model = Proposal
    template_name = 'mooringlicensing/dash/index.html'

class ExternalComplianceView(DetailView):
    model = Compliance
    template_name = 'mooringlicensing/dash/index.html'

class InternalComplianceView(DetailView):
    model = Compliance
    template_name = 'mooringlicensing/dash/index.html'


class MooringLicensingRoutingView(TemplateView):
    template_name = 'mooringlicensing/index.html'

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            if is_internal(self.request):
                return redirect('internal')
            return redirect('external')
        kwargs['form'] = LoginForm
        return super(MooringLicensingRoutingView, self).get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(MooringLicensingRoutingView, self).get_context_data(**kwargs)
        daily_admission_page_url = env('DAILY_ADMISSION_PAGE_URL', '')
        context.update({
            'daily_admission_page_url': daily_admission_page_url
        })
        return context


class MooringLicensingContactView(TemplateView):
    template_name = 'mooringlicensing/contact.html'


class MooringLicensingFurtherInformationView(TemplateView):
    template_name = 'mooringlicensing/further_info.html'


class InternalProposalView(DetailView):
    model = Proposal
    template_name = 'mooringlicensing/dash/index.html'

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            if is_internal(self.request):
                return super(InternalProposalView, self).get(*args, **kwargs)
            return redirect('external')
        kwargs['form'] = LoginForm
        return redirect('')


class LoginSuccess(TemplateView):
    template_name = 'mooringlicensing/login_success.html';

    def get(self, request, *args, **kwargs):
        context = {'LEDGER_UI_URL' : settings.LEDGER_UI_URL}
        response = render(request, self.template_name, context)
        return response


class ManagementCommandsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'mooringlicensing/mgt-commands.html'

    def test_func(self):
        return is_internal(self.request) and settings.ENABLE_MANAGEMENT_COMMANDS

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def post(self, request):
        data = {}
        command_script = request.POST.get('script', None)

        if command_script:
            logger.info('Running {}...'.format(command_script))
            call_command(command_script,)
            data.update({command_script: 'true'})

        return render(request, self.template_name, data)

class EmailExportsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'mooringlicensing/email_exports.html'

    def test_func(self):
        return is_internal(self.request)

    def get_context_data(self, **kwargs):
        context=super().get_context_data(**kwargs)
        context["proposal_type_options"] = Proposal.application_types_dict(apply_page=False)
        context["proposal_category_options"] = Proposal.application_categories_dict(apply_page=False)
        context["proposal_status_options"] = [{'code': i[0], 'description': i[1]} for i in Proposal.PROCESSING_STATUS_CHOICES]
        context["approval_type_options"] = Approval.approval_types_dict(['ml','aap','aup'])
        context["approval_status_options"] = [{'code': i[0], 'description': i[1]} for i in Approval.STATUS_CHOICES]
        context["compliance_status_options"] = [{'code': i[0], 'description': i[1]} for i in Compliance.PROCESSING_STATUS_CHOICES]
        context["mooring_bay_options"] = list(MooringBay.objects.filter(active=True).values("id","name"))
        context["mooring_status_options"] = ["Unlicensed","Licensed","Licence application"]
        context["dcv_permit_fee_seasons"] = list(FeeSeason.objects.filter(application_type__code='dcvp').values("id","name"))
        context["sticker_status_options"] = [{'id': i[0], 'display': i[1]} for i in Sticker.STATUS_CHOICES]
        context["sticker_fee_seasons"] = list(FeeSeason.objects.exclude(application_type__code__in=['dcvp','dcv']).distinct("name").values("name"))
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def post(self, request):
        context = self.get_context_data()
        export_model = request.POST.get('export_model', None)
        filters = request.POST.get('filters', None)
        format = request.POST.get('format', 'csv')
        num_records = request.POST.get('num_records', settings.MAX_NUM_ROWS_MODEL_EXPORT)

        try:
            num_records = min(int(num_records), settings.MAX_NUM_ROWS_MODEL_EXPORT)
        except:
            num_records = settings.MAX_NUM_ROWS_MODEL_EXPORT

        if export_model:
            parameters = {"model":export_model, "filters":filters, "format":format, "num_records": num_records}
            parameters_json = parameters
            #check if job with same params that is not completed/failed already exists - prevent needless duplicates
            if not JobQueue.objects.filter(job_cmd="email_exports", status__lt=2, parameters_json=parameters_json, user=request.user.id):
                JobQueue.objects.create(
                    job_cmd="email_exports",
                    status=0,
                    parameters_json=parameters_json,
                    user=request.user.id
                )
                context.update({"message": "{} data export shall be emailed to {} when ready.".format(export_model,request.user.email).capitalize()})
            else:
                context.update({"message": "{} data export for {} already in progress.".format(export_model,request.user.email).capitalize()})
        else:
            context.update({"message": "Export request failed."})

        return self.render_to_response(context)

def is_authorised_to_access_proposal_document(request,document_id):
    if is_internal(request):
        return True
    elif is_customer(request):
        user = request.user
        return Proposal.objects.filter(id=document_id).filter(
            Q(proposal_applicant__email_user_id=user.id)
        ).exists()
    
def is_authorised_to_access_approval_document(request,document_id):
    if is_internal(request):
        return True
    elif is_customer(request):
        user = request.user
        return Approval.objects.filter(id=document_id).filter(
            Q(current_proposal__proposal_applicant__email_user_id=user.id)
        ).exists()
    
def is_authorised_to_access_dcv_admission_document(request,document_id):
    if is_internal(request):
        return True
    elif is_customer(request):
        user = request.user
        return DcvAdmission.objects.filter(id=document_id).filter(applicant=user.id).exists()
    
def is_authorised_to_access_dcv_permit_document(request,document_id):
    if is_internal(request):
        return True
    elif is_customer(request):
        user = request.user
        return DcvPermit.objects.filter(id=document_id).filter(applicant=user.id).exists()
    
def get_file_path_id(check_str,file_path):
    file_name_path_split = file_path.split("/")
    #if the check_str is in the file path, the next value should be the id
    if check_str in file_name_path_split:
        id_index = file_name_path_split.index(check_str)+1
        if len(file_name_path_split) > id_index and file_name_path_split[id_index].isnumeric():
            return int(file_name_path_split[id_index])
        else:
            return False
    else:
        return False

def is_authorised_to_access_document(request):

    if is_internal(request):
        return True
    elif is_customer(request):
        p_document_id = get_file_path_id("proposals",request.path) or get_file_path_id("proposal",request.path)
        if p_document_id:
            return is_authorised_to_access_proposal_document(request,p_document_id)
        a_document_id = get_file_path_id("approvals",request.path) or get_file_path_id("approval",request.path)
        if a_document_id:
            return is_authorised_to_access_approval_document(request,a_document_id)
        da_document_id = get_file_path_id("dcv_admission",request.path)
        if da_document_id:
            return is_authorised_to_access_dcv_admission_document(request,da_document_id)
        dp_document_id = get_file_path_id("dcv_permit",request.path)
        if dp_document_id:
            return is_authorised_to_access_dcv_permit_document(request,dp_document_id)
        return False
    else:
        return False

def getPrivateFile(request):

    if is_authorised_to_access_document(request):
        file_name_path =  request.path
        #norm path will convert any traversal or repeat / in to its normalised form
        full_file_path= os.path.normpath(settings.BASE_DIR+file_name_path) 
        #we then ensure the normalised path is within the BASE_DIR (and the file exists)
        if full_file_path.startswith(settings.BASE_DIR) and os.path.isfile(full_file_path):
            extension = file_name_path.split(".")[-1].lower()
            the_file = open(full_file_path, 'rb')
            the_data = the_file.read()
            the_file.close()
            if extension == 'msg':
                return HttpResponse(the_data, content_type="application/vnd.ms-outlook")
            if extension == 'eml':
                return HttpResponse(the_data, content_type="application/vnd.ms-outlook")

            return HttpResponse(the_data, content_type=mimetypes.types_map['.'+str(extension)])

    return HttpResponse()