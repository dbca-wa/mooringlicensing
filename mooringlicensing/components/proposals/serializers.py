import logging
from django.db.models import Q
from ledger_api_client.settings_base import TIME_ZONE
import pytz
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from ledger_api_client.ledger_models import Invoice

from mooringlicensing.components.proposals.models import (
    Proposal,
    ProposalUserAction,
    ProposalLogEntry,
    VesselLogEntry,
    MooringLogEntry,
    ProposalRequirement,
    ProposalStandardRequirement,
    ProposalDeclinedDetails,
    AmendmentRequest,
    VesselDetails,
    VesselOwnership,
    Vessel,
    MooringBay,
    ProposalType,
    Company,
    CompanyOwnership,
    Mooring, MooringLicenceApplication, AuthorisedUserApplication,
    ProposalSiteLicenseeMooringRequest,
    MooringUserAction
)
from mooringlicensing.components.main.models import GlobalSettings
from mooringlicensing.ledger_api_utils import retrieve_email_userro
from mooringlicensing.components.approvals.models import MooringLicence, MooringOnApproval, Approval, VesselOwnershipOnApproval
from mooringlicensing.components.main.serializers import CommunicationLogEntrySerializer
from mooringlicensing.components.users.serializers import UserSerializer, ProposalApplicantSerializer
from ledger_api_client.managed_models import SystemUser
from rest_framework import serializers
from mooringlicensing.helpers import is_internal, is_system_admin
from mooringlicensing.settings import PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_NEW, PROPOSAL_TYPE_RENEWAL
from mooringlicensing.ledger_api_utils import retrieve_system_user
from mooringlicensing.components.users.utils import get_user_name

logger = logging.getLogger(__name__)


class ProposalTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProposalType
        fields = (
            'id',
            'code',
            'description',
        )


class CompanySerializer(serializers.ModelSerializer):

    class Meta:
        model = Company
        fields = (
                'id',
                'name',
                )


class CompanyOwnershipSerializer(serializers.ModelSerializer):
    company = CompanySerializer()
    percentage = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = CompanyOwnership
        fields = (
                'id',
                'blocking_proposal',
                'vessel',
                'company',
                'percentage',
                'created',
                'updated',
                )

    def validate_percentage(self, value):
        if not value:
            return 0
        try:
            return int(value)
        except ValueError:
            raise serializers.ValidationError('You must supply an integer value.')


class MooringSerializer(serializers.ModelSerializer):
    mooring_bay_name = serializers.SerializerMethodField()

    class Meta:
        model = Mooring
        fields = '__all__'

    def get_mooring_bay_name(self, obj):
        return obj.mooring_bay.name


class MooringSimpleSerializer(serializers.ModelSerializer):
    mooring_bay_name = serializers.CharField(source='mooring_bay.name')

    class Meta:
        model = Mooring
        fields = (
            'name',
            'mooring_bay_name',
        )


