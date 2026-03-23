<template>
    <div :class="classCompute" id="userInfo">
      <div class="col-sm-12">
        <div class="row">
            <div class="col-sm-12">
                <div class="panel panel-default" v-if="!readonly && is_internal && proposal.proposal_type.code == 'new' && proposal.processing_status == 'Draft'">
                    <div class="panel-heading">
                        <h3 class="panel-title">Applicant
                        <a class="panelClicker" :href="'#'+appBody" data-toggle="collapse" expanded="true" data-parent="#userInfo" :aria-controls="appBody">
                            <span class="glyphicon glyphicon-chevron-up pull-right "></span>
                        </a>
                        </h3>
                    </div>
                    <div class="panel-body collapse in" :id="appBody">
                        <form class="form-horizontal">
                            <div class="form-group">
                                <label class="col-sm-3 control-label">Applicant</label>
                                <div class="col-sm-6">
                                    <select 
                                        id="person_lookup"  
                                        name="person_lookup"  
                                        ref="person_lookup" 
                                        class="form-control" 
                                    />
                                </div>
                            </div>
                            <div>
                                <div class="col-sm-12">
                                    <button v-if="changingApplicant" type="button" class="btn btn-primary pull-right" disabled>
                                    Change Applicant&nbsp;<i class="fa fa-circle-o-notch fa-spin fa-fw"></i>
                                    </button>
                                    <button v-else type="button" @click.prevent="changeApplicant" class="btn btn-primary pull-right"
                                    :disabled="applicant_system_id == null || applicant_system_id == original_applicant_system_id">
                                    Change Applicant
                                    </button>
                                </div>
                            </div>                        
                        </form>
                    </div>
                </div>
                <div class="panel panel-default">
                  <div class="panel-heading">
                    <h3 class="panel-title">Personal Details
                        <a class="panelClicker" :href="'#'+pBody" data-toggle="collapse"  data-parent="#userInfo" expanded="false" :aria-controls="pBody">
                            <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                        </a>
                    </h3>
                  </div>
                  <div class="panel-body collapse" :id="pBody">
                      <form class="form-horizontal">
                        <div v-if="!proposalApplicant" class="form-group">
                            <label for="" class="col-sm-3 control-label"></label>
                            <div class="col-sm-12">
                                <div class="alert alert-info"><b>To update the legal name of the permit holder, contact moorings@rottnestisland.com</b></div>
                            </div>
                        </div>
                        <div class="form-group">
                          <label for="" class="col-sm-3 control-label">Given name(s)</label>
                          <div class="col-sm-6" v-if="profile.legal_first_name">
                              <input readonly type="text" class="form-control" id="first_name" name="Given name" placeholder="" v-model="profile.legal_first_name" required="">
                          </div>
                          <div class="col-sm-6" v-else>
                              <input readonly type="text" class="form-control" id="first_name" name="Given name" placeholder="" v-model="profile.first_name" required="">
                          </div>
                        </div>
                        <div class="form-group">
                          <label for="" class="col-sm-3 control-label" >Surname</label>
                          <div class="col-sm-6" v-if="profile.legal_first_name">
                              <input readonly type="text" class="form-control" id="surname" name="Surname" placeholder="" v-model="profile.legal_last_name">
                          </div>
                          <div class="col-sm-6" v-else>
                              <input readonly type="text" class="form-control" id="first_name" name="Surname" placeholder="" v-model="profile.last_name" required="">
                          </div>
                        </div>
                        <div class="row form-group" v-if="!forEndorser">
                            <label for="" class="col-sm-3 control-label" >Date of Birth</label>
                          <div class="col-sm-6">
                              <input readonly type="text" class="form-control" id="dob" name="Date of Birth" placeholder="" v-model="profile.legal_dob">
                          </div>
                        </div>
                       </form>
                  </div>
                </div>
            </div>
        </div>

        <div class="row" v-if="!forEndorser">
            <div class="col-sm-12">
                <div class="panel panel-default">
                    <div class="panel-heading">
                        <h3 class="panel-title">Address Details <small>Select address details for this application</small>
                        <a class="panelClicker" :href="'#'+adBody" data-toggle="collapse" expanded="true" data-parent="#userInfo" :aria-controls="adBody">
                            <span class="glyphicon glyphicon-chevron-up pull-right "></span>
                        </a>
                        </h3>
                    </div>
                    <div v-if="!readonly" class="panel-body collapse in" :id="adBody">
                        <form class="form-horizontal">
                        <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >
                                <strong>
                                Residential Address
                                </strong>
                            </label>
                            <div class="col-sm-6">
                            <select v-model="residential_address" class="form-control">
                                <option selected disabled hidden value>Select residential address...</option>
                                <option v-for="option in profile.residential_address_list" :value="option">
                                    {{ option.line1 }}, {{ option.locality }}, {{ option.state }}, {{ option.postcode }}, {{ option.country }}
                                </option>
                            </select>
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >
                                <strong>
                                Postal Address
                                </strong>
                            </label>
                            <div class="col-sm-6">
                            <select v-model="postal_address" class="form-control">
                                <option selected disabled hidden value>Select postal address...</option>
                                <option v-for="option in profile.postal_address_list" :value="option">
                                    {{ option.line1 }}, {{ option.locality }}, {{ option.state }}, {{ option.postcode }}, {{ option.country }}
                                </option>
                            </select>
                            </div>
                        </div>
                    </form>
                  </div>
                  <div v-else-if="proposal.proposal_applicant" class="panel-body collapse in" :id="adBody">
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
                                <input readonly type="text" class="form-control" v-model="proposal.proposal_applicant.residential_address_line1">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Town/Suburb</label>
                            <div class="col-sm-6">
                                <input readonly type="text" class="form-control" v-model="proposal.proposal_applicant.residential_address_locality">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >State</label>
                            <div class="col-sm-6">
                                <input readonly type="text" class="form-control" v-model="proposal.proposal_applicant.residential_address_state">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Postcode</label>
                            <div class="col-sm-6">
                                <input readonly type="text" class="form-control" v-model="proposal.proposal_applicant.residential_address_postcode">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Country</label>
                            <div class="col-sm-6">
                                <input readonly type="text" class="form-control" v-model="proposal.proposal_applicant.residential_address_country">
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
                                <input readonly type="text" class="form-control" v-model="proposal.proposal_applicant.postal_address_line1">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Town/Suburb</label>
                            <div class="col-sm-6">
                                <input readonly type="text" class="form-control" v-model="proposal.proposal_applicant.postal_address_locality">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >State</label>
                            <div class="col-sm-6">
                                <input readonly type="text" class="form-control" v-model="proposal.proposal_applicant.postal_address_state">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Postcode</label>
                            <div class="col-sm-6">
                                <input readonly type="text" class="form-control" v-model="proposal.proposal_applicant.postal_address_postcode">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Country</label>
                            <div class="col-sm-6">
                                <input readonly type="text" class="form-control" v-model="proposal.proposal_applicant.postal_address_country">
                            </div>
                          </div> 
                        </div>
                    </form>
                  </div>
                </div>
            </div>
        </div>
        <div class="row">
            <div class="col-sm-12">
                <div class="panel panel-default">
                  <div class="panel-heading">
                    <h3 class="panel-title">Contact Details
                        <a class="panelClicker" :href="'#'+cBody" data-toggle="collapse" data-parent="#userInfo" expanded="false" :aria-controls="cBody">
                            <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                        </a>
                    </h3>
                  </div>
                  <div class="panel-body collapse" :id="cBody">
                      <form class="form-horizontal">
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label">Phone (work)</label>
                            <div class="col-sm-6">
                               <input readonly type="text" class="form-control" id="phone" name="Phone" placeholder="" v-model="profile.phone_number">
                            </div>
                          </div>
                          <div class="form-group" v-if="!forEndorser">
                            <label for="" class="col-sm-3 control-label" >Mobile</label>
                            <div class="col-sm-6">
                                <input readonly type="text" class="form-control" id="mobile" name="Mobile" placeholder="" v-model="profile.mobile_number">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Email</label>
                            <div class="col-sm-6">
                                <input readonly type="email" class="form-control" id="email" name="Email" placeholder="" v-model="profile.email">
                            </div>
                          </div>
                       </form>
                  </div>
                </div>
            </div>
        </div>
        <FormSection v-if="showElectoralRoll" label="WA State Electoral Roll" :Index="electoralRollSectionIndex">
            <div class="form-group">
                <div class="col-sm-8 mb-3">
                    <strong>
                        You must be on the WA state electoral roll to make an application
                    </strong>
                </div>
                <div class="col-sm-8">
                    <input :disabled="readonly" type="radio" id="electoral_roll_yes" :value="false" v-model="silentElector"/>
                    <label for="electoral_roll_yes">
                        Yes, I am on the
                        <a target="_blank" href="https://www.elections.wa.gov.au/oes#/oec">WA state electoral roll</a>
                    </label>
                </div>
                <div class="col-sm-8">
                    <input :disabled="readonly" class="mb-3" type="radio" id="electoral_roll_silent" :value="true" v-model="silentElector"/>
                    <label for="electoral_roll_silent">
                        I am a silent elector
                    </label>
                    <div v-if="silentElector===true">
                        <FileField
                            :readonly="readonly"
                            headerCSS="ml-3"
                            label="Provide evidence"
                            ref="electoral_roll_documents"
                            name="electoral-roll-documents"
                            :isRepeatable="true"
                            :documentActionUrl="electoralRollDocumentUrl"
                            :replace_button_by_text="true"
                        />
                    </div>
                </div>
            </div>
        </FormSection>
        </div>
    </div>
