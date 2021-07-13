<template>
    <div class="container" id="externalDash">
        <FormSection 
            :formCollapse="false" 
            label="Applications" 
            subtitle="- View existing applications and lodge new ones" 
            Index="applications"
        >
            <ApplicationsTable
                level="external"
            />
        </FormSection>

        <FormSection 
            :formCollapse="false" 
            label="Waiting List" 
            subtitle="- View and amend your waiting list allocation" 
            Index="waiting_list"
        >
            <WaitingListTable
                level="external"
                :approvalTypeFilter="wlaApprovalTypeFilter"
            />
        </FormSection>

        <FormSection 
            :formCollapse="false" 
            label="Licences and Permits" 
            subtitle="- View existing licences / permits and renew them" 
            Index="licences_and_permits"
        >
            <LicencesAndPermitsTable
                level="external"
                :approvalTypeFilter="allApprovalTypeFilter"
            />
        </FormSection>

        <FormSection 
            :formCollapse="false" 
            label="Compliances" 
            subtitle="- View submitted Compliances and submit new ones" 
            Index="compliances"
        >
            <CompliancesTable
                level="external"
            />
        </FormSection>

        <FormSection 
            :formCollapse="false" 
            label="Authorised User Applications for my Endorsement" 
            subtitle="" 
            Index="authorised_user_applications_for_my_endorsement"
        >
            <AuthorisedUserApplicationsTable
                level="external"
            />
        </FormSection>
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import FormSection from "@/components/forms/section_toggle.vue"
import ApplicationsTable from "@/components/common/table_proposals"
//import WaitingListTable from "@/components/common/table_approval_waiting_list"
import WaitingListTable from "@/components/common/table_approvals"
//import LicencesAndPermitsTable from "@/components/common/table_approval_licences_and_permits"
import LicencesAndPermitsTable from "@/components/common/table_approvals"
import CompliancesTable from "@/components/common/table_compliances"
import AuthorisedUserApplicationsTable from "@/components/common/table_approval_to_be_endorsed"
import { api_endpoints, helpers } from '@/utils/hooks'

export default {
    name: 'ExternalDashboard',
    data() {
        let vm = this;
        return {
            empty_list: '/api/empty_list',
            //proposals_url: helpers.add_endpoint_json(api_endpoints.proposals,'user_list'),
            //approvals_url: helpers.add_endpoint_json(api_endpoints.approvals,'user_list'),
            //compliances_url: helpers.add_endpoint_json(api_endpoints.compliances,'user_list'),

            proposals_url: api_endpoints.proposals_paginated_external,
            approvals_url: api_endpoints.approvals_paginated_external,
            compliances_url: api_endpoints.compliances_paginated_external,

            system_name: api_endpoints.system_name,
            allApprovalTypeFilter: ['ml', 'aap', 'aup'],
            wlaApprovalTypeFilter: ['wla',],
        }
    },
    components:{
        FormSection,
        ApplicationsTable,
        WaitingListTable,
        LicencesAndPermitsTable,
        CompliancesTable,
        AuthorisedUserApplicationsTable,
    },
    watch: {

    },
    computed: {
        is_external: function() {
            return this.level == 'external'
        },

    },
    methods: {
    },
    mounted: function () {

    },
    created: function() {

    },
}
</script>
