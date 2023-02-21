from rest_framework import serializers
from django.db.models import Sum, Max
from mooringlicensing.components.main.models import (
        CommunicationsLogEntry,
        GlobalSettings, TemporaryDocumentCollection,
        )
# from ledger.payments.invoice.models import Invoice
# from ledger.accounts.models import EmailUser
from ledger_api_client.ledger_models import EmailUserRO as EmailUser, Invoice
from datetime import datetime, date


class CommunicationLogEntrySerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=EmailUser.objects.all(),required=False)
    documents = serializers.SerializerMethodField()
    class Meta:
        model = CommunicationsLogEntry
        fields = (
            'id',
            'customer',
            'to',
            'fromm',
            'cc',
            'type',
            'reference',
            'subject'
            'text',
            'created',
            'staff',
            'proposal'
            'documents'
        )

    def get_documents(self,obj):
        return [[d.name,d._file.url] for d in obj.documents.all()]


class GlobalSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalSettings
        fields = ('key', 'value')


class BookingSettlementReportSerializer(serializers.Serializer):
    date = serializers.DateTimeField(input_formats=['%d/%m/%Y'])


class OracleSerializer(serializers.Serializer):
    date = serializers.DateField(input_formats=['%d/%m/%Y','%Y-%m-%d'])
    override = serializers.BooleanField(default=False)


class InvoiceSerializer(serializers.ModelSerializer):
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            'id',
            'amount',
            'reference',
            'payment_status',
            'settlement_date',
        )

    def get_payment_status(self, invoice):
        if invoice.payment_status.lower() == 'unpaid':
            return 'Unpaid'
        elif invoice.payment_status.lower() == 'partially_paid':
            return 'Partially Paid'
        elif invoice.payment_status.lower() == 'paid':
            return 'Paid'
        else:
            return 'Over Paid'

class TemporaryDocumentCollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemporaryDocumentCollection
        fields = ('id',)

