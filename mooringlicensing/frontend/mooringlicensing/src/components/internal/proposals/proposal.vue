<template lang="html">
    <div v-if="proposal" class="container" id="internalProposal">
        <div class="row">
            <h3>Proposal: {{ proposal.lodgement_number }}</h3>
            <h4>Proposal Type: {{ proposal.proposal_type.description }}</h4>
            <div v-if="proposal.application_type!='Apiary'">
                <h4>Approval Level: {{ proposal.approval_level }}</h4>
            </div>
            <div class="col-md-3">
                <CommsLogs 
                    :comms_url="comms_url" 
                    :logs_url="logs_url" 
                    :comms_add_url="comms_add_url" 
                    :disable_add_entry="false"
                />

                <Submission v-if="canSeeSubmission"
                    :submitter_first_name="proposal.submitter.first_name"
                    :submitter_last_name="proposal.submitter.last_name"
                    :lodgement_date="proposal.lodgement_date"
                />

                <Workflow
                    :proposal="proposal"
                    :isFinalised="isFinalised"
                    :canAction="canAction"
                    :canAssess="canAssess"
                    :can_user_edit="proposal.can_user_edit"
                    @toggleProposal="toggleProposal"
                    @toggleRequirements="toggleRequirements"
                    @switchStatus="switchStatus"
                    @amendmentRequest="amendmentRequest"
                    @proposedDecline="proposedDecline"
                    @proposedApproval="proposedApproval"
                    @issueProposal="issueProposal"
                    @declineProposal="declineProposal"
                    @assignRequestUser="assignRequestUser"
                />

            </div>

            <div class="col-md-1"></div>

            <div class="col-md-8">
                <!-- Main contents -->
                <template v-if="display_approval_screen">
                    <ApprovalScreen 
                        :proposal="proposal" 
                        @refreshFromResponse="refreshFromResponse"
                    />
                </template>

                <template v-if="canSeeSubmission || (!canSeeSubmission && showingProposal)">
                    <WaitingListApplication
                        v-if="proposal && proposal.application_type_dict.code==='wla'"
                        :proposal="proposal" 
                        :show_application_title="false"
                        :is_external="false" 
                        :is_internal="true" 
                        ref="waiting_list_application"
                        :showElectoralRoll="showElectoralRoll"
                        :readonly="readonly"
                        :submitterId="proposal.submitter.id"
                        :key="computedProposalId"
                    />

                    <AnnualAdmissionApplication
                        v-if="proposal && proposal.application_type_dict.code==='aaa'"
                        :proposal="proposal" 
                        :show_application_title="false"
                        :is_external="false" 
                        :is_internal="true" 
                        ref="annual_admission_application"
                        :showElectoralRoll="showElectoralRoll"
                        :readonly="readonly"
                        :submitterId="proposal.submitter.id"
                    />
                    <AuthorisedUserApplication
                        v-if="proposal && proposal.application_type_dict.code==='aua'"
                        :proposal="proposal" 
                        :show_application_title="false"
                        :is_external="false" 
                        :is_internal="true" 
                        ref="authorised_user_application"
                        :readonly="readonly"
                        :submitterId="proposal.submitter.id"
                    />
                    <MooringLicenceApplication
                        v-if="proposal && proposal.application_type_dict.code==='mla'"
                        :proposal="proposal" 
                        :show_application_title="false"
                        :is_external="false" 
                        :is_internal="true" 
                        ref="mooring_licence_application"
                        :showElectoralRoll="showElectoralRoll"
                        :readonly="readonly"
                        :submitterId="proposal.submitter.id"
                    />
                </template>
<!--
                <template v-if="proposal.processing_status == 'With Approver' || isFinalised">
-->

<!--
                <template v-if="proposal.processing_status == 'With Assessor (Requirements)' || ((proposal.processing_status == 'With Approver' || isFinalised) && showingRequirements)">
-->
                <template v-if="display_requirements">
                    <Requirements 
                        :proposal="proposal" 
                        @refreshRequirements="refreshRequirements"
                    />
                </template>
