<template lang="html">
    <div id="proposedIssuanceApproval">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <form class="form-horizontal" name="approvalForm">
                        <!-- <alert v-if="isApprovalLevelDocument" type="warning"><strong>{{warningString}}</strong></alert> -->
                        <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div v-show="showProposedStartEndDate" class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label v-if="processing_status == 'With Approver'" class="control-label pull-left"  for="Name">Start Date</label>
                                        <label v-else class="control-label pull-left"  for="Name">Proposed Start Date</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <div class="input-group date" ref="start_date" style="width: 70%;">
                                            <input type="text" class="form-control" name="start_date" placeholder="DD/MM/YYYY" v-model="approval.start_date">
                                            <span class="input-group-addon">
                                                <span class="glyphicon glyphicon-calendar"></span>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div class="row" v-show="showstartDateError">
                                    <alert  class="col-sm-12" type="danger"><strong>{{startDateErrorString}}</strong></alert>

                                </div>
                            </div>
                            <div v-show="showProposedStartEndDate" class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label v-if="processing_status == 'With Approver'" class="control-label pull-left"  for="Name">Expiry Date</label>
                                        <label v-else class="control-label pull-left"  for="Name">Proposed Expiry Date</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <div class="input-group date" ref="due_date" style="width: 70%;">
                                            <input type="text" class="form-control" name="due_date" placeholder="DD/MM/YYYY" v-model="approval.expiry_date" :readonly="is_amendment">
                                            <span class="input-group-addon">
                                                <span class="glyphicon glyphicon-calendar"></span>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div class="row" v-show="showtoDateError">
                                    <alert  class="col-sm-12" type="danger"><strong>{{toDateErrorString}}</strong></alert>

                                </div>

                            </div>
                            <div class="form-group" v-if="display_bay_field">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left" for="mooring_bay">Bay</label>
                                    </div>
                                    <div v-if="siteLicensee" class="col-sm-9" id="mooring_bay">
                                        <input disabled :value="siteLicenseeMooring.mooring_bay_name" name="mooring_bay" />
                                    </div>
                                    <div v-else class="col-sm-6">
                                        <select class="form-control" v-model="approval.mooring_bay_id" id="mooring_bay_lookup">
                                            <option v-for="bay in mooringBays" v-bind:value="bay.id">
                                            {{ bay.name }}
                                            </option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                            <div class="form-group" v-if="display_mooring_site_id_field">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left" for="mooring_site_id">Mooring Site ID</label>
                                    </div>
                                    <div v-if="siteLicensee" class="col-sm-9">
                                        <input disabled :value="siteLicenseeMooring.name" id="mooring_site_id"/>
                                    </div>
                                    <div v-else class="col-sm-6">
                                        <select
                                            id="mooring_lookup"
                                            name="mooring_lookup"
                                            ref="mooring_lookup"
                                            class="form-control"
                                            style="width:100%"
                                        />
                                    </div>
                                </div>
                            </div>
                            <!-- div class="form-group" v-if="display_sticker_number_field">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left" for="Bay">Sticker number</label>
                                    </div>
                                    <div class="col-sm-9">
                                        TODO: implement
                                    </div>
                                </div>
                            </div -->

                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label v-if="processing_status == 'With Approver'" class="control-label pull-left"  for="Name">Details</label>
                                        <label v-else class="control-label pull-left"  for="Name">Proposed Details</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <textarea name="approval_details" class="form-control" style="width:70%;" v-model="approval.details"></textarea>
                                    </div>
                                </div>
                            </div>
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label v-if="processing_status == 'With Approver'" class="control-label pull-left"  for="Name">BCC email</label>
                                        <label v-else class="control-label pull-left"  for="Name">Proposed BCC email</label>
                                    </div>
                                    <div class="col-sm-9">
                                            <input type="text" class="form-control" name="approval_cc" style="width:70%;" ref="bcc_email" v-model="approval.cc_email">
                                    </div>
                                </div>
                            </div>
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-12">
                                        <label v-if="submitter_email && applicant_email" class="control-label pull-left"  for="Name">After approving this proposal, approval will be emailed to {{submitter_email}} and {{applicant_email}}.</label>
                                        <label v-else class="control-label pull-left"  for="Name">After approving this proposal, approval will be emailed to {{submitter_email}}.</label>
                                    </div>

                                </div>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
            <p v-if="can_preview">Click <a href="#" @click.prevent="preview">here</a> to preview the approval letter.</p>

            <div slot="footer">
                <button type="button" v-if="issuingApproval" disabled class="btn btn-default" @click="ok"><i class="fa fa-spinner fa-spin"></i> Processing</button>
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
import { helpers, api_endpoints, constants } from "@/utils/hooks.js"

