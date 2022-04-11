<template lang="html">
    <div class="">

        <div v-if="proposal && show_application_title" id="scrollspy-heading" class="" >
            <h4>Waiting List {{applicationTypeText}} Application: {{proposal.lodgement_number}}</h4>
        </div>

        <div class="">
            <ul class="nav nav-pills mb-3" id="pills-tab" role="tablist">
              <li class="nav-item">
                <a class="nav-link active" id="pills-applicant-tab" data-toggle="pill" href="#pills-applicant" role="tab" aria-controls="pills-applicant" aria-selected="true">
                  Applicant
                </a>
              </li>
              <li class="nav-item">
                <a class="nav-link" id="pills-vessels-tab" data-toggle="pill" href="#pills-vessels" role="tab" aria-controls="pills-vessels" aria-selected="false">
                  Vessel
                </a>
              </li>
              <li class="nav-item">
                <a class="nav-link" id="pills-mooring-tab" data-toggle="pill" href="#pills-mooring" role="tab" aria-controls="pills-mooring" aria-selected="false">
                  Mooring
                </a>
              </li>
              <li v-show="showPaymentTab" class="nav-item" id="li-payment">
                <a class="nav-link disabled" id="pills-payment-tab" data-toggle="pill" href="" role="tab" aria-controls="pills-payment" aria-selected="false">
                  Payment
                </a>
              </li>
              <li v-if="is_external" class="nav-item" id="li-confirm">
                <a class="nav-link disabled" id="pills-confirm-tab" data-toggle="pill" href="" role="tab" aria-controls="pills-confirm" aria-selected="false">
                    Confirmation
                </a>
              </li>
            </ul>
            <div class="tab-content" id="pills-tabContent">
              <div class="tab-pane fade" id="pills-applicant" role="tabpanel" aria-labelledby="pills-applicant-tab">
                  <div v-if="is_external">
                    <Profile 
                    :isApplication="true" 
                    v-if="applicantType == 'SUB'" 
                    ref="profile"
                    @profile-fetched="populateProfile"
                    :showElectoralRoll="showElectoralRoll"
                    :storedSilentElector="silentElector"
                    :proposalId="proposal.id"
                    :readonly="readonly"
                    :submitterId="submitterId"
                    />
                  </div>
                  <div v-else>
                    <Applicant 
                        :email_user="proposal.submitter" 
                        :applicantType="proposal.applicant_type" 
                        id="proposalStartApplicant"
                        :readonly="readonly"
                        :showElectoralRoll="showElectoralRoll"
                        :storedSilentElector="silentElector"
                        :proposalId="proposal.id"
                    />
                  </div>
              </div>
              <div class="tab-pane fade" id="pills-vessels" role="tabpanel" aria-labelledby="pills-vessels-tab">
                  <div v-if="proposal">
                      <CurrentVessels 
                          :proposal=proposal
                          :readonly=readonly
                          :is_internal=is_internal
                          @resetCurrentVessel=resetCurrentVessel
                          />
                  </div>
                  <Vessels 
                  :proposal="proposal" 
                  :profile="profileVar" 
                  :id="'proposalStartVessels' + uuid"
                  :key="'proposalStartVessels' + uuid"
                  :keep_current_vessel="keepCurrentVessel"
                  ref="vessels"
                  :readonly="readonly"
                  :is_internal="is_internal"
                  @updateVesselLength="updateVesselLength"
                  @vesselChanged="vesselChanged"
                  />
              </div>
              <div class="tab-pane fade" id="pills-mooring" role="tabpanel" aria-labelledby="pills-mooring-tab">
                  <Mooring
                  :proposal="proposal" 
                  id="mooring" 
                  ref="mooring"
                  :readonly="readonly"
                  @mooringPreferenceChanged="toggleMooringPreference"
                  />
              </div>
              <div class="tab-pane fade" id="pills-confirm" role="tabpanel" aria-labelledby="pills-confirm-tab">
                <Confirmation :proposal="proposal" id="proposalStartConfirmation"></Confirmation>
              </div>
            </div>
        </div>
    </div>
</template>

