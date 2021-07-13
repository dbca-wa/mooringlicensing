<template lang="html">
    <div v-if="mooring" class="container" id="internalMooring">
        <div class="row">
            <h3>{{ mooring.name}}</h3>
            <div class="col-md-3">
                <CommsLogs 
                    :comms_url="comms_url" 
                    :logs_url="logs_url" 
                    :comms_add_url="comms_add_url" 
                    :disable_add_entry="false"
                />

            </div>

            <div class="col-md-1"></div>

            <div class="col-md-8">

        <!--div-->
                <ul class="nav nav-pills mb-3" id="pills-tab" role="tablist">
                  <li class="nav-item">
                    <a class="nav-link active" id="pills-mooring-details-tab" data-toggle="pill" href="#pills-mooring-details" role="tab" aria-controls="pills-mooring-details" aria-selected="true">
                      Details
                    </a>
                  </li>
                  <li class="nav-item">
                    <a class="nav-link" id="pills-bookings-permits-tab" data-toggle="pill" href="#pills-bookings-permits" role="tab" aria-controls="pills-bookings-permits" aria-selected="false">
                      Bookings/Permits
                    </a>
                  </li>
                </ul>

                <div class="tab-content" id="pills-tabContent">
                    <div class="tab-pane fade" id="pills-mooring-details" role="tabpanel" aria-labelledby="pills-mooring-details-tab">
                        <FormSection label="Mooring details" Index="mooring_details">
                            <div class="row form-group">
                                <div class="col-sm-3">
                                    <label>Name:</label>
                                </div>
                                <div class="col-sm-6">
                                    {{ mooring.name }}
                                </div>
                            </div>
                            <div class="row form-group">
                                <div class="col-sm-3">
                                    <label>Mooring Bay:</label>
                                </div>
                                <div class="col-sm-6">
                                    {{ mooring.mooring_bay_name }}
                                </div>
                            </div>
                        </FormSection>
                        <FormSection label="Vessel limits" Index="vessel_limits">
                            <div class="row form-group">
                                <div class="col-sm-3">
                                    <label>Vessel beam limit:</label>
                                </div>
                                <div class="col-sm-6">
                                    {{ mooring.vessel_beam_limit }}
                                </div>
                            </div>
                            <div class="row form-group">
                                <div class="col-sm-3">
                                    <label>Vessel draft limit:</label>
                                </div>
                                <div class="col-sm-6">
                                    {{ mooring.vessel_draft_limit }}
                                </div>
                            </div>
                            <div class="row form-group">
                                <div class="col-sm-3">
                                    <label>Vessel size limit:</label>
                                </div>
                                <div class="col-sm-6">
                                    {{ mooring.vessel_size_limit }}
                                </div>
                            </div>
                            <div class="row form-group">
                                <div class="col-sm-3">
                                    <label>Vessel weight limit:</label>
                                </div>
                                <div class="col-sm-6">
                                    {{ mooring.vessel_weight_limit }}
                                </div>
                            </div>
                        </FormSection>
                        <FormSection label="Closure history" Index="closure_history">
                        what goes here?
                        </FormSection>
                    </div>
                    <div class="tab-pane fade" id="pills-bookings-permits" role="tabpanel" aria-labelledby="pills-bookings-permits-tab">
                        <FormSection label="Bookings/Permits" Index="bookings_permits">
                            <div v-if="entity.id">
                                <BookingsPermits
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
import BookingsPermits from '@common-utils/bookings_permits.vue'
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'
    export default {
        name:'MooringDetails',
        components:{
            FormSection,
            CommsLogs,
            BookingsPermits,
        },
         data:function () {
            return {
                mooring: {},
                comms_url: helpers.add_endpoint_json(api_endpoints.mooring, this.$route.params.mooring_id + '/comms_log'),
                comms_add_url: helpers.add_endpoint_json(api_endpoints.mooring, this.$route.params.mooring_id + '/add_comms_log'),
                logs_url: helpers.add_endpoint_json(api_endpoints.mooring, this.$route.params.mooring_id + '/action_log'),
             }
        },
        computed: {
            entity: function() {
                return {
                    type: "mooring",
                    id: this.mooring.id,
                }
            },
        },
        methods:{
            setTabs:function(){
                let vm = this;

                /* set Applicant tab Active */
                $('#pills-tab a[href="#pills-mooring-details"]').tab('show');

            },

        },
        mounted: function () {
            this.$nextTick(async () => {
                this.setTabs();
            });
        },
        created: async function() {
            const res = await this.$http.get(`/api/mooring/${this.$route.params.mooring_id}.json`);
            this.mooring = Object.assign({}, res.body);

        },
        /*
        beforeRouteEnter: async function(to, from, next) {
            if (to.params.mooring_id) {
                const res = await this.$http.get(`/api/mooring/${to.params.mooring_id}.json`);
                this.mooring = Object.assign({}, res.body);
            }
        },
        */

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

