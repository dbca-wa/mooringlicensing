<template>
    <div id="approvalCancellation">
        <modal v-model:show="isModalOpen"transition="modal fade" @ok="ok()" @cancel="cancel()" :processing="issuingApproval" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <form   name="approvalForm">
                        <alert v-model:show="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="row mb-3">
                                <div class="row">
                                    <div class="col-sm-3">

                                        <label class="form-label float-start"  for="Name">From Date</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <div style="width: 70%;">
                                            <input
                                                type="date"
                                                class="form-control"
                                                name="from_date"
                                                v-model="approval.from_date"
                                                :min="approval.from_date"
                                            >
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="row mb-3">
                                <div class="row">
                                    <div class="col-sm-3">

                                        <label class="form-label float-start"  for="Name">To Date</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <div style="width: 70%;">
                                            <input
                                                type="date"
                                                class="form-control"
                                                name="to_date"
                                                v-model="approval.to_date"
                                                :min="today"
                                            >
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="row mb-3">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="form-label float-start"  for="Name">Suspension Details</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <textarea name="suspension_details" class="form-control" style="width:70%;" v-model="approval.suspension_details"></textarea>
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
    name:'Suspend-Approval',
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
            return 'Suspend Approval';
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
            this.approval.from_date = '';
            this.approval.to_date = '';
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

            vm.$http.post(helpers.add_endpoint_json(api_endpoints.approvals,vm.approval_id+'/approval_suspension'),JSON.stringify(approval),{
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.issuingApproval = false;
                        vm.approval={};
                        vm.close();
                        swal(
                             'Suspend',
                             'An email has been sent to the proponent about suspension of this approval',
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
                    from_date:"required",
                    suspension_details:"required",
                },
                messages: {
                    suspension_details:"Field is required",
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