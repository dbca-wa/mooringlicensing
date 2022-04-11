<template lang="html">
    <div v-if="vessel" class="container" id="internalDcvVessel">
        <div class="row">
            <h3>{{ vessel.vessel_name}} - {{ vessel.rego_no }}</h3>
            <div class="col-md-3">
                <!--CommsLogs 
                    :comms_url="comms_url" 
                    :logs_url="logs_url" 
                    :comms_add_url="comms_add_url" 
                    :disable_add_entry="false"
                /-->

            </div>

            <div class="col-md-1"></div>

            <div class="col-md-8">

        <!--div-->
                <ul class="nav nav-pills mb-3" id="pills-tab" role="tablist">
                  <li class="nav-item">
                    <a class="nav-link active" id="pills-vessel-details-tab" data-toggle="pill" href="#pills-vessel-details" role="tab" aria-controls="pills-vessel-details" aria-selected="true">
                      Details
                    </a>
                  </li>
                  <!--li class="nav-item">
                    <a class="nav-link" id="pills-owners-tab" data-toggle="pill" href="#pills-owners" role="tab" aria-controls="pills-owners" aria-selected="false">
                      Owner(s)
                    </a>
                  </li-->
                  <li class="nav-item">
                    <a class="nav-link" id="pills-dcv-admissions-permits-tab" data-toggle="pill" href="#pills-dcv-admissions-permits" role="tab" aria-controls="pills-dcv-admissions-permits" aria-selected="false">
                      Dcv Admissions/Permits
                    </a>
                  </li>
                </ul>

                <div class="tab-content" id="pills-tabContent">
                    <div class="tab-pane fade" id="pills-vessel-details" role="tabpanel" aria-labelledby="pills-vessel-details-tab">
                        <FormSection label="Registration details" Index="registration_details">
                            <div class="row form-group">
                                <div class="col-sm-3">
                                    <label>Registration number:</label>
                                </div>
                                <div class="col-sm-6">
                                    {{ vessel.rego_no }}
                                </div>
                            </div>

                            <div class="row form-group">
                                <div class="col-sm-3">
                                    <label>Name:</label>
                                </div>
                                <div class="col-sm-6">
                                    {{ vessel.vessel_name }}
                                </div>
                            </div>
                        </FormSection>
                    </div>
                    <div class="tab-pane fade" id="pills-dcv-admissions-permits" role="tabpanel" aria-labelledby="pills-dcv-admissions-permits-tab">
                        <FormSection label="DCV Admissions/Permits" Index="dcv_admissions_permits">
                            <div v-if="entity.id">
                                <DcvAdmissionsPermits
                                :entity="entity"
                                :key="entity.id"
                                />
                            </div>
                        </FormSection>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import FormSection from '@/components/forms/section_toggle.vue'
import CommsLogs from '@common-utils/comms_logs.vue'
import DcvAdmissionsPermits from '@common-utils/dcv_admissions_permits.vue'
import datatable from '@/utils/vue/datatable.vue'
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'
    export default {
        name:'DcvVesselDetails',
        components:{
            FormSection,
            CommsLogs,
            datatable,
            DcvAdmissionsPermits,
        },
        data:function () {
            let vm = this;
            return {
                vessel: {
                    vessel_details: {
                    }
                },
                /*
                comms_url: helpers.add_endpoint_json(api_endpoints.vessel, this.$route.params.vessel_id + '/comms_log'),
                comms_add_url: helpers.add_endpoint_json(api_endpoints.vessel, this.$route.params.vessel_id + '/add_comms_log'),
                logs_url: helpers.add_endpoint_json(api_endpoints.vessel, this.$route.params.vessel_id + '/action_log'),
                datatable_id: 'owners-datatable-' + this._uid,
                owners_headers: ['Name', 'Company', 'Percentage', 'Phone', 'Start', 'End', 'Action'],
                */
             }
        },
        computed: {
            entity: function() {
                return {
                    type: "vessel",
                    id: this.vessel.id,
                }
            },
        },
        methods:{
            setTabs:function(){
                let vm = this;

                /* set Applicant tab Active */
                $('#pills-tab a[href="#pills-vessel-details"]').tab('show');

            },

        },
        mounted: function () {
            this.$nextTick(async () => {
                this.setTabs();
            });
        },
        created: async function() {
            const res = await this.$http.get(`/api/dcv_vessel/${this.$route.params.dcv_vessel_id}/lookup_dcv_vessel.json`);
            this.vessel = Object.assign({}, res.body);

        },
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

