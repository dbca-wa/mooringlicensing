<template lang="html">
    <div class="container" >
        <form :action="proposal_form_url" method="post" name="new_proposal" enctype="multipart/form-data">
            <div v-if="!proposal_readonly">
              <div v-if="hasAmendmentRequest" class="row" style="color:red;">
                  <div class="col-lg-12 pull-right">
                    <div class="panel panel-default">
                      <div class="panel-heading">
                        <h3 class="panel-title" style="color:red;">An amendment has been requested for this Application
                          <a class="panelClicker" :href="'#'+pBody" data-toggle="collapse"  data-parent="#userInfo" expanded="true" :aria-controls="pBody">
                                <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                          </a>
                        </h3>
                      </div>
                      <div class="panel-body collapse in" :id="pBody">
                        <div v-for="a in amendment_request">
                          <p>Reason: {{a.reason}}</p>
                          <p>Details: <p v-for="t in splitText(a.text)">{{t}}</p></p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div id="error" v-if="missing_fields.length > 0" style="margin: 10px; padding: 5px; color: red; border:1px solid red;">
                <b>Please answer the following mandatory question(s):</b>
                <ul>
                    <li v-for="error in missing_fields">
                        {{ error.label }}
                    </li>
                </ul>
            </div>
            <WaitingListApplication
            v-if="proposal && proposal.application_type_code==='wla'"
            :proposal="proposal"
            :is_external="true"
            ref="waiting_list_application"
            :showElectoralRoll="showElectoralRoll"
            :readonly="readonly"
            :submitterId="submitterId"
            @updateAutoApprove="updateAutoApprove"
            @updateSubmitText="updateSubmitText"
            @vesselChanged="updateVesselChanged"
            @mooringPreferenceChanged="updateMooringPreference"
            @noVessel="noVessel"
            />

            <AnnualAdmissionApplication
            v-if="proposal && proposal.application_type_code==='aaa'"
            :proposal="proposal"
            :is_external="true"
            ref="annual_admission_application"
            :showElectoralRoll="showElectoralRoll"
            :readonly="readonly"
            :submitterId="submitterId"
            @updateAutoApprove="updateAutoApprove"
            @updateSubmitText="updateSubmitText"
            @vesselChanged="updateVesselChanged"
            @noVessel="noVessel"
            />
            <AuthorisedUserApplication
            v-if="proposal && proposal.application_type_code==='aua'"
            :proposal="proposal"
            :is_external="true"
            ref="authorised_user_application"
            :readonly="readonly"
            :submitterId="submitterId"
            @updateSubmitText="updateSubmitText"
            @updateAutoApprove="updateAutoApprove"
            @vesselChanged="updateVesselChanged"
            @changeMooring="updateMooringAuth"
            @noVessel="noVessel"
            />
            <MooringLicenceApplication
            v-if="proposal && proposal.application_type_code==='mla'"
            :proposal="proposal"
            :is_external="true"
            ref="mooring_licence_application"
            :showElectoralRoll="showElectoralRoll"
            :readonly="readonly"
            :submitterId="submitterId"
            @updateSubmitText="updateSubmitText"
            @updateAutoApprove="updateAutoApprove"
            @vesselChanged="updateVesselChanged"
            @noVessel="noVessel"
            />

            <div>
                <input type="hidden" name="csrfmiddlewaretoken" :value="csrf_token"/>
                <input type='hidden' name="schema" :value="JSON.stringify(proposal)" />
                <input type='hidden' name="proposal_id" :value="1" />

                <div class="row" style="margin-bottom: 50px">
                        <div  class="container">
                          <div class="row" style="margin-bottom: 50px">
                              <div class="navbar navbar-fixed-bottom"  style="background-color: #f5f5f5;">
                                  <div class="navbar-inner">
                                    <div v-if="proposal && !proposal.readonly" class="container">
                                        <p class="pull-right" style="margin-top:5px">
                                            <input type="checkbox" v-model="terms_and_conditions_checked" id="terms_and_conditions_checked" />
                                            <label for="terms_and_conditions_checked">
                                                I agree with all the <a href="https://rottnestisland.com/boating/boating-on-rottnest-island/tandc" target="_blank">RIA Terms and Conditions</a>
                                            </label>

                                            <button v-if="saveExitProposal" type="button" class="btn btn-primary" disabled>
                                                Save and Exit&nbsp;<i class="fa fa-circle-o-notch fa-spin fa-fw"></i>
                                            </button>
                                            <input v-else type="button" @click.prevent="save_exit" class="btn btn-primary" value="Save and Exit" :disabled="savingProposal || paySubmitting"/>

                                            <button v-if="savingProposal" type="button" class="btn btn-primary" disabled>
                                                Save and Continue&nbsp;<i class="fa fa-circle-o-notch fa-spin fa-fw"></i>
                                            </button>
                                            <input v-else type="button" @click.prevent="save" class="btn btn-primary" value="Save and Continue" :disabled="saveExitProposal || paySubmitting"/>

                                            <button v-if="paySubmitting || !terms_and_conditions_checked" type="button" class="btn btn-primary" disabled>
                                                {{ submitText }}&nbsp; <i v-show="terms_and_conditions_checked" class="fa fa-circle-o-notch fa-spin fa-fw"></i>
                                            </button>
                                            <input v-else 
                                            type="button" 
                                            @click.prevent="submit" 
                                            class="btn btn-primary" 
                                            :value="submitText" 
                                            :disabled="saveExitProposal || savingProposal || disableSubmit"
                                            id="submitButton"
                                            :title="disabledSubmitText"
                                            />

                                            <input id="save_and_continue_btn" type="hidden" @click.prevent="save_wo_confirm" class="btn btn-primary" value="Save Without Confirmation"/>
                                        </p>
                                    </div>
                                    <div v-else class="container">
                                      <p class="pull-right" style="margin-top:5px;">
                                        <router-link class="btn btn-primary" :to="{name: 'external-dashboard'}">Back to Dashboard</router-link>
                                      </p>
                                    </div>
                                  </div>
                                </div>
                            </div>
                        </div>
                </div>
            </div>

        </form>
    </div>
