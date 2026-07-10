<template lang="html">
    <div class="container" >

        <div class="alert round-box col-12 px-3 mb-3" style='background: #c4e6fd; border: 1px solid #80beff'>
            <div>
            <strong>Privacy Notice</strong>
            </div>
            <div>
            <p>The Rottnest Island Authority (RIA) collects this personal information to issue with you with appropriate licenses permits and authorisations required for utilising moorings within the Rottnest Island Reserve.</p>
            <p>We may share this information with other organisations/individuals, to assess your applications and undertake compliance and monitoring of your activity on the island and to advise you of any changes to permissions or conditions as they arise. It may also be used to ensure compliance with other relevant legislation.</p>
            <p>You are required to provide this information/specific personal information to comply with <em>Rottnest Island Regulations 1988 and Rottnest Island Authority Act 1987.</em></p>
            <p>If you choose not to provide the required information we will be unable to issue you with the required permissions and any mooring use will be unlawful.</p>
            <p>For further details on how RIA manage your personal information, you can read the <a href="https://www.dbca.wa.gov.au/media/6324/download">Privacy Policy</a>. If you have any questions about how your personal information will be handled, or if you would like to access your personal information, please contact RIA on 08 9432 9300 or email <a href="mailto:privacy.rottnest@dbca.wa.gov.au">privacy.rottnest@dbca.wa.gov.au</a>.</p>
            </div>
        </div>
        <br>

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
                @updateSubmitText="updateSubmitText"
                @vesselChanged="updateVesselChanged"
                @mooringPreferenceChanged="updateMooringPreference"
                @updateVesselOwnershipChanged="updateVesselOwnershipChanged"
                @noVessel="noVessel"
                @profile-fetched="populateProfile"
            />

            <AnnualAdmissionApplication
                v-if="proposal && proposal.application_type_code==='aaa'"
                :proposal="proposal"
                :is_external="true"
                ref="annual_admission_application"
                :showElectoralRoll="showElectoralRoll"
                :readonly="readonly"
                @updateSubmitText="updateSubmitText"
                @vesselChanged="updateVesselChanged"
                @updateVesselOwnershipChanged="updateVesselOwnershipChanged"
                @noVessel="noVessel"
                @profile-fetched="populateProfile"
            />
            <AuthorisedUserApplication
                v-if="proposal && proposal.application_type_code==='aua'"
                :proposal="proposal"
                :is_external="true"
                ref="authorised_user_application"
                :readonly="readonly"
                @updateSubmitText="updateSubmitText"
                @vesselChanged="updateVesselChanged"
                @changeMooring="updateMooringAuth"
                @updateVesselOwnershipChanged="updateVesselOwnershipChanged"
                @noVessel="noVessel"
                @profile-fetched="populateProfile"
            />
            <MooringLicenceApplication
                v-if="proposal && proposal.application_type_code==='mla'"
                :proposal="proposal"
                :is_external="true"
                ref="mooring_licence_application"
                :showElectoralRoll="showElectoralRoll"
                :readonly="readonly"
                @updateSubmitText="updateSubmitText"
                @vesselChanged="updateVesselChanged"
                @updateVesselOwnershipChanged="updateVesselOwnershipChanged"
                @noVessel="noVessel"
                @profile-fetched="populateProfile"
            />

            <div>
                <input type="hidden" name="csrfmiddlewaretoken" :value="csrf_token"/>
                <input type='hidden' name="schema" :value="JSON.stringify(proposal)" />
                <input type='hidden' name="proposal_id" :value="1" />

                <div class="row">
                        <div  class="container">
                          <div class="row">
                              <div class="navbar navbar-fixed-bottom"  style="background-color: #f5f5f5;">
                                  <div class="navbar-inner">
                                    <div v-if="proposal && !proposal.readonly" class="container">
                                        <p class="pull-right" style="margin-top:5px">
                                            <input type="checkbox" v-model="terms_and_conditions_checked" id="terms_and_conditions_checked" />
                                            <label for="terms_and_conditions_checked">
                                              &nbsp;I agree with all the <a href="https://www.ria.wa.gov.au/boating/licensed-moorings-permits/mooring-terms-and-conditions" target="_blank">RIA Terms and Conditions&nbsp;</a>
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
                                                {{ submitText }}&nbsp;
                                                <i v-show="terms_and_conditions_checked" class="fa fa-circle-o-notch fa-spin fa-fw"></i>
                                            </button>
                                            <input v-else 
                                                type="button" 
                                                @click.prevent="submit" 
                                                class="btn btn-primary" 
                                                :value="submitText" 
                                                :disabled="saveExitProposal || savingProposal "
                                                id="submitButton"
                                                
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
      vesselOwnershipChanged: false,
      submitText: "Submit",
      missingVessel: false,
      profile_original: {},
      profile: {},
      submitRes: null,
    }
  },
  components: {
      WaitingListApplication,
      AnnualAdmissionApplication,
      AuthorisedUserApplication,
      MooringLicenceApplication,
  },
  computed: {
      profileHasChanged: function(){
        console.log(this.profile_original)
        let originalHash = JSON.stringify(this.profile_original)
        let currentHash = JSON.stringify(this.profile)
        if (originalHash !== currentHash){
          return true
        } else {
          return false
        }
      },
      disableSubmit: function() {
          let disable = false

          if (this.proposal){
              if (this.proposal.proposal_type.code ==='amendment'){
                  if (this.missingVessel && ['aaa', 'aua'].includes(this.proposal.application_type_code)){
                      disable = true
                  } else {
                      if (['aaa', 'mla'].includes(this.proposal.application_type_code)){
                          if (!this.vesselChanged && !this.vesselOwnershipChanged && !this.profileHasChanged) {
                              disable = true
                              console.log('%cSubmit button is disabled 1', 'color: #FF0000')
                          }
                      } else if (this.proposal.application_type_code === 'wla'){
                          if (!this.vesselChanged && !this.mooringPreferenceChanged && !this.vesselOwnershipChanged && !this.profileHasChanged) {
                              disable = true
                              console.log('%cSubmit button is disabled 2', 'color: #FF0000')
                          }
                      } else if (this.proposal.application_type_code === 'aua'){
                          if (!this.vesselChanged && !this.mooringOptionsChanged && !this.vesselOwnershipChanged && !this.profileHasChanged) {
                              disable = true
                              console.log('%cSubmit button is disabled 3', 'color: #FF0000')
                          }
                      }
                  }
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
          if(this.proposal && this.proposal.proposal_type && this.proposal.proposal_type.code !== 'new'){
              amendRenew=true;
          }
          return amendRenew;
      },
  },
  methods: {
    buildPayload: function() {
        let payload = {
            proposal: {},
            vessel: {},
            profile: {},
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

        return payload;
    },
    populateProfile: function(profile) {
        this.profile_original = Object.assign({}, profile)  // This is shallow copy but it's enough 
        this.profile = profile
    },
    noVessel: function(noVessel) {
        this.missingVessel = noVessel;
    },
    updateMooringAuth: function(changed) {
        this.mooringOptionsChanged = changed;
    },
    updateVesselChanged: function(vesselChanged) {
        console.log('in updateVesselChanged at the proposal.vue')
        this.vesselChanged = vesselChanged;
        console.log('this.vesselChanged: ' + this.vesselChanged)
    },
    updateMooringPreference: function(preferenceChanged) {
        this.mooringPreferenceChanged = preferenceChanged;
    },
    updateVesselOwnershipChanged: function(changed) {
        console.log('updateVesselOwnershipChanged in proposal.vue:' + changed)
        this.vesselOwnershipChanged = changed
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

    set_formData: function(e) {
      let vm = this;
      let formData = new FormData(vm.form);
      return formData;
    },
    save: async function(withConfirm=true, url=this.proposal_form_url) {
        let vm = this;
        let payload = this.buildPayload();
        vm.savingProposal=true;

        try {
          const res = await vm.$http.post(url, payload); 
          if (res.ok) {
              if (withConfirm) {
                  swal(
                      'Saved',
                      'Your application has been saved',
                      'success'
                  );
              };
              if (res.body.auto_approve !== undefined) {
                  vm.proposal.auto_approve = res.body.auto_approve;
              }
              vm.savingProposal=false;
              this.submitRes = true;
              return res;
            }
        } catch(err) {
            swal({
                title: "Please fix following errors before saving",
                text: helpers.formatError(err),
                type:'error'
            });
            vm.savingProposal=false;
            this.submitRes = false;
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
    },
    save_and_pay: async function() {
      try {
            await this.save(false, this.proposal_submit_url)
            this.$nextTick(async () => {
                console.log(this.submitRes)
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
                    this.submitting=false;
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
            this.submitting=false;
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
            await swal({
                title: 'Submit Error',
                html: helpers.formatError(err),
                type: "error",
            })
            this.savingProposal=false;
            this.paySubmitting=false;
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
                var acc_ref= vm.proposal.other_details.accreditations[i].accreditation_type;
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
  },

  mounted: function() {
    let vm = this;
    vm.form = document.forms.new_proposal;
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
            });
          },
        err => {
        });
    }
  }
}
</script>