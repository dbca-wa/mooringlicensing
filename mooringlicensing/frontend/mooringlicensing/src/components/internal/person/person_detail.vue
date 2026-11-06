<template>
    <div class="container" id="personDash">
        <h4>{{ user_header }}</h4>
        <div class="row">
            <div class="col-md-3">
                <CommsLogs
                    :comms_url="comms_url"
                    :logs_url="logs_url"
                    :comms_add_url="comms_add_url"
                    :disable_add_entry="false"
                    :enable_actions_section="false"
                />
            </div>

            <div class="col-md-8">
                <ul class="nav nav-pills mb-3" id="pills-tab" role="tablist">
                    <li class="nav-item">
                        <a class="nav-link active" id="pills-details-tab" data-toggle="pill" href="#pills-details" role="tab" aria-controls="pills-details" aria-selected="true" @click="tab_clicked()">
                            Details
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" id="pills-approvals-tab" data-toggle="pill" href="#pills-approvals" role="tab" aria-controls="pills-approvals" aria-selected="false">
                            Approvals
                        </a>
                    </li>
                    <li v-if="user" class="nav-item">
                        <a class="nav-link" id="pills-vessels-tab" data-toggle="pill" href="#pills-vessels" role="tab" aria-controls="pills-vessels" aria-selected="false" @click="tab_clicked()">
                            Vessels
                        </a>
                    </li>
                </ul>
                <div class="tab-content" id="pills-tabContent">
                    <div class="tab-pane fade" id="pills-details" role="tabpanel" aria-labelledby="pills-details-tab">
                        <Applicant v-if="user"
                            ref="applicant_table"
                            :user="user" 
                            id="proposalStartApplicant"
                        />
                    </div>
                    <div class="tab-pane fade" id="pills-approvals" role="tabpanel" aria-labelledby="pills-approvals-tab">
                        <FormSection :formCollapse="false" label="Applications" subtitle="" Index="applications" >
                            <ApplicationsTable 
                                ref="applications_table"
                                v-if="user"
                                level="internal"
                                :target_email_user_id="user.ledger_id"
                            />
                        </FormSection>

                        <FormSection :formCollapse="false" label="Waiting List" subtitle="" Index="waiting_list" >
                            <WaitingListTable
                                ref="waiting_list_table"
                                v-if="user"
                                level="internal"
                                :approvalTypeFilter="wlaApprovalTypeFilter"
                                :target_email_user_id="user.ledger_id"
                            />
                        </FormSection>

                        <FormSection :formCollapse="false" label="Licences and Permits" subtitle="" Index="licences_and_permits" >
                            <LicencesAndPermitsTable
                                ref="licences_and_permits_table"
                                v-if="user"
                                level="internal"
                                :approvalTypeFilter="allApprovalTypeFilter"
                                :target_email_user_id="user.ledger_id"
                            />
                        </FormSection>

                        <FormSection :formCollapse="false" label="Compliances" subtitle="" Index="compliances" >
                            <CompliancesTable
                                ref="compliances_table"
                                v-if="user"
                                level="internal"
                                :target_email_user_id="user.ledger_id"
                            />
                        </FormSection>
                    </div>
                    <div v-if="user" class="tab-pane fade" id="pills-vessels" role="tabpanel" aria-labelledby="pills-vessels-tab">
                        <FormSection :formCollapse="false" label="Vessels" subtitle="" Index="vessels" @click="tab_clicked()">
                            <VesselsTable
                                ref="vessels_table"
                                level="internal"
                                :target_email_user_id="user.ledger_id"
                            />
                        </FormSection>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import Applicant from '@/components/common/applicant.vue'
import ApplicationsTable from "@/components/common/table_proposals.vue"
import WaitingListTable from "@/components/common/table_approvals.vue"
import LicencesAndPermitsTable from "@/components/common/table_approvals.vue"
import CompliancesTable from "@/components/common/table_compliances.vue"
import VesselsTable from "@/components/common/table_vessels.vue"
import { api_endpoints, helpers } from '@/utils/hooks'
import CommsLogs from '@common-utils/comms_logs.vue'

export default {
    name: 'PersonDetail',
    data() {
        let vm = this
        return {
            user: null,
            allApprovalTypeFilter: ['ml', 'aap', 'aup'],
            wlaApprovalTypeFilter: ['wla',],

            comms_url: helpers.add_endpoint_json(api_endpoints.users, vm.$route.params.email_user_id + '/comms_log'),
            comms_add_url: helpers.add_endpoint_json(api_endpoints.users, vm.$route.params.email_user_id + '/add_comms_log'),
            logs_url: helpers.add_endpoint_json(api_endpoints.users, vm.$route.params.email_user_id + '/action_log'),
        }
    },
    components: {
        FormSection,
        Applicant,
        ApplicationsTable,
        WaitingListTable,
        LicencesAndPermitsTable,
        CompliancesTable,
        VesselsTable,
        CommsLogs,
    },
    computed: {
        user_header: function(){
            if (this.user) {
                if (this.user.legal_dob){
                    return this.user.legal_first_name + ' ' + this.user.legal_last_name + '(DOB: ' + this.user.legal_dob + ')'
                } else {
                    return this.user.legal_first_name + ' ' + this.user.legal_last_name
                }
            }
            return ''
        }
    },
    created: async function(){
        const res = await this.$http.get('/api/users/' + this.$route.params.email_user_id)
        if (res.ok) {
            this.user = res.body
        }
    },
    methods: {
        tab_clicked: function() {
            let vm = this;
            vm.$refs.applicant_table.adjust_address_tables();
            vm.$refs.vessels_table.adjust_vessel_table();
        }
    },
    mounted: function(){
        /* set Details tab Active */
        $('#pills-tab a[href="#pills-details"]').tab('show');
        // ensure datatables in tabs are responsive
        let vm=this;
        $('#pills-approvals-tab').on('shown.bs.tab', function (e) {
            vm.$refs.applications_table.$refs.application_datatable.vmDataTable.columns.adjust().responsive.recalc();
            vm.$refs.waiting_list_table.$refs.approvals_datatable.vmDataTable.columns.adjust().responsive.recalc();
            vm.$refs.licences_and_permits_table.$refs.approvals_datatable.vmDataTable.columns.adjust().responsive.recalc();
            vm.$refs.compliances_table.$refs.compliances_datatable.vmDataTable.columns.adjust().responsive.recalc();
        });
        $('#pills-vessels-tab').on('shown.bs.tab', function (e) {
            console.log(vm.$refs.vessels_table);
            vm.$refs.vessels_table.$refs.vessels_datatable.vmDataTable.columns.adjust().responsive.recalc();
        });
    },
}
</script>

<style>
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
