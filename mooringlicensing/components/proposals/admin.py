import django.forms
from django.contrib import admin
from django.utils.html import mark_safe

from mooringlicensing.components.proposals import models
from mooringlicensing.components.proposals import forms
from mooringlicensing.components.main.models import (
    SystemMaintenance,
    GlobalSettings,
)
from reversion.admin import VersionAdmin as ReversionVersionAdmin
from mooringlicensing.components.proposals.models import StickerPrintingBatch, StickerPrintingResponse, \
    StickerPrintingContact, StickerPrintedContact, MooringBay, Mooring
from mooringlicensing.ledger_api_utils import retrieve_email_userro
from mooringlicensing.components.payments_ml.models import ApplicationFee

from django.core.exceptions import PermissionDenied
from django.urls import reverse
from reversion.models import Version
from django.contrib.admin.utils import unquote, quote

class VersionAdmin(ReversionVersionAdmin):

    def history_view(self, request, object_id, extra_context=None):

        if hasattr(self, 'has_view_or_change_permission'):
            if not self.has_view_or_change_permission(request):
                raise PermissionDenied
        else:
            if not self.has_change_permission(request):
                raise PermissionDenied

        opts = self.model._meta
        action_list = [
            {
                "revision": version.revision,
                "url": reverse(
                    f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_revision",
                    args=(quote(version.object_id), version.id)
                ),
            }
            for version
            in self._reversion_order_version_queryset(Version.objects.get_for_object_reference(
                self.model,
                unquote(object_id),
            ))
        ]
        # Compile the context.
        context = {"action_list": action_list}
        context.update(extra_context or {})
        return super(ReversionVersionAdmin, self).history_view(request, object_id, context)

class ProposalDocumentInline(admin.TabularInline):
    model = models.ProposalDocument
    extra = 0

class ApplicationFeeInline(admin.TabularInline):
    model = ApplicationFee
    extra = 0

@admin.register(models.ProposalType)
class ProposalTypeAdmin(admin.ModelAdmin):
    list_display = ['code','description']

@admin.register(models.AmendmentReason)
class AmendmentReasonAdmin(admin.ModelAdmin):
    list_display = ['reason']


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['id', 'name',]
    list_display_links = ['id', 'name',]
    search_fields = ['name',]


@admin.register(models.VesselRegistrationDocument)
class VesselRegistrationDocumentAdmin(admin.ModelAdmin):
    list_display = ['original_file_name', 'original_file_ext', 'proposal', 'vessel_ownership', '_file']
    readonly_fields = ['vessel_ownership', 'proposal']


@admin.register(models.VesselOwnership)
class VesselOwnershipAdmin(admin.ModelAdmin):
    list_display = ['id', 'owner', 'vessel', 'percentage', 'start_date', 'end_date', 'dot_name',]
    readonly_fields = ['owner','vessel']
    search_fields = ['vessel__rego_no']


@admin.register(models.VesselDetails)
class VesselDetailsAdmin(admin.ModelAdmin):
    list_display = ['id', 'vessel', 'vessel_type', 'vessel_name', 'vessel_length', 'vessel_draft',]
    readonly_fields = ['vessel']
    search_fields = ['vessel__rego_no','vessel_name',]


@admin.register(models.CompanyOwnership)
class CompanyOwnershipAdmin(admin.ModelAdmin):
    list_display = ['id', 'company', 'vessel', 'percentage',]
    readonly_fields = ['blocking_proposal','vessel','company']


@admin.register(models.Proposal)
class ProposalAdmin(VersionAdmin):
    list_display = ['id', 'lodgement_number', 'lodgement_date', 'processing_status', 'get_submitter', 'approval',]
    readonly_fields = ['vessel_ownership', 'listed_moorings', 'listed_vessels', 'vessel_details', 'allocated_mooring', 'approval', 'previous_application', 'waiting_list_allocation', 'fee_season']
    list_display_links = ['id', 'lodgement_number', ]
    inlines =[ProposalDocumentInline,ApplicationFeeInline,]
    search_fields = ['id', 'lodgement_number', 'approval__lodgement_number',]

    def get_submitter(self, obj):
        if obj.submitter:
            return retrieve_email_userro(obj.submitter)
        else:
            return '---'


