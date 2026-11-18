<template>
    <div id="approvalExtension">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <form class="form-horizontal" name="approvalForm">
                        <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">

                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left" for="Name">New Expiry Date</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <div style="width: 70%;">
                                            <input
                                                type="date"
                                                class="form-control"
                                                name="expiry_date"
                                                v-model="approval.expiry_date"
                                                :min="today"
                                            >
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left"  for="Name">Extension Details</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <textarea name="extension_details" class="form-control" style="width:70%;" v-model="approval.extension_details"></textarea>
                                    </div>
                                </div>
                            </div>

                        </div>
                    </form>
                </div>
            </div>
            <div slot="footer">
                <button type="button" v-if="extendingApproval" disabled class="btn btn-default" @click="ok"><i class="fa fa-spinner fa-spin"></i> Processing</button>
                <button type="button" v-else class="btn btn-default" @click="ok">Ok</button>
                <button type="button" class="btn btn-default" @click="cancel">Cancel</button>
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
    name:'Extend-Approval',
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
            extendingApproval: false,
            validation_form: null,
            errors: false,
            errorString: '',
            success:false,
        }
    },
    computed: {
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        title: function(){
            return 'Extend Approval Expiry Date';
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
            this.approval.expiry_date = '';
            this.validation_form.resetForm();
        },
        sendData:function(){
            let vm = this;
            vm.errors = false;
            let approval = JSON.parse(JSON.stringify(vm.approval));
            vm.extendingApproval = true;

            vm.$http.post(helpers.add_endpoint_json(api_endpoints.approvals,vm.approval_id+'/approval_extension'),JSON.stringify(approval),{
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.extendingApproval = false;
                        vm.approval={};
                        vm.close();
                        swal(
                             'Extend',
                             'The expiry date of this Approval will be updated',
                             'success'
                        );
                        vm.$emit('refreshFromResponse',response);
                    },(error)=>{
                        vm.errors = true;
                        vm.extendingApproval = false;
                        vm.errorString = helpers.apiVueResourceError(error);
                    });
        },
        addFormValidations: function() {
            let vm = this;
            vm.validation_form = $(vm.form).validate({
                rules: {
                    expiry_date:"required",
                    extension_details:"required",
                },
                messages: {
                    extension_details:"Field is required",
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