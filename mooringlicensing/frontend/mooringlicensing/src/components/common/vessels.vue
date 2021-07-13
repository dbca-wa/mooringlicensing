<template lang="html">
    <div id="vessels">
        <FormSection label="Registration Details" Index="registration_details">
            <div v-if="mooringLicenceCurrentVesselDisplayText" class="row form-group">
                <div class="col-sm-9">
                    {{ mooringLicenceCurrentVesselDisplayText }}
                    <s>Below you can enter the details of a new vessel to be added to the mooring licence if required, otherwise leave the vessel details blank.</s>
                    <strong>BB note: As discussed, for all renewal/amendments I am currently prefilling the vessel (unless sold) from the last application in the chain of applications linked to an approval.</strong>
                </div>
            </div>
            <div class="row form-group">
                <label for="vessel_search" class="col-sm-3 control-label">Vessel registration number</label>
                <div class="col-sm-9">
                    <select :disabled="readonly || editingVessel" id="vessel_search"  ref="vessel_rego_nos" class="form-control" style="width: 40%">
                    </select>
                </div>
            </div>
            <!--div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel registration number</label>
                <div class="col-sm-9">
                    <input :readonly="!editableVessel" type="text" class="form-control" id="vessel_registration_number" placeholder="" v-model="vessel.rego_no" required=""/>
                </div>
            </div-->
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel name</label>
                <div class="col-sm-9">
                    <input :readonly="readonly" type="text" class="form-control" id="vessel_name" placeholder="" v-model="vessel.vessel_details.vessel_name" required/>
                </div>
            </div>
            <!--div v-if="!vessel.read_only" class="row form-group"-->
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
                            <!--input 
                            :readonly="readonly" 
                            type="text" 
                            class="form-control" 
                            id="registered_owner_company_name" 
                            placeholder="Company name" 
                            v-model="vessel.vessel_ownership.org_name" 
                            required=""
                            /-->
                        </div>
                    </div>
                </div>
            </div>
            <!--div v-else class="row form-group">
                <label for="" class="col-sm-3 control-label">Registration vessel owner</label>
                <div class="col-sm-9">
                    <div class="row">
                        <div class="col-sm-9">
                            {{   registeredOwner }}
                        </div>
                    </div>
                </div>
            </div-->
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
                    v-model="vessel.vessel_ownership.company_ownership.percentage" 
                    required=""
                    />
                </div>

            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Name as shown on DoT registration papers</label>
                <!--label for="" class="col-sm-3 control-label">Permanent or usual place</label-->
                <div class="col-sm-9">
                    <input :readonly="readonly" type="text" class="col-sm-9 form-control" id="dot_name" placeholder="" v-model="dotName" required=""/>
                </div>
            </div>

            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Permanent or usual place of berthing/mooring of vessel</label>
                <!--label for="" class="col-sm-3 control-label">Permanent or usual place</label-->
                <div class="col-sm-9">
                    <input :readonly="readonly" type="text" class="col-sm-9 form-control" id="berth_mooring" placeholder="" v-model="vessel.vessel_details.berth_mooring" required=""/>
                </div>
            </div>
            <div v-if="showDotRegistrationPapers" class="row form-group">
                <label for="" class="col-sm-3 control-label">Copy of DoT registration papers</label>
                <div class="col-sm-9">
                    <FileField 
                        :readonly="readonly"
                        ref="vessel_registration_documents"
                        name="vessel-registration-documents"
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
                        :readonly="readonly"
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
                    <input :readonly="readonly" type="number" min="1" class="form-control" id="vessel_length" placeholder="" v-model="vessel.vessel_details.vessel_length" required=""/>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Overall length of vessel</label>
                <div class="col-sm-2">
                    <input :readonly="readonly" type="number" min="1" class="form-control" id="overall_length" placeholder="" v-model="vessel.vessel_details.vessel_overall_length" required=""/>
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
            creatingVessel:{
                type: Boolean,
            },
            editingVessel:{
                type: Boolean,
            },
        },
        watch: {
            individualOwner: async function() {
                if (this.individualOwner) {
                    console.log("watch indiv")
                    await this.retrieveIndividualOwner();
                }
            },
        },
        computed: {
            mooringLicenceCurrentVesselDisplayText: function() {
                let displayText = '';
                if (this.proposal.mooring_licence_vessels && this.proposal.mooring_licence_vessels.length) {
                    displayText += `Your mooring licence ${this.proposal.approval_lodgement_number} 
                    currently lists the following vessels ${this.proposal.mooring_licence_vessels.toString()}.`;
                }
                return displayText;
            },
            showDotRegistrationPapers: function() {
                let retVal = false;
                if (this.proposal && this.proposal.id && this.companyOwner) {
                    retVal = true
                }
                return retVal;
            },
            /*
            companyOwnerPercentage: function() {
                if (this.vessel.vessel_ownership.company_ownership.percentage) {
                    return this.vessel.vessel_ownership.company_ownership.percentage;
                }
            },
            */
            companyOwner: function() {
                //let returnVal = false;
                if (this.vessel && this.vessel.vessel_ownership && this.vessel.vessel_ownership.individual_owner === false) {
                    //returnVal = this.vessel.vessel_ownership.individual_owner;
                    return true;
                }
                //return returnVal;
            },
            individualOwner: function() {
                if (this.vessel && this.vessel.vessel_ownership && this.vessel.vessel_ownership.individual_owner) {
                    return true;
                }
            },
            /*
            registeredOwner: function() {
                if (this.vessel && this.vessel.vessel_ownership) {
                    return this.vessel.vessel_ownership.registered_owner;
                }
            },
            orgName: function() {
                if (this.vessel && this.vessel.vessel_ownership) {
                    return this.vessel.vessel_ownership.org_name;
                }
            },
            editableVesselDetails: function() {
                let retVal = false;
                if (this.creatingVessel) {
                    retVal = true;
                } else if (!this.readonly) {
                    // front-end lookup 
                    if (this.vessel.vessel_details.hasOwnProperty('read_only')) {
                        retVal = !this.vessel.vessel_details.read_only;
                    // vessel stored on Proposal
                    } else if (this.proposal) {
                        retVal = this.proposal.editable_vessel_details;
                    }
                }
                return retVal;
            },
            */
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
                if (this.proposal && this.proposal.id) {
                    url = helpers.add_endpoint_join(
                        api_endpoints.proposal,
                        this.proposal.id + '/process_vessel_registration_document/'
                    )
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

        },
        methods:{
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
                /*
                if (!data.disabled && data.text && typeof(data.text) === "string") {
                    // force uppercase and no whitespace
                    data = data.text.toUpperCase();
                    console.log(data);
                    data = data.text.replace(/\s/g,"");
                    data = data.text.replace(/\W/g,"");
                }
                */
                return data;
            },
            initialiseCompanyNameSelect: async function(){
                let vm = this;
                // Vessel search
                $(vm.$refs.company_name).select2({
                    minimumInputLength: 2,
                    "theme": "bootstrap",
                    allowClear: true,
                    //placeholder:"Select Vessel Registration",
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
                                //create_vessel: vm.creatingVessel,
                                //org_name: vm.orgName,
                            }
                            return query;
                        },
                    },
                    //templateSelection: vm.validateRegoNo,
                    //templateResult: vm.validateRegoNo,
                    /*
                    templateSelection: function(data) {
                        return vm.validateRegoNo(data.text);
                    },
                    */
                }).
                on("select2:select", async function (e) {
                    var selected = $(e.currentTarget);
                    let data = e.params.data.id;
                    console.log(e.params.data)
                    vm.$nextTick(async () => {
                        //if (!isNew) {
                        if (!e.params.data.tag) {
                            //console.log("fetch new vessel");
                            // fetch draft/approved vessel
                            //vm.lookupVessel(data);
                            await vm.lookupCompanyOwnership(data);
                            //vm.readCompanyName();
                        } else {
                            //data = vm.validateRegoNo(data);
                            let text = e.params.data.text;
                            //vm.vessel.vessel_ownership.company_ownership.company.name = text;

                            let companyOwnership = {
                                company: {
                                    name: text,
                                }
                            }
                            vm.vessel.vessel_ownership.company_ownership = Object.assign({}, companyOwnership);
                            console.log(data)
                        }
                    });
                }).
                on("select2:unselect",function (e) {
                    //var selected = $(e.currentTarget);
                    let companyOwnership = {
                        company: {
                            //name: text,
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
                        //console.log("readCompanyName")
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
                    allowClear: true,
                    //placeholder:"Select Vessel Registration",
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
                                create_vessel: vm.creatingVessel,
                                //org_name: vm.orgName,
                                company_name: vm.companyName,
                            }
                            return query;
                        },
                    },
                    //templateSelection: vm.validateRegoNo,
                    //templateResult: vm.validateRegoNo,
                    templateSelection: function(data) {
                        return vm.validateRegoNo(data.text);
                    },
                }).
                on("select2:select", function (e) {
                    var selected = $(e.currentTarget);
                    let data = e.params.data.id;
                    vm.$nextTick(async () => {
                        //if (!isNew) {
                        if (!e.params.data.tag) {
                            console.log("fetch existing vessel");
                            // fetch draft/approved vessel
                            await vm.lookupVessel(data);
                            console.log("individual")
                            if (this.proposal && this.proposal.id) {
                                await vm.retrieveIndividualOwner();
                            } else {
                                // retrieve list of Vessel Owners
                                const res = await vm.$http.get(`${api_endpoints.vessel}${data}/lookup_vessel_ownership`);
                                console.log(res);
                                vm.parseVesselOwnershipList(res);
                                /*
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
                                } else if (companyOwner) {
                                    // read first company ownership data
                                    vm.vessel.vessel_ownership.individual_owner = false;
                                    const vo = res.body[0]
                                    const companyId = vo.company_ownership.company.id;
                                    await vm.lookupCompanyOwnership(companyId);
                                    vm.readCompanyName();
                                }
                                */
                            }
                        } else {
                            console.log("new vessel");
                            data = vm.validateRegoNo(data);

                            vm.vessel = Object.assign({},
                                {
                                    new_vessel: true,
                                    rego_no: data,
                                    vessel_details: {
                                        //read_only: false,
                                    },
                                    vessel_ownership: {
                                        company_ownership: {
                                        }
                                        //registered_owner: 'current_user',
                                    }
                                });
                        }
                    });
                }).
                on("select2:unselect",function (e) {
                    var selected = $(e.currentTarget);
                    vm.vessel.rego_no = '';
                    vm.vessel = Object.assign({}, 
                        {   
                            vessel_details: {
                                //read_only: false,
                            },
                            vessel_ownership: {
                                company_ownership: {
                                }
                                //registered_owner: 'current_user',
                            }
                        });
                }).
                on("select2:open",function (e) {
                    const searchField = $(".select2-search__field")
                    // move focus to select2 field
                    searchField[0].focus();
                    // prevent spacebar from being used
                    searchField.on("keydown",function (e) {
                        //console.log(e.which);
                        if ([32,].includes(e.which)) {
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
            /*
            fetchVesselRegoNos: async function() {
                const response = await this.$http.get(api_endpoints.vessel_rego_nos);
                for (let rego of response.body) {
                    this.vesselRegoNos.push(rego)
                }
            },
            */
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
            /*
            lookupVessel: async function(id) {
                const res = await this.$http.get(api_endpoints.lookupVessel(id));
                const vesselData = res.body;
                console.log(res);
                if (vesselData && vesselData.rego_no) {
                    if (this.creatingVessel) {
                        console.log("lookup - creating vessel")
                        this.vessel.vessel_details = Object.assign({}, vesselData.vessel_details);
                    } else {
                        console.log("lookup - not creating vessel")
                        this.vessel = Object.assign({}, vesselData);
                    }
                }
            },
            */
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
                    //this.$set(this.vessel.vessel_ownership, 'company_ownership', Object.assign({}, res.body));
                    this.$set(this.vessel.vessel_ownership, 'company_ownership', Object.assign({}, res.body));
                    this.vessel = Object.assign({}, this.vessel);
                    /*
                    this.vessel.id = vesselData.id;
                    this.vessel.rego_no = vesselData.rego_no;
                    this.vessel.read_only = true;
                    */
                }
            },

            lookupVessel: async function(id) {
                const url = api_endpoints.lookupVessel(id);
                await this.fetchReadonlyVesselCommon(url);
                /*
                const res = await this.$http.get(api_endpoints.lookupVessel(id));
                const vesselData = res.body;
                //console.log(res);
                if (vesselData && vesselData.rego_no) {
                    this.vessel.vessel_details = Object.assign({}, vesselData.vessel_details);
                    this.vessel.id = vesselData.id;
                    this.vessel.rego_no = vesselData.rego_no;
                    this.vessel.read_only = true;
                }
                */
            },

            fetchVessel: async function() {
                if (this.proposal.processing_status === 'Draft' && !this.proposal.vessel_details_id) {
                    console.log("new")
                    this.vessel.rego_no = this.proposal.rego_no;
                    //this.vessel.vessel_id = this.proposal.vessel_id;
                    this.vessel.id = this.proposal.vessel_id;
                    let vessel_details = {};
                    vessel_details.vessel_type = this.proposal.vessel_type;
                    vessel_details.vessel_name = this.proposal.vessel_name;
                    vessel_details.vessel_overall_length = this.proposal.vessel_overall_length;
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
                /*
                if (vesselData && vesselData.rego_no) {
                    this.vessel = Object.assign({}, vesselData);
                }
                */
                // read in vessel ownership data from Proposal if in Draft status
                if (this.proposal && this.proposal.processing_status === 'Draft') {
                    if (vesselData && vesselData.rego_no) {
                        this.vessel.vessel_details = Object.assign({}, vesselData.vessel_details);
                        this.vessel.id = vesselData.id;
                        this.vessel.rego_no = vesselData.rego_no;
                        //this.vessel.read_only = true;
                        /*
                        // vessel ownership
                        this.vessel.vessel_ownership.org_name = this.proposal.org_name;
                        this.vessel.vessel_ownership.percentage = this.proposal.percentage;
                        this.vessel.vessel_ownership.individual_owner = this.proposal.individual_owner;
                        */
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
                if (this.proposal && this.proposal.proposal_type.code==='new') {
                    await this.fetchVessel();
                } else if (!this.proposal && !this.creatingVessel) {
                    // route.params.vessel_id in this case is a vesselownership id
                    const url = api_endpoints.lookupVesselOwnership(this.$route.params.vessel_id);
                    this.fetchReadonlyVesselCommon(url);
                }
                this.initialiseRegoNoSelect();
                this.initialiseCompanyNameSelect();
                this.addEventListeners();
                // read in Renewal/Amendment vessel details
                if (this.proposal.processing_status === 'Draft' && !this.proposal.vessel_details_id && !(this.proposal.proposal_type.code==='new')) {
                    let vm = this;
                    let res = null;
                    // check vessel ownership on the previous application
                    if (this.proposal.previous_application_vessel_details_id) {
                        const url = helpers.add_endpoint_join(
                            api_endpoints.proposal,
                            this.proposal.previous_application_id + '/fetch_vessel/'
                        );
                        res = await this.$http.get(url);
                    }
                    //if (this.proposal.vessel_id && res.body && !res.body.vessel_ownership.end_date) {
                    if (!this.proposal.rego_no && res.body && !res.body.vessel_ownership.end_date) {
                        this.vessel = Object.assign({}, res.body);
                        const payload = {
                            id: this.vessel.id,
                            tag: false,
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
                if (this.proposal.dot_name) {
                    this.dotName = this.proposal.dot_name;
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