class BaseProposalSerializer(serializers.ModelSerializer):
    readonly = serializers.SerializerMethodField(read_only=True)
    documents_url = serializers.SerializerMethodField()
    allowed_assessors = serializers.SerializerMethodField()
    get_history = serializers.ReadOnlyField()
    application_type_code = serializers.SerializerMethodField()
    application_type_text = serializers.SerializerMethodField()
    approval_type_text = serializers.SerializerMethodField()
    application_type_dict = serializers.SerializerMethodField()
    proposal_type = ProposalTypeSerializer()
    invoices = serializers.SerializerMethodField()
    start_date = serializers.ReadOnlyField()
    previous_application_vessel_details_id = serializers.SerializerMethodField()
    previous_application_preferred_bay_id = serializers.SerializerMethodField()
    current_vessels_rego_list = serializers.SerializerMethodField()
    approval_lodgement_number = serializers.SerializerMethodField()
    approval_vessel_rego_no = serializers.SerializerMethodField()
    waiting_list_application_id = serializers.SerializerMethodField()
    authorised_user_moorings_str = serializers.SerializerMethodField()
    previous_application_vessel_details_obj = serializers.SerializerMethodField()
    previous_application_vessel_ownership_obj = serializers.SerializerMethodField()
    approval_reissued = serializers.SerializerMethodField()
    vessel_on_proposal = serializers.SerializerMethodField()
    proposal_applicant = ProposalApplicantSerializer()
    uuid = serializers.SerializerMethodField()
    amendment_requests = serializers.SerializerMethodField()
    site_licensee_moorings = serializers.SerializerMethodField()
    previous_application_insurance_choice = serializers.SerializerMethodField()
    stat_dec_form = serializers.SerializerMethodField()
    can_user_bypass_payment = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = (
                'id',
                'start_date',
                'application_type_code',
                'application_type_text',
                'approval_type_text',
                'application_type_dict',
                'proposal_type',
                'title',
                'customer_status',
                'processing_status',
                'applicant',
                'assigned_officer',
                'lodgement_date',
                'documents',
                'requirements',
                'readonly',
                'can_user_edit',
                'can_user_cancel_payment',
                'can_user_bypass_payment',
                'can_user_view',
                'documents_url',
                'lodgement_number',
                'can_officer_process',
                'allowed_assessors',
                'pending_amendment_request',
                'fee_paid',
                'invoices',
                'rego_no',
                'vessel_id',
                'vessel_details_id',
                'vessel_ownership_id',
                'vessel_type',
                'vessel_name',
                'vessel_length',
                'vessel_draft',
                'vessel_beam',
                'vessel_weight',
                'berth_mooring',
                'dot_name',
                'percentage',
                'individual_owner',
                'insurance_choice',
                'preferred_bay_id',
                'silent_elector',
                'bay_preferences_numbered',
                'site_licensee_moorings',
                'mooring_authorisation_preference',
                'company_ownership_name',
                'company_ownership_percentage',
                'previous_application_id',
                'previous_application_vessel_details_id',
                'previous_application_preferred_bay_id',
                'previous_application_insurance_choice',
                'current_vessels_rego_list',
                'approval_lodgement_number',
                'approval_vessel_rego_no',
                'waiting_list_application_id',
                'authorised_user_moorings_str',
                'temporary_document_collection_id',
                'previous_application_vessel_details_obj',
                'previous_application_vessel_ownership_obj',
                'keep_existing_mooring',
                'keep_existing_vessel',
                'approval_reissued',
                'vessel_on_proposal',
                'null_vessel_on_create',
                'proposal_applicant',
                'uuid',
                'amendment_requests',
                'auto_approve',
                'stat_dec_form',
                )
        read_only_fields=('documents','auto_approve')

    def get_can_user_bypass_payment(self, obj):

        if 'request' in self.context and is_internal(self.context['request']):
            return (obj.customer_status == Proposal.CUSTOMER_STATUS_AWAITING_PAYMENT and is_system_admin(self.context['request']))
        else:
            return False

    def get_site_licensee_moorings(self, obj):

        site_licensee_moorings = []
        for i in obj.site_licensee_mooring_request.filter(enabled=True):
            if i.mooring:
                site_licensee_moorings.append(
                    {
                    "email":i.site_licensee_email, 
                    "mooring_name":i.mooring.name,
                    "mooring_id":i.mooring.id
                    }
                )

        return site_licensee_moorings

    def get_amendment_requests(self, obj):
        data = None
        if obj.proposalrequest_set.count():
            amendment_requests = obj.proposalrequest_set.all()
            serializer = AmendmentRequestSerializer(amendment_requests, many=True)
            data = serializer.data
        return data

    def get_uuid(self, obj):
        if hasattr(obj.child_obj, 'uuid'):
            return obj.child_obj.uuid
        else:
            return ''

    def get_allowed_assessors(self, obj):
        if 'request' in self.context and is_internal(self.context['request']):
            email_user_ids = list(obj.allowed_assessors.values_list("id",flat=True))
            system_users = SystemUser.objects.filter(ledger_id__id__in=email_user_ids)
            serializer = UserSerializer(system_users, many=True)
            return serializer.data
        else:
            return None

    def get_vessel_on_proposal(self, obj):
        return obj.vessel_on_proposal()

    def get_approval_reissued(self, obj):
        reissue = False
        if obj.approval:
            reissue = obj.approval.reissued
        return reissue

    def get_previous_application_vessel_details_obj(self, obj):
        if (obj.previous_application and obj.previous_application.vessel_details):
            return VesselDetailsSerializer(obj.previous_application.vessel_details).data

    def get_previous_application_vessel_ownership_obj(self, obj):
        if (obj.previous_application and obj.previous_application.vessel_details):
            return VesselOwnershipSerializer(obj.previous_application.vessel_ownership).data

    def get_authorised_user_moorings_str(self, obj):
        if type(obj.child_obj) == AuthorisedUserApplication and obj.approval:
            moorings_str = ''
            moorings_str += ', '.join([mooring.name for mooring in obj.listed_moorings.all()])
            return moorings_str

    def get_waiting_list_application_id(self, obj):
        wla_id = None
        if obj.waiting_list_allocation:
            wla_id = obj.waiting_list_allocation.current_proposal.id
        return wla_id

    def get_approval_vessel_rego_no(self, obj):
        rego_no = None
        if obj.approval and type(obj.approval) is not MooringLicence:
            rego_no = (obj.approval.current_proposal.vessel_details.vessel.rego_no if
                    obj.approval and obj.approval.current_proposal and obj.approval.current_proposal.vessel_details and
                    not obj.approval.current_proposal.vessel_ownership.end_date
                    else None)
        return rego_no

    def get_approval_lodgement_number(self, obj):
        lodgement_number = None
        if obj.approval:
            lodgement_number = obj.approval.lodgement_number
        return lodgement_number

    def get_current_vessels_rego_list(self, obj):
        if obj.approval and type(obj.approval.child_obj) is MooringLicence:
            vessels_str = ''
            vessels_str += ', '.join([vo.vessel.rego_no for vo in obj.listed_vessels.filter(end_date__isnull=True)])

            if not vessels_str and obj.approval and obj.approval.reissued:
                voas = VesselOwnershipOnApproval.objects.filter(approval=obj.approval,end_date__isnull=True).distinct("vessel_ownership__vessel__rego_no")
                vessels_str += ', '.join([voa.vessel_ownership.vessel.rego_no for voa in voas])

            return vessels_str

    def get_previous_application_preferred_bay_id(self, obj):
        preferred_bay_id = None
        if obj.previous_application and obj.previous_application.preferred_bay:
            preferred_bay_id = obj.previous_application.preferred_bay.id
        return preferred_bay_id

    def get_previous_application_vessel_details_id(self, obj):
        vessel_details_id = None
        if obj.previous_application and obj.previous_application.vessel_details:
            vessel_details_id = obj.previous_application.vessel_details.id
        return vessel_details_id

    def get_application_type_code(self, obj):
        return obj.application_type_code

    def get_approval_type_text(self, obj):
        return obj.approval.child_obj.description if obj.approval else None

    def get_application_type_text(self, obj):
        return obj.child_obj.description

    def get_application_type_dict(self, obj):
        return {
            'code': obj.child_obj.code,
            'description': obj.child_obj.description,
        }

    def get_documents_url(self,obj):
        return '/private-media/{}/proposals/{}/documents/'.format(settings.MEDIA_APP_DIR, obj.id)

    def get_readonly(self,obj):
        return False

    def get_processing_status(self,obj):
        return obj.get_processing_status_display()

    def get_customer_status(self,obj):
        return obj.get_customer_status_display()

    def get_fee_invoice_references(self, obj):
        ret_list = list(obj.application_fees.filter(cancelled=False).values_list('invoice_reference', flat=True))
        return ret_list

    def get_invoices(self, obj):
        if ('request' in self.context and 
        (
            is_internal(self.context['request']) or
            (obj.proposal_applicant and obj.proposal_applicant.email_user_id == self.context['request'].user.id)
        )):
            invoice_references = list(obj.application_fees.filter(cancelled=False).values_list('invoice_reference', flat=True))
            invoices = Invoice.objects.filter(reference__in=invoice_references)
            if not invoices:
                return ''
            else:
                inv_props = obj.get_invoice_property_cache()
                invoice_data = []
                for invoice in inv_props:
                    invoice_data.append(
                        {
                            'id': invoice,
                            'amount':inv_props[invoice]['amount'],
                            'reference':inv_props[invoice]['reference'],
                            'payment_status':inv_props[invoice]['payment_status'],
                            'settlement_date':inv_props[invoice]['settlement_date'],
                            'invoice_url':f'/ledger-toolkit-api/invoice-pdf/{inv_props[invoice]['reference']}/',
                            'ledger_payment_url':f'{settings.LEDGER_UI_URL}/ledger/payments/oracle/payments?invoice_no={inv_props[invoice]['reference']}',
                        }
                    )

                return invoice_data
        return ''
    
    def get_previous_application_insurance_choice(self, obj):
        if (obj.previous_application and obj.previous_application.insurance_choice):
            return obj.previous_application.insurance_choice

    def get_stat_dec_form(self, obj):
        try:
            return GlobalSettings.objects.get(key=GlobalSettings.KEY_STAT_DEC_FORM)._file.url
        except:
            return ""

