from django.contrib import admin
from mooringlicensing.components.compliances import models
# Register your models here.


@admin.register(models.ComplianceAmendmentReason)
class ComplianceAmendmentReasonAdmin(admin.ModelAdmin):
    list_display = ['reason']

@admin.register(models.Compliance)
class ComplianceAdmin(admin.ModelAdmin):
    list_display = ['id', 'lodgement_number', 'proposal__lodgement_number', 'processing_status', 'approval__lodgement_number',]
    readonly_fields = ['proposal','approval','requirement']
    search_fields = ['id', 'lodgement_number', 'proposal__lodgement_number' ,'approval__lodgement_number',]