<!-- Main content copied from the Disturbance
                    <template v-if="canSeeSubmission || (!canSeeSubmission && showingProposal)">
                        <div class="col-md-12">
                            <div class="row">
                                <div class="panel panel-default">
                                    <div class="panel-heading">
                                        <h3 class="panel-title">Applicant
                                            <a class="panelClicker" :href="'#'+detailsBody" data-toggle="collapse"  data-parent="#userInfo" expanded="true" :aria-controls="detailsBody">
                                                <span class="glyphicon glyphicon-chevron-up pull-right "></span>
                                            </a>
                                        </h3>
                                    </div>
                                    <div class="panel-body panel-collapse collapse in" :id="detailsBody">
                                          <form class="form-horizontal">
                                              <div class="form-group">
                                                <label for="" class="col-sm-3 control-label">Name</label>
                                                <div class="col-sm-6">
                                                    <input disabled type="text" class="form-control" name="applicantName" placeholder="" v-model="proposal.applicant.name">
                                                </div>
                                              </div>
                                              <div class="form-group">
                                                <label for="" class="col-sm-3 control-label" >ABN/ACN</label>
                                                <div class="col-sm-6">
                                                    <input disabled type="text" class="form-control" name="applicantABN" placeholder="" v-model="proposal.applicant.abn">
                                                </div>
                                              </div>
                                          </form>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-12">
                            <div class="row">
                                <div class="panel panel-default">
                                    <div class="panel-heading">
                                        <h3 class="panel-title">Address Details
                                            <a class="panelClicker" :href="'#'+addressBody" data-toggle="collapse"  data-parent="#userInfo" expanded="false" :aria-controls="addressBody">
                                                <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                                            </a>
                                        </h3>
                                    </div>
                                    <div class="panel-body panel-collapse collapse" :id="addressBody">
                                          <form class="form-horizontal">
                                              <div class="form-group">
                                                <label for="" class="col-sm-3 control-label">Street</label>
                                                <div class="col-sm-6">
                                                    <input disabled type="text" class="form-control" name="street" placeholder="" v-model="proposal.applicant.address.line1">
                                                </div>
                                              </div>
                                              <div class="form-group">
                                                <label for="" class="col-sm-3 control-label" >Town/Suburb</label>
                                                <div class="col-sm-6">
                                                    <input disabled type="text" class="form-control" name="surburb" placeholder="" v-model="proposal.applicant.address.locality">
                                                </div>
                                              </div>
                                              <div class="form-group">
                                                <label for="" class="col-sm-3 control-label">State</label>
                                                <div class="col-sm-2">
                                                    <input disabled type="text" class="form-control" name="country" placeholder="" v-model="proposal.applicant.address.state">
                                                </div>
                                                <label for="" class="col-sm-2 control-label">Postcode</label>
                                                <div class="col-sm-2">
                                                    <input disabled type="text" class="form-control" name="postcode" placeholder="" v-model="proposal.applicant.address.postcode">
                                                </div>
                                              </div>
                                              <div class="form-group">
                                                <label for="" class="col-sm-3 control-label" >Country</label>
                                                <div class="col-sm-4">
                                                    <input disabled type="text" class="form-control" name="country" v-model="proposal.applicant.address.country"/>
                                                </div>
                                              </div>
                                           </form>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-12">
                            <div class="row">
                                <div class="panel panel-default">
                                    <div class="panel-heading">
                                        <h3 class="panel-title">Contact Details
                                            <a class="panelClicker" :href="'#'+contactsBody" data-toggle="collapse"  data-parent="#userInfo" expanded="false" :aria-controls="contactsBody">
                                                <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                                            </a>
                                        </h3>
                                    </div>
                                    <div class="panel-body panel-collapse collapse" :id="contactsBody">
                                        <table ref="contacts_datatable" :id="contacts_table_id" class="hover table table-striped table-bordered dt-responsive" cellspacing="0" width="100%">
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="col-md-12">
                            <div class="row">
                                <form :action="proposal_form_url" method="post" name="new_proposal" enctype="multipart/form-data">

                                    <div v-if="proposal.application_type=='Apiary'">
                                        <ProposalApiary v-if="proposal" :proposal="proposal" id="proposalStart" :showSections="sectionShow" ref="proposal_apiary" :is_external="false" :is_internal="true" :hasAssessorMode="hasAssessorMode"></ProposalApiary>
                                    </div>
                                    <div v-else>
                                        <ProposalDisturbance form_width="inherit" :withSectionsSelector="false" v-if="proposal" :proposal="proposal"> </ProposalDisturbance>
                                        <NewApply v-if="proposal" :proposal="proposal"></NewApply>
                                    </div>


                                    <div>
                                        <input type="hidden" name="csrfmiddlewaretoken" :value="csrf_token"/>
                                        <input type='hidden' name="schema" :value="JSON.stringify(proposal)" />
                                        <input type='hidden' name="proposal_id" :value="1" />
                                        <div class="row" style="margin-bottom: 50px">
                                          <div class="navbar navbar-fixed-bottom" v-if="hasAssessorMode" style="background-color: #f5f5f5;">
                                            <div class="navbar-inner">
                                                <div v-if="hasAssessorMode" class="container">
                                                  <p class="pull-right">
                                                    <button class="btn btn-primary pull-right" style="margin-top:5px;" @click.prevent="save()">Save Changes</button>
                                                  </p>
                                                </div>
                                            </div>
                                          </div>
                                        </div>

                                    </div>
                                </form>
                            </div>
                        </div>
                    </template>
