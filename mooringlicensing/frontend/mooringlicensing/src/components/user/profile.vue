<template>
    <div :class="classCompute" id="userInfo">
      <div class="col-sm-12">
        <div v-if="showCompletion" class="row">
            <div class="col-sm-12">
                <div class="well well-sm">
                    <div class="row">
                        <div class="col-sm-12">
                            <p>
                                We have detected that this is the first time you have logged into the system.Please take a moment to provide us with your details
                                (personal details, address details, contact details, and whether you are managing licences for an organisation).
                                Once completed, click Continue to start using the system.
                            </p>
                            <a :disabled="!completedProfile" href="/" class="btn btn-primary pull-right">Continue</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="row">
            <div class="col-sm-12">
                <div class="panel panel-default">
                  <div class="panel-heading">
                    <i v-if="showCompletion && profile.personal_details" class="fa fa-check fa-2x pull-left" style="color:green"></i>
                    <i v-else-if="showCompletion && !profile.personal_details" class="fa fa-times fa-2x pull-left" style="color:red"></i>
                    <h3 class="panel-title">Personal Details <small>Provide your personal details</small>
                        <a class="panelClicker" :href="'#'+pBody" data-toggle="collapse"  data-parent="#userInfo" expanded="true" :aria-controls="pBody">
                            <span class="glyphicon glyphicon-chevron-up pull-right "></span>
                        </a>
                    </h3>
                  </div>
                  <div class="panel-body collapse in" :id="pBody">
                      <form class="form-horizontal" name="personal_form" method="post">
                        <alert v-if="showPersonalError" type="danger" style="color:red"><div v-for="item in errorListPersonal"><strong>{{item}}</strong></div></alert>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label">Given name(s)</label>
                            <div class="col-sm-6">
                                <input :readonly="readonly" type="text" class="form-control" id="first_name" name="Given name" placeholder="" v-model="profile.first_name" required="">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Surname</label>
                            <div class="col-sm-6">
                                <input :readonly="readonly" type="text" class="form-control" id="surname" name="Surname" placeholder="" v-model="profile.last_name">
                            </div>
                          </div>
                          <div class="form-group">
                            <div v-if="!readonly" class="col-sm-12">
                                <button v-if="!updatingPersonal" class="pull-right btn btn-primary" @click.prevent="updatePersonal()">Update</button>
                                <button v-else disabled class="pull-right btn btn-primary"><i class="fa fa-spin fa-spinner"></i>&nbsp;Updating</button>
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
                    <i v-if="showCompletion && profile.address_details" class="fa fa-check fa-2x pull-left" style="color:green"></i>
                    <i v-else-if="showCompletion && !profile.address_details" class="fa fa-times fa-2x pull-left" style="color:red"></i>
                    <h3 class="panel-title">Address Details <small>Provide your address details</small>
                        <a class="panelClicker" :href="'#'+adBody" data-toggle="collapse" expanded="false"  data-parent="#userInfo" :aria-controls="adBody">
                            <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                        </a>
                    </h3>
                  </div>
                  <div v-if="loading.length == 0" class="panel-body collapse" :id="adBody">
                      <form class="form-horizontal" action="index.html" method="post">
                        <alert v-if="showAddressError" type="danger" style="color:red"><div v-for="item in errorListAddress"><strong>{{item}}</strong></div></alert>
                      <div class="address-box">
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label">Residential Address</label>
                            <div class="col-sm-6">
                                <input :readonly="readonly" type="text" class="form-control" id="line1" name="Street" placeholder="" v-model="profile.residential_address.line1">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Town/Suburb</label>
                            <div class="col-sm-6">
                                <input :readonly="readonly" type="text" class="form-control" id="locality" name="Town/Suburb" placeholder="" v-model="profile.residential_address.locality">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label">State</label>
                            <div class="col-sm-3">
                                <input :readonly="readonly" type="text" class="form-control" id="state" name="State" placeholder="" v-model="profile.residential_address.state">
                            </div>
                            <label for="" class="col-sm-1 control-label">Postcode</label>
                            <div class="col-sm-2">
                                <input :readonly="readonly" type="text" class="form-control" id="postcode" name="Postcode" placeholder="" v-model="profile.residential_address.postcode">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Country</label>
                            <div class="col-sm-4">
                                <select :disabled="readonly" class="form-control" id="country" name="Country" v-model="profile.residential_address.country">
                                    <option v-for="c in countries" :value="c.alpha2Code">{{ c.name }}</option>
                                </select>
                            </div>
                          </div>
                      </div>
                          <!-- -->
                      <div class="form-group"/>
                      <div class="address-box">
                          <div class="form-group">
                            <div class="col-sm-3">
                            </div>
                            <div class="col-sm-6">
                              <input :readonly="readonly" type="checkbox" id="postal_same_as_residential" v-model="profile.postal_same_as_residential"/>
                              <label for="postal_same_as_residential" class="control-label">Same as residential address</label>
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label">Postal Address</label>
                            <div class="col-sm-6">
                                <input :readonly="postalAddressReadonly" type="text" class="form-control" id="postal_line1" name="Street" placeholder="" v-model="profile.postal_address.line1">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Town/Suburb</label>
                            <div class="col-sm-6">
                                <input :readonly="postalAddressReadonly" type="text" class="form-control" id="postal_locality" name="Town/Suburb" placeholder="" v-model="profile.postal_address.locality">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label">State</label>
                            <div class="col-sm-3">
                                <input :readonly="postalAddressReadonly" type="text" class="form-control" id="postal_state" name="State" placeholder="" v-model="profile.postal_address.state">
                            </div>
                            <label for="" class="col-sm-1 control-label">Postcode</label>
                            <div class="col-sm-2">
                                <input :readonly="postalAddressReadonly" type="text" class="form-control" id="postal_postcode" name="Postcode" placeholder="" v-model="profile.postal_address.postcode">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Country</label>
                            <div class="col-sm-4">
                                <select :disabled="postalAddressReadonly" class="form-control" id="postal_country" name="Country" v-model="profile.postal_address.country">
                                    <option v-for="c in countries" :value="c.alpha2Code">{{ c.name }}</option>
                                </select>
                            </div>
                          </div>
                      </div>

                          <div class="form-group">
                            <div v-if="!readonly" class="col-sm-12">
                                <button v-if="!updatingAddress" class="pull-right btn btn-primary" @click.prevent="updateAddress()">Update</button>
                                <button v-else disabled class="pull-right btn btn-primary"><i class="fa fa-spin fa-spinner"></i>&nbsp;Updating</button>
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
                    <i v-if="showCompletion && profile.contact_details" class="fa fa-check fa-2x pull-left" style="color:green"></i>
                    <i v-else-if="showCompletion && !profile.contact_details" class="fa fa-times fa-2x pull-left" style="color:red"></i>
                    <h3 class="panel-title">Contact Details <small>Provide your contact details</small>
                        <a class="panelClicker" :href="'#'+cBody" data-toggle="collapse"  data-parent="#userInfo" expanded="false" :aria-controls="cBody">
                            <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                        </a>
                    </h3>
                  </div>
                  <div class="panel-body collapse" :id="cBody">
                      <form class="form-horizontal" action="index.html" method="post">
                        <alert v-if="showContactError" type="danger" style="color:red"><div v-for="item in errorListContact"><strong>{{item}}</strong></div></alert>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label">Phone (work)</label>
                            <div v-if="profile.is_department_user" class="col-sm-6">
                               <input :readonly="phoneNumberReadonly || readonly" type="text" class="form-control" id="phone" name="Phone" placeholder="" v-model="profile.phone_number">           
                            </div>
                            <div v-else class="col-sm-6">
                                <input type="text" class="form-control" id="phone" name="Phone" placeholder="" v-model="profile.phone_number">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Mobile</label>
                            <div v-if="profile.is_department_user" class="col-sm-6">
                                <input :readonly="mobileNumberReadonly || readonly" type="text" class="form-control" id="mobile" name="Mobile" placeholder="" v-model="profile.mobile_number">
                            </div>
                            <div v-else class="col-sm-6">
                                <input type="text" class="form-control" id="mobile" name="Mobile" placeholder="" v-model="profile.mobile_number">
                            </div>
                          </div>
                          <div class="form-group">
                            <label for="" class="col-sm-3 control-label" >Email</label>
                            <div class="col-sm-6">
                                <input :readonly="readonly" type="email" class="form-control" id="email" name="Email" placeholder="" v-model="profile.email">
                            </div>
                          </div>
                          <div class="form-group">
                            <div v-if="!readonly" class="col-sm-12">
                                <button v-if="!updatingContact" class="pull-right btn btn-primary" @click.prevent="updateContact()">Update</button>
                                <button v-else disabled class="pull-right btn btn-primary"><i class="fa fa-spin fa-spinner"></i>&nbsp;Updating</button>
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
                        <a href="/" @click.prevent="uploadProofElectoralRoll">WA state electoral roll</a>
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
export default {
    name: 'Profile',
    props:{
        proposalId: {
            type: Number,
        },
        submitterId: {
            type: Number,
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

    },
    data () {
        let vm = this;
        return {
            electoralRollSectionIndex: 'electoral_roll_' + vm._uid,
            silentElector: null,
            adBody: 'adBody'+vm._uid,
            pBody: 'pBody'+vm._uid,
            cBody: 'cBody'+vm._uid,
            oBody: 'oBody'+vm._uid,
            idBody: 'idBody'+vm._uid,
            sBody: 'sBody'+vm._uid,
            profile: {
                first_name: '',
                last_name: '',
                mooringlicensing_organisations:[],
                residential_address : {},
                postal_address : {},
                electoral_roll: null,
            },
            newOrg: {
                'detailsChecked': false,
                'exists': false
            },
            countries: [],
            loading: [],
            registeringOrg: false,
            validatingPins: false,
            checkingDetails: false,
            addingCompany: false,
            managesOrg: 'No',
            uploadedFile: null,
            uploadedID: null,
            updatingPersonal: false,
            updatingAddress: false,
            updatingContact: false,
            updatingSystemSettings: false,
            registeringOrg: false,
            orgRequest_list: [],
            missing_fields: [],
            errorListPersonal:[],
            showPersonalError: false,
            errorListAddress:[],
            showAddressError: false,
            errorListContact:[],
            showContactError: false,
            role : null,
            phoneNumberReadonly: false,
            mobileNumberReadonly: false,
        }
    },
    components: {
        FormSection,
        FileField,
    },
    watch: {
        managesOrg: function() {
            if (this.managesOrg == 'Yes'){
              this.newOrg.detailsChecked = false;
              this.role = 'employee'
            } else if (this.managesOrg == 'Consultant'){
              this.newOrg.detailsChecked = false;
              this.role ='consultant'
            }else{this.role = null
              this.newOrg.detailsChecked = false;
            }

            if (this.managesOrg  == 'Yes' && !this.hasOrgs && this.newOrg){
                 this.addCompany()
            } else if (this.managesOrg == 'No' && this.newOrg){
                this.resetNewOrg();
                this.uploadedFile = null;
                this.addingCompany = false;
            } else {
                this.addCompany()
                this.addingCompany=false
            }
        },
    },
    computed: {
        postalAddressReadonly: function() {
            if (this.readonly || this.profile.postal_same_as_residential) {
                return true;
            }
        },
        electoralRollDocumentUrl: function() {
            let url = '';
            if (this.profile && this.profile.id) {
                url = helpers.add_endpoint_join(
                    '/api/proposal/',
                    this.proposalId + '/process_electoral_roll_document/'
                )
            }
            return url;
        },
        classCompute:function(){
          return this.isApplication? 'row' : 'container';
        },
        hasOrgs: function() {
            return this.profile.mooringlicensing_organisations && this.profile.mooringlicensing_organisations.length > 0 ? true: false;
        },
        uploadedFileName: function() {
            return this.uploadedFile != null ? this.uploadedFile.name: '';
        },
        uploadedIDFileName: function() {
            return this.uploadedID != null ? this.uploadedID.name: '';
        },
        isFileUploaded: function() {
            return this.uploadedFile != null ? true: false;
        },
        isNewOrgDetails: function() {
            return this.newOrg && this.newOrg.name != '' && this.newOrg.abn != '' ? true: false;
        },
        showCompletion: function() {
            return this.$route.name == 'first-time'
        },
        completedProfile: function(){
            return this.profile.contact_details && this.profile.personal_details && this.profile.address_details;
        },
    },
    methods: {
        uploadProofElectoralRoll: function() {
            console.log("proof");
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
        readFileID: function() {
            let vm = this;
            let _file = null;
            var input = $(vm.$refs.uploadedID)[0];
            if (input.files && input.files[0]) {
                var reader = new FileReader();
                reader.readAsDataURL(input.files[0]);
                reader.onload = function(e) {
                    _file = e.target.result;
                };
                _file = input.files[0];
            }
            vm.uploadedID = _file;
        },
        addCompany: function (){
            this.newOrg.push = {
                'name': '',
                'abn': '',
            };
            this.addingCompany=true;
        },
        resetNewOrg: function(){
            this.newOrg = {
                'detailsChecked': false,
                'exists': false
            };
        },
        updatePersonal: function() {
            let vm = this;
            //console.log(vm.profile);
            vm.missing_fields = [];
            var required_fields=[];
            vm.errorListPersonal=[];
            required_fields = $('#first_name, #surname')
            vm.missing_fields = [];
            required_fields.each(function() {
            if (this.value == '') {
                    //var text = $('#'+id).text()
                    //console.log(this);
                    vm.errorListPersonal.push('Value not provided: ' + this.name)
                    vm.missing_fields.push({id: this.id});
                }
            });

            if (vm.missing_fields.length > 0)
            {
              vm.showPersonalError = true;
              //console.log(vm.showPersonalError)
            }
            else
            {
              vm.showPersonalError = false;
            vm.updatingPersonal = true;
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.users,(vm.profile.id+'/update_personal')),JSON.stringify(vm.profile),{
                emulateJSON:true
            }).then((response) => {
                //console.log(response);
                vm.updatingPersonal = false;
                vm.profile = response.body;
                if (vm.profile.residential_address == null){ vm.profile.residential_address = {}; }
                if (vm.profile.postal_address == null){ vm.profile.postal_address = {}; }
            }, (error) => {
                console.log(error);
                vm.updatingPersonal = false;
            });
          }
        },
        
        uploadID: function() {
            let vm = this;
            console.log('uploading id');
            vm.uploadingID = true;
            let data = new FormData();
            data.append('identification', vm.uploadedID);
            console.log(data);
            if (vm.uploadedID == null){
                vm.uploadingID = false;
                swal({
                        title: 'Upload ID',
                        html: 'Please select a file to upload.',
                        type: 'error'
                });
            } else {
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.users,(vm.profile.id+'/upload_id')),data,{
                    emulateJSON:true
                }).then((response) => {
                    vm.uploadingID = false;
                    vm.uploadedID = null;
                    swal({
                        title: 'Upload ID',
                        html: 'Your ID has been successfully uploaded.',
                        type: 'success',
                    }).then(() => {
                        window.location.reload(true);
                    });
                }, (error) => {
                    console.log(error);
                    vm.uploadingID = false;
                    let error_msg = '<br/>';
                    for (var key in error.body) {
                        error_msg += key + ': ' + error.body[key] + '<br/>';
                    }
                    swal({
                        title: 'Upload ID',
                        html: 'There was an error uploading your ID.<br/>' + error_msg,
                        type: 'error'
                    });
                });
            }
        },
        
        updateContact: function() {
            let vm = this;
            vm.missing_fields = [];
            var required_fields=[];
            vm.errorListContact=[];
            required_fields = $('#email')
            vm.missing_fields = [];
            required_fields.each(function() {
            if (this.value == '') {
                    //var text = $('#'+id).text()
                    console.log(this);
                    vm.errorListContact.push('Value not provided: ' + this.name)
                    vm.missing_fields.push({id: this.id});
                }
            });
            if (vm.profile.mobile_number == '' || vm.profile.phone_number ==''){
              vm.errorListContact.push('Value not provided: mobile/ Phone number')
              vm.missing_fields.push({id: $('#mobile').id});
            }
            if (vm.missing_fields.length > 0)
            {
              vm.showContactError = true;
            }
            else{
              vm.showContactError = false;
            vm.updatingContact = true;
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.users,(vm.profile.id+'/update_contact')),JSON.stringify(vm.profile),{
                emulateJSON:true
            }).then((response) => {
                //console.log(response);
                vm.updatingContact = false;
                vm.profile = response.body;
                if (vm.profile.residential_address == null){ vm.profile.residential_address = {}; }
                if (vm.profile.postal_address == null){ vm.profile.postal_address = {}; }
            }, (error) => {
                console.log(error);
                vm.updatingContact = false;
            });
          }
        },
        updateAddress: async function() {
            let vm = this;

            vm.missing_fields = [];
            var required_fields=[];
            vm.errorListAddress=[];
            required_fields = $('#postcode, #line1, #locality, #country, #state')
            vm.missing_fields = [];
            required_fields.each(function() {
            if (this.value == '') {
                    //var text = $('#'+id).text()
                    vm.errorListAddress.push('Value not provided: ' + this.name)
                    vm.missing_fields.push({id: this.id});
                }
            });

            if (vm.missing_fields.length > 0)
            {
              vm.showAddressError = true;
            }
            else{
              vm.showAddressError = false;

            vm.updatingAddress = true;
            let payload = {}
            payload.residential_address = Object.assign({}, vm.profile.residential_address);
            payload.postal_address = Object.assign({}, vm.profile.postal_address);
            if (vm.profile.postal_same_as_residential) {
                payload.postal_same_as_residential = true;
            }
            try {
                const response = await vm.$http.post(helpers.add_endpoint_json(api_endpoints.users,(vm.profile.id+'/update_address')), payload);
                vm.updatingAddress = false;
                vm.profile = response.body;
                if (vm.profile.residential_address == null){ vm.profile.residential_address = {}; }
                if (vm.profile.postal_address == null){ vm.profile.postal_address = {}; }
            } catch (error) {
                swal({
                    title: "Please fix these errors before saving",
                    //text: error.bodyText,
                    html: helpers.formatError(error),
                    type:'error'
                });

                vm.updatingAddress = false;
            }
          }
        },
        updateSystemSettings: function() {
            let vm = this;
            vm.updatingSystemSettings=true;
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.users,(vm.profile.id+'/update_system_settings')),JSON.stringify(vm.profile.system_settings),{
                emulateJSON:true
            }).then((response) => {
                //console.log(response);
                vm.updatingSystemSettings=false;
                vm.profile = response.body;
                if (vm.profile.residential_address == null){ vm.profile.residential_address = {}; }
                if (vm.profile.postal_address == null){ vm.profile.postal_address = {}; }
            }, (error) => {
                console.log(error);
                vm.updatingSystemSettings=false;
            });
        },
        checkOrganisation: function() {
            let vm = this;
            //this.newOrg.abn = this.newOrg.abn.replace(/\s+/g,'');
            this.newOrg.abn = this.newOrg.abn.replace(/[^0-9]/g,'')

            vm.$http.post(helpers.add_endpoint_json(api_endpoints.organisations,'existance'),JSON.stringify(this.newOrg),{
                emulateJSON:true
            }).then((response) => {
                //console.log(response);
                this.newOrg.exists = response.body.exists;
                this.newOrg.detailsChecked = true;
                this.newOrg.id = response.body.id;
                if (response.body.first_five){this.newOrg.first_five = response.body.first_five }
            }, (error) => {
                console.log(error);
            });
        },

        fetchOrgRequestList: function() { //Fetch all the Organisation requests submitted by user which are pending for approval.
            let vm = this;
            vm.$http.get(helpers.add_endpoint_json(api_endpoints.organisation_requests,'get_pending_requests')).then((response) => {
                
                vm.orgRequest_list=response.body; 
            }, (error) => {
                console.log(error);
            });
        },



        validatePins: function() {
            let vm = this;
            vm.validatingPins = true;
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.organisations,(vm.newOrg.id+'/validate_pins')),JSON.stringify(this.newOrg),{
                emulateJSON:true
            }).then((response) => {
                if (response.body.valid){
                    swal(
                        'Validate Pins',
                        'The pins you entered have been validated and your request will be processed by Organisation Administrator.',
                        'success'
                    )
                    vm.registeringOrg = false;
                    vm.uploadedFile = null;
                    vm.addingCompany = false;
                    vm.resetNewOrg();
                    Vue.http.get(api_endpoints.profile).then((response) => {
                        vm.profile = response.body
                        if (vm.profile.residential_address == null){ vm.profile.residential_address = {}; }
                        if (vm.profile.postal_address == null){ vm.profile.postal_address = {}; }
                        if ( vm.profile.mooringlicensing_organisations && vm.profile.mooringlicensing_organisations.length > 0 ) { vm.managesOrg = 'Yes' }
                    },(error) => {
                        console.log(error);
                    })
                }else {
                    swal(
                        'Validate Pins',
                        'The pins you entered were incorrect', 
                        'error'
                    )
                }
                vm.validatingPins = false;
            }, (error) => {
                vm.validatingPins = false;
                console.log(error);
            });
        },
        orgRequest: function() {
            let vm = this;
            vm.registeringOrg = true;
            let data = new FormData();
            vm.newOrg.abn = vm.newOrg.abn.replace(/[^0-9]/g,'')
            data.append('name', vm.newOrg.name);
            data.append('abn', vm.newOrg.abn);
            data.append('identification', vm.uploadedFile);
            data.append('role',vm.role);
            if (vm.newOrg.name == '' || vm.newOrg.abn == '' || vm.uploadedFile == null){
                vm.registeringOrg = false;
                swal(
                    'Error submitting organisation request',
                    'Please enter the organisation details and attach a file before submitting your request.',
                    'error'
                )
            } else {
                vm.$http.post(api_endpoints.organisation_requests,data,{
                    emulateJSON:true
                }).then((response) => {
                    vm.registeringOrg = false;
                    vm.uploadedFile = null;
                    vm.addingCompany = false;
                    vm.resetNewOrg();
                    swal({
                        title: 'Sent',
                        html: 'Your organisation request has been successfully submitted.',
                        type: 'success',
                    }).then(() => {
                        window.location.reload(true);
                    });
                }, (error) => {
                    console.log(error);
                    vm.registeringOrg = false;
                    let error_msg = '<br/>';
                    for (var key in error.body) {
                        error_msg += key + ': ' + error.body[key] + '<br/>';
                    }
                    swal(
                        'Error submitting organisation request',
                        error_msg,
                        'error'
                    );
                });
            }

        },
        orgConsultRequest: function() {
            let vm = this;
            vm.registeringOrg = true;
            let data = new FormData();
            let new_organisation = vm.newOrg;
            for (var organisation in vm.profile.mooringlicensing_organisations) {
                if (new_organisation.abn && vm.profile.mooringlicensing_organisations[organisation].abn == new_organisation.abn) {
                    swal({
                        title: 'Checking Organisation',
                        html: 'You are already associated with this organisation.',
                        type: 'info'
                    })
                    vm.registeringOrg = false;
                    vm.uploadedFile = null;
                    vm.addingCompany = false;
                    vm.resetNewOrg();
                    return;
                }
            }
            vm.newOrg.abn = vm.newOrg.abn.replace(/[^0-9]/g,'')
            data.append('name', vm.newOrg.name);
            data.append('abn', vm.newOrg.abn);
            data.append('identification', vm.uploadedFile);
            data.append('role',vm.role);
            if (vm.newOrg.name == '' || vm.newOrg.abn == '' || vm.uploadedFile == null){
                vm.registeringOrg = false;
                swal(
                    'Error submitting organisation request',
                    'Please enter the organisation details and attach a file before submitting your request.',
                    'error'
                )
            } else {
                vm.$http.post(api_endpoints.organisation_requests,data,{
                    emulateJSON:true
                }).then((response) => {
                    vm.registeringOrg = false;
                    vm.uploadedFile = null;
                    vm.addingCompany = false;
                    vm.resetNewOrg();
                    swal({
                        title: 'Sent',
                        html: 'Your organisation request has been successfully submitted.',
                        type: 'success',
                    }).then(() => {
                        if (this.$route.name == 'account'){
                           window.location.reload(true);
                        }
                    });
                }, (error) => {
                    console.log(error);
                    vm.registeringOrg = false;
                    let error_msg = '<br/>';
                    for (var key in error.body) {
                        error_msg += key + ': ' + error.body[key] + '<br/>';
                    }
                    swal(
                        'Error submitting organisation request',
                        error_msg,
                        'error'
                    );
                });
            }
        },
        toggleSection: function (e) {
            let el = e.target;
            let chev = null;
            //console.log(el);
            $(el).on('click', function (event) {
                chev = $(this);
                //console.log(chev);
                $(chev).toggleClass('glyphicon-chevron-down glyphicon-chevron-up');
            })
        },
        fetchCountries:function (){
            let vm =this;
            vm.loading.push('fetching countries');
            vm.$http.get(api_endpoints.countries).then((response)=>{
                vm.countries = response.body;
                vm.loading.splice('fetching countries',1);
            },(response)=>{
                //console.log(response);
                vm.loading.splice('fetching countries',1);
            });
        },
        unlinkUser: function(org){
            let vm = this;
            let org_name = org.name;
            swal({
                title: "Unlink From Organisation",
                text: "Are you sure you want to be unlinked from "+org.name+" ?",
                type: "question",
                showCancelButton: true,
                confirmButtonText: 'Accept'
            }).then(() => {
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.organisations,org.id+'/unlink_user'),JSON.stringify(vm.profile),{
                    emulateJSON:true
                }).then((response) => {
                    Vue.http.get(api_endpoints.profile).then((response) => {
                        vm.profile = response.body
                        if (vm.profile.residential_address == null){ vm.profile.residential_address = {}; }
                        if ( vm.profile.mooringlicensing_organisations && vm.profile.mooringlicensing_organisations.length > 0 ) { vm.managesOrg = 'Yes' }
                    },(error) => {
                        console.log(error);
                    })
                    swal(
                        'Unlink',
                        'You have been successfully unlinked from '+org_name+'.',
                        'success'
                    )
                }, (error) => {
                    swal(
                        'Unlink',
                        'There was an error unlinking you from '+org_name+'. '+error.body,
                        'error'
                    )
                });
            },(error) => {
            }); 
        },
        fetchProfile: async function(){
            let response = null;
            //let submitter_id = 666;
            if (this.submitterId) {
                response = await Vue.http.get(`${api_endpoints.submitter_profile}?submitter_id=${this.submitterId}`);
            } else {
                response = await Vue.http.get(api_endpoints.profile);
            }
            this.profile = response.body
            if (this.profile.residential_address == null){ this.profile.residential_address = {}; }
            if (this.profile.postal_address == null){ this.profile.postal_address = {}; }
            //if (this.profile.mooringlicensing_organisations && this.profile.mooringlicensing_organisations.length > 0 ) { this.managesOrg = 'Yes' }
            this.phoneNumberReadonly = this.profile.phone_number === '' || this.profile.phone_number === null || this.profile.phone_number === 0 ?  false : true;
            this.mobileNumberReadonly = this.profile.mobile_number === '' || this.profile.mobile_number === null || this.profile.mobile_number === 0 ?  false : true;

        },
    },
    beforeRouteEnter: function(to,from,next){
        Vue.http.get(api_endpoints.profile).then((response) => {
            if (response.body.address_details && response.body.personal_details && response.body.contact_details && to.name == 'first-time'){
                window.location.href='/';
            }
            else{
                next(vm => {
                    vm.profile = response.body
                    if (vm.profile.residential_address == null){ vm.profile.residential_address = {}; }
                    if (vm.profile.postal_address == null){ vm.profile.postal_address = {}; }
                    //if ( vm.profile.mooringlicensing_organisations && vm.profile.mooringlicensing_organisations.length > 0 ) { vm.managesOrg = 'Yes' }
                });
            }
        },(error) => {
            console.log(error);
        })
    },

    mounted: async function(){
        this.fetchCountries();
        this.fetchOrgRequestList();
        await this.fetchProfile(); //beforeRouteEnter doesn't work when loading this component in Application.vue so adding an extra method to get profile details.
        await this.$nextTick(() => {
            this.$emit('profile-fetched', this.profile);
        });
        this.personal_form = document.forms.personal_form;
        $('.panelClicker[data-toggle="collapse"]').on('click', function () {
            var chev = $(this).children()[0];
            window.setTimeout(function () {
                $(chev).toggleClass("glyphicon-chevron-down glyphicon-chevron-up");
            },100);
        });
        // read in storedSilentElector
        //if (this.storedSilentElector !== null) {
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
.electoral-label {
    margin-bottom: 25px !important;
}
.label-right {
    float: right;
    text-align: left;
    /*margin-right: 50%;*/
}
/*
input[type=checkbox] {
    transform: scale(0.4, 0.4);
    float: left;
}
*/
/*
input[type=checkbox] {
}
*/
.address-box {
    border: 1px solid;
    border-color: #DCDCDC;
    padding: 15px;
}
</style>
