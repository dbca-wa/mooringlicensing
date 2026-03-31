from django.core.management.base import BaseCommand
from ledger_api_client.ledger_models import EmailUserRO
from ledger_api_client.managed_models import SystemUser

from mooringlicensing.components.approvals.models import (
    Approval, DcvAdmission, DcvPermit, ApprovalUserAction, StickerActionDetail, ApprovalLogEntry
)
from mooringlicensing.components.compliances.models import (
    Compliance, ComplianceUserAction, ComplianceLogEntry
)
from mooringlicensing.components.payments_ml.models import (
    DcvAdmissionFee, DcvPermitFee, StickerActionFee, ApplicationFee
)
from mooringlicensing.components.proposals.models import (
    Proposal, ProposalApplicant, Owner, ProposalUserAction, ProposalLogEntry, MooringLogEntry, VesselLogEntry, VesselOwnership, ProposalSiteLicenseeMooringRequest
)
from ledger_api_client.utils import get_or_create, change_user_invoice_ownership
from django.db import transaction
from mooringlicensing.components.users.utils import get_or_create_system_user_system_user

class Command(BaseCommand):
    help = 'Change user email address and all associated mooring licensing records'

    def add_arguments(self, parser):
        parser.add_argument('--current_email', type=str)
        parser.add_argument('--new_email', type=str)

    def check_proposals_and_approvals(self,to_be_changed,existing):
        #go through each proposal/approval type and ensure no conflict between to_be_changed and existing
        #check for application limit rules (e.g. one wla per user), vessel rules (can only be one application at a time, can not be on an AAP and an MLA, etc)
        proposals_to_be_changed = sum(list(map(lambda i:i[1],list(filter(lambda i: i[0]==Proposal,to_be_changed)))),[])
        proposals_existing = sum(list(map(lambda i:i[1],list(filter(lambda i: i[0]==Proposal,existing)))),[])
        wl_appl_to_be_changed = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'application_type') and hasattr(i.child_obj.application_type, 'code') and i.child_obj.application_type.code == 'wla',proposals_to_be_changed))))
        aa_appl_to_be_changed = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'application_type') and hasattr(i.child_obj.application_type, 'code') and i.child_obj.application_type.code == 'aaa',proposals_to_be_changed))))
        au_appl_to_be_changed = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'application_type') and hasattr(i.child_obj.application_type, 'code') and i.child_obj.application_type.code == 'aua',proposals_to_be_changed))))
        ml_appl_to_be_changed = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'application_type') and hasattr(i.child_obj.application_type, 'code') and (i.child_obj.application_type.code == 'mla' or i.application_type.code == 'mooring_swap'),proposals_to_be_changed))))
        wl_appl_existing = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'application_type') and hasattr(i.child_obj.application_type, 'code') and i.child_obj.application_type.code == 'wla',proposals_existing))))
        aa_appl_existing = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'application_type') and hasattr(i.child_obj.application_type, 'code') and i.child_obj.application_type.code == 'aaa',proposals_existing))))
        au_appl_existing = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'application_type') and hasattr(i.child_obj.application_type, 'code') and i.child_obj.application_type.code == 'aua',proposals_existing))))
        ml_appl_existing = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'application_type') and hasattr(i.child_obj.application_type, 'code') and (i.child_obj.application_type.code == 'mla' or i.application_type.code == 'mooring_swap'),proposals_existing))))

        approvals_to_be_changed = sum(list(map(lambda i:i[1],list(filter(lambda i: i[0]==Approval,to_be_changed)))),[])
        approvals_existing = sum(list(map(lambda i:i[1],list(filter(lambda i: i[0]==Approval,existing)))),[])
        wl_appr_to_be_changed = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'code') and i.child_obj.code == 'wla',approvals_to_be_changed))))
        aa_appr_to_be_changed = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'code') and i.child_obj.code == 'aap',approvals_to_be_changed))))
        au_appr_to_be_changed = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'code') and i.child_obj.code == 'aup',approvals_to_be_changed))))
        ml_appr_to_be_changed = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'code') and i.child_obj.code == 'ml',approvals_to_be_changed))))
        wl_appr_existing = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'code') and i.child_obj.code == 'wla',approvals_existing))))
        aa_appr_existing = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'code') and i.child_obj.code == 'aap',approvals_existing))))
        au_appr_existing = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'code') and i.child_obj.code == 'aup',approvals_existing))))
        ml_appr_existing = list(set(list(filter(lambda i: hasattr(i,'child_obj') and hasattr(i.child_obj, 'code') and i.child_obj.code == 'ml',approvals_existing))))

        to_be_changed_numbers = []

        # WAITING LIST APPLICATION RULES
        for wl_appl in wl_appl_to_be_changed:
            to_be_changed_numbers.append(wl_appl.lodgement_number)
            vessel = wl_appl.rego_no

            # Vessel cannot be part of another Waiting List application in status other than issued, declined or discarded
            allowed_appl_status = [Proposal.PROCESSING_STATUS_APPROVED,Proposal.PROCESSING_STATUS_DECLINED,Proposal.PROCESSING_STATUS_DISCARDED]
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), wl_appl_existing))
            if len(check) > 0 and wl_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of another Waiting List application in status other than issued, declined or discarded: {} conflicts with {}".format(wl_appl.lodgement_number,check), []

            # Vessel cannot be part of a current or suspended Waiting List Allocation
            disallowed_appr_status = [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED]
            check = list(filter(lambda i: (i.current_proposal.rego_no == vessel and i.status in disallowed_appr_status), wl_appr_existing))
            if len(check) > 0 and wl_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of a current or suspended Waiting List Allocation: {} conflicts with {}".format(wl_appl.lodgement_number,check), []

            # Vessel cannot be part of a Mooring Licence application in status other than issued, declined or discarded
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), ml_appl_existing))
            if len(check) > 0 and wl_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of a Mooring Licence application in status other than issued, declined or discarded: {} conflicts with {}".format(wl_appl.lodgement_number,check), []

            # Vessel cannot be part of a current or suspended Mooring Licence allocation (as nominated vessel or as one of other vessels on the licence)
            check = list(filter(lambda i: (vessel in i.child_obj.current_vessel_attributes(attribute="rego_no") and i.status in disallowed_appr_status), ml_appr_existing))
            if len(check) > 0 and wl_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of a current or suspended Mooring Licence allocation (as nominated vessel or as one of other vessels on the licence): {} conflicts with {}".format(wl_appl.lodgement_number,check), []

            # A person cannot start a Waiting List Application if there is another Waiting List application for that person in status other than issued, declined, discarded
            check = list(filter(lambda i: not i.processing_status in allowed_appl_status, wl_appl_existing))
            if len(check) > 0 and wl_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person cannot start a Waiting List Application if there is another Waiting List application for that person in status other than issued, declined, discarded: {} conflicts with {}".format(wl_appl.lodgement_number,check), []
            
            # A person cannot start a Waiting List Application if there is another Waiting List Allocation for that person in status other than cancelled, expired, surrendered
            allowed_appr_status = [Approval.APPROVAL_STATUS_CANCELLED,Approval.APPROVAL_STATUS_EXPIRED,Approval.APPROVAL_STATUS_SURRENDERED]
            check = list(filter(lambda i: (not i.status in allowed_appr_status), wl_appr_existing))
            if len(check) > 0 and wl_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person cannot start a Waiting List Application if there is another Waiting List Allocation for that person in status other than cancelled, expired, surrendered: {} conflicts with {}".format(wl_appl.lodgement_number,check), []

            # A person cannot start a Waiting List Application if there is a Mooring Licence application in status other than issued, declined or discarded
            check = list(filter(lambda i: not i.processing_status in allowed_appl_status, ml_appl_existing))
            if len(check) > 0 and wl_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person cannot start a Waiting List Application if there is a Mooring Licence application in status other than issued, declined or discarded: {} conflicts with {}".format(wl_appl.lodgement_number,check), []

            # A person cannot start a Waiting List Application if there is a Mooring Licence in status Current or Suspended
            check = list(filter(lambda i: i.status in disallowed_appr_status, ml_appr_existing))
            if len(check) > 0 and wl_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person cannot start a Waiting List Application if there is a Mooring Licence in status Current or Suspended: {} conflicts with {}".format(wl_appl.lodgement_number,check), []

        # WAITING LIST ALLOCATION RULES
        # A waiting list allocation must follow an application, therefore is subject to some of the same rules
        for wl_appr in wl_appr_to_be_changed:
            to_be_changed_numbers.append(wl_appr.lodgement_number)
            # A person cannot have a Current or Suspended Waiting List Allocation if there is a Waiting List application for that person in status other than issued, declined, discarded
            allowed_appl_status = [Proposal.PROCESSING_STATUS_APPROVED,Proposal.PROCESSING_STATUS_DECLINED,Proposal.PROCESSING_STATUS_DISCARDED]
            check = list(filter(lambda i: not i.processing_status in allowed_appl_status, wl_appl_existing))
            disallowed_appr_status = [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED]
            if len(check) > 0 and wl_appr.status in disallowed_appr_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person cannot have a Current or Suspended Waiting List Allocation if there is a Waiting List application for that person in status other than issued, declined, discarded: {} conflicts with {}".format(wl_appr.lodgement_number,check), []

            # A person cannot have a Current or Suspended Waiting List Allocation if there is a Mooring Licence application in status other than issued, declined or discarded
            check = list(filter(lambda i: not i.processing_status in allowed_appl_status, ml_appl_existing))
            if len(check) > 0 and wl_appr.status in disallowed_appr_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person cannot have a Current or Suspended Waiting List Allocation if there is a Mooring Licence application in status other than issued, declined or discarded: {} conflicts with {}".format(wl_appr.lodgement_number,check), []
            
            # A person can have only one Current or Suspended Waiting List Allocation in status other than cancelled, expired, surrendered
            allowed_appr_status = [Approval.APPROVAL_STATUS_CANCELLED,Approval.APPROVAL_STATUS_EXPIRED,Approval.APPROVAL_STATUS_SURRENDERED]
            check = list(filter(lambda i: (not i.status in allowed_appr_status), wl_appr_existing))
            if len(check) > 0 and wl_appr.status in disallowed_appr_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person can have only one Current or Suspended Waiting List Allocation in status other than cancelled, expired, surrendered: {} conflicts with {}".format(wl_appr.lodgement_number,check), []

            # A person cannot have a Current or Suspended Waiting List Allocation if there is a Mooring Licence in status Current or Suspended
            check = list(filter(lambda i: (i.status in disallowed_appr_status), ml_appr_existing))
            if len(check) > 0 and wl_appr.status in disallowed_appr_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person cannot have a Current or Suspended Waiting List Allocation if there is a Mooring Licence in status Current or Suspended: {} conflicts with {}".format(wl_appr.lodgement_number,check), []

        # ANNUAL ADMISSION APPLICATION RULES
        for aa_appl in aa_appl_to_be_changed:
            to_be_changed_numbers.append(aa_appl.lodgement_number)

            vessel = aa_appl.rego_no

            # Vessel cannot be part of another Annual Admission application in status other than issued, declined or discarded
            allowed_appl_status = [Proposal.PROCESSING_STATUS_APPROVED,Proposal.PROCESSING_STATUS_DECLINED,Proposal.PROCESSING_STATUS_DISCARDED]
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), aa_appl_existing))
            if len(check) > 0 and aa_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of another Annual Admission application in status other than issued, declined or discarded: {} conflicts with {}".format(aa_appl.lodgement_number,check), []

            # Vessel cannot be part of a current or suspended Annual Admission Permit
            disallowed_appr_status = [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED]
            check = list(filter(lambda i: (i.current_proposal.rego_no == vessel and i.status in disallowed_appr_status), aa_appr_existing))
            if len(check) > 0 and aa_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of a current or suspended Annual Admission Permit: {} conflicts with {}".format(aa_appl.lodgement_number), []

            # Vessel cannot be part of an Authorised User application in status other than issued, declined or discarded
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), au_appl_existing))
            if len(check) > 0 and aa_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of an Authorised User application in status other than issued, declined or discarded: {} conflicts with {}".format(aa_appl.lodgement_number,check), []

            # Vessel cannot be part of a current or suspended Authorised User Permit
            check = list(filter(lambda i: (i.current_proposal.rego_no == vessel and i.status in disallowed_appr_status), au_appr_existing))
            if len(check) > 0 and aa_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of a current or suspended Authorised User Permit: {} conflicts with {}".format(aa_appl.lodgement_number), []

            # Vessel cannot be part of a Mooring Licence application in status other than issued, declined or discarded
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), ml_appl_existing))
            if len(check) > 0 and aa_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of a Mooring Licence application in status other than issued, declined or discarded: {} conflicts with {}".format(aa_appl.lodgement_number,check), []
            
            # Vessel cannot be part of a current or suspended Mooring Licence (as nominated vessel or as one of other vessels on the licence)
            check = list(filter(lambda i: (vessel in i.child_obj.current_vessel_attributes(attribute="rego_no") and i.status in disallowed_appr_status), ml_appr_existing))
            if len(check) > 0 and aa_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of a current or suspended Mooring Licence (as nominated vessel or as one of other vessels on the licence): {} conflicts with {}".format(aa_appl.lodgement_number,check), []

        # ANNUAL ADMISSION PERMIT RULES
        for aa_appr in aa_appr_to_be_changed:
            to_be_changed_numbers.append(aa_appr.lodgement_number)

            vessel = aa_appr.current_proposal.rego_no

            # Vessel in Current or Suspended Annual Admission Permit cannot be part of a Annual Admission application in status other than issued, declined or discarded
            allowed_appl_status = [Proposal.PROCESSING_STATUS_APPROVED,Proposal.PROCESSING_STATUS_DECLINED,Proposal.PROCESSING_STATUS_DISCARDED]
            disallowed_appr_status = [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED]
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), aa_appl_existing))
            if len(check) > 0 and aa_appr.status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of another Annual Admission application in status other than issued, declined or discarded: {} conflicts with {}".format(aa_appr.lodgement_number,check), []

            # Vessel in Current or Suspended Annual Admission Permit cannot be part of a another current or suspended Annual Admission Permit
            check = list(filter(lambda i: (i.current_proposal.rego_no == vessel and i.status in disallowed_appr_status), aa_appr_existing))
            if len(check) > 0 and aa_appr.status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel in Current or Suspended Annual Admission Permit cannot be part of a another current or suspended Annual Admission Permit: {} conflicts with {}".format(aa_appr.lodgement_number,check), []

            # Vessel in Current or Suspended Annual Admission Permit cannot be part of an Authorised User application in status other than issued, declined or discarded
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), au_appl_existing))
            if len(check) > 0 and aa_appr.status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel in Current or Suspended Annual Admission Permit cannot be part of an Authorised User application in status other than issued, declined or discarded: {} conflicts with {}".format(aa_appr.lodgement_number,check), []

            # Vessel in Current or Suspended Annual Admission Permit cannot be part of a current or suspended Authorised User Permit
            check = list(filter(lambda i: (i.current_proposal.rego_no == vessel and i.status in disallowed_appr_status), au_appr_existing))
            if len(check) > 0 and aa_appr.status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel in Current or Suspended Annual Admission Permit cannot be part of a current or suspended Authorised User Permit: {} conflicts with {}".format(aa_appr.lodgement_number,check), []

            # Vessel in Current or Suspended Annual Admission Permit cannot be part of a Mooring Licence application in status other than issued, declined or discarded
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), ml_appl_existing))
            if len(check) > 0 and aa_appr.status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel in Current or Suspended Annual Admission Permit cannot be part of a Mooring Licence application in status other than issued, declined or discarded: {} conflicts with {}".format(aa_appr.lodgement_number,check), []

            # Vessel in Current or Suspended Annual Admission Permit cannot be part of a current or suspended Mooring Licence (as nominated vessel or as one of other vessels on the licence)
            check = list(filter(lambda i: (vessel in i.child_obj.current_vessel_attributes(attribute="rego_no") and i.status in disallowed_appr_status), ml_appr_existing))
            if len(check) > 0 and aa_appr.status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel in Current or Suspended Annual Admission Permit cannot be part of a current or suspended Mooring Licence (as nominated vessel or as one of other vessels on the licence): {} conflicts with {}".format(aa_appr.lodgement_number,check), []

        # AUTHORISED USER APPLICATION RULES
        for au_appl in au_appl_to_be_changed:
            to_be_changed_numbers.append(au_appl.lodgement_number)

            vessel = au_appl.rego_no

            # Vessel cannot be part of another Authorised User application in status other than issued, declined or discarded
            allowed_appl_status = [Proposal.PROCESSING_STATUS_APPROVED,Proposal.PROCESSING_STATUS_DECLINED,Proposal.PROCESSING_STATUS_DISCARDED]
            disallowed_appr_status = [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED]
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), au_appl_existing))
            if len(check) > 0 and au_appl.status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of another Authorised User application in status other than issued, declined or discarded: {} conflicts with {}".format(au_appl.lodgement_number,check), []
            
            # Vessel cannot be part of a current or suspended Authorised User Permit
            check = list(filter(lambda i: (i.current_proposal.rego_no == vessel and i.status in disallowed_appr_status), au_appr_existing))
            if len(check) > 0 and au_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of a current or suspended Authorised User Permit: {} conflicts with {}".format(au_appl.lodgement_number,check), []


        # AUTHORISED USER PERMIT RULES
        for au_appr in au_appr_to_be_changed:
            to_be_changed_numbers.append(au_appr.lodgement_number)

            vessel = au_appr.current_proposal.rego_no

            # Vessel in Current or Suspended Authorised User Permit cannot be part of an Authorised User application in status other than issued, declined or discarded
            allowed_appl_status = [Proposal.PROCESSING_STATUS_APPROVED,Proposal.PROCESSING_STATUS_DECLINED,Proposal.PROCESSING_STATUS_DISCARDED]
            disallowed_appr_status = [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED]
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), au_appl_existing))
            if len(check) > 0 and au_appr.status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel in Current or Suspended Authorised User Permit cannot be part of an Authorised User application in status other than issued, declined or discarded: {} conflicts with {}".format(au_appr.lodgement_number,check), []

            # Vessel in Current or Suspended Authorised User Permit cannot be part of a another current or suspended Authorised User Permit
            check = list(filter(lambda i: (i.current_proposal.rego_no == vessel and i.status in disallowed_appr_status), au_appr_existing))
            if len(check) > 0 and au_appr.status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel in Current or Suspended Authorised User Permit cannot be part of a another current or suspended Authorised User Permit: {} conflicts with {}".format(au_appr.lodgement_number,check), []


        # MOORING LICENSE APPLICATION RULES
        for ml_appl in ml_appl_to_be_changed:
            to_be_changed_numbers.append(ml_appl.lodgement_number)

            vessel = ml_appl.rego_no

            # Vessel cannot be part of another Mooring Licence application in status other than issued, declined or discarded that is not already with the new email account
            allowed_appl_status = [Proposal.PROCESSING_STATUS_APPROVED,Proposal.PROCESSING_STATUS_DECLINED,Proposal.PROCESSING_STATUS_DISCARDED]
            disallowed_appr_status = [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED]
            check = list(filter(lambda i: (i.rego_no == vessel and not i.processing_status in allowed_appl_status), ml_appl_existing))
            if len(check) > 0 and ml_appl.status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of another Mooring Licence application in status other than issued, declined or discarded that is not already with the new email account: {} conflicts with {}".format(ml_appl.lodgement_number,check), []

            # Vessel cannot be part of a current or suspended Mooring Licence
            check = list(filter(lambda i: (vessel in i.child_obj.current_vessel_attributes(attribute="rego_no") and i.status in disallowed_appr_status), ml_appr_existing))
            if len(check) > 0 and ml_appl.processing_status not in allowed_appl_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of a current or suspended Mooring Licence: {} conflicts with {}".format(ml_appl.lodgement_number,check), []

        # MOORING LICENSE RULES
        # As a mooring license would require the issuance of waiting list allocation, it is effectively subject to the same rules
        for ml_appr in ml_appr_to_be_changed:
            to_be_changed_numbers.append(ml_appr.lodgement_number)

            # A person can have only one Current or Suspended Mooring License in status other than cancelled, expired, surrendered
            disallowed_appr_status = [Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED]
            allowed_appr_status = [Approval.APPROVAL_STATUS_CANCELLED,Approval.APPROVAL_STATUS_EXPIRED,Approval.APPROVAL_STATUS_SURRENDERED]
            check = list(filter(lambda i: not i.status in allowed_appr_status, ml_appr_existing))
            if len(check) > 0 and ml_appr.status in disallowed_appr_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "Vessel cannot be part of a current or suspended Mooring Licence: {} conflicts with {}".format(ml_appr.lodgement_number,check), []
            
            # A person cannot have a Current or Suspended Mooring Licence if there is Waiting List application for that person in status other than issued, declined, discarded that is not already with the new email account
            allowed_appl_status = [Proposal.PROCESSING_STATUS_APPROVED,Proposal.PROCESSING_STATUS_DECLINED,Proposal.PROCESSING_STATUS_DISCARDED]
            check = list(filter(lambda i: not i.processing_status in allowed_appl_status, wl_appl_existing))
            if len(check) > 0 and ml_appr.status in disallowed_appr_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person cannot have a Current or Suspended Mooring Licence if there is Waiting List application for that person in status other than issued, declined, discarded that is not already with the new email account: {} conflicts with {}".format(ml_appr.lodgement_number,check), []
            
            # A person cannot have a Current or Suspended Mooring Licence if there is Mooring License application for that person in status other than issued, declined, discarded that is not already with the new email account
            check = list(filter(lambda i: not i.processing_status in allowed_appl_status, ml_appl_existing))
            if len(check) > 0 and ml_appr.status in disallowed_appr_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person cannot have a Current or Suspended Mooring Licence if there is Mooring License application for that person in status other than issued, declined, discarded that is not already with the new email account: {} conflicts with {}".format(ml_appr.lodgement_number,check), []

            # A person cannot have a Current or Suspended Mooring Licence if there is a Waiting List Allocation in status Current or Suspended
            check = list(filter(lambda i: i.status in disallowed_appr_status, wl_appr_existing))
            if len(check) > 0 and ml_appr.status in disallowed_appr_status:
                check = list(map(lambda i:i.lodgement_number,check))
                return False, "A person cannot have a Current or Suspended Mooring Licence if there is a Waiting List Allocation in status Current or Suspended: {} conflicts with {}".format(ml_appr.lodgement_number,check), []

        return True, "Records validated and acceptable for merging", to_be_changed_numbers

    def check_ownerships(self,to_be_changed,existing):
        owners_to_be_changed = list(filter(lambda i: i[0]==Owner,to_be_changed))
        owners_existing = list(filter(lambda i: i[0]==Owner,existing))

        if owners_to_be_changed and owners_existing:
            to_be_changed_rego_nos = []
            for owner_to_be_changed in owners_to_be_changed:
                for i in owner_to_be_changed[1]:
                    to_be_changed_rego_nos += list(i.vessels.filter(vesselownership__end_date=None).values_list('rego_no',flat=True))

            existing_rego_nos = []
            for owner_existing in owners_existing:
                for i in owner_existing[1]:
                    existing_rego_nos += list(i.vessels.filter(vesselownership__end_date=None).values_list('rego_no',flat=True))

            intersecting_rego_nos = list(set(existing_rego_nos).intersection(set(to_be_changed_rego_nos)))
            if intersecting_rego_nos:
                return False, "Both accounts own vessels with rego_nos {intersecting_rego_nos}. Please discontinue vessel ownerships under one user to allow for records to merge."
            else:
                return True, "No conflicting Owner records"
        else:
            return True, "No conflicting Owner records"

    def handle(self, *args, **options):

        if not(options["current_email"] and options["new_email"]):
            print("please specify both the current email and the new email with the --current_email and --new_email options respectively")
            return

        #get original email
        current_email = options["current_email"]

        #get new email
        new_email = options["new_email"]

        #check if original email exists both on ledger and locally
        current_email_ledger = EmailUserRO.objects.filter(email__iexact=current_email).last()
        current_email_system = SystemUser.objects.filter(email__iexact=current_email).last()

        if not current_email_system:
            print("System User record does not exist for specified current email")
            return
        if not current_email_ledger:
            print("Ledger User record does not exist for specified current email")
            return

        new_email_ledger = EmailUserRO.objects.filter(email__iexact=new_email).last()
        #check if new email already exists on ledger (create new if it does not)
        if not new_email_ledger:
            new_email_resp = get_or_create(new_email)["data"]["email"]
            new_email_ledger = EmailUserRO.objects.filter(email__iexact=new_email_resp).last()

        system_user_exists = False
        #if it already exists, check if system user record exists on ML - stop if it does
        if SystemUser.objects.filter(email__iexact=new_email):
            print("Provided email already has an associated System User")
            system_user_exists = True

        #get all pertaining records (anything that refers to ledger id or email, except for log emails)
        #Approval (submitter)
        #DcvAdmission (submitter, applicant)
        #DcvPermit (submitter, applicant)
        #ApprovalUserAction (who) 
        #StickerActionDetail (user)
        #ApprovalLogEntry (customer)
        
        #Compliance (submitter)
        #ComplianceUserAction (who)
        #ComplianceLogEntry (customer)

        #DcvAdmissionFee (created_by)
        #DcvPermitFee (created_by)
        #StickerActionFee (created_by)
        #ApplicationFee (created_by)

        #Proposal (submitter)
        #ProposalApplicant (email_user_id, email)
        #Owner (emailuser)
        #ProposalUserAction (who)
        #ProposalLogEntry (customer)
        #MooringLogEntry (customer)
        #VesselLogEntry (customer)

        potential_blockers = {Approval: ["current_proposal__proposal_applicant__email_user_id"],Proposal: ["proposal_applicant__email_user_id"],Owner: ["emailuser"]}

        special_handling = {Owner:False} #if a model require special handling under certain conditions, set Key bool to True

        if Owner.objects.filter(emailuser=current_email_ledger.id).exists():
            special_handling[Owner] = True

        change_ledger_id = {
            Approval: ["submitter"],
            DcvAdmission: ["submitter", "applicant"],
            DcvPermit: ["submitter", "applicant"],
            ApprovalUserAction: ["who"],
            StickerActionDetail: ["user"],
            ApprovalLogEntry: ["customer"],
            Compliance: ["submitter"],
            ComplianceUserAction: ["who"],
            ComplianceLogEntry: ["customer"],
            DcvAdmissionFee: ["created_by"],
            DcvPermitFee: ["created_by"],
            StickerActionFee: ["created_by"],
            ApplicationFee: ["created_by"],
            Proposal: ["submitter"],
            ProposalApplicant: ["email_user_id"],
            Owner: ["emailuser"],
            ProposalUserAction: ["who"],
            ProposalLogEntry: ["customer"],
            MooringLogEntry: ["customer"],
            VesselLogEntry: ["customer"],
        }
        change_email = {
            ProposalApplicant: ["email"],
            ProposalSiteLicenseeMooringRequest: ["site_licensee_email"],
        }
        log_change_models = {
            Approval: (ApprovalUserAction, "approval"), #(logging_model, logging_model_relation)
            Compliance: (ComplianceUserAction, "compliance"),
            Proposal: (ProposalUserAction, "proposal"),
            ProposalApplicant: (ProposalUserAction, "proposal", "proposal"), #(logging_model, logging_model_relation, changed_model_relation)
        }

        with transaction.atomic():
            #change all records to the new email and ledger id 
            #log all record changes to record's respective action logs where applicable (Applicant/Submitter/Holder Email Address change)
            if not system_user_exists:
                SystemUser.objects.create(
                    email = new_email,
                    ledger_id_id = new_email_ledger.id,
                    legal_first_name = current_email_system.legal_first_name,
                    legal_last_name = current_email_system.legal_last_name,
                    first_name = current_email_system.first_name,
                    last_name = current_email_system.last_name,
                    is_staff = current_email_system.is_staff,
                    is_active = current_email_system.is_active,
                    title = current_email_system.title,
                    legal_dob = current_email_system.legal_dob,
                    phone_number = current_email_system.phone_number,
                    mobile_number = current_email_system.mobile_number,
                    fax_number = current_email_system.fax_number,
                )
            else:
                existing_system_user = SystemUser.objects.filter(email__iexact=new_email).first()
                #if somehow a system user already exists but their ledger id does not match that of the provided email, update it (with a warning)
                if existing_system_user.ledger_id_id != new_email_ledger.id: 
                    if existing_system_user.ledger_id_id != None:
                        
                        answer = input(f"""
    ####################################################################################################################################################################################################################            
    WARNING: Existing system user account has a different ledger id ({existing_system_user.ledger_id_id}) to that of the provided new email address {new_email} ledger id {new_email_ledger.id}

    Proceeding will change the the ledger id of the system user record for {new_email} from {existing_system_user.ledger_id_id} to {new_email_ledger.id}. 

    Do not proceed if there are other records referencing ledger id {existing_system_user.ledger_id_id} that need to remain associated with the new email - they should be adjusted prior to conducting an email change.
    #################################################################################################################################################################################################################### 
    Are you sure you want to continue? (y/n): """)
                        if answer.lower() != 'y':
                            return
                    else:
                        print(f"System user with email {new_email} does not have a ledger id set, updating to use ledger id {new_email_ledger.id}")
                        
                system_user_system_user = get_or_create_system_user_system_user()
                existing_system_user.ledger_id_id = new_email_ledger.id
                existing_system_user.change_by_user_id = system_user_system_user.id

                if not existing_system_user.first_name:
                    existing_system_user.first_name = current_email_system.first_name
                if not existing_system_user.last_name:
                    existing_system_user.last_name = current_email_system.last_name
                if not existing_system_user.legal_first_name:
                    existing_system_user.legal_first_name = current_email_system.legal_first_name
                if not existing_system_user.legal_last_name:
                    existing_system_user.legal_last_name = current_email_system.legal_last_name
                if not existing_system_user.legal_dob:
                    existing_system_user.legal_dob = current_email_system.legal_dob
                if not existing_system_user.title:
                    existing_system_user.title = current_email_system.title
                if not existing_system_user.phone_number:
                    existing_system_user.phone_number = current_email_system.phone_number
                if not existing_system_user.mobile_number:
                    existing_system_user.mobile_number = current_email_system.mobile_number
                if not existing_system_user.fax_number:
                    existing_system_user.fax_number = current_email_system.fax_number

                existing_system_user.save()

                #first, get every record from the current email that will move to the new email (only models in change_ledger_id need to be checked)
                to_be_changed = []
                for k in potential_blockers:
                    for v in potential_blockers[k]:
                        change = k.objects.filter(**{v:current_email_ledger.id})
                        if change.exists():
                            to_be_changed.append((k,list(change)))

                existing = []
                for k in potential_blockers:
                    for v in potential_blockers[k]:
                        exists = k.objects.filter(**{v:new_email_ledger.id})
                        if exists.exists():
                            existing.append((k,list(exists)))

                if to_be_changed and existing:
                    #check validity - if a record cannot be moved STOP
                    #proposals and approvals will need to be checked together to ensure they can exist on the same user
                    valid1, reason, merging_records = self.check_proposals_and_approvals(to_be_changed, existing)
                    print(reason)
                    #owners will require special handling - users may only have one owner record each so the vessel ownerships will need to be moved instead
                    #if a current vessel_ownership on the current owner shares a rego_no with the new owner's current vessel_ownerships, count as invalid and STOP
                    valid2, reason = self.check_ownerships(to_be_changed, existing)
                    print(reason)

                    if valid1 and valid2:
                        #deliver a warning - once merged the change CANNOT be reversed, so make that clear to the user
                        answer = input(f"""
###############################################################################################################################################################                                    
WARNING: you are about to merge {merging_records} and related records (such as logs and relation tables) in to a user with existing records!                
This process cannot be reversed using the change_user_email management command, the records will be bound to the same user once this process has completed. 

Will move and merge records from {current_email} in to {new_email}. Potential payment adjustments will need to be reviewed and conducted manually.
###############################################################################################################################################################  
Are you sure you want to continue? (y/n): """)
                        if answer.lower() != 'y':
                            return
                    else:
                        return 
                else:
                    if not to_be_changed:
                        print("Current user has no potentially conflicting records - change can proceed")
                    if not existing:
                        print("New (existing) user has no potentially conflicting records - change can proceed")

            for k in change_email:
                changed = []
                for v in change_email[k]:
                    change = k.objects.filter(**{v:current_email_ledger.email})
                    if change.exists():
                        count = change.count()
                        changed.append((v,list(change)))
                        change.update(**{v:new_email_ledger.email})
                        print("changed {} {} {}(s)".format(count,k._meta.model_name,v))
                        
                if changed and k in log_change_models:
                    try:
                        logging_model = log_change_models[k][0]
                        logging_model_relation = log_change_models[k][1]
                        changed_model = k
                        changed_model_relation = None if len(log_change_models[k]) < 3 else log_change_models[k][2]
                        for i in changed:
                            for c in i[1]:
                                if changed_model_relation:
                                    action = "Changed {} field due to user email change from {} to {} change for {} {} {}".format(i[0], current_email, new_email,changed_model._meta.model_name,logging_model_relation,getattr(c,changed_model_relation))
                                    print(logging_model.log_action(getattr(c,changed_model_relation),action))
                                else:
                                    action = "Changed {} field due to user email change from {} to {} change for {} {}".format(i[0], current_email, new_email,changed_model._meta.model_name,c)
                                    print(logging_model.log_action(c,action))

                    except Exception as e:
                        print("Error:",e)

            for k in change_ledger_id:
                if k in special_handling:
                    continue
                changed = []
                for v in change_ledger_id[k]:
                    change = k.objects.filter(**{v:current_email_ledger.id})
                    if change.exists():
                        count = change.count()
                        changed.append((v,list(change)))
                        change.update(**{v:new_email_ledger.id})
                        print("changed {} {} {}(s)".format(count,k._meta.model_name,v))
                        
                if changed and k in log_change_models:
                    try:
                        logging_model = log_change_models[k][0]
                        logging_model_relation = log_change_models[k][1]
                        changed_model = k
                        changed_model_relation = None if len(log_change_models[k]) < 3 else log_change_models[k][2]
                        for i in changed:
                            for c in i[1]:
                                if changed_model_relation:
                                    action = "Changed {} field due to user email from {} to {} change for {} {} {}".format(i[0], current_email, new_email, changed_model._meta.model_name,logging_model_relation,getattr(c,changed_model_relation))
                                    print(logging_model.log_action(getattr(c,changed_model_relation),action))
                                else:
                                    action = "Changed {} field due to user email from {} to {} change for {} {}".format(i[0], current_email, new_email, changed_model._meta.model_name,c)
                                    print(logging_model.log_action(c,action))

                    except Exception as e:
                        print("Error:",e)

            

            #special handling for certain models happens here
            if special_handling[Owner]:
                #check if new owner record exists, create it if it does not
                if not Owner.objects.filter(emailuser=new_email_ledger.id):
                    new_owner = Owner.objects.create(emailuser=new_email_ledger.id)

                #Users may only have one owner record, so we have to change to change VesselOwnership records instead
                try:
                    current_owner = Owner.objects.get(emailuser=current_email_ledger.id)
                    new_owner = Owner.objects.get(emailuser=new_email_ledger.id)
                    VesselOwnership.objects.filter(owner=current_owner).update(owner=new_owner)
                    print(f"changed all vessel ownerships from {current_owner} to {new_owner}")
                except Exception as e:
                    print(e)

            #transfer invoice ownership on ledger - raise an error if this fails
            res = change_user_invoice_ownership(current_email, new_email)
            if not 'message' in res or res['message'] != 'success':
                raise ValueError("Invoice ownership change failed")
            print("change_user_invoice_ownership response:", res['message'])
            