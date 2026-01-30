import logging
import pytz
from datetime import datetime
from mooringlicensing.settings import TIME_ZONE

from django.conf import settings
from ledger_api_client.ledger_models import Invoice
from ledger_api_client.managed_models import SystemUser
from django.db.models import Q
from mooringlicensing.helpers import is_internal

from mooringlicensing.components.main import serializers
from mooringlicensing.components.payments_ml.serializers import (
    DcvPermitSerializer, FeeConstructorSerializer, 
    DcvAdmissionArrivalSerializer, DcvPermitSimpleSerializer
)
from mooringlicensing.components.approvals.models import (
    Approval,
    ApprovalLogEntry,
    ApprovalUserAction,
    DcvOrganisation,
    DcvVessel,
    DcvPermit,
    DcvAdmission,
    WaitingListAllocation,
    Sticker,
    MooringLicence,
    AnnualAdmissionPermit,
    AuthorisedUserPermit, StickerActionDetail, 
    ApprovalHistory, MooringOnApproval, VesselOwnershipOnApproval,
)

from mooringlicensing.components.main.serializers import CommunicationLogEntrySerializer
from mooringlicensing.components.proposals.serializers import (
    InternalProposalSerializer, 
    MooringSimpleSerializer, 
    ProposalApplicantSerializer
)
from mooringlicensing.components.proposals.models import Proposal, VesselOwnership
from mooringlicensing.components.users.serializers import UserSerializer
from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist

from mooringlicensing.ledger_api_utils import retrieve_system_user

logger = logging.getLogger(__name__)


class DcvOrganisationSerializer(serializers.ModelSerializer):

    def validate(self, data):
        field_errors = {}
        non_field_errors = []

        abn_required = self.context.get('abn_required')

        if not data['name']:
            field_errors['name'] = ['Please enter organisation name.',]
        if abn_required and not data['abn']:
            field_errors['abn'] = ['Please enter ABN / ACN.',]

        # Raise errors
        if field_errors:
            raise serializers.ValidationError(field_errors)
        if non_field_errors:
            raise serializers.ValidationError(non_field_errors)

        return data

    class Meta:
        model = DcvOrganisation
        fields = (
            'id',
            'name',
            'abn',
        )
        read_only_fields = (
            'id',
        )


class LookupDcvAdmissionSerializer(serializers.ModelSerializer):
    entity_type = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DcvAdmission
        fields = (
                'id',
                'lodgement_number',
                'entity_type',
                )

    def get_entity_type(self, obj):
        return 'Admission'


class LookupDcvPermitSerializer(serializers.ModelSerializer):
    entity_type = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DcvPermit
        fields = (
                'id',
                'lodgement_number',
                'entity_type',
                )

    def get_entity_type(self, obj):
        return 'Permit'


class DcvVesselSerializer(serializers.ModelSerializer):
    dcv_organisation_id = serializers.IntegerField(allow_null=True, required=False)
    dcv_permits = DcvPermitSerializer(many=True, read_only=True)

    def validate(self, data):
        field_errors = {}
        non_field_errors = []

        if not data['rego_no']:
            field_errors['rego_no'] = ['Please enter vessel registration number.',]
        if not data['vessel_name']:
            field_errors['vessel_name'] = ['Please enter vessel name.',]
        if 'dcv_organisation_id' in data and not data['dcv_organisation_id']:
            field_errors['dcv_organisation_id'] = ['Please enter organisation and/or ABN / ACN.',]

        # Raise errors
        if field_errors:
            raise serializers.ValidationError(field_errors)
        if non_field_errors:
            raise serializers.ValidationError(non_field_errors)

        return data

    class Meta:
        model = DcvVessel
        fields = (
            'id',
            'vessel_name',
            'rego_no',
            'dcv_organisation_id',
            'dcv_permits',
        )
        read_only_fields = (
            'id',
            'dcv_permits',
        )


class ApprovalCancellationSerializer(serializers.Serializer):
    cancellation_date = serializers.DateField(input_formats=['%d/%m/%Y'])
    cancellation_details = serializers.CharField()


class ApprovalSuspensionSerializer(serializers.Serializer):
    from_date = serializers.DateField(input_formats=['%d/%m/%Y'])
    to_date = serializers.DateField(input_formats=['%d/%m/%Y'], required=False, allow_null=True)
    suspension_details = serializers.CharField()

class ApprovalExtensionSerializer(serializers.Serializer):
    expiry_date = serializers.DateField(input_formats=['%d/%m/%Y'])
    extension_details = serializers.CharField()

class ApprovalSurrenderSerializer(serializers.Serializer):
    surrender_date = serializers.DateField(input_formats=['%d/%m/%Y'])
    surrender_details = serializers.CharField()


class ApprovalUserActionSerializer(serializers.ModelSerializer):
    who = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalUserAction
        fields = '__all__'

    def get_who(self, obj):
        ret_name = 'System'
        if obj.who:
            name = obj.who_obj.get_full_name()
            name = name.strip()
            if name:
                ret_name = name
        return ret_name


class ApprovalLogEntrySerializer(CommunicationLogEntrySerializer):
    documents = serializers.SerializerMethodField()
    class Meta:
        model = ApprovalLogEntry
        fields = '__all__'
        read_only_fields = (
            'customer',
        )

    def get_documents(self,obj):
        return [[d.name,d._file.url] for d in obj.documents.all()]


class WaitingListAllocationSerializer(serializers.ModelSerializer):

    class Meta:
        model = WaitingListAllocation
        fields = '__all__'


