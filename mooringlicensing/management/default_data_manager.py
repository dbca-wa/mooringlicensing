import datetime
import logging
import pytz
import os

from django.contrib.auth.models import Group
from django.core.files import File

from mooringlicensing import settings
from mooringlicensing.components.approvals.models import AgeGroup, AdmissionType
from mooringlicensing.components.main.models import (
        ApplicationType, 
        GlobalSettings, 
        NumberOfDaysType,
        NumberOfDaysSetting
        )
from mooringlicensing.components.payments_ml.models import OracleCodeItem, FeeItemStickerReplacement
from mooringlicensing.components.proposals.models import (
        ProposalType, 
        Proposal, 
        StickerPrintingContact
        )

logger = logging.getLogger(__name__)


class DefaultDataManager(object):

    def __init__(self):
        # Proposal Types
        for item in settings.PROPOSAL_TYPES_FOR_FEE_ITEM:
            try:
                myType, created = ProposalType.objects.get_or_create(code=item[0])
                if created:
                    myType.description = item[1]
                    myType.save()
                    logger.info("Created ProposalType: {}".format(item[1]))
            except Exception as e:
                logger.error('{}, ProposalType: {}'.format(e, item[1]))

        # Application Types
        for item in Proposal.__subclasses__():
            # Create record(s) based on the existence of the subclasses
            if hasattr(item, 'code'):
                try:
                    myType, created = ApplicationType.objects.get_or_create(code=item.code)
                    if created:
                        myType.description = item.description
                        myType.save()
                        logger.info("Created ApplicationType: {}".format(item.description))
                except Exception as e:
                    logger.error('{}, ApplicationType: {}'.format(e, item.code))
        try:
            for app_type in settings.APPLICATION_TYPES:
                myType, created = ApplicationType.objects.get_or_create(code=app_type['code'])
                if created:
                    myType.description = app_type['description']
                    logger.info("Created ApplicationType: {}".format(myType.description))
                myType.fee_by_fee_constructor = app_type['fee_by_fee_constructor']  # In order to configure the data, which have already exist in the DB
                myType.save()
        except Exception as e:
            logger.error('{}, ApplicationType: {}'.format(e, item.code))

        # Store
        for item in GlobalSettings.keys:
            try:
                obj, created = GlobalSettings.objects.get_or_create(key=item[0])
                if created:
                    if item[0] in GlobalSettings.keys_for_file:
                        with open(GlobalSettings.default_values[item[0]], 'rb') as doc_file:
                            obj._file.save(os.path.basename(GlobalSettings.default_values[item[0]]), File(doc_file), save=True)
                        obj.save()
                    else:
                        obj.value = item[1]
                        obj.save()
                    logger.info("Created {}: {}".format(item[0], item[1]))
            except Exception as e:
                logger.error('{}, Key: {}'.format(e, item[0]))

        # Printing company email
        try:
            tos = StickerPrintingContact.objects.filter(type=StickerPrintingContact.TYPE_EMIAL_TO, enabled=True)
            if not tos:
                contact, created = StickerPrintingContact.objects.create(type=StickerPrintingContact.TYPE_EMIAL_TO, email='printing_company@mail.com')
                if created:
                    logger.info("Created {}".format(contact))
        except Exception as e:
            logger.error('{}'.format(e))

        # AgeGroup for the DcvAdmission fees
        for item in AgeGroup.NAME_CHOICES:
            try:
                myType, created = AgeGroup.objects.get_or_create(code=item[0])
                if created:
                    logger.info("Created AgeGroup: {}".format(item[1]))
            except Exception as e:
                logger.error('{}, AgeGroup: {}'.format(e, item[1]))

        # AdmissionType for the DcvAdmission fees
        for item in AdmissionType.TYPE_CHOICES:
            try:
                myType, created = AdmissionType.objects.get_or_create(code=item[0])
                if created:
                    logger.info("Created AdmissionType: {}".format(item[1]))
            except Exception as e:
                logger.error('{}, AdmissionType: {}'.format(e, item[1]))

        # Groups
        for group_name in settings.CUSTOM_GROUPS:
            try:
                group, created = Group.objects.get_or_create(name=group_name)
                if created:
                    logger.info("Created group: {}".format(group_name))
            except Exception as e:
                logger.error('{}, Group name: {}'.format(e, group_name))

        # Types of configurable number of days
        for item in settings.TYPES_OF_CONFIGURABLE_NUMBER_OF_DAYS:
            try:
                types_to_be_deleted = NumberOfDaysType.objects.filter(code__isnull=True)
                types_to_be_deleted.delete()  # Delete left overs
            except Exception as e:
                logger.error('{}'.format(e))

            try:
                myType, created = NumberOfDaysType.objects.get_or_create(code=item['code'])
                if created:
                    # Save description
                    myType.description = item['description']
                    myType.name = item['name']
                    myType.save()
                    logger.info("Created number of days type: {}".format(myType.name))

                setting = NumberOfDaysSetting.objects.filter(number_of_days_type=myType)
                if not setting:
                    # No setting for this type. Create one
                    enforcement_date = datetime.date(year=2021, month=1, day=1)
                    NumberOfDaysSetting.objects.create(
                        number_of_days=item['default'],
                        date_of_enforcement=enforcement_date,
                        number_of_days_type=myType
                    )

            except Exception as e:
                # logger.error('{}, Number of days type: {}'.format(e, myType.name))
                logger.error('{}'.format(e))

        # Oracle account codes
        today = datetime.datetime.now(pytz.timezone(settings.TIME_ZONE)).date()
        for application_type in ApplicationType.objects.all():
            if not application_type.oracle_code_items.count() > 0:
                try:
                    oracle_code_item = OracleCodeItem.objects.create(
                        application_type=application_type,
                        date_of_enforcement=today,
                    )
                    logger.info("Created oracle code item: {}".format(oracle_code_item))
                except Exception as e:
                    logger.error('{}, failed to create oracle code item'.format(application_type))

        # StickerReplacementFee
        fee_item = FeeItemStickerReplacement.get_fee_item_by_date()
        target_date = datetime.datetime.now(pytz.timezone(settings.TIME_ZONE)).date()
        if not fee_item:
            try:
                fee_item = FeeItemStickerReplacement.objects.create(
                    amount=24.00,
                    date_of_enforcement=target_date,
                    incur_gst=False,
                )
                logger.info("Created fee item sticker replacement: {}".format(fee_item))
            except Exception as e:
                logger.error('{}, failed to create fee item sticker replacement'.format(fee_item))

