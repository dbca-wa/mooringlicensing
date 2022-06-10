<template lang="html">
    <div id="proposedIssuanceApproval">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <form class="form-horizontal" name="approvalForm">
                        <!-- <alert v-if="isApprovalLevelDocument" type="warning"><strong>{{warningString}}</strong></alert> -->
                        <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="form-group" v-if="displayBayField">
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
                            <div class="form-group" v-if="displayMooringSiteIdField">
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
                            <div class="form-group" v-if="displayAssociatedMoorings">
                                <div class="row col-sm-12">
                                    <datatable
                                        ref="mooringsTable"
                                        :id="mooringsTableId"
                                        :dtOptions="mooringsDtOptions"
                                        :dtHeaders="mooringsDtHeaders"
                                    />
                                </div>

                            </div>
                            <div class="form-group" v-if="displayAssociatedVessels">
                                <div class="row col-sm-12">
                                    <datatable
                                        ref="vesselsTable"
                                        :id="vesselsTableId"
                                        :dtOptions="vesselsDtOptions"
                                        :dtHeaders="vesselsDtHeaders"
                                    />
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
                                        <!--label v-if="processing_status == 'With Approver'" class="control-label pull-left"  for="Name">Details</label>
                                        <label v-else class="control-label pull-left"  for="Name">Proposed Details</label-->
                                        <label class="control-label pull-left"  for="Name">{{ detailsText }}</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <textarea name="approval_details" class="form-control" style="width:70%;" v-model="approval.details"></textarea>
                                    </div>
                                </div>
                            </div>
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <!--label v-if="processing_status == 'With Approver'" class="control-label pull-left"  for="Name">BCC email</label>
                                        <label v-else class="control-label pull-left"  for="Name">Proposed BCC email</label-->
                                        <label class="control-label pull-left"  for="Name">{{ ccText }}</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <input type="text" class="form-control" name="approval_cc" style="width:70%;" ref="bcc_email" v-model="approval.cc_email">
                                    </div>
                                </div>
                            </div>
                            <div class="form-group">
                                <div class="row">
                                    <!--div class="col-sm-12">
                                        <label v-if="submitter_email && applicant_email" class="control-label pull-left"  for="Name">After approving this application, approval will be emailed to {{submitter_email}} and {{applicant_email}}.</label>
                                        <label v-else class="control-label pull-left"  for="Name">After approving this application, approval will be emailed to {{submitter_email}}.</label>
                                    </div-->

                                </div>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
            <!--p v-if="can_preview">Click <a href="#" @click.prevent="preview">here</a> to preview the approval letter.</p-->

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
import datatable from '@vue-utils/datatable.vue'
import { helpers, api_endpoints, constants } from "@/utils/hooks.js"

