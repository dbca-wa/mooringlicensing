<template lang="html">
    <div class="row">
        <div class="col-sm-12">
            <div class="col-md-12">
                <div class="row">
                    <div class="panel panel-default">
                        <div class="panel-heading">
                            <h3 class="panel-title">{{ customerLabel }}
                                <a class="panelClicker" :href="'#' + detailsBody" data-toggle="collapse"
                                    data-parent="#userInfo" expanded="true" :aria-controls="detailsBody">
                                    <span class="glyphicon glyphicon-chevron-up pull-right "></span>
                                </a>
                            </h3>
                        </div>
                        <div class="panel-body panel-collapse collapse in" :id="detailsBody">

                            <form class="form-horizontal">
                                <div v-if="!proposalApplicant" class="form-group">
                                    <label for="" class="col-sm-3 control-label"></label>
                                    <div class="col-sm-12">
                                        <div class="alert alert-info"><b>The user must log in to the system, navigate to Options > Manage Account, and click Click Here to update their account name</b></div>
                                    </div>
                                </div>

                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label">Legal Given Name(s)</label>
                                    <div class="col-sm-6">
                                        <input disabled type="text" class="form-control" placeholder=""
                                            v-model="user.first_name">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label">Legal Surname</label>
                                    <div class="col-sm-6">
                                        <input disabled type="text" class="form-control" placeholder=""
                                            v-model="user.last_name">
                                    </div>
                                </div>

                                <div v-if="!proposalApplicant" class="form-group">
                                    <label for="" class="col-sm-3 control-label"></label>
                                    <div class="col-sm-12">
                                        <div class="alert alert-info"><b>To update the legal name of the permit holder go to Accounts Management: <u><a :href="'/ledger-ui/accounts-management/'+user.id+'/change'">Edit System Account</a></u></b></div>
                                    </div>
                                </div>

                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label">Legal Given Name(s)</label>
                                    <div class="col-sm-6">
                                        <input v-if="user.legal_first_name" disabled type="text" class="form-control" placeholder=""
                                            v-model="user.legal_first_name">
                                        <input v-else disabled type="text" class="form-control" placeholder=""
                                            v-model="user.first_name">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label">Legal Surname</label>
                                    <div class="col-sm-6">
                                        <input v-if="user.legal_last_name" disabled type="text" class="form-control" placeholder=""
                                            v-model="user.legal_last_name">
                                        <input v-else disabled type="text" class="form-control" placeholder=""
                                            v-model="user.last_name">
                                    </div>
                                </div>

                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label">Legal Date of Birth</label>
                                    <div class="col-sm-6">
                                        <input disabled type="text" class="form-control" placeholder=""
                                            v-model="user.legal_dob">
                                    </div>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
            <div v-if="proposalId && proposalApplicant" class="col-md-12">
                <div class="row">
                    <div class="panel panel-default">
                        <div class="panel-heading">
                            <h3 class="panel-title">Address Details
                                <a class="panelClicker" :href="'#' + addressBody" data-toggle="collapse"
                                    data-parent="#userInfo" expanded="false" :aria-controls="addressBody"
                                    @click="adjust_address_tables">
                                    <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                                </a>
                            </h3>
                        </div>
                        <div class="panel-body panel-collapse collapse" :id="addressBody"> 
                            <form class="form-horizontal">
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >
                                        <strong>
                                        Residential Address
                                        </strong>
                                    </label>
                                </div>
                                <div class="row">
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >Street</label>
                                    <div class="col-sm-6">
                                        <input readonly type="text" class="form-control" v-model="proposalApplicant.residential_address_line1">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >Town/Suburb</label>
                                    <div class="col-sm-6">
                                        <input readonly type="text" class="form-control" v-model="proposalApplicant.residential_address_locality">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >State</label>
                                    <div class="col-sm-6">
                                        <input readonly type="text" class="form-control" v-model="proposalApplicant.residential_address_state">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >Postcode</label>
                                    <div class="col-sm-6">
                                        <input readonly type="text" class="form-control" v-model="proposalApplicant.residential_address_postcode">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >Country</label>
                                    <div class="col-sm-6">
                                        <input readonly type="text" class="form-control" v-model="proposalApplicant.residential_address_country">
                                    </div>
                                </div> 
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >
                                        <strong>
                                        Postal Address
                                        </strong>
                                    </label>
                                </div>
                                <div class="row">
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >Street</label>
                                    <div class="col-sm-6">
                                        <input readonly type="text" class="form-control" v-model="proposalApplicant.postal_address_line1">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >Town/Suburb</label>
                                    <div class="col-sm-6">
                                        <input readonly type="text" class="form-control" v-model="proposalApplicant.postal_address_locality">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >State</label>
                                    <div class="col-sm-6">
                                        <input readonly type="text" class="form-control" v-model="proposalApplicant.postal_address_state">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >Postcode</label>
                                    <div class="col-sm-6">
                                        <input readonly type="text" class="form-control" v-model="proposalApplicant.postal_address_postcode">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label" >Country</label>
                                    <div class="col-sm-6">
                                        <input readonly type="text" class="form-control" v-model="proposalApplicant.postal_address_country">
                                    </div>
                                </div> 
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
            <div v-else class="col-md-12">
                <div class="row">
                    <div class="panel panel-default">
                        <div class="panel-heading">
                            <h3 class="panel-title">Address Details
                                <a class="panelClicker" :href="'#' + addressBody" data-toggle="collapse"
                                    data-parent="#userInfo" expanded="false" :aria-controls="addressBody"
                                    @click="adjust_address_tables">
                                    <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                                </a>
                            </h3>
                        </div>

                        <div class="panel-body panel-collapse collapse" :id="addressBody"> 
                            <div class="row">
                                <div class="col-lg-12">
                                    <strong>
                                    Residential Address
                                    </strong>
                                </div>
                            </div>
                            <div class="row">
                                <div class="col-lg-12">
                                    <datatable
                                        ref="residential_address_datatable"
                                        :id="residential_address_datatable_id"
                                        :dtOptions="residential_address_datatable_options"
                                        :dtHeaders="address_datatable_headers"
                                    />
                                </div>
                            </div>
                            <div class="row">
                                <div class="col-lg-12">
                                    <strong>
                                    Postal Address
                                    </strong>
                                </div>
                            </div>
                            <div class="row">
                                <div class="col-lg-12">
                                    <datatable
                                        ref="postal_address_datatable"
                                        :id="postal_address_datatable_id"
                                        :dtOptions="postal_address_datatable_options"
                                        :dtHeaders="address_datatable_headers"
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-12">
                <div class="row">
                    <div class="panel panel-default">
                        <div class="panel-heading">
                            <h3 class="panel-title">Contact Details
                                <a class="panelClicker" :href="'#' + contactsBody" data-toggle="collapse"
                                    data-parent="#userInfo" expanded="false" :aria-controls="contactsBody">
                                    <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                                </a>
                            </h3>
                        </div>
                        <div class="panel-body panel-collapse collapse" :id="contactsBody">
                            <form class="form-horizontal">
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label">Phone (work)</label>
                                    <div class="col-sm-6">
                                        <input disabled type="text" class="form-control" name="phoneNumber"
                                            placeholder="" v-model="user.phone_number">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label">Mobile</label>
                                    <div class="col-sm-6">
                                        <input disabled type="text" class="form-control" name="mobileNumber"
                                            placeholder="" v-model="user.mobile_number">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label for="" class="col-sm-3 control-label">Email</label>
                                    <div class="col-sm-6">
                                        <input disabled type="text" class="form-control" name="email"
                                            placeholder="" v-model="user.email">
                                    </div>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-12" v-if="showElectoralRoll">
                <div class="row">
                    <div class="panel panel-default">
                        <div class="panel-heading">
                            <h3 class="panel-title">WA State Electoral Roll
                                <a class="panelClicker" :href="'#' + electoralRollBody" data-toggle="collapse"
                                    data-parent="#userInfo" expanded="false" :aria-controls="electoralRollBody">
                                    <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                                </a>
                            </h3>
                        </div>

                        <div class="panel-body panel-collapse collapse" :id="electoralRollBody">
                            <form class="form-horizontal">
                                <div class="form-group">
                                    <div class="col-sm-8 mb-3">
                                        <strong>
                                            You must be on the WA state electoral roll to make an application
                                        </strong>
                                    </div>
                                    <div class="col-sm-8">
                                        <input disabled type="radio" id="electoral_roll_yes" :value="false"
                                            v-model="silentElector" />
                                        <label for="electoral_roll_yes">
                                            Yes, I am on the
                                            <a href="/" @click.prevent="uploadProofElectoralRoll">WA state electoral
                                                roll</a>
                                        </label>
                                    </div>
                                    <div class="col-sm-8">
                                        <input disabled class="mb-3" type="radio" id="electoral_roll_silent"
                                            :value="true" v-model="silentElector" />
                                        <label for="electoral_roll_silent">
                                            I am a silent elector
                                        </label>
                                        <div v-if="silentElector === true">
                                            <FileField readonly headerCSS="ml-3" label="Provide evidence"
                                                ref="electoral_roll_documents" name="electoral-roll-documents"
                                                :isRepeatable="true" :documentActionUrl="electoralRollDocumentUrl"
                                                :replace_button_by_text="true" />
                                        </div>
                                    </div>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import FileField from '@/components/forms/filefield_immediate.vue'
