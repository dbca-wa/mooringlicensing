<template>
    <div id="current_vessels" v-if="vesselExists && !forEndorser">
        <FormSection
            v-if="
                mooringLicenceCurrentVesselDisplayText ||
                currentVesselDisplayText
            "
            label="Current Vessel"
            Index="current_vessel"
        >
            <div v-if="mooringLicenceCurrentVesselDisplayText" class="row mb-3">
                <div class="col-sm-9">
                    <label for="" class="col-sm-12 form-label">{{
                        mooringLicenceCurrentVesselDisplayText
                    }}</label>
                    <div class="col-sm-9">
                        <input
                            @change="resetCurrentVessel"
                            :disabled="readonly"
                            class="form-check-input"
                            type="radio"
                            id="current_vessel_false"
                            name="current_vessel_false"
                            :value="false"
                            v-model="keep_current_vessel"
                            required
                        />
                        <label for="current_vessel_false" class="form-label"
                            >Yes</label
                        >
                    </div>
                    <div class="col-sm-9">
                        <input
                            @change="resetCurrentVessel"
                            :disabled="readonly"
                            class="form-check-input"
                            type="radio"
                            id="current_vessel_true"
                            name="current_vessel_true"
                            :value="true"
                            v-model="keep_current_vessel"
                            required
                        />
                        <label for="current_vessel_true" class="form-label"
                            >No</label
                        >
                    </div>
                </div>
            </div>
            <div v-else class="row mb-3">
                <div class="col-sm-9">
                    <label for="" class="col-sm-12 form-label">{{
                        currentVesselDisplayText
                    }}</label>
                    <div class="col-sm-9">
                        <input
                            @change="resetCurrentVessel"
                            :disabled="readonly"
                            class="form-check-input"
                            type="radio"
                            id="current_vessel_true"
                            name="current_vessel_true"
                            :value="true"
                            v-model="keep_current_vessel"
                            required
                        />
                        <label for="current_vessel_true" class="form-label"
                            >Keep my current vessel</label
                        >
                    </div>
                    <div class="col-sm-9">
                        <input
                            @change="resetCurrentVessel"
                            :disabled="readonly"
                            class="form-check-input"
                            type="radio"
                            id="current_vessel_false"
                            name="current_vessel_false"
                            :value="false"
                            v-model="keep_current_vessel"
                            required
                        />
                        <label for="current_vessel_false" class="form-label"
                            >Change to different vessel</label
                        >
                    </div>
                </div>
            </div>
        </FormSection>
    </div>
</template>
<script>
import FormSection from '@/components/forms/section_toggle.vue';

export default {
    name: 'current_vessels',
    emits: ['resetCurrentVessel'],
    data: function () {
        return {
            keep_current_vessel: null, // Force the user to select one of the radio buttons
        };
    },
    components: {
        FormSection,
    },
    props: {
        proposal: {
            type: Object,
            required: true,
        },
        readonly: {
            type: Boolean,
            default: true,
        },
        is_internal: {
            type: Boolean,
            default: false,
        },
        add_vessel: {
            type: Boolean,
            default: false,
        },
        forEndorser: {
            type: Boolean,
            default: false,
        },
    },
    computed: {
        vesselExists: function () {
            if (this.proposal && !this.proposal.null_vessel_on_create) {
                return true;
            }
            return false;
        },
        mooringLicenceCurrentVesselDisplayText: function () {
            if (
                this.proposal &&
                this.proposal.current_vessels_rego_list &&
                this.proposal.current_vessels_rego_list.length > 0
            ) {
                return `Your mooring site licence ${this.proposal.approval_lodgement_number}
                currently lists the following vessels ${this.proposal.current_vessels_rego_list}.
                    Do you want to apply to add another vessel to your Mooring Site Licence?`;
            }
        },
        currentVesselDisplayText: function () {
            if (this.proposal && this.proposal.approval_vessel_rego_no) {
                return `Your ${this.proposal.approval_type_text} ${this.proposal.approval_lodgement_number}
                lists a vessel with registration number ${this.proposal.approval_vessel_rego_no}.
                    Do you want to keep this vessel listed or do you want to change to a different vessel?`;
            }
        },
    },
    methods: {
        resetCurrentVessel: function () {
            this.$nextTick(() => {
                this.$emit('resetCurrentVessel', this.keep_current_vessel);
            });
        },
    },
    mounted: function () {
        if (!this.vesselExists) {
            // When there are no vessels, it is internally handled as keep_current_vessel=false
            this.keep_current_vessel = false;
            this.resetCurrentVessel();
            return;
        }

        if (this.proposal) {
            if (this.proposal.proposal_type.code == 'swap_moorings') {
                // When swap moorings, always keep the current vessel
                this.keep_current_vessel = true;
                this.resetCurrentVessel();
            } else if (
                this.proposal.proposal_type.code == 'new' &&
                this.proposal.processing_status != 'Draft'
            ) {
                // When new and Draft
                this.keep_current_vessel = true;
                this.resetCurrentVessel();
            } else {
                this.keep_current_vessel = this.proposal.keep_existing_vessel;
                this.resetCurrentVessel();
            }
        }
    },
};
</script>

<style lang="css" scoped>
input[type='text'] {
    padding-left: 1em;
}
</style>
