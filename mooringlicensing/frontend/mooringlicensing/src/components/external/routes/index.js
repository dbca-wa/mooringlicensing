import ExternalDashboard from '@/components/external/dashboard.vue'
import Proposal from '@/components/external/proposal.vue'
import ProposalApply from '@/components/external/proposal_apply.vue'
import ProposalSubmit from '@/components/external/proposal_submit.vue'
import Organisation from '@/components/external/organisations/manage.vue'
import DcvPermit from '@/components/external/dcv/dcv_permit.vue'
import DcvAdmission from '@/components/external/dcv/dcv_admission.vue'
import VesselsDashboard from '@/components/external/vessels_dashboard.vue'
import ManageVessel from '@/components/external/manage_vessel.vue'
import Compliance from '../compliances/access.vue'
import ComplianceSubmit from '../compliances/submit.vue'
/*
import Compliance from '../compliances/access.vue'
import ComplianceSubmit from '../compliances/submit.vue'
import Approval from '../approvals/approval.vue'
*/
export default
{
    path: '/external',
    component:
    {
        render(c)
        {
            return c('router-view')
        }
    },
    children: [
        {
            path: '/',
            component: ExternalDashboard,
            name: 'external-dashboard'
        },
        {
            path: 'organisations/manage/:org_id',
            component: Organisation
        },
        {
            path: 'compliance/:compliance_id',
            component: Compliance
        },
        {
            path: 'compliance/submit',
            component: ComplianceSubmit,
            name:"submit_compliance"
        },
        /*
        {
            path: 'approval/:approval_id',
            component: Approval,
        },
        */
        {
            path: 'proposal',
            component:
            {
                render(c)
                {
                    return c('router-view')
                }
            },
            children: [
                {
                    path: '/',
                    component: ProposalApply,
                    name:"apply_proposal"
                },
                {
                    path: 'submit',
                    component: ProposalSubmit,
                    name:"submit_proposal"
                },
                {
                    path: ':proposal_id',
                    component: Proposal,
                    name:"draft_proposal"
                },
            ]
        },
        {
            path: 'dcv_permit',
            component: DcvPermit,
            name: 'dcv_permit'
        },
        {
            path: 'dcv_admission',
            component: DcvAdmission,
            name: 'dcv_admission'
        },
        {
            path: 'vessels',
            component: VesselsDashboard,
            name: 'vessels-dashboard'
        },
        {
            path: 'vesselownership',
            component:
            {
                render(c)
                {
                    return c('router-view')
                }
            },
            children: [
                {
                    path: '/',
                    component: ManageVessel,
                    name:"new-vessel"
                },
                {
                    path: ':vessel_id',
                    component: ManageVessel,
                    name:"manage-vessel"
                },
            ]
        },

    ]
}