@admin.register(models.ProposalStandardRequirement)
class ProposalStandardRequirementAdmin(admin.ModelAdmin):
    list_display = [
            'code',
            'text',
            'application_type',
            'obsolete',
            ]
    list_filter = ('application_type', 'obsolete',)

    def get_form(self, request, obj=None, **kwargs):
        form = super(ProposalStandardRequirementAdmin, self).get_form(request, obj, **kwargs)
        return form


@admin.register(SystemMaintenance)
class SystemMaintenanceAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'start_date', 'end_date', 'duration']
    ordering = ('start_date',)
    readonly_fields = ('duration',)
    form = forms.SystemMaintenanceAdminForm


@admin.register(MooringBay)
class MooringBayAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'mooring_bookings_id', 'active',]
    list_filter = ('active',)


@admin.register(Mooring)
class MooringAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'mooring_bay', 'active', 'vessel_size_limit', 'vessel_draft_limit', ]
    readonly_fields = ['mooring_licence', 'name', 'mooring_bay', 'active', 'vessel_size_limit', 'vessel_draft_limit', 'vessel_weight_limit', 'mooring_bookings_id', 'mooring_bookings_bay_id', 'mooring_bookings_mooring_specification']
    list_filter = ('active',)
    search_fields = ['name',]
    

    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    

class GlobalSettingsForm(django.forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(GlobalSettingsForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance', None)
        if instance:
            if instance.key == GlobalSettings.KEY_EXTERNAL_DASHBOARD_SECTIONS_LIST:
                self.fields['value'].help_text = 'Arrange the table names below in the order in which you want them to appear on the external dashboard page:<ul><li>LicencesAndPermitsTable</li><li>ApplicationsTable</li><li>CompliancesTable</li><li>WaitingListTable</li><li>AuthorisedUserApplicationsTable</li></ul>'


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', '_file',]
    ordering = ('key',)
    form = GlobalSettingsForm

    def get_fields(self, request, obj=None):
        if obj and obj.key in GlobalSettings.keys_for_file:
            return ['key', '_file',]
        else:
            return ['key', 'value', ]

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        return ['key',]

    def has_delete_permission(self, request, obj=None):
        if obj:
            if obj.key in [item[0] for item in GlobalSettings.keys]:
                return False
        return True


@admin.register(StickerPrintingContact)
class StickersPrintingContactAdmin(admin.ModelAdmin):
    list_display = ['email', 'type', 'enabled',]
    ordering = ('type', 'email',)


@admin.register(StickerPrintedContact)
class StickersPrintedContactAdmin(admin.ModelAdmin):
    list_display = ['email', 'type', 'enabled',]
    ordering = ('type', 'email',)


@admin.register(StickerPrintingBatch)
class StickersPrintingBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', '_file', 'uploaded_date', 'emailed_datetime',]
    list_display_links = ['id', 'name', '_file',]
    search_fields = ['name',]

    def get_actions(self, request):
        actions = super(StickersPrintingBatchAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions["delete_selected"]
        return actions

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [
            'id',
            'name',
            'emailed_datetime',
            'uploaded_date',
            '_file',
        ]

    def save_model(self, request, obj, form, change):
        pass

    def delete_model(self, request, obj):
        pass

    def save_related(self, request, form, formsets, change):
        pass


@admin.register(StickerPrintingResponse)
class StickersPrintingResponseAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'get_attached_file',
        'uploaded_date',
        'email_subject',
        'email_date',
        'processed',
        'no_errors_when_process',
    ]
    exclude = ['sticker_printing_response_email']
    search_fields = ['name',]
    list_filter = ('processed', 'no_errors_when_process',)

    def get_attached_file(self, obj):
        if obj._file:
            return mark_safe('<a href="{}">{}</a>'.format(obj._file.url, obj.name))
        return ''
    get_attached_file.short_description = 'File attached'

    def get_actions(self, request):
        actions = super(StickersPrintingResponseAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions["delete_selected"]
        return actions

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [
            'id',
            'name',
            'uploaded_date',
            '_file',
        ]

    def delete_model(self, request, obj):
        pass

    def save_related(self, request, form, formsets, change):
        pass

