from django.core.management.base import BaseCommand

from mooringlicensing.components.proposals.models import (
    Proposal
)

from mooringlicensing.components.approvals.models import (
    Approval, Sticker
)

from mooringlicensing.management.commands.utils import (
    check_invalid_expired_approval,
    check_proposal_stuck_at_printing,
    get_unaccounted_sold_vessel_ownerships,
    get_late_expired_approvals,
    get_late_surrendered_approvals,
    get_late_suspended_approvals,
    get_late_cancelled_approvals,
    get_late_resuming_approvals,
    get_approvals_due_for_renewal_without_notice,
    get_incorrect_sticker_seasons,
    get_stickers_not_on_MOAs,
    get_invalid_stickers_still_current,
    get_proposals_with_fee_records_missing_vessel_details,
    get_stickers_missing_vessel,
)

from mooringlicensing import settings
from mooringlicensing.components.emails.emails import TemplateEmailBase

from ledger_api_client.managed_models import SystemGroup
from ledger_api_client.ledger_models import EmailUserRO

import logging
logger = logging.getLogger('cron_tasks')
cron_email = logging.getLogger('cron_email')

import datetime

class Command(BaseCommand):
    """
    This management command will attempt to find conflicting or otherwise incorrect record data and regularly report on them.

    Initially this report will include attempts to find issues that have previously occurred throughout the system and whatever else can be established as useful.

    This functionality may be extended over time as additional issues become apparent that have not yet been covered.

    Usage of this script should be only running without date filters sparingly (no more than weekly, for example), running with a from date filter regularly, and running with a to date filter on a case by case basis.
    
    Not all records can be filtered using date values and using date values may exclude some records related to one another that may be involved in a date conflict.
    """
    help = 'Report for issues in records such as incorrect record status and duplicate records. A from date and to date can be provided to narrow down a search but may exclude some potential findings.'

    def add_arguments(self, parser):
        parser.add_argument('--from_date', default=None)
        parser.add_argument('--to_date', default=None)
 
    def parse_date_arg(self, key, options):

        if key in options and options[key]:
            try:
                logger.info(f'{options[key]} provided as {key}')
                return datetime.datetime.strptime(options[key], '%Y-%m-%d')
            except Exception as e:
                logger.error("Invalid date format, please provide valid date in format YYYY-MM-DD")
                raise e

        return None

    def handle(self, *args, **options):
        logger.info("Running Records Issues Report.")

        #parse date range if provided
        from_date = self.parse_date_arg('from_date',options)
        to_date = self.parse_date_arg('to_date',options)

        #list of models to examine
        examine_models = [
            Proposal,
            Approval,
            Sticker,
        ]

        #date field to filter by (if any, one per model)
        examine_model_date_fields = {
            Proposal:'created_at',
            Approval:'created_at',
            Sticker: 'date_created',
        }

        #Get examination querysets
        examination_querysets = {}
        for model in examine_models:
            if from_date and model in examine_model_date_fields:
                date_field = examine_model_date_fields[model]
                if to_date:
                    qs = model.objects.filter(**{f'{date_field}__lte':to_date},**{f'{date_field}__gte':from_date})
                else:
                    qs = model.objects.filter(**{f'{date_field}__gte':from_date})
            else:
                qs = model.objects.all()
            examination_querysets[model] = qs

        #list of examination functions (and the model querysets they require)
        #NOTE: this is where any new report functions go
        #format: function_name: examination_querysets[ModelName] (make sure the model is in the examine_models list)
        examination_functions = {
            check_invalid_expired_approval: [examination_querysets[Approval]],
            check_proposal_stuck_at_printing: [examination_querysets[Proposal]],
            #check_duplicate_vessel_ownerships_among_proposals: [examination_querysets[Proposal]],
            get_unaccounted_sold_vessel_ownerships: [examination_querysets[Proposal]],
            get_late_expired_approvals: [examination_querysets[Approval]],
            get_late_surrendered_approvals: [examination_querysets[Approval]],
            get_late_suspended_approvals: [examination_querysets[Approval]],
            get_late_cancelled_approvals: [examination_querysets[Approval]],
            get_late_resuming_approvals: [examination_querysets[Approval]],
            get_approvals_due_for_renewal_without_notice: [examination_querysets[Approval]],
            get_incorrect_sticker_seasons: [examination_querysets[Sticker]],
            get_stickers_not_on_MOAs: [examination_querysets[Sticker]],
            get_invalid_stickers_still_current: [examination_querysets[Sticker]],
            get_proposals_with_fee_records_missing_vessel_details: [examination_querysets[Proposal]],
            get_stickers_missing_vessel: [examination_querysets[Sticker]],
        }

        reports = []

        #run examination functions
        for examination_function, examination_querysets in examination_functions.items():
            if examination_querysets:
                reports.append(examination_function(*examination_functions[examination_function]))
            else:
                reports.append(examination_function())

        for report in reports:
            if report and len(report)>1 and report[1]:
                print(f"\n{report[0]}")
                for number in report[1]:
                    print(number)

        if reports:
            #email to group
            recipient_group = settings.GROUP_SYSTEM_ADMIN
            ledger_ids = SystemGroup.objects.get(name=recipient_group).get_system_group_member_ids_active_users()

            emails = list(EmailUserRO.objects.filter(id__in=ledger_ids).values_list('email', flat=True))

            email = TemplateEmailBase(
                subject=f'Issues with data records found {settings.LEDGER_SYSTEM_ID}', 
                html_template='mooringlicensing/emails_2/record_issue_report.html',
                txt_template='mooringlicensing/emails_2/record_issue_report.txt',
            )
            context = {"reports":reports}
            ## Send email
            email.send(emails, context=context)