export default {
    name:'Proposed-Approval',
    components:{
        modal,
        alert
    },
    props:{
        proposal_id: {
            type: Number,
            required: true
        },
        proposal: null,
        processing_status: {
            type: String,
            required: true
        },
        proposal_type: {
            type: String,
            required: true
        },
        isApprovalLevelDocument: {
            type: Boolean,
            required: true
        },
        submitter_email: {
            type: String,
            required: true
        },
        applicant_email: {
            type: String,
            //default: ''
        },
    },
    data:function () {
        let vm = this;
        return {
            isModalOpen:false,
            form:null,
            approval: {
                mooring_id: null,
                mooring_bay_id: null,
            },
            state: 'proposed_approval',
            issuingApproval: false,
            validation_form: null,
            errors: false,
            toDateError:false,
            startDateError:false,
            errorString: '',
            toDateErrorString:'',
            startDateErrorString:'',
            successString: '',
            success:false,
            datepickerOptions:{
                format: 'DD/MM/YYYY',
                showClear:true,
                useCurrent:false,
                keepInvalid:true,
                allowInputToggle:true
            },
            warningString: 'Please attach Level of Approval document before issuing Approval',
            siteLicenseeMooring: {},
            mooringBays: [],
        }
    },
    computed: {
        siteLicensee: function() {
            let licensee = false;
            if (this.proposal && this.proposal.mooring_authorisation_preference === 'site_licensee') {
                licensee = true;
            }
            return licensee;
        },
        /*
        siteLicenseeMooring: function() {
            let mooring = null;
            if (this.proposal) {
                mooring = this.proposal.mooring_id;
            }
            return mooring;
        },
        */
        display_bay_field: function(){
            if ([constants.AU_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                return true
            }
            return false
        },
        display_mooring_site_id_field: function(){
            if ([constants.AU_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                return true
            }
            return false
        },
        display_sticker_number_field: function() {
            if ([constants.WL_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                return false
            }
            return true
        },
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        showtoDateError: function() {
            var vm = this;
            return vm.toDateError;
        },
        showstartDateError: function() {
            var vm = this;
            return vm.startDateError;
        },
        title: function(){
            return this.processing_status == 'With Approver' ? 'Grant' : 'Propose grant';
        },
        is_amendment: function(){
            return this.proposal_type == 'Amendment' ? true : false;
        },
        csrf_token: function() {
          return helpers.getCookie('csrftoken')
        },
        can_preview: function(){
            return this.processing_status == 'With Approver' ? true : false;
        },
        preview_licence_url: function() {
          return (this.proposal_id) ? `/preview/licence-pdf/${this.proposal_id}` : '';
        },
        showProposedStartEndDate: function(){
            // For mooringlicensing, we don't neeed 'start date' and 'expiry date' at all...?
            return false
        },
    },
    methods:{
        preview:function () {
            let vm =this;
            let formData = new FormData(vm.form)
            // convert formData to json
            let jsonObject = {};
            for (const [key, value] of formData.entries()) {
                jsonObject[key] = value;
            }
            vm.post_and_redirect(vm.preview_licence_url, {'csrfmiddlewaretoken' : vm.csrf_token, 'formData': JSON.stringify(jsonObject)});
        },
        post_and_redirect: function(url, postData) {
            /* http.post and ajax do not allow redirect from Django View (post method),
               this function allows redirect by mimicking a form submit.
               usage:  vm.post_and_redirect(vm.application_fee_url, {'csrfmiddlewaretoken' : vm.csrf_token});
            */
            var postFormStr = "<form method='POST' target='_blank' name='Preview Licence' action='" + url + "'>";
            for (var key in postData) {
                if (postData.hasOwnProperty(key)) {
                    postFormStr += "<input type='hidden' name='" + key + "' value='" + postData[key] + "'>";
                }
            }
            postFormStr += "</form>";
            var formElement = $(postFormStr);
            $('body').append(formElement);
            $(formElement).submit();
        },
        ok:function () {
            let vm =this;
            if($(vm.form).valid()){
                vm.sendData();
                //vm.$router.push({ path: '/internal' });
            }
        },
        cancel:function () {
            this.close()
        },
        close:function () {
            this.isModalOpen = false;
            this.approval = {};
            this.errors = false;
            this.toDateError = false;
            this.startDateError = false;
            $('.has-error').removeClass('has-error');
            this.validation_form.resetForm();
        },
        fetchMooringBays: async function() {
            const res = await this.$http.get(api_endpoints.mooring_bays);
            for (let bay of res.body) {
                this.mooringBays.push(bay)
            }
        },
        fetchSiteLicenseeMooring: async function() {
            const res = await this.$http.get(`${api_endpoints.mooring}${this.proposal.mooring_id}`);
            this.siteLicenseeMooring = Object.assign({}, res.body);
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
            if (vm.state == 'proposed_approval'){
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal,vm.proposal_id + '/proposed_approval'),JSON.stringify(approval),{
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.issuingApproval = false;
                        vm.close();
                        vm.$emit('refreshFromResponse',response);
                        vm.$router.push({ path: '/internal' }); //Navigate to dashboard page after Propose issue.

                    },(error)=>{
                        vm.errors = true;
                        vm.issuingApproval = false;
                        vm.errorString = helpers.apiVueResourceError(error);
                    });
            }
            else if (vm.state == 'final_approval'){
                console.log('final_approval in proposed_issuance.vue')
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal,vm.proposal_id+'/final_approval'),JSON.stringify(approval),{
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.issuingApproval = false;
                        vm.close();
                        vm.$emit('refreshFromResponse', response);
                    },(error)=>{
                        vm.errors = true;
                        vm.issuingApproval = false;
                        vm.errorString = helpers.apiVueResourceError(error);
                    });
            }

        },
        addFormValidations: function() {
            let vm = this;
            vm.validation_form = $(vm.form).validate({
                rules: {
                    //start_date:"required",
                    //due_date:"required",
                    approval_details:"required",
                },
                messages: {
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
       },
        initialiseMooringLookup: function(){
            let vm = this;
            $(vm.$refs.mooring_lookup).select2({
                minimumInputLength: 2,
                "theme": "bootstrap",
                allowClear: true,
                placeholder:"Select Mooring",
                ajax: {
                    url: api_endpoints.mooring_lookup_per_bay,
                    //url: api_endpoints.vessel_rego_nos,
                    dataType: 'json',
                    data: function(params) {
                        var query = {
                            term: params.term,
                            type: 'public',
                            mooring_bay_id: vm.approval.mooring_bay_id,
                        }
                        return query;
                    },
                },
            }).
            on("select2:select", function (e) {
                var selected = $(e.currentTarget);
                let data = e.params.data.id;
                vm.approval.mooring_id = data;
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.approval.mooring_id = null;
            }).
            on("select2:open",function (e) {
                //const searchField = $(".select2-search__field")
                const searchField = $('[aria-controls="select2-mooring_lookup-results"]')
                // move focus to select2 field
                searchField[0].focus();
            });
            vm.readRiaMooring();
            // clear mooring lookup on Mooring Bay change
            $('#mooring_bay_lookup').on('change', function() {
                $(vm.$refs.mooring_lookup).val(null).trigger('change');
            });
        },
        readRiaMooring: function() {
            let vm = this;
            if (vm.approval.ria_mooring_name) {
                console.log("read ria mooring")
                var option = new Option(vm.approval.ria_mooring_name, vm.approval.ria_mooring_name, true, true);
                $(vm.$refs.mooring_lookup).append(option).trigger('change');
            }
        },

    },
    mounted:function () {
        let vm =this;
        vm.form = document.forms.approvalForm;
        vm.addFormValidations();
        this.$nextTick(()=>{
            //vm.eventListeners();
            this.approval = Object.assign({}, this.proposal.proposed_issuance_approval);
            this.initialiseMooringLookup();

        });
    },
    created: function() {
        this.$nextTick(()=>{
            this.fetchMooringBays();
            if (this.siteLicensee) {
                this.fetchSiteLicenseeMooring();
            }
        });
    },
}
</script>

<style lang="css">
</style>