class ListProposalSiteLicenseeMooringRequestSerializer(serializers.ModelSerializer):
    
    can_endorse = serializers.SerializerMethodField()
    proposal_number = serializers.SerializerMethodField()
    mooring_name = serializers.SerializerMethodField()
    proposal_status = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()
    uuid = serializers.SerializerMethodField()

    class Meta:
        model = ProposalSiteLicenseeMooringRequest
        fields = (
            'id',
            'site_licensee_email',
            'declined_by_endorser',
            'proposal_id',
            'proposal_number',
            'mooring_name',
            'proposal_status',
            'can_endorse',
            'applicant_name',
            'uuid',
            'approved_by_endorser',
            'declined_by_endorser',
        )
        datatables_always_serialize = (
            'id',
            'proposal_id',
            'uuid',
            'can_endorse',
            'approved_by_endorser',
            'declined_by_endorser',
        )

    def get_uuid(self, obj):
        try:
            return obj.proposal.child_obj.uuid
        except:
            return ''

    def get_applicant_name(self,obj):
        if obj.proposal and obj.proposal.proposal_applicant:
            return obj.proposal.proposal_applicant.first_name + " " + obj.proposal.proposal_applicant.last_name

    def get_proposal_number(self,obj):
        if obj.proposal:
            return obj.proposal.lodgement_number
        
    def get_mooring_name(self,obj):
        if obj.mooring:
            return obj.mooring.name
        
    def get_proposal_status(self,obj):
        if obj.proposal:
            return obj.proposal.get_customer_status_display()

    def get_can_endorse(self,obj):
        if (obj.mooring and 
            obj.mooring.mooring_licence and
            obj.mooring.mooring_licence.approval and
            obj.mooring.mooring_licence.approval.status == "current"):
            return True
        return False


class ListProposalSerializer(BaseProposalSerializer):
    submitter = serializers.SerializerMethodField(read_only=True)
    applicant = serializers.SerializerMethodField(read_only=True)
    processing_status = serializers.SerializerMethodField()
    customer_status = serializers.SerializerMethodField()
    assigned_officer = serializers.SerializerMethodField()
    assigned_approver = serializers.SerializerMethodField()
    application_type_dict = serializers.SerializerMethodField()

    assessor_process = serializers.SerializerMethodField()
    uuid = serializers.SerializerMethodField()
    document_upload_url = serializers.SerializerMethodField()
    can_view_payment_details = serializers.SerializerMethodField()
    invoice_links = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = (
            'id',
            'migrated',
            'application_type_dict',
            'proposal_type',
            'customer_status',
            'processing_status',
            'applicant',
            'submitter',
            'assigned_officer',
            'assigned_approver',
            'lodgement_date',
            'can_user_edit',
            'can_user_cancel_payment',
            'can_user_bypass_payment',
            'can_user_view',
            'lodgement_number',
            'assessor_process',
            'invoices',
            'uuid',
            'document_upload_url',
            'can_view_payment_details',
            'invoice_links',
            'mooring_authorisation_preference',
        )
        # the serverSide functionality of datatables is such that only columns that have field 'data' defined are requested from the serializer. We
        # also require the following additional fields for some of the mRender functions
        datatables_always_serialize = (
            'id',
            'migrated',
            'proposal_type',
            'customer_status',
            'application_type_dict',
            'processing_status',
            'applicant',
            'submitter',
            'assigned_officer',
            'assigned_approver',
            'lodgement_date',
            'can_user_edit',
            'can_user_cancel_payment',
            'can_user_bypass_payment',
            'can_user_view',
            'lodgement_number',
            'assessor_process',
            'invoices',
            'uuid',
            'document_upload_url',
            'can_view_payment_details',
            'invoice_links',
            'mooring_authorisation_preference',
        )

    def get_submitter(self, obj):
        request = self.context.get("request")
        if obj.submitter and is_internal(request):             
            user = retrieve_system_user(obj.submitter)
            return UserSerializer(user).data
        else:
            return ""
        
    def get_applicant(self, obj):
        try:
            if obj.proposal_applicant:
                user = retrieve_system_user(obj.proposal_applicant.email_user_id)
                return UserSerializer(user).data
            else:
                return ""
        except:
            return ""

    def get_invoice_links(self, proposal):
        links = ""
        if ('request' in self.context and 
        (
            is_internal(self.context['request']) or
            (proposal.proposal_applicant and proposal.proposal_applicant.email_user_id == self.context['request'].user.id)
        )):       
            invoice_property_cache = proposal.get_invoice_property_cache()
            # pdf
            try:
                for invoice in invoice_property_cache:
                    url = f'/ledger-toolkit-api/invoice-pdf/{invoice_property_cache[invoice]["reference"]}/'
                    links += f"<div><a href='{url}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> #{invoice_property_cache[invoice]["reference"]}</a></div>"

                if self.context.get('request') and is_internal(self.context.get('request')): #and proposal.application_fees.filter(cancelled=False):
                    # paid invoices url
                    invoices_str=''
                    for inv in invoice_property_cache:
                        if invoice_property_cache[invoice]["reference"]:
                            invoices_str += 'invoice_no={}&'.format(invoice_property_cache[invoice]["reference"])
                    if invoices_str:
                        invoices_str = invoices_str[:-1]
                        links += "<div><a href='{}/ledger/payments/oracle/payments?{}' target='_blank'>Ledger Payment</a></div>".format(settings.LEDGER_UI_URL, invoices_str)
            except:
                return links
        return links

    def get_can_view_payment_details(self, proposal):
        if 'request' in self.context:
            from mooringlicensing.components.main.utils import is_payment_officer
            return is_payment_officer(self.context['request'].user)

    def get_document_upload_url(self, proposal):
        if proposal.application_type.code == MooringLicenceApplication.code and proposal.processing_status == Proposal.PROCESSING_STATUS_AWAITING_DOCUMENTS:
            request = self.context['request']
            return proposal.child_obj.get_document_upload_url(request)
        return ''

    def get_uuid(self, obj):
        try:
            return obj.child_obj.uuid
        except:
            return ''

    def get_assigned_officer(self,obj):
        if obj.assigned_officer:
            return retrieve_email_userro(obj.assigned_officer).get_full_name() if obj.assigned_officer else ''
        return None

    def get_assigned_approver(self,obj):
        if obj.assigned_approver:
            return retrieve_email_userro(obj.assigned_approver).get_full_name() if obj.assigned_approver else ''
        return None

    def get_assessor_process(self,obj):
        # Check if currently logged in user has access to process the proposal
        request = self.context['request']
        user = request.user
        if obj.can_officer_process:
            '''if (obj.assigned_officer and obj.assigned_officer == user) or (user in obj.allowed_assessors):
                return True'''
            if obj.assigned_officer:
                if obj.assigned_officer == user.id:
                    return True
            elif user in obj.allowed_assessors:
                return True
        return False


class ProposalForEndorserSerializer(BaseProposalSerializer):
    for_endorser = serializers.SerializerMethodField()
    readonly = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = (
            'id',
            'for_endorser',
            'readonly',
            'application_type_code',
            'application_type_text',
            'approval_type_text',
            'application_type_dict',
            'proposal_type',
            'title',
            'customer_status',
            'processing_status',
            'applicant',
            'assigned_officer',
            #'get_history',
            'lodgement_date',
            #'modified_date',
            'documents',
            'requirements',
            'readonly',
            'can_user_edit',
            'can_user_cancel_payment',
            'can_user_view',
            'documents_url',
            'lodgement_number',
            'can_officer_process',
            'allowed_assessors',
            'pending_amendment_request',
            'vessel_type',
            'vessel_length',
            'vessel_draft',
            'vessel_beam',
            'vessel_weight',
            'berth_mooring',
            'dot_name',
            'insurance_choice',
            'mooring_authorisation_preference',
            'company_ownership_name',
            'company_ownership_percentage',
            'previous_application_id',
            'previous_application_vessel_details_id',
            'previous_application_preferred_bay_id',
            'current_vessels_rego_list',
            'approval_lodgement_number',
            'approval_vessel_rego_no',
            'waiting_list_application_id',
            'authorised_user_moorings_str',
            'previous_application_vessel_details_obj',
            'previous_application_vessel_ownership_obj',
            'keep_existing_mooring',
            'keep_existing_vessel',
            'approval_reissued',
            'vessel_on_proposal',
            'null_vessel_on_create',
            'proposal_applicant',
            'uuid',
            'amendment_requests',
        )

    def get_readonly(self, obj):
        return True
        
    def get_for_endorser(self, obj):
        return True


