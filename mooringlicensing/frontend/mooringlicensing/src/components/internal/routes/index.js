
import InternalDashboard from '@/components/internal/dashboard.vue'
import OrgAccessTable from '@/components/internal/organisations/dashboard.vue'
import OrgAccess from '@/components/internal/organisations/access.vue'
import Organisation from '@/components/internal/organisations/manage.vue'
import Proposal from '@/components/internal/proposals/proposal.vue'
import DcvDashboard from '@/components/internal/dcv/dashboard.vue'
import ApprovalDash from '@/components/internal/approvals/dashboard.vue'
import ComplianceDash from '@/components/internal/compliances/dashboard.vue'
import StickersDash from '@/components/internal/stickers/dashboard.vue'
import WaitingListDash from '@/components/internal/waiting_list/dashboard.vue'
import MooringsDash from '@/components/internal/moorings/dashboard.vue'
import MooringDetail from '@/components/internal/moorings/mooring_detail.vue'
import VesselDetail from '@/components/internal/vessels/vessel_detail.vue'
import DcvVesselDetail from '@/components/internal/vessels/dcv_vessel_detail.vue'
import Search from '@/components/internal/search/dashboard.vue'
import PersonDetail from '@/components/internal/person/person_detail.vue'
import Compliance from '../compliances/access.vue'
import Reports from '@/components/reports/reports.vue'
import Approval from '@/components/internal/approvals/approval.vue'
import ManageVessel from '@/components/internal/manage_vessel.vue'
/*
import User from '../users/manage.vue'
import ProposalCompare from '../proposals/proposal_compare.vue'
import Referral from '../referrals/referral.vue'
import PaymentOrder from '@/components/common/tclass/payment_order.vue'
import ParkEntryFeesDashboard from '../park_entry_fees_dashboard.vue'
import DistrictProposal from '../district_proposals/district_proposal.vue'
*/
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
            component: InternalDashboard
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
            //component: MooringsDash,
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
            //component: MooringsDash,
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
            path: 'dcv_vessel',
            //component: MooringsDash,
            component: {
                render(c)
                {
                    return c('router-view')
                }
            },
            children: [
                {
                    path: ':dcv_vessel_id',
                    component: DcvVesselDetail,
                    name:"internal-dcv-vessel-detail"
                },
            ]
        },

        {
            path: 'sticker',
            component: StickersDash,
            name: "internal-stickers-dash"
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
            path:'reports',
            name:'reports',
            component:Reports
        },
        {
            path: 'organisations',
            component: {
                render(c)
                {
                    return c('router-view')
                }
            },
            children: [
                {
                    path: 'access',
                    component: OrgAccessTable,
                    name:"org-access-dash"
                },
                {
                    path: 'access/:access_id',
                    component: OrgAccess,
                    name:"org-access"
                },
                {
                    path: ':org_id',
                    component: Organisation,
                    name:"internal-org-detail"
                },

            ]
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
