<template>
    <FormSection label="Insurance details" Index="insurance_details">
        <div class="row form-group">
            <label for="" class="col-sm-9 control-label">The nominated vessel has
            </label>
        </div>
        <div class="row form-group">
            <div class="col-sm-9" v-for="choice in insuranceChoices">
                <div class="col-sm-1">
                <input :disabled="readonly" type="radio" name="insuranceChoice" :id="choice.code" :value="choice.code" required=""/>
                </div>
                <div class="col-sm-8">
                <label :for="choice.code">{{ choice.description }}</label>
                </div>
            </div>
        </div>
        <div v-if="!(applicationTypeCode==='aaa')" class="row form-group">
            <label for="" class="col-sm-3 control-label">Copy of the vessel's current insurance certificate showing legal liability amount</label>
            <div class="col-sm-9">
                <FileField 
                    :readonly="readonly"
                    ref="insurance_certificate_documents"
                    name="insurance-certificate-documents"
                    :isRepeatable="true"
                    :documentActionUrl="insuranceCertificateDocumentUrl"
                    :replace_button_by_text="true"
                    :keepCurrentVessel="keepCurrentVessel"
                />
            </div>
        </div>

    </FormSection>
</template>

<script>
import FormSection from '@/components/forms/section_toggle.vue'
import FileField from '@/components/forms/filefield_immediate.vue'
import {
  api_endpoints
}
from '@/utils/hooks'
    export default {
        name:'Insurance',
        components:{
            FormSection,
            FileField,
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
            keepCurrentVessel:{
                type: Boolean,
                default: true, 
            },
        },
        watch: {
            keepCurrentVessel: { 
                handler: function() {
                    if(!this.keepCurrentVessel){
                        this.selectedOption = null;
                        $('input[name="insuranceChoice"]').prop('checked', false).trigger('change');
                    }
                }
            }
        },

        data:function () {
            return {
                selectedOption: null,
                insuranceChoices: [],
            }
        },
        computed: {
            insuranceCertificateDocumentUrl: function() {
                let url = '';
                if (this.proposal && this.proposal.id) {
                    url = '/api/proposal/' + this.proposal.id + '/insurance_certificate_document/'
                }
                return url;
            },
            applicationTypeCode: function() {
                if (this.proposal) {
                    return this.proposal.application_type_code;
                }
            },

        },
        methods:{
            fetchInsuranceChoices: async function(){
                const response = await this.$http.get(api_endpoints.insurance_choices_dict);
                for (let choice of response.body) {
                    this.insuranceChoices.push(choice);
                }
            },
            addEventHandlers: function() {
                let vm = this;
                for (let choice of vm.insuranceChoices) {
                    let choiceSelector = '#' + choice.code;
                    $(choiceSelector).on('change', (e) => {
                        vm.selectedOption = e.currentTarget.value
                    });
                }
            },
        },
        mounted:function () {
            this.$nextTick(async () => {
                await this.fetchInsuranceChoices();
                this.addEventHandlers();
                // read selectedOption from proposal
                let vm = this;
                if (this.proposal.insurance_choice) {
                    this.selectedOption = this.proposal.insurance_choice;
                    let selected = $('#' + vm.selectedOption);
                    selected.prop('checked', true).trigger('change');
                }
                //selecting insurance choice of previous application
                else if (this.proposal.previous_application_id && this.keepCurrentVessel){
                    this.selectedOption = this.proposal.previous_application_insurance_choice
                    let selected = $('#' + vm.selectedOption);
                    selected.prop('checked', true).trigger('change');
                }
            });
        },
    }
</script>