class ProposalSerializer(BaseProposalSerializer):
    processing_status = serializers.SerializerMethodField(read_only=True)
    customer_status = serializers.SerializerMethodField(read_only=True)

    def get_readonly(self,obj):
        return obj.can_user_view


class SaveWaitingListApplicationSerializer(serializers.ModelSerializer):
    preferred_bay_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Proposal
        fields = (
                'id',
                'preferred_bay_id',
                'silent_elector',
                'temporary_document_collection_id',
                'keep_existing_vessel',
                )
        read_only_fields=('id',)

    def validate(self, data):
        custom_errors = {}
        proposal_type_new = ProposalType.objects.get(code=PROPOSAL_TYPE_NEW)
        if self.instance.proposal_type != proposal_type_new:
            if self.instance.previous_application.preferred_bay_id != data.get('preferred_bay_id'):
                custom_errors["Preferred bay"] = "You can not change a preferred bay"
        if self.context.get("action") == 'submit':
            if not data.get("preferred_bay_id"):
                custom_errors["Mooring Details"] = "You must choose a mooring bay"
            # electoral roll validation
            if 'silent_elector' not in data.keys():
                custom_errors["Electoral Roll"] = "You must complete this section"
            elif data.get("silent_elector"):
                if not self.instance.electoral_roll_documents.all():
                    custom_errors["Silent Elector"] = "You must provide evidence of this"
            
            # When company ownership, vessel registration document is compulsory
            if self.instance.vessel_ownership  and not self.instance.vessel_ownership.individual_owner:
                if not self.instance.vessel_ownership.vessel_registration_documents.count():
                    custom_errors["Copy of registration papers"] = "You must provide evidence of this"

        if custom_errors.keys():
            raise serializers.ValidationError(custom_errors)
        return data


class SaveAnnualAdmissionApplicationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Proposal
        fields = (
                'id',
                'insurance_choice',
                'temporary_document_collection_id',
                'keep_existing_vessel',
                )
        read_only_fields=('id',)

    def validate(self, data):
        custom_errors = {}
        proposal = Proposal.objects.get(id=self.context.get("proposal_id"))
        if self.context.get("action") == 'submit':
            insurance_choice = data.get("insurance_choice")
            vessel_length = proposal.vessel_length
            if not insurance_choice:
                custom_errors["Insurance Choice"] = "You must make an insurance selection"
            elif vessel_length > Decimal("6.4") and insurance_choice not in ['ten_million', 'over_ten']:
                custom_errors["Insurance Choice"] = "Insurance selected is insufficient for your nominated vessel"

        if custom_errors.keys():
            raise serializers.ValidationError(custom_errors)
        return data


class SaveMooringLicenceApplicationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Proposal
        fields = (
                'id',
                'insurance_choice',
                'silent_elector',
                'customer_status',
                'processing_status',
                'temporary_document_collection_id',
                'keep_existing_vessel',
                )
        read_only_fields=('id',)

    def validate(self, data):
        logger.info(f'Validating the proposal: [{self.instance}]...')
        custom_errors = {}
        proposal = Proposal.objects.get(id=self.context.get("proposal_id"))
        if self.context.get("action") == 'submit':
            renewal_or_amendment_application_with_vessel = proposal.proposal_type.code in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT,] and proposal.rego_no
            new_application = proposal.proposal_type.code == PROPOSAL_TYPE_NEW
            if renewal_or_amendment_application_with_vessel or new_application:
                logger.info(f'This proposal: [{self.instance}] is a new proposal or a renewal/amendment proposal with a vessel.')
                insurance_choice = data.get("insurance_choice")
                vessel_length = proposal.vessel_length
                if not insurance_choice:
                    custom_errors["Insurance Choice"] = "You must make an insurance selection"
                elif vessel_length > Decimal("6.4") and insurance_choice not in ['ten_million', 'over_ten']:
                    custom_errors["Insurance Choice"] = "Insurance selected is insufficient for your nominated vessel"
                if not self.instance.insurance_certificate_documents.all():
                    custom_errors["Insurance Certificate"] = "Please attach"
            else:
                logger.info(f'This proposal: [{self.instance}] is a renewal/amendment proposal without a vessel.')

            # electoral roll validation
            if 'silent_elector' not in data.keys():
                custom_errors["Electoral Roll"] = "You must complete this section"
            elif data.get("silent_elector"):
                if not self.instance.electoral_roll_documents.all():
                    custom_errors["Silent Elector"] = "You must provide evidence of this"

            # When company ownership, vessel registration document is compulsory
            if self.instance.vessel_ownership and not self.instance.vessel_ownership.individual_owner:
                if not self.instance.vessel_ownership.vessel_registration_documents.count():
                    custom_errors["Copy of registration papers"] = "You must provide evidence of this"

        if custom_errors.keys():
            raise serializers.ValidationError(custom_errors)

        return data


class SaveAuthorisedUserApplicationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Proposal
        fields = (
                'id',
                'insurance_choice',
                'mooring_authorisation_preference',
                'bay_preferences_numbered',
                'customer_status',
                'processing_status',
                'temporary_document_collection_id',
                'keep_existing_mooring',
                'keep_existing_vessel',
                )
        read_only_fields=('id',)

    def validate(self, data):
        custom_errors = {}
        proposal = Proposal.objects.get(id=self.context.get("proposal_id"))

        if self.context.get("action") == 'submit':
            insurance_choice = data.get("insurance_choice")
            vessel_length = proposal.vessel_length
            if not insurance_choice:
                custom_errors["Insurance Choice"] = "You must make an insurance selection"
            elif vessel_length > Decimal("6.4") and insurance_choice not in ['ten_million', 'over_ten']:
                custom_errors["Insurance Choice"] = "Insurance selected is insufficient for your nominated vessel"
            if not self.instance.insurance_certificate_documents.all():
                custom_errors["Insurance Certificate"] = "Please attach"

            if not data.get("mooring_authorisation_preference"):
                custom_errors["Mooring Details"] = "You must complete this tab"
        if custom_errors.keys():
            raise serializers.ValidationError(custom_errors)
        return data


