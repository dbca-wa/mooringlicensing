<template lang="html">
    <div id="approvalSurrender">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <div class="col-sm-12 warning">
                        Are you sure you want to surrender your {{ approval_type_name }}?<br />
                        Note: this is permanent and cannot be reversed.
                    </div>
                </div>
                <form class="form-horizontal" name="approvalForm">
                    <div class="row">
                        <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <!--<div class="col-sm-12">
                            <div class="form-group">
                                <div class="col-sm-3">
                                    <label class="control-label pull-left"  for="Name">Surrender Date</label>
                                </div>
                                <div class="col-sm-9">
                                    <div class="input-group date" ref="surrender_date" style="width: 70%;">
                                        <input type="text" class="form-control" name="surrender_date" placeholder="DD/MM/YYYY" v-model="approval.surrender_date">
                                        <span class="input-group-addon">
                                            <span class="glyphicon glyphicon-calendar"></span>
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>-->

                        <div class="col-sm-12">
                            <div class="form-group">
                                <div class="col-sm-3">
                                    <label class="control-label pull-left"  for="Name">Surrender Details</label>
                                </div>
                                <div class="col-sm-9">
                                    <textarea name="surrender_details" class="form-control" style="width:70%;" v-model="approval.surrender_details"></textarea>
                                </div>
                            </div>

                        </div>
                    </div>
                </form>
            </div>
            <div slot="footer">
                <button type="button" v-if="issuingApproval" disabled class="btn btn-default" @click="ok"><i class="fa fa-spinner fa-spin"></i> Processing</button>
                <button type="button" v-else class="btn btn-default" @click="ok">Ok</button>
                <button type="button" class="btn btn-default" @click="cancel">Cancel</button>
            </div>
        </modal>
    </div>
</template>

<script>
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
            datepickerOptions:{
                format: 'DD/MM/YYYY',
                showClear:true,
                useCurrent:false,
                keepInvalid:true,
                allowInputToggle:true
            },
        }
    },
    computed: {
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        title: function(){
            return 'Surrender Approval';
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
            //$(this.$refs.surrender_date).data('DateTimePicker').clear();
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
       eventListeners:function () {
            let vm = this;
            // Initialise Date Picker
            $(vm.$refs.surrender_date).datetimepicker(vm.datepickerOptions);
            $(vm.$refs.surrender_date).on('dp.change', function(e){
                if ($(vm.$refs.surrender_date).data('DateTimePicker').date()) {
                    vm.approval.surrender_date =  e.date.format('DD/MM/YYYY');
                }
                else if ($(vm.$refs.surrender_date).data('date') === "") {
                    vm.approval.surrender_date = "";
                }
             });


       }
   },
   mounted:function () {
        let vm =this;
        vm.form = document.forms.approvalForm;
        vm.addFormValidations();
        this.$nextTick(()=>{
            vm.eventListeners();
        });
   }
}
</script>

<style lang="css">
.warning {
    margin: 1em 0 2em 0;
    font-weight: bold;
}
</style>
