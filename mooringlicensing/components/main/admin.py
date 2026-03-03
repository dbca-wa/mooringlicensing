from django import forms
from django.contrib import admin

from mooringlicensing.components.main.models import (
    VesselSizeCategory, VesselSizeCategoryGroup, ApplicationType, 
    NumberOfDaysSetting, NumberOfDaysType, Document, 
    FileExtensionWhitelist, Notice, JobQueue
)
from mooringlicensing.components.payments_ml.models import OracleCodeItem
from django.utils.html import mark_safe
from django.apps import apps
from django.utils.html import strip_tags
from django_summernote.widgets import SummernoteWidget

@admin.register(JobQueue)
class JobQueueAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user',
        'job_cmd',
        'status',
        'created',
        'processed_dt',
    ]
    readonly_fields = [
        'id',
        'job_cmd',
        'status',
        'parameters_json',
        'processed_dt',
        'user',
        'created',
        'system_id',
    ]
    list_filter = ['status']
    ordering = ['-id', ]

    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

class NoticeForm(forms.ModelForm):
    message = forms.CharField(
        widget=SummernoteWidget(
            attrs={'summernote': {'toolbar': [['style', ['bold', 'italic', 'underline', 'strikethrough', 'fontsize']], ['insert', ['link']]]}}
        )
    )

    class Meta:
        model = Notice
        fields = '__all__'

@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    form = NoticeForm
    list_display = ('formatted_message', 'notice_type', 'order', 'created', 'active', 'page')
    readonly_fields = ['created',]
    search_fields = ('page',)

    def save_model(self, request, obj, form, change):
        obj.save(exclude_sanitise=["message"])

    def formatted_message(self, obj):
        return f"{strip_tags(obj.message).replace('&nbsp;', ' ')}"
    formatted_message.short_description = 'Message'

class VesselSizeCategoryForm(forms.ModelForm):

    model = VesselSizeCategory
    fields = '__all__'

    def clean_name(self):
        data = self.cleaned_data.get('name')
        if self.instance != None and self.instance.pk:
            if not self.instance.is_editable:
                if data != self.instance.name:
                    raise forms.ValidationError('Name cannot be changed once used for payment calculation.')
        return data

    def clean_start_size(self):
        data = self.cleaned_data.get('start_size')
        if self.instance != None and self.instance.pk:
            if not self.instance.is_editable:
                if data != self.instance.start_size:
                    raise forms.ValidationError('Start size cannot be changed once used for payment calculation.')
        return data

    def clean_include_start_size(self):
        data = self.cleaned_data.get('include_start_size')
        if self.instance != None and self.instance.pk:
            if not self.instance.is_editable:
                if data != self.instance.include_start_size:
                    raise forms.ValidationError('Include start size cannot be changed once used for payment calculation.')
        return data

    def clean(self):
        cleaned_data = super(VesselSizeCategoryForm, self).clean()
        return cleaned_data


class VesselSizeCategoryFormset(forms.models.BaseInlineFormSet):

    def clean(self):
        '''
        Validate forms as a whole
        '''
        null_vessel_count = 0
        size_list = []

        if self.instance != None and self.instance.pk:
            if not self.instance.is_editable:
                raise forms.ValidationError('{} cannot be changed once used for payment calculation.'.format(self.instance))

        for form in self.forms:
            if form.cleaned_data['null_vessel']:
                null_vessel_count += 1
            if form.cleaned_data.get('start_size') in size_list:
                raise forms.ValidationError('There is a duplicate vessel size: {}'.format(form.cleaned_data['start_size']))
            else:
                size_list.append(form.cleaned_data['start_size'])

        if null_vessel_count > 1:
            raise forms.ValidationError('There can be at most one null-vessel catergory.  There are {} defined.'.format(null_vessel_count))


class VesselSizeCategoryInline(admin.TabularInline):
    model = VesselSizeCategory
    extra = 0
    can_delete = True
    form = VesselSizeCategoryForm
    formset = VesselSizeCategoryFormset


class VesselSizeCategoryGroupForm(forms.ModelForm):

    model = VesselSizeCategoryGroup
    fields = '__all__'

    def clean_name(self):
        data = self.cleaned_data.get('name')

        if self.instance != None and self.instance.pk:
            if not self.instance.is_editable:
                if data != self.instance.name:
                    raise forms.ValidationError('Name cannot be changed once used for payment calculation.')
            if not data:
                raise forms.ValidationError('Please enter the name field.')

        return data

    def clean(self):
        cleaned_data = super(VesselSizeCategoryGroupForm, self).clean()

        return cleaned_data


@admin.register(VesselSizeCategoryGroup)
class VesselSizeCategoryGroupAdmin(admin.ModelAdmin):
    inlines = [VesselSizeCategoryInline,]
    form = VesselSizeCategoryGroupForm
    list_display = ['name', 'get_vessel_size_categories',]

    def get_vessel_size_categories(self, obj):
        aho = list(obj.vessel_size_categories.all())
        baka = '<br />'.join(str(v) for v in aho)
        return mark_safe(baka)

    get_vessel_size_categories.short_description = 'vessel size category'


class OracleCodeItemInline(admin.TabularInline):
    model = OracleCodeItem
    extra = 0
    can_delete = True

    def has_delete_permission(self, request, obj=None):
        if obj.oracle_code_items.count() <= 1:
            return False
        return True


@admin.register(ApplicationType)
class ApplicationTypeAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'code', 'description', 'get_value_today', 'get_enforcement_date',]
    readonly_fields = ['code', 'description',]
    inlines = [OracleCodeItemInline,]

    def get_actions(self, request):
        actions = super(ApplicationTypeAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def get_value_today(self, obj):
        try:
            return obj.get_oracle_code_by_date()
        except:
            return '(not found, please add)'

    def get_enforcement_date(self, obj):
        try:
            return obj.get_enforcement_date_by_date()
        except:
            return '(not found, please add)'

    get_value_today.short_description = 'Oracle code (current)'
    get_enforcement_date.short_description = 'Since'


class NumberOfDaysSettingInline(admin.TabularInline):
    model = NumberOfDaysSetting
    extra = 0
    can_delete = True


@admin.register(NumberOfDaysType)
class NumberOfDaysTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'number_by_date',]
    list_display_links = ['name',]
    fields = ['name', 'description',]
    inlines = [NumberOfDaysSettingInline,]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class ModelForm(forms.ModelForm):
    choices = (
        (
            "all",
            "all",
        ),
    ) + tuple(
        map(
            lambda m: (m, m),
            filter(
                lambda m: Document
                in apps.get_app_config("mooringlicensing").models[m].__bases__,
                apps.get_app_config("mooringlicensing").models,
            ),
        )
    )

    model = forms.ChoiceField(choices=choices)

@admin.register(FileExtensionWhitelist)
class FileExtensionWhitelistAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "model",
    )
    list_display = (
        "name",
        "model",
    )
    form = ModelForm