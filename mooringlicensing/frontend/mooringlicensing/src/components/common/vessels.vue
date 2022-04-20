<template lang="html">
    <div id="vessels">
        <FormSection label="Registration Details" Index="registration_details">
            <div class="row form-group">
                <label for="vessel_search" class="col-sm-3 control-label">Vessel registration number</label>
                <div class="col-sm-9">
                    <select :disabled="regoReadonly" id="vessel_search"  ref="vessel_rego_nos" class="form-control" style="width: 40%">
                        <option></option>
                    </select>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel name</label>
                <div class="col-sm-9">
                    <input :readonly="readonly" type="text" class="form-control" id="vessel_name" placeholder="" v-model="vessel.vessel_details.vessel_name" required/>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Registration vessel owner</label>
                <div class="col-sm-9">
                    <div class="row">
                        <div class="col-sm-9">
                            <input 
                            @change="clearOrgName" 
                            :disabled="readonly" 
                            type="radio" 
                            id="registered_owner_current_user" 
                            name="registered_owner" 
                            :value="true" 
                            v-model="vessel.vessel_ownership.individual_owner" 
                            required
                            />
                            <label for="registered_owner_current_user" class="control-label">{{  profileFullName }}</label>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-sm-3">
                            <input 
                            :disabled="readonly" 
                            type="radio" 
                            id="registered_owner_company" 
                            name="registered_owner" 
                            :value="false" 
                            v-model="vessel.vessel_ownership.individual_owner" 
                            required=""
                            />
                            <label for="registered_owner_company" class="control-label">Your company</label>
                        </div>
                        <div v-show="companyOwner" class="col-sm-8">
                            <select :disabled="readonly" id="company_name"  ref="company_name" class="form-control" style="width: 40%"/>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Ownership percentage</label>
                <div v-if="individualOwner" class="col-sm-2">
                    <input 
                     :readonly="readonly" 
                    type="number" 
                    step="1"
                    min="25" 
                    max="100" 
                    class="form-control" 
                    id="ownership_percentage" 
                    placeholder="" 
                    v-model="vessel.vessel_ownership.percentage" 
                    required=""
                    />
                </div>
                <div v-else-if="companyOwner" class="col-sm-2">
                    <input 
                     :readonly="readonly" 
                    type="number" 
                    step="1"
                    min="25" 
                    max="100" 
                    class="form-control" 
                    id="ownership_percentage_company" 
                    placeholder="" 
                    :key="companyOwnershipName"
                    v-model="vessel.vessel_ownership.company_ownership.percentage" 
                    required=""
                    />
                </div>

            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Name as shown on DoT registration papers</label>
                <div class="col-sm-9">
                    <input 
                    :readonly="readonly" 
                    type="text" 
                    class="col-sm-9 form-control" 
                    id="dot_name" 
                    placeholder="" 
                    v-model="vessel.vessel_ownership.dot_name" required=""/>
                </div>
            </div>

            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Permanent or usual place of berthing/mooring of vessel</label>
                <div class="col-sm-9">
                    <input :readonly="readonly" type="text" class="col-sm-9 form-control" id="berth_mooring" placeholder="" v-model="vessel.vessel_details.berth_mooring" required=""/>
                </div>
            </div>
            <div v-if="showDotRegistrationPapers" class="row form-group">
                <label for="" class="col-sm-3 control-label">Copy of DoT registration papers</label>
                <div v-if="!existingVesselOwnership" class="col-sm-9">
                    <FileField 
                        :readonly="readonly"
                        ref="temp_document"
                        name="temp_document"
                        :isRepeatable="true"
                        :documentActionUrl="vesselRegistrationDocumentUrl"
                        :replace_button_by_text="true"
                        :temporaryDocumentCollectionId="temporary_document_collection_id"
                        @update-temp-doc-coll-id="addToTemporaryDocumentCollectionList"
                    />
                </div>
                <div v-else class="col-sm-9">
                    <FileField 
                        :readonly="readonly"
                        ref="vessel_registration_document"
                        name="vessel_registration_document"
                        :isRepeatable="true"
                        :documentActionUrl="vesselRegistrationDocumentUrl"
                        :replace_button_by_text="true"
                    />
                </div>

            </div>
            <div v-if="applicationTypeCodeMLA" class="row form-group">
                <label for="" class="col-sm-3 control-label">Certified Hull Identification Number (HIN), if not already provided on the registration papers</label>
                <div class="col-sm-9">
                    <FileField 
                        :readonly="hinReadonly"
                        ref="hull_identification_number_documents"
                        name="hull-identification-number-documents"
                        :isRepeatable="true"
                        :documentActionUrl="hullIdentificationNumberDocumentUrl"
                        :replace_button_by_text="true"
                    />
                </div>
            </div>

        </FormSection>
        <FormSection label="Vessel Details" Index="vessel_details">
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel length</label>
                <div class="col-sm-2">
                    <input 
                    :readonly="readonly" 
                    type="number" 
                    min="1" 
                    class="form-control" 
                    id="vessel_length" 
                    placeholder="" 
                    v-model="vessel.vessel_details.vessel_length" 
                    required=""
                    @change="emitVesselLength"/>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Displacement tonnage</label>
                <div class="col-sm-2">
                    <input :readonly="readonly" type="number" min="1" class="form-control" id="displacement_tonnage" placeholder="" v-model="vessel.vessel_details.vessel_weight" required=""/>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Draft</label>
                <div class="col-sm-2">
                    <input :readonly="readonly" type="number" min="1" class="form-control" id="draft" placeholder="" v-model="vessel.vessel_details.vessel_draft" required=""/>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel Type</label>
                <div class="col-sm-4">
                    <select :disabled="readonly" class="form-control" style="width:40%" v-model="vessel.vessel_details.vessel_type">
                        <option v-for="vesselType in vesselTypes" :value="vesselType.code">
                            {{ vesselType.description }}
                        </option>
                    </select>
                </div>
            </div>
        </FormSection>
    </div>

