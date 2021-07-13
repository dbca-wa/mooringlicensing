<template>
    <div class="container" id="SearchDash">
        <FormSection :formCollapse="false" label="Search Persons" Index="search_persons">

        </FormSection>
        <SearchVessel />
        <SearchMooring />
        <FormSection :formCollapse="false" label="Search Sticker Number" Index="search_sticker_number">

        </FormSection>
        <FormSection :formCollapse="false" label="Search Reference Number" Index="search_reference_number">

        </FormSection>
        <FormSection :formCollapse="false" label="Search Keyword" Index="search_keyword">

        </FormSection>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import SearchMooring from "./search_mooring.vue"
import SearchVessel from "./search_vessel.vue"
export default {
    name: 'InternalSearch',
    data() {
        let vm = this;
        return {

        }
    },
    components:{
        FormSection,
        SearchMooring,
        SearchVessel,
    },
    methods: {

    },
}
</script>

