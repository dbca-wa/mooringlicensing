<template lang="html">
    <div v-if="proposal" class="container" id="internalProposal">
        <alert v-if="proposal.affected_by_fee_constructor_change" type="warning">{{proposal.affected_by_fee_constructor_change}}</alert>
        <div class="row">
            <h3 v-if="proposal.migrated">Application: {{ proposal.lodgement_number }} (Migrated)</h3>
            <h3 v-else>Application: {{ proposal.lodgement_number }}</h3>
            <h4>Application Type: {{ proposal.proposal_type.description }}</h4>

            <div class="col-md-3">
                <CommsLogs
                    :comms_url="comms_url"
                    :logs_url="logs_url"
                    :comms_add_url="comms_add_url"
                    :disable_add_entry="false"
                />

                <Submission v-if="canSeeSubmission && proposal.submitter.legal_first_name"
                    :submitter_first_name="proposal.submitter.legal_first_name"
                    :submitter_last_name="proposal.submitter.legal_last_name"
                    :lodgement_date="proposal.lodgement_date"
                />
                <Submission v-else-if="canSeeSubmission"
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
                    @bypassEndorsement="bypassEndorsement"
                    @requestEndorsement="requestEndorsement"
                    @backToAssessorRequirements="backToAssessorRequirements"
                    @amendmentRequest="amendmentRequest"
                    @proposedDecline="proposedDecline"
                    @proposedApproval="proposedApproval"
                    @issueProposal="issueProposal"
                    @declineProposal="declineProposal"
                    @assignRequestUser="assignRequestUser"
                    @assignTo="assignTo"
                />

            </div>

            <div class="col-md-1"></div>

            <div class="col-md-8">
                <!-- Main contents -->
                <template v-if="display_approval_screen">
                    <ApprovalScreen
                        :proposal="proposal"
                        @refreshFromResponse="refreshFromResponse"
                        ref="approval_screen"
                        :mooringBays="mooringBays"
                        :siteLicenseeMooring="siteLicenseeMooring"
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
                        :key="computedProposalId"
                        @profile-fetched="populateProfile"
                        @updateSubmitText="updateSubmitText"
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
                        @profile-fetched="populateProfile"
                        @updateSubmitText="updateSubmitText"
                    />
                    <AuthorisedUserApplication
                        v-if="proposal && proposal.application_type_dict.code==='aua'"
                        :proposal="proposal"
                        :show_application_title="false"
                        :is_external="false"
                        :is_internal="true"
                        ref="authorised_user_application"
                        :readonly="readonly"
                        @profile-fetched="populateProfile"
                        @updateSubmitText="updateSubmitText"
                        @updateProposal="updateProposal"
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
                        @profile-fetched="populateProfile"
                        @updateSubmitText="updateSubmitText"
                    />
                </template>
                <template v-if="display_requirements">
                    <Requirements
                        :proposal="proposal"
                        @refreshRequirements="refreshRequirements"
                    />
                </template>
            </div>
        </div>

        <ProposedApproval
            v-if="proposal"
            :proposal="proposal"
            ref="proposed_approval"
            :processing_status="proposal.processing_status"
            :proposal_id="proposal.id"
            :proposal_type='proposal.proposal_type.code'
            :submitter_email="proposal.submitter.email"
            :applicant_email="applicant_email"
            @refreshFromResponse="refreshFromResponse"
            :key="proposedApprovalKey"
            :mooringBays="mooringBays"
            :siteLicenseeMooring="siteLicenseeMooring"
            :readonly="readonly"
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
        <BackToAssessor
            ref="back_to_assessor"
            :proposal="proposal"
        />

        <div class="row" style="margin-bottom: 50px">
            <div  class="container">
                <div class="row" style="margin-bottom: 50px">
                    <div class="navbar navbar-fixed-bottom"  style="background-color: #f5f5f5;">
                        <div class="navbar-inner">
                            <div v-if="!readonly" class="container">
                                <p class="pull-right" style="margin-top:5px">

                                    <input v-if="proposal.can_bypass_auto_approval" type="checkbox" v-model="bypass_auto_approval" id="noAutoApprove" />
                                    <label v-if="proposal.can_bypass_auto_approval" for="noEmails">
                                        &nbsp;Prevent this application from being auto approved &nbsp;
                                    </label>

                                    <input type="checkbox" v-model="proposal.no_email_notifications" id="noEmails" />
                                    <label for="noEmails">
                                        &nbsp;Do not send email notifications for this application &nbsp;
                                    </label>
                                    <button v-if="savingProposal" type="button" class="btn btn-primary" disabled>
                                        Save Proposal&nbsp;<i class="fa fa-circle-o-notch fa-spin fa-fw"></i>
                                    </button>
                                    <input v-else type="button" @click.prevent="save" 
                                        class="btn btn-primary" value="Save Proposal"/>

                                    <button v-if="submittingProposal" type="button" class="btn btn-primary" disabled>
                                        {{submitText}}&nbsp;<i class="fa fa-circle-o-notch fa-spin fa-fw"></i>
                                    </button>
                                    <input v-else-if="submittable" type="button" @click.prevent="submit" 
                                        class="btn btn-primary" :value="submitText" />
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import Vue from 'vue'
import ProposedDecline from '@/components/internal/proposals/proposal_proposed_decline.vue'
import AmendmentRequest from '@/components/internal/proposals/amendment_request.vue'
import BackToAssessor from '@/components/internal/proposals/back_to_assessor.vue'
import datatable from '@vue-utils/datatable.vue'
import Requirements from '@/components/internal/proposals/proposal_requirements.vue'
import ProposedApproval from '@/components/internal/proposals/proposed_issuance.vue'
import ApprovalScreen from '@/components/internal/proposals/proposal_approval.vue'
import CommsLogs from '@common-utils/comms_logs.vue'
import Submission from '@common-utils/submission.vue'
import Workflow from '@common-utils/workflow.vue'
import { api_endpoints, helpers, constants } from '@/utils/hooks'
import WaitingListApplication from '@/components/form_wla.vue';
import AnnualAdmissionApplication from '@/components/form_aaa.vue';
import AuthorisedUserApplication from '@/components/form_aua.vue';
import MooringLicenceApplication from '@/components/form_mla.vue';
import alert from '@vue-utils/alert.vue'