class SaveDraftProposalVesselSerializer(serializers.ModelSerializer):
    percentage = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Proposal
        fields = (
                'rego_no',
                'vessel_id',
                'vessel_type',
                'vessel_name',
                'vessel_length',
                'vessel_draft',
                'vessel_beam',
                'vessel_weight',
                'berth_mooring',
                'percentage',
                'individual_owner',
                'company_ownership_percentage',
                'company_ownership_name',
                'dot_name',
                'temporary_document_collection_id',
                )

    def validate_percentage(self, value):
        if not value:
            return 0
        try:
            return int(value)
        except ValueError:
            raise serializers.ValidationError('You must supply an integer value.')


class ProposalDeclinedDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposalDeclinedDetails
        fields = '__all__'


class InternalProposalSerializer(BaseProposalSerializer):
    applicant = serializers.CharField(read_only=True)
    processing_status = serializers.SerializerMethodField(read_only=True)
    customer_status = serializers.SerializerMethodField(read_only=True)
    submitter = serializers.SerializerMethodField()
    proposaldeclineddetails = ProposalDeclinedDetailsSerializer()
    assessor_mode = serializers.SerializerMethodField()
    approver_mode = serializers.SerializerMethodField()
    current_assessor = serializers.SerializerMethodField()
    allowed_assessors = serializers.SerializerMethodField()
    application_type = serializers.CharField(source='application_type.name', read_only=True)
    fee_invoice_url = serializers.SerializerMethodField()
    previous_application_vessel_details_id = serializers.SerializerMethodField()
    previous_application_preferred_bay_id = serializers.SerializerMethodField()
    mooring_licence_vessels = serializers.SerializerMethodField()
    authorised_user_moorings = serializers.SerializerMethodField()
    reissued = serializers.SerializerMethodField()
    current_vessels_rego_list = serializers.SerializerMethodField()
    application_type_code = serializers.SerializerMethodField()
    authorised_user_moorings_str = serializers.SerializerMethodField()
    waiting_list_application_id = serializers.SerializerMethodField()
    approval_type_text = serializers.SerializerMethodField()
    approval_lodgement_number = serializers.SerializerMethodField()
    approval_vessel_rego_no = serializers.SerializerMethodField()
    vessel_on_proposal = serializers.SerializerMethodField()
    proposed_issuance_approval = serializers.SerializerMethodField()
    site_licensee_moorings = serializers.SerializerMethodField()
    has_unactioned_endorsements = serializers.SerializerMethodField()
    can_bypass_auto_approval = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = (
                'id',
                'migrated',
                'start_date',
                'application_type',
                'approval_id',
                'title',
                'customer_status',
                'processing_status',
                'applicant',
                'submitter',
                'assigned_officer',
                'assigned_approver',
                #'get_history',
                'lodgement_date',
                #'modified_date',
                'documents',
                'requirements',
                'readonly',
                'can_user_edit',
                'can_user_cancel_payment',
                'can_user_bypass_payment',
                'can_user_view',
                'documents_url',
                'assessor_mode',
                'approver_mode',
                'current_assessor',
                'allowed_assessors',
                'proposed_issuance_approval',
                'proposed_decline_status',
                'proposaldeclineddetails',
                'permit',
                'lodgement_number',
                'can_officer_process',
                'proposal_type',
                'fee_invoice_url',
                'fee_paid',
                'application_type_dict',
                'vessel_details_id',
                'vessel_ownership_id',
                'insurance_choice',
                'preferred_bay_id',
                'silent_elector',
                'bay_preferences_numbered',
                'site_licensee_moorings',
                'mooring_authorisation_preference',
                'previous_application_id',
                'previous_application_vessel_details_id',
                'previous_application_preferred_bay_id',
                'mooring_licence_vessels',
                'authorised_user_moorings',
                'reissued',
                'dot_name',
                'current_vessels_rego_list',
                'application_type_code',
                'authorised_user_moorings_str',
                'keep_existing_mooring',
                'keep_existing_vessel',
                'rego_no',
                'vessel_id',
                'vessel_details_id',
                'vessel_ownership_id',
                'vessel_type',
                'vessel_name',
                'vessel_length',
                'vessel_draft',
                'vessel_beam',
                'vessel_weight',
                'berth_mooring',
                'dot_name',
                'percentage',
                'individual_owner',
                'company_ownership_name',
                'company_ownership_percentage',
                'waiting_list_application_id',
                'pending_amendment_request',
                'approval_type_text',
                'approval_lodgement_number',
                'approval_vessel_rego_no',
                'vessel_on_proposal',
                'null_vessel_on_create',
                'proposal_applicant',
                'amendment_requests',
                'uuid',
                'allocated_mooring',
                'has_unactioned_endorsements',
                'no_email_notifications',
                'stat_dec_form',
                'can_bypass_auto_approval'
                )
        read_only_fields = (
            'documents',
            'requirements',
        )

    def get_can_bypass_auto_approval(self,obj):
        if 'request' in self.context and is_internal(self.context['request']):
            return (obj.customer_status == Proposal.CUSTOMER_STATUS_DRAFT and is_system_admin(self.context['request']))
        else:
            return False

    def get_site_licensee_moorings(self, obj):

        site_licensee_moorings = []
        su_qs = SystemUser.objects
        for i in obj.site_licensee_mooring_request.filter(enabled=True):

            checked = i.approved_by_endorser
            if obj.proposed_issuance_approval and 'requested_mooring_on_approval' in obj.proposed_issuance_approval:
                for item in obj.proposed_issuance_approval['requested_mooring_on_approval']:
                    if  i.mooring_id == item['id']:
                        checked = item['checked']

            site_licensee = ""
            site_licensee_system_user = su_qs.filter(email__iexact=i.site_licensee_email)
            if site_licensee_system_user.exists():
                site_licensee = get_user_name(site_licensee_system_user.first())["full_name"]
            endorsement = "Not Actioned"
            if i.approved_by_endorser:
                endorsement = "Endorsed"
            elif i.declined_by_endorser:
                endorsement = "Declined"

            if i.mooring:
                site_licensee_moorings.append(
                    {
                    "id":i.id,
                    "email":i.site_licensee_email, 
                    "mooring_name":i.mooring.name,
                    "mooring_id":i.mooring.id,
                    "bay":i.mooring.mooring_bay.name,
                    "checked": checked,
                    'vessel_weight_limit': i.mooring.vessel_weight_limit,
                    'vessel_size_limit': i.mooring.vessel_size_limit,
                    'vessel_draft_limit': i.mooring.vessel_draft_limit,
                    "site_licensee": site_licensee,
                    "endorsement": endorsement,
                    }
                )

        return site_licensee_moorings

    def get_allowed_assessors(self, obj):
        if 'request' in self.context and is_internal(self.context['request']):
            email_user_ids = list(obj.allowed_assessors.values_list("id",flat=True))
            system_users = SystemUser.objects.filter(ledger_id__id__in=email_user_ids)
            serializer = UserSerializer(system_users, many=True)
            return serializer.data
        else:
            return None

    def get_proposed_issuance_approval(self, obj):
        if obj.proposed_issuance_approval and obj.proposed_issuance_approval.get('mooring_bay_id', None):
            # Add bay_name when possible to display on the frontend
            bay = MooringBay.objects.get(id=obj.proposed_issuance_approval.get('mooring_bay_id'))
            obj.proposed_issuance_approval['bay_name'] = bay.name
        return obj.proposed_issuance_approval

    def get_submitter(self, obj):
        if obj.submitter:    
            user = retrieve_system_user(obj.submitter)
            return UserSerializer(user).data
        else:
            return ""

    def get_vessel_on_proposal(self, obj):
        return obj.vessel_on_proposal()

    def get_approval_vessel_rego_no(self, obj):
        rego_no = None
        if obj.approval and type(obj.approval) is not MooringLicence:
            rego_no = (obj.approval.current_proposal.vessel_details.vessel.rego_no if
                    obj.approval and obj.approval.current_proposal and obj.approval.current_proposal.vessel_details and
                    not obj.approval.current_proposal.vessel_ownership.end_date
                    else None)
        return rego_no

    def get_approval_type_text(self, obj):
        return obj.approval.child_obj.description if obj.approval else None

    def get_approval_lodgement_number(self, obj):
        lodgement_number = None
        if obj.approval:
            lodgement_number = obj.approval.lodgement_number
        return lodgement_number

    def get_waiting_list_application_id(self, obj):
        wla_id = None
        if obj.waiting_list_allocation:
            wla_id = obj.waiting_list_allocation.current_proposal.id
        return wla_id

    def get_application_type_code(self, obj):
        return obj.application_type_code

    def get_current_vessels_rego_list(self, obj):
        if obj.approval and type(obj.approval.child_obj) is MooringLicence:
            vessels_str = ''
            vessels_str += ', '.join([vo.vessel.rego_no for vo in obj.listed_vessels.filter(end_date__isnull=True)])

            if not vessels_str and obj.approval and obj.approval.reissued:
                voas = VesselOwnershipOnApproval.objects.filter(approval=obj.approval,end_date__isnull=True).distinct("vessel_ownership__vessel__rego_no")
                vessels_str += ', '.join([voa.vessel_ownership.vessel.rego_no for voa in voas])

            return vessels_str

    def get_reissued(self, obj):
        return obj.approval.reissued if obj.approval else False

    def get_authorised_user_moorings_str(self, obj):
        if type(obj.child_obj) == AuthorisedUserApplication and obj.approval:
            moorings_str = ''
            moorings_str += ', '.join([mooring.name for mooring in obj.listed_moorings.all()])
            return moorings_str

    def get_authorised_user_moorings(self, obj):
        moorings = []
        if type(obj.child_obj) == AuthorisedUserApplication and obj.approval:
            for moa in obj.approval.mooringonapproval_set.all():
                suitable_for_mooring = True
                # only do check if vessel details exist
                if obj.vessel_details:
                    suitable_for_mooring = moa.mooring.suitable_vessel(obj.vessel_details)

                # Retrieve checkbox status for this mooring (moa.mooring)
                checked = moa.active
                if obj.proposed_issuance_approval and 'mooring_on_approval' in obj.proposed_issuance_approval:
                    for item in obj.proposed_issuance_approval['mooring_on_approval']:
                        if  moa.id == item['id']:
                            checked = item['checked']

                moorings.append({
                    "id": moa.id,
                    "mooring_name": moa.mooring.name,
                    "bay": str(moa.mooring.mooring_bay),
                    "site_licensee": 'RIA Allocated' if not moa.site_licensee else 'User Requested',
                    "status": 'Current' if not moa.end_date else 'Historical',
                    "checked": checked,
                    'vessel_weight_limit': moa.mooring.vessel_weight_limit,
                    'vessel_size_limit': moa.mooring.vessel_size_limit,
                    'vessel_draft_limit': moa.mooring.vessel_draft_limit,
                    "suitable_for_mooring": suitable_for_mooring,
                    "mooring_licence_current": moa.mooring.mooring_licence.status in [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED] if moa.mooring.mooring_licence else None,
                })
        return moorings

    def get_mooring_licence_vessels(self, obj):
        vessels = []
        vessel_details = []
        if type(obj.child_obj) == MooringLicenceApplication and obj.approval:
            for vooa in obj.approval.vesselownershiponapproval_set.filter(vessel_ownership__end_date__isnull=True):
                vessel = vooa.vessel_ownership.vessel
                vessels.append(vessel)
                status = 'Current' if not vooa.end_date else 'Historical'

                # Retrieve checkbox status for this mooring (moa.mooring)
                checked = True
                if obj.proposed_issuance_approval and 'vessel_ownership' in obj.proposed_issuance_approval:
                    for item in obj.proposed_issuance_approval['vessel_ownership']:
                        if  vooa.vessel_ownership.id == item['id']:
                            checked = item['checked']

                vessel_details.append({
                    "id": vooa.vessel_ownership.id,
                    "rego": vooa.vessel_ownership.vessel.rego_no,
                    "vessel_name": vooa.vessel_ownership.vessel.latest_vessel_details.vessel_name,
                    "status": status,
                    'checked': checked,
                })
        return vessel_details

    def get_previous_application_vessel_details_id(self, obj):
        vessel_details_id = None
        if obj.previous_application and obj.previous_application.vessel_details:
            vessel_details_id = obj.previous_application.vessel_details.id
        return vessel_details_id

    def get_previous_application_preferred_bay_id(self, obj):
        preferred_bay_id = None
        if obj.previous_application and obj.previous_application.preferred_bay:
            preferred_bay_id = obj.previous_application.preferred_bay.id
        return preferred_bay_id

    def get_assessor_mode(self,obj):
        request = self.context['request']
        user = request.user._wrapped if hasattr(request.user,'_wrapped') else request.user
        return {
            'has_assessor_mode': obj.has_assessor_mode(user),
            'assessor_can_assess': obj.can_assess(user),
        }
    
    def get_has_unactioned_endorsements(self,obj):
        return obj.site_licensee_mooring_request.filter(enabled=True, declined_by_endorser=False, approved_by_endorser=False).exists()

    def get_approver_mode(self,obj):
        request = self.context['request']
        user = request.user._wrapped if hasattr(request.user,'_wrapped') else request.user
        return {
            'has_approver_mode': obj.has_approver_mode(user),
            'approver_can_approve': obj.can_assess(user),
        }

    def get_readonly(self,obj):
        return True

    def get_current_assessor(self,obj):
        if 'request' in self.context and is_internal(self.context['request']):
            return {
                'id': self.context['request'].user.id,
                'name': self.context['request'].user.get_full_name(),
                'email': self.context['request'].user.email
            }

    def get_fee_invoice_url(self,obj):
        url = f'/ledger-toolkit-api/invoice-pdf/{obj.invoice.reference}/' if obj.invoice else ''
        return url


