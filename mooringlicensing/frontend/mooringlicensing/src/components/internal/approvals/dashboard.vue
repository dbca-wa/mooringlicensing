<template>
    <div class="container" id="approvalsDash">
        <FormSection :formCollapse="false" label="Approvals" Index="approvals">
            <ApprovalsTable
                level="internal"
                :approvalTypeFilter="approvalTypeFilter"
            />
        </FormSection>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import ApprovalsTable from "@/components/common/table_approvals.vue"

export default {
    name: 'InternalApprovalsDashboard',
    data() {
        let vm = this;
        return {
            approvalTypeFilter: ['ml', 'aap', 'aup'],
        }
    },
    components:{
        FormSection,
        ApprovalsTable,
    },
    methods: {

    },
}
</script>

