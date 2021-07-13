<template lang="html">
    <div class="">

        <div v-if="proposal && show_application_title" id="scrollspy-heading" class="" >
            <h4>Annual Admission Application: {{proposal.lodgement_number}}</h4>
        </div>

        <div class="">
            <ul class="nav nav-pills mb-3" id="pills-tab" role="tablist">
              <li class="nav-item">
                <a class="nav-link active" id="pills-applicant-tab" data-toggle="pill" href="#pills-applicant" role="tab" aria-controls="pills-applicant" aria-selected="true">
                  1. Applicant
                </a>
              </li>
              <li class="nav-item">
                <a class="nav-link" id="pills-vessels-tab" data-toggle="pill" href="#pills-vessels" role="tab" aria-controls="pills-vessels" aria-selected="false">
                  2. Vessel
                </a>
              </li>
              <li class="nav-item">
                <a class="nav-link" id="pills-insurance-tab" data-toggle="pill" href="#pills-insurance" role="tab" aria-controls="pills-insurance" aria-selected="false">
                  3. Insurance
                </a>
              </li>
              <!--li class="nav-item">
                <a class="nav-link" id="pills-activities-marine-tab" data-toggle="pill" href="#pills-activities-marine" role="tab" aria-controls="pills-activities-marine" aria-selected="false">
                  3. Activities (marine)
                </a>
              </li>
              <li class="nav-item">
                <a class="nav-link" id="pills-other-details-tab" data-toggle="pill" href="#pills-other-details" role="tab" aria-controls="pills-other-details" aria-selected="false">
                  4. Other Details
                </a>
              </li>
              <li v-if="is_external" class="nav-item" id="li-training">
                <a class="nav-link" id="pills-online-training-tab" data-toggle="pill" href="#pills-online-training" role="tab" aria-controls="pills-online-training" aria-selected="false">
                  5. Questionnaire
                </a>
              </li-->
              <li v-if="is_external" class="nav-item" id="li-payment">
                <a class="nav-link disabled" id="pills-payment-tab" data-toggle="pill" href="" role="tab" aria-controls="pills-payment" aria-selected="false">
                  4. Payment
                </a>
              </li>
              <li v-if="is_external" class="nav-item" id="li-confirm">
                <a class="nav-link disabled" id="pills-confirm-tab" data-toggle="pill" href="" role="tab" aria-controls="pills-confirm" aria-selected="false">
                    5. Confirmation
                    <!--
                    <span v-if="proposal.is_amendment_proposal">
                        5. Confirmation
                    </span>
                    <span v-else>
                        7. Confirmation
                    </span>
                    -->
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
                    :proposal="proposal" 
                    id="proposalStartApplicant"
                    :readonly="readonly"
                    />
                  </div>
              </div>
              <div class="tab-pane fade" id="pills-vessels" role="tabpanel" aria-labelledby="pills-vessels-tab">
                  <Vessels 
                  :proposal="proposal" 
                  :profile="profile" 
                  id="proposalStartVessels" 
                  ref="vessels"
                  :readonly="readonly"
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

              <!--div class="tab-pane fade" id="pills-activities-land" role="tabpanel" aria-labelledby="pills-activities-land-tab">
                <ActivitiesLand :proposal="proposal" id="proposalStartActivitiesLand" :canEditActivities="canEditActivities" :proposal_parks="proposal_parks" ref="activities_land"></ActivitiesLand>
              </div>
              <div class="tab-pane fade" id="pills-activities-marine" role="tabpanel" aria-labelledby="pills-activities-marine-tab">
                <ActivitiesMarine :proposal="proposal" id="proposalStartActivitiesMarine" :canEditActivities="canEditActivities" ref="activities_marine" :proposal_parks="proposal_parks"></ActivitiesMarine>
              </div>
              <div class="tab-pane fade" id="pills-other-details" role="tabpanel" aria-labelledby="pills-other-details-tab">
                <OtherDetails :proposal="proposal" id="proposalStartOtherDetails" ref="other_details"></OtherDetails>
              </div>
              <div class="tab-pane fade" id="pills-online-training" role="tabpanel" aria-labelledby="pills-online-training-tab">
                <OnlineTraining :proposal="proposal" id="proposalStartOnlineTraining"></OnlineTraining>
              </div>
              <div class="tab-pane fade" id="pills-payment" role="tabpanel" aria-labelledby="pills-payment-tab">
                <!-- This is a Dummy Tab -->
              </div-->
              <div class="tab-pane fade" id="pills-confirm" role="tabpanel" aria-labelledby="pills-confirm-tab">
                <Confirmation :proposal="proposal" id="proposalStartConfirmation"></Confirmation>
              </div>
            </div>
        </div>
    </div>