class ProposalUserActionSerializer(serializers.ModelSerializer):
    who = serializers.SerializerMethodField()

    class Meta:
        model = ProposalUserAction
        fields = '__all__'

    def get_who(self, obj):
        ret_name = 'System'
        if obj.who:
            name = obj.who_obj.get_full_name()
            name = name.strip()
            if name:
                ret_name = name
        return ret_name


class ProposalLogEntrySerializer(CommunicationLogEntrySerializer):
    documents = serializers.SerializerMethodField()
    class Meta:
        model = ProposalLogEntry
        fields = '__all__'
        read_only_fields = (
            'customer',
        )

    def get_documents(self,obj):
        return [[d.name,d._file.url if d._file else ""] for d in obj.documents.all()]


class VesselLogEntrySerializer(CommunicationLogEntrySerializer):
    documents = serializers.SerializerMethodField()
    class Meta:
        model = VesselLogEntry
        fields = '__all__'
        read_only_fields = (
            'customer',
        )

    def get_documents(self,obj):
        return [[d.name,d._file.url] for d in obj.documents.all()]


class MooringUserActionSerializer(serializers.ModelSerializer):
    who = serializers.SerializerMethodField()

    class Meta:
        model = MooringUserAction
        fields = '__all__'

    def get_who(self, obj):
        ret_name = 'System'
        if obj.who:
            name = obj.who_obj.get_full_name()
            name = name.strip()
            if name:
                ret_name = name
        return ret_name

