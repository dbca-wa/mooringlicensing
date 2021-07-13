<template>
    <div class="container" id="WaitingListDash">
        <FormSection :formCollapse="false" label="Waiting List" Index="waiting_list">
            <WaitingListTable
                level="internal"
                :approvalTypeFilter="approvalTypeFilter"
            />
        </FormSection>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
//import WaitingListTable from "@/components/common/table_approval_waiting_list"
import WaitingListTable from "@/components/common/table_approvals"

export default {
    name: 'InternalWaitingListDashboard',
    data() {
        let vm = this;
        return {
            approvalTypeFilter: ['wla',],
        }
    },
    components:{
        FormSection,
        WaitingListTable,
    },
    methods: {

    },
}
</script>

