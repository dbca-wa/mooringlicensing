<template>
    <div class="container">
        <FormSection label="Select Applicant" v-if="is_internal">
            <div>
                <div>
                    <label class="col-sm-3">Applicant</label>
                    <div class="col-sm-6">
                        <select 
                            id="person_lookup"  
                            name="person_lookup"  
                            ref="person_lookup" 
                            class="form-control" 
                        />
                    </div>
                </div>
            </div>
        </FormSection>
        <div v-if="applicationsLoading">
            <div style="text-align: center;">
                <i class='fa fa-5x fa-spinner fa-spin'></i>
            </div>
        </div>
        <div v-else class="row">
            <div class="col-sm-12">
                <form class="form-horizontal" name="personal_form" method="post">
                    <FormSection label="Apply for">
                        <div>
                            <div v-if="season_text" class="col-sm-12" style="margin-bottom: 1em;">
                                <strong>
                                    Application for the current season: {{ season_text }}
                                </strong>
                            </div>
                            <div class="col-sm-12" style="margin-left:20px">
                                <div class="form-group">
                                    <label v-if="aaaChoices.length > 0">Annual Admission</label>
                                    <div v-if="aaaApprovals.length <= 1">
                                        <div v-for="(application_type, index) in aaaChoices">
                                            <input type="radio" name="applicationType"
                                                :id="application_type.code + '_' + index" value="application_type"
                                                @change="selectApplication(application_type)" />
                                            <label :for="application_type.code + '_' + index" style="font-weight:normal">{{
                                                application_type.new_application_text }}</label>
                                        </div>
                                    </div>
                                    <div v-else>
                                        <div class="row" v-for="application_type in aaaMultiple">
                                            <div class="col-sm-5">
                                                <input type="radio" name="applicationType" :id="application_type.code"
                                                    value="application_type"
                                                    @change="selectApplication(application_type)" />
                                                <label :for="application_type.code" style="font-weight:normal">{{
                                                    application_type.new_application_text }}</label>
                                            </div>
                                            <span class="pull-left col-sm-2" v-if="application_type.multiple">
                                                <select class="form-control" v-model="selectedCurrentProposal">
                                                    <option v-for="approval in aaaApprovals"
                                                        :value="approval.current_proposal_id">
                                                        {{ approval.lodgement_number }}
                                                    </option>
                                                </select>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label v-if="auaChoices.length > 0">Authorised User</label>
                                    <div v-if="auaApprovals.length <= 1">
                                        <div v-for="(application_type, index) in auaChoices">
                                            <input type="radio" name="applicationType"
                                                :id="application_type.code + '_' + index" value="application_type"
                                                @change="selectApplication(application_type)" />
                                            <label :for="application_type.code + '_' + index" style="font-weight:normal">{{
                                                application_type.new_application_text }}</label>
                                        </div>
                                    </div>
                                    <div v-else>
                                        <div class="row" v-for="application_type in auaMultiple">
                                            <div class="col-sm-5">
                                                <input type="radio" name="applicationType" :id="application_type.code"
                                                    value="application_type"
                                                    @change="selectApplication(application_type)" />
                                                <label :for="application_type.code" style="font-weight:normal">{{
                                                    application_type.new_application_text }}</label>
                                            </div>
                                            <span class="pull-left col-sm-2" v-if="application_type.multiple">
                                                <select class="form-control" v-model="selectedCurrentProposal">
                                                    <option v-for="approval in auaApprovals"
                                                        :value="approval.current_proposal_id">
                                                        {{ approval.lodgement_number }}
                                                    </option>
                                                </select>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label v-if="wlaChoices.length > 0">Waiting List</label>
                                    <div v-if="wlaApprovals.length <= 1">
                                        <div v-for="(application_type, index) in wlaChoices">
                                            <input type="radio" name="applicationType"
                                                :id="application_type.code + '_' + index" value="application_type"
                                                @change="selectApplication(application_type)" />
                                            <label :for="application_type.code + '_' + index" style="font-weight:normal">{{
                                                application_type.new_application_text }}</label>
                                        </div>
                                    </div>
                                    <div v-else>
                                        <div class="row" v-for="application_type in wlaMultiple">
                                            <div class="col-sm-5">
                                                <input type="radio" name="applicationType" :id="application_type.code"
                                                    value="application_type"
                                                    @change="selectApplication(application_type)" />
                                                <label :for="application_type.code" style="font-weight:normal">{{
                                                    application_type.new_application_text }}</label>
                                            </div>
                                            <span class="pull-left col-sm-2" v-if="application_type.multiple">
                                                <select class="form-control" v-model="selectedCurrentProposal">
                                                    <option v-for="approval in wlaApprovals"
                                                        :value="approval.current_proposal_id">
                                                        {{ approval.lodgement_number }}
                                                    </option>
                                                </select>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div v-if="mlApprovals.length" class="form-group">
                                    <label>Mooring Site Licence</label>
                                    <div v-if="mlApprovals.length <= 1">
                                        <!-- Approvals <= 1 -->
                                        <div v-for="(application_type, index) in mlChoices">
                                            <div class="row">
                                                <div class="col-sm-7">
                                                    <input
                                                        type="radio"
                                                        name="applicationType"
                                                        :id="application_type.code + '_' + index"
                                                        value="application_type"
                                                        @change="selectApplication(application_type)"
                                                    />
                                                    <label
                                                        :for="application_type.code + '_' + index"
                                                        style="font-weight:normal"
                                                    >
                                                        {{ application_type.new_application_text }}
                                                    </label>
                                                </div>
                                            </div>
                                            <div class="row">
                                                <div class="col-sm-7">
                                                    <input
                                                        type="radio"
                                                        name="applicationType"
                                                        :id="application_type.code + '_' + index + '_add_vessel'"
                                                        value="application_type"
                                                        @change="selectApplication(application_type, true)"
                                                    />
                                                    <label
                                                        :for="application_type.code + '_' + index + '_add_vessel'"
                                                        style="font-weight:normal"
                                                    >
                                                        {{ application_type.new_application_text_add_vessel }}
                                                    </label>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div v-else>
                                        <!-- Approvals >= 2 -->
                                        <div class="row" v-for="application_type in mlMultiple">
                                            <div class="col-sm-5">
                                                <input
                                                    type="radio"
                                                    name="applicationType"
                                                    :id="application_type.code"
                                                    value="application_type"
                                                    @change="selectApplication(application_type)"
                                                />
                                                <label
                                                    :for="application_type.code"
                                                    style="font-weight:normal"
                                                >
                                                    {{ application_type.new_application_text }}
                                                </label>
                                            </div>
                                            <span class="pull-left col-sm-2" v-if="application_type.multiple">
                                                <select class="form-control" v-model="selectedCurrentProposal">
                                                    <option v-for="approval in mlApprovals"
                                                        :value="approval.current_proposal_id"
                                                    >
                                                        {{ approval.lodgement_number }}
                                                    </option>
                                                </select>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                
                                <!--<div v-if="!is_internal" class="form-group">
                                    <label>DCV Permit</label>
                                    <div>
                                        <div v-for="(application_type, index) in dcvpChoices">
                                            <input type="radio" name="applicationType"
                                                :id="application_type.code + '_' + index" value="application_type"
                                                @change="selectApplication(application_type)" />
                                            <label :for="application_type.code + '_' + index" style="font-weight:normal">{{
                                                application_type.new_application_text }}</label>
                                        </div>
                                    </div>
                                </div>-->
                            </div>
                        </div>
                    </FormSection>
                    
                    <div class="col-sm-12">
                        <p class="pull-right" style="margin-top:5px">
                        <input v-if="is_internal" type="checkbox" v-model="noEmails" id="noEmails" />
                        <label v-if="is_internal" for="noEmails">
                            &nbsp;Do not send email notifications for this application &nbsp;
                        </label>

                        <button v-if="!creatingProposal" :disabled="isDisabled" @click.prevent="submit()"
                            class="btn btn-primary pull-right">Continue</button>
                        <button v-else disabled class="pull-right btn btn-primary"><i
                                class="fa fa-spin fa-spinner"></i>&nbsp;Creating</button>
                        </p>
                    </div>
                </form>
            </div>
        </div>
    </div>
