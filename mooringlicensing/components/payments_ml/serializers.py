import datetime

from rest_framework import serializers

from mooringlicensing.components.approvals.models import DcvPermit, DcvOrganisation, DcvVessel, DcvAdmission, \
    DcvAdmissionArrival, NumberOfPeople, AgeGroup, AdmissionType
from mooringlicensing.components.payments_ml.models import FeeSeason, FeeConstructor, FeeItem, FeePeriod


class DcvAdmissionSerializer(serializers.ModelSerializer):

    class Meta:
        model = DcvAdmission
        fields = (
            'id',
            'lodgement_number',
            'submitter',
            'skipper',
            'contact_number',
        )
        read_only_fields = (
            'id',
            'lodgement_number',
        )

    def validate(self, data):
        field_errors = {}
        non_field_errors = []

        if not self.partial:
            if not data['skipper']:
                field_errors['skipper'] = ['Please enter the skipper name.',]
            if not data['contact_number']:
                field_errors['contact_number'] = ['Please enter the contact number.',]

            # dcv_permit_qs = DcvAdmission.objects.filter(dcv_vessel_id=data.get('dcv_vessel_id', 0), fee_season_id=data.get('fee_season_id', 0))
            # if dcv_permit_qs:
            #     dcv_organisation = DcvOrganisation.objects.get(id=data.get('dcv_organisation_id'))
            #     dcv_vessel = DcvVessel.objects.get(id=data.get('dcv_vessel_id'))
            #     fee_season = FeeSeason.objects.get(id=data.get('fee_season_id'))
            #     non_field_errors.append('{} already is the holder of DCV Permit: {} for the vessel: {} for the year: {}'.format(
            #         dcv_organisation,
            #         dcv_permit_qs.first().lodgement_number,
            #         dcv_vessel,
            #         fee_season.name,
            #     ))

            # Raise errors
            if field_errors:
                raise serializers.ValidationError(field_errors)
            if non_field_errors:
                raise serializers.ValidationError(non_field_errors)
        else:
            # Partial udpate, which means the dict data doesn't have all the field
            pass

        return data


class DcvAdmissionArrivalSerializer(serializers.ModelSerializer):
    arrival_date = serializers.DateField(input_formats=(['%d/%m/%Y']))  # allow_null=True, required=False

    def validate(self, data):
        field_errors = {}
        non_field_errors = []

        if not self.partial:
            if not data.get('arrival_date', None):
                field_errors['year'] = ['Please enter an arrival date.',]

            # Raise errors
            if field_errors:
                raise serializers.ValidationError(field_errors)
            if non_field_errors:
                raise serializers.ValidationError(non_field_errors)

        else:
            pass

        return data

    class Meta:
        model = DcvAdmissionArrival
        fields = (
            'id',
            'arrival_date',
            'dcv_admission',
            'private_visit',
        )
        read_only_fields = (
            'id',
        )


class NumberOfPeopleSerializer(serializers.ModelSerializer):

    def validate(self, data):
        return data

    class Meta:
        model = NumberOfPeople
        fields = (
            'id',
            'number',
            'dcv_admission_arrival',
            'age_group',
            'admission_type',
        )
        read_only_fields = (
            'id',
        )


class DcvPermitSerializer(serializers.ModelSerializer):
    dcv_vessel_id = serializers.IntegerField(required=True)
    dcv_organisation_id = serializers.IntegerField(required=True)
    fee_season_id = serializers.IntegerField(required=True)

    def validate(self, data):
        field_errors = {}
        non_field_errors = []

        if not self.partial:
            if not data['fee_season_id']:
                field_errors['year'] = ['Please select a year.',]
            # if not data['period_to']:
            #     field_errors['Period to'] = ['Please select a date.',]
            # # if not data['apiary_site_id'] and not data['apiary_site_id'] > 0:
            # #     field_errors['Site'] = ['Please select a site',]
            # if not data['comments']:
            #     field_errors['comments'] = ['Please enter comments.',]

            dcv_permit_qs = DcvPermit.objects.filter(
                dcv_vessel_id=data.get('dcv_vessel_id', 0),
                fee_season_id=data.get('fee_season_id', 0),
                dcv_organisation_id=data.get('dcv_organisation_id', 0)  # TODO <== check if works
            )
            if dcv_permit_qs:
                dcv_organisation = DcvOrganisation.objects.get(id=data.get('dcv_organisation_id'))
                dcv_vessel = DcvVessel.objects.get(id=data.get('dcv_vessel_id'))
                fee_season = FeeSeason.objects.get(id=data.get('fee_season_id'))
                non_field_errors.append('{} already is the holder of DCV Permit: {} for the vessel: {} for the year: {}'.format(
                    dcv_organisation,
                    dcv_permit_qs.first().lodgement_number,
                    dcv_vessel,
                    fee_season.name,
                ))

            # Raise errors
            if field_errors:
                raise serializers.ValidationError(field_errors)
            if non_field_errors:
                raise serializers.ValidationError(non_field_errors)
        else:
            # Partial udpate, which means the dict data doesn't have all the field
            pass

        return data

    class Meta:
        model = DcvPermit
        fields = (
            'id',
            'lodgement_number',
            'submitter',
            'lodgement_datetime',
            'dcv_vessel_id',
            'dcv_organisation_id',
            'fee_season_id',
            'start_date',
            'end_date',
        )
        read_only_fields = (
            'id',
            'lodgement_number',
            'start_date',
            'end_date',
        )


class FeeSeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeSeason
        fields = (
            'id',
            'name'
        )


# class AgeGroupSerializer(serializers.ModelSerializer):
#
#     class Meta:
#         model = AgeGroup
#         fields = (
#             'id',
#             'code',
#         )
#
#
# class AdmissionTypeSerializer(serializers.ModelSerializer):
#
#     class Meta:
#         model = AdmissionType
#         fields = (
#             'id',
#             'code',
#         )


class FeePeriodSerializer(serializers.ModelSerializer):

    class Meta:
        model = FeePeriod
        fields = (
            'id',
            'start_date',
            'name',
        )


# class FeeItemSerializer(serializers.ModelSerializer):
#     age_group = serializers.CharField(source='age_group.code')
#     admission_type = serializers.CharField(source='admission_type.code')
#
#     class Meta:
#         model = FeeItem
#         fields = (
#             'id',
#             'amount',
#             'age_group',
#             'admission_type'
#         )


class FeeConstructorSerializer(serializers.ModelSerializer):
    start_date = serializers.ReadOnlyField()
    end_date = serializers.ReadOnlyField()
    fee_season = FeeSeasonSerializer()
    fee_items = serializers.SerializerMethodField()

    class Meta:
        model = FeeConstructor
        fields = (
            'id',
            'start_date',
            'end_date',
            'fee_season',
            'incur_gst',
            'fee_items',
        )

    def get_fee_items(self, fee_constructor):
        fee_configurations = {}

        for age_group in AgeGroup.NAME_CHOICES:
            fee_configurations[age_group[0]] = {}
        for fee_item in fee_constructor.feeitem_set.all():
            if fee_item.admission_type:
                fee_configurations[fee_item.age_group.code].update({fee_item.admission_type.code: fee_item.amount})

        return fee_configurations
