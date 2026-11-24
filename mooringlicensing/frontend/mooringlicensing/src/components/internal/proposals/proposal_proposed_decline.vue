<template>
    <div id="change-contact">
        <modal v-model:show="isModalOpen"transition="modal fade" @ok="ok()" @cancel="cancel()" :processing="decliningProposal" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <form   name="declineForm">
                        <alert v-model:show="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="row mb-3">
                                <div class="row">
                                    <div class="col-sm-12">
                                        <label class="form-label"  for="Name">{{ detailsText }} </label>
                                        <textarea style="width: 70%;"class="form-control" name="reason" v-model="decline.reason"></textarea>
                                    </div>
                                </div>
                            </div>
                            <div class="row mb-3">
                                <div class="row">
                                    <div class="col-sm-12">
                                        <label class="form-label"  for="Name">{{ ccText }}</label>
                                        <input type="text" style="width: 70%;"class="form-control" name="cc_email" v-model="decline.cc_email"/>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
        </modal>
    </div>
</template>

<script>
import $ from 'jquery'
import modal from '@vue-utils/bootstrap-modal.vue'
import alert from '@vue-utils/alert.vue'
import { helpers, api_endpoints, constants } from "@/utils/hooks.js"
export default {
    name:'Decline-Proposal',
    emits: [
        'refreshFromResponse',
    ],
    components:{
        modal,
        alert
    },
    props:{
        proposal: {
            type: Object,
            default: null,
        },
        processing_status:{
            type:String,
            required: true
        },
    },
    data:function () {
        let vm = this;
        return {
            isModalOpen:false,
            form:null,
            decline: {},
            decliningProposal: false,
            errors: false,
            validation_form: null,
            errorString: '',
            successString: '',
            success:false,
        }
    },
    computed: {
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        detailsText: function() {
            let details = 'Provide reason for the proposed decline';
            if (this.proposal && ['wla', 'aaa'].includes(this.proposal.application_type_code) || this.proposal.processing_status === "With Approver") {
                details = 'Details';
            }
            return details
        },
        ccText: function() {
            let details = 'Proposed CC Email';
            if (this.proposal && ['wla', 'aaa'].includes(this.proposal.application_type_code) || this.proposal.processing_status === "With Approver") {
                details = 'CC Email';
            }
            return details
        },
        title: function(){
            let title = this.processing_status == 'With Approver' ? 'Decline': 'Proposed Decline';
            if (this.proposal && ['wla', 'aaa'].includes(this.proposal.application_type_code)) {
                title = 'Decline';
            }
            return title;
        },
        callFinalDecline: function() {
            let callFinalDecline = false
            if (this.processing_status === constants.WITH_APPROVER){
                callFinalDecline = true
            }
            if ([constants.WL_PROPOSAL, constants.AA_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                if ([constants.WITH_ASSESSOR, constants.WITH_ASSESSOR_REQUIREMENTS].includes(this.processing_status)){
                    // For the WLA or AAA, assessor can final decline
                    callFinalDecline = true
                }
            }
            return callFinalDecline
        },
    },
    methods:{
        ok:function () {
            let vm =this;
            if($(vm.form).valid()){
                vm.sendData();
            }
        },
        cancel:function () {
            this.close();
        },
        close:function () {
            this.isModalOpen = false;
            this.decline = {};
            this.errors = false;
            $('.has-error').removeClass('has-error');
            this.validation_form.resetForm();
        },
        sendData:function(){

            let vm = this;
            vm.errors = false;
            let decline = JSON.parse(JSON.stringify(vm.decline));
            vm.decliningProposal = true;
            if (vm.callFinalDecline){
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, vm.proposal.id + '/final_decline'), JSON.stringify(decline), {
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.decliningProposal = false;
                        vm.close();
                        vm.$emit('refreshFromResponse',response);
                    },(error)=>{
                        vm.errors = true;
                        vm.decliningProposal = false;
                        vm.errorString = helpers.apiVueResourceError(error);
                    });
            } else {
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, vm.proposal.id + '/proposed_decline'), JSON.stringify(decline), {
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.decliningProposal = false;
                        vm.close();
                        vm.$emit('refreshFromResponse',response);
                        vm.$router.push({ path: '/internal' }); //Navigate to dashboard after propose decline.
                    },(error)=>{
                        vm.errors = true;
                        vm.decliningProposal = false;
                        vm.errorString = helpers.apiVueResourceError(error);
                    });
            }
        },
        addFormValidations: function() {
            let vm = this;
            vm.validation_form = $(vm.form).validate({
                messages: {
                    arrival:"field is required",
                    departure:"field is required",
                    campground:"field is required",
                    campsite:"field is required"
                },
                showErrors: function(errorMap, errorList) {
                    helpers.showValidationErrors.call(
                        this,
                        errorMap,
                        errorList
                    );
                },
            });
       },
   },
   mounted:function () {
       let vm =this;
       vm.form = document.forms.declineForm;
       vm.addFormValidations();
   }
}
</script>