import logging

from django.conf import settings
from ledger.accounts.models import EmailUser
from ledger.payments.models import Invoice
from django.db.models import Q, Min, Count

from mooringlicensing.components.main import serializers
from mooringlicensing.components.payments_ml.serializers import DcvPermitSerializer, FeeConstructorSerializer, \
    DcvAdmissionArrivalSerializer, DcvPermitSimpleSerializer
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
    AuthorisedUserPermit, StickerActionDetail, ApprovalHistory, MooringOnApproval,
)
from mooringlicensing.components.organisations.models import (
    Organisation
)
from mooringlicensing.components.main.serializers import CommunicationLogEntrySerializer, InvoiceSerializer
from mooringlicensing.components.proposals.serializers import InternalProposalSerializer, \
    MooringSimpleSerializer  # EmailUserAppViewSerializer
from mooringlicensing.components.users.serializers import UserSerializer
from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist


logger = logging.getLogger('mooringlicensing')


class EmailUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = EmailUser
        fields = (
                'id',
                'email',
                'first_name',
                'last_name',
                'title',
                'organisation',
                'full_name',
                )

    def get_full_name(self, obj):
        return obj.get_full_name()


class ApprovalPaymentSerializer(serializers.ModelSerializer):
    org_applicant = serializers.SerializerMethodField(read_only=True)
    bpay_allowed = serializers.SerializerMethodField(read_only=True)
    monthly_invoicing_allowed = serializers.SerializerMethodField(read_only=True)
    other_allowed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Approval
        fields = (
            'lodgement_number',
            'current_proposal',
            'expiry_date',
            'org_applicant',
            'bpay_allowed',
            'monthly_invoicing_allowed',
            'other_allowed',
        )
        read_only_fields = (
            'lodgement_number',
            'current_proposal',
            'expiry_date',
            'org_applicant',
            'bpay_allowed',
            'monthly_invoicing_allowed',
            'other_allowed',
        )

    def get_org_applicant(self,obj):
        return obj.org_applicant.name if obj.org_applicant else None

    def get_bpay_allowed(self,obj):
        return obj.bpay_allowed

    def get_monthly_invoicing_allowed(self,obj):
        return obj.monthly_invoicing_allowed

    def get_other_allowed(self,obj):
        return settings.OTHER_PAYMENT_ALLOWED


class _ApprovalPaymentSerializer(serializers.ModelSerializer):
    applicant = serializers.SerializerMethodField(read_only=True)
    applicant_type = serializers.SerializerMethodField(read_only=True)
    applicant_id = serializers.SerializerMethodField(read_only=True)
    status = serializers.CharField(source='get_status_display')
    title = serializers.CharField(source='current_proposal.title')
    application_type = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Approval
        fields = (
            'id',
            'lodgement_number',
            'current_proposal',
            'title',
            'issue_date',
            'start_date',
            'expiry_date',
            'applicant',
            'applicant_type',
            'applicant_id',
            'status',
            'cancellation_date',
            'application_type',
        )

    def get_application_type(self,obj):
        if obj.current_proposal.application_type:
            return obj.current_proposal.application_type.name
        return None

    def get_applicant(self,obj):
        return obj.applicant.name if isinstance(obj.applicant, Organisation) else obj.applicant

    def get_applicant_type(self,obj):
        return obj.applicant_type

    def get_applicant_id(self,obj):
        return obj.applicant_id


class DcvOrganisationSerializer(serializers.ModelSerializer):
    def validate(self, data):
        field_errors = {}
        non_field_errors = []

        if not data['name']:
            field_errors['name'] = ['Please enter organisation name.',]
        if not data['abn']:
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