</template>

<script>
import Vue from 'vue'
import $ from 'jquery'
import { api_endpoints, helpers } from '@/utils/hooks'
import FormSection from '@/components/forms/section_toggle.vue'
import FileField from '@/components/forms/filefield_immediate.vue'
import alert from '@vue-utils/alert.vue'
import datatable from '@/utils/vue/datatable.vue'

export default {
    name: 'Profile',
    props:{
        proposalId: {
            type: Number,
        },
        proposal: {
            type: Object,
        },
        isApplication:{
                type: Boolean,
                default: false
            },
        showElectoralRoll:{
                type: Boolean,
                default: false
            },
        storedSilentElector:{
                type: Boolean,
            },
        readonly:{
            type: Boolean,
            default: false,
        },
        forEndorser: {
            type: Boolean,
            default: false,
        },
        is_internal: {
            type: Boolean,
            default: false
        },
    },
    data () {
        let vm = this;
        return {
            electoralRollSectionIndex: 'electoral_roll_' + vm._uid,
            silentElector: null,
            appBody: 'appBody'+vm._uid,
            adBody: 'adBody'+vm._uid,
            pBody: 'pBody'+vm._uid,
            cBody: 'cBody'+vm._uid,
            profile: {},
            residential_address_datatable_id: 'residential-address-datatable-' + vm._uid,
            postal_address_datatable_id: 'postal-address-datatable-' + vm._uid,
            address_datatable_headers: ["Street","Locality","State","Postcode","Country","Action"],
            residential_address_table_key: 0,
            postal_address_table_key: 0,
            selected_residential_id: null,
            selected_postal_id: null,
            residential_address: "",
            postal_address:"",
            original_applicant_system_id: null,
            applicant_system_id: null,
            changingApplicant: false,
        }
    },
    components: {
        FormSection,
        FileField,
        alert,
        datatable,
    },
    watch: {
        residential_address: function() {
            this.profile.residential_address = this.residential_address;
        },
        postal_address: function() {
            this.profile.postal_address = this.postal_address;
        }
    },
    computed: {
        electoralRollDocumentUrl: function() {
            let url = '';
            if (this.profile && this.profile.id) {
                url = '/api/proposal/' + this.proposalId + '/electoral_roll_document/'
            }
            return url;
        },
        classCompute:function(){
          return this.isApplication? 'row' : 'container';
        },
        uploadedFileName: function() {
            return this.uploadedFile != null ? this.uploadedFile.name: '';
        },
        isFileUploaded: function() {
            return this.uploadedFile != null ? true: false;
        },
    },
    methods: {
        changeApplicant: async function() {
            
            if (this.applicant_system_id != null &&
                this.applicant_system_id != this.original_applicant_system_id) {
                console.log(this.applicant_system_id)
                console.log(this.original_applicant_system_id)
                this.changingApplicant = true;

                try {
                    await swal({
                        title: "Change Applicant",
                        text: "Are you sure you want to change the applicant of this application?",
                        type: "question",
                        showCancelButton: true,
                        confirmButtonText: "Change Applicant"
                    })
                } catch (cancel) {
                    this.changingApplicant = false;
                    return;
                }

                let url = `/api/proposal/${this.proposal.id}/change_applicant/`;
                const payload = {"applicant_system_id":this.applicant_system_id};

                this.$http.post(
                    url, 
                    payload,
                ).then((res)=>{
                    this.changingApplicant = false;
                    this.$router.go();
                },(err)=>{
                    swal({
                        title: "Please fix following errors before saving",
                        text: err.bodyText,
                        type:'error'
                    });
                    this.changingApplicant = false;
                });
            }          
        },
        initialisePersonLookup: function() {
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
                vm.applicant_system_id = vm.profile.id;;
            }).
            on("select2:open",function (e) {
                const searchField = $('[aria-controls="select2-person_lookup-results"]')
                // move focus to select2 field
                searchField[0].focus();
            });
        },
        getApplicantDisplay: function () {           
            let vm = this; 
            console.log("getApplicantDisplay")
            let display = null
            if (vm.profile.legal_first_name) {
                display = vm.profile.legal_first_name + " " + vm.profile.legal_last_name + " (DOB: "+vm.profile.legal_dob+")";
            } else {
                display = vm.profile.first_name + " " + vm.profile.last_name + " (DOB: "+vm.profile.legal_dob+")";
            }
            var newOption = new Option(display, vm.profile.id, false, true);
            $('#person_lookup').append(newOption);         
        },
        readFile: function() {
            let vm = this;
            let _file = null;
            var input = $(vm.$refs.uploadedFile)[0];
            if (input.files && input.files[0]) {
                var reader = new FileReader();
                reader.readAsDataURL(input.files[0]);
                reader.onload = function(e) {
                    _file = e.target.result;
                };
                _file = input.files[0];
            }
            vm.uploadedFile = _file;
        },       
        toggleSection: function (e) {
            let el = e.target;
            let chev = null;
            $(el).on('click', function (event) {
                chev = $(this);
                $(chev).toggleClass('glyphicon-chevron-down glyphicon-chevron-up');
            })
        },

        fetchProfile: async function(){
            console.log('in fetchProfile')
            let response = null;
            response = await Vue.http.get(api_endpoints.profile + '/' + this.proposalId)
            this.profile = Object.assign(response.body)

            if (this.profile.residential_address_list !== undefined)
            {
                if (this.proposal.proposal_applicant !== null) {
                    this.profile.residential_address_list.forEach(addr => {
                        if (
                            addr.line1 === this.proposal.proposal_applicant.residential_address_line1 &&
                            addr.locality === this.proposal.proposal_applicant.residential_address_locality &&
                            addr.state === this.proposal.proposal_applicant.residential_address_state &&
                            addr.country === this.proposal.proposal_applicant.residential_address_country &&
                            addr.postcode === this.proposal.proposal_applicant.residential_address_postcode
                        ) {
                            this.residential_address = Object.assign(addr)
                        }
                    });
                } else if (this.profile.residential_address_list.length == 1){
                    this.residential_address = Object.assign(this.profile.residential_address_list[0])
                } 
            } else {
                this.residential_address = "";
            }

            if (this.profile.postal_address_list !== undefined)
            {
                if (this.proposal.proposal_applicant !== null) {
                    this.profile.postal_address_list.forEach(addr => {
                        if (
                            addr.line1 === this.proposal.proposal_applicant.postal_address_line1 &&
                            addr.locality === this.proposal.proposal_applicant.postal_address_locality &&
                            addr.state === this.proposal.proposal_applicant.postal_address_state &&
                            addr.country === this.proposal.proposal_applicant.postal_address_country &&
                            addr.postcode === this.proposal.proposal_applicant.postal_address_postcode
                        ) {
                            this.postal_address = Object.assign(addr)
                        }
                    });
                } else if (this.profile.postal_address_list.length  == 1){
                    this.postal_address = Object.assign(this.profile.postal_address_list[0])
                } 
            }   else {
                    this.postal_address = "";
            }

            if (this.profile.legal_dob !== null && this.profile.legal_dob !== "") {
                this.profile.legal_dob = moment(this.profile.legal_dob).format('DD/MM/YYYY')
            }
        },
    },
    beforeRouteEnter: function(to,from,next){
        Vue.http.get(api_endpoints.profile).then((response) => {
            next(vm => {
                vm.profile = Object.assign(response.body);
            });           
        },(error) => {
            console.log(error);
        })
    },
    mounted: async function(){

        await this.fetchProfile(); //beforeRouteEnter doesn't work when loading this component in Application.vue so adding an extra method to get profile details.
        await this.$nextTick(() => {
            this.$emit('profile-fetched', this.profile);
            this.residential_address_table_key++;
            this.postal_address_table_key++;
            if (this.is_internal && !this.readonly && this.proposal.proposal_type.code == 'new' && this.proposal.processing_status == 'Draft') {
                //must select user to load for
                this.applicant_system_id = this.profile.id;
                this.original_applicant_system_id = this.profile.id;
                this.$nextTick(async () => {
                    this.initialisePersonLookup();
                    this.getApplicantDisplay();
                });
            }
        });
        $('.panelClicker[data-toggle="collapse"]').on('click', function () {
            var chev = $(this).children()[0];
            window.setTimeout(function () {
                $(chev).toggleClass("glyphicon-chevron-down glyphicon-chevron-up");
            },100);
        });
        this.silentElector = this.storedSilentElector;
    }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
.btn-file {
    position: relative;
    overflow: hidden;
}
.btn-file input[type=file] {
    position: absolute;
    top: 0;
    right: 0;
    min-width: 100%;
    min-height: 100%;
    font-size: 100px;
    text-align: right;
    filter: alpha(opacity=0);
    opacity: 0;
    outline: none;
    background: white;
    cursor: inherit;
    display: block;
}
.mb-3 {
    margin-bottom: 1em !important;
}
.ml-1 {
    margin-left: 1em !important;
}
.electoral-label {
    margin-bottom: 25px !important;
}
.label-right {
    float: right;
    text-align: left;
}
.address-box {
    border: 1px solid;
    border-color: #DCDCDC;
    padding: 15px;
}
</style>