</template>

<script>
    import Profile from '@/components/user/profile.vue'
    //import Organisation from '@/components/external/organisations/manage.vue'
    import Applicant from '@/components/common/applicant.vue'
    import Confirmation from '@/components/common/confirmation.vue'
    import Vessels from '@/components/common/vessels.vue'
    import Insurance from '@/components/common/insurance.vue'
    /*
    import Assessment from '@/components/common/tclass/assessment.vue'
    import ActivitiesLand from '@/components/common/tclass/activities_land.vue'
    import ActivitiesMarine from '@/components/common/tclass/activities_marine.vue'
    import OtherDetails from '@/components/common/tclass/other_details.vue'
    import OnlineTraining from '@/components/common/tclass/online_training.vue'
    import Confirmation from '@/components/common/tclass/confirmation.vue'
    */
    export default {
        name: 'AnnualAdmissionApplication',
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
                default: true
            },
        },
        data:function () {
            return{
                values:null,
                profile: {},
            }
        },
        components: {
            Applicant,
            Confirmation,
            Vessels,
            Insurance,
            /*
            ActivitiesLand,
            ActivitiesMarine,
            OtherDetails,
            OnlineTraining,
            */
            Profile,
            /*
            Organisation,
            Assessment
            */
        },
        computed:{
            applicantType: function(){
                return this.proposal.applicant_type;
            },
            /*
            showElectoralRoll: function() {
                let show = false;
                if (this.proposal && ['wla', 'mla'].includes(this.proposal.application_type_code)) {
                    show = true;
                }
                return show;
            },
            */
        },
        methods:{
            populateProfile: function(profile) {
                this.profile = Object.assign({}, profile);
            },
            set_tabs:function(){
                let vm = this;

                /* set Applicant tab Active */
                $('#pills-tab a[href="#pills-applicant"]').tab('show');

                if (vm.proposal.fee_paid) {
                    /* Online Training tab */
                    $('#pills-online-training-tab').attr('style', 'background-color:#E5E8E8 !important; color: #99A3A4;');
                    $('#li-training').attr('class', 'nav-item disabled');
                    $('#pills-online-training-tab').attr("href", "")
                }

                if (!vm.proposal.training_completed) {
                    /* Payment tab  (this is enabled after online_training is completed - in online_training.vue)*/
                    $('#pills-payment-tab').attr('style', 'background-color:#E5E8E8 !important; color: #99A3A4;');
                    $('#li-payment').attr('class', 'nav-item disabled');
                }

                /* Confirmation tab - Always Disabled */
                $('#pills-confirm-tab').attr('style', 'background-color:#E5E8E8 !important; color: #99A3A4;');
                $('#li-confirm').attr('class', 'nav-item disabled');
            },
            eventListener: function(){
              let vm=this;
              $('a[href="#pills-activities-land"]').on('shown.bs.tab', function (e) {
                vm.$refs.activities_land.$refs.vehicles_table.$refs.vehicle_datatable.vmDataTable.columns.adjust().responsive.recalc();
              });
              $('a[href="#pills-activities-marine"]').on('shown.bs.tab', function (e) {
                vm.$refs.activities_marine.$refs.vessel_table.$refs.vessel_datatable.vmDataTable.columns.adjust().responsive.recalc();
              });
            },

        },
        mounted: function() {
            let vm = this;
            vm.set_tabs();
            vm.form = document.forms.new_proposal;
            vm.eventListener();
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