class LookupDcvVesselSerializer(serializers.ModelSerializer):
    class Meta:
        model = DcvVessel
        fields = (
                'id',
                'rego_no',
                'vessel_name',
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


class ApprovalExtendSerializer(serializers.Serializer):
    extend_details = serializers.CharField()

class ApprovalCancellationSerializer(serializers.Serializer):
    cancellation_date = serializers.DateField(input_formats=['%d/%m/%Y'])
    cancellation_details = serializers.CharField()

class ApprovalSuspensionSerializer(serializers.Serializer):
    from_date = serializers.DateField(input_formats=['%d/%m/%Y'])
    to_date = serializers.DateField(input_formats=['%d/%m/%Y'], required=False, allow_null=True)
    suspension_details = serializers.CharField()

class ApprovalSurrenderSerializer(serializers.Serializer):
    surrender_date = serializers.DateField(input_formats=['%d/%m/%Y'])
    surrender_details = serializers.CharField()


class ApprovalUserActionSerializer(serializers.ModelSerializer):
    who = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalUserAction
        fields = '__all__'

    def get_who(self, obj):
        if obj.who:
            return obj.who.get_full_name()
        else:
            return 'System'


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
    submitter = UserSerializer()
    current_proposal = InternalProposalSerializer()
    licence_document = serializers.CharField(source='licence_document._file.url')
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
    allowed_assessors = EmailUserSerializer(many=True)
    stickers = serializers.SerializerMethodField()
    is_approver = serializers.SerializerMethodField()

    class Meta:
        model = Approval
        fields = (
            'id',
            'submitter',
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
            'can_reinstate',
            'amend_or_renew',
            'renewal_document',
            'renewal_sent',
            'allowed_assessors',
            'stickers',
            'licence_document',
            'is_approver',
        )

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
                    )
            for moa in moa_set:
                approval = moa.approval
                authorised_users.append({
                    "id": moa.id,
                    "lodgement_number": approval.lodgement_number,
                    "vessel_name": (
                        approval.current_proposal.vessel_details.vessel.latest_vessel_details.vessel_name
                        if approval.current_proposal.vessel_details else ''
                        ),
                    "holder": approval.submitter.get_full_name(),
                    "mobile": approval.submitter.mobile_number,
                    "email": approval.submitter.email,
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
                sticker_numbers = ''
                for sticker in obj.stickers.filter(
                        status__in=['current', 'ready', 'awaiting_printing', 'to_be_returned'],
                        vessel_ownership=vessel_ownership):
                    sticker_numbers += sticker.number + ', '
                sticker_numbers = sticker_numbers[0:-2]

                vessel_details.append({
                    "id": vessel.id,
                    "vessel_name": vessel.latest_vessel_details.vessel_name,
                    "rego_no": vessel.rego_no,
                    "sticker_numbers": sticker_numbers,
                    "owner": vessel_ownership.owner.emailuser.get_full_name(),
                    "mobile": vessel_ownership.owner.emailuser.mobile_number,
                    "email": vessel_ownership.owner.emailuser.email,
                    })
        return vessel_details

    def get_authorised_user_moorings_detail(self, obj):
        moorings = []
        if type(obj.child_obj) == AuthorisedUserPermit:
            for moa in obj.mooringonapproval_set.filter(end_date__isnull=True):
                if moa.mooring.mooring_licence:
                    licence_holder_data = UserSerializer(moa.mooring.mooring_licence.submitter).data
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
            for moa in obj.mooringonapproval_set.filter(mooring__mooring_licence__status='current'):
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
                obj.status == 'current' and
                obj.current_proposal.preferred_bay and
                obj.internal_status == 'waiting'
                ):
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
        return obj.get_status_display()

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
        submitter = ''
        if obj.submitter:
            submitter = obj.submitter.get_full_name()
        return submitter

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
    licence_document = serializers.CharField(source='licence_document._file.url')
    authorised_user_summary_document = serializers.CharField(source='authorised_user_summary_document._file.url')
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
    current_proposal_approved = serializers.SerializerMethodField()
    vessel_registration = serializers.SerializerMethodField()
    vessel_name = serializers.SerializerMethodField()
    offer_link = serializers.SerializerMethodField()
    ria_generated_proposals = serializers.SerializerMethodField()
    can_reissue = serializers.SerializerMethodField()
    can_external_action = serializers.SerializerMethodField()
    can_action = serializers.SerializerMethodField()
    can_reinstate = serializers.SerializerMethodField()
    amend_or_renew = serializers.SerializerMethodField()
    allowed_assessors_user = serializers.SerializerMethodField()
    stickers = serializers.SerializerMethodField()
    is_approver = serializers.SerializerMethodField()
    vessel_regos = serializers.SerializerMethodField()

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
            'expiry_date_str',
            'vessel_length',
            'vessel_draft',
            'preferred_mooring_bay',
            'preferred_mooring_bay_id',
            'current_proposal_number',
            'current_proposal_approved',
            'current_proposal_id',
            'vessel_registration',
            'vessel_name',
            'wla_order',
            'offer_link',
            'ria_generated_proposals',
            'can_reissue',
            'can_external_action',
            'can_action',
            'can_reinstate',
            'amend_or_renew',
            'renewal_document',
            'allowed_assessors_user',
            'stickers',
            'licence_document',
            'authorised_user_summary_document',
            'is_approver',
            'vessel_regos',
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
            'expiry_date_str',
            'vessel_length',
            'vessel_draft',
            'preferred_mooring_bay',
            'preferred_mooring_bay_id',
            'current_proposal_number',
            'current_proposal_approved',
            'current_proposal_id',
            'vessel_registration',
            'vessel_name',
            'wla_order',
            'offer_link',
            'ria_generated_proposals',
            'can_reissue',
            'can_external_action',
            'can_action',
            'can_reinstate',
            'amend_or_renew',
            'renewal_document',
            'allowed_assessors_user',
            'stickers',
            'licence_document',
            'authorised_user_summary_document',
            'is_approver',
            'vessel_regos',
        )

    def get_allowed_assessors_user(self, obj):
        request = self.context.get('request')
        if request:
            return obj.allowed_assessors_user(request)
        else:
            return False

    def get_current_proposal_approved(self, obj):
        return obj.current_proposal.processing_status == 'approved'

    def get_is_approver(self, obj):
        request = self.context.get('request')
        if request:
            return obj.is_approver(request.user)
        else:
            return False

    def get_stickers(self, obj):
        stickers = obj.stickers.filter(status__in=[Sticker.STICKER_STATUS_CURRENT, Sticker.STICKER_STATUS_AWAITING_PRINTING])
        list_return = [{'number': sticker.number, 'mailing_date': sticker.mailing_date} for sticker in stickers]
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

    def get_amend_or_renew(self,obj):
        return obj.amend_or_renew

    def get_vessel_regos(self, obj):
        regos = ''
        if type(obj.child_obj) == MooringLicence:
            for vessel_details in obj.child_obj.vessel_details_list:
                regos += '{}\n'.format(vessel_details.vessel.rego_no)
        else:
            regos += '{}\n'.format(obj.current_proposal.vessel_details.vessel.rego_no) if obj.current_proposal.vessel_details else ''
        return regos

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

    def get_authorised_user_moorings(self, obj):
        links = ''
        request = self.context.get('request')
        if type(obj.child_obj) == AuthorisedUserPermit:
            for mooring in obj.moorings.all():
                if request and request.GET.get('is_internal') and request.GET.get('is_internal') == 'true':
                    links += '<a href="/internal/moorings/{}">{}</a><br/>'.format(
                            mooring.id,
                            str(mooring),
                            )
                else:
                    links += '{}\n'.format(str(mooring))
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
                obj.status == 'current' and
                obj.current_proposal.preferred_bay and
                obj.internal_status == 'waiting'
                ):
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
        return obj.get_status_display()

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
        holder_str = ''
        if obj.submitter:
            holder_str = '<span>{}</br>{}</br>{}</br></span>'.format(
                    obj.submitter.get_full_name(),
                    obj.submitter.mobile_number,
                    obj.submitter.email
                    )
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


class LookupApprovalSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    approval_type_dict = serializers.SerializerMethodField()
    submitter_phone_number = serializers.SerializerMethodField()
    vessel_data = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

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
        )

    def get_url(self, obj):
        return '/internal/approval/{}'.format(obj.id)

    def get_status(self, obj):
        return obj.get_status_display()

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

    def get_submitter_phone_number(self, obj):
        return obj.submitter.mobile_number if obj.submitter.mobile_number else obj.submitter.phone_number

    def get_vessel_data(self, obj):
        vessel_data = []
        if type(obj.child_obj) != MooringLicence:
            vessel_data.append({
                "rego_no": obj.current_proposal.vessel_details.vessel.rego_no,
                "vessel_name": obj.current_proposal.vessel_details.vessel.latest_vessel_details.vessel_name,
                })
        else:
            for vessel_details in obj.child_obj.vessel_details_list:
                vessel_data.append({
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
    user_detail = EmailUserSerializer(source='user', read_only=True)

    class Meta:
        model = StickerActionDetail
        fields = (
            'id',
            'sticker',
            'reason',
            'date_created',
            'date_updated',
            'date_of_lost_sticker',
            'date_of_returned_sticker',
            'action',
            'user',  # For saving the user data
            'user_detail',  # For reading the user data
        )


class StickerForDcvSaveSerializer(serializers.ModelSerializer):

    class Meta:
        model = Sticker
        fields = (
            'status',
            'number',
            'dcv_permit',
            'mailing_date',
        )

    def validate(self, data):
        field_errors = {}
        non_field_errors = []

        from mooringlicensing.components.main.models import GlobalSettings
        min_number = GlobalSettings.objects.get(key=GlobalSettings.KEY_MINUMUM_STICKER_NUMBER_FOR_DCV_PERMIT).value
        if data['number'] < min_number:
            field_errors['number'] = ['DCV Sticker number must be greater than ' + GlobalSettings.KEY_MINUMUM_STICKER_NUMBER_FOR_DCV_PERMIT,]

        # Raise errors
        if field_errors:
            raise serializers.ValidationError(field_errors)
        if non_field_errors:
            raise serializers.ValidationError(non_field_errors)

        return data


class StickerSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    approval = ApprovalSimpleSerializer()
    sent_date = serializers.SerializerMethodField()
    sticker_action_details = StickerActionDetailSerializer(many=True)
    fee_constructor = FeeConstructorSerializer()
    fee_season = serializers.CharField(source='fee_season.name')
    vessel_rego_no = serializers.CharField(source='vessel_ownership.vessel.rego_no')
    moorings = serializers.SerializerMethodField()
    dcv_permit = DcvPermitSimpleSerializer()
    invoices = serializers.SerializerMethodField()
    can_view_payment_details = serializers.SerializerMethodField()

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
            'moorings',
            'dcv_permit',
            'fee_season',
            'invoices',
            'can_view_payment_details',
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
            'moorings',
            'dcv_permit',
            'fee_season',
            'invoices',
            'can_view_payment_details',
        )

    def get_can_view_payment_details(self, proposal):
        if 'request' in self.context:
            from mooringlicensing.components.main.utils import is_payment_officer
            return is_payment_officer(self.context['request'].user)

    def get_invoices(self, obj):
        invoices = obj.get_invoices()
        if not invoices:
            return ''
        else:
            serializer = InvoiceSerializer(invoices, many=True)
            return serializer.data

    def get_moorings(self, obj):
        moas = obj.mooringonapproval_set.filter(Q(end_date__isnull=True) & Q(mooring__mooring_licence__status=MooringLicence.APPROVAL_STATUS_CURRENT))
        moorings = []
        for moa in moas:
            moorings.append(moa.mooring)
        serializers = MooringSimpleSerializer(moorings, many=True)
        return serializers.data

    def get_status(self, obj):
        choices = dict(Sticker.STATUS_CHOICES)
        return {'code': obj.status, 'display': choices[obj.status]}

    def get_sent_date(self, sticker):
        if sticker.sticker_printing_batch and sticker.sticker_printing_batch.emailed_datetime:
            return sticker.sticker_printing_batch.emailed_datetime.date()
        return None


class ListDcvPermitSerializer(serializers.ModelSerializer):
    dcv_organisation_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    fee_season = serializers.SerializerMethodField()
    fee_invoice_url = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    permits = serializers.SerializerMethodField()
    stickers = serializers.SerializerMethodField()
    display_create_sticker_action = serializers.SerializerMethodField()

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
            'permits',
            'stickers',
            'display_create_sticker_action',
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
            'permits',
            'stickers',
            'display_create_sticker_action',
            )

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

    def get_permits(self, obj):
        permit_urls = []
        for permit in obj.permits.all():
            permit_urls.append(permit._file.url)
        return permit_urls

    def get_invoices(self, obj):
        invoice_references = [item.invoice_reference for item in obj.dcv_permit_fees.all()]
        invoices = Invoice.objects.filter(reference__in=invoice_references)
        if not invoices:
            return ''
        else:
            serializer = InvoiceSerializer(invoices, many=True)
            return serializer.data

    def get_fee_invoice_url(self, obj):
        url = '/payments/invoice-pdf/{}'.format(obj.invoice.reference) if obj.fee_paid else None
        return url

    def get_dcv_organisation_name(self, obj):
        try:
            if obj.dcv_organisation:
                return obj.dcv_organisation.name
            else:
                return obj.submitter.get_full_name() + ' (P)'
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
        for admission in obj.admissions.all():
            admission_urls.append(admission._file.url)
        return admission_urls

    def get_invoices(self, obj):
        invoice_references = [item.invoice_reference for item in obj.dcv_admission_fees.all()]
        invoices = Invoice.objects.filter(reference__in=invoice_references)
        if not invoices:
            return ''
        else:
            serializer = InvoiceSerializer(invoices, many=True)
            return serializer.data

    def get_fee_invoice_url(self, obj):
        url = '/payments/invoice-pdf/{}'.format(obj.invoice.reference) if obj.fee_paid else None
        return url

    def get_lodgement_date(self, obj):
        lodgement_datetime = ''
        if obj.lodgement_datetime:
            lodgement_datetime = obj.lodgement_datetime.strftime('%d/%m/%Y')
        return lodgement_datetime


class ApprovalHistorySerializer(serializers.ModelSerializer):
    #reason = serializers.SerializerMethodField()
    approval_letter = serializers.CharField(source='approval_letter._file.url')
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

    #def get_reason(self, obj):
     #   return ''

    def get_approval_status(self, obj):
        return obj.approval.get_status_display()

    def get_holder(self, obj):
        return obj.approval.submitter.get_full_name()

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