export default {
    name: 'InternalProposal',
    data: function() {
        let vm = this;
        return {
            bypass_auto_approval: false,
            profile: {},
            savingProposal: false,
            submittingProposal: false,
            submitText: "Submit",
            paySubmitting:false,
            detailsBody: 'detailsBody'+vm._uid,
            addressBody: 'addressBody'+vm._uid,
            contactsBody: 'contactsBody'+vm._uid,
            siteLocations: 'siteLocations'+vm._uid,
            defaultKey: "aho",
            "proposal": null,
            "original_proposal": null,
            "loading": [],
            approver_comment: '',
            form: null,
            members: [],
            contacts_table_initialised: false,
            initialisedSelects: false,
            showingProposal:false,
            showingRequirements:false,
            showingProposal:true,
            showingRequirements:true,
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
            comms_url: helpers.add_endpoint_json(api_endpoints.proposal, vm.$route.params.proposal_id + '/comms_log'),
            comms_add_url: helpers.add_endpoint_json(api_endpoints.proposal, vm.$route.params.proposal_id + '/add_comms_log'),
            logs_url: helpers.add_endpoint_json(api_endpoints.proposal, vm.$route.params.proposal_id + '/action_log'),
            panelClickersInitialised: false,
            uuid: 0,
            mooringBays: [],
            siteLicenseeMooring: {},
            submitRes: null,
        }
    },
    components: {
        datatable,
        ProposedDecline,
        AmendmentRequest,
        BackToAssessor,
        Requirements,
        ProposedApproval,
        ApprovalScreen,
        CommsLogs,
        Submission,
        Workflow,
        WaitingListApplication,
        AnnualAdmissionApplication,
        AuthorisedUserApplication,
        MooringLicenceApplication,
        alert,
    },
    props: {
        proposalId: {
            type: Number,
        },
    },
    watch: {
        proposal: function(){
            console.log('%cproposal has been changed.', 'color: #33f;')
            if (this.proposal){
                this.fetchSiteLicenseeMooring()
            }
        }
    },
    computed: {
        confirmation_url: function() {
            return (this.proposal) ? `/confirmation/${this.proposal.id}/` : '';
        },
        application_fee_url: function() {
            return (this.proposal) ? `/application_fee/${this.proposal.id}/` : '';
        },
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
        proposal_form_url: function() {
            return (this.proposal) ? `/api/proposal/${this.proposal.id}/internal_save.json` : '';
        },
        showElectoralRoll: function() {
            let show = false;
            if (this.proposal && ['wla', 'mla'].includes(this.proposal.application_type_code)) {
                show = true;
            }
            return show;
        },
        readonly: function() {
            if (this.proposal.assessor_mode.has_assessor_mode) {
                return false
            }
            return true
        },
        submittable: function() {
            if ((this.proposal.assessor_mode.has_assessor_mode) &&
                (this.proposal.processing_status == 'Draft' || 
                this.proposal.processing_status == 'Awaiting Payment')) {
                return true
            }
            return false
        },
        isLoading: function() {
          return this.loading.length > 0
        },
        csrf_token: function() {
          return helpers.getCookie('csrftoken')
        },
        isFinalised: function(){
            return this.proposal.processing_status == 'Declined' || this.proposal.processing_status == 'Approved';
        },
        canAssess: function(){
            return this.proposal.assessor_mode.assessor_can_assess;
        },
        hasAssessorMode:function(){
            return this.proposal && this.proposal.assessor_mode.has_assessor_mode ? true : false;
        },
        hasApproverMode:function(){
            return this.proposal && this.proposal.assessor_mode.has_assessor_mode ? true : false;
        },
        canAction: function(){

            if (this.proposal.processing_status == 'With Approver'){
                return this.proposal && 
                (
                    this.proposal.processing_status == 'With Approver' || 
                    this.proposal.processing_status == 'With Assessor' || 
                    this.proposal.processing_status == 'With Assessor (Requirements)') && 
                    !this.isFinalised && 
                    !this.proposal.can_user_edit && 
                    (this.proposal.current_assessor.id == this.proposal.assigned_approver || 
                    this.proposal.assigned_approver == null
                )
                && this.proposal.assessor_mode.assessor_can_assess? true : false;
            }
            else{
                return this.proposal && 
                (
                    this.proposal.processing_status == 'Awaiting Endorsement' ||
                    this.proposal.processing_status == 'With Approver' || 
                    this.proposal.processing_status == 'With Assessor' || 
                    this.proposal.processing_status == 'With Assessor (Requirements)') && 
                    !this.isFinalised && !this.proposal.can_user_edit && 
                    (
                        this.proposal.current_assessor.id == this.proposal.assigned_officer || 
                        this.proposal.assigned_officer == null
                    ) && 
                    this.proposal.assessor_mode.assessor_can_assess? true : false;
            }
        },
        canSeeSubmission: function(){
            return this.proposal && (this.proposal.processing_status != 'With Assessor (Requirements)' && this.proposal.processing_status != 'With Approver' && !this.isFinalised)
        },
        applicant_email:function(){
            return this.proposal && this.proposal.applicant && this.proposal.applicant.email ? this.proposal.applicant.email : '';
        },
        proposal_submit_url: function() {
            return (this.proposal) ? `/api/proposal/${this.proposal.id}/submit.json` : '';
        },
    },
    methods: {
        updateProposal: function(data) {
            console.log("updateProposal")
            this.proposal = data;
        },
        buildPayload: function() {

            let payload = {
                proposal: {},
                vessel: {},
                profile: {},
                bypass_auto_approval: this.bypass_auto_approval,
            }

            // WLA
            if (this.$refs.waiting_list_application) {
                if (this.$refs.waiting_list_application.$refs.vessels) {
                    payload.vessel = Object.assign({}, this.$refs.waiting_list_application.$refs.vessels.vessel);
                    payload.proposal.temporary_document_collection_id = this.$refs.waiting_list_application.$refs.vessels.temporary_document_collection_id;
                    payload.proposal.keep_existing_vessel = this.$refs.waiting_list_application.keepCurrentVessel;
                }
                if (typeof(this.$refs.waiting_list_application.$refs.profile.silentElector) === 'boolean') {
                    payload.proposal.silent_elector = this.$refs.waiting_list_application.$refs.profile.silentElector;
                }
                if (this.$refs.waiting_list_application.$refs.mooring && this.$refs.waiting_list_application.$refs.mooring.selectedMooring) {
                    payload.proposal.preferred_bay_id = this.$refs.waiting_list_application.$refs.mooring.selectedMooring;
                }
            // AAA
            } else if (this.$refs.annual_admission_application) {
                if (this.$refs.annual_admission_application.$refs.vessels) {
                    payload.vessel = Object.assign({}, this.$refs.annual_admission_application.$refs.vessels.vessel);
                    payload.proposal.temporary_document_collection_id = this.$refs.annual_admission_application.$refs.vessels.temporary_document_collection_id;
                    payload.proposal.keep_existing_vessel = this.$refs.annual_admission_application.keepCurrentVessel;
                }
                if (this.$refs.annual_admission_application.$refs.insurance.selectedOption) {
                    // modify if additional proposal attributes required
                    payload.proposal.insurance_choice = this.$refs.annual_admission_application.$refs.insurance.selectedOption;
                }
            // AUA
            } else if (this.$refs.authorised_user_application) {
                if (this.$refs.authorised_user_application.$refs.vessels) {
                    payload.vessel = Object.assign({}, this.$refs.authorised_user_application.$refs.vessels.vessel);
                    payload.proposal.temporary_document_collection_id = this.$refs.authorised_user_application.$refs.vessels.temporary_document_collection_id;
                    payload.proposal.keep_existing_vessel = this.$refs.authorised_user_application.keepCurrentVessel;
                }
                if (this.$refs.authorised_user_application.$refs.insurance.selectedOption) {
                    // modify if additional proposal attributes required
                    payload.proposal.insurance_choice = this.$refs.authorised_user_application.$refs.insurance.selectedOption;
                }
                if (this.$refs.authorised_user_application.$refs.mooring_authorisation) {
                    payload.proposal.keep_existing_mooring =
                        !this.$refs.authorised_user_application.$refs.mooring_authorisation.changeMooring;
                    if (this.$refs.authorised_user_application.$refs.mooring_authorisation.mooringAuthPreference) {
                        payload.proposal.mooring_authorisation_preference =
                            this.$refs.authorised_user_application.$refs.mooring_authorisation.mooringAuthPreference;
                    }
                    if (payload.proposal.mooring_authorisation_preference === 'ria') {
                        payload.proposal.bay_preferences_numbered =
                            this.$refs.authorised_user_application.$refs.mooring_authorisation.mooringBays.map((item) => item.id);
                    } else if (payload.proposal.mooring_authorisation_preference === 'site_licensee') {
                        payload.proposal.site_licensee_moorings = this.proposal.site_licensee_moorings;
                    }
                }
            // MLA
            } else if (this.$refs.mooring_licence_application) {
                if (this.$refs.mooring_licence_application.$refs.vessels) {
                    payload.vessel = Object.assign({}, this.$refs.mooring_licence_application.$refs.vessels.vessel);
                    payload.vessel.readonly = this.$refs.mooring_licence_application.$refs.vessels.readonly;
                    payload.proposal.temporary_document_collection_id = this.$refs.mooring_licence_application.$refs.vessels.temporary_document_collection_id;
                    payload.proposal.keep_existing_vessel = this.$refs.mooring_licence_application.keepCurrentVessel;
                }
                if (typeof(this.$refs.mooring_licence_application.$refs.profile.silentElector) === 'boolean') {
                    payload.proposal.silent_elector = this.$refs.mooring_licence_application.$refs.profile.silentElector;
                }
                if (this.$refs.mooring_licence_application.$refs.insurance.selectedOption) {
                    payload.proposal.insurance_choice = this.$refs.mooring_licence_application.$refs.insurance.selectedOption;
                }
            }
            payload.profile = this.profile
            payload.proposal.no_email_notifications = this.proposal.no_email_notifications;

            return payload;
        },
        updateSubmitText: function(submitText) {
            this.submitText = submitText;
        },
        save: async function(withConfirm=true, url=this.proposal_form_url,updateProposalData=true) {
            console.log("saving as assessor/approver");
            let vm = this;
            vm.savingProposal=true;

            let payload = this.buildPayload();
   
            return vm.$http.post(
                url, 
                payload, {}
            ).then((res)=>{
                if (withConfirm) {
                    swal(
                        'Saved',
                        'Your application has been saved',
                        'success'
                    );                   
                }
                //we want to update the local client-side proposal data if we remain on the same page, to accomodate details that change on the backend (e.g. vessel details id)
                //we do not want to update that data if we need to immediately redirect (save_and_pay)
                if (updateProposalData) {
                    vm.proposal = res.body;
                }
                if (res.body.auto_approve !== undefined) {
                    vm.proposal.auto_approve = res.body.auto_approve;
                }
                vm.savingProposal=false;
                this.submitRes = true;               
            },(err)=>{
                swal({
                    title: "Please fix following errors before saving",
                    text: err.bodyText,
                    type:'error'
                });
                vm.savingProposal=false;  
                this.submitRes = false;
            })
        },

        submit: async function(){
            // remove the confirm prompt when navigating away from window (on button 'Submit' click)
            this.submittingProposal = true;
            this.paySubmitting=true;

            try {
                await swal({
                    title: this.submitText + " Application",
                    text: "Are you sure you want to " + this.submitText.toLowerCase()+ " this application?",
                    type: "question",
                    showCancelButton: true,
                    confirmButtonText: this.submitText
                })
            } catch (cancel) {
                this.submittingProposal = false;
                this.paySubmitting=false;
                return;
            }

            if (!this.proposal.fee_paid) {
                this.$nextTick(async () => {
                    try {
                        await this.save_and_pay();
                    } catch (err) {
                        console.log(err)
                        await swal({
                            title: 'Submit Error',
                            html: helpers.formatError(err),
                            type: "error",
                        })
                    }
                });
            } else {
                await this.save_without_pay();
            }
        },
        post_and_redirect: function(url, postData) {
            /* http.post and ajax do not allow redirect from Django View (post method),
            this function allows redirect by mimicking a form submit.

            usage:  vm.post_and_redirect(vm.application_fee_url, {'csrfmiddlewaretoken' : vm.csrf_token});
            */
            var postFormStr = "<form method='POST' action='" + url + "'>";

            for (var key in postData) {
                if (postData.hasOwnProperty(key)) {
                    if (typeof (postData[key]) === 'object') {
                        let data = JSON.stringify(postData[key]);
                        postFormStr += "<input type='hidden' name='" + key + "' value='" + data + "'>";
                    } else {
                        postFormStr += "<input type='hidden' name='" + key + "' value='" + postData[key] + "'>";
                    }
                }
            }
            postFormStr += "</form>";
            var formElement = $(postFormStr);
            $('body').append(formElement);
            $(formElement).submit();
        },
        save_and_pay: async function() {
            try {
                await this.save(false, this.proposal_submit_url,false)
                this.$nextTick(async () => {
                    if (this.submitRes) {
                        let payload = this.buildPayload();
                        payload.csrfmiddlewaretoken = this.csrf_token;
                        if (this.proposal.auto_approve) {
                            this.post_and_redirect(this.application_fee_url, payload);
                        } else if (['wla', 'aaa'].includes(this.proposal.application_type_code)) {
                            this.post_and_redirect(this.application_fee_url, payload);
                        } else {
                            this.post_and_redirect(this.confirmation_url, payload);
                        }
                        this.submitRes = null;
                    } else {
                        this.savingProposal=false;
                        this.paySubmitting=false;
                        this.submittingProposal=false;
                        this.submitRes = null;
                    }
                });
            } catch(err) {
                console.log(err)
                console.log(typeof(err.body))
                await swal({
                    title: 'Submit Error',
                    html: helpers.formatError(err),
                    type: "error",
                })
                this.savingProposal=false;
                this.paySubmitting=false;
                this.submittingProposal=false;
            }
        },
        save_without_pay: async function(){
            /* just save and submit - no payment required (probably application was pushed back by assessor for amendment */
            let vm = this
            try {
                await this.save(false, this.proposal_submit_url,true)
                this.$nextTick(async () => {
                    if (this.submitRes) {
                        vm.$router.go();
                    }
                });
            } catch(err) {
                await swal({
                    title: 'Submit Error',
                    html: helpers.formatError(err),
                    type: "error",
                })
                this.savingProposal=false;
                this.paySubmitting=false;
                this.submitRes = null;
                this.submittingProposal=false;
            }
        },
        populateProfile: function(profile) {
            this.profile = profile
        },
        fetchSiteLicenseeMooring: async function() {
            console.log('%cin fetchSiteLicenseeMooring', 'color:#f33;')
            if (this.proposal.mooring_id){
                const res = await this.$http.get(`${api_endpoints.mooring}${this.proposal.mooring_id}`);
                this.siteLicenseeMooring = Object.assign({}, res.body);
            }
        },
        fetchMooringBays: async function() {
            console.log('%cin fetchMooringBays', 'color:#f33;')
            const res = await this.$http.get(api_endpoints.mooring_bays_lookup);
            console.log(res.body)
            for (let bay of res.body) {
                this.mooringBays.push(bay)
            }
        },
        locationUpdated: function(){
            console.log('in locationUpdated()');
        },
        commaToNewline(s){
            return s.replace(/[,;]/g, '\n');
        },
        proposedDecline: function(){
            console.log('in proposedDecline')
            this.$refs.proposed_decline.decline = this.proposal.proposaldeclineddetails != null ? helpers.copyObject(this.proposal.proposaldeclineddetails): {};
            this.$refs.proposed_decline.isModalOpen = true;
        },
        proposedApproval: function(){
            console.log('proposedApproval')
            this.uuid++;
            this.$nextTick(() => {
                this.$refs.proposed_approval.approval = this.proposal.proposed_issuance_approval != null ? helpers.copyObject(this.proposal.proposed_issuance_approval) : {};
                this.$refs.proposed_approval.isModalOpen = true;
            });
        },
        issueProposal:function(){
            console.log('%cin issueProposal', 'color:#f33;')
            this.uuid++;
            this.$nextTick(() => {
                if (this.proposal.proposed_issuance_approval != null){
                    this.$refs.proposed_approval.approval = helpers.copyObject(this.proposal.proposed_issuance_approval)
                } else {
                    this.$refs.proposed_approval.approval = {}
                }
                this.$refs.proposed_approval.state = 'final_approval';
                this.$refs.proposed_approval.isModalOpen = true;
            });
        },
        declineProposal:function(){
            console.log('in declineProposal')
            this.$refs.proposed_decline.decline = this.proposal.proposaldeclineddetails != null ? helpers.copyObject(this.proposal.proposaldeclineddetails): {};
            this.$refs.proposed_decline.isModalOpen = true;
        },
        bypassEndorsement: function(){
            console.log("bypassEndorsement")
            let vm = this;

            if(vm.proposal.processing_status == 'Awaiting Endorsement' && 
            [constants.AU_PROPOSAL].includes(vm.proposal.application_type_dict.code)){

                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/bypass_endorsement')),{
                    emulateJSON:true,
                })
                .then((response) => {
                    console.log('0 response.body: ')
                    console.log(response.body)
                    vm.proposal = response.body;
                    vm.original_proposal = helpers.copyObject(response.body);
                    vm.approver_comment='';
                    vm.$nextTick(() => {
                        vm.initialiseAssignedOfficerSelect(true);
                        vm.updateAssignedOfficerSelect();
                    });
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(error),
                        'error'
                    )
                });

            }
        },
        requestEndorsement: function(){
            console.log("requestEndorsement")
            let vm = this;

            if(vm.proposal.processing_status == 'With Assessor' && 
            [constants.AU_PROPOSAL].includes(vm.proposal.application_type_dict.code) &&
            vm.proposal.has_unactioned_endorsements){

                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/request_endorsement')),{
                    emulateJSON:true,
                })
                .then((response) => {
                    console.log('0 response.body: ')
                    console.log(response.body)
                    vm.proposal = response.body;
                    vm.original_proposal = helpers.copyObject(response.body);
                    vm.approver_comment='';
                    vm.$nextTick(() => {
                        vm.initialiseAssignedOfficerSelect(true);
                        vm.updateAssignedOfficerSelect();
                    });
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(error),
                        'error'
                    )
                });

            }
        },
        backToAssessorRequirements: function(){
            console.log('Open modal here!')
            this.$refs.back_to_assessor.isModalOpen = true
        },
        amendmentRequest: function(){
            let values = '';
            $('.deficiency').each((i,d) => {
                values +=  $(d).val() != '' ? `Question - ${$(d).data('question')}\nDeficiency - ${$(d).val()}\n\n`: '';
            });
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
                }
            });
            vm.highlight_deficient_fields(deficient_fields);
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
                vm.updateAssignedOfficerSelect();
            }, (error) => {
                vm.proposal = helpers.copyObject(vm.original_proposal)
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
            vm.$nextTick(() => {
                vm.initialiseAssignedOfficerSelect(true);
                vm.updateAssignedOfficerSelect();
            });
        },
        refreshRequirements: function(bool){
              let vm=this;
              vm.requirementsComplete = bool;
        },
        assignTo: function(){
            let vm = this;
            let unassign = true;
            let data = {};
            if (vm.proposal && vm.proposal.processing_status == 'With Approver'){
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
                    vm.updateAssignedOfficerSelect();
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
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
                    vm.updateAssignedOfficerSelect();
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
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
            console.log('in switchStatus')
            console.log(this.proposal.processing_status)
            console.log(status)

            let vm = this;
            if(vm.proposal.processing_status == 'With Assessor' && status == 'with_assessor_requirements'){
                let formData = new FormData(vm.form);
                let data = {'status': status, 'approver_comment': vm.approver_comment}
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/switch_status')), JSON.stringify(data),{
                    emulateJSON:true,
                })
                .then((response) => {
                    console.log('0 response.body: ')
                    console.log(response.body)
                    vm.proposal = response.body;
                    vm.original_proposal = helpers.copyObject(response.body);
                    vm.approver_comment='';
                    vm.$nextTick(() => {
                        vm.initialiseAssignedOfficerSelect(true);
                        vm.updateAssignedOfficerSelect();
                    });
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(error),
                        'error'
                    )
                });
            }

            //if approver is pushing back proposal to Assessor then navigate the approver back to dashboard page
            else if(vm.proposal.processing_status == 'With Approver' && (status == 'with_assessor_requirements' || status=='with_assessor')) {
                let data = {'status': status, 'approver_comment': vm.approver_comment}
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/switch_status')),JSON.stringify(data),{
                    emulateJSON:true,
                })
                .then((response) => {
                    vm.proposal = response.body;
                    vm.original_proposal = helpers.copyObject(response.body);
                    vm.approver_comment='';
                    vm.$nextTick(() => {
                        vm.initialiseAssignedOfficerSelect(true);
                        vm.updateAssignedOfficerSelect();
                    });
                    vm.$router.push({ path: '/internal' });
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(error),
                        'error'
                    )
                });
            } else {
                let data = {'status': status, 'approver_comment': vm.approver_comment}
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/switch_status')), JSON.stringify(data),{
                    emulateJSON:true,
                })
                .then((response) => {
                    console.log('2 response.body:')
                    console.log(response.body)

                    vm.proposal = response.body;
                    vm.original_proposal = helpers.copyObject(response.body);
                    vm.approver_comment='';
                    vm.$nextTick(() => {
                        vm.initialiseAssignedOfficerSelect(true);
                        vm.updateAssignedOfficerSelect();
                    });
                }, (error) => {
                    vm.proposal = helpers.copyObject(vm.original_proposal)
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(error),
                        'error'
                    )
                });
            }
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
                vm.initialiseAssignedOfficerSelect();
                vm.initialisedSelects = true;
            }
        },
    },
    mounted: function() {
        let vm = this;
        vm.fetchMooringBays()
        console.log('AAA')
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
            vm.initialiseSelects();
            vm.form = document.forms.new_proposal;
            if(vm.hasAmendmentRequest){
                vm.deficientFields();
            }
        });
    },
    created: function() {
        console.log('%cin created', 'color:#f33;')
        Vue.http.get(`/api/proposal/${this.$route.params.proposal_id}/internal_proposal.json`).then(res => {
            console.log('%cproposal has been returned.', 'color: #f11;')
            this.proposal = res.body;
            this.original_proposal = helpers.copyObject(res.body);
            this.hasAmendmentRequest=this.proposal.hasAmendmentRequest;
        },
        err => {
          console.log(err);
        });
    },
    beforeRouteUpdate: function(to, from, next) {
        console.log("beforeRouteUpdate")
          Vue.http.get(`/api/proposal/${to.params.proposal_id}.json`).then(res => {
              next(vm => {
                vm.proposal = res.body;
                vm.original_proposal = helpers.copyObject(res.body);
              });
            },
            err => {
              console.log(err);
            });
    }
}
</script>