class ApprovalSerializer(serializers.ModelSerializer):
    submitter = serializers.SerializerMethodField()
    applicant = serializers.SerializerMethodField()
    current_proposal = InternalProposalSerializer()
    licence_document = serializers.SerializerMethodField()
    renewal_document = serializers.SerializerMethodField(read_only=True)
    status = serializers.SerializerMethodField()
    internal_status = serializers.SerializerMethodField()
    approval_type_dict = serializers.SerializerMethodField()
    holder = serializers.SerializerMethodField()
    issue_date_str = serializers.SerializerMethodField()
    expiry_date_str = serializers.SerializerMethodField()
    vessel_length = serializers.SerializerMethodField()
    vessel_draft = serializers.SerializerMethodField()
    preferred_mooring_bay = serializers.SerializerMethodField()
    preferred_mooring_bay_id = serializers.SerializerMethodField()
    current_proposal_number = serializers.SerializerMethodField()
    vessel_registration = serializers.SerializerMethodField()
    vessel_name = serializers.SerializerMethodField()
    offer_link = serializers.SerializerMethodField()
    ria_generated_proposals = serializers.SerializerMethodField()
    mooring_licence_vessels = serializers.SerializerMethodField()
    mooring_licence_vessels_detail = serializers.SerializerMethodField()
    mooring_licence_authorised_users = serializers.SerializerMethodField()
    mooring_licence_mooring = serializers.SerializerMethodField()
    authorised_user_moorings = serializers.SerializerMethodField()
    authorised_user_moorings_detail = serializers.SerializerMethodField()
    can_reissue = serializers.SerializerMethodField()
    can_external_action = serializers.SerializerMethodField()
    can_action = serializers.SerializerMethodField()
    can_reinstate = serializers.SerializerMethodField()
    amend_or_renew = serializers.SerializerMethodField()
    allowed_assessors = serializers.SerializerMethodField()
    stickers = serializers.SerializerMethodField()
    is_approver = serializers.SerializerMethodField()

    class Meta:
        model = Approval
        fields = (
            'id',
            'submitter',
            'applicant',
            'lodgement_number',
            'status',
            'internal_status',
            'approval_type_dict',
            'issue_date',
            'holder',
            'start_date',
            'issue_date',
            'expiry_date',
            'issue_date_str',
            'expiry_date_str',
            'vessel_length',
            'vessel_draft',
            'preferred_mooring_bay',
            'preferred_mooring_bay_id',
            'current_proposal_number',
            'current_proposal_id',
            'current_proposal',
            'vessel_registration',
            'vessel_name',
            'wla_order',
            'wla_queue_date',
            'offer_link',
            'ria_generated_proposals',
            'mooring_licence_vessels',
            'mooring_licence_vessels_detail',
            'mooring_licence_authorised_users',
            'mooring_licence_mooring',
            'authorised_user_moorings',
            'authorised_user_moorings_detail',
            'can_reissue',
            'can_external_action',
            'can_action',
            'can_extend',
            'can_reinstate',
            'amend_or_renew',
            'renewal_document',
            'renewal_sent',
            'allowed_assessors',
            'stickers',
            'licence_document',
            'is_approver',
        )

    def get_licence_document(self, obj):
        if obj.licence_document and obj.licence_document._file:
            return obj.licence_document._file.url

    def get_allowed_assessors(self, obj):
        if 'request' in self.context and is_internal(self.context['request']):
            email_user_ids = list(obj.allowed_assessors.values_list("id",flat=True))
            system_users = SystemUser.objects.filter(ledger_id__id__in=email_user_ids)
            serializer = UserSerializer(system_users, many=True)
            return serializer.data
        else:
            return None

    def get_submitter(self, obj):
        if 'request' in self.context and is_internal(self.context['request']):
            serializer = UserSerializer(retrieve_system_user(obj.submitter))
            return serializer.data
        return None
    
    def get_applicant(self, obj):
        if obj.proposal_applicant:
            serializer = UserSerializer(retrieve_system_user(obj.proposal_applicant.email_user_id))
            return serializer.data
        return None

    def get_mooring_licence_mooring(self, obj):
        if type(obj.child_obj) == MooringLicence:
            return obj.child_obj.mooring.name
        else:
            return None

    def get_stickers(self, obj):
        return [sticker.number for sticker in obj.stickers.filter(status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])]

    def get_renewal_document(self,obj):
        if obj.renewal_document and obj.renewal_document._file:
            return obj.renewal_document._file.url
        return None

    def get_can_external_action(self,obj):
        return obj.can_external_action

    def get_can_reissue(self,obj):
        return obj.can_reissue

    def get_can_reinstate(self,obj):
        return obj.can_reinstate

    def get_can_action(self,obj):
        return obj.can_action

    def get_amend_or_renew(self,obj):
        return obj.amend_or_renew

    def get_is_approver(self, obj):
        request = self.context.get('request')
        return obj.is_approver(request.user)

    def get_mooring_licence_vessels(self, obj):
        links = ''
        request = self.context.get('request')
        if type(obj.child_obj) == MooringLicence:
            for vessel_details in obj.child_obj.vessel_details_list:
                if request and request.GET.get('is_internal') and request.GET.get('is_internal') == 'true':
                    links += '<a href="/internal/vessel/{}">{}</a><br/>'.format(
                            vessel_details.vessel.id,
                            vessel_details.vessel.rego_no,
                            )
                else:
                    links += '{}\n'.format(vessel_details.vessel.rego_no)
        return links

    def get_mooring_licence_authorised_users(self, obj):
        authorised_users = []
        if type(obj.child_obj) == MooringLicence:
            moa_set = MooringOnApproval.objects.filter(
                    mooring=obj.child_obj.mooring,
                    active=True
                    )
            for moa in moa_set:
                approval = moa.approval
                if approval and approval.lodgement_number.startswith('AUP'):
                    authorised_users.append({
                        "id": moa.id,
                        "lodgement_number": approval.lodgement_number,
                        "vessel_name": (
                            approval.current_proposal.vessel_details.vessel.latest_vessel_details.vessel_name
                            if approval.current_proposal and approval.current_proposal.vessel_details else ''
                            ),
                        "holder": approval.current_proposal.proposal_applicant.get_full_name(),
                        "mobile": approval.current_proposal.proposal_applicant.mobile_number if approval.current_proposal.proposal_applicant.mobile_number else approval.current_proposal.proposal_applicant.phone_number,
                        "email": approval.current_proposal.proposal_applicant.email,
                        "status": approval.get_status_display(),
                        })
        return authorised_users

    def get_mooring_licence_vessels_detail(self, obj):
        vessels = []
        vessel_details = []
        if type(obj.child_obj) == MooringLicence:
            for vessel_ownership in obj.child_obj.vessel_ownership_list:
                vessel = vessel_ownership.vessel
                vessels.append(vessel)
                sticker_numbers = []
                for sticker in obj.stickers.filter(
                        status__in=['current', 'awaiting_printing', 'to_be_returned'],
                        vessel_ownership=vessel_ownership).order_by('-number'):
                    sticker_numbers.append(sticker.number)
                sticker_numbers = '<br/>'.join(sticker_numbers)

                vessel_details.append({
                    "id": vessel.id,
                    "vessel_name": vessel.latest_vessel_details.vessel_name,
                    "rego_no": vessel.rego_no,
                    "sticker_numbers": sticker_numbers,
                    "owner": vessel_ownership.owner.emailuser_obj.get_full_name(),
                    "mobile": vessel_ownership.owner.emailuser_obj.mobile_number,
                    "email": vessel_ownership.owner.emailuser_obj.email,
                    })
        return vessel_details

    def get_authorised_user_moorings_detail(self, obj):
        moorings = []
        if type(obj.child_obj) == AuthorisedUserPermit:
            for moa in obj.mooringonapproval_set.filter(end_date__isnull=True, active=True):
                if moa.mooring.mooring_licence is not None:
                    licence_holder_data = ProposalApplicantSerializer(moa.mooring.mooring_licence.current_proposal.proposal_applicant).data
                    moorings.append({
                        "id": moa.id,
                        "mooring_name": moa.mooring.name,
                        "sticker": moa.sticker.number if moa.sticker else '',
                        "licensee": licence_holder_data.get('full_name') if licence_holder_data else '',
                        'allocated_by': 'Site Licensee' if moa.site_licensee else 'RIA',
                        "mobile": licence_holder_data.get('mobile_number') if licence_holder_data else '',
                        "email": licence_holder_data.get('email') if licence_holder_data else '',
                        })
        return moorings

    def get_authorised_user_moorings(self, obj):
        links = ''
        request = self.context.get('request')
        if type(obj.child_obj) == AuthorisedUserPermit:
            for moa in obj.mooringonapproval_set.filter(mooring__mooring_licence__status='current', active=True):
                if request and request.GET.get('is_internal') and request.GET.get('is_internal') == 'true':
                    links += '<a href="/internal/moorings/{}">{}</a><br/>'.format(
                            moa.mooring.id,
                            str(moa.mooring),
                            )
                else:
                    links += '{}\n'.format(str(moa.mooring))
        return links

    def get_ria_generated_proposals(self, obj):
        links = '<br/>'
        if type(obj.child_obj) == WaitingListAllocation:
            for mla in obj.child_obj.ria_generated_proposal.all():
                links += '<a href="/internal/proposal/{}">{} : {}</a><br/>'.format(
                        mla.id,
                        mla.lodgement_number,
                        mla.get_processing_status_display(),
                        )
        return links

    def get_offer_link(self, obj):
        link = ''
        if (
            type(obj.child_obj) == WaitingListAllocation and 
            obj.status == Approval.APPROVAL_STATUS_CURRENT and
            obj.current_proposal.preferred_bay and
            obj.internal_status == Approval.INTERNAL_STATUS_WAITING
            ):
            related_wla = Proposal.objects.filter(approval=obj).exclude(
                Q(processing_status=Proposal.PROCESSING_STATUS_APPROVED)|
                Q(processing_status=Proposal.PROCESSING_STATUS_DECLINED)|
                Q(processing_status=Proposal.PROCESSING_STATUS_DISCARDED)|
                Q(processing_status=Proposal.PROCESSING_STATUS_EXPIRED)
            )
            if related_wla.exists():
                return ''
            link = '<a href="{}" class="offer-link" data-offer="{}" data-mooring-bay={}>Offer</a><br/>'.format(
                    obj.id,
                    obj.id,
                    obj.current_proposal.preferred_bay.id,
                    )
        return link

    def get_current_proposal_number(self, obj):
        number = ''
        if obj.current_proposal:
            number = obj.current_proposal.lodgement_number
        return number

    def get_vessel_length(self, obj):
        vessel_length = ''
        if (
                obj.current_proposal and
                obj.current_proposal.vessel_details and
                obj.current_proposal.vessel_ownership and
                not obj.current_proposal.vessel_ownership.end_date
                ):
            vessel_length = obj.current_proposal.vessel_details.vessel_applicable_length
        return vessel_length

    def get_vessel_registration(self, obj):
        vessel_rego = ''
        if (
                obj.current_proposal and
                obj.current_proposal.vessel_details and
                obj.current_proposal.vessel_ownership and
                not obj.current_proposal.vessel_ownership.end_date
                ):
            vessel_rego = obj.current_proposal.vessel_details.vessel.rego_no
        return vessel_rego

    def get_vessel_name(self, obj):
        vessel_name = ''
        if (
                obj.current_proposal and
                obj.current_proposal.vessel_details and
                obj.current_proposal.vessel_ownership and
                not obj.current_proposal.vessel_ownership.end_date
                ):
            vessel_name = obj.current_proposal.vessel_details.vessel_name
        return vessel_name

    def get_vessel_draft(self, obj):
        vessel_draft = ''
        if (
                obj.current_proposal and
                obj.current_proposal.vessel_details and
                obj.current_proposal.vessel_ownership and
                not obj.current_proposal.vessel_ownership.end_date
                ):
            vessel_draft = obj.current_proposal.vessel_details.vessel_draft
        return vessel_draft

    def get_preferred_mooring_bay(self, obj):
        bay = ''
        if obj.current_proposal and obj.current_proposal.preferred_bay:
            bay = obj.current_proposal.preferred_bay.name
        return bay

    def get_preferred_mooring_bay_id(self, obj):
        bay_id = None
        if obj.current_proposal and obj.current_proposal.preferred_bay:
            bay_id = obj.current_proposal.preferred_bay.id
        return bay_id

    def get_status(self, obj):
        return obj.detailed_status

    def get_internal_status(self, obj):
        return obj.get_internal_status_display()

    def get_approval_type_dict(self, obj):
        try:
            return {
                'code': obj.child_obj.code,
                'description': obj.child_obj.description,
            }
        except ObjectDoesNotExist:
            # Should not reach here
            logger.warn('{} does not have any associated child object - WLA, AAP, AUP or ML'.format(obj))
            return {
                'code': 'child-obj-notfound',
                'description': 'child-obj-notfound',
            }
        except:
            raise

    def get_holder(self, obj):
        return obj.applicant

    def get_issue_date_str(self, obj):
        issue_date = ''
        if obj.issue_date:
            issue_date = obj.issue_date.strftime('%d/%m/%Y')
        return issue_date

    def get_expiry_date_str(self, obj):
        expiry_date = ''
        if obj.expiry_date:
            expiry_date = obj.expiry_date.strftime('%d/%m/%Y')
        return expiry_date


