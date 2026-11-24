<template>
    <div class="container" id="externalDash">
        <FormSection :formCollapse="false" label="Applications" Index="applications">
            <ApplicationsTable
                level="internal"
            />
        </FormSection>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import ApplicationsTable from "@/components/common/table_proposals.vue"
import { api_endpoints, helpers } from '@/utils/hooks'

export default {
    name: 'InternalDashboard',
    data() {
        let vm = this;
        return {
            proposals_url: api_endpoints.proposals_paginated_external,
            approvals_url: api_endpoints.approvals_paginated_external,
            compliances_url: api_endpoints.compliances_paginated,
            system_name: api_endpoints.system_name,
        }
    },
    components:{
        FormSection,
        ApplicationsTable,
    },
    computed: {
        is_external: function() {
            return this.level == 'external'
        },
    },
}
</script>