-->
            </div>
        </div>

        <ProposedApproval 
            v-if="proposal"
            :proposal="proposal" 
            ref="proposed_approval" 
            :processing_status="proposal.processing_status" 
            :proposal_id="proposal.id" 
            :proposal_type='proposal.proposal_type.code' 
            :isApprovalLevelDocument="isApprovalLevelDocument" 
            :submitter_email="proposal.submitter.email" 
            :applicant_email="applicant_email" 
            @refreshFromResponse="refreshFromResponse"
            :key="proposedApprovalKey"
        />
        <ProposedDecline 
            ref="proposed_decline" 
            :processing_status="proposal.processing_status" 
            :proposal="proposal" 
            @refreshFromResponse="refreshFromResponse"
        />
        <AmendmentRequest 
            ref="amendment_request" 
            :proposal="proposal" 
            @refreshFromResponse="refreshFromResponse"
        />
    </div>
</template>

<script>
//import ProposalDisturbance from '../../form.vue'
//import ProposalApiary from '@/components/form_apiary.vue'
//import NewApply from '../../external/proposal_apply_new.vue'
import Vue from 'vue'
import ProposedDecline from '@/components/internal/proposals/proposal_proposed_decline.vue'
import AmendmentRequest from '@/components/internal/proposals/amendment_request.vue'
import datatable from '@vue-utils/datatable.vue'
import Requirements from '@/components/internal/proposals/proposal_requirements.vue'
import ProposedApproval from '@/components/internal/proposals/proposed_issuance.vue'
import ApprovalScreen from '@/components/internal/proposals/proposal_approval.vue'
import CommsLogs from '@common-utils/comms_logs.vue'
import Submission from '@common-utils/submission.vue'
import Workflow from '@common-utils/workflow.vue'
import ResponsiveDatatablesHelper from "@/utils/responsive_datatable_helper.js"
import { api_endpoints, helpers, constants } from '@/utils/hooks'
import WaitingListApplication from '@/components/form_wla.vue';
import AnnualAdmissionApplication from '@/components/form_aaa.vue';
import AuthorisedUserApplication from '@/components/form_aua.vue';
import MooringLicenceApplication from '@/components/form_mla.vue';