</template>
<script>
import Vue from 'vue'
import FormSection from '@/components/forms/section_toggle.vue'
import FileField from '@/components/forms/filefield_immediate.vue'
var select2 = require('select2');
require("select2/dist/css/select2.min.css");
require("select2-bootstrap-theme/dist/select2-bootstrap.min.css");
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'

    export default {
        name:'vessels',
        data:function () {
            return {
                dotName: '',
                vessel: {
                    vessel_details: {},
                    vessel_ownership: {
                        company_ownership: {
                            company: {
                            }
                        },
                        //registered_owner: 'current_user',
                    }
                },
                vesselTypes: [],
                vesselRegoNos: [],
                selectedRego: null,
                temporary_document_collection_id: null,
            }
        },
        components:{
            FormSection,
            FileField,
        },
        props:{
            proposal:{
                type: Object,
                //required:true
            },
            profile:{
                type: Object,
                required:true
            },
            readonly:{
                type: Boolean,
                default: true,
            },
            is_internal: {
              type: Boolean,
              default: false
            },
            keep_current_vessel: {
              type: Boolean,
            },
        },
        watch: {
            vessel: {
                handler: async function() {
                    await this.vesselChanged();
                },
                deep: true
            },
        },
        computed: {
            regoReadonly: function() {
                let readonly = false;
                if ((this.proposal && this.keep_current_vessel && ['amendment', 'renewal']. includes(this.proposal.proposal_type.code)) || 
                    this.readonly || 
                    (this.proposal.pending_amendment_request && ['wla','aaa'].includes(this.proposal.application_type_code))
                ) {
                    readonly = true;
                }
                return readonly;
            },
            vesselLength: function() {
                let length = 0;
                if (this.vessel && this.vessel.vessel_details && this.vessel.vessel_details.vessel_length) {
                    length = this.vessel.vessel_details.vessel_length;
                }
                return length;
            },
            hinReadonly: function() {
                let readonly = true;
                if (this.proposal && this.proposal.processing_status === 'Draft') {
                    readonly = false;
                }
                return readonly;
            },
            companyOwnershipName: function() {
                let companyName = null;
                if (this.vessel.vessel_ownership && this.vessel.vessel_ownership.company_ownership && this.vessel.vessel_ownership.company_ownership.company) {
                    companyName = this.vessel.vessel_ownership.company_ownership.company.name;
                }
                return companyName
            },
            existingVesselOwnership: function() {
                if (this.vessel.vessel_ownership && this.vessel.vessel_ownership.id) {
                    return true;
                }
            },
            mooringLicenceCurrentVesselDisplayText: function() {
                let displayText = '';
                if (this.proposal && this.proposal.mooring_licence_vessels && this.proposal.mooring_licence_vessels.length) {
                    displayText += `Your mooring licence ${this.proposal.approval_lodgement_number} 
                    currently lists the following vessels ${this.proposal.mooring_licence_vessels.toString()}.`;
                }
                return displayText;
            },
            currentVesselDisplayText: function() {
                let displayText = '';
                if (this.proposal && this.proposal.approval_vessel_rego_no) {
                    displayText += `Your ${this.proposal.approval_type_text} ${this.proposal.approval_lodgement_number} 
                    lists a vessel with registration number ${this.proposal.approval_vessel_rego_no}.`;
                }
                return displayText;
            },
            showDotRegistrationPapers: function() {
                let retVal = false;
                if (this.companyOwner) {
                    retVal = true
                }
                return retVal;
            },
            companyOwner: function() {
                if (this.vessel && this.vessel.vessel_ownership && this.vessel.vessel_ownership.individual_owner === false) {
                    return true;
                }
            },
            individualOwner: function() {
                if (this.vessel && this.vessel.vessel_ownership && this.vessel.vessel_ownership.individual_owner) {
                    return true;
                }
            },
            profileFullName: function() {
                if (this.profile) {
                    return this.profile.full_name;
                }
            },
            fee_invoice_url: function(){
                return this.fee_paid ? this.proposal.fee_invoice_url : '';
            },
            vesselRegistrationDocumentUrl: function() {
                let url = '';
                if (this.existingVesselOwnership) {
                    url = helpers.add_endpoint_join(
                        api_endpoints.vesselownership,
                        this.vessel.vessel_ownership.id + '/process_vessel_registration_document/'
                    )
                } else {
                    url = 'temporary_document';
                }
                return url;
            },
            hullIdentificationNumberDocumentUrl: function() {
                let url = '';
                if (this.proposal && this.proposal.id) {
                    url = helpers.add_endpoint_join(
                        api_endpoints.proposal,
                        this.proposal.id + '/process_hull_identification_number_document/'
                    )
                }
                return url;
            },
            applicationTypeCodeMLA: function() {
                if (this.proposal && this.proposal.application_type_code==='mla') {
                    return true;
                }
            },
            companyName: function() {
                if (this.vessel.vessel_ownership.company_ownership && this.vessel.vessel_ownership.company_ownership.company) {
                    return this.vessel.vessel_ownership.company_ownership.company.name;
                }
            },
            vesselDetails: function() {
                return this.vessel ? this.vessel.vessel_details : {};
            },
            vesselOwnership: function() {
                return this.vessel ? this.vessel.vessel_ownership : {};
            },
            previousApplicationVesselDetails: function() {
                return this.proposal ? this.proposal.previous_application_vessel_details_obj : null;
            },
            previousApplicationVesselOwnership: function() {
                return this.proposal ? this.proposal.previous_application_vessel_ownership_obj : null;
            },
        },
        methods:{
            emitVesselLength: function() {
                this.$nextTick(() => {
                    this.$emit("updateVesselLength", this.vesselLength)
                });
            },
            vesselChanged: async function() {
                let vesselChanged = false;
                await this.$nextTick(() => {
                    // do not perform check if no previous application vessel
                    if (!this.previousApplicationVesselDetails) {
                        return
                    }
                    if (
                        (this.vesselDetails.berth_mooring && this.vesselDetails.berth_mooring.trim() !== this.previousApplicationVesselDetails.berth_mooring.trim()) ||
                        this.vesselDetails.vessel_draft != this.previousApplicationVesselDetails.vessel_draft ||
                        this.vesselDetails.vessel_length != this.previousApplicationVesselDetails.vessel_length ||
                        (this.vesselDetails.vessel_name && this.vesselDetails.vessel_name.trim() !== this.previousApplicationVesselDetails.vessel_name.trim()) ||
                        this.vesselDetails.vessel_type !== this.previousApplicationVesselDetails.vessel_type ||
                        this.vesselDetails.vessel_name.weight != this.previousApplicationVesselDetails.vessel_name.weight ||
                        this.vesselOwnership.percentage != this.previousApplicationVesselOwnership.percentage ||
                        (this.vesselOwnership.dot_name && this.vesselOwnership.dot_name.trim() !== this.previousApplicationVesselOwnership.dot_name.trim())
                    ) {
                        vesselChanged = true;
                    }
                    // company ownership
                    if (this.previousApplicationVesselOwnership.company_ownership) {
                        if (this.vesselOwnership.individual_owner) {
                            vesselChanged = true;
                        } else if (this.previousApplicationVesselOwnership.company_ownership.company.trim() !== this.vesselOwnership.company_ownership.company.name.trim() ||
                            this.previousApplicationVesselOwnership.company_ownership.percentage != this.vesselOwnership.company_ownership.company.percentage) {
                            vesselChanged = true;
                        }
                    } else if (!this.previousApplicationVesselOwnership.company_ownership && !this.vesselOwnership.individual_owner) {
                        vesselChanged = true;
                    }
                });
                this.$emit("vesselChanged", vesselChanged)
                //return vesselChanged;
            },
            addToTemporaryDocumentCollectionList(temp_doc_id) {
                this.temporary_document_collection_id = temp_doc_id;
            },
            /*
            resetCurrentVessel: function() {
            },
            */
            retrieveIndividualOwner: async function() {
                console.log("retrieve individual owner")
                if (this.individualOwner && this.vessel.id) {
                    const url = api_endpoints.lookupIndividualOwnership(this.vessel.id);
                    const res = await this.$http.post(url);
                    if (res.body) {
                        let vesselOwnership = Object.assign({}, res.body);
                        vesselOwnership.individual_owner = true;
                        vesselOwnership.company_ownership = {
                            company: {}
                        }
                        this.vessel.vessel_ownership = Object.assign({}, vesselOwnership);
                        this.vessel = Object.assign({}, this.vessel);
                    }
                }
            },
            clearOrgName: function() {
                this.$nextTick(() => {
                    if (this.individualOwner) {
                        this.vessel.vessel_ownership.org_name = '';
                    }
                })
            },
            validateRegoNo: function(data) {
                // force uppercase and no whitespace
                data = data.toUpperCase();
                data = data.replace(/\s/g,"");
                data = data.replace(/\W/g,"");
                return data;
            },
            initialiseCompanyNameSelect: async function(){
                let vm = this;
                // Vessel search
                $(vm.$refs.company_name).select2({
                    minimumInputLength: 2,
                    "theme": "bootstrap",
                    placeholder:"",
                    tags: true,
                    createTag: function (tag) {
                        return {
                            id: tag.term,
                            text: tag.term,
                            tag: true
                        };
                    },
                    ajax: {
                        url: api_endpoints.company_names,
                        dataType: 'json',
                        data: function(params) {
                            var query = {
                                term: params.term,
                                type: 'public',
                            }
                            return query;
                        },
                    },
                }).
                on("select2:select", async function (e) {
                    var selected = $(e.currentTarget);
                    let data = e.params.data.id;
                    vm.$nextTick(async () => {
                        if (!e.params.data.tag) {
                            await vm.lookupCompanyOwnership(data);
                        } else {
                            let text = e.params.data.text;

                            let companyOwnership = {
                                company: {
                                    name: text,
                                }
                            }
                            vm.vessel.vessel_ownership = Object.assign({}, vm.vessel.vessel_ownership, {company_ownership: companyOwnership});
                        }
                    });
                }).
                on("select2:unselect",function (e) {
                    let companyOwnership = {
                        company: {
                        }
                    }
                    vm.vessel.vessel_ownership.company_ownership = Object.assign({}, companyOwnership);
                    vm.vessel = Object.assign({}, vm.vessel);
                }).
                on("select2:open",function (e) {
                    const searchField = $(".select2-search__field")
                    // move focus to select2 field
                    searchField[0].focus();
                });
                // read company name if exists on vessel.vue open
                vm.readCompanyName();
            },
            readCompanyName: function() {
                this.$nextTick(() => {
                    let vm = this;
                    if (vm.vessel.vessel_ownership.company_ownership && vm.vessel.vessel_ownership.company_ownership.company) {
                        var option = new Option(
                            vm.vessel.vessel_ownership.company_ownership.company.name, 
                            vm.vessel.vessel_ownership.company_ownership.company.name, 
                            true, 
                            true
                        );
                        console.log(option);
                        $(vm.$refs.company_name).append(option).trigger('change');
                    }
                });
            },
            initialiseRegoNoSelect: function(){
                let vm = this;
                // Vessel search
                $(vm.$refs.vessel_rego_nos).select2({
                    minimumInputLength: 2,
                    "theme": "bootstrap",
                    placeholder:"",
                    tags: true,
                    createTag: function (tag) {
                        return {
                            id: tag.term,
                            text: tag.term,
                            tag: true
                        };
                    },
                    ajax: {
                        url: api_endpoints.vessel_rego_nos,
                        dataType: 'json',
                        data: function(params) {
                            var query = {
                                term: params.term,
                                type: 'public',
                            }
                            return query;
                        },
                    },
                    templateSelection: function(data) {
                        console.log("templateSelection");
                        return vm.validateRegoNo(data.text);
                    },
                }).
                on("select2:select", function (e) {
                    console.log("select2:select");
                    if (!e.params.data.selected) {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log("No selection");
                        return false;
                    }
                    console.log("Process select2");
                    let data = e.params.data;
                    vm.$nextTick(async () => {
                        if (!data.tag) {
                            console.log("fetch existing vessel");
                            // fetch draft/approved vessel
                            await vm.lookupVessel(data.id);
                            // retrieve list of Vessel Owners
                            const res = await vm.$http.get(`${api_endpoints.vessel}${data.id}/lookup_vessel_ownership`);
                            await vm.parseVesselOwnershipList(res);
                        } else {
                            console.log("new vessel");
                            const validatedRego = vm.validateRegoNo(data.id);

                            vm.vessel = Object.assign({},
                                {
                                    new_vessel: true,
                                    rego_no: validatedRego,
                                    vessel_details: {
                                    },
                                    vessel_ownership: {
                                        company_ownership: {
                                        }
                                    }
                                });
                        }
                    });
                }).
                on("select2:unselect",function (e) {
                    console.log("select2:unselect")
                    var selected = $(e.currentTarget);
                    vm.vessel.rego_no = '';
                    vm.vessel = Object.assign({}, 
                        {   
                            vessel_details: {
                            },
                            vessel_ownership: {
                                company_ownership: {
                                }
                            }
                        });
                }).
                on("select2:open",function (e) {
                    console.log("select2:open")
                    const searchField = $(".select2-search__field")
                    // move focus to select2 field
                    searchField[0].focus();
                    // prevent spacebar from being used
                    searchField.on("keydown",function (e) {
                        if ([32,].includes(e.which)) {
                            // space bar
                            e.preventDefault();
                            return false;
                        } 
                    });
                });
                // read vessel.rego_no if exists on vessel.vue open
                vm.readRegoNo();
            },
            parseVesselOwnershipList: async function(res) {
                let vm = this;
                let individualOwner = false;
                let companyOwner = false;
                for (let vo of res.body) {
                    if (vo.individual_owner) {
                        individualOwner = true;
                    } else if (vo.company_ownership) {
                        companyOwner = true;
                    }
                }
                if (individualOwner) {
                    // read individual ownership data
                    vm.vessel.vessel_ownership.individual_owner = true;
                    await this.retrieveIndividualOwner();
                } else if (companyOwner) {
                    // read first company ownership data
                    vm.vessel.vessel_ownership.individual_owner = false;
                    const vo = res.body[0]
                    const companyId = vo.company_ownership.company.id;
                    await vm.lookupCompanyOwnership(companyId);
                    vm.readCompanyName();
                }
            },
            addEventListeners: function() {
                let vm = this;
                $('#ownership_percentage').on('keydown', (e) => {
                    if ([190, 110].includes(e.which)) {
                        e.preventDefault();
                        return false;
                    }
                });
            },
            readRegoNo: function() {
                let vm = this;
                if (vm.vessel.rego_no) {
                    var option = new Option(vm.vessel.rego_no, vm.vessel.rego_no, true, true);
                    $(vm.$refs.vessel_rego_nos).append(option).trigger('change');
                }
            },
            fetchVesselTypes: async function(){
                const response = await this.$http.get(api_endpoints.vessel_types_dict);
                for (let vessel_type of response.body) {
                    this.vesselTypes.push(vessel_type)
                }
            },
            lookupCompanyOwnership: async function(id) {
                console.log(id)
                const url = api_endpoints.lookupCompanyOwnership(id);
                const payload = {
                    "vessel_id": this.vessel.id,
                }
                const res = await this.$http.post(url, payload);
                const companyOwnershipData = res.body;
                console.log(res);
                if (companyOwnershipData && companyOwnershipData.company) {
                    this.$set(this.vessel.vessel_ownership, 'company_ownership', Object.assign({}, res.body));
                    this.vessel = Object.assign({}, this.vessel);
                }
            },

            lookupVessel: async function(id) {
                const url = api_endpoints.lookupVessel(id);
                await this.fetchReadonlyVesselCommon(url);
            },

            fetchVessel: async function() {
                // changed to read in application data for amendment/request amendment/renewal
                if (this.proposal.processing_status === 'Draft' && (!this.readonly || this.is_internal)) {
                    console.log("new")
                    this.vessel.rego_no = this.proposal.rego_no;
                    //this.vessel.vessel_id = this.proposal.vessel_id;
                    this.vessel.id = this.proposal.vessel_id;
                    let vessel_details = {};
                    vessel_details.vessel_type = this.proposal.vessel_type;
                    vessel_details.vessel_name = this.proposal.vessel_name;
                    //vessel_details.vessel_overall_length = this.proposal.vessel_overall_length;
                    vessel_details.vessel_length = this.proposal.vessel_length;
                    vessel_details.vessel_draft = this.proposal.vessel_draft;
                    vessel_details.vessel_beam = this.proposal.vessel_beam;
                    vessel_details.vessel_weight = this.proposal.vessel_weight;
                    vessel_details.berth_mooring = this.proposal.berth_mooring;
                    this.vessel.vessel_details = Object.assign({}, vessel_details);
                    this.readOwnershipFromProposal();
                } else {
                    let url = '';
                    if (this.proposal && this.proposal.id && this.proposal.vessel_details_id) {
                        url = helpers.add_endpoint_join(
                            //'/api/proposal/',
                            api_endpoints.proposal,
                            this.proposal.id + '/fetch_vessel/'
                        )
                    }
                    await this.fetchReadonlyVesselCommon(url);
                }
            },
            readOwnershipFromProposal: function() {
                let vessel_ownership = {};
                vessel_ownership.percentage = this.proposal.percentage;
                vessel_ownership.individual_owner = this.proposal.individual_owner;
                vessel_ownership.dot_name = this.proposal.dot_name;
                this.vessel.vessel_ownership = Object.assign({}, vessel_ownership);
                // company ownership
                this.vessel.vessel_ownership.company_ownership = {};
                if (this.proposal.company_ownership_name) {
                    this.vessel.vessel_ownership.company_ownership.company = {
                        name: this.proposal.company_ownership_name,
                    }
                }
                if (this.proposal.company_ownership_percentage) {
                    this.vessel.vessel_ownership.company_ownership.percentage = this.proposal.company_ownership_percentage;
                }
            },
            fetchReadonlyVesselCommon: async function(url) {
                const res = await this.$http.get(url);
                const vesselData = res.body;
                // read in vessel ownership data from Proposal if in Draft status
                if (this.proposal && this.proposal.processing_status === 'Draft' && !this.proposal.pending_amendment_request) {
                    if (vesselData && vesselData.rego_no) {
                        this.vessel.vessel_details = Object.assign({}, vesselData.vessel_details);
                        this.vessel.id = vesselData.id;
                        this.vessel.rego_no = vesselData.rego_no;
                        //this.vessel.read_only = true;
                    }
                } else {
                    // Proposal has been submitted
                    if (vesselData && vesselData.rego_no) {
                        this.vessel = Object.assign({}, vesselData);
                    }
                }
                this.readRegoNo();
                this.readCompanyName();
            },
        },
        mounted: function () {
            this.$nextTick(async () => {
                await this.fetchVesselTypes();
                if (this.proposal && this.keep_current_vessel) {
                    // fetches vessel data from proposal (saved as draft)
                    await this.fetchVessel();
                //} else if (!this.proposal && !this.creatingVessel) {
                } else if (!this.proposal) {
                    // route.params.vessel_id in this case is a vesselownership id
                    const url = api_endpoints.lookupVesselOwnership(this.$route.params.vessel_id);
                    this.fetchReadonlyVesselCommon(url);
                }
                this.initialiseRegoNoSelect();
                this.initialiseCompanyNameSelect();
                this.addEventListeners();
                // read in Renewal/Amendment vessel details
                //if (!this.keep_current_vessel && this.proposal.proposal_type.code !=='new' && this.proposal.application_type_code === 'mla') {
                if (!this.keep_current_vessel && this.proposal && this.proposal.proposal_type.code !=='new') {
                    await this.fetchVessel();
                } else if (!this.keep_current_vessel) {
                    // pass
                } else if (this.proposal && this.proposal.pending_amendment_request) {
                    // ensure an Amendment which has been sent back to draft with request amendment does not have the logic applied below
                    console.log("amendment request")
                    // pass
                } else if (this.proposal && this.proposal.processing_status === 'Draft' && 
                    !this.proposal.vessel_details_id && (this.proposal.proposal_type.code !=='new' || this.proposal.application_type_code === 'mla') &&
                    !this.vessel.rego_no
                ) {
                    console.log("Amendment/Renewal/Reissue & MLA");
                    let vm = this;
                    let res = null;
                    // if mla, get vessel from waiting list
                    if (this.proposal.waiting_list_application_id) {
                        const url = helpers.add_endpoint_join(
                            api_endpoints.proposal,
                            this.proposal.waiting_list_application_id + '/fetch_vessel/'
                        );
                        res = await this.$http.get(url);
                        console.log(res)
                    } else if (this.proposal.previous_application_vessel_details_id) {
                        // check vessel ownership on the previous application
                        const url = helpers.add_endpoint_join(
                            api_endpoints.proposal,
                            this.proposal.previous_application_id + '/fetch_vessel/'
                        );
                        res = await this.$http.get(url);
                    }
                    if (!this.proposal.rego_no && res && res.body && !res.body.vessel_ownership.end_date) {
                        this.vessel = Object.assign({}, res.body);
                        const payload = {
                            id: this.vessel.id,
                            tag: false,
                            selected: true,
                        }
                        $(vm.$refs.vessel_rego_nos).trigger({
                            type: 'select2:select',
                            params: {
                                data: payload,
                            }
                        });
                    }
                }
                // read in dot_name
                if (this.vessel.vessel_ownership && this.vessel.vessel_ownership.dot_name) {
                    this.dotName = this.vessel.vessel_ownership.dot_name;
                }
                // read in temporary_document_collection_id
                if (this.proposal && this.proposal.temporary_document_collection_id) {
                    this.temporary_document_collection_id = this.proposal.temporary_document_collection_id;
                }
            });
        },
        created: function() {
        },
    }
</script>

<style lang="css" scoped>
    input[type=text] {
        padding-left: 1em;
    }
</style>