</template>
<script>

import FormSection from '@/components/forms/section_toggle.vue'

import {
    api_endpoints,
    helpers
}
    from '@/utils/hooks'
import utils from './utils'
export default {
    props: {
        is_internal: {
            type: Boolean,
            required: false,
            default: false,
        }
    },
    data: function () {
        let vm = this;
        return {
            applicationsLoading: false,
            "proposal": null,
            profile: {
            },
            "loading": [],
            form: null,
            selectedApplication: {},
            add_vessel: false,
            selectedCurrentProposal: null,
            application_types_and_licences: [],

            wlaChoices: [],
            aaaChoices: [],
            auaChoices: [],
            mlChoices: [],
            dcvpChoices: [
                {
                    'code': 'dcvp',
                    'description': 'DCV permit application',
                    'new_application_text': 'I want to apply for a DCV permit',
                },
            ],

            wlaApprovals: [],
            aaaApprovals: [],
            auaApprovals: [],
            mlApprovals: [],

            wlaMultiple: [],
            aaaMultiple: [],
            auaMultiple: [],
            mlMultiple: [],

            creatingProposal: false,
            newWlaAllowed: false,
            
            noEmails: false,
            season_text: '',

            applicant_system_id: null,
        }
    },
    components: {
        FormSection
    },
    computed: {
        isLoading: function () {
            return this.loading.length > 0
        },
        isDisabled: function () {
            let disabled = true;
            if (this.selectedApplication && this.selectedApplication.code) {
                disabled = false;
            }
            return disabled;
        },
        alertText: function () {
            let text = '';
            if (this.selectedApplication && this.selectedApplication.description) {
                text = this.selectedApplication.description;
            }
            if (this.selectedApplication.code == 'wla' || this.selectedApplication.code == 'dcvp') {
                text = "a " + text;
            } else if (this.selectedApplication.code == 'ml') {
                text = "your " + text
            } else if (this.selectedApplication.code == 'aaa' || this.selectedApplication.code == 'aua'){
                text = "an " + text;
            }
            return text
        },

    },
    methods: {
        resetForm: function() {
            this.form =  null;
            this.selectedApplication =  {};
            this.add_vessel =  false;
            this.selectedCurrentProposal =  null;
            this.application_types_and_licences =  [];
            this.wlaChoices =  [];
            this.aaaChoices =  [];
            this.auaChoices =  [];
            this.mlChoices =  [];
            this.wlaApprovals =  [];
            this.aaaApprovals =  [];
            this.auaApprovals =  [];
            this.mlApprovals =  [];
            this.wlaMultiple =  [];
            this.aaaMultiple =  [];
            this.auaMultiple =  [];
            this.mlMultiple =  [];
            this.newWlaAllowed =  false;
            this.season_text =  '';
        },
        initialisePersonLookup: function(){
            let vm = this;
            $(vm.$refs.person_lookup).select2({
                minimumInputLength: 2,
                "theme": "bootstrap",
                allowClear: true,
                placeholder:"Select Person",
                pagination: true,
                ajax: {
                    url: api_endpoints.person_lookup,
                    dataType: 'json',
                    data: function(params) {
                        return {
                            search_term: params.term,
                            page_number: params.page || 1,
                            type: 'public',
                        }
                    },
                    processResults: function(data){
                        console.log({data})
                        return {
                            'results': data.results,
                            'pagination': {
                                'more': data.pagination.more
                            }
                        }
                    },
                },
            }).
            on("select2:select", function (e) {
                var selected = $(e.currentTarget);
                vm.applicant_system_id = e.params.data.id;
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.applicant_system_id  = null;
            }).
            on("select2:open",function (e) {
                const searchField = $('[aria-controls="select2-person_lookup-results"]')
                // move focus to select2 field
                searchField[0].focus();
            });
        },
        parseApprovals: function () {
            this.application_types_and_licences.forEach(app => {
                if (app.code === 'wla' && app.lodgement_number) {
                    this.wlaApprovals.push({
                        lodgement_number: app.lodgement_number,
                        current_proposal_id: app.current_proposal_id,
                    });
                } else if (app.code === 'aap' && app.lodgement_number) {
                    this.aaaApprovals.push({
                        lodgement_number: app.lodgement_number,
                        current_proposal_id: app.current_proposal_id,
                    });
                } else if (app.code === 'aup' && app.lodgement_number) {
                    this.auaApprovals.push({
                        lodgement_number: app.lodgement_number,
                        current_proposal_id: app.current_proposal_id,
                    });
                } else if (app.code === 'ml' && app.lodgement_number) {
                    this.mlApprovals.push({
                        lodgement_number: app.lodgement_number,
                        current_proposal_id: app.current_proposal_id,
                    });
                }
            });
        },
        parseWla: function () {
            console.log('in parseWla')
            if (this.wlaApprovals.length > 1) {
                console.log('wlaApprovals > 1')
                for (let app of this.application_types_and_licences) {
                    if (app.code === 'wla' && !app.approval_id) {
                        // new app
                        this.wlaMultiple.push(app)
                    }
                }
                // add generic
                this.wlaMultiple.push({
                    new_application_text: "I want to amend or renew my current waiting list allocation",
                    description: "Waiting List Application",
                    code: "wla_multiple",
                    multiple: true
                })
            } else {
                console.log('wlaApprovals = 0 or 1')
                // add wla approval to wlaChoices
                for (let app of this.application_types_and_licences) {
                    if (app.code === 'wla' && (this.newWlaAllowed || app.approval_id)) {
                        this.wlaChoices.push(app);
                    }
                }
            }
        },
        parseAaa: function () {
            if (this.aaaApprovals.length > 1) {
                // new app
                for (let app of this.application_types_and_licences) {
                    if (['aaa', 'aap'].includes(app.code) && !app.approval_id) {
                        this.aaaMultiple.push(app)
                    }
                }
                // add generic
                this.aaaMultiple.push({
                    new_application_text: "I want to amend or renew my current annual admission permit",
                    description: "Annual Admission Application",
                    code: "aaa_multiple",
                    multiple: true
                })
            } else {
                // add wla approval to wlaChoices
                for (let app of this.application_types_and_licences) {
                    if (['aaa', 'aap'].includes(app.code)) {
                        this.aaaChoices.push(app);
                    }
                }
            }
        },
        parseAua: function () {
            if (this.auaApprovals.length > 1) {
                // new app
                for (let app of this.application_types_and_licences) {
                    if (['aua', 'aup'].includes(app.code) && !app.approval_id) {
                        this.auaMultiple.push(app)
                    }
                }
                // add generic
                this.auaMultiple.push({
                    new_application_text: "I want to amend or renew my current authorised user permit",
                    description: "Authorised User Application",
                    code: "aua_multiple",
                    multiple: true
                })
            } else {
                // add wla approval to wlaChoices
                for (let app of this.application_types_and_licences) {
                    if (['aua', 'aup'].includes(app.code)) {
                        this.auaChoices.push(app);
                    }
                }
            }
        },
        parseMl: function () {
            if (this.mlApprovals.length > 1) {
                // add generic
                this.mlMultiple.push({
                    new_application_text: "I want to amend or renew my current mooring site licence",
                    description: "Mooring Site Licence Application",
                    code: "ml_multiple",
                    multiple: true
                })
            } else {
                // add wla approval to wlaChoices
                for (let app of this.application_types_and_licences) {
                    if (app.code === "ml") {
                        this.mlChoices.push(app);
                    }
                }
            }
        },
        selectApplication(applicationType, add_vessel=false) {
            this.selectedCurrentProposal = null;
            this.selectedApplication = Object.assign({}, applicationType)
            this.add_vessel = add_vessel
            if (this.selectedApplication.current_proposal_id) {
                this.selectedCurrentProposal = this.selectedApplication.current_proposal_id;
            }
        },
        submit: function () {
            let title_verb = 'Create'
            let text_verb = 'create'
            if (this.selectedApplication.approval_id) {
                title_verb = 'Amend or renew'
                text_verb = 'amend or renew'
            }
            if (this.add_vessel){
                text_verb = 'add another vessel to'
            }
            swal({
                title: title_verb + " " + this.selectedApplication.description.toLowerCase(),
                text: "Are you sure you want to " + text_verb + " " + this.alertText.toLowerCase() + "?",
                type: "question",
                showCancelButton: true,
                confirmButtonText: 'Accept'
            }).then(() => {
                this.createProposal();
            }, (error) => {
            });
        },
        createProposal: async function () {
            let vm = this
            this.$nextTick(async () => {
                let res = null;
                try {
                    this.creatingProposal = true;

                    if (this.is_internal) {

                        const payload = {
                            "applicant_system_id": this.applicant_system_id,
                            "no_emails": this.noEmails,
                        };

                        const url = helpers.add_endpoint_json(api_endpoints.proposal, (
                            this.selectedCurrentProposal + '/renew_amend_approval_wrapper')
                        )
                        if (this.selectedApplication && ['wla', 'wla_multiple'].includes(this.selectedApplication.code)) {
                            if (this.selectedCurrentProposal) {
                                res = await this.$http.post(url);
                            } else {
                                res = await this.$http.post(api_endpoints.internalwaitinglistapplication,payload);
                            }
                        } else if (this.selectedApplication && ['aaa', 'aap', 'aaa_multiple'].includes(this.selectedApplication.code)) {
                            if (this.selectedCurrentProposal) {
                                res = await this.$http.post(url);
                            } else {
                                res = await this.$http.post(api_endpoints.internalannualadmissionapplication,payload);
                            }
                        } else if (this.selectedApplication && ['aua', 'aup', 'aua_multiple'].includes(this.selectedApplication.code)) {
                            if (this.selectedCurrentProposal) {
                                res = await this.$http.post(url);
                            } else {
                                res = await this.$http.post(api_endpoints.internalauthoriseduserapplication,payload);
                            }
                        } else if (this.selectedApplication && ['ml', 'ml_multiple'].includes(this.selectedApplication.code)) {
                            res = await this.$http.post(url, {'add_vessel': vm.add_vessel});
                        } 
                        const proposal = res.body;
                        this.$router.push({
                            name: "internal-proposal",
                            params: { proposal_id: proposal.id }
                        });
                    } else {
                        const url = helpers.add_endpoint_json(api_endpoints.proposal, (
                            this.selectedCurrentProposal + '/renew_amend_approval_wrapper')
                        )
                        if (this.selectedApplication && ['wla', 'wla_multiple'].includes(this.selectedApplication.code)) {
                            if (this.selectedCurrentProposal) {
                                res = await this.$http.post(url);
                            } else {
                                res = await this.$http.post(api_endpoints.waitinglistapplication);
                            }
                        } else if (this.selectedApplication && ['aaa', 'aap', 'aaa_multiple'].includes(this.selectedApplication.code)) {
                            if (this.selectedCurrentProposal) {
                                res = await this.$http.post(url);
                            } else {
                                res = await this.$http.post(api_endpoints.annualadmissionapplication);
                            }
                        } else if (this.selectedApplication && ['aua', 'aup', 'aua_multiple'].includes(this.selectedApplication.code)) {
                            if (this.selectedCurrentProposal) {
                                res = await this.$http.post(url);
                            } else {
                                res = await this.$http.post(api_endpoints.authoriseduserapplication);
                            }
                        } else if (this.selectedApplication && ['ml', 'ml_multiple'].includes(this.selectedApplication.code)) {
                            res = await this.$http.post(url, {'add_vessel': vm.add_vessel});
                        } else if (this.selectedApplication && ['dcvp',].includes(this.selectedApplication.code)) {
                            this.$router.push('/external/dcv_permit')
                            return
                        }
                        const proposal = res.body;
                        this.$router.push({
                            name: "draft_proposal",
                            params: { proposal_id: proposal.id }
                        });
                    }
                    this.creatingProposal = false;
                } catch (error) {
                    console.log(error)
                    await swal({
                        title: "Renew/Amend Approval",
                        text: error.body,
                        type: "error",
                    });
                    this.$router.go();
                }
            });
        },
        searchList: function (id, search_list) {
            /* Searches for dictionary in list */
            for (var i = 0; i < search_list.length; i++) {
                if (search_list[i].value == id) {
                    return search_list[i];
                }
            }
            return [];
        },
        fetchApplicationTypes: async function () {
            const response = await this.$http.get(api_endpoints.application_types_dict + '?apply_page=True');
            for (let app_type of response.body) {
                this.application_types_and_licences.push(app_type)
            }
        },
        fetchExistingLicences: async function () {
            if (this.is_internal && this.applicant_system_id) {
                const response = await this.$http.get(api_endpoints.existing_licences + '?applicant_system_id='+this.applicant_system_id);
                for (let l of response.body) {
                    this.application_types_and_licences.push(l)
                }
            } else {
                const response = await this.$http.get(api_endpoints.existing_licences);
                for (let l of response.body) {
                    this.application_types_and_licences.push(l)
                }
            }            
        },
        fetchWlaAllowed: async function () {
            if (this.is_internal && this.applicant_system_id) {
                const response = await this.$http.get(api_endpoints.wla_allowed+ '?applicant_system_id='+this.applicant_system_id);
                this.newWlaAllowed = response.body.wla_allowed;
            } else {
                const response = await this.$http.get(api_endpoints.wla_allowed);
                this.newWlaAllowed = response.body.wla_allowed;
            }
        },
        fetchCurrentSeason: async function () {
            const response = await this.$http.get(api_endpoints.current_season);
            console.log(response.body)
            if (response.body.length) {
                this.season_text = response.body[0].start_date + ' to ' + response.body[0].end_date
            }
        }
    },
    watch: {
        applicant_system_id: async function () {
            console.log(this.applicant_system_id)
            this.applicationsLoading = true;
            this.resetForm();
            if (this.applicant_system_id != null) {
                await this.fetchApplicationTypes();
                await this.fetchExistingLicences();
                await this.fetchWlaAllowed();
                await this.fetchCurrentSeason();

                this.parseApprovals();  // wlaApprovals, aaaApprovals, auaApprovals and ml Approvals
                this.parseWla();
                this.parseAaa();
                this.parseAua();
                this.parseMl();
                this.form = document.forms.new_proposal;
            }
            this.applicationsLoading = false;
        }
    },
    mounted: async function () {
        this.applicationsLoading = true;

        if (this.is_internal) {
            //must select user to load for
            this.$nextTick(async () => {
                this.initialisePersonLookup();
            });
        } else {

            await this.fetchApplicationTypes();
            await this.fetchExistingLicences();  // application_types_and_licences has all the application types and the existing licences
            await this.fetchWlaAllowed();
            await this.fetchCurrentSeason();

            this.parseApprovals();  // wlaApprovals, aaaApprovals, auaApprovals and ml Approvals
            this.parseWla();
            this.parseAaa();
            this.parseAua();
            this.parseMl();
            this.form = document.forms.new_proposal;

        }
        this.applicationsLoading = false;
    },
    beforeRouteEnter: function (to, from, next) {

        let initialisers = [
            utils.fetchProfile(),
        ]
        next(vm => {
            vm.loading.push('fetching profile')
            Promise.all(initialisers).then(data => {
                vm.profile = data[0];
                vm.loading.splice('fetching profile', 1)
            })
        })

    }
}
</script>

<style lang="css">
input[type=text],
select {
    width: 40%;
    box-sizing: border-box;

    min-height: 34px;
    padding: 0;
    height: auto;
}

.group-box {
    border-style: solid;
    border-width: thin;
    border-color: #FFFFFF;
}

.radio-buttons {
    padding: 5px;
}
</style>
