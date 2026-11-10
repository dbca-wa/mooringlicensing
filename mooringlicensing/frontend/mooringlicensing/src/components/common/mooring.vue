<template>
    <FormSection label="Preferred mooring area" Index="preferred_mooring_area">
        <div class="row form-group">
            <label for="" class="col-sm-9 control-label">Select one preferred mooring area. Preference cannot be changed without losing your original application date.</label>
        </div>
        <div class="row form-group">
            <div class="col-sm-6" v-for="mooring in mooringBays">
                <label :for="mooring.id" class="label-right col-sm-5 control-label">{{ mooring.name }}</label>
                <input :disabled="readonly" type="radio" :id="mooring.id" :value="mooring.id" v-model="selectedMooring" @change="mooringPreferenceChanged" required=""/>
            </div>
        </div>
    </FormSection>
</template>

<script>
import FormSection from '@/components/forms/section_toggle.vue'
import {
  api_endpoints
}
from '@/utils/hooks'

    export default {
        name:'mooring',
        components:{
            FormSection,
        },
        props:{
            proposal:{
                type: Object,
                required:true
            },
            readonly:{
                type: Boolean,
                default: true,
            },
        },
        data:function () {
            return {
                selectedMooring: null,
                mooringBays: [],
            }
        },
        methods:{
            mooringPreferenceChanged: async function() {
                console.log("mooringPrefChanged");
                let preferenceChanged = false;
                if (this.proposal.previous_application_preferred_bay_id !== this.selectedMooring) {
                    preferenceChanged = true;
                }
                this.$emit("mooringPreferenceChanged", preferenceChanged);
            },
            fetchMooringBays: async function(){
                const response = await this.$http.get(api_endpoints.mooring_bays);
                console.log(response.body)
                for (let bay of response.body.results) {
                    this.mooringBays.push(bay)
                }
            },
        },
        mounted:function () {
            this.$nextTick(async () => {
                await this.fetchMooringBays();
                // read in currently selected preference from Proposal
                if (this.proposal.preferred_bay_id) {
                    console.log("preferred bay");
                    this.selectedMooring = this.proposal.preferred_bay_id;
                }
                // now read in previously selected mooring bay
                if (this.proposal && !this.proposal.preferred_bay_id && this.proposal.previous_application_preferred_bay_id) {
                    this.selectedMooring = this.proposal.previous_application_preferred_bay_id;
                }
            });

        }
    }
</script>

<style lang="css" scoped>
.label-right {
    float: right;
    text-align: left;
    margin-right: 50%;
}
</style>