class MooringLogEntrySerializer(CommunicationLogEntrySerializer):
    documents = serializers.SerializerMethodField()
    class Meta:
        model = MooringLogEntry
        fields = '__all__'
        read_only_fields = (
            'customer',
        )

    def get_documents(self,obj):
        return [[d.name,d._file.url] for d in obj.documents.all()]


class ProposalRequirementSerializer(serializers.ModelSerializer):
    due_date = serializers.DateField(input_formats=['%d/%m/%Y'],required=False,allow_null=True)
    read_due_date = serializers.SerializerMethodField()

    class Meta:
        model = ProposalRequirement
        fields = (
            'id',
            'due_date',
            'free_requirement',
            'standard_requirement',
            'standard',
            'order',
            'proposal',
            'recurrence',
            'recurrence_schedule',
            'recurrence_pattern',
            'requirement',
            'is_deleted',
            'copied_from',
            'require_due_date',
            'copied_for_renewal',
            'read_due_date',
        )
        read_only_fields = ('id', 'order', 'requirement', 'copied_from')

    def create(self, validated_data):
        return super(ProposalRequirementSerializer, self).create(validated_data)

    def get_read_due_date(self, obj):
        due_date_str = ''
        if obj.due_date:
            due_date_str = obj.due_date.strftime('%d/%m/%Y')
        return due_date_str


class ProposalStandardRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposalStandardRequirement
        fields = ('id','code','text')


class ProposedApprovalSerializer(serializers.Serializer):
    expiry_date = serializers.DateField(input_formats=['%d/%m/%Y'], required=False)
    start_date = serializers.DateField(input_formats=['%d/%m/%Y'], required=False)
    details = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    cc_email = serializers.CharField(required=False, allow_null=True)
    mooring_id = serializers.IntegerField(required=False, allow_null=True)
    mooring_bay_id = serializers.IntegerField(required=False, allow_null=True)
    ria_mooring_name = serializers.CharField(required=False, allow_blank=True)
    mooring_on_approval = serializers.ListField(
            child=serializers.JSONField(),
            required=False,
            )
    requested_mooring_on_approval = serializers.ListField(
            child=serializers.JSONField(),
            required=False,
            )
    vessel_ownership = serializers.ListField(
            child=serializers.JSONField(),
            required=False,
            )


class ProposedDeclineSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False)
    cc_email = serializers.CharField(required=False, allow_null=True)


class AmendmentRequestSerializer(serializers.ModelSerializer):

    class Meta:
        model = AmendmentRequest
        fields = '__all__'


class AmendmentRequestDisplaySerializer(serializers.ModelSerializer):
    reason = serializers.SerializerMethodField()

    class Meta:
        model = AmendmentRequest
        fields = '__all__'

    def get_reason (self,obj):
        return obj.reason.reason if obj.reason else None


class SearchKeywordSerializer(serializers.Serializer):
    number = serializers.CharField()
    id = serializers.IntegerField()
    type = serializers.CharField()
    applicant = serializers.CharField()
    text = serializers.JSONField(required=False)


class SearchReferenceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.CharField()


class VesselSerializer(serializers.ModelSerializer):

    class Meta:
        model = Vessel
        fields = '__all__'


class VesselFullSerializer(serializers.ModelSerializer):
    vessel_details = serializers.SerializerMethodField()

    class Meta:
        model = Vessel
        fields = '__all__'

    def get_vessel_details(self, obj):
        return VesselDetailsSerializer(obj.latest_vessel_details).data


class ListVesselDetailsSerializer(serializers.ModelSerializer):
    rego_no = serializers.SerializerMethodField()
    vessel_length = serializers.SerializerMethodField()
    vessel_type = serializers.SerializerMethodField()

    class Meta:
        model = VesselDetails
        fields = (
                'id',
                'vessel_id',
                'vessel_type',
                'rego_no', # link to rego number
                'vessel_name',
                'vessel_length',
                'vessel_draft',
                )

    def get_rego_no(self, obj):
        if obj.vessel:
            return obj.vessel.rego_no

    def get_vessel_length(self, obj):
        return obj.vessel_applicable_length

    def get_vessel_type(self, obj):
        return obj.get_vessel_type_display()


class ListVesselOwnershipSerializer(serializers.ModelSerializer):
    vessel_details = serializers.SerializerMethodField()
    emailuser = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()
    record_sale_link = serializers.SerializerMethodField()
    sale_date = serializers.SerializerMethodField()
    class Meta:
        model = VesselOwnership
        fields = (
                'id',
                'emailuser',
                'owner_name',
                'percentage',
                'vessel_details',
                'record_sale_link',
                'sale_date',
                )

    def get_emailuser(self, obj):
        try:
            system_user = SystemUser.objects.get(ledger_id=obj.owner.emailuser_obj)
            serializer = UserSerializer(system_user)
        except:
            return ""
        return serializer.data

    def get_vessel_details(self, obj):
        serializer = ListVesselDetailsSerializer(obj.vessel.latest_vessel_details)
        return serializer.data

    def get_owner_name(self, obj):
        return obj.applicable_owner_name

    def get_percentage(self, obj):
        return obj.applicable_percentage

    def get_record_sale_link(self, obj):
        return '<a href=# data-id="{}">Record Sale</a><br/>'.format(obj.id, obj.id)

    def get_sale_date(self, obj):
        sale_date = ''
        if obj.end_date:
            sale_date = obj.end_date.strftime('%d/%m/%Y')
        return sale_date