import {
    api_endpoints
}
from '@/utils/hooks'
export default {
    name: 'Applicant',
    props: {
        user: {
            type: Object,
            required: true,
        },
        customerType: {
            type: String,
            required: false,
        },
        showElectoralRoll: {
            type: Boolean,
            default: false
        },
        storedSilentElector: {
            type: Boolean,
        },
        proposalId: {
            type: Number,
        },
        proposalApplicant: {
            type: Object,
        },
    },
    data: function () {
        let vm = this;
        return {
            electoralRollSectionIndex: 'electoral_roll_' + vm._uid,
            silentElector: null,
            countries: [],
            showAddressError: false,
            detailsBody: 'detailsBody' + vm._uid,
            addressBody: 'addressBody' + vm._uid,
            contactsBody: 'contactsBody' + vm._uid,
            electoralRollBody: 'electoralRollBody' + vm._uid,
            residential_address_datatable_id: 'residential-address-datatable-' + vm._uid,
            postal_address_datatable_id: 'postal-address-datatable-' + vm._uid,
            panelClickersInitialised: false,
            address_datatable_headers: ["Street","Locality","State","Postcode","Country"],
        }
    },
    components: {
        FileField,
        datatable,
    },
    computed: {
        electoralRollDocumentUrl: function () {
            let url = '';
            if (this.proposalId) {
                url = '/api/proposal/' + this.proposalId + '/electoral_roll_document/'
            }
            return url;
        },
        customerLabel: function () {
            let label = 'User';
            if (this.proposalId) {
                label = 'Applicant';
                if (this.customerType && this.customerType === 'holder') {
                    label = 'Holder';
                }
            }
            return label;
        },
        residential_address_datatable_options: function() {
            return this.datatable_options("residential");
        },
        postal_address_datatable_options: function() {
            return this.datatable_options("postal");
        },
        column_street: function(){
            return {
                data: "line1",
            }
        },
        column_locality: function(){
            return {
                data: "locality",
            }
        },
        column_state: function(){
            return {
                data: "state",
            }
        },
        column_postcode: function(){
            return {
                data: "postcode",
            }
        },
        column_country: function(){
            return {
                data: "country",
            }
        },
    },
    methods: {
        adjust_address_tables: function() {
            let vm = this;
            setTimeout(function () {
                vm.adjust_table_width();
            }, 200);
        },
        adjust_table_width: function() {
            let vm = this;
            if (vm.$refs.residential_address_datatable !== undefined) {
                vm.$refs.postal_address_datatable.vmDataTable.columns.adjust().responsive.recalc();
            }
            if (vm.$refs.residential_address_datatable !== undefined) {
                vm.$refs.postal_address_datatable.vmDataTable.columns.adjust().responsive.recalc();
            }
        },
        datatable_options: function(address_type){
            let vm = this;
            let data = [];
            if (address_type == "residential") {
                data = vm.user.residential_address_list;
            } else if (address_type == "postal") {
                data = vm.user.postal_address_list;
            }
            return {
                searching: false,
                autoWidth: true,
                responsive: true,
                data: data,
                dom: 'lBfrtip',
                buttons: [],
                columns: [
                    vm.column_street,
                    vm.column_locality,
                    vm.column_state,
                    vm.column_postcode,
                    vm.column_country,
                ],
                processing: true,
            }
        },
        fetchCountries: function () {
            let vm = this;
            vm.$http.get(api_endpoints.countries).then((response) => {
                vm.countries = response.body;
            });
        },
    },
    mounted: function () {
        let vm = this;
        this.fetchCountries();
        if (!vm.panelClickersInitialised) {
            $('.panelClicker[data-toggle="collapse"]').on('click', function () {
                var chev = $(this).children()[0];
                window.setTimeout(function () {
                    $(chev).toggleClass("glyphicon-chevron-down glyphicon-chevron-up");
                }, 100);
            });
            vm.panelClickersInitialised = true;
        }
        this.silentElector = this.storedSilentElector;
    }
}
</script>