class ListApprovalSerializer(serializers.ModelSerializer):
    licence_document = serializers.SerializerMethodField()
    authorised_user_summary_document = serializers.SerializerMethodField()
    renewal_document = serializers.SerializerMethodField(read_only=True)
    status = serializers.SerializerMethodField()
    internal_status = serializers.SerializerMethodField()
    approval_type_dict = serializers.SerializerMethodField()
    holder = serializers.SerializerMethodField()
    issue_date_str = serializers.SerializerMethodField()
    start_date_str = serializers.SerializerMethodField()
    expiry_date_str = serializers.SerializerMethodField()
    vessel_length = serializers.SerializerMethodField()
    vessel_draft = serializers.SerializerMethodField()
    preferred_mooring_bay = serializers.SerializerMethodField()
    preferred_mooring_bay_id = serializers.SerializerMethodField()
    current_proposal_number = serializers.SerializerMethodField()
    current_proposal_approved = serializers.SerializerMethodField()
    vessel_name = serializers.SerializerMethodField()
    offer_link = serializers.SerializerMethodField()
    ria_generated_proposals = serializers.SerializerMethodField()
    can_reissue = serializers.SerializerMethodField()
    can_external_action = serializers.SerializerMethodField()
    can_action = serializers.SerializerMethodField()
    can_reinstate = serializers.SerializerMethodField()
    amend_or_renew = serializers.SerializerMethodField()
    mooring_swappable = serializers.SerializerMethodField()
    allowed_assessors_user = serializers.SerializerMethodField()
    stickers = serializers.SerializerMethodField()
    stickers_historical = serializers.SerializerMethodField()
    has_sticker = serializers.SerializerMethodField()
    is_missing_sticker = serializers.SerializerMethodField()
    missing_sticker_message = serializers.SerializerMethodField()
    is_approver = serializers.SerializerMethodField()
    is_assessor = serializers.SerializerMethodField()
    vessel_regos = serializers.SerializerMethodField()
    moorings = serializers.SerializerMethodField()
    mooring_offered = serializers.SerializerMethodField()
    grace_period_details = serializers.SerializerMethodField()

    class Meta:
        model = Approval
        fields = (
            'id',
            'migrated',
            'lodgement_number',
            'status',
            'internal_status',
            'approval_type_dict',
            'issue_date',
            'holder',
            'issue_date_str',
            'start_date_str',
            'expiry_date_str',
            'vessel_length',
            'vessel_draft',
            'preferred_mooring_bay',
            'preferred_mooring_bay_id',
            'current_proposal_number',
            'current_proposal_approved',
            'current_proposal_id',
            'vessel_name',
            'wla_order',
            'offer_link',
            'ria_generated_proposals',
            'can_reissue',
            'can_external_action',
            'can_action',
            'can_extend',
            'can_reinstate',
            'amend_or_renew',
            'mooring_swappable',
            'renewal_document',
            'allowed_assessors_user',
            'stickers',
            'stickers_historical',
            'has_sticker',
            'is_missing_sticker',
            'missing_sticker_message',
            'licence_document',
            'authorised_user_summary_document',
            'is_assessor',
            'is_approver',
            'vessel_regos',
            'moorings',
            'mooring_offered',
            'grace_period_details',
        )
        # the serverSide functionality of datatables is such that only columns that have field 'data' defined are requested from the serializer. We
        # also require the following additional fields for some of the mRender functions
        datatables_always_serialize = (
            'id',
            'migrated',
            'lodgement_number',
            'status',
            'internal_status',
            'approval_type_dict',
            'issue_date',
            'holder',
            'issue_date_str',
            'start_date_str',
            'expiry_date_str',
            'vessel_length',
            'vessel_draft',
            'preferred_mooring_bay',
            'preferred_mooring_bay_id',
            'current_proposal_number',
            'current_proposal_approved',
            'current_proposal_id',
            'vessel_name',
            'wla_order',
            'offer_link',
            'ria_generated_proposals',
            'can_reissue',
            'can_external_action',
            'can_action',
            'can_extend',
            'can_reinstate',
            'amend_or_renew',
            'mooring_swappable',
            'renewal_document',
            'allowed_assessors_user',
            'stickers',
            'stickers_historical',
            'has_sticker',
            'is_missing_sticker',
            'missing_sticker_message',
            'licence_document',
            'authorised_user_summary_document',
            'is_assessor',
            'is_approver',
            'vessel_regos',
            'moorings',
            'mooring_offered',
            'grace_period_details',
        )

    def get_grace_period_details(self, obj):
        grace_period_end_date = obj.grace_period_end_date
        days_left = None

        if grace_period_end_date:
            today = datetime.now(pytz.timezone(settings.TIME_ZONE)).date()
            days_left = (grace_period_end_date - today).days

        return {
            'grace_period_end_date': grace_period_end_date,
            'days_left': days_left,
        }

    def get_mooring_offered(self, obj):
        mooring = {}
        if type(obj.child_obj) == WaitingListAllocation:
            proposal = obj.child_obj.ria_generated_proposal.first()
            if proposal and proposal.allocated_mooring:
                mooring = {
                    'id': proposal.allocated_mooring.id,
                    'name': proposal.allocated_mooring.name,
                }
        return mooring

    def get_has_sticker(self,obj):
        return Sticker.objects.filter(approval=obj).exclude(status__in=[Sticker.STICKER_STATUS_EXPIRED,Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_RETURNED,Sticker.STICKER_STATUS_TO_BE_RETURNED,Sticker.STICKER_STATUS_LOST]).exists()

    #we only consider a sticker missing if the only stickers that exist for the season are lost or cancelled
    def get_is_missing_sticker(self,obj):
        season = obj.latest_applied_season
        if type(obj.child_obj) == AuthorisedUserPermit:
            #check moas
            return MooringOnApproval.objects.filter(
                    approval=obj,active=True
                ).filter(
                    Q(sticker__isnull=True)|(Q(sticker__status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST])&Q(sticker__fee_season=season))
                ).exists()
        elif type(obj.child_obj) == MooringLicence:
            #check vos
            vo_ids = list(VesselOwnershipOnApproval.objects.filter(approval=obj, end_date__isnull=True, vessel_ownership__end_date__isnull=True).values_list("vessel_ownership__id",flat=True))
            vos = VesselOwnership.objects.filter(id__in=vo_ids)
            for vo in vos:
                #NOTE: we exclude returned from the check because a vessel can be re-added to a permit, but we never replace a returned sticker
                if not Sticker.objects.filter(approval=obj,vessel_ownership=vo).filter(fee_season=season).exclude(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST, Sticker.STICKER_STATUS_RETURNED]).exists():
                    return True
        elif type(obj.child_obj) == WaitingListAllocation:
            return False
        return not Sticker.objects.filter(approval=obj).filter(fee_season=season).exclude(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST, Sticker.STICKER_STATUS_RETURNED]).exists()


    def get_missing_sticker_message(self,obj):
        #specified WHICH valid sticker(s) is/are missing (and what invalid stikcers will be replaced)
        #OR what vessel/mooring is missing a sticker (and will have a sticker made for)
        season = obj.latest_applied_season
        if type(obj.child_obj) == AuthorisedUserPermit:
            moas = MooringOnApproval.objects.filter(
                    approval=obj,active=True
                ).filter(
                    Q(sticker__isnull=True)|(Q(sticker__status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST, Sticker.STICKER_STATUS_RETURNED])&Q(sticker__fee_season=season))
                ).order_by("-id")

            message = ""
            stickers = []
            if moas.exists():
                message = "The following moorings do not have a valid sticker record assigned: "
                for moa in moas:
                    #We do not want to replace a returned sticker, we treat it as if there is no sticker
                    if moa.sticker and moa.sticker.status != Sticker.STICKER_STATUS_RETURNED:
                        stickers.append(moa.sticker.number)
                    if moa.mooring and moa.mooring.name:
                        message += f"{str(moa.mooring.name)}, "

                message = f"{message[:-2]}."
                stickers = list(set(stickers))
                if stickers:
                    message += f" Stickers that need to be replaced: {','.join(stickers)}."
                    if len(stickers) > 1:
                        message += " New sticker will replace first in list." 
                return message
            else:
                return ""

        elif type(obj.child_obj) == MooringLicence:
            vo_ids = list(VesselOwnershipOnApproval.objects.filter(approval=obj, end_date__isnull=True, vessel_ownership__end_date__isnull=True).values_list("vessel_ownership__id",flat=True))
            vos = VesselOwnership.objects.filter(id__in=vo_ids)
            vo_stickers = Sticker.objects.filter(vessel_ownership_id__in=vo_ids,approval=obj).filter(fee_season=season).order_by('-id')
            
            bad_vos = []
            bad_stickers = []

            for vo in vos:
                sticker_check = vo_stickers.filter(vessel_ownership=vo,approval=obj)

                if sticker_check.exclude(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST, Sticker.STICKER_STATUS_RETURNED]).exists():
                    #vo is fine
                    continue
                elif not sticker_check.exclude(status=Sticker.STICKER_STATUS_RETURNED).exists():
                    #vo has no stickers at all
                    bad_vos.append(vo)
                elif sticker_check.filter(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST]).exists():
                    #vo has bad stickers
                    bad_vos.append(vo)
                    bad_stickers.append(sticker_check.filter(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST]).first().number)

            if bad_vos:
                message = "The following vessels do not have a valid sticker record assigned: "
                for vo in bad_vos:
                    if vo.vessel:
                        message += f"{str(vo.vessel.rego_no)}, "
                message = f"{message[:-2]}."

                if bad_stickers:
                    message += f" Stickers that need to be replaced: {','.join(bad_stickers)}."
                    if len(bad_stickers) > 1:
                        message += " New sticker will replace first in list." 
                return message
            else:
                return ""

        elif type(obj.child_obj) == AnnualAdmissionPermit:
            stickers = Sticker.objects.filter(approval=obj).filter(fee_season=season).exclude(status=Sticker.STICKER_STATUS_RETURNED).order_by('-id')
            bad_vo = None
            bad_sticker = None
            if not stickers.exists():
                #AA has no stickers at all
                bad_vo = obj.current_proposal.vessel_ownership if obj.current_proposal else None
            elif not stickers.exclude(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST]).exists():
                #AA has no valid stickers
                bad_vo = obj.current_proposal.vessel_ownership if obj.current_proposal else None
                bad_sticker = stickers.filter(status__in=[Sticker.STICKER_STATUS_CANCELLED,Sticker.STICKER_STATUS_LOST]).first()
            
            if bad_vo and bad_vo.vessel:
                message = f"{bad_vo.vessel.rego_no} has no valid sticker record assigned."
                if bad_sticker:
                    message += f" Sticker {bad_sticker.number} will need to be replaced."
                return message
        else:
            return ""
        

    def get_moorings(self, obj):
        links = []
        request = self.context.get('request')
        if obj.child_obj:
            if type(obj.child_obj) == AuthorisedUserPermit:
                moas = MooringOnApproval.get_current_moas_by_approval(obj)
                for moa in moas:
                    if moa.mooring and moa.mooring.mooring_bay:
                        links.append({
                            'id': moa.mooring.id,
                            'bay_name': moa.mooring.mooring_bay.name,
                            'mooring_name': moa.mooring.name,
                        })
            elif type(obj.child_obj) == MooringLicence and hasattr(obj.child_obj,'mooring') and obj.child_obj.mooring.mooring_bay: 
                links.append({
                    'id': obj.child_obj.mooring.id,
                    'bay_name': obj.child_obj.mooring.mooring_bay.name,
                    'mooring_name': obj.child_obj.mooring.name,
                })

        return links

    def get_licence_document(self, obj):
        if obj.licence_document and obj.licence_document._file:
            return obj.licence_document._file.url
        return 'no-licence-document-found'

    def get_authorised_user_summary_document(self, obj):
        if obj.authorised_user_summary_document:
            return obj.authorised_user_summary_document._file.url
        else:
            return ''

    def get_allowed_assessors_user(self, obj):
        request = self.context.get('request')
        if request:
            return obj.allowed_assessors_user(request)
        else:
            return False

    def get_current_proposal_approved(self, obj):
        from mooringlicensing.components.proposals.models import Proposal
        if obj.current_proposal:
            return obj.current_proposal.processing_status == Proposal.PROCESSING_STATUS_APPROVED
        else:
            logger.warning(f'Current proposal of the approval: [{obj}] not found.')
            return ''

    def get_is_assessor(self, obj):
        request = self.context.get('request')
        if request:
            return obj.is_assessor(request.user)
        else:
            return False

    def get_is_approver(self, obj):
        request = self.context.get('request')
        if request:
            return obj.is_approver(request.user)
        else:
            return False

    def get_stickers_historical(self, obj):
        stickers = obj.stickers.all()
        serializers = StickerSerializerSimple(stickers, many=True)
        list_return = serializers.data
        return list_return

    def get_stickers(self, obj):
        stickers = obj.stickers.order_by('id').filter(status__in=[
            Sticker.STICKER_STATUS_CURRENT,
            Sticker.STICKER_STATUS_AWAITING_PRINTING]
        )

        if not stickers.exists() and type(obj.child_obj) != AuthorisedUserPermit:
            stickers = obj.stickers.order_by('-id')[0:]
        elif not stickers.exists() and type(obj.child_obj) == AuthorisedUserPermit:
            moas = MooringOnApproval.objects.filter(approval=obj).order_by('mooring','-id').distinct('mooring')
            sticker_ids = []
            for moa in moas:
                if moa.sticker:
                    sticker_ids.append(moa.sticker.id)
            stickers = Sticker.objects.filter(id__in=sticker_ids)
        
        if stickers.exists() and type(obj.child_obj) == AnnualAdmissionPermit:
            #Annual Admissions can only have one sticker at a time, if multiple returned present only the last
            stickers = stickers.order_by('-id')[:1]

        serializers = StickerSerializerSimple(stickers, many=True)
        list_return = serializers.data
        return list_return

    def get_renewal_document(self,obj):
        if obj.renewal_document and obj.renewal_document._file:
            return obj.renewal_document._file.url
        return None

    def get_can_external_action(self,obj):
        return obj.can_external_action

    def get_can_reissue(self,obj):
        return obj.can_reissue

    def get_can_reinstate(self,obj):
        return obj.can_reinstate

    def get_can_action(self,obj):
        return obj.can_action
    
    def get_can_extend(self,obj):
        return obj.can_extend

    def get_amend_or_renew(self,obj):
        return obj.amend_or_renew

    def get_mooring_swappable(self,obj):
        return obj.mooring_swappable

    def get_mooring_licence_vessels(self, obj):
        links = ''
        request = self.context.get('request')
        if type(obj.child_obj) == MooringLicence:
            for vessel_details in obj.child_obj.vessel_details_list:
                if request and request.GET.get('is_internal') and request.GET.get('is_internal') == 'true':
                    links += '<a href="/internal/vessel/{}">{}</a><br/>'.format(
                            vessel_details.vessel.id,
                            vessel_details.vessel.rego_no,
                            )
                else:
                    links += '{}\n'.format(vessel_details.vessel.rego_no)
        return links

    def get_ria_generated_proposals(self, obj):
        links = '<br/>'
        if type(obj.child_obj) == WaitingListAllocation:
            for mla in obj.child_obj.ria_generated_proposal.all():
                links += '<a href="/internal/proposal/{}">{} : {}</a><br/>'.format(
                        mla.id,
                        mla.lodgement_number,
                        mla.get_processing_status_display(),
                        )
        return links

    def get_offer_link(self, obj):
        link = ''
        if (
            type(obj.child_obj) == WaitingListAllocation and 
            obj.status == Approval.APPROVAL_STATUS_CURRENT and
            obj.current_proposal.preferred_bay and
            obj.internal_status == Approval.INTERNAL_STATUS_WAITING
            ):
            related_wla = Proposal.objects.filter(approval=obj).exclude(
                Q(processing_status=Proposal.PROCESSING_STATUS_APPROVED)|
                Q(processing_status=Proposal.PROCESSING_STATUS_DECLINED)|
                Q(processing_status=Proposal.PROCESSING_STATUS_DISCARDED)|
                Q(processing_status=Proposal.PROCESSING_STATUS_EXPIRED)
            )
            if related_wla.exists():
                return ''
            link = '<a href="{}" class="offer-link" data-offer="{}" data-mooring-bay={}>Offer</a><br/>'.format(
                    obj.id,
                    obj.id,
                    obj.current_proposal.preferred_bay.id,
                    )
        return link

    def get_current_proposal_number(self, obj):
        number = ''
        if obj.current_proposal:
            number = obj.current_proposal.lodgement_number
        return number

    def get_vessel_length(self, obj):
        vessel_length = ''
        if (
                obj.current_proposal and
                obj.current_proposal.vessel_details and
                obj.current_proposal.vessel_ownership and
                not obj.current_proposal.vessel_ownership.end_date
                ):
            vessel_length = obj.current_proposal.vessel_details.vessel_applicable_length
        return vessel_length

    def get_vessel_regos(self, obj):
        today = datetime.now(pytz.timezone(TIME_ZONE)).date()
        regos = []
        if type(obj.child_obj) == MooringLicence:
            for vessel_details in obj.child_obj.vessel_details_list:
                regos.append(vessel_details.vessel.rego_no)
        else:
            if obj.current_proposal:
                if obj.current_proposal.vessel_ownership:
                    if obj.current_proposal.vessel_ownership.end_date is None or obj.current_proposal.vessel_ownership.end_date >= today:
                        # We don't want to include the sold vessel
                        regos.append(obj.current_proposal.vessel_ownership.vessel.rego_no)
            else:
                logger.warning(f'Current proposal of the approval: [{obj}] not found.')
                return ''


        return regos

    def get_vessel_name(self, obj):
        vessel_name = ''
        if (
                obj.current_proposal and
                obj.current_proposal.vessel_details and
                obj.current_proposal.vessel_ownership and
                not obj.current_proposal.vessel_ownership.end_date
                ):
            vessel_name = obj.current_proposal.vessel_details.vessel_name
        return vessel_name

    def get_vessel_draft(self, obj):
        vessel_draft = ''
        if (
                obj.current_proposal and
                obj.current_proposal.vessel_details and
                obj.current_proposal.vessel_ownership and
                not obj.current_proposal.vessel_ownership.end_date
                ):
            vessel_draft = obj.current_proposal.vessel_details.vessel_draft
        return vessel_draft

    def get_preferred_mooring_bay(self, obj):
        bay = ''
        if obj.current_proposal and obj.current_proposal.preferred_bay:
            bay = obj.current_proposal.preferred_bay.name
        return bay

    def get_preferred_mooring_bay_id(self, obj):
        bay_id = None
        if obj.current_proposal and obj.current_proposal.preferred_bay:
            bay_id = obj.current_proposal.preferred_bay.id
        return bay_id

    def get_status(self, obj):
        return obj.detailed_status

    def get_internal_status(self, obj):
        return obj.get_internal_status_display()

    def get_approval_type_dict(self, obj):
        try:
            return {
                'code': obj.child_obj.code,
                'description': obj.child_obj.description,
            }
        except ObjectDoesNotExist:
            # Should not reach here
            logger.warning('{} does not have any associated child object - WLA, AAP, AUP or ML'.format(obj))
            return {
                'code': 'child-obj-notfound',
                'description': 'child-obj-notfound',
            }
        except:
            raise

    def get_holder(self, obj):
        holder_str = ''
        if obj.current_proposal and obj.current_proposal.proposal_applicant:
            items = []
            try:
                items.append(f'{obj.current_proposal.proposal_applicant.first_name} {obj.current_proposal.proposal_applicant.last_name}')
                if obj.current_proposal.proposal_applicant.mobile_number:
                    items.append('<span class="glyphicon glyphicon-phone"></span> ' + obj.current_proposal.proposal_applicant.mobile_number)
                if obj.current_proposal.proposal_applicant.phone_number:
                    items.append('<span class="glyphicon glyphicon-earphone"></span> ' + obj.current_proposal.proposal_applicant.phone_number)
                items.append(obj.current_proposal.proposal_applicant.email)
            except Exception as e:
                logger.error(e)

            items = '</br>'.join(items)
            holder_str = '<span>' + items + '</span>'
        return holder_str

    def get_issue_date_str(self, obj):
        issue_date = ''
        if obj.issue_date:
            issue_date = obj.issue_date.strftime('%d/%m/%Y')
        return issue_date

    def get_expiry_date_str(self, obj):
        expiry_date = ''
        if obj.expiry_date:
            expiry_date = obj.expiry_date.strftime('%d/%m/%Y')
        return expiry_date

    def get_start_date_str(self, obj):
        start_date = ''
        if obj.start_date:
            start_date = obj.start_date.strftime('%d/%m/%Y')
        return start_date


class LookupApprovalSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    approval_type_dict = serializers.SerializerMethodField()
    submitter_phone_number = serializers.SerializerMethodField()
    vessel_data = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    allocated_by = serializers.SerializerMethodField()

    class Meta:
        model = Approval
        fields = (
            'id',
            'lodgement_number',
            'status',
            'approval_type_dict',
            'issue_date',
            'submitter_phone_number',
            'vessel_data',
            'url',
            'allocated_by',
        )

    def get_allocated_by(self, obj):
        allocated_by = ''
        mooring = self.context.get('mooring', None)

        if mooring and obj.code == AuthorisedUserPermit.code:
            query = Q()
            query &= Q(mooring=mooring)
            query &= Q(approval=obj)
            query &= Q(active=True)

            try:
                moa = MooringOnApproval.objects.get(query)
                allocated_by = 'LIC' if moa.site_licensee else 'RIA'
            except Exception as e:
                logger.error(f'{e}')

        return allocated_by

    def get_url(self, obj):
        return '/internal/approval/{}'.format(obj.id)

    def get_status(self, obj):
        return obj.detailed_status

    def get_approval_type_dict(self, obj):
        try:
            return {
                'code': obj.child_obj.code,
                'description': obj.child_obj.description,
            }
        except ObjectDoesNotExist:
            # Should not reach here
            logger.warning('{} does not have any associated child object - WLA, AAP, AUP or ML'.format(obj))
            return {
                'code': 'child-obj-notfound',
                'description': 'child-obj-notfound',
            }
        except:
            raise

    def get_submitter_phone_number(self, obj):
        return obj.proposal_applicant.mobile_number if obj.proposal_applicant.mobile_number else obj.proposal_applicant.phone_number

    def get_vessel_data(self, obj):
        vessel_data = []
        if type(obj.child_obj) != MooringLicence:
            if obj.current_proposal and obj.current_proposal.vessel_details and obj.current_proposal.vessel_details.vessel:
                vessel_data.append({
                    "id": obj.current_proposal.vessel_details.vessel.id,
                    "rego_no": obj.current_proposal.vessel_details.vessel.rego_no,
                    "vessel_name": obj.current_proposal.vessel_details.vessel.latest_vessel_details.vessel_name,
                })
        else:
            for vessel_details in obj.child_obj.vessel_details_list:
                if vessel_details and vessel_details.vessel:
                    vessel_data.append({
                        "id": vessel_details.vessel.id,
                        "rego_no": vessel_details.vessel.rego_no,
                        "vessel_name": vessel_details.vessel.latest_vessel_details.vessel_name,
                    })
        return vessel_data


