from django.contrib import admin

from mooringlicensing.components.approvals import models
from mooringlicensing.ledger_api_utils import retrieve_email_userro


@admin.register(models.Sticker)
class StickerAdmin(admin.ModelAdmin):
    list_display = ['id', 'number', 'status', 'approval', 'dcv_permit', 'printing_date', 'mailing_date', 'fee_season', 'date_created', 'date_updated',]
    search_fields = ['id', 'number', 'approval__lodgement_number',]
    readonly_fields = ['sticker_printing_batch','sticker_printing_response','approval','dcv_permit','fee_constructor','fee_season','vessel_ownership','proposal_initiated','sticker_to_replace',]
    list_filter = ['status',]
    list_display_links = ['id', 'number',]
    ordering = ['-id', ]


@admin.register(models.Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = [
        'lodgement_number',
        'status',
        'get_submitter',
        'issue_date',
        'start_date',
        'expiry_date',
        'current_proposal',
        'applicant',
    ]
    search_fields = ['lodgement_number',]
    readonly_fields = ['licence_document', 'authorised_user_summary_document', 'current_proposal', 'renewal_document']
    list_filter = ('status',)

    def get_submitter(self, obj):
        if obj.submitter:
            return retrieve_email_userro(obj.submitter)
        else:
            return ''

    get_submitter.short_description = 'submitter'  # Rename column header

@admin.register(models.MooringOnApproval)
class MooringOnApprovalAdmin(admin.ModelAdmin):
    list_display = [
        'approval__lodgement_number',
        'mooring__name',
        'sticker__number',
        'end_date',
        'site_licensee',
        'migrated',
    ]
    search_fields = ['approval__lodgement_number','mooring__name','sticker__number']
    readonly_fields = ['approval','mooring','sticker','previous_sticker', 'site_licensee', 'migrated']
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False