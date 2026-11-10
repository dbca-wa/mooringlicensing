<template>
    <div id="bypassPayment">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <form class="form-horizontal" name="bypassForm">
                        <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <alert type="warning">
                            <strong>Caution</strong> 
                            This form will cancel the application invoice and forward the application to the approval/printing sticker stage.
                            This cannot be reversed through ordinary means.
                            </br></br>
                            Please consider whether or not the payment amount should be recorded as paid. If <strong>this</strong> application has already been paid for, for example, then the amount for this submission should not be recorded as paid.
                            </br></br>
                            If the amount is recorded as paid it may be factored in future payment deductions. If there is no record of payment associated with <strong>this</strong> application but payment has been made (either externally or via another defunct application), this may be needed.
                            </br></br>
                            Otherwise, if the checkbox if left unchecked then the amount paid will be recored as 0 and will not affect future payments.
                            </alert>
                        <div class="col-sm-12">
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left"  for="Name">Bypass Payment Reason</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <textarea name="bypass_payment_reason" class="form-control" style="width:70%;" v-model="bypass_payment_reason"></textarea>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="col-sm-12">
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-6">
                                        <label class="control-label pull-left"  for="Name">Record amount as paid (for potential future deductions)</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <input type="checkbox" v-model="record_amount_as_paid" />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
            <div slot="footer">
                <button type="button" v-if="submitting" disabled class="btn btn-default" @click="ok"><i class="fa fa-spinner fa-spin"></i> Processing</button>
                <button type="button" v-else class="btn btn-default" @click="ok">Ok</button>
                <button type="button" class="btn btn-default" @click="cancel">Cancel</button>
            </div>
        </modal>
    </div>
</template>

<script>
//import $ from 'jquery'
import modal from '@vue-utils/bootstrap-modal.vue'
import alert from '@vue-utils/alert.vue'
import {helpers,api_endpoints} from "@/utils/hooks.js"
export default {
    name:'Bypass-Payment',
    components:{
        modal,
        alert
    },
    data:function () {
        let vm = this;
        return {
            isModalOpen:false,
            form:null,
            proposal_id: Number,
            invoice_ref: String,
            submitting: false,
            validation_form: null,
            errors: false,
            errorString: '',
            success:false,
            bypass_payment_reason: '',
            record_amount_as_paid: false,
        }
    },
    computed: {
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        title: function(){
            return 'Bypass Application Payment for Proposal ' + this.proposal_id;
        }
    },
    methods:{
        ok:function () {
            let vm =this;
            if($(vm.form).valid()){
                vm.sendData();
            }
        },
        cancel:function () {
            this.close()
        },
        close:function () {
            this.isModalOpen = false;
            this.errors = false;
            $('.has-error').removeClass('has-error');
            this.validation_form.resetForm();
        },
        sendData:function(){
            let vm = this;
            vm.errors = false;
            let data = {'bypass_payment_reason':vm.bypass_payment_reason,'record_amount_as_paid':vm.record_amount_as_paid, 'invoice_ref':vm.invoice_ref}
            vm.submitting = true;

            vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal,vm.proposal_id+'/bypass_payment'),JSON.stringify(data),{
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.submitting = false;
                        vm.close();
                        swal(
                             'Bypass Payment',
                             'Payment of this application will be bypassed. The invoice will be voided and the application forwarded for final approval.',
                             'success'
                        );
                        vm.bypass_payment_reason = "";
                        vm.record_amount_as_paid = false;
                        vm.$emit('refreshFromResponse',response);
                    },(error)=>{
                        vm.errors = true;
                        vm.submitting = false;
                        vm.errorString = helpers.apiVueResourceError(error);
                    });
        },
        addFormValidations: function() {
            let vm = this;
            vm.validation_form = $(vm.form).validate({
                rules: {
                    bypass_payment_reason:"required",
                },
                messages: {
                    bypass_payment_reason:"Field is required",
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
        vm.form = document.forms.bypassForm;
        vm.addFormValidations();
   }
}
</script>