<template>
    <div class="container" id="MooringsDash">
        <FormSection :formCollapse="false" label="Moorings" Index="moorings">
            <MooringsTable/>
        </FormSection>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import MooringsTable from "@/components/common/table_moorings.vue"
export default {
    name: 'InternalMooringsDashboard',
    data() {
        let vm = this;
        return {

        }
    },
    components:{
        FormSection,
        MooringsTable,
    },
    methods: {

    },
}
</script>