class ApprovalSimpleSerializer(serializers.ModelSerializer):
    approval_type_dict = serializers.SerializerMethodField()

    class Meta:
        model = Approval
        fields = (
            'id',
            'lodgement_number',
            'approval_type_dict',
            'applicant',
        )

    def get_approval_type_dict(self, obj):
        return {
            'code': obj.child_obj.code,
            'description': obj.child_obj.description,
        }


class StickerActionDetailSerializer(serializers.ModelSerializer):
    date_of_lost_sticker = serializers.DateField(input_formats=['%d/%m/%Y'], required=False, allow_null=True)
    date_of_returned_sticker = serializers.DateField(input_formats=['%d/%m/%Y'], required=False, allow_null=True)
    date_created = serializers.DateTimeField(read_only=True)
    date_updated = serializers.DateTimeField(read_only=True)
    user_detail = serializers.SerializerMethodField()
    waive_the_fee = serializers.BooleanField(required=False)
    change_sticker_address = serializers.BooleanField(required=False)
    new_postal_address_country = serializers.SerializerMethodField()

    class Meta:
        model = StickerActionDetail
        fields = (
            'id',
            'approval',
            'sticker',
            'reason',
            'date_created',
            'date_updated',
            'date_of_lost_sticker',
            'date_of_returned_sticker',
            'action',
            'user',  # For saving the user data
            'user_detail',  # For reading the user data
            'waive_the_fee',
            'change_sticker_address',
            'new_postal_address_line1',
            'new_postal_address_line2',
            'new_postal_address_line3',
            'new_postal_address_locality',
            'new_postal_address_state',
            'new_postal_address_country',
            'new_postal_address_postcode',
        )
    
    def get_new_postal_address_country(self, obj):
        return obj.new_postal_address_country.code

    def get_user_detail(self, obj):
        serializer = UserSerializer(retrieve_system_user(obj.user))
        return serializer.data


