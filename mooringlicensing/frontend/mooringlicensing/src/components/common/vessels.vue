<template lang="html">
    <div id="vessels">
        <FormSection label="Registration Details" Index="registration_details" v-if="!forEndorser">
            <div class="row form-group">
                <label for="vessel_search" class="col-sm-3 control-label">Vessel registration <span style="color: red;">*</span></label>
                <div class="col-sm-9">
                    <select :disabled="readonly" id="vessel_search" ref="vessel_rego_nos" class="form-control"
                        style="width: 40%">
                        <option></option>
                    </select>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel name <span style="color: red;">*</span></label>
                <div class="col-sm-9">
                    <input :readonly="readonly" type="text" class="form-control" id="vessel_name" placeholder=""
                        v-model="vessel.vessel_details.vessel_name" required />
                </div>
            </div>
            <div v-if="!readonly || (vessel.vessel_ownership.individual_owner && vessel.vessel_ownership.owner_name)" class="row form-group">
                <label for="" class="col-sm-3 control-label">Registration vessel owner <span style="color: red;">*</span></label>
                <div v-if="!readonly" class="col-sm-9">
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
                            <label for="registered_owner_current_user" class="control-label">{{ profileFullName }}</label>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-sm-3">
                            <input
                                @change="clearOrgName"
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
                    </div>
                </div>
                <div v-else>
                    <div class="col-sm-3">
                        <input :readonly="readonly" type="text" class="form-control" id="vessel_name" placeholder=""
                        v-model="vessel.vessel_ownership.owner_name" required />
                    </div>
                </div>
            </div>
            <transition>
                <div v-show="companyOwner" class="row form-group">
                    <label for="" class="col-sm-3 control-label">Company</label>
                    <div class="col-sm-8">
                        <select :disabled="readonly" id="company_name" ref="company_name" class="form-control"
                            style="width: 40%" />
                    </div>
                </div>
            </transition>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Ownership percentage <span style="color: red;"><span style="color: red;">*</span></span></label>
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
                <div v-if="companyOwner" class="col-sm-2">
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
                <label for="" class="col-sm-3 control-label">Owner name as shown on DoT registration (SURNAME FIRST MIDDLE) <span style="color: red;">*</span></label>
                <div class="col-sm-9">
                    <input
                        :readonly="readonly"
                        type="text"
                        class="col-sm-9 form-control"
                        id="dot_name"
                        placeholder=""
                        v-model="vessel.vessel_ownership.dot_name"
                        required=""
                    />
                </div>
            </div>

            <div v-show="false" class="row form-group">
                <label for="" class="col-sm-3 control-label">Permanent or usual place of berthing/mooring of vessel</label>
                <div class="col-sm-9">
                    <input :readonly="readonly" type="text" class="col-sm-9 form-control" id="berth_mooring" placeholder=""
                        v-model="vessel.vessel_details.berth_mooring" required="" />
                </div>
            </div>
            <!-- Start:new file field -->
            <transition>
                <div v-if="showDotRegistrationPapers" class="row form-group">
                    <label for="" class="col-sm-3 control-label">Copy of registration papers</label>
                    <div class="col-sm-9">
                        <FileField
                            :readonly="hinReadonly"
                            ref="vessel_rego_document"
                            name="vessel_rego_document"
                            :isRepeatable="true"
                            :documentActionUrl="vesselRegoDocumentUrl"
                            :replace_button_by_text="true"
                        />
                    </div>
                </div>
            </transition>
            <!-- End:new file field -->

            <transition>
                <div v-if="showProofOfVesselOwnership" class="row form-group">
                    <label for="" class="col-sm-3 control-label">A statutory declaration is required as proof of vessel ownership</label>
                    <div class="col-sm-9" v-if="proposal && proposal.stat_dec_form">
                        Download form <a target="_blank" :href="proposal.stat_dec_form">here</a>
                    </div>
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
            </transition>

        </FormSection>
        <FormSection label="Vessel Details" Index="vessel_details">
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel length (m) <span style="color: red;">*</span></label>
                <div class="col-sm-2">
                    <input :readonly="readonly" type="number" min="1" class="form-control" id="vessel_length" placeholder=""
                        v-model="vessel.vessel_details.vessel_length" required="" @change="emitVesselLength" />
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Displacement tonnage <span style="color: red;">*</span></label>
                <div class="col-sm-2">
                    <input :readonly="readonly" type="number" min="1" class="form-control" id="displacement_tonnage"
                        placeholder="" v-model="vessel.vessel_details.vessel_weight" required="" />
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Draft (m) <span style="color: red;">*</span></label>
                <div class="col-sm-2">
                    <input :readonly="readonly" type="number" min="1" class="form-control" id="draft" placeholder=""
                        v-model="vessel.vessel_details.vessel_draft" required="" />
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel Type <span style="color: red;">*</span></label>
                <div class="col-sm-4">
                    <select :disabled="readonly" class="form-control" style="width:40%"
                        v-model="vessel.vessel_details.vessel_type">
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
import FormSection from '@/components/forms/section_toggle.vue'
import FileField from '@/components/forms/filefield_immediate.vue'
require("select2/dist/css/select2.min.css");
require("select2-bootstrap-theme/dist/select2-bootstrap.min.css");
import {
    api_endpoints,
    helpers
}
    from '@/utils/hooks'

