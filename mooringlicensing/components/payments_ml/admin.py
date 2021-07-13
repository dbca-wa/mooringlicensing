from dateutil.relativedelta import relativedelta
from django import forms
from django.contrib import admin
from django.db.models import Min

from mooringlicensing import settings
from mooringlicensing.components.main.models import ApplicationType
from mooringlicensing.components.payments_ml.models import FeeSeason, FeePeriod, FeeConstructor, FeeItem
from mooringlicensing.components.proposals.models import AnnualAdmissionApplication, AuthorisedUserApplication, \
    MooringLicenceApplication


class FeePeriodFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        num_of_periods = len(self.cleaned_data)
        if num_of_periods < 1:
            # No periods configured for this season
            raise forms.ValidationError('At lease one period must exist in a season.')
        elif num_of_periods == 1:
            # There is one period configured
            # All fine
            pass
        else:
            # There are more than one periods configured
            # Check if all the periods sit in one year span
            sorted_cleaned_data = sorted(self.cleaned_data, key=lambda item: item['start_date'])
            start_date = sorted_cleaned_data[0]['start_date']
            end_date = sorted_cleaned_data[num_of_periods - 1]['start_date']
            start_date_plus_year = start_date + relativedelta(years=1)
            if end_date < start_date_plus_year:
                # All periods sit within an year span
                pass
            else:
                raise forms.ValidationError('All periods must sit within one year span.')

            # Check if all the period have unique start_date
            temp = []
            for item in self.cleaned_data:
                if not item['start_date'] in temp:
                    temp.append(item['start_date'])
                else:
                    raise forms.ValidationError('Period\'s start date must be unique, but {} is duplicated.'.format(item['start_date']))

    # def clean_name(self):
    #     data = self.cleaned_data['name']
    #     if not self.instance.is_editable:
    #         if data != self.instance.name:
    #             raise forms.ValidationError('Fee period cannot be changed once used for payment calculation')
    #     return data


class FeePeriodForm(forms.ModelForm):
    class Meta:
        model = FeePeriod
        fields = '__all__'

    def clean_name(self):
        data = self.cleaned_data['name']
        if not self.instance.is_editable:
            if data != self.instance.name:
                raise forms.ValidationError('Fee period\'s name cannot be changed once used for payment calculation')
        return data

    def clean_start_date(self):
        data = self.cleaned_data['start_date']
        if not self.instance.is_editable:
            if data != self.instance.start_date:
                raise forms.ValidationError('Fee period\'s start date cannot be changed once used for payment calculation')
        return data

    def clean(self):
        cleaned_data = super(FeePeriodForm, self).clean()

        return cleaned_data


class FeePeriodInline(admin.TabularInline):
    model = FeePeriod
    extra = 0
    can_delete = True
    formset = FeePeriodFormSet
    form = FeePeriodForm


class FeeSeasonForm(forms.ModelForm):
    class Meta:
        model = FeeSeason
        fields = '__all__'

    def clean_name(self):
        data = self.cleaned_data['name']

        if not self.instance.is_editable:
            if data != self.instance.name:
                raise forms.ValidationError('Fee season cannot be changed once used for payment calculation')
        if not data:
            raise forms.ValidationError('Please enter the name field.')

        return data

    # def clean(self):
    #     cleaned_data = super(FeeSeasonForm, self).clean()
    #     if cleaned_data['name']:
    #         return cleaned_data
    #     else:
    #         raise forms.ValidationError('Please enter the name field.')


class FeeItemForm(forms.ModelForm):

    class Meta:
        model = FeeItem
        fields = '__all__'
        # fields = ('amount',)

    def clean_amount(self):
        data = self.cleaned_data['amount']
        if not self.instance.is_editable:
            if data != self.instance.amount:
                raise forms.ValidationError('Fee item cannot be changed once used for payment calculation')
        return data


class FeeItemInline(admin.TabularInline):
    model = FeeItem
    extra = 0
    can_delete = False
    readonly_fields = ('fee_period', 'vessel_size_category', 'proposal_type', 'age_group', 'admission_type')
    max_num = 0  # This removes 'Add another ...' button
    form = FeeItemForm

    def get_formset(self, request, obj=None, **kwargs):
        formset = super(FeeItemInline, self).get_formset(request, obj, **kwargs)
        # form = formset.form
        # widget = form.base_fields['fee_period'].widget
        # widget.can_change_related = False
        return formset

    def get_fields(self, request, obj=None):
        fields = super(FeeItemInline, self).get_fields(request, obj)
        if obj:
            if obj.application_type == ApplicationType.objects.get(code=settings.APPLICATION_TYPE_DCV_ADMISSION['code']):
                fields.remove('proposal_type')
            elif obj.application_type == ApplicationType.objects.get(code=settings.APPLICATION_TYPE_DCV_PERMIT['code']):
                fields.remove('proposal_type')
                fields.remove('age_group')
                fields.remove('admission_type')
            else:
                fields.remove('age_group')
                fields.remove('admission_type')
        return fields