class StickerForDcvSaveSerializer(serializers.ModelSerializer):

    class Meta:
        model = Sticker
        fields = (
            'status',
            'number',
            'dcv_permit',
            'mailing_date',
            'postal_address_line1',
            'postal_address_line2',
            'postal_address_line3',
            'postal_address_locality',
            'postal_address_state',
            'postal_address_country',
            'postal_address_postcode',
        )

    def validate(self, data):
        field_errors = {}
        non_field_errors = []
        if int(data['number']) < 1:
            field_errors['number'] = ['Sticker number must be greater than 0']

        # Raise errors
        if field_errors:
            raise serializers.ValidationError(field_errors)
        if non_field_errors:
            raise serializers.ValidationError(non_field_errors)

        return data


class StickerSerializerSimple(serializers.ModelSerializer):
    invoices = serializers.SerializerMethodField()
    vessel_rego_no = serializers.SerializerMethodField()

    class Meta:
        model = Sticker
        fields = (
            'id',
            'number',
            'mailing_date',
            'invoices',
            'vessel_rego_no',
        )

    def get_invoices(self, obj):
        invoices = obj.get_invoices()
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

    def get_vessel_rego_no(self, obj):
        if obj.vessel_ownership and obj.vessel_ownership.vessel:
            return obj.vessel_ownership.vessel.rego_no
        else:
            return ''


class StickerSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    approval = ApprovalSimpleSerializer()
    sent_date = serializers.SerializerMethodField()
    sticker_action_details = StickerActionDetailSerializer(many=True)
    fee_constructor = FeeConstructorSerializer()
    fee_season = serializers.SerializerMethodField()
    vessel_rego_no = serializers.SerializerMethodField()
    vessel = serializers.SerializerMethodField()
    moorings = serializers.SerializerMethodField()
    dcv_permit = DcvPermitSimpleSerializer()
    invoices = serializers.SerializerMethodField()
    can_view_payment_details = serializers.SerializerMethodField()
    migrated = serializers.SerializerMethodField()

    class Meta:
        model = Sticker
        fields = (
            'id',
            'number',
            'status',
            'approval',
            'printing_date',
            'mailing_date',
            'sent_date',
            'sticker_action_details',
            'fee_constructor',
            'vessel_rego_no',
            'vessel',
            'moorings',
            'dcv_permit',
            'fee_season',
            'invoices',
            'can_view_payment_details',
            'date_created',
            'date_updated',
            'postal_address_line1',
            'postal_address_line2',
            'postal_address_line3',
            'postal_address_locality',
            'postal_address_state',
            'postal_address_country',
            'postal_address_postcode',
            'migrated',
        )
        datatables_always_serialize = (
            'id',
            'number',
            'status',
            'approval',
            'printing_date',
            'mailing_date',
            'sent_date',
            'sticker_action_details',
            'fee_constructor',
            'vessel_rego_no',
            'vessel',
            'moorings',
            'dcv_permit',
            'fee_season',
            'invoices',
            'can_view_payment_details',
            'date_created',
            'date_updated',
            'postal_address_line1',
            'postal_address_line2',
            'postal_address_line3',
            'postal_address_locality',
            'postal_address_state',
            'postal_address_country',
            'postal_address_postcode',
            'migrated',
        )

    def get_fee_season(self, obj):
        if obj.fee_season:
            return obj.fee_season.name
        return ''

    def get_vessel_rego_no(self, obj):
        if obj.vessel_ownership and obj.vessel_ownership.vessel:
            return obj.vessel_ownership.vessel.rego_no
        else:
            return ''

    def get_vessel(self, obj):
        if obj.vessel_ownership and obj.vessel_ownership.vessel:
            return {
                'id': obj.vessel_ownership.vessel.id,
                'rego_no': obj.vessel_ownership.vessel.rego_no,
            }
        else:
            return {
                'id': '',
                'rego_no': '',
            }

    def get_can_view_payment_details(self, proposal):
        if 'request' in self.context:
            from mooringlicensing.components.main.utils import is_payment_officer
            return is_payment_officer(self.context['request'].user)

    def get_invoices(self, obj):
        invoices = obj.get_invoices()
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

    def get_moorings(self, obj):
        moorings = obj.get_moorings()
        serializers = MooringSimpleSerializer(moorings, many=True)
        return serializers.data

    def get_status(self, obj):
        choices = dict(Sticker.STATUS_CHOICES)
        return {'code': obj.status, 'display': choices[obj.status]}

    def get_sent_date(self, sticker):
        if sticker.sticker_printing_batch and sticker.sticker_printing_batch.emailed_datetime:
            return sticker.sticker_printing_batch.emailed_datetime.date()
        return None
    
    def get_migrated(self,sticker):
        if sticker.approval:
            return sticker.approval.migrated
        return False


class NonExportedStickerSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    approval = ApprovalSimpleSerializer()
    sticker_action_details = StickerActionDetailSerializer(many=True)
    vessel_rego_no = serializers.SerializerMethodField()
    vessel = serializers.SerializerMethodField()
    moorings = serializers.SerializerMethodField()
    dcv_permit = DcvPermitSimpleSerializer()
    migrated = serializers.SerializerMethodField()

    class Meta:
        model = Sticker
        fields = (
            'id',
            'status',
            'approval',
            'sticker_action_details',
            'vessel_rego_no',
            'vessel',
            'moorings',
            'dcv_permit',
            'date_created',
            'date_updated',
            'postal_address_line1',
            'postal_address_line2',
            'postal_address_line3',
            'postal_address_locality',
            'postal_address_state',
            'postal_address_country',
            'postal_address_postcode',
            'migrated',
        )
        datatables_always_serialize = (
            'id',
            'status',
            'approval',
            'sticker_action_details',
            'vessel_rego_no',
            'vessel',
            'moorings',
            'dcv_permit',
            'date_created',
            'date_updated',
            'postal_address_line1',
            'postal_address_line2',
            'postal_address_line3',
            'postal_address_locality',
            'postal_address_state',
            'postal_address_country',
            'postal_address_postcode',
            'migrated',
        )

    def get_vessel_rego_no(self, obj):
        if obj.vessel_ownership and obj.vessel_ownership.vessel:
            return obj.vessel_ownership.vessel.rego_no
        else:
            return ''

    def get_vessel(self, obj):
        if obj.vessel_ownership and obj.vessel_ownership.vessel:
            return {
                'id': obj.vessel_ownership.vessel.id,
                'rego_no': obj.vessel_ownership.vessel.rego_no,
            }
        else:
            return {
                'id': '',
                'rego_no': '',
            }

    def get_moorings(self, obj):
        moorings = obj.get_moorings()
        serializers = MooringSimpleSerializer(moorings, many=True)
        return serializers.data

    def get_status(self, obj):
        choices = dict(Sticker.STATUS_CHOICES)
        return {'code': obj.status, 'display': choices[obj.status]}

    def get_migrated(self,sticker):
        if sticker.approval:
            return sticker.approval.migrated
        return False



class StickerPostalAddressSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sticker
        fields = (
            'id',
            'postal_address_line1',
            'postal_address_line2',
            'postal_address_line3',
            'postal_address_locality',
            'postal_address_state',
            'postal_address_country',
            'postal_address_postcode',
        )
        read_only = ('id',)

