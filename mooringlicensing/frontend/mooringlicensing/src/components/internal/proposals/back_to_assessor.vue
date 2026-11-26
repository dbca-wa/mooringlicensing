
<template>
    <div id="internal-proposal-amend">
        <modal v-model:show="isModalOpen"transition="modal fade" @ok="ok()" @cancel="cancel()" :processing="processing" title="Back To Assessor" large>
            <div class="container-fluid">
                <div class="row">
                    <form   name="backToAssessorForm">
                        <alert v-model:show="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="row">
                                <div class="row mb-3">
                                    <div class="col-sm-3">
                                        <label class="form-label float-end" for="back_to_assessor_details">Details</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <textarea class="form-control" name="details" v-model="back_to_assessor.details" id="back_to_assessor_details"></textarea>
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
import {helpers, api_endpoints} from "@/utils/hooks.js"

export default {
    name:'BackToAssessor',
    components:{
        modal,
        alert,
    },
    props: {
        proposal: {
            type: Object,
            default: null,
        },
    },
    data:function () {
        let vm = this;
        return {
            isModalOpen:false,
            form: null,
            back_to_assessor: {
                details: '',
                proposal: vm.proposal,
            },
            errors: false,
            errorString: '',
            validation_form: null,
            processing: false,
        }
    },
    methods: {
        addFormValidations: function() {
            let vm = this;
            vm.validation_form = $(vm.form).validate({
                rules: {
                    details: {
                        required: true,
                    }
                },
                messages: {
                    details: {
                        required:"field is required",
                    }
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
        ok:function () {
            let vm =this;
            if($(vm.form).valid()){
                vm.sendData();
            }
        },
        cancel:function () {
            let vm = this;
            vm.close();
        },
        sendData: function(){

            let vm = this;
            vm.errors = false;
            vm.processing = true;
            let data = {'status': 'with_assessor_requirements', 'approver_comment': vm.back_to_assessor.details}
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/switch_status')), JSON.stringify(data),{
                emulateJSON:true,
            })
            .then(
                (res) => {
                    vm.close()
                    vm.$router.push({ path: '/internal' }); //Navigate to dashboard after creating Amendment request
                    vm.processing = false;
                }, 
                (err) => {
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(err),
                        'error'
                    )
                    vm.processing = false;
                }
            );
        },
        close: function(){
            this.isModalOpen = false;
            this.back_to_assessor = {
                details: '',
                proposal: {},
            };
            this.errors = false;
            $(this.$refs.details).val(null).trigger('change');
            $('.has-error').removeClass('has-error');

            this.validation_form.resetForm();
        },
    },
    computed: {
        showError: function() {
            return this.errors;
        },
    },
    mounted:function () {
        this.form = document.forms.backToAssessorForm;
        this.addFormValidations();
    },
}
</script>