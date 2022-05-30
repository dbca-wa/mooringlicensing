<template>
    <div class="container" id="SearchDash">

        <SearchPerson />
        <SearchVessel />
        <SearchMooring />
        <SearchSticker />
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import SearchMooring from "./search_mooring.vue"
import SearchVessel from "./search_vessel.vue"
import SearchSticker from "./search_sticker.vue"
import SearchPerson from "./search_person.vue"

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
        SearchSticker,
        SearchPerson,
    },
    methods: {

    },
}
</script>

