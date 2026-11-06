<template>
    <div class="container" id="externalDash">
        <template v-for="component in components_ordered">
            <FormSection 
                :formCollapse="component.formCollapse"
                :label="component.label"
                :subtitle="component.subtitle"
                :Index="component.Index"
                :subtitle_class_name="component.subtitle_class_name"
            >
                <component 
                    :is="component.type"
                    level="external"
                    :approvalTypeFilter="component.approvalTypeFilter"
                ></component>
            </FormSection>
        </template>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import ApplicationsTable from "@/components/common/table_proposals.vue"
import WaitingListTable from "@/components/common/table_approvals.vue"
import LicencesAndPermitsTable from "@/components/common/table_approvals.vue"
import CompliancesTable from "@/components/common/table_compliances.vue"
import AuthorisedUserApplicationsTable from "@/components/common/table_approval_to_be_endorsed.vue"
import { api_endpoints, helpers } from '@/utils/hooks'

export default {
    name: 'ExternalDashboard',
    data() {
        return {
            proposals_url: api_endpoints.proposals_paginated_external,
            approvals_url: api_endpoints.approvals_paginated_external,
            compliances_url: api_endpoints.compliances_paginated,

            system_name: api_endpoints.system_name,
            allApprovalTypeFilter: ['ml', 'aap', 'aup'],
            wlaApprovalTypeFilter: ['wla',],

            components_ordered: [],
            components: {
                'ApplicationsTable': {
                    type: 'ApplicationsTable',
                    approvalTypeFilter: [],
                    formCollapse: true,
                    label: "Applications",
                    subtitle: "- Lodge new applications or view pending applications",
                    Index: "applications",
                    subtitle_class_name: "subtitle-l",
                },
                'WaitingListTable': {
                    type: 'WaitingListTable',
                    approvalTypeFilter: ['wla',],
                    formCollapse: true,
                    label: "Waiting List",
                    subtitle: "- View or amend your waiting list allocation",
                    Index: "waiting_list",
                    subtitle_class_name: "subtitle-l",
                },
                'LicencesAndPermitsTable': {
                    type: 'LicencesAndPermitsTable',
                    approvalTypeFilter: ['ml', 'aap', 'aup'],
                    formCollapse: true,
                    label: "Licences and Permits", 
                    subtitle: "- View or renew licences or permits",
                    Index: "licences_and_permits",
                    subtitle_class_name: "subtitle-l",
                },
                'CompliancesTable': {
                    type: 'CompliancesTable',
                    approvalTypeFilter: [],
                    formCollapse: true,
                    label: "Compliances", 
                    subtitle: "- Manage compliance requirements",
                    Index: "compliances",
                    subtitle_class_name: "subtitle-l",
                },
                'AuthorisedUserApplicationsTable': {
                    type: 'AuthorisedUserApplicationsTable',
                    approvalTypeFilter: [],
                    formCollapse: true,
                    label: "Endorsements (licensees only)",
                    subtitle: "- View or approve mooring authorisations", 
                    Index: "authorised_user_applications_for_my_endorsement",
                    subtitle_class_name: "subtitle-l",
                },
            }
        }
    },
    components:{
        'FormSection': FormSection,
        'ApplicationsTable': ApplicationsTable,
        'WaitingListTable': WaitingListTable,
        'LicencesAndPermitsTable': LicencesAndPermitsTable,
        'CompliancesTable': CompliancesTable,
        'AuthorisedUserApplicationsTable': AuthorisedUserApplicationsTable,
    },
    watch: {

    },
    computed: {
        is_external: function() {
            return this.level == 'external'
        },

    },
    methods: {
        recalc: function(){
            console.log('test')
            console.log(this.components['WaitingListTable'])
        }
    },
    mounted: function () {

    },
    created: async function() {
        const res = await this.$http.get('/api/external_dashboard_sections_list/')
        let name_ordered = res.body
        for (let name of name_ordered){
            this.components_ordered.push(this.components[name])
        }
    },
}
</script>
