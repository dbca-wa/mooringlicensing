<template lang="html">
    <div>

        <div v-if="proposal && show_application_title" id="scrollspy-heading">
            <h4>Authorised User {{applicationTypeText}} Application: {{proposal.lodgement_number}}</h4>
        </div>

        <div>
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
              <li v-show="showInsuranceTab" class="nav-item">
                <a class="nav-link" id="pills-insurance-tab" data-toggle="pill" href="#pills-insurance" role="tab" aria-controls="pills-insurance" aria-selected="false">
                  Insurance
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
                  :keep_current_vessel=keepCurrentVessel
                  ref="vessels"
                  :readonly="readonly"
                  :is_internal="is_internal"
                  @updateVesselLength="updateVesselLength"
                  @vesselChanged="vesselChanged"
                  @noVessel="noVessel"
                  @updateMaxVesselLengthForAAComponent=updateMaxVesselLengthForAAComponent
                  @updateMaxVesselLengthForMainComponent=updateMaxVesselLengthForMainComponent
                  />
              </div>
              <div class="tab-pane fade" id="pills-insurance" role="tabpanel" aria-labelledby="pills-insurance-tab">
                  <Insurance
                  :proposal="proposal"
                  id="insurance"
                  ref="insurance"
                  :readonly="readonly"
                  />
              </div>
              <div class="tab-pane fade" id="pills-mooring" role="tabpanel" aria-labelledby="pills-mooring-tab">
                  <div v-if="proposal">
                      <CurrentMooring
                          :proposal=proposal
                          :readonly=readonly
                          :is_internal=is_internal
                          @resetCurrentMooring=resetCurrentMooring
                          />
                  </div>
                  <MooringAuthorisation
                  :proposal="proposal"
                  id="mooring_authorisation"
                  :id="'mooringAuthorisation' + mooringAuthorisationUuid"
                  :key="'mooringAuthorisation' + mooringAuthorisationUuid"
                  :changeMooring="changeMooring"
                  :newAua="newAua"
                  ref="mooring_authorisation"
                  :readonly="readonly"
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
    import CurrentMooring from '@/components/common/current_mooring.vue'
    import Insurance from '@/components/common/insurance.vue'
    import MooringAuthorisation from '@/components/common/mooring_authorisation.vue'
    export default {
        name: 'AuthorisedUserApplication',
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
                mooringAuthorisationUuid: 0,
                keepCurrentVessel: true,
                changeMooring: false,
                showPaymentTab: false,
                showInsuranceTab: true,
                higherVesselCategory: false,
                max_vessel_length_with_no_payment: 0,
                max_vessel_length_for_main_component: 0,
                max_vessel_length_for_aa_component: 0,
            }
        },
        watch: {
            changeMooring: {
                handler: async function() {
                    await this.$emit("changeMooring", this.changeMooring);
                },
            },
        },
        components: {
            Applicant,
            Confirmation,
            Vessels,
            CurrentVessels,
            CurrentMooring,
            Insurance,
            MooringAuthorisation,
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
            applicantType: function(){
                return this.proposal.applicant_type;
            },
            applicationTypeText: function(){
                let text = '';
                if (this.proposal && this.proposal.proposal_type && this.proposal.proposal_type.code !== 'new') {
                    text = this.proposal.proposal_type.description;
                }
                return text;
            },
            newAua: function(){
                let newApp = false;
                if (this.proposal && this.proposal.proposal_type && this.proposal.proposal_type.code === 'new') {
                    newApp = true;
                }
                return newApp;
            },
            /*
            showInsuranceTab: function(){
                let show=true;
                if(this.proposal && this.proposal.proposal_type && this.proposal.proposal_type.code !=='new' && this.keep_current_vessel)
                {
                    show=false;
                }
                return show;

            },
            */
        },
        methods:{
            updateMaxVesselLength: function(max_length) {
                console.log('updateMaxVesselLength')
                //this.max_vessel_length_with_no_payment = max_length
                let combined_length = 0
                if (this.max_vessel_length_for_main_component == null && this.max_vessel_length_for_aa_component == null){
                    combined_length = null
                } else {
                    if (this.max_vessel_length_for_main_component == null){
                        // aa component has a value
                        combined_length = this.max_vessel_length_for_aa_component
                    } else if (this.max_vessel_length_for_aa_component == null){
                        // main component has a value
                        combined_length = this.max_vessel_length_for_main_component
                    } else {
                        // both have a value
                        if (this.max_vessel_length_for_aa_component < this.max_vessel_length_for_main_component){
                            combined_length = this.max_vessel_length_for_aa_component
                        } else {
                            combined_length = this.max_vessel_length_for_main_component
                        }
                    }
                }
                if (combined_length < 0){  // This can be -1, which is set as a defautl value at the vessels.vue
                    combined_length = 0
                }
                this.max_vessel_length_with_no_payment = combined_length
            },
            updateMaxVesselLengthForAAComponent: function(length){
                console.log('updateMaxVesselLengthForAAComponent')
                this.max_vessel_length_for_aa_component = length
                this.updateMaxVesselLength()
            },
            updateMaxVesselLengthForMainComponent: function(length){
                console.log('updateMaxVesselLengthForMainComponent')
                this.max_vessel_length_for_main_component = length
                this.updateMaxVesselLength()
            },
            noVessel: async function(noVessel) {
                await this.$emit("noVessel", noVessel);
            },
            vesselChanged: async function(vesselChanged) {
                await this.$emit("vesselChanged", vesselChanged);
            },
            /*
            updateVesselLength: function(length) {
                let higherCategory = false;
                if (this.is_external && this.proposal) {
                    if (!this.proposal.previous_application_id) {
                        // new application
                        //higherCategory = true;
                        //pass
                    } else if (this.proposal.max_vessel_length_with_no_payment &&
                        this.proposal.max_vessel_length_with_no_payment <= length) {
                        // vessel length is in higher category
                        higherCategory = true;
                    }
                }
                console.log(higherCategory);
                if (higherCategory) {
                    this.showPaymentTab = true;
                    this.$emit("updateSubmitText", "Pay / Submit");
                }
            },
            */
            updateVesselLength: function(length) {
                if (this.is_external && this.proposal) {
                    //if (this.proposal.max_vessel_length_with_no_payment !== null &&
                    //    this.proposal.max_vessel_length_with_no_payment <= length) {
                    if (this.max_vessel_length_with_no_payment !== null &&
                        this.max_vessel_length_with_no_payment <= length) {
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
            resetCurrentMooring: function(keep) {
                console.log('resetCurrentMooring() in form_aua.vue')
                this.changeMooring = keep;
                this.mooringAuthorisationUuid++
                this.updateAmendmentRenewalProperties();
            },
            updateAmendmentRenewalProperties: function() {
                console.log('updateAmendmentRenewalProperties in form_aua.vue')
                if (this.proposal && this.proposal.proposal_type.code === 'amendment') {
                    this.$nextTick(() => {
                        if (!this.keepCurrentVessel) {
                            this.showPaymentTab = false;
                            this.showInsuranceTab = true;
                            this.$emit("updateSubmitText", "Submit");
                        } else {
                            this.showPaymentTab = false;
                            this.showInsuranceTab = false;
                            this.$emit("updateSubmitText", "Submit");
                        }
                        // auto approve
                        if (!this.proposal.vessel_on_proposal || this.higherVesselCategory || !this.keepCurrentVessel || this.changeMooring) {
                            this.$emit("updateAutoApprove", false);
                        } else {
                            this.$emit("updateAutoApprove", true);
                        }
                    });
                } else if (this.proposal && this.proposal.proposal_type.code === 'renewal') {
                    this.$nextTick(() => {
                        if (this.keepCurrentVessel && !this.higherVesselCategory && !this.changeMooring) {
                            this.showPaymentTab = true;
                            this.showInsuranceTab = false;
                            this.$emit("updateSubmitText", "Pay / Submit");
                            //this.$emit("updateAutoRenew", true);
                        } else if (!this.keepCurrentVessel) {
                            this.showPaymentTab = false;
                            this.showInsuranceTab = true;
                            this.$emit("updateSubmitText", "Submit");
                            //this.$emit("updateAutoRenew", false);
                        } else {
                            this.showPaymentTab = false;
                            this.showInsuranceTab = false;
                            this.$emit("updateSubmitText", "Submit");
                            //this.$emit("updateAutoRenew", false);
                        }
                        // auto approve
                        if (!this.proposal.vessel_on_proposal || this.higherVesselCategory || !this.keepCurrentVessel || this.changeMooring) {
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

                /*
                if (vm.proposal.fee_paid) {
                    $('#pills-online-training-tab').attr('style', 'background-color:#E5E8E8 !important; color: #99A3A4;');
                    $('#li-training').attr('class', 'nav-item disabled');
                    $('#pills-online-training-tab').attr("href", "")
                }
                if (!vm.proposal.training_completed) {
                    $('#pills-payment-tab').attr('style', 'background-color:#E5E8E8 !important; color: #99A3A4;');
                    $('#li-payment').attr('class', 'nav-item disabled');
                }
                */

                /* Confirmation tab - Always Disabled */
                $('#pills-confirm-tab').attr('style', 'background-color:#E5E8E8 !important; color: #99A3A4;');
                $('#li-confirm').attr('class', 'nav-item disabled');
                /* Payment tab - Always Disabled */
                $('#pills-payment-tab').attr('style', 'background-color:#E5E8E8 !important; color: #99A3A4;');
                $('#li-payment').attr('class', 'nav-item disabled');
            },
            /*
            eventListener: function(){
              let vm=this;
              $('a[href="#pills-activities-land"]').on('shown.bs.tab', function (e) {
                vm.$refs.activities_land.$refs.vehicles_table.$refs.vehicle_datatable.vmDataTable.columns.adjust().responsive.recalc();
              });
              $('a[href="#pills-activities-marine"]').on('shown.bs.tab', function (e) {
                vm.$refs.activities_marine.$refs.vessel_table.$refs.vessel_datatable.vmDataTable.columns.adjust().responsive.recalc();
              });
            },
            */

        },
        mounted: function() {
            let vm = this;
            vm.set_tabs();
            vm.form = document.forms.new_proposal;
            this.updateAmendmentRenewalProperties();
            //vm.eventListener();
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