</template>
<script>
import WaitingListApplication from '../form_wla.vue';
import AnnualAdmissionApplication from '../form_aaa.vue';
import AuthorisedUserApplication from '../form_aua.vue';
import MooringLicenceApplication from '../form_mla.vue';
import Vue from 'vue'
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'
export default {
  name: 'ExternalProposal',
  data: function() {
    return {
      "proposal": null,
      "loading": [],
      form: null,
      amendment_request: [],
      //isDataSaved: false,
      proposal_readonly: true,
      hasAmendmentRequest: false,
      submitting: false,
      saveExitProposal: false,
      savingProposal:false,
      paySubmitting:false,
      newText: "",
      pBody: 'pBody',
      missing_fields: [],
      proposal_parks:null,
      terms_and_conditions_checked: false,
      vesselChanged: false,
      // AUA
      mooringOptionsChanged: false,
      // WLA
      mooringPreferenceChanged: false,
      submitText: "Submit",
      autoApprove: false,
      missingVessel: false,
    }
  },
  components: {
      WaitingListApplication,
      AnnualAdmissionApplication,
      AuthorisedUserApplication,
      MooringLicenceApplication,
  },
  watch: {
      disableSubmit() {
          //console.log("disableSubmit")
      },
  },
  computed: {
      disableSubmit: function() {
          let disable = false;
          if (this.proposal && this.proposal.proposal_type.code ==='amendment' && this.missingVessel) {
              disable = true;
          } else if (this.proposal && this.proposal.proposal_type.code ==='amendment') {
              if (['aaa', 'mla'].includes(this.proposal.application_type_code) && !this.vesselChanged) {
                  disable = true;
              } else if (this.proposal.application_type_code === 'wla' && !this.vesselChanged && !this.mooringPreferenceChanged) {
                  disable = true;
              } else if (this.proposal.application_type_code === 'aua' && !this.vesselChanged && !this.mooringOptionsChanged) {
                  disable = true;
              }
          }
          return disable;
      },
      disabledSubmitText: function() {
          let text = "";
          if (this.disableSubmit) {
              text = "No relevant details have been detected in this amendment application";
          }
          return text;
      },
      submitterId: function() {
          let submitter = null;
          if (this.proposal && this.proposal.submitter && this.proposal.submitter.id) {
              submitter = this.proposal.submitter.id;
          }
          return submitter;
      },
      readonly: function() {
          let returnVal = true;
          if (this.proposal.processing_status === 'Draft') {
              returnVal = false;
          }
          return returnVal;
      },
      isLoading: function() {
        return this.loading.length > 0
      },
      csrf_token: function() {
        return helpers.getCookie('csrftoken')
      },
      proposal_form_url: function() {
        return (this.proposal) ? `/api/proposal/${this.proposal.id}/draft.json` : '';
          // revert to above
        //return (this.proposal) ? `/api/proposal/${this.proposal.id}/submit.json` : '';
      },
      application_fee_url: function() {
          return (this.proposal) ? `/application_fee/${this.proposal.id}/` : '';
      },
      confirmation_url: function() {
          // For authorised user application and mooring licence application
          return (this.proposal) ? `/confirmation/${this.proposal.id}/` : '';
      },
      proposal_submit_url: function() {
        return (this.proposal) ? `/api/proposal/${this.proposal.id}/submit.json` : '';
        //return this.submit();
      },
      canEditActivities: function(){
        return this.proposal ? this.proposal.can_user_edit: 'false';
      },
      canEditPeriod: function(){
        return this.proposal ? this.proposal.can_user_edit: 'false';
      },
      trainingCompleted: function(){
        if(this.proposal.application_type== 'Event')
          {
            return this.proposal.applicant_training_completed;
          }
        return this.proposal.training_completed;
      },
      showElectoralRoll: function() {
          let show = false;
          if (this.proposal && ['wla', 'mla'].includes(this.proposal.application_type_code)) {
              show = true;
          }
          return show;
      },
      applicationTypeCode: function() {
          if (this.proposal) {
              return this.proposal.application_type_code;
          }
      },
      amendmentOrRenewal: function(){
          let amendRenew=false;
          //if (this.proposal && ['amendment', 'renewal'].includes(this.proposal.proposal_type.code)) 
          if(this.proposal && this.proposal.proposal_type && this.proposal.proposal_type.code !== 'new'){
              amendRenew=true;
          }
          return amendRenew;
      },
  },
  methods: {
    noVessel: function(noVessel) {
        this.missingVessel = noVessel;
    },
    updateAutoApprove: function(approve) {
        this.autoApprove = approve;
        //console.log("updateAutoApprove");
    },
    updateMooringAuth: function(changed) {
        this.mooringOptionsChanged = changed;
        //console.log("updateMooringAuth");
    },
    updateVesselChanged: function(vesselChanged) {
        this.vesselChanged = vesselChanged;
        //console.log("updateVesselChanged");
    },
    updateMooringPreference: function(preferenceChanged) {
        this.mooringPreferenceChanged = preferenceChanged;
        //console.log("updateMooringPreference");
    },
    proposal_refs:function(){
      if(this.applicationTypeCode == 'wla') {
          return this.$refs.waiting_list_application;
      } else if (this.applicationTypeCode == 'aaa') {
          return this.$refs.annual_admission_application;
      } else if (this.applicationTypeCode == 'aua') {
          return this.$refs.authorised_user_application;
      } else if (this.applicationTypeCode == 'mla') {
          return this.$refs.mooring_licence_application;
      }
    },
    updateSubmitText: function(submitText) {
        this.submitText = submitText;
    },
    save_applicant_data:function(){
      if(this.proposal.applicant_type == 'SUB')
      {
        this.proposal_refs().$refs.profile.updatePersonal();
        this.proposal_refs().$refs.profile.updateAddress();
        this.proposal_refs().$refs.profile.updateContact();
      }
    },


    set_formData: function(e) {
      let vm = this;
      let formData = new FormData(vm.form);
      return formData;
    },
    save: async function(withConfirm=true, url=this.proposal_form_url) {
        let vm = this;
        vm.savingProposal=true;
        vm.save_applicant_data();

        let payload = {
            proposal: {},
            vessel: {},
        }
        // WLA
        if (this.$refs.waiting_list_application) {
            payload.proposal.auto_approve = this.autoApprove;
            if (this.$refs.waiting_list_application.$refs.vessels) {
                payload.vessel = Object.assign({}, this.$refs.waiting_list_application.$refs.vessels.vessel);
                //payload.proposal.dot_name = this.$refs.waiting_list_application.$refs.vessels.dotName;
                //payload.vessel.vessel_ownership.dot_name = this.$refs.waiting_list_application.$refs.vessels.vessel.vessel_ownership.dotName;
                payload.proposal.temporary_document_collection_id = this.$refs.waiting_list_application.$refs.vessels.temporary_document_collection_id;
                payload.proposal.keep_existing_vessel = this.$refs.waiting_list_application.keepCurrentVessel;
            }
            if (typeof(this.$refs.waiting_list_application.$refs.profile.silentElector) === 'boolean') {
                payload.proposal.silent_elector = this.$refs.waiting_list_application.$refs.profile.silentElector;
            }
            if (this.$refs.waiting_list_application.$refs.mooring && this.$refs.waiting_list_application.$refs.mooring.selectedMooring) {
                //payload.proposal.preferred_bay_id = this.$refs.waiting_list_application.$refs.mooring.selectedMooring.id;
                payload.proposal.preferred_bay_id = this.$refs.waiting_list_application.$refs.mooring.selectedMooring;
            }
        // AAA
        } else if (this.$refs.annual_admission_application) {
            payload.proposal.auto_approve = this.autoApprove;
            if (this.$refs.annual_admission_application.$refs.vessels) {
                payload.vessel = Object.assign({}, this.$refs.annual_admission_application.$refs.vessels.vessel);
                payload.proposal.temporary_document_collection_id = this.$refs.annual_admission_application.$refs.vessels.temporary_document_collection_id;
                payload.proposal.keep_existing_vessel = this.$refs.annual_admission_application.keepCurrentVessel;
                //payload.vessel.vessel_ownership.dot_name = this.$refs.annual_admission_application.$refs.vessels.vessel.vessel_ownership.dotName;
            }
            if (this.$refs.annual_admission_application.$refs.insurance.selectedOption) {
                // modify if additional proposal attributes required
                payload.proposal.insurance_choice = this.$refs.annual_admission_application.$refs.insurance.selectedOption;
            }
            /*
            if(this.amendmentOrRenewal && this.$refs.annual_admission_application.keepCurrentVessel){
                payload.ignore_insurance_check=true;
            }
            */
        // AUA
        } else if (this.$refs.authorised_user_application) {
            payload.proposal.auto_approve = this.autoApprove;
            if (this.$refs.authorised_user_application.$refs.vessels) {
                payload.vessel = Object.assign({}, this.$refs.authorised_user_application.$refs.vessels.vessel);
                payload.proposal.temporary_document_collection_id = this.$refs.authorised_user_application.$refs.vessels.temporary_document_collection_id;
                payload.proposal.keep_existing_vessel = this.$refs.authorised_user_application.keepCurrentVessel;
                //payload.vessel.vessel_ownership.dot_name = this.$refs.authorised_user_application.$refs.vessels.vessel.vessel_ownership.dotName;
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
                    payload.proposal.site_licensee_email = this.$refs.authorised_user_application.$refs.mooring_authorisation.siteLicenseeEmail;
                    payload.proposal.mooring_id = this.$refs.authorised_user_application.$refs.mooring_authorisation.mooringSiteId;
                }
            }
            /*
            if(this.amendmentOrRenewal && this.$refs.authorised_user_application.keepCurrentVessel){
                payload.ignore_insurance_check=true;
            }
            */
        // MLA
        } else if (this.$refs.mooring_licence_application) {
            payload.proposal.auto_approve = this.autoApprove;
            //this.vesselChanged = await this.$refs.mooring_licence_application.$refs.vessels.vesselChanged();
            //console.log(vesselChanged);
            if (this.$refs.mooring_licence_application.$refs.vessels) {
                payload.vessel = Object.assign({}, this.$refs.mooring_licence_application.$refs.vessels.vessel);
                payload.vessel.readonly = this.$refs.mooring_licence_application.$refs.vessels.readonly;
                payload.proposal.temporary_document_collection_id = this.$refs.mooring_licence_application.$refs.vessels.temporary_document_collection_id;
                payload.proposal.keep_existing_vessel = this.$refs.mooring_licence_application.keepCurrentVessel;
                //payload.vessel.vessel_ownership.dot_name = this.$refs.mooring_licence_application.$refs.vessels.vessel.vessel_ownership.dotName;
            }
            if (typeof(this.$refs.mooring_licence_application.$refs.profile.silentElector) === 'boolean') {
            //if (this.$refs.mooring_licence_application.$refs.profile.silentElector !== null) {
            //if (this.$refs.mooring_licence_application.$refs.profile.profile.hasOwnProperty('silent_elector')) {
                payload.proposal.silent_elector = this.$refs.mooring_licence_application.$refs.profile.silentElector;
            }
            if (this.$refs.mooring_licence_application.$refs.insurance.selectedOption) {
                // modify if additional proposal attributes required
                payload.proposal.insurance_choice = this.$refs.mooring_licence_application.$refs.insurance.selectedOption;
            }
            /*
            if(this.amendmentOrRenewal && this.$refs.mooring_licence_application.keepCurrentVessel){
              payload.ignore_insurance_check=true;
            } else if(this.amendmentOrRenewal && !this.$refs.mooring_licence_application.keepCurrentVessel){
              payload.proposal.keep_existing_vessel=false;
            }
            */
        }

        //vm.$http.post(vm.proposal_form_url,payload).then(res=>{
        const res = await vm.$http.post(url, payload);
        if (res.ok) {
            if (withConfirm) {
                swal(
                    'Saved',
                    'Your application has been saved',
                    'success'
                );
            };
            vm.savingProposal=false;
            return res;
        } else {
            swal({
                title: "Please fix following errors before saving",
                text: err.bodyText,
                type:'error'
            });
            vm.savingProposal=false;
        }
    },
    save_exit: function() {
      let vm = this;
      this.submitting = true;
      this.saveExitProposal=true;
      this.save();
      this.saveExitProposal=false;
      // redirect back to dashboard
      vm.$router.push({
        name: 'external-dashboard'
      });
    },

    save_wo_confirm: function() {
      this.save(false);
        /*
      let vm = this;
      vm.save_applicant_data();
      let formData = vm.set_formData()

      vm.$http.post(vm.proposal_form_url,formData);
      */
    },
    save_and_pay: async function() {
        //let formData = this.set_formData()
        //console.log('in save_and_pay')
        try {
            const res = await this.save(false, this.proposal_submit_url);
            this.$nextTick(async () => {
                if (this.autoApprove) {
                    //await this.post_and_redirect(this.application_fee_url, {'auto_approve': true, 'csrfmiddlewaretoken' : this.csrf_token});
                    await this.post_and_redirect(this.application_fee_url, {'csrfmiddlewaretoken' : this.csrf_token});
                } else if (['wla', 'aaa'].includes(this.proposal.application_type_code)) {
                    console.log('aho1')
                    await this.post_and_redirect(this.application_fee_url, {'csrfmiddlewaretoken' : this.csrf_token});
                    console.log('aho2')
                } else {
                    await this.post_and_redirect(this.confirmation_url, {'csrfmiddlewaretoken' : this.csrf_token});
                    //this.$router.push({
                    //    name: 'external-dashboard'
                    //});
                }
            });
        } catch(err) {
            console.log('aho3')
            console.log(err)
            console.log(typeof(err.body))
            await swal({
                title: 'Submit Error',
                //text: helpers.apiVueResourceError(err),
                html: helpers.formatError(err),
                type: "error",
                //html: true,
            })
            this.savingProposal=false;
            this.paySubmitting=false;
            //this.submitting = false;
        }
    },
    save_without_pay: async function(){
        /* just save and submit - no payment required (probably application was pushed back by assessor for amendment */
        let vm = this
        try {
            const res = await this.save(false, this.proposal_submit_url);
            if (res.ok) {
                vm.$router.push({
                  name: 'external-dashboard'
                });
            }
        } catch(err) {
            //console.log(err)
            //console.log(typeof(err.body))
            await swal({
                title: 'Submit Error',
                //text: helpers.apiVueResourceError(err),
                html: helpers.formatError(err),
                type: "error",
                //html: true,
            })
            this.savingProposal=false;
            this.paySubmitting=false;
            //this.submitting = false;
        }
    },
    setdata: function(readonly){
      this.proposal_readonly = readonly;
    },

    setAmendmentData: function(amendment_request){
      this.amendment_request = amendment_request;

      if (amendment_request.length > 0)
        this.hasAmendmentRequest = true;

    },

    splitText: function(aText){
      let newText = '';
      newText = aText.split("\n");
      return newText;

    },

    leaving: function(e) {
      let vm = this;
      var dialogText = 'You have some unsaved changes.';
      if (!vm.proposal_readonly && !vm.submitting){
        e.returnValue = dialogText;
        return dialogText;
      }
      else{
        return null;
      }
    },

    highlight_missing_fields: function(){
        let vm = this;
        for (var missing_field of vm.missing_fields) {
            $("#" + missing_field.id).css("color", 'red');
        }
    },
    /*
    validate: function(){
        let vm = this;

        // reset default colour
        for (var field of vm.missing_fields) {
            $("#" + field.id).css("color", '#515151');
        }
        vm.missing_fields = [];

        // get all required fields, that are not hidden in the DOM
        //var hidden_fields = $('input[type=text]:hidden, textarea:hidden, input[type=checkbox]:hidden, input[type=radio]:hidden, input[type=file]:hidden');
        //hidden_fields.prop('required', null);
        //var required_fields = $('select:required').not(':hidden');
        var required_fields = $('input[type=text]:required, textarea:required, input[type=checkbox]:required, input[type=radio]:required, input[type=file]:required, select:required').not(':hidden');
        console.log(required_fields);
        // loop through all (non-hidden) required fields, and check data has been entered
        required_fields.each(function() {

            //console.log('type: ' + this.type + ' ' + this.name)
            var id = 'id_' + this.name
            if (this.type == 'radio') {
                //if (this.type == 'radio' && !$("input[name="+this.name+"]").is(':checked')) {
                if (!$("input[name="+this.name+"]").is(':checked')) {
                    var text = $('#'+id).text()
                    console.log('radio not checked: ' + this.type + ' ' + text)
                    vm.missing_fields.push({id: id, label: text});
                }
            }

            if (this.type == 'checkbox') {
                //if (this.type == 'radio' && !$("input[name="+this.name+"]").is(':checked')) {
                var id = 'id_' + this.classList['value']
                if ($("[class="+this.classList['value']+"]:checked").length == 0) {
                    var text = $('#'+id).text()
                    console.log('checkbox not checked: ' + this.type + ' ' + text)
                    vm.missing_fields.push({id: id, label: text});
                }
            }

            if (this.type == 'select-one') {
                if ($(this).val() == '') {
                    var text = $('#'+id).text()  // this is the (question) label
                    var id = 'id_' + $(this).prop('name'); // the label id
                    console.log('selector not selected: ' + this.type + ' ' + text)
                    vm.missing_fields.push({id: id, label: text});
                }
            }

            if (this.type == 'file') {
                var num_files = $('#'+id).attr('num_files')
                if (num_files == "0") {
                    var text = $('#'+id).text()
                    console.log('file not uploaded: ' + this.type + ' ' + this.name)
                    vm.missing_fields.push({id: id, label: text});
                }
            }

            if (this.type == 'text') {
                if (this.value == '') {
                    var text = $('#'+id).text()
                    console.log('text not provided: ' + this.type + ' ' + this.name)
                    vm.missing_fields.push({id: id, label: text});
                }
            }

            if (this.type == 'textarea') {
                if (this.value == '') {
                    var text = $('#'+id).text()
                    console.log('textarea not provided: ' + this.type + ' ' + this.name)
                    vm.missing_fields.push({id: id, label: text});
                }
            }

        });

        return vm.missing_fields.length
    },
      */

    can_submit: function(){
      let vm=this;
      let blank_fields=[]

      if (vm.proposal.application_type==vm.application_type_tclass) {
          if (vm.$refs.proposal_tclass.$refs.other_details.selected_accreditations.length==0 ){
            blank_fields.push(' Level of Accreditation is required')
          }
          else{
            for(var i=0; i<vm.proposal.other_details.accreditations.length; i++){
              if(!vm.proposal.other_details.accreditations[i].is_deleted && vm.proposal.other_details.accreditations[i].accreditation_type!='no'){
                if(vm.proposal.other_details.accreditations[i].accreditation_expiry==null || vm.proposal.other_details.accreditations[i].accreditation_expiry==''){
                  blank_fields.push('Expiry date for accreditation type '+vm.proposal.other_details.accreditations[i].accreditation_type_value+' is required')
                }
                // var acc_doc_ref='accreditation_file'+vm.proposal.other_details.accreditations[i].accreditation_type;
                var acc_ref= vm.proposal.other_details.accreditations[i].accreditation_type;
                // console.log(acc_doc_ref, acc_ref);
                if(vm.$refs.proposal_tclass.$refs.other_details.$refs[acc_ref][0].$refs.accreditation_file.documents.length==0){
                  blank_fields.push('Accreditation Certificate for accreditation type '+vm.proposal.other_details.accreditations[i].accreditation_type_value+' is required')
                }

              }
            }
          }

          if (vm.proposal.other_details.preferred_licence_period=='' || vm.proposal.other_details.preferred_licence_period==null ){
            blank_fields.push(' Preferred Licence Period is required')
          }
          if (vm.proposal.other_details.nominated_start_date=='' || vm.proposal.other_details.nominated_start_date==null ){
            blank_fields.push(' Licence Nominated Start Date is required')
          }

          if(vm.$refs.proposal_tclass.$refs.other_details.$refs.deed_poll_doc.documents.length==0){
            blank_fields.push(' Deed poll document is missing')
          }

          if(vm.$refs.proposal_tclass.$refs.other_details.$refs.currency_doc.documents.length==0){
            blank_fields.push(' Certificate of currency document is missing')
          }
          if(vm.proposal.other_details.insurance_expiry=='' || vm.proposal.other_details.insurance_expiry==null){
            blank_fields.push(' Certificate of currency expiry date is missing')
          }

      } else if (vm.proposal.application_type==vm.application_type_filming) {
          blank_fields=vm.can_submit_filming()

      } else if (vm.proposal.application_type==vm.application_type_event) {
          blank_fields=vm.can_submit_event();

      }

      if(blank_fields.length==0){
        return true;
      }
      else{
        return blank_fields;
      }

    },
    submit: async function(){
        //console.log('in submit()')
        //let vm = this;

        // remove the confirm prompt when navigating away from window (on button 'Submit' click)
        this.submitting = true;
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
            this.submitting = false;
            this.paySubmitting=false;
            return;
        }

        if (!this.proposal.fee_paid) {
            this.$nextTick(async () => {
                try {
                    await this.save_and_pay();
                    console.log('aho5')
                } catch (err) {
                    console.log(err)
                    await swal({
                        title: 'Submit Error',
                        //text: helpers.apiVueResourceError(err),
                        html: helpers.formatError(err),
                        type: "error",
                        //html: true,
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
        console.log(url)
        console.log(postData)
        var postFormStr = "<form method='POST' action='" + url + "'>";

        for (var key in postData) {
            if (postData.hasOwnProperty(key)) {
                postFormStr += "<input type='hidden' name='" + key + "' value='" + postData[key] + "'>";
            }
        }
        postFormStr += "</form>";
        var formElement = $(postFormStr);
        $('body').append(formElement);
        $(formElement).submit();
        console.log('aho4')
    },

  },

  mounted: function() {
    let vm = this;
    vm.form = document.forms.new_proposal;
    //this.addEventListeners();
      /* uncomment later - too annoying while making front end changes
    window.addEventListener('beforeunload', vm.leaving);
    window.addEventListener('onblur', vm.leaving);
    */
  },


  beforeRouteEnter: function(to, from, next) {
    if (to.params.proposal_id) {
      let vm = this;
      Vue.http.get(`/api/proposal/${to.params.proposal_id}.json`).then(res => {
          next(vm => {
            vm.loading.push('fetching proposal')
            vm.proposal = res.body;
            //used in activities_land for T Class licence
            vm.loading.splice('fetching proposal', 1);
            vm.setdata(vm.proposal.readonly);
              /*
            Vue.http.get(helpers.add_endpoint_json(api_endpoints.proposals,to.params.proposal_id+'/amendment_request')).then((res) => {
                      vm.setAmendmentData(res.body);
                },
              err => {
                        console.log(err);
                  });
              */
              });
          },
        err => {
          //console.log(err);
        });
    }
      /*
    else {
      Vue.http.post('/api/proposal.json').then(res => {
          next(vm => {
            vm.loading.push('fetching proposal')
            vm.proposal = res.body;
            vm.loading.splice('fetching proposal', 1);
          });
        },
        err => {
          console.log(err);
        });
    }
    */
  }
}
</script>

<style lang="css" scoped>
</style>
