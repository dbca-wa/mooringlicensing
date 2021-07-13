<template>
    <div class="container" id="compliancesDash">
        <FormSection :formCollapse="false" label="Compliances" Index="compliances">
            <CompliancesTable
                level="internal"
            />

        </FormSection>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import CompliancesTable from "@/components/common/table_compliances.vue"
export default {
    name: 'InternalCompliancesDashboard',
    data() {
        let vm = this;
        return {

        }
    },
    components:{
        FormSection,
        CompliancesTable,
    },
    methods: {

    },
}
</script>