export default {
    name: 'InternalProposal',
    data: function() {
        let vm = this;
        return {
            detailsBody: 'detailsBody'+vm._uid,
            addressBody: 'addressBody'+vm._uid,
            contactsBody: 'contactsBody'+vm._uid,
            siteLocations: 'siteLocations'+vm._uid,
            defaultKey: "aho",
            "proposal": null,
            "original_proposal": null,
            "loading": [],
            //selected_referral: '',
            //referral_text: '',
            approver_comment: '',
            form: null,
            members: [],
            department_users : [],
            contacts_table_initialised: false,
            initialisedSelects: false,
            showingProposal:false,
            showingRequirements:false,
            hasAmendmentRequest: false,
            requirementsComplete:true,
            state_options: ['requirements','processing'],
            contacts_table_id: vm._uid+'contacts-table',
            contacts_options:{
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                ajax: {
                    "url": vm.contactsURL,
                    "dataSrc": ''
                },
                columns: [
                    {
                        title: 'Name',
                        mRender:function (data,type,full) {
                            return full.first_name + " " + full.last_name;
                        }
                    },
                    {
                        title: 'Phone',
                        data:'phone_number'
                    },
                    {
                        title: 'Mobile',
                        data:'mobile_number'
                    },
                    {
                        title: 'Fax',
                        data:'fax_number'
                    },
                    {
                        title: 'Email',
                        data:'email'
                    },
                  ],
                  processing: true
            },
            contacts_table: null,
            DATE_TIME_FORMAT: 'DD/MM/YYYY HH:mm:ss',
            //comms_url: helpers.add_endpoint_json(api_endpoints.proposals, vm.$route.params.proposal_id + '/comms_log'),
            //comms_add_url: helpers.add_endpoint_json(api_endpoints.proposals, vm.$route.params.proposal_id + '/add_comms_log'),
            //logs_url: helpers.add_endpoint_json(api_endpoints.proposals, vm.$route.params.proposal_id + '/action_log'),
            comms_url: helpers.add_endpoint_json(api_endpoints.proposal, vm.$route.params.proposal_id + '/comms_log'),
            comms_add_url: helpers.add_endpoint_json(api_endpoints.proposal, vm.$route.params.proposal_id + '/add_comms_log'),
            logs_url: helpers.add_endpoint_json(api_endpoints.proposal, vm.$route.params.proposal_id + '/action_log'),
            panelClickersInitialised: false,
            //sendingReferral: false,
            uuid: 0,
        }
    },
    components: {
        //ProposalDisturbance,
        //ProposalApiary,
        datatable,
        ProposedDecline,
        AmendmentRequest,
        Requirements,
        ProposedApproval,
        ApprovalScreen,
        CommsLogs,
        Submission,
        Workflow,
        //MoreReferrals,
        //NewApply,
        //MapLocations,
        WaitingListApplication,
        AnnualAdmissionApplication,
        AuthorisedUserApplication,
        MooringLicenceApplication,
    },
    props: {
        proposalId: {
            type: Number,
        },
    },
    watch: {

    },
    computed: {
        proposedApprovalKey: function() {
            return "proposed_approval_" + this.uuid;
        },
        computedProposalId: function(){
            if (this.proposal) {
                return this.proposal.id;
            }
        },
        display_approval_screen: function(){
            let ret_val = 
                this.proposal.processing_status == constants.WITH_APPROVER || 
                this.proposal.processing_status == constants.AWAITING_STICKER ||
                this.proposal.processing_status == constants.AWAITING_PAYMENT ||
                this.isFinalised
            return ret_val
        },
        display_requirements: function(){
            let ret_val = 
                this.proposal.processing_status == constants.WITH_ASSESSOR_REQUIREMENTS || 
                ((this.proposal.processing_status == constants.WITH_APPROVER || this.isFinalised) && this.showingRequirements)
            return ret_val
        },
        showElectoralRoll: function(){
            // TODO: implement
            return true
        },
        readonly: function() {
            // TODO: implement
            return true
        },
        contactsURL: function(){
            return this.proposal!= null ? helpers.add_endpoint_json(api_endpoints.organisations, this.proposal.applicant.id + '/contacts') : '';
        },
        isLoading: function() {
          return this.loading.length > 0
        },
        csrf_token: function() {
          return helpers.getCookie('csrftoken')
        },
        proposal_form_url: function() {
          return (this.proposal) ? `/api/proposal/${this.proposal.id}/assessor_save.json` : '';
        },
        isFinalised: function(){
            return this.proposal.processing_status == 'Declined' || this.proposal.processing_status == 'Approved';
        },
        canAssess: function(){
            return true  // TODO: Implement correctly.  May not be needed though

            //return this.proposal && this.proposal.assessor_mode.assessor_can_assess ? true : false;
        },
        hasAssessorMode:function(){
            return this.proposal && this.proposal.assessor_mode.has_assessor_mode ? true : false;
        },
        canAction: function(){

            return true  // TODO: implement this.  This is just temporary solution

            if (this.proposal.processing_status == 'With Approver'){
                return this.proposal && (this.proposal.processing_status == 'With Approver' || this.proposal.processing_status == 'With Assessor' || this.proposal.processing_status == 'With Assessor (Requirements)') && !this.isFinalised && !this.proposal.can_user_edit && (this.proposal.current_assessor.id == this.proposal.assigned_approver || this.proposal.assigned_approver == null ) && this.proposal.assessor_mode.assessor_can_assess? true : false;
            }
            else{
                return this.proposal && (this.proposal.processing_status == 'With Approver' || this.proposal.processing_status == 'With Assessor' || this.proposal.processing_status == 'With Assessor (Requirements)') && !this.isFinalised && !this.proposal.can_user_edit && (this.proposal.current_assessor.id == this.proposal.assigned_officer || this.proposal.assigned_officer == null ) && this.proposal.assessor_mode.assessor_can_assess? true : false;
            }
        },
        canLimitedAction: function(){

            return false  // TODO: implement this.  This is just temporary solution

            if (this.proposal.processing_status == 'With Approver'){
                return 
                    this.proposal 
                    && (
                        this.proposal.processing_status == 'With Assessor' || 
                        //this.proposal.processing_status == 'With Referral' || 
                        this.proposal.processing_status == 'With Assessor (Requirements)'
                    ) 
                    && !this.isFinalised && !this.proposal.can_user_edit 
                    && (
                        this.proposal.current_assessor.id == this.proposal.assigned_approver || 
                        this.proposal.assigned_approver == null 
                    ) && this.proposal.assessor_mode.assessor_can_assess? true : false;
            }
            else{
                return 
                    this.proposal 
                    && (
                        this.proposal.processing_status == 'With Assessor' || 
                        //this.proposal.processing_status == 'With Referral' || 
                        this.proposal.processing_status == 'With Assessor (Requirements)'
                    ) && !this.isFinalised && !this.proposal.can_user_edit 
                    && (
                        this.proposal.current_assessor.id == this.proposal.assigned_officer || 
                        this.proposal.assigned_officer == null 
                    ) && this.proposal.assessor_mode.assessor_can_assess? true : false;
            }
        },
        canSeeSubmission: function(){
            return this.proposal && (this.proposal.processing_status != 'With Assessor (Requirements)' && this.proposal.processing_status != 'With Approver' && !this.isFinalised)
        },
        isApprovalLevelDocument: function(){
            return this.proposal && this.proposal.processing_status == 'With Approver' && this.proposal.approval_level != null && this.proposal.approval_level_document == null ? true : false;
        },
        applicant_email:function(){
            return this.proposal && this.proposal.applicant.email ? this.proposal.applicant.email : '';
        },
    },
    methods: {
        locationUpdated: function(){
            console.log('in locationUpdated()');
        },
        checkAssessorData: function(){
            //check assessor boxes and clear value of hidden assessor boxes so it won't get printed on approval pdf.

            //select all fields including hidden fields
            //console.log("here");
            var all_fields = $('input[type=text]:required, textarea:required, input[type=checkbox]:required, input[type=radio]:required, input[type=file]:required, select:required')

            all_fields.each(function() {
                var ele=null;
                //check the fields which has assessor boxes.
                ele = $("[name="+this.name+"-Assessor]");
                if(ele.length>0){
                    var visiblity=$("[name="+this.name+"-Assessor]").is(':visible')
                    if(!visiblity){
                        if(ele[0].value!=''){
                            //console.log(visiblity, ele[0].name, ele[0].value)
                            ele[0].value=''
                        }
                    }
                }
            });
        },
        initialiseOrgContactTable: function(){
            let vm = this;
            if (vm.proposal && !vm.contacts_table_initialised){
                vm.contacts_options.ajax.url = helpers.add_endpoint_json(api_endpoints.organisations,vm.proposal.applicant.id+'/contacts');
                vm.contacts_table = $('#'+vm.contacts_table_id).DataTable(vm.contacts_options);
                vm.contacts_table_initialised = true;
            }
        },
        commaToNewline(s){
            return s.replace(/[,;]/g, '\n');
        },
        proposedDecline: function(){
            console.log('in proposedDecline')
            this.save_wo();
            this.$refs.proposed_decline.decline = this.proposal.proposaldeclineddetails != null ? helpers.copyObject(this.proposal.proposaldeclineddetails): {};
            this.$refs.proposed_decline.isModalOpen = true;
        },
        proposedApproval: function(){
            console.log('proposedApproval')
            this.$refs.proposed_approval.approval = this.proposal.proposed_issuance_approval != null ? helpers.copyObject(this.proposal.proposed_issuance_approval) : {};
            if(this.proposal.proposed_issuance_approval == null){
                //var test_approval={
                //    'cc_email': this.proposal.referral_email_list
                //};
                //this.$refs.proposed_approval.approval=helpers.copyObject(test_approval);
                // this.$refs.proposed_approval.$refs.bcc_email=this.proposal.referral_email_list;
            }
            //this.$refs.proposed_approval.submitter_email=helpers.copyObject(this.proposal.submitter_email);
            // if(this.proposal.applicant.email){
            //     this.$refs.proposed_approval.applicant_email=helpers.copyObject(this.proposal.applicant.email);
            // }
            this.uuid++;
            this.$nextTick(() => {
                this.$refs.proposed_approval.isModalOpen = true;
            });
        },
        issueProposal:function(){
            console.log('in issueProposal')
            //this.$refs.proposed_approval.approval = helpers.copyObject(this.proposal.proposed_issuance_approval);

            //save approval level comment before opening 'issue approval' modal
            if(this.proposal && this.proposal.processing_status == 'With Approver' && this.proposal.approval_level != null && this.proposal.approval_level_document == null){
                if (this.proposal.approval_level_comment!=''){
                    let vm = this;
                    let data = new FormData();
                    data.append('approval_level_comment', vm.proposal.approval_level_comment)
                    //vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposals,vm.proposal.id+'/approval_level_comment'),data,{
                    console.log('3')
                    vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal,vm.proposal.id+'/approval_level_comment'), data, {emulateJSON:true}).then(
                        res => {
                            vm.proposal = res.body;
                            vm.refreshFromResponse(res);
                        }, err => {
                            console.log(err);
                        }
                    );
                }
            }
            if(this.isApprovalLevelDocument && this.proposal.approval_level_comment==''){
                swal(
                    'Error',
                    'Please add Approval document or comments before final approval',
                    'error'
                )
            } else {
                this.$refs.proposed_approval.approval = this.proposal.proposed_issuance_approval != null ? helpers.copyObject(this.proposal.proposed_issuance_approval) : {};
                this.$refs.proposed_approval.state = 'final_approval';
                this.$refs.proposed_approval.isApprovalLevelDocument = this.isApprovalLevelDocument;
                if(this.proposal.proposed_issuance_approval != null && this.proposal.proposed_issuance_approval.start_date!=null){
                    var start_date=new Date();
                    start_date=moment(this.proposal.proposed_issuance_approval.start_date, 'DD/MM/YYYY')
                    $(this.$refs.proposed_approval.$refs.start_date).data('DateTimePicker').date(start_date);
                }
                if(this.proposal.proposed_issuance_approval != null && this.proposal.proposed_issuance_approval.expiry_date!=null){
                    var expiry_date=new Date();
                    expiry_date=moment(this.proposal.proposed_issuance_approval.expiry_date, 'DD/MM/YYYY')
                    $(this.$refs.proposed_approval.$refs.due_date).data('DateTimePicker').date(expiry_date);
                }
                //this.$refs.proposed_approval.submitter_email=helpers.copyObject(this.proposal.submitter_email);
                // if(this.proposal.applicant.email){
                //     this.$refs.proposed_approval.applicant_email=helpers.copyObject(this.proposal.applicant.email);
                // }
                this.$refs.proposed_approval.isModalOpen = true;
            }

        },
        declineProposal:function(){
            console.log('in declineProposal')
            this.$refs.proposed_decline.decline = this.proposal.proposaldeclineddetails != null ? helpers.copyObject(this.proposal.proposaldeclineddetails): {};
            this.$refs.proposed_decline.isModalOpen = true;
        },
        amendmentRequest: function(){
            this.save_wo();
            let values = '';
            $('.deficiency').each((i,d) => {
                values +=  $(d).val() != '' ? `Question - ${$(d).data('question')}\nDeficiency - ${$(d).val()}\n\n`: '';
            });
            //this.deficientFields();
            this.$refs.amendment_request.amendment.text = values;

            this.$refs.amendment_request.isModalOpen = true;
        },
        highlight_deficient_fields: function(deficient_fields){
            let vm = this;
            for (var deficient_field of deficient_fields) {
                $("#" + "id_"+deficient_field).css("color", 'red');
            }
        },
        deficientFields(){
            let vm=this;
            let deficient_fields=[]
            $('.deficiency').each((i,d) => {
                if($(d).val() != ''){
                    var name=$(d)[0].name
                    var tmp=name.replace("-comment-field","")
                    deficient_fields.push(tmp);
                    //console.log('data', $("#"+"id_" + tmp))
                }
            });
            //console.log('deficient fields', deficient_fields);
            vm.highlight_deficient_fields(deficient_fields);
        },
        save: function(e) {
            let vm = this;
            vm.checkAssessorData();
            let formData = new FormData(vm.form);
            vm.$http.post(vm.proposal_form_url,formData).then(res=>{
                swal(
                  'Saved',
                  'Your proposal has been saved',
                  'success'
                )
            },err=>{ });
        },
        save_wo: function() {
            let vm = this;
            vm.checkAssessorData();
            let formData = new FormData(vm.form);
            vm.$http.post(vm.proposal_form_url,formData).then(res=>{


            },err=>{
            });
        },
        toggleProposal:function(value){
            this.showingProposal = value
        },
        toggleRequirements:function(value){
            this.showingRequirements = value
        },
        updateAssignedOfficerSelect:function(){
            console.log('updateAssignedOfficerSelect')
            let vm = this;
            if (vm.proposal.processing_status == 'With Approver'){
                $(vm.$refs.assigned_officer).val(vm.proposal.assigned_approver);
                $(vm.$refs.assigned_officer).trigger('change');
            }
            else{
                $(vm.$refs.assigned_officer).val(vm.proposal.assigned_officer);
                $(vm.$refs.assigned_officer).trigger('change');
            }
        },
        assignRequestUser: function(){
            let vm = this;
            vm.$http.get(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/assign_request_user')))
            .then((response) => {
                vm.proposal = response.body;
                vm.original_proposal = helpers.copyObject(response.body);
                //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                vm.updateAssignedOfficerSelect();
            }, (error) => {
                vm.proposal = helpers.copyObject(vm.original_proposal)
                //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                vm.updateAssignedOfficerSelect();
                swal(
                    'Proposal Error',
                    helpers.apiVueResourceError(error),
                    'error'
                )
            });
        },
        refreshFromResponse:function(response){
            console.log('in refreshFromResponse')
            console.log('response')
            console.log(response)
            let vm = this;
            vm.original_proposal = helpers.copyObject(response.body);
            vm.proposal = helpers.copyObject(response.body);
            //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
            vm.$nextTick(() => {
                vm.initialiseAssignedOfficerSelect(true);
                vm.updateAssignedOfficerSelect();
            });
        },
        refreshRequirements: function(bool){
              let vm=this;
              //vm.proposal.requirements_completed=bool;
              //console.log('here', bool);
              vm.requirementsComplete = bool;
        },
        assignTo: function(){
            let vm = this;
            let unassign = true;
            let data = {};
            if (vm.processing_status == 'With Approver'){
                unassign = vm.proposal.assigned_approver != null && vm.proposal.assigned_approver != 'undefined' ? false: true;
                data = {'assessor_id': vm.proposal.assigned_approver};
            }
            else{
                unassign = vm.proposal.assigned_officer != null && vm.proposal.assigned_officer != 'undefined' ? false: true;
                data = {'assessor_id': vm.proposal.assigned_officer};
            }
            if (!unassign){
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id+'/assign_to')),JSON.stringify(data),{
                    emulateJSON:true
                }).then((response) => {
                    vm.proposal = response.body;
                    vm.original_proposal = helpers.copyObject(response.body);
                    //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                    vm.updateAssignedOfficerSelect();
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
                    //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                    vm.updateAssignedOfficerSelect();
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(error),
                        'error'
                    )
                });
            }
            else{
                vm.$http.get(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id+'/unassign')))
                .then((response) => {
                    vm.proposal = response.body;
                    vm.original_proposal = helpers.copyObject(response.body);
                    //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                    vm.updateAssignedOfficerSelect();
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
                    //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                    vm.updateAssignedOfficerSelect();
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(error),
                        'error'
                    )
                });
            }
        },
        switchStatus: function(status){
            let vm = this;
            //vm.save_wo();
            //let vm = this;
            if(vm.proposal.processing_status == 'With Assessor' && status == 'with_assessor_requirements'){
                console.log('0')
                vm.checkAssessorData();
                let formData = new FormData(vm.form);
                console.log(vm.proposal_form_url)
                vm.$http.post(vm.proposal_form_url, formData).then(res=>{ //save Proposal before changing status so that unsaved assessor data is saved.
                    let data = {'status': status, 'approver_comment': vm.approver_comment}
                    vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/switch_status')), JSON.stringify(data),{
                        emulateJSON:true,
                    })
                    .then((response) => {
                        console.log('0 response.body: ')
                        console.log(response.body)
                        vm.proposal = response.body;
                        vm.original_proposal = helpers.copyObject(response.body);
                        //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                        vm.approver_comment='';
                        vm.$nextTick(() => {
                            vm.initialiseAssignedOfficerSelect(true);
                            vm.updateAssignedOfficerSelect();
                        });
                    }, (error) => {
                        vm.proposal = helpers.copyObject(vm.original_proposal)
                        //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                        swal(
                            'Proposal Error',
                            helpers.apiVueResourceError(error),
                            'error'
                        )
                    })
                }, err=>{

                });
            }

            //if approver is pushing back proposal to Assessor then navigate the approver back to dashboard page
            if(vm.proposal.processing_status == 'With Approver' && (status == 'with_assessor_requirements' || status=='with_assessor')) {
                let data = {'status': status, 'approver_comment': vm.approver_comment}

                console.log('1')
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/switch_status')),JSON.stringify(data),{
                    emulateJSON:true,
                })
                .then((response) => {
                    vm.proposal = response.body;
                    vm.original_proposal = helpers.copyObject(response.body);
                    //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                    vm.approver_comment='';
                    vm.$nextTick(() => {
                        vm.initialiseAssignedOfficerSelect(true);
                        vm.updateAssignedOfficerSelect();
                    });
                    vm.$router.push({ path: '/internal' });
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
                    //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(error),
                        'error'
                    )
                });
            } else {
                let data = {'status': status, 'approver_comment': vm.approver_comment}

                console.log('2')
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/switch_status')), JSON.stringify(data),{
                    emulateJSON:true,
                })
                .then((response) => {
                    console.log('2 response.body:')
                    console.log(response.body)

                    vm.proposal = response.body;
                    vm.original_proposal = helpers.copyObject(response.body);
                    //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                    vm.approver_comment='';
                    vm.$nextTick(() => {
                        vm.initialiseAssignedOfficerSelect(true);
                        vm.updateAssignedOfficerSelect();
                    });
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
                    //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(error),
                        'error'
                    )
                });
            }
        },
        fetchDeparmentUsers: function(){
            let vm = this;
            vm.loading.push('Loading Department Users');
            vm.$http.get(api_endpoints.department_users).then((response) => {
                vm.department_users = response.body
                vm.loading.splice('Loading Department Users',1);
            },(error) => {
                console.log(error);
                vm.loading.splice('Loading Department Users',1);
            })
        },
        initialiseAssignedOfficerSelect:function(reinit=false){
            console.log('initialiseAssignedOfficerSelect')
            let vm = this;
            if (reinit){
                $(vm.$refs.assigned_officer).data('select2') ? $(vm.$refs.assigned_officer).select2('destroy'): '';
            }
            // Assigned officer select
            $(vm.$refs.assigned_officer).select2({
                "theme": "bootstrap",
                allowClear: true,
                placeholder:"Select Officer"
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                if (vm.proposal.processing_status == 'With Approver'){
                    vm.proposal.assigned_approver = selected.val();
                }
                else{
                    vm.proposal.assigned_officer = selected.val();
                }
                vm.assignTo();
            }).on("select2:unselecting", function(e) {
                var self = $(this);
                setTimeout(() => {
                    self.select2('close');
                }, 0);
            }).on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                if (vm.proposal.processing_status == 'With Approver'){
                    vm.proposal.assigned_approver = null;
                }
                else{
                    vm.proposal.assigned_officer = null;
                }
                vm.assignTo();
            });
        },
        initialiseSelects: function(){
            let vm = this;
            if (!vm.initialisedSelects){
                $(vm.$refs.department_users).select2({
                    "theme": "bootstrap",
                    allowClear: true,
                    //placeholder:"Select Referral"
                }).
                on("select2:select",function (e) {
                    var selected = $(e.currentTarget);
                    //vm.selected_referral = selected.val();
                }).
                on("select2:unselect",function (e) {
                    var selected = $(e.currentTarget);
                    //vm.selected_referral = ''
                });
                vm.initialiseAssignedOfficerSelect();
                vm.initialisedSelects = true;
            }
        },
    },
    mounted: function() {
        let vm = this;
        vm.fetchDeparmentUsers();

    },
    updated: function(){
        let vm = this;
        if (!vm.panelClickersInitialised){
            $('.panelClicker[data-toggle="collapse"]').on('click', function () {
                var chev = $(this).children()[0];
                window.setTimeout(function () {
                    $(chev).toggleClass("glyphicon-chevron-down glyphicon-chevron-up");
                },100);
            });
            vm.panelClickersInitialised = true;
        }
        this.$nextTick(() => {
            vm.initialiseOrgContactTable();
            vm.initialiseSelects();
            vm.form = document.forms.new_proposal;
            if(vm.hasAmendmentRequest){
                vm.deficientFields();
            }
        });
    },
    created: function() {
        Vue.http.get(`/api/proposal/${this.$route.params.proposal_id}/internal_proposal.json`).then(res => {
            console.log('res.body: ')
            console.log(res.body)
            this.proposal = res.body;
            this.original_proposal = helpers.copyObject(res.body);
            //this.proposal.applicant.address = this.proposal.applicant.address != null ? this.proposal.applicant.address : {};
            this.hasAmendmentRequest=this.proposal.hasAmendmentRequest;
        },
        err => {
          console.log(err);
        });
    },
    /*
    beforeRouteEnter: function(to, from, next) {
          Vue.http.get(`/api/proposal/${to.params.proposal_id}/internal_proposal.json`).then(res => {
              next(vm => {
                vm.proposal = res.body;
                vm.original_proposal = helpers.copyObject(res.body);
                vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                vm.hasAmendmentRequest=vm.proposal.hasAmendmentRequest;
              });
            },
            err => {
              console.log(err);
            });
    },
    */
    beforeRouteUpdate: function(to, from, next) {
        console.log("beforeRouteUpdate")
          Vue.http.get(`/api/proposal/${to.params.proposal_id}.json`).then(res => {
              next(vm => {
                vm.proposal = res.body;
                vm.original_proposal = helpers.copyObject(res.body);
                //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
              });
            },
            err => {
              console.log(err);
            });
    }
}
</script>
<style scoped>

</style>
