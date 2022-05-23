<template lang="html">
    <div id="current_vessels" v-if="vesselExists">
        current_vessels.vue
        <FormSection v-if="mooringLicenceCurrentVesselDisplayText || currentVesselDisplayText" label="Current Vessel" Index="current_vessel">
            <div v-if="mooringLicenceCurrentVesselDisplayText" class="row form-group">
                <div class="col-sm-9">
                    <label for="" class="col-sm-12 control-label">{{ mooringLicenceCurrentVesselDisplayText }}</label>
                        <div class="col-sm-9">
                            <input 
                            @change="resetCurrentVessel" 
                            :disabled="readonly" 
                            type="radio" 
                            id="current_vessel_false" 
                            name="current_vessel_false" 
                            :value="false" 
                            v-model="keep_current_vessel" 
                            required
                            />
                            <label for="current_vessel_false" class="control-label">Yes</label>
                        </div>
                        <div class="col-sm-9">
                            <input 
                            @change="resetCurrentVessel" 
                            :disabled="readonly" 
                            type="radio" 
                            id="current_vessel_true" 
                            name="current_vessel_true" 
                            :value="true" 
                            v-model="keep_current_vessel" 
                            required
                            />
                            <label for="current_vessel_true" class="control-label">No</label>
                        </div>
                </div>
            </div>
            <div v-else class="row form-group">
                <div class="col-sm-9">
                    <label for="" class="col-sm-12 control-label">{{ currentVesselDisplayText }}</label>
                        <div class="col-sm-9">
                            <input 
                            @change="resetCurrentVessel" 
                            :disabled="readonly" 
                            type="radio" 
                            id="current_vessel_true" 
                            name="current_vessel_true" 
                            :value="true" 
                            v-model="keep_current_vessel" 
                            required
                            />
                            <label for="current_vessel_true" class="control-label">Keep my current vessel</label>
                        </div>
                        <div class="col-sm-9">
                            <input 
                            @change="resetCurrentVessel" 
                            :disabled="readonly" 
                            type="radio" 
                            id="current_vessel_false" 
                            name="current_vessel_false" 
                            :value="false" 
                            v-model="keep_current_vessel" 
                            required
                            />
                            <label for="current_vessel_false" class="control-label">Change to different vessel</label>
                        </div>

                </div>
            </div>
        </FormSection>
    </div>

</template>
<script>
import Vue from 'vue'
import FormSection from '@/components/forms/section_toggle.vue'
var select2 = require('select2');
require("select2/dist/css/select2.min.css");
require("select2-bootstrap-theme/dist/select2-bootstrap.min.css");
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'

    export default {
        name:'current_vessels',
        data:function () {
            return {
                keep_current_vessel: true,
            }
        },
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
            is_internal:{
              type: Boolean,
              default: false
            },
        },
        computed: {
            vesselExists: function() {
                if (this.proposal && !this.proposal.null_vessel_on_create) {
                    return true;
                }
            },
            mooringLicenceCurrentVesselDisplayText: function() {
                //if (this.proposal && this.proposal.mooring_licence_vessels && this.proposal.mooring_licence_vessels.length) {
                if (this.proposal && this.proposal.current_vessels_rego_list && this.proposal.current_vessels_rego_list.length > 0) {
                    return `Your mooring licence ${this.proposal.approval_lodgement_number} 
                    currently lists the following vessels ${this.proposal.current_vessels_rego_list}. 
                        Do you want to apply to add another vessel to your Mooring Licence?`;
                }
                //return '';
            },
            currentVesselDisplayText: function() {
                if (this.proposal && this.proposal.approval_vessel_rego_no) {
                    return `Your ${this.proposal.approval_type_text} ${this.proposal.approval_lodgement_number} 
                    lists a vessel with registration number ${this.proposal.approval_vessel_rego_no}. 
                        Do you want to keep this vessel listed or do you want to change to a different vessel?`;
                }
                //return '';
            },

        },
        methods:{
            resetCurrentVessel: function() {
                this.$nextTick(() => {
                    this.$emit("resetCurrentVessel", this.keep_current_vessel)
                });
            },
        },
        mounted: function () {
        },
        created: function() {
            if (this.proposal && !this.proposal.keep_existing_vessel) {
                this.keep_current_vessel = false;
                this.resetCurrentVessel();
            }
        },
    }
</script>

<style lang="css" scoped>
    input[type=text] {
        padding-left: 1em;
    }
</style>

