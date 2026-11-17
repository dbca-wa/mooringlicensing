
import InternalDashboard from '@/components/internal/dashboard.vue'
import Proposal from '@/components/internal/proposals/proposal.vue'
import DcvDashboard from '@/components/internal/dcv/dashboard.vue'
import ApprovalDash from '@/components/internal/approvals/dashboard.vue'
import ComplianceDash from '@/components/internal/compliances/dashboard.vue'
import StickersDash from '@/components/internal/stickers/dashboard.vue'
import InvoicesDash from '@/components/internal/invoices/dashboard.vue'
import WaitingListDash from '@/components/internal/waiting_list/dashboard.vue'
import MooringsDash from '@/components/internal/moorings/dashboard.vue'
import MooringDetail from '@/components/internal/moorings/mooring_detail.vue'
import VesselDetail from '@/components/internal/vessels/vessel_detail.vue'
import Search from '@/components/internal/search/dashboard.vue'
import PersonDetail from '@/components/internal/person/person_detail.vue'
import Compliance from '../compliances/access.vue'
import Approval from '@/components/internal/approvals/approval.vue'
import ManageVessel from '@/components/internal/manage_vessel.vue'
import ProposalApply from '@/components/external/proposal_apply.vue'
import DcvAdmissionForm from '@/components/external/dcv/dcv_admission.vue'
import DcvPermit from '@/components/external/dcv/dcv_permit.vue'

export default
{
    path: '/internal',
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
            component: InternalDashboard,
            name: 'internal-dashboard'
        },
        {
            path: 'approvals',
            component: ApprovalDash,
            name:"internal-approvals-dash"
        },
        {
            path: 'approval/:approval_id',
            component: Approval,
            name: 'internal-approval-detail',
        },
        {
            path: 'compliances',
            component: ComplianceDash,
            name: "internal-compliances-dash"
        },
        {
            path: 'waiting_list',
            component: WaitingListDash,
            name: "internal-waiting-list-dash"
        },
        {
            path: 'moorings',
            component: {
                render(c)
                {
                    return c('router-view')
                }
            },
            children: [
                {
                    path: '/',
                    component: MooringsDash,
                    name: "internal-moorings-dash",
                },
                {
                    path: ':mooring_id',
                    component: MooringDetail,
                    name:"internal-mooring-detail"
                },
            ]
        },
        {
            path: 'vessel',
            component: {
                render(c)
                {
                    return c('router-view')
                }
            },
            children: [
                {
                    path: ':vessel_id',
                    component: VesselDetail,
                    name:"internal-vessel-detail"
                },
            ]
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
                    path: ':vessel_id',
                    component: ManageVessel,
                    name:"internal-manage-vessel"
                },
            ]
        },
        {
            path: 'sticker',
            component: StickersDash,
            name: "internal-stickers-dash"
        },
        {
            path: 'invoice',
            component: InvoicesDash,
            name: "internal-invoices-dash"
        },
        {
            path: 'person/:email_user_id',
            component: PersonDetail,
            name: "internal-person-detail"
        },
        {
            path: 'compliance/:compliance_id',
            component: Compliance,

        },
        {
            path: 'search',
            component: Search,
            name:"internal-search"
        },
        {   
            path: 'dcv_permit',
            component: DcvPermit,
            name:"internal_dcv_permit",
            props: {is_internal:true},    
        },
        {
            path: 'dcv',
            component: {
                render(c)
                {
                    return c('router-view')
                }
            },
            children: [
                {
                    path: '/',
                    component: DcvDashboard,
                    name:"internal-dcv-dash"
                },
                {
                    path: 'dcv_admission_form',
                    component: DcvAdmissionForm,
                    name:"internal-dcv-admission-form",
                    props: {is_internal:true}, 
                }
            ]
        },
        {
            path: 'proposal',
            component: {
                render(c)
                {
                    return c('router-view')
                }
            },
            children: [
                {
                    path: '/',
                    component: ProposalApply,
                    name:"internal_apply_proposal",
                    props: {is_internal:true},
                },
                {
                    path: ':proposal_id',
                    component: {
                        render(c)
                        {
                            return c('router-view')
                        }
                    },
                    children: [
                        {
                            path: '/',
                            component: Proposal,
                            name:"internal-proposal"
                        },
                    ]
                },
            ]
        },
    ]
}