class VesselDetailsSerializer(serializers.ModelSerializer):
    read_only = serializers.SerializerMethodField()
    vessel_type_display = serializers.SerializerMethodField()

    class Meta:
        model = VesselDetails
        fields = (
                'id',
                'vessel_type',
                'vessel',
                'vessel_name',
                'vessel_length',
                'vessel_draft',
                'vessel_beam',
                'vessel_weight',
                'berth_mooring',
                'created',
                'updated',
                'read_only',
                'vessel_type_display',
                )

    def get_vessel_type_display(self, obj):
        return obj.get_vessel_type_display()

    def get_read_only(self, obj):
        return False


class SaveVesselDetailsSerializer(serializers.ModelSerializer):

    class Meta:
        model = VesselDetails
        fields = (
                'vessel_type',
                'vessel', # link to rego number
                'vessel_name',
                'vessel_length',
                'vessel_draft',
                'vessel_weight',
                'berth_mooring',
                )

    def validate(self, data):
        custom_errors = {}
        if custom_errors.keys():
            raise serializers.ValidationError(custom_errors)
        return data


class VesselOwnershipSerializer(serializers.ModelSerializer):
    company_ownership = serializers.SerializerMethodField()
    proposal_id = serializers.SerializerMethodField()
    
    class Meta:
        model = VesselOwnership
        fields = '__all__'

    def get_company_ownership(self, obj):
        co = obj.get_latest_company_ownership()
        data = None
        if co:
            serializer = CompanyOwnershipSerializer(co)
            data = serializer.data
        return data

    def get_proposal_id(self, obj):
        proposal = Proposal.objects.filter(vessel_ownership=obj).last()
        if(proposal):
            return proposal.id
        return None
    
class VesselFullOwnershipSerializer(serializers.ModelSerializer):
    company_ownership = serializers.SerializerMethodField()
    owner_full_name = serializers.SerializerMethodField()
    applicable_percentage = serializers.SerializerMethodField()
    start_date = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    owner_phone_number = serializers.SerializerMethodField()
    individual_owner = serializers.SerializerMethodField()
    action_link = serializers.SerializerMethodField()

    class Meta:
        model = VesselOwnership
        fields = (
                'id',
                'company_ownership',
                'percentage',
                'start_date',
                'end_date',
                'owner_full_name',
                'applicable_percentage',
                'owner_phone_number',
                'individual_owner',
                'dot_name',
                'action_link',
                )
    
    def get_company_ownership(self, obj):
        co = obj.get_latest_company_ownership()
        if co:
            serializer = CompanyOwnershipSerializer(co)
            return serializer.data
        return {}

    def get_action_link(self, obj):
        return '/internal/person/{}'.format(obj.owner.emailuser)

    def get_owner_full_name(self, obj):
        owner = obj.owner.emailuser_obj
        return owner.get_full_name()

    def get_applicable_percentage(self, obj):
        return obj.applicable_percentage

    def get_start_date(self, obj):
        start_date_str = ''
        if obj.start_date:
            start_date_str = obj.start_date.strftime('%d/%m/%Y')
        return start_date_str

    def get_end_date(self, obj):
        end_date_str = ''
        if obj.end_date:
            end_date_str = obj.end_date.strftime('%d/%m/%Y')
        return end_date_str

    def get_owner_phone_number(self, obj):
        owner = obj.owner.emailuser_obj
        return owner.phone_number if owner.phone_number else owner.mobile_number

    def get_individual_owner(self, obj):
        return obj.individual_owner


class SaveVesselOwnershipSaleDateSerializer(serializers.ModelSerializer):
    end_date = serializers.DateTimeField(input_formats=['%d/%m/%Y'],required=True,allow_null=False)

    class Meta:
        model = VesselOwnership
        fields = (
                'end_date',
                )


class VesselOwnershipSaleDateSerializer(serializers.ModelSerializer):
    end_date = serializers.SerializerMethodField()

    class Meta:
        model = VesselOwnership
        fields = (
                'end_date',
                )

    def get_end_date(self, obj):
        if obj.end_date:
            return obj.end_date.strftime('%d/%m/%Y')


class SaveVesselOwnershipSerializer(serializers.ModelSerializer):
    percentage = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = VesselOwnership
        fields = (
                'owner',
                'vessel',
                'percentage',
                'dot_name',
                'company_ownerships',
                )

    def validate(self, data):
        logger.info(f'Validating data: [{data}]...')
        custom_errors = {}

        if data.get("percentage") and data.get("percentage") < 25:
            custom_errors["Ownership Percentage"] = "Minimum of 25 percent"
        if custom_errors.keys():
            raise serializers.ValidationError(custom_errors)
        return data

    def validate_percentage(self, value):
        logger.info(f'Validating percentage: [{value}]...')
        if not value:
            return 0
        try:
            return int(value)
        except ValueError:
            raise serializers.ValidationError('You must supply an integer value.')


class MooringBaySerializer(serializers.ModelSerializer):

    class Meta:
        model = MooringBay
        fields = '__all__'


class ListMooringSerializer(serializers.ModelSerializer):
    mooring_bay_name = serializers.SerializerMethodField()
    authorised_user_permits = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    holder = serializers.SerializerMethodField()

    class Meta:
        model = Mooring
        fields = (
                'id',
                'name',
                'mooring_bay_name',
                'vessel_size_limit',
                'vessel_draft_limit',
                'vessel_beam_limit',
                'vessel_weight_limit',
                'authorised_user_permits',
                'status',
                'holder',
            )
        datatables_always_serialize = (
                'id',
                'name',
                'mooring_bay_name',
                'vessel_size_limit',
                'vessel_draft_limit',
                'vessel_beam_limit',
                'vessel_weight_limit',
                'authorised_user_permits',
                'status',
                'holder',
            )
    
    def get_holder(self, obj):
        if obj.mooring_licence and obj.mooring_licence.approval and not obj.mooring_licence.approval.status in ["surrendered","cancelled","expired"]:
            try:
                return obj.mooring_licence.approval.current_proposal.proposal_applicant.get_full_name()
            except:
                return 'N/A'
        return 'N/A'

    def get_mooring_bay_name(self, obj):
        return obj.mooring_bay.name

    def get_authorised_user_permits(self, obj):
        target_date=datetime.now(pytz.timezone(TIME_ZONE)).date()

        query = Q()
        query &= Q(mooring=obj)
        query &= Q(approval__status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,])
        query &= (Q(end_date__gt=target_date) | Q(end_date__isnull=True))

        preference_count_ria = MooringOnApproval.objects.filter(
            query,
            site_licensee=False,
            active=True
        ).count()

        preference_count_site_licensee = MooringOnApproval.objects.filter(
            query,
            site_licensee=True,
            active=True
        ).count()

        return {
            'ria': preference_count_ria,
            'site_licensee': preference_count_site_licensee
        }

    def get_status(status, obj):
        return obj.status


class SaveCompanyOwnershipSerializer(serializers.ModelSerializer):
    percentage = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = CompanyOwnership
        fields = (
                'company',
                'vessel',
                'percentage',
                )

    def validate_percentage(self, value):
        if not value:
            return 0
        try:
            return int(value)
        except ValueError:
            raise serializers.ValidationError('You must supply an integer value.')