class ListDcvPermitSerializer(serializers.ModelSerializer):
    dcv_organisation_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    fee_season = serializers.SerializerMethodField()
    fee_invoice_url = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    dcv_permit_documents = serializers.SerializerMethodField()
    stickers = serializers.SerializerMethodField()
    display_create_sticker_action = serializers.SerializerMethodField()
    display_request_sticker_action = serializers.SerializerMethodField()
    display_update_sticker_address_action = serializers.SerializerMethodField()
    vessel_rego = serializers.CharField(source='dcv_vessel.rego_no')
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = DcvPermit
        fields = (
            'id',
            'migrated',
            'lodgement_number',
            'lodgement_datetime',
            'fee_season',
            'start_date',
            'end_date',
            'dcv_organisation_name',
            'status',
            'fee_invoice_url',
            'invoices',
            'dcv_permit_documents',
            'stickers',
            'display_create_sticker_action',
            'display_request_sticker_action',
            'display_update_sticker_address_action',
            'vessel_rego',
            'payment_status',
        )
        datatables_always_serialize = (
            'id',
            'migrated',
            'lodgement_number',
            'lodgement_datetime',
            'fee_season',
            'start_date',
            'end_date',
            'dcv_organisation_name',
            'status',
            'fee_invoice_url',
            'invoices',
            'dcv_permit_documents',
            'stickers',
            'display_create_sticker_action',
            'display_request_sticker_action',
            'display_update_sticker_address_action',
            'vessel_rego',
            'payment_status',
        )

    def get_payment_status(self, obj):
        try:
            dcv_permit_fee = obj.dcv_permit_fees.order_by('-id').first()
            if dcv_permit_fee:
                invoice = Invoice.objects.get(reference=dcv_permit_fee.invoice_reference)
                inv_props = obj.get_invoice_property_cache()
                invoice_payment_status = inv_props[str(invoice.id)]["payment_status"]
                if invoice_payment_status == 'unpaid':
                    return 'Unpaid'
                elif invoice_payment_status == 'partially_paid':
                    return 'Partially Paid'
                elif invoice_payment_status == 'paid':
                    return 'Paid'
                else:
                    return 'Over Paid'
            else:
                if obj.migrated:
                    return 'Migrated'
                return 'Unpaid'
        except Exception as e:
            logger.warning(f'Payment status of the DcvPermit: [{obj}] is unavailable - {e}')
            return 'Unavailable'

    def get_stickers(self, obj):
        stickers = []
        for sticker in obj.stickers.filter(status__in=Sticker.EXPOSED_STATUS):
            serializer = StickerSerializer(sticker)
            stickers.append(serializer.data)
        return stickers

    def get_display_create_sticker_action(self, obj):
        display = True
        if obj.stickers.exclude(status__in=[Sticker.STICKER_STATUS_LOST,]).count():
            display = False
        return display
    
    def get_display_request_sticker_action(self, obj):
        display = False
        if obj.stickers.exclude(status__in=[Sticker.STICKER_STATUS_LOST,]).count():
            display = True
        return display
    
    def get_display_update_sticker_address_action(self, obj):
        display = False
        if obj.stickers.filter(
            status__in=[Sticker.STICKER_STATUS_CURRENT, 
                        Sticker.STICKER_STATUS_READY, 
                        Sticker.STICKER_STATUS_NOT_READY_YET, 
                        Sticker.STICKER_STATUS_AWAITING_PRINTING]
            ).count() > 0:
            display = True
        return display

    def get_dcv_permit_documents(self, obj):
        permit_urls = []
        for permit in obj.dcv_permit_documents.all():
            permit_urls.append(permit._file.url)
        return permit_urls

    def get_invoices(self, obj):
        invoice_references = [item.invoice_reference for item in obj.dcv_permit_fees.all()]
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

    def get_fee_invoice_url(self, obj):
        url = f'/ledger-toolkit-api/invoice-pdf/{obj.invoice.reference}/' if obj.invoice else ''
        return url

    def get_dcv_organisation_name(self, obj):
        try:
            if obj.dcv_organisation:
                return obj.dcv_organisation.name
            else:
                return obj.submitter_obj.get_full_name() + ' (P)'
        except:
            return ''

    def get_status(self, obj):
        status = ''
        if obj.status:
            status = obj.status[1]
        return status

    def get_fee_season(self, obj):
        fee_season = ''
        if obj.fee_season:
            fee_season = obj.fee_season.name
        return fee_season


class ListDcvAdmissionSerializer(serializers.ModelSerializer):
    lodgement_date = serializers.SerializerMethodField()
    fee_invoice_url = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    admission_urls = serializers.SerializerMethodField()
    arrivals = DcvAdmissionArrivalSerializer(source='dcv_admission_arrivals', many=True)

    class Meta:
        model = DcvAdmission
        fields = (
            'id',
            'lodgement_number',
            'lodgement_date',
            'fee_invoice_url',
            'invoices',
            'admission_urls',
            'arrivals',
            )
        datatables_always_serialize = (
            'id',
            'lodgement_number',
            'lodgement_date',
            'fee_invoice_url',
            'invoices',
            'admission_urls',
            'arrivals',
            )

    def get_admission_urls(self, obj):
        admission_urls = []
        for admission in obj.dcv_admission_documents.all():
            admission_urls.append(admission._file.url)
        return admission_urls

    def get_invoices(self, obj):
        try:
            invoice_references = [item.invoice_reference for item in obj.dcv_admission_fees.all()]
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
        except Exception as e:
            logger.warning(f'Exception raised when retrieving the invoice of the item : [{obj}] - [{e}].')
            return ''

    def get_fee_invoice_url(self, obj):
        try:
            url = f'/ledger-toolkit-api/invoice-pdf/{obj.invoice.reference}/' if obj.invoice else ''
            return url
        except Exception as e:
            logger.warning(f'Exception raised when retrieving the invoice reference of the item: [{obj}].')
            return '---'

    def get_lodgement_date(self, obj):
        lodgement_datetime = ''
        if obj.lodgement_datetime:
            lodgement_datetime = obj.lodgement_datetime.strftime('%d/%m/%Y')
        return lodgement_datetime


class ApprovalHistorySerializer(serializers.ModelSerializer):
    approval_letter = serializers.SerializerMethodField()
    sticker_numbers = serializers.SerializerMethodField()
    approval_lodgement_number = serializers.SerializerMethodField()
    approval_type_description = serializers.SerializerMethodField()
    approval_status = serializers.SerializerMethodField()
    holder = serializers.SerializerMethodField()
    start_date_str = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalHistory
        fields = (
                'id',
                'approval_lodgement_number',
                'approval_type_description',
                'approval_status',
                'holder',
                'start_date_str',
                'sticker_numbers',
                'reason',
                'approval_letter',
                )
        datatables_always_serialize = (
                'id',
                'approval_lodgement_number',
                'approval_type_description',
                'approval_status',
                'holder',
                'start_date_str',
                'sticker_numbers',
                'reason',
                'approval_letter',
                )

    def get_approval_letter(self ,obj):
        if obj.approval_letter and obj.approval_letter._file:
            return obj.approval_letter._file.url

    def get_approval_status(self, obj):
        return obj.approval.get_status_display()

    def get_holder(self, obj):
        return obj.approval.current_proposal.proposal_applicant.get_full_name()

    def get_sticker_numbers(self, obj):
        numbers = ""
        for sticker in obj.stickers.all():
            if numbers:
                numbers += ',\n' + sticker.number
            else:
                numbers += sticker.number
        return numbers

    def get_approval_type_description(self, obj):
        return obj.approval.child_obj.description

    def get_approval_lodgement_number(self, obj):
        return obj.approval.lodgement_number

    def get_start_date_str(self, obj):
        start_date = ''
        if obj.start_date:
            start_date = obj.start_date.strftime('%d/%m/%Y')
        return start_date

