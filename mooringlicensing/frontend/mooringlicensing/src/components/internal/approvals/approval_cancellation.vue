<template>
    <div id="approvalCancellation">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :processing="issuingApproval" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <form class="form-horizontal" name="approvalForm">
                        <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">

                                        <label class="form-label float-start"  for="Name">Cancellation Date</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <div style="width: 70%;">
                                            <input
                                                type="date"
                                                class="form-control"
                                                name="cancellation_date"
                                                v-model="approval.cancellation_date"
                                                :min="today"
                                            >
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">

                                        <label class="form-label float-start"  for="Name">Cancellation Details</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <textarea name="cancellation_details" class="form-control" style="width:70%;" v-model="approval.cancellation_details"></textarea>
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
import {helpers,api_endpoints} from "@/utils/hooks.js"
export default {
    name:'Cancel-Approval',
    components:{
        modal,
        alert
    },
    data:function () {
        let vm = this;
        return {
            isModalOpen:false,
            form:null,
            approval: {},
            approval_id: Number,
            state: 'proposed_approval',
            issuingApproval: false,
            validation_form: null,
            errors: false,
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
        title: function(){
            return 'Cancel Approval';
        },
        today() {
            return new Date().toISOString().split('T')[0];
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
            this.approval = {};
            this.errors = false;
            $('.has-error').removeClass('has-error');
            this.approval.cancellation_date = '';
            this.validation_form.resetForm();
        },
        fetchContact: function(id){
            let vm = this;
            vm.$http.get(api_endpoints.contact(id)).then((response) => {
                vm.contact = response.body; vm.isModalOpen = true;
            },(error) => {
                console.log(error);
            } );
        },
        sendData:function(){
            let vm = this;
            vm.errors = false;
            let approval = JSON.parse(JSON.stringify(vm.approval));
            vm.issuingApproval = true;

            vm.$http.post(helpers.add_endpoint_json(api_endpoints.approvals,vm.approval_id+'/approval_cancellation'),JSON.stringify(approval),{
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.issuingApproval = false;
                        vm.close();
                        swal(
                             'Cancelled',
                             'An email has been sent to the proponent about cancellation of this approval',
                             'success'
                        );
                        vm.$emit('refreshFromResponse',response);


                    },(error)=>{
                        vm.errors = true;
                        vm.issuingApproval = false;
                        vm.errorString = helpers.apiVueResourceError(error);
                    });


        },
        addFormValidations: function() {
            let vm = this;
            vm.validation_form = $(vm.form).validate({
                rules: {
                    cancellation_date:"required",
                    cancellation_details:"required",
                },
                messages: {
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
        vm.form = document.forms.approvalForm;
        vm.addFormValidations();
   }
}
</script>