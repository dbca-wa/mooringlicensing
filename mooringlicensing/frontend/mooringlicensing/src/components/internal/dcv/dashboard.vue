<template>
    <div class="container" id="dcvDash">
        <FormSection :formCollapse="false" label="DCV Permits" Index="dcv_permits">
            <DcvPermitsTable
                level="internal"
            />
        </FormSection>
        <FormSection :formCollapse="false" label="DCV Admission Fees" Index="dcv_admission_fees">
            <DcvAdmissionsTable
                level="internal"
            />
        </FormSection>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import DcvPermitsTable from "@/components/common/table_dcv_permits.vue"
import DcvAdmissionsTable from "@/components/common/table_dcv_admissions.vue"

export default {
    name: 'InternalDcvDashboard',
    data() {
        let vm = this;
        return {

        }
    },
    components:{
        FormSection,
        DcvPermitsTable,
        DcvAdmissionsTable,
    },
    methods: {

    },
}
</script>

