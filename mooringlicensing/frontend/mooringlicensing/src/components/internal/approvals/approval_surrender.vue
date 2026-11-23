<template>
    <div id="approvalSurrender">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :processing="issuingApproval" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <div class="col-sm-12 warning">
                        Are you sure you want to surrender your {{ approval_type_name }}?<br />
                        Note: this is permanent and cannot be reversed.
                    </div>
                </div>
                <form   name="approvalForm">
                    <div class="row">
                        <alert v-model:show="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="row mb-3">
                                <div class="col-sm-3">
                                    <label class="form-label float-start"  for="Name">Surrender Details</label>
                                </div>
                                <div class="col-sm-9">
                                    <textarea name="surrender_details" class="form-control" style="width:70%;" v-model="approval.surrender_details"></textarea>
                                </div>
                            </div>

                        </div>
                    </div>
                </form>
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
    name:'Surrender-Approval',
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
            approval_type_name: '',
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
            return 'Surrender Approval';
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

            vm.$http.post(helpers.add_endpoint_json(api_endpoints.approvals,vm.approval_id+'/approval_surrender'),JSON.stringify(approval),{
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.issuingApproval = false;
                        vm.close();
                        swal(
                             'Surrender',
                             'An email has been sent to you confirming surrender of your ' + vm.approval_type_name + '.',
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
                    to_date:"required",
                    surrender_details:"required",
                },
                messages: {
                    surrender_details:"Field is required",
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

<style lang="css">
.warning {
    margin: 1em 0 2em 0;
    font-weight: bold;
}
</style>