export default {
    name:'Proposed-Approval',
    components:{
        modal,
        alert,
        datatable,
    },
    props:{
        enable_col_checkbox: {
            type: Boolean,
            default: true,
        },
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
    /*
    watch: {
        authorisedUserMoorings: function() {
            console.log("watch")
            if (this.authorisedUserMoorings.length > 0) {
                this.constructMooringsTable();
            }
        },
    },
    */
    data:function () {
        let vm = this;
        return {
            isModalOpen:false,
            form:null,
            approval: {
                mooring_id: null,
                mooring_bay_id: null,
                /*
                mooring_on_approval: [],
                vessel_ownership: [],
                */
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
            mooringsTableId: 'moorings_table' + vm._uid,
            vesselsTableId: 'vessels_table' + vm._uid,
            mooringsDtHeaders: [
                'Id',
                '',
                'Currently listed moorings',
                'Bay',
                '',
                'Status',
            ],
            mooringsDtOptions: {
                serverSide: false,
                searching: false,
                searchDelay: 1000,
                lengthMenu: [ [10, 25, 50, 100, -1], [10, 25, 50, 100, "All"] ],
                order: [
                    [1, 'desc'], [0, 'desc'],
                ],
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                processing: true,
                createdRow: function(row, data, index){
                    $(row).attr('data-mooring-on-approval-id', data.id)
                },
                columns: [
                    {
                        // Id (database id)
                        visible: false,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.id;
                            //return '';
                        }
                    },
                    {
                        // Checkbox
                        //visible: vm.show_col_checkbox,
                        //className: 'dt-body-center',
                        data: 'id',
                        mRender: function (data, type, full) {
                            /*
                            let disabled_str = ''
                            if (vm.readonly || !full.mooring_licence_current || !full.suitable_for_mooring){
                                disabled_str = ' disabled '
                            }
                            if (full.checked){
                                return '<input type="checkbox" class="mooring_on_approval_checkbox" data-mooring-on-approval-id="' + full.id + '"' + disabled_str + ' checked/>'
                            } else {
                                return '<input type="checkbox" class="mooring_on_approval_checkbox" data-mooring-on-approval-id="' + full.id + '"' + disabled_str + '/>'
                            }
                            return '';
                            */
                            if (full.checked){
                                return '<input type="checkbox" class="mooring_on_approval_checkbox" data-mooring-on-approval-id="' + full.id + '"' + ' checked/>'
                            } else {
                                return '<input type="checkbox" class="mooring_on_approval_checkbox" data-mooring-on-approval-id="' + full.id + '"' + '/>'
                            }
                            return '';

                        }
                    },
                    {
                        // Id (database id)
                        //visible: vm.show_col_id,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.mooring_name;
                            //return '';
                        }
                    },
                    {
                        // Id (database id)
                        //visible: vm.show_col_id,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.bay;
                            //return '';
                        }
                    },
                    {
                        // Id (database id)
                        //visible: vm.show_col_id,
                        data: 'id',
                        mRender: function (data, type, full) {
                            //return full.site_licensee ? 'User requested' : 'RIA allocated';
                            return full.site_licensee;
                            //return '';
                        }
                    },
                    {
                        // Id (database id)
                        //visible: vm.show_col_id,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.status;
                            //return '';
                        }
                    },
                    ],
            },
            vesselsDtHeaders: [
                'Id',
                '',
                'Currently listed vessels',
                'Vessel name',
                'Status',
            ],
            vesselsDtOptions: {
                serverSide: false,
                searching: false,
                searchDelay: 1000,
                lengthMenu: [ [10, 25, 50, 100, -1], [10, 25, 50, 100, "All"] ],
                order: [
                    [1, 'desc'], [0, 'desc'],
                ],
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                processing: true,
                createdRow: function(row, data, index){
                    $(row).attr('data-vessel-ownership-id', data.id)
                },
                columns: [
                    {
                        // Id (database id)
                        visible: false,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.id;
                            //return '';
                        }
                    },
                    {
                        // Checkbox
                        //visible: vm.show_col_checkbox,
                        //className: 'dt-body-center',
                        data: 'id',
                        mRender: function (data, type, full) {
                            let disabled_str = ''
                            if (vm.readonly){
                                disabled_str = ' disabled '
                            }
                            if (full.checked){
                                return '<input type="checkbox" class="mooring_on_approval_checkbox" data-vessel-ownership-id="' + full.id + '"' + disabled_str + ' checked/>'
                            } else {
                                return '<input type="checkbox" class="mooring_on_approval_checkbox" data-vessel-ownership-id="' + full.id + '"' + disabled_str + '/>'
                            }
                            return '';
                        }
                    },
                    {
                        // Id (database id)
                        //visible: vm.show_col_id,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.rego;
                            //return '';
                        }
                    },
                    {
                        // Id (database id)
                        //visible: vm.show_col_id,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.vessel_name;
                            //return '';
                        }
                    },
                    /*
                    {
                        // Id (database id)
                        //visible: vm.show_col_id,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.site_licensee ? 'User requested' : 'RIA allocated';
                            //return '';
                        }
                    },
                    */
                    {
                        // Id (database id)
                        //visible: vm.show_col_id,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.status;
                            //return '';
                        }
                    },
                    ],
            },

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
        mooringLicenceApplication: function() {
            let app = false;
            if ([constants.ML_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                app = true;
            }
            return app;
        },
        authorisedUserApplication: function() {
            let app = false;
            if ([constants.AU_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                app = true;
            }
            return app;
        },
        authorisedUserMoorings: function() {
            if (this.proposal.authorised_user_moorings.length > 0) {
                return this.proposal.authorised_user_moorings;
            }
        },
        mooringLicenceVessels: function() {
            if (this.proposal.mooring_licence_vessels.length > 0) {
                return this.proposal.mooring_licence_vessels;
            }
        },
        displayAssociatedMoorings: function(){
            return this.authorisedUserApplication && this.authorisedUserMoorings;
        },
        displayAssociatedVessels: function(){
            return this.mooringLicenceApplication && this.mooringLicenceVessels;
        },
        displayBayField: function(){
            return this.authorisedUserApplication;
        },
        displayMooringSiteIdField: function(){
            return this.authorisedUserApplication;
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
        detailsText: function() {
            let details = 'Proposed details';
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
            let title = this.processing_status == 'With Approver' ? 'Grant' : 'Propose grant';
            if (this.proposal && ['wla', 'aaa'].includes(this.proposal.application_type_code)) {
                title = 'Grant';
            }
            return title;
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
            //const res = await this.$http.get(api_endpoints.mooring_bays);
            const res = await this.$http.get(api_endpoints.mooring_bays_lookup);
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
            this.$nextTick(()=>{
                // ensure mooring_on_approval is not null
                if (!this.approval.mooring_on_approval) {
                    this.approval.mooring_on_approval = [];
                }
                // ensure vessel_ownership is not null
                if (!this.approval.vessel_ownership) {
                    this.approval.vessel_ownership = [];
                }
                if (this.authorisedUserApplication && this.authorisedUserMoorings) {
                    for (let moa of this.authorisedUserMoorings) {
                        this.approval.mooring_on_approval.push({"id": moa.id, "checked": moa.checked});
                    }
                }
                if (this.mooringLicenceApplication && this.mooringLicenceVessels) {
                    for (let vo of this.mooringLicenceVessels) {
                        this.approval.vessel_ownership.push({"id": vo.id, "checked": vo.checked});
                    }
                }
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
                            vm.$router.push({ path: '/internal' }); //Navigate to dashboard page after final approval.
                        },(error)=>{
                            vm.errors = true;
                            vm.issuingApproval = false;
                            vm.errorString = helpers.apiVueResourceError(error);
                        });
                }
            });

        },
        addFormValidations: function() {
            let vm = this;
            vm.validation_form = $(vm.form).validate({
                rules: {
                    //start_date:"required",
                    //due_date:"required",
                    //approval_details:"required",
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
       /*
       eventListeners:function () {
            let vm = this;
       },
       */
       constructMooringsTable: function() {
           // update checkboxes
           if (this.authorisedUserMoorings && this.approval.mooring_on_approval && this.approval.mooring_on_approval.length > 0) {
               for (let moa1 of this.approval.mooring_on_approval) {
                   for (let moa2 of this.authorisedUserMoorings) {
                       if (moa1.id === moa2.id) {
                           moa2.checked = moa1.checked;
                       }
                   }
               }
           }
           // now draw table
           if (this.$refs.mooringsTable){
               // Clear table
               this.$refs.mooringsTable.vmDataTable.clear().draw();
               // Construct table
               if (this.authorisedUserMoorings.length > 0){
                   for(let mooring of this.authorisedUserMoorings){
                       this.addMooringToTable(mooring);
                   }
               }
           }
       },
       addMooringToTable: function(mooring) {
           this.$refs.mooringsTable.vmDataTable.row.add(mooring).draw();
       },
       getMooringOnApprovalIdFromEvent(e) {
           let mooringOnApprovalId = e.target.getAttribute("data-mooring-on-approval-id");
           if (!(mooringOnApprovalId)) {
               mooringOnApprovalId = e.target.getElementsByTagName('span')[0].getAttribute('data-mooring-on-approval-id');
           }
           return mooringOnApprovalId;
       },
       mooringsCheckboxClicked: function(e) {
           let vm = this;
           //let apiary_site_id = e.target.getAttribute("data-apiary-site-id");
           let mooringOnApprovalId = this.getMooringOnApprovalIdFromEvent(e);
           //console.log(mooringOnApprovalId);
           let checked_status = e.target.checked;
           //for (let i=0; i<this.apiary_sites_local.length; i++) {
           for (let mooring of this.authorisedUserMoorings) {
               if (mooring.id == mooringOnApprovalId) {
                   //console.log(e.target.checked)
                   mooring.checked = checked_status;
               }
           }
           //this.$emit('authorised_user_moorings_updated', this.authorisedUserMoorings)
           //this.$emit('authorised_user_moorings_updated');
           //this.$refs.component_map.setApiarySiteSelectedStatus(apiary_site_id, checked_status)
           e.stopPropagation();
       },
       constructVesselsTable: function() {
           // update checkboxes
           if (this.mooringLicenceVessels && this.approval.vessel_ownership && this.approval.vessel_ownership.length > 0) {
               for (let vo1 of this.approval.vessel_ownership) {
                   for (let vo2 of this.mooringLicenceVessels) {
                       if (vo1.id === vo2.id) {
                           vo2.checked = vo1.checked;
                       }
                   }
               }
           }
           // now draw table
           if (this.$refs.vesselsTable){
               // Clear table
               this.$refs.vesselsTable.vmDataTable.clear().draw();
               // Construct table
               if (this.mooringLicenceVessels.length > 0){
                   for(let vo of this.mooringLicenceVessels){
                       this.addVesselToTable(vo);
                   }
               }
           }
       },
       addVesselToTable: function(vo) {
           this.$refs.vesselsTable.vmDataTable.row.add(vo).draw();
       },

       getVesselOwnershipIdFromEvent(e) {
           let vesselOwnershipId = e.target.getAttribute("data-vessel-ownership-id");
           if (!(vesselOwnershipId)) {
               vesselOwnershipId = e.target.getElementsByTagName('span')[0].getAttribute('data-vessel-ownership-id');
           }
           return vesselOwnershipId;
       },
       vesselsCheckboxClicked: function(e) {
           let vm = this;
           //let apiary_site_id = e.target.getAttribute("data-apiary-site-id");
           let vesselOwnershipId = this.getVesselOwnershipIdFromEvent(e);
           console.log(vesselOwnershipId);
           let checked_status = e.target.checked;
           //for (let i=0; i<this.apiary_sites_local.length; i++) {
           for (let vo of this.mooringLicenceVessels) {
               if (vo.id == vesselOwnershipId) {
                   console.log(e.target.checked)
                   vo.checked = checked_status;
               }
           }
           //this.$emit('authorised_user_moorings_updated', this.authorisedUserMoorings)
           //this.$emit('mooring_licence_vessels_updated');
           //this.$refs.component_map.setApiarySiteSelectedStatus(apiary_site_id, checked_status)
           e.stopPropagation();
       },

       addEventListeners: function () {
           /*
           $("#" + this.table_id).on("click", "a[data-view-on-map]", this.zoomOnApiarySite)
           $("#" + this.table_id).on("click", "a[data-toggle-availability]", this.toggleAvailability)
           */
           $("#" + this.mooringsTableId).on('click', 'input[type="checkbox"]', this.mooringsCheckboxClicked);
           $("#" + this.vesselsTableId).on('click', 'input[type="checkbox"]', this.vesselsCheckboxClicked);
           /*
           $("#" + this.table_id).on('click', 'a[data-make-vacant]', this.makeVacantClicked)
           $("#" + this.table_id).on('click', 'a[data-contact-licence-holder]', this.contactLicenceHolder)
           $("#" + this.table_id).on('mouseenter', "tr", this.mouseEnter)
           $("#" + this.table_id).on('mouseleave', "tr", this.mouseLeave)
           */
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
                            vessel_details_id: vm.proposal.vessel_details_id,
                            aup_id: vm.proposal.approval_id,
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
            /*
            // AUP reissue
            if (!this.proposal.reissued) {
                this.approval = Object.assign({}, this.proposal.proposed_issuance_approval);
            }
            */
            //this.approval.mooring_bay_id = null;
            this.initialiseMooringLookup();
            this.addEventListeners();
            if (this.authorisedUserApplication) {
                this.constructMooringsTable();
            }
            if (this.mooringLicenceApplication) {
                this.constructVesselsTable();
            }
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
    .site_checkbox {
        text-align: center;
    }
</style>