export default {
    name: 'vessels',
    data: function () {
        return {
            dotName: '',
            vessel: {
                vessel_details: {},
                vessel_ownership: {
                    company_ownership: {
                        company: {
                        }
                    },
                }
            },
            vesselTypes: [],
            vesselRegoNos: [],
            selectedRego: null,
            temporary_document_collection_id: null,
            max_vessel_length_tuple: null,
            max_vessel_length_for_aa_component: -1,
            include_max_vessel_length_for_aa_component: null,
        }
    },
    components: {
        FormSection,
        FileField,
    },
    props: {
        proposal: {
            type: Object,
        },
        profile: {
            type: Object,
            required: true
        },
        readonly: {
            type: Boolean,
            default: true,
        },
        is_internal: {
            type: Boolean,
            default: false,
        },
        keep_current_vessel: {
            type: Boolean,
        },
        forEndorser: {
            type: Boolean,
            default: false,
        }
    },
    watch: {
        vessel: {
            handler: async function () {
                await this.vesselChanged();
            },
            deep: true
        },
        max_vessel_length_tuple: {
            handler: function () {
                this.$emit("updateMaxVesselLengthForMainComponent", this.max_vessel_length_tuple)
            }
        },
        max_vessel_length_for_aa_component: {
            handler: function () {
                this.$emit("updateMaxVesselLengthForAAComponent", this.max_vessel_length_for_aa_component)
            }
        },
    },
    computed: {
        vesselLength: function () {
            let length = 0;
            if (this.vessel && this.vessel.vessel_details && this.vessel.vessel_details.vessel_length) {
                length = this.vessel.vessel_details.vessel_length;
            }
            return length;
        },
        hinReadonly: function () {
            let readonly = true;
            if (this.proposal && this.proposal.processing_status === 'Draft') {
                readonly = false;
            }
            return readonly;
        },
        companyOwnershipName: function () {
            let companyName = null;
            if (this.vessel.vessel_ownership && this.vessel.vessel_ownership.company_ownership && this.vessel.vessel_ownership.company_ownership.company) {
                companyName = this.vessel.vessel_ownership.company_ownership.company.name;
            }
            return companyName
        },
        existingVesselOwnership: function () {
            // Found that there is a case where there is no vessel_ownership.id is defined (I don't know why), which results in javascript error.
            // Therefore rewrite the above line avoiding accessing the vessel_ownership.id
            if (this.vessel.vessel_ownership) {
                if (this.vessel.vessel_ownership.percentage) {
                    return true
                }
                if (this.vessel.vessel_ownership.company_ownership) {
                    if (this.vessel.vessel_ownership.company_ownership.percentage) {
                        return true
                    }
                }
            }
            return false
        },
        mooringLicenceCurrentVesselDisplayText: function () {
            let displayText = '';
            if (this.proposal && this.proposal.mooring_licence_vessels && this.proposal.mooring_licence_vessels.length) {
                displayText += `Your mooring site licence ${this.proposal.approval_lodgement_number}
                    currently lists the following vessels ${this.proposal.mooring_licence_vessels.toString()}.`;
            }
            return displayText;
        },
        currentVesselDisplayText: function () {
            let displayText = '';
            if (this.proposal && this.proposal.approval_vessel_rego_no) {
                displayText += `Your ${this.proposal.approval_type_text} ${this.proposal.approval_lodgement_number}
                    lists a vessel with registration number ${this.proposal.approval_vessel_rego_no}.`;
            }
            return displayText;
        },
        showProofOfVesselOwnership: function(){
            let retVal = false
            if (this.companyOwner){
                retVal = true
            }
            return retVal
        },
        showDotRegistrationPapers: function () {
            let retVal = false;
            if (this.companyOwner) {
                retVal = true
            }
            return retVal;
        },
        companyOwner: function () {
            if (this.vessel && this.vessel.vessel_ownership && this.vessel.vessel_ownership.individual_owner == false) {
                return true;
            }
            return false
        },
        individualOwner: function () {
            if (this.vessel && this.vessel.vessel_ownership && this.vessel.vessel_ownership.individual_owner == true) {
                return true;
            }
            return false
        },
        profileFullName: function () {
            if (this.profile) {
                if (this.profile.legal_first_name) {
                    return this.profile.legal_first_name + ' ' + this.profile.legal_last_name;
                } else {
                    return this.profile.first_name + ' ' + this.profile.last_name;
                }
            }
            return ''
        },
        fee_invoice_url: function () {
            return this.fee_paid ? this.proposal.fee_invoice_url : '';
        },
        vesselRegoDocumentUrl: function () {
            let url = ''
            if (this.proposal && this.proposal.id){
                // Call a function defined in the ProposalViewSet
                url = '/api/proposal/' + this.proposal.id + '/vessel_rego_document/'
            }
            else if (this.vesselOwnership.proposal_id){
                url = '/api/proposal/' + this.vesselOwnership.proposal_id + '/vessel_rego_document/'
            }
            return url
        },
        hullIdentificationNumberDocumentUrl: function () {
            let url = '';
            if (this.proposal && this.proposal.id) {
                url = '/api/proposal/' + this.proposal.id + '/hull_identification_number_document/'
            }
            else if (this.vesselOwnership.proposal_id){
                url = '/api/proposal/' + this.vesselOwnership.proposal_id + '/hull_identification_number_document/'
            }
            return url
        },
        companyName: function () {
            if (this.vessel.vessel_ownership.company_ownership && this.vessel.vessel_ownership.company_ownership.company) {
                return this.vessel.vessel_ownership.company_ownership.company.name;
            }
        },
        vesselDetails: function () {
            return this.vessel ? this.vessel.vessel_details : {};
        },
        vesselOwnership: function () {
            return this.vessel ? this.vessel.vessel_ownership : {};
        },
        previousApplicationVesselDetails: function () {
            return this.proposal ? this.proposal.previous_application_vessel_details_obj : null;
        },
        previousApplicationVesselOwnership: function () {
            return this.proposal ? this.proposal.previous_application_vessel_ownership_obj : null;
        },
    },
    methods: {
        emitVesselLength: function () {
            this.$nextTick(() => {
                this.$emit("updateVesselLength", this.vesselLength)
            });
        },
        vesselChanged: async function () {
            let vesselChanged = false
            let vesselOwnershipChanged = false

            await this.$nextTick(() => {
                if (!this.previousApplicationVesselDetails || !this.previousApplicationVesselOwnership || (this.proposal && this.proposal.null_vessel_on_create)) {
                    if (
                        Number(this.vesselDetails.vessel_draft) ||
                        Number(this.vesselDetails.vessel_length) ||
                        (this.vesselDetails.vessel_name && this.vesselDetails.vessel_name.trim()) ||
                        this.vesselDetails.vessel_type ||
                        Number(this.vesselDetails.vessel_weight) ||
                        Number(this.vesselOwnership.percentage) ||
                        this.vessel.new_vessel
                    ) {
                        vesselChanged = true;
                    }
                } else {
                    if (
                        Number(this.vesselDetails.vessel_draft) != Number(this.previousApplicationVesselDetails.vessel_draft) ||
                        Number(this.vesselDetails.vessel_length) != Number(this.previousApplicationVesselDetails.vessel_length) ||
                        (this.vesselDetails.vessel_name && this.vesselDetails.vessel_name.trim() !== this.previousApplicationVesselDetails.vessel_name.trim()) ||
                        this.vesselDetails.vessel_type !== this.previousApplicationVesselDetails.vessel_type ||
                        Number(this.vesselDetails.vessel_weight) != Number(this.previousApplicationVesselDetails.vessel_weight) ||
                        Number(this.vesselOwnership.percentage) != Number(this.previousApplicationVesselOwnership.percentage) ||
                        this.vessel.new_vessel
                    ) {
                        vesselChanged = true;
                    }

                    // Ownership
                    if (this.previousApplicationVesselOwnership.company_ownership) {
                        if (this.vesselOwnership.individual_owner) {
                            // Company ownership --> Individual ownership
                            vesselOwnershipChanged = true
                        } else {
                            if (this.vesselOwnership.company_ownership) {
                                if (this.previousApplicationVesselOwnership.company_ownership.company && this.vesselOwnership.company_ownership.company) {
                                    if (this.previousApplicationVesselOwnership.company_ownership.company.name && this.vesselOwnership.company_ownership.company.name) {
                                        if (this.previousApplicationVesselOwnership.company_ownership.company.name.trim() !== this.vesselOwnership.company_ownership.company.name.trim()) {
                                            // Company name changed
                                            vesselOwnershipChanged = true
                                        }
                                    }
                                }
                                if (this.previousApplicationVesselOwnership.company_ownership && this.previousApplicationVesselOwnership.company_ownership.percentage && this.vesselOwnership.company_ownership.percentage) {
                                    if (Number(this.previousApplicationVesselOwnership.company_ownership.percentage) !== Number(this.vesselOwnership.company_ownership.percentage)) {
                                        // Company percentage changed
                                        vesselOwnershipChanged = true
                                    }
                                }
                            }
                        }
                    } else { //not company ownership
                        if (!this.vesselOwnership.individual_owner) { //company ownership
                            // Individual ownership --> Company ownership
                            vesselOwnershipChanged = true
                        }
                    }
                }
            })
            await this.$emit("vesselChanged", vesselChanged)

            const missingVessel = this.vessel.rego_no ? false : true;
            await this.$emit("noVessel", missingVessel)

            await this.$emit("updateVesselOwnershipChanged", vesselOwnershipChanged)
        },
        addToTemporaryDocumentCollectionList(temp_doc_id) {
            this.temporary_document_collection_id = temp_doc_id;
        },
        retrieveIndividualOwner: async function () {
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
        clearOrgName: function () {
            this.$nextTick(() => {
                if (this.individualOwner) {
                    this.vessel.vessel_ownership.org_name = '';
                }
            })
        },
        validateRegoNo: function (data) {
            // force uppercase and no whitespace
            data = data.toUpperCase();
            data = data.replace(/\s/g, "");
            data = data.replace(/\W/g, "");
            return data;
        },
        initialiseCompanyNameSelect: async function () {
            let vm = this;
            // Vessel search
            $(vm.$refs.company_name).select2({
                minimumInputLength: 2,
                "theme": "bootstrap",
                placeholder: "",
                tags: true,
                ajax: {
                    url: api_endpoints.company_names,
                    dataType: 'json',
                    data: function (params) {
                        var query = {
                            term: params.term,
                            type: 'public',
                        }
                        return query;
                    },
                    processResults: function(data, params) {
                        const searchOption = {
                            id: params.term,
                            text: params.term ,
                            tag : true
                        };
                        return {
                            results: [searchOption,
                                ...data.results
                                
                            ],
                        };
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
                            vm.vessel.vessel_ownership = Object.assign({}, vm.vessel.vessel_ownership, { company_ownership: companyOwnership });
                        }
                    });
                }).
                on("select2:unselect", function (e) {
                    let companyOwnership = {
                        company: {
                        }
                    }
                    vm.vessel.vessel_ownership.company_ownership = Object.assign({}, companyOwnership);
                    vm.vessel = Object.assign({}, vm.vessel);
                }).
                on("select2:open", function (e) {
                    const searchField = $(".select2-search__field")
                    // move focus to select2 field
                    searchField[0].focus();
                });
            // read company name if exists on vessel.vue open
            vm.readCompanyName();
        },
        readCompanyName: function () {
            this.$nextTick(() => {
                let vm = this;
                if (vm.vessel.vessel_ownership && vm.vessel.vessel_ownership.company_ownership && vm.vessel.vessel_ownership.company_ownership.company) {
                    var option = new Option(
                        vm.vessel.vessel_ownership.company_ownership.company.name,
                        vm.vessel.vessel_ownership.company_ownership.company.name,
                        true,
                        true
                    );
                    $(vm.$refs.company_name).append(option).trigger('change');
                }
            });
        },
        initialiseRegoNoSelect: function () {
            let vm = this
            let allow_add_new_vessel = !vm.keep_current_vessel

            $(vm.$refs.vessel_rego_nos).select2({
                minimumInputLength: 2,
                "theme": "bootstrap",
                placeholder: "",
                allowClear: true,
                tags: allow_add_new_vessel,
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
                    data: function (params) {  // This function is called before the ajax call.
                        var query = {
                            term: params.term,
                            type: 'public',
                            allow_add_new_vessel: allow_add_new_vessel,
                            proposal_id: vm.proposal.id,
                        }
                        return query;
                    },
                    processResults: function(data, params){  // This function is called after the results are returned.
                                                             // Mainly used for modifying the items before being displayed.
                        return {
                            results: data.results,  // This is the array of items to be displayed
                        }
                    }
                },
                templateSelection: function (data) {
                    return vm.validateRegoNo(data.text);
                },
            }).
                on("select2:select", function (e) {
                    if (!e.params.data.selected) {
                        e.preventDefault();
                        e.stopPropagation();
                        return false;
                    }
                    let data = e.params.data;
                    vm.$nextTick(async () => {
                        let max_length = 0
                        if (!data.tag) {
                            var error_status = null;
                            // fetch draft/approved vessel
                            try {
                                await vm.lookupVessel(data.id);
                            } catch(e) {
                                error_status = e.status;
                                console.error(e);
                            } finally {
                                if (error_status == '400'){
                                    //empty the search
                                    var searchValue = "";
                                    var err = "The selected vessel is already listed with RIA under another owner";
                                    await swal({
                                        title: 'Selection Error',
                                        text: err,
                                        type: "error",
                                    })
                                    vm.vessel.rego_no = null;
                                    var option = new Option(searchValue, searchValue, true, true);
                                    $(vm.$refs.vessel_rego_nos).append(option).trigger('change');
                                    
                                } 
                                // retrieve list of Vessel Owners
                                const res = await vm.$http.get(`${api_endpoints.vessel}${data.id}/lookup_vessel_ownership`);
                                await vm.parseVesselOwnershipList(res);
                                
                                try {
                                    const res_for_length = await vm.$http.get(`${api_endpoints.proposal}${vm.proposal.id}/get_max_vessel_length_for_aa_component?vid=${data.id}`);
                                    vm.max_vessel_length_for_aa_component = res_for_length.body.max_length
                                } catch(e) {
                                    console.error(e);
                                }
                                
                            }
                        } else {
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
                            // Get minimum Max vessel length which doesn't require payments
                            vm.max_vessel_length_for_aa_component = 0
                        }
                    });
                }).
                on("select2:unselect", function (e) {
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
                on("select2:open", function (e) {
                    const searchField = $(".select2-search__field")
                    // move focus to select2 field
                    searchField[0].focus();
                    // prevent spacebar from being used
                    searchField.on("keydown", function (e) {
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
        parseVesselOwnershipList: async function (res) {
            let vm = this;
            let individualOwner = false;
            let companyOwner = false;
            for (let vo of res.body) {
                if (vo.individual_owner) {
                    individualOwner = true  // Is this correct?  This variable is overwritten by the last loop accessing here.
                } else if (vo.company_ownership) {
                    companyOwner = true  // Is this correct?  This variable is overwritten by the last loop accessing here.
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
                const companyId = vo.company_ownership.company.id
                await vm.lookupCompanyOwnership(companyId);
                vm.readCompanyName();
            }
        },
        addEventListeners: function () {
            let vm = this;
            $('#ownership_percentage').on('keydown', (e) => {
                if ([190, 110].includes(e.which)) {
                    e.preventDefault();
                    return false;
                }
            });
        },
        readRegoNo: function () {
            let vm = this;
            if (vm.vessel.rego_no) {
                var option = new Option(vm.vessel.rego_no, vm.vessel.rego_no, true, true);
                $(vm.$refs.vessel_rego_nos).append(option).trigger('change');
            }
        },
        fetchVesselTypes: async function () {
            const response = await this.$http.get(api_endpoints.vessel_types_dict);
            for (let vessel_type of response.body) {
                this.vesselTypes.push(vessel_type)
            }
        },
        lookupCompanyOwnership: async function (id) {
            const url = api_endpoints.lookupCompanyOwnership(id);
            const payload = {
                "vessel_id": this.vessel.id,
            }
            const res = await this.$http.post(url, payload);
            const companyOwnershipData = res.body;
            if (companyOwnershipData && companyOwnershipData.company) {
                this.$set(this.vessel.vessel_ownership, 'company_ownership', Object.assign({}, res.body));
                this.vessel = Object.assign({}, this.vessel);
            }
        },

        lookupVessel: async function (id) {
            const url = api_endpoints.lookupVessel(id);
            await this.fetchReadonlyVesselCommon(url);
        },
        fetchDraftData: function () {
            console.log('fetchDraftData');
            this.vessel.rego_no = this.proposal.rego_no;
            this.vessel.id = this.proposal.vessel_id;
            let vessel_details = {};
            vessel_details.vessel_type = this.proposal.vessel_type;
            vessel_details.vessel_name = this.proposal.vessel_name;
            vessel_details.vessel_length = this.proposal.vessel_length;
            vessel_details.vessel_draft = this.proposal.vessel_draft;
            vessel_details.vessel_beam = this.proposal.vessel_beam;
            vessel_details.vessel_weight = this.proposal.vessel_weight;
            vessel_details.berth_mooring = this.proposal.berth_mooring;
            this.vessel.vessel_details = Object.assign({}, vessel_details);
            this.readOwnershipFromProposal();
        },
        readOwnershipFromProposal: function () {
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
        fetchReadonlyVesselCommon: async function (url) {
            const res = await this.$http.get(url);
            const vesselData = res.body;
            // read in vessel ownership data from Proposal if in Draft status
            if (this.proposal && this.proposal.processing_status === 'Draft' && !this.proposal.pending_amendment_request) {
                if (vesselData && vesselData.rego_no ) {
                    this.vessel.vessel_details = Object.assign({}, vesselData.vessel_details);
                    if (Object.keys(vesselData.vessel_ownership).length) {
                        this.vessel.vessel_ownership = Object.assign({}, vesselData.vessel_ownership);
                    }
                    this.vessel.id = vesselData.id;
                    this.vessel.rego_no = vesselData.rego_no;
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
        let consoleColour = 'color: #000099'
        this.$nextTick(async () => {
            await this.fetchVesselTypes();
            
            if (this.proposal){
                // fetches vessel data from proposal (saved as draft)
                await this.fetchDraftData();
            } else if (!this.proposal) {
                // route.params.vessel_id in this case is a vesselownership id
                const url = api_endpoints.lookupVesselOwnership(this.$route.params.vessel_id);
                this.fetchReadonlyVesselCommon(url);
            }
            this.initialiseRegoNoSelect();
            this.initialiseCompanyNameSelect();
            this.addEventListeners();

            // read in Renewal/Amendment vessel details
            if (!(
                (!this.keep_current_vessel && this.proposal && this.proposal.proposal_type.code !== 'new') ||
                (!this.keep_current_vessel) ||
                (this.proposal && this.proposal.pending_amendment_request)
            ) && 
                (this.proposal && this.proposal.processing_status === 'Draft' &&
                !this.proposal.vessel_details_id && 
                (this.proposal.proposal_type.code !== 'new' || this.proposal.application_type_code === 'mla') &&
                !this.vessel.rego_no
                )
            ) 
            {
                let vm = this;
                let res = null;
                // if mla, get vessel from waiting list
                if (this.proposal.waiting_list_application_id) {
                    const url = helpers.add_endpoint_join(
                        api_endpoints.proposal,
                        this.proposal.waiting_list_application_id + '/fetch_vessel/'
                    );
                    res = await this.$http.get(url);
                } else if (this.proposal.previous_application_vessel_details_id) {
                    // check vessel ownership on the previous application
                    const url = helpers.add_endpoint_join(
                        api_endpoints.proposal,
                        this.proposal.previous_application_id + '/fetch_vessel/'
                    );
                    res = await this.$http.get(url);
                }


                if (!this.proposal.rego_no && res && res.body && !res.body.vessel_ownership.end_date) {
                    try {
                        this.vessel.id = res.body.id;
                        this.vessel.rego_no = res.body.rego_no;
                        console.log(res.body)
                        this.vessel.vessel_ownership.percentage = res.body.vessel_ownership.percentage;
                        this.vessel.vessel_ownership.created = res.body.vessel_ownership.created;
                        this.vessel.vessel_ownership.dot_name = res.body.vessel_ownership.dot_name;
                        this.vessel.vessel_ownership.end_name = res.body.vessel_ownership.end_name;
                        this.vessel.vessel_ownership.id = res.body.vessel_ownership.id;
                        this.vessel.vessel_ownership.start_date = res.body.vessel_ownership.start_date;
                        this.vessel.vessel_ownership.updated = res.body.vessel_ownership.updated;
                        this.vessel.vessel_ownership.vessel = res.body.vessel_ownership.vessel;
                        this.vessel.vessel_ownership.individual_owner = res.body.vessel_ownership.individual_owner;
                        this.vessel.vessel_ownership.owner = res.body.vessel_ownership.owner;
                        this.vessel.vessel_ownership.proposal_id = res.body.vessel_ownership.proposal_id;
                        
                        this.vessel.vessel_details.berth_mooring = res.body.vessel_details.berth_mooring;
                        this.vessel.vessel_details.created = res.body.vessel_details.created;
                        this.vessel.vessel_details.id = res.body.vessel_details.id;
                        this.vessel.vessel_details.read_only = res.body.vessel_details.read_only;
                        this.vessel.vessel_details.updated = res.body.vessel_details.updated;
                        this.vessel.vessel_details.vessel = res.body.vessel_details.vessel;
                        this.vessel.vessel_details.vessel_beam = res.body.vessel_details.vessel_beam;
                        this.vessel.vessel_details.vessel_draft = res.body.vessel_details.vessel_draft;
                        this.vessel.vessel_details.vessel_length = res.body.vessel_details.vessel_length;
                        this.vessel.vessel_details.vessel_name = res.body.vessel_details.vessel_name;
                        this.vessel.vessel_details.vessel_type = res.body.vessel_details.vessel_type;
                        this.vessel.vessel_details.vessel_type_display = res.body.vessel_details.vessel_type_display;
                        this.vessel.vessel_details.vessel_weight = res.body.vessel_details.vessel_weight;
                        
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
                    } catch (err) {
                        console.log(err);
                    }
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
            if (!this.vessel.rego_no) {
                await this.$emit("noVessel", true)
            }
        });
    },
    created: async function () {
        if (this.proposal){
            let res = await this.$http.get(`${api_endpoints.proposal}${this.proposal.id}/get_max_vessel_length_for_main_component?uuid=${this.proposal.uuid}`);
            this.max_vessel_length_tuple = res.body
        }
    },
}
</script>

<style lang="css" scoped>
input[type=text] {
    padding-left: 1em;
}
</style>