class FeeConstructorForm(forms.ModelForm):
    class Meta:
        model = FeeConstructor
        fields = '__all__'

    def clean_application_type(self):
        data = self.cleaned_data['application_type']
        if not self.instance.is_editable:
            # This fee_constructor object has been used at least once.
            if data != self.instance.application_type:
                raise forms.ValidationError('Application type cannot be changed once used for payment calculation')
        return data

    def clean_vessel_size_category_group(self):
        data = self.cleaned_data['vessel_size_category_group']
        if not self.instance.is_editable:
            # This fee_constructor object has been used at least once.
            if data != self.instance.vessel_size_category_group:
                raise forms.ValidationError('Vessel size category group cannot be changed once used for payment calculation')
        return data

    def clean_fee_season(self):
        data = self.cleaned_data['fee_season']
        if not self.instance.is_editable:
            # This fee_constructor object has been used at least once.
            if data != self.instance.fee_season:
                raise forms.ValidationError('Fee season cannot be changed once used for payment calculation')
        return data

    def clean_incur_gst(self):
        data = self.cleaned_data['incur_gst']
        if not self.instance.is_editable:
            # This fee_constructor object has been used at least once.
            if data != self.instance.incur_gst:
                # Once used, application_type must not be changed
                raise forms.ValidationError('Incur gst cannot be changed once used for payment calculation')
        return data

    def clean(self):
        cleaned_data = super(FeeConstructorForm, self).clean()
        if len(self.changed_data) == 1 and self.changed_data[0] == 'enabled' and cleaned_data['enabled'] is False:
            # When change is setting 'enabled' field to False, no validation required
            return cleaned_data

        cleaned_application_type = cleaned_data.get('application_type', None)
        cleaned_fee_season = cleaned_data.get('fee_season', None)
        cleaned_vessel_size_category_group = cleaned_data.get('vessel_size_category_group', None)

        if cleaned_application_type and cleaned_application_type.code in (settings.APPLICATION_TYPE_DCV_PERMIT['code'], settings.APPLICATION_TYPE_DCV_ADMISSION['code']):
            # If application type is DcvPermit
            if cleaned_fee_season and cleaned_fee_season.fee_periods.count() > 1:
                # There are more than 1 periods in the season
                raise forms.ValidationError('The season for the {} cannot have more than 1 period.  Selected season: {} has {} periods.'.format(
                    cleaned_application_type.description,
                    cleaned_fee_season.name,
                    cleaned_fee_season.fee_periods.count(),
                ))
            if cleaned_vessel_size_category_group and cleaned_vessel_size_category_group.vessel_size_categories.count() > 1:
                # There are more than 1 categories in the season
                raise forms.ValidationError('The vessel size category group for the {} cannot have more than 1 vessel size category.  Selected vessel size category group: {} has {} vessel size categories.'.format(
                    cleaned_application_type.description,
                    cleaned_vessel_size_category_group.name,
                    cleaned_vessel_size_category_group.vessel_size_categories.count(),
                ))

        # Check if the applied season overwraps the existing season
        existing_fee_constructors = FeeConstructor.objects.filter(application_type=cleaned_application_type, enabled=True)
        if self.instance and self.instance.id:
            # Exclude the instance itself (allow edit)
            existing_fee_constructors = existing_fee_constructors.exclude(id=self.instance.id)
        for existing_fc in existing_fee_constructors:
            if existing_fc.fee_season.start_date <= cleaned_fee_season.start_date <= existing_fc.fee_season.end_date or existing_fc.fee_season.start_date <= cleaned_fee_season.end_date <= existing_fc.fee_season.end_date:
                # Season overwrapps
                raise forms.ValidationError('The season applied overwraps the existing season: {} ({} to {})'.format(
                    existing_fc.fee_season,
                    existing_fc.fee_season.start_date,
                    existing_fc.fee_season.end_date))

        # Check if the season start and end date of the annual admission fee_constructor match those of the authorised user fee_constructor and mooring licence fee_constructor.
        application_types_aa_au_ml = ApplicationType.objects.filter(code__in=(AnnualAdmissionApplication.code, AuthorisedUserApplication.code, MooringLicenceApplication.code))
        if cleaned_application_type in application_types_aa_au_ml:
            existing_fcs = FeeConstructor.objects.filter(application_type__in=application_types_aa_au_ml, enabled=True)
            if self.instance and self.instance.id:
                # Exclude the instance itself (allow edit)
                existing_fcs = existing_fcs.exclude(id=self.instance.id)
            for existing_fc in existing_fcs:
                if existing_fc.fee_season.start_date < cleaned_fee_season.start_date < existing_fc.fee_season.end_date or existing_fc.fee_season.start_date < cleaned_fee_season.end_date < existing_fc.fee_season.end_date:
                    # Season of the annual admission permit doesn't match the season of the authorised user permit
                    raise forms.ValidationError('The date range of the season applied: {} ({} to {}) does not match that of the existing AAP/AUP/ML: {} ({} to {})'.format(
                            cleaned_fee_season,
                            cleaned_fee_season.start_date,
                            cleaned_fee_season.end_date,
                            existing_fc.fee_season,
                            existing_fc.fee_season.start_date,
                            existing_fc.fee_season.end_date))

        return cleaned_data


@admin.register(FeeSeason)
class FeeSeasonAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date',]
    inlines = [FeePeriodInline,]
    form = FeeSeasonForm


@admin.register(FeeConstructor)
class FeeConstructorAdmin(admin.ModelAdmin):
    form = FeeConstructorForm
    inlines = [FeeItemInline,]
    list_display = ('id', 'application_type', 'fee_season', 'start_date', 'end_date', 'vessel_size_category_group', 'incur_gst', 'enabled', 'num_of_times_used_for_payment',)
    list_display_links = ['id', 'application_type', ]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Sort 'fee_season' dropdown by the start_date
        if db_field.name == "fee_season":
            kwargs["queryset"] = FeeSeason.objects.annotate(s_date=Min("fee_periods__start_date")).order_by('s_date')
        return super(FeeConstructorAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