<script>
    import Profile from '@/components/user/profile.vue'
    import Applicant from '@/components/common/applicant.vue'
    import Confirmation from '@/components/common/confirmation.vue'
    import Vessels from '@/components/common/vessels.vue'
    import CurrentVessels from '@/components/common/current_vessels.vue'
    import Mooring from '@/components/common/mooring.vue'
    export default {
        name: 'WaitingListApplication',
        props:{
            proposal:{
                type: Object,
                required:true
            },
            show_application_title: {
                type: Boolean,
                default: true,
            },
            submitterId: {
                type: Number,
            },
            canEditActivities:{
              type: Boolean,
              default: true
            },
            is_external:{
              type: Boolean,
              default: false
            },
            is_internal:{
              type: Boolean,
              default: false
            },
            is_referral:{
              type: Boolean,
              default: false
            },
            hasReferralMode:{
                type:Boolean,
                default: false
            },
            hasAssessorMode:{
                type:Boolean,
                default: false
            },
            referral:{
                type: Object,
                required:false
            },
            proposal_parks:{
                type:Object,
                default:null
            },
            showElectoralRoll:{
                type:Boolean,
                default: false
            },
            readonly:{
                type: Boolean,
                default: true,
            },
        },
        data:function () {
            return{
                values:null,
                profile: {},
                uuid: 0,
                keepCurrentVessel: true,
                mooringPreferenceChanged: false,
                //vesselLength: null,
                showPaymentTab: true,
                higherVesselCategory: false,
            }
        },
        components: {
            Applicant,
            Confirmation,
            Vessels,
            Mooring,
            CurrentVessels,
            Profile,
        },
        computed:{
            profileVar: function() {
                if (this.is_external) {
                    return this.profile;
                } else if (this.proposal) {
                    return this.proposal.submitter;
                }
            },
            silentElector: function() {
                if (this.proposal) {
                    return this.proposal.silent_elector;
                }
            },
            applicantType: function(){
                if (this.proposal) {
                    return this.proposal.applicant_type;
                }
            },
            applicationTypeText: function(){
                let text = '';
                if (this.proposal && this.proposal.proposal_type && this.proposal.proposal_type.code !== 'new') {
                    text = this.proposal.proposal_type.description;
                }
                return text;
            },
        },
        methods:{
            vesselChanged: async function(vesselChanged) {
                await this.$emit("vesselChanged", vesselChanged);
            },
            toggleMooringPreference: async function(preferenceChanged) {
                this.mooringPreferenceChanged = preferenceChanged;
                await this.$emit("mooringPreferenceChanged", preferenceChanged);
                //this.updateAmendmentRenewalProperties();
            },
            updateVesselLength: function(length) {
                if (this.is_external && this.proposal) {
                    if (this.proposal.max_vessel_length_with_no_payment &&
                        this.proposal.max_vessel_length_with_no_payment <= length) {
                        // vessel length is in higher category
                        this.higherVesselCategory = true;
                    } else {
                        this.higherVesselCategory = false;
                    }
                }
                this.updateAmendmentRenewalProperties();
            },
            resetCurrentVessel: function(keep) {
                this.keepCurrentVessel = keep;
                this.uuid++
                this.updateAmendmentRenewalProperties();
            },
            updateAmendmentRenewalProperties: function() {
                console.log('updateAmendmentRenewalProperties in form_wla.vue')
                //if (this.proposal && ['renewal', 'amendment'].includes(this.proposal.proposal_type.code)) {
                if (this.proposal && (this.proposal.proposal_type.code === 'amendment' || this.proposal.pending_amendment_request)) {
                    this.$nextTick(() => {
                        if (this.higherVesselCategory) {
                            this.showPaymentTab = true;
                            this.$emit("updateSubmitText", "Pay / Submit");
                        } else {
                            this.showPaymentTab = false;
                            this.$emit("updateSubmitText", "Submit");
                        }
                        // auto approve
                        if (this.higherVesselCategory || !this.keepCurrentVessel || this.mooringPreferenceChanged) {
                            this.$emit("updateAutoApprove", false);
                        } else {
                            this.$emit("updateAutoApprove", true);
                        }

                    });
                } else if (this.proposal && this.proposal.proposal_type.code === 'renewal') {
                    this.$nextTick(() => {
                        this.showPaymentTab = true;
                        this.$emit("updateSubmitText", "Pay / Submit");
                        // auto approve
                        if (this.higherVesselCategory || !this.keepCurrentVessel || this.mooringPreferenceChanged) {
                            this.$emit("updateAutoApprove", false);
                        } else {
                            this.$emit("updateAutoApprove", true);
                        }
                    });
                }
            },

            populateProfile: function(profile) {
                this.profile = Object.assign({}, profile);
            },
            set_tabs:function(){
                let vm = this;

                /* set Applicant tab Active */
                $('#pills-tab a[href="#pills-applicant"]').tab('show');


                /* Confirmation tab - Always Disabled */
                $('#pills-confirm-tab').attr('style', 'background-color:#E5E8E8 !important; color: #99A3A4;');
                $('#li-confirm').attr('class', 'nav-item disabled');
                /* Payment tab - Always Disabled */
                $('#pills-payment-tab').attr('style', 'background-color:#E5E8E8 !important; color: #99A3A4;');
                $('#li-payment').attr('class', 'nav-item disabled');
            },

        },
        mounted: function() {
            let vm = this;
            vm.set_tabs();
            vm.form = document.forms.new_proposal;
            this.updateAmendmentRenewalProperties();
            this.$emit("updateSubmitText", "Pay / Submit");
            //window.addEventListener('beforeunload', vm.leaving);
            //indow.addEventListener('onblur', vm.leaving);

        }
 
    }
</script>

<style lang="css" scoped>
    .section{
        text-transform: capitalize;
    }
    .list-group{
        margin-bottom: 0;
    }
    .fixed-top{
        position: fixed;
        top:56px;
    }

    .nav-item {
        background-color: rgb(200,200,200,0.8) !important;
        margin-bottom: 2px;
    }

    .nav-item>li>a {
        background-color: yellow !important;
        color: #fff;
    }

    .nav-item>li.active>a, .nav-item>li.active>a:hover, .nav-item>li.active>a:focus {
      color: white;
      background-color: blue;
      border: 1px solid #888888;
    }

	.admin > div {
	  display: inline-block;
	  vertical-align: top;
	  margin-right: 1em;
	}
</style>

