from django.conf import settings
from ledger.accounts.models import EmailUser,Address
from mooringlicensing.components.compliances.models import (
    Compliance, ComplianceUserAction, ComplianceLogEntry, ComplianceAmendmentRequest, ComplianceAmendmentReason
)
from mooringlicensing.components.proposals.serializers import ProposalRequirementSerializer
from rest_framework import serializers


class EmailUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailUser
        fields = ('id','email','first_name','last_name','title','organisation')

class ComplianceSerializer(serializers.ModelSerializer):
    #regions = serializers.CharField(source='proposal.region')
    #activity = serializers.CharField(source='proposal.activity')
    title = serializers.CharField(source='proposal.title')
    holder = serializers.CharField(source='proposal.applicant')
    processing_status = serializers.SerializerMethodField(read_only=True)
    customer_status = serializers.SerializerMethodField(read_only=True)
    submitter = serializers.SerializerMethodField(read_only=True)
    documents = serializers.SerializerMethodField()
    #submitter = serializers.CharField(source='submitter.get_full_name')
    submitter = serializers.SerializerMethodField(read_only=True)
    allowed_assessors = EmailUserSerializer(many=True)
    #assigned_to = serializers.CharField(source='assigned_to.get_full_name')
    assigned_to = serializers.SerializerMethodField(read_only=True)
    requirement = serializers.CharField(source='requirement.requirement', required=False, allow_null=True)
    approval_lodgement_number = serializers.SerializerMethodField()
    #application_type = serializers.SerializerMethodField(read_only=True)
    application_type_code = serializers.SerializerMethodField()
    application_type_text = serializers.SerializerMethodField()
    application_type_dict = serializers.SerializerMethodField()


    class Meta:
        model = Compliance
        fields = (
            'id',
            'proposal',
            'due_date',
            'processing_status',
            'customer_status',
            #'regions',
            #'activity',
            'title',
            'text',
            'holder',
            'assigned_to',
            'approval',
            'documents',
            'requirement',
            'can_user_view',
            'can_process',
            'reference',
            'lodgement_number',
            'lodgement_date',
            'submitter',
            'allowed_assessors',
            'lodgement_date',
            'approval_lodgement_number',
            'num_participants',
            'participant_number_required',
            'fee_invoice_reference',
            'fee_paid',
            'application_type_code',
            'application_type_text',
            'application_type_dict',

        )

    def get_documents(self,obj):
        return [[d.name,d._file.url,d.can_delete,d.id] for d in obj.documents.all()]

    def get_approval_lodgement_number(self,obj):
        return obj.approval.lodgement_number

    def get_assigned_to(self,obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name()
        return None

    def get_submitter(self,obj):
        if obj.submitter:
            return obj.submitter.get_full_name()
        return None

    #def get_application_type(self,obj):
     #   if obj.proposal.application_type:
      #      return obj.proposal.application_type.name
       # return None
    def get_application_type_code(self, obj):
        return obj.proposal.application_type_code

    def get_application_type_text(self, obj):
        return obj.proposal.child_obj.description

    def get_application_type_dict(self, obj):
        return {
            'code': obj.proposal.child_obj.code,
            'description': obj.proposal.child_obj.description,
        }

    def get_processing_status(self, obj):
        return obj.get_processing_status_display()

    def get_customer_status(self, obj):
        return obj.get_customer_status_display()



class InternalComplianceSerializer(serializers.ModelSerializer):
    #regions = serializers.CharField(source='proposal.region')
    #activity = serializers.CharField(source='proposal.activity')
    title = serializers.CharField(source='proposal.title')
    holder = serializers.CharField(source='proposal.applicant')
    processing_status = serializers.SerializerMethodField(read_only=True)
    customer_status = serializers.SerializerMethodField(read_only=True)
    submitter = serializers.SerializerMethodField(read_only=True)
    documents = serializers.SerializerMethodField()
    #submitter = serializers.CharField(source='submitter.get_full_name')
    submitter = serializers.SerializerMethodField(read_only=True)
    allowed_assessors = EmailUserSerializer(many=True)
    #assigned_to = serializers.CharField(source='assigned_to.get_full_name')
    #assigned_to = serializers.SerializerMethodField(read_only=True)
    requirement = serializers.CharField(source='requirement.requirement', required=False, allow_null=True)
    approval_lodgement_number = serializers.SerializerMethodField()


    class Meta:
        model = Compliance
        fields = (
            'id',
            'proposal',
            'due_date',
            'processing_status',
            'customer_status',
            #'regions',
            #'activity',
            'title',
            'text',
            'holder',
            'assigned_to',
            'approval',
            'documents',
            'requirement',
            'can_user_view',
            'can_process',
            'reference',
            'lodgement_number',
            'lodgement_date',
            'submitter',
            'allowed_assessors',
            'lodgement_date',
            'approval_lodgement_number',
            'participant_number_required',
            'num_participants',
            'fee_invoice_reference',
            'fee_paid',
        )

    def get_documents(self,obj):
        return [[d.name,d._file.url,d.can_delete,d.id] for d in obj.documents.all()]

    def get_approval_lodgement_number(self,obj):
        return obj.approval.lodgement_number

    # def get_assigned_to(self,obj):
    #     if obj.assigned_to:
    #         return obj.assigned_to.get_full_name()
    #     return None

    def get_submitter(self,obj):
        if obj.submitter:
            return obj.submitter.get_full_name()
        return None

    def get_processing_status(self, obj):
        return obj.get_processing_status_display()

    def get_customer_status(self, obj):
        return obj.get_customer_status_display()


class SaveComplianceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Compliance
        fields = (
            'id',
            'title',
            'text',
            'num_participants',
        )

class ComplianceActionSerializer(serializers.ModelSerializer):
    who = serializers.CharField(source='who.get_full_name')
    class Meta:
        model = ComplianceUserAction
        fields = '__all__'

class ComplianceCommsSerializer(serializers.ModelSerializer):
    documents = serializers.SerializerMethodField()
    class Meta:
        model = ComplianceLogEntry
        fields = '__all__'
    def get_documents(self,obj):
        return [[d.name,d._file.url] for d in obj.documents.all()]

class ComplianceAmendmentRequestSerializer(serializers.ModelSerializer):
    #reason = serializers.SerializerMethodField()

    class Meta:
        model = ComplianceAmendmentRequest
        fields = '__all__'

    # def get_reason (self,obj):
    #     return obj.get_reason_display()

class CompAmendmentRequestDisplaySerializer(serializers.ModelSerializer):
    reason = serializers.SerializerMethodField()

    class Meta:
        model = ComplianceAmendmentRequest
        fields = '__all__'

    def get_reason (self,obj):
        #return obj.get_reason_display()
        return obj.reason.reason if obj.reason else None


class ListComplianceSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    approval_number = serializers.SerializerMethodField()
    requirement = ProposalRequirementSerializer()
    approval_type = serializers.SerializerMethodField()
    approval_submitter = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Compliance
        fields = (
            'id',
            'lodgement_number',
            'status',
            'approval_number',
            'requirement',
            'approval_type',
            'approval_submitter',
            'assigned_to_name',
            'can_process',
        )
        datatables_always_serialize = (
            'id',
            'lodgement_number',
            'status',
            'approval_number',
            'requirement',
            'approval_type',
            'approval_submitter',
            'assigned_to_name',
            'can_process',
        )

    def get_status(self, obj):
        return obj.get_customer_status_display()

    def get_approval_number(self, obj):
        return obj.approval.lodgement_number

    def get_approval_type(self, obj):
        if obj.approval.child_obj:
            return obj.approval.child_obj.description

    def get_approval_submitter(self, obj):
        return obj.approval.submitter.get_full_name()

    def get_assigned_to_name(self, obj):
        assigned_to = ''
        if obj.assigned_to:
            assigned_to = obj.assigned_to.get_full_name()
        return assigned_to

