<template lang="html">
    <div id="change-contact">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <form class="form-horizontal" name="declineForm">
                        <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-12">
                                        <label class="control-label"  for="Name">{{ detailsText }} </label>
                                        <textarea style="width: 70%;"class="form-control" name="reason" v-model="decline.reason"></textarea>
                                    </div>
                                </div>
                            </div>
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-12">
                                        <label class="control-label"  for="Name">{{ ccText }}</label>
                                        <input type="text" style="width: 70%;"class="form-control" name="cc_email" v-model="decline.cc_email"/>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
            <div slot="footer">
                <button type="button" v-if="decliningProposal" disabled class="btn btn-default" @click="ok"><i class="fa fa-spinner fa-spin"></i> Processing</button>
                <button type="button" v-else class="btn btn-default" @click="ok">Ok</button>
                <button type="button" class="btn btn-default" @click="cancel">Cancel</button>
            </div>
        </modal>
    </div>
</template>

<script>
import modal from '@vue-utils/bootstrap-modal.vue'
import alert from '@vue-utils/alert.vue'
import { helpers, api_endpoints, constants } from "@/utils/hooks.js"
export default {
    name:'Decline-Proposal',
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
            console.log('in sendData')
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
                    $.each(this.validElements(), function(index, element) {
                        var $element = $(element);
                        $element.attr("data-original-title", "").parents('.form-group').removeClass('has-error');
                    });
                    // destroy tooltips on valid elements
                    $("." + this.settings.validClass).tooltip("destroy");
                    // add or update tooltips
                    for (var i = 0; i < errorList.length; i++) {
                        var error = errorList[i];
                        $(error.element)
                            .tooltip({
                                trigger: "focus"
                            })
                            .attr("data-original-title", error.message)
                            .parents('.form-group').addClass('has-error');
                    }
                }
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