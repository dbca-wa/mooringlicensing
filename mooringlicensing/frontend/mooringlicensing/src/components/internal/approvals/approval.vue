<template>
    <div class="container" id="internalApproval">
        <div class="row">
            <h3>{{ approvalLabel }}: {{ approval.lodgement_number }}</h3>
            <div class="col-md-3">
                <CommsLogs
                    :comms_url="comms_url"
                    :logs_url="logs_url"
                    :comms_add_url="comms_add_url"
                    :disable_add_entry="false"
                />
                <div class="card mb-3">
                    <div class="card-header">Submission</div>
                    <div class="card-body border-bottom">
                        <div class="col-sm-12 top-buffer-s">
                            <strong>Issued on</strong><br />
                            {{ formatDate(approval.issue_date) }}
                        </div>
                    </div>
                </div>
                <div class="card mb-3">
                    <div class="card-header">Workflow</div>
                    <div class="card-body border-bottom">
                        <div class="row">
                            <div class="col-sm-12">
                                <strong>Status</strong><br />
                                {{ approval.status }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-1"></div>
            <div class="col-md-8">
                <div class="row" v-if="approval && approval.applicant">
                    <Applicant
                        :user="approval.applicant"
                        id="approvalSubmitterDetails"
                        :readonly="true"
                        customerType="holder"
                        :proposalId="approval.current_proposal.id"
                        :proposalApplicant="
                            approval.current_proposal.proposal_applicant
                        "
                    />
                </div>

                <div class="row">
                    <div>
                        <FormSection
                            :label="approvalLabel"
                            :formCollapse="true"
                            :Index="oBody"
                        >
                            <div v-if="loading.length == 0">
                                <form action="index.html" method="post">
                                    <div v-if="mooringLicence" class="row mb-3">
                                        <label
                                            for=""
                                            class="col-sm-3 col-form-label"
                                            >Mooring</label
                                        >
                                        <div class="col-sm-6">
                                            <label
                                                for=""
                                                class="form-label float-start"
                                                >{{
                                                    approval.mooring_licence_mooring
                                                }}</label
                                            >
                                        </div>
                                    </div>
                                    <div class="row mb-3">
                                        <label
                                            for=""
                                            class="col-sm-3 col-form-label"
                                            >Issue Date</label
                                        >
                                        <div class="col-sm-6">
                                            <label
                                                for=""
                                                class="form-label float-start"
                                                >{{
                                                    formatDate(
                                                        approval.issue_date
                                                    )
                                                }}</label
                                            >
                                        </div>
                                    </div>
                                    <div class="row mb-3">
                                        <label
                                            for=""
                                            class="col-sm-3 col-form-label"
                                            >Start Date</label
                                        >
                                        <div class="col-sm-6">
                                            <label
                                                for=""
                                                class="form-label float-start"
                                                >{{
                                                    formatDate(
                                                        approval.start_date
                                                    )
                                                }}</label
                                            >
                                        </div>
                                    </div>
                                    <div class="row mb-3">
                                        <label
                                            for=""
                                            class="col-sm-3 col-form-label"
                                            >Expiry Date</label
                                        >
                                        <div class="col-sm-3">
                                            <label
                                                for=""
                                                class="form-label float-start"
                                                >{{
                                                    approval.expiry_date_str
                                                }}</label
                                            >
                                        </div>
                                    </div>
                                    <div class="row mb-3">
                                        <label
                                            for=""
                                            class="col-sm-3 col-form-label"
                                            >{{ approvalLabel }}</label
                                        >
                                        <div class="col-sm-4">
                                            <p>
                                                <a
                                                    target="_blank"
                                                    :href="
                                                        approval.licence_document
                                                    "
                                                    class="form-label float-start"
                                                    >Licence.pdf</a
                                                >
                                            </p>
                                        </div>
                                    </div>
                                </form>
                            </div>
                        </FormSection>
                    </div>
                </div>
                <div
                    class="row"
                    v-if="
                        approval &&
                        approval.applicant &&
                        approval.current_proposal &&
                        annualAdmissionPermit
                    "
                >
                    <div class="col-12">
                        <Vessels
                            :proposal="approval.current_proposal"
                            :profile="approval.applicant"
                            id="approvalVessel"
                            ref="vessel"
                            :readonly="true"
                            :is_internal="true"
                            :keep_current_vessel="true"
                        />
                    </div>
                </div>
                <div
                    class="row"
                    v-if="approval && approval.id && authorisedUserPermit"
                >
                    <div>
                        <FormSection
                            :formCollapse="false"
                            label="Moorings"
                            Index="moorings"
                        >
                            <div class="col-sm-12">
                                <datatable
                                    ref="moorings_datatable"
                                    :id="moorings_datatable_id"
                                    :dtOptions="moorings_datatable_options"
                                    :dtHeaders="moorings_datatable_headers"
                                />
                            </div>
                        </FormSection>
                    </div>
                </div>
                <div
                    class="row"
                    v-if="approval && approval.id && mooringLicence"
                >
                    <div>
                        <FormSection
                            :formCollapse="false"
                            label="Authorised Users"
                            Index="mooringLicenceAuthorisedUsers"
                        >
                            <div class="row">
                                <div class="col-lg-12">
                                    <input
                                        type="checkbox"
                                        id="checkbox_show_expired"
                                        v-model="showExpired"
                                    />
                                    <label for="checkbox_show_expired"
                                        >Show expired and/or surrendered
                                        authorised user permits</label
                                    >
                                </div>
                            </div>
                            <div class="col-sm-12">
                                <datatable
                                    ref="ml_authorised_users_datatable"
                                    :id="ml_authorised_users_datatable_id"
                                    :dtOptions="
                                        ml_authorised_users_datatable_options
                                    "
                                    :dtHeaders="
                                        ml_authorised_users_datatable_headers
                                    "
                                />
                            </div>
                        </FormSection>
                    </div>
                </div>

                <div
                    class="row"
                    v-if="approval && approval.id && mooringLicence"
                >
                    <div>
                        <FormSection
                            :formCollapse="false"
                            label="Vessels"
                            Index="mooringLicenceVessels"
                        >
                            <div class="col-sm-12">
                                <datatable
                                    ref="ml_vessels_datatable"
                                    :id="ml_vessels_datatable_id"
                                    :dtOptions="ml_vessels_datatable_options"
                                    :dtHeaders="ml_vessels_datatable_headers"
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
import http from '@/utils/vue-resource-shim';
import datatable from '@vue-utils/datatable.vue';
import CommsLogs from '@common-utils/comms_logs.vue';
import Applicant from '@/components/common/applicant.vue';
import Vessels from '@/components/common/vessels.vue';
import FormSection from '@/components/forms/section_toggle.vue';
import { api_endpoints, helpers } from '@/utils/hooks';
export default {
    name: 'ApprovalDetail',
    data() {
        let vm = this;
        return {
            showExpired: false,
            moorings_datatable_id: 'moorings-datatable-' + vm.$.uid,
            ml_vessels_datatable_id: 'ml-vessels-datatable-' + vm.$.uid,
            ml_authorised_users_datatable_id:
                'ml-authorised-users-datatable-' + vm.$.uid,
            loading: [],
            approval: {
                applicant_id: null,
            },
            DATE_TIME_FORMAT: 'DD/MM/YYYY HH:mm:ss',
            adBody: 'adBody' + vm.$.uid,
            pBody: 'pBody' + vm.$.uid,
            cBody: 'cBody' + vm.$.uid,
            oBody: 'oBody' + vm.$.uid,
            org: {
                address: {},
            },

            // Filters
            logs_url: helpers.add_endpoint_json(
                api_endpoints.approvals,
                vm.$route.params.approval_id + '/action_log'
            ),
            comms_url: helpers.add_endpoint_json(
                api_endpoints.approvals,
                vm.$route.params.approval_id + '/comms_log'
            ),
            comms_add_url: helpers.add_endpoint_json(
                api_endpoints.approvals,
                vm.$route.params.approval_id + '/add_comms_log'
            ),
            moorings_datatable_headers: [
                'Mooring',
                'Sticker',
                'Licensee',
                'Allocated By',
                'Mobile',
                'Email',
                'Action',
            ],

            moorings_datatable_options: {
                autoWidth: false,
                responsive: false,
                scrollX: true,
                fixedColumns: {
                    leftColumns: 1,
                    rightColumns: 1,
                },
                columns: [
                    {
                        data: 'mooring_name',
                    },
                    {
                        data: 'sticker',
                    },
                    {
                        data: 'licensee',
                    },
                    {
                        data: 'allocated_by',
                    },
                    {
                        data: 'mobile',
                    },
                    {
                        data: 'email',
                    },
                    {
                        data: 'action',
                        render: function (row, type, full) {
                            let links = '';
                            links += `<a href="#${full.mooring_name}" onclick="window.removeMooringFromAUP('${full.mooring_name}')" style="cursor: pointer;">Remove</a><br/>`;
                            return links;
                        },
                    },
                ],
            },
            ml_vessels_datatable_headers: [
                'Vessel',
                'Rego No',
                'Sticker',
                'Owner',
                'Mobile',
                'Email',
            ],

            ml_vessels_datatable_options: {
                autoWidth: false,
                responsive: false,
                scrollX: true,
                fixedColumns: {
                    leftColumns: 1,
                    rightColumns: 1,
                },
                columns: [
                    {
                        data: 'vessel_name',
                    },
                    {
                        data: 'rego_no',
                    },
                    {
                        data: 'sticker_numbers',
                    },
                    {
                        data: 'owner',
                    },
                    {
                        data: 'mobile',
                    },
                    {
                        data: 'email',
                    },
                ],
            },
            ml_authorised_users_datatable_headers: [
                'Number',
                'Vessel',
                'Holder',
                'Mobile',
                'Email',
                'Status',
            ],

            ml_authorised_users_datatable_options: {
                autoWidth: false,
                responsive: false,
                scrollX: true,
                fixedColumns: {
                    leftColumns: 1,
                    rightColumns: 1,
                },
                columns: [
                    {
                        data: 'lodgement_number',
                    },
                    {
                        data: 'vessel_name',
                    },
                    {
                        data: 'holder',
                    },
                    {
                        data: 'mobile',
                    },
                    {
                        data: 'email',
                    },
                    {
                        data: 'status',
                    },
                ],
            },
        };
    },
    watch: {
        showExpired: function (value) {
            this.$nextTick(() => {
                this.constructMLAuthorisedUsersTable();
            });
        },
    },
    props: {
        approvalId: {
            type: Number,
        },
    },
    created: async function () {
        const response = await http.get(
            helpers.add_endpoint_json(
                api_endpoints.approvals,
                this.$route.params.approval_id
            )
        );
        this.approval = Object.assign({}, response.body);
        this.approval.applicant_id = response.body.applicant_id;

        await this.$nextTick(() => {
            if (
                this.approval &&
                this.approval.id &&
                this.authorisedUserPermit
            ) {
                this.constructMooringsTable();
            }
            if (this.approval && this.approval.id && this.mooringLicence) {
                this.constructMLVesselsTable();
                this.constructMLAuthorisedUsersTable();
            }
        });
    },
    components: {
        datatable,
        CommsLogs,
        FormSection,
        Applicant,
        Vessels,
    },
    computed: {
        isLoading: function () {
            return this.loading.length > 0;
        },
        approvalLabel: function () {
            let description = '';
            if (this.approval && this.approval.approval_type_dict) {
                description = this.approval.approval_type_dict.description;
            }
            return description;
        },
        annualAdmissionPermit: function () {
            let permit = false;
            if (
                this.approval &&
                this.approval.approval_type_dict &&
                this.approval.approval_type_dict.code === 'aap'
            ) {
                permit = true;
            }
            return permit;
        },
        authorisedUserPermit: function () {
            let permit = false;
            if (
                this.approval &&
                this.approval.approval_type_dict &&
                this.approval.approval_type_dict.code === 'aup'
            ) {
                permit = true;
            }
            return permit;
        },
        mooringLicence: function () {
            let permit = false;
            if (
                this.approval &&
                this.approval.approval_type_dict &&
                this.approval.approval_type_dict.code === 'ml'
            ) {
                permit = true;
            }
            return permit;
        },
    },
    methods: {
        formatDate: function (data) {
            return moment(data).format('DD/MM/YYYY');
        },
        constructMooringsTable: function () {
            let vm = this;
            this.$refs.moorings_datatable.vmDataTable.clear().draw();
            for (let aum of vm.approval.authorised_user_moorings_detail) {
                this.$refs.moorings_datatable.vmDataTable.row
                    .add({
                        mooring_name: aum.mooring_name,
                        sticker: aum.sticker,
                        licensee: aum.licensee,
                        allocated_by: aum.allocated_by,
                        mobile: aum.mobile,
                        email: aum.email,
                        action: null,
                    })
                    .draw();
            }
            vm.$refs.moorings_datatable.vmDataTable.columns
                .adjust()
                .responsive.recalc();
        },

        constructMLVesselsTable: function () {
            let vm = this;
            this.$refs.ml_vessels_datatable.vmDataTable.clear().draw();

            for (let mlv of vm.approval.mooring_licence_vessels_detail) {
                this.$refs.ml_vessels_datatable.vmDataTable.row
                    .add({
                        vessel_name: mlv.vessel_name,
                        rego_no: mlv.rego_no,
                        sticker_numbers: mlv.sticker_numbers,
                        owner: mlv.owner,
                        mobile: mlv.mobile,
                        email: mlv.email,
                    })
                    .draw();
            }
            vm.$refs.ml_vessels_datatable.vmDataTable.columns
                .adjust()
                .responsive.recalc();
        },
        constructMLAuthorisedUsersTable: function () {
            let vm = this;
            this.$refs.ml_authorised_users_datatable.vmDataTable.clear().draw();

            for (let mlau of vm.approval.mooring_licence_authorised_users) {
                if (
                    this.showExpired ||
                    (!this.showExpired && ['Current'].includes(mlau.status))
                ) {
                    this.$refs.ml_authorised_users_datatable.vmDataTable.row
                        .add({
                            lodgement_number: mlau.lodgement_number,
                            vessel_name: mlau.vessel_name,
                            holder: mlau.holder,
                            mobile: mlau.mobile,
                            email: mlau.email,
                            status: mlau.status,
                        })
                        .draw();
                }
            }
            vm.$refs.ml_authorised_users_datatable.vmDataTable.columns
                .adjust()
                .responsive.recalc();
        },
        commaToNewline(s) {
            return s.replace(/[,;]/g, '\n');
        },
        removeMooringFromAUP(mooringName) {
            let vm = this;
            swal({
                title: 'Remove Mooring',
                text: 'Are you sure you want to Remove the Mooring?',
                type: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Remove',
                confirmButtonColor: '#dc3545',
                allowOutsideClick: false,
                preConfirm: function () {
                    return new Promise(async function () {
                        try {
                            let payload = {
                                mooring_name: mooringName,
                            };
                            const resp = await vm.$http.post(
                                `/api/approvals/${vm.approval.id}/removeMooringFromApproval/`,
                                payload
                            );
                            if (resp.status === 200) {
                                const rowIndex =
                                    vm.approval.authorised_user_moorings_detail.findIndex(
                                        (row) =>
                                            row.mooring_name === mooringName
                                    );
                                if (rowIndex !== -1) {
                                    vm.approval.authorised_user_moorings_detail.splice(
                                        rowIndex,
                                        1
                                    );
                                    swal(
                                        'Removed!',
                                        'The mooring has been removed successfully.',
                                        'success'
                                    ).then(() => {
                                        vm.$nextTick(async () => {
                                            window.location.reload();
                                        });
                                    });
                                }
                            }
                        } catch (error) {
                            swal('Error!', error.bodyText, 'error');
                            console.error(error);
                        }
                    });
                },
            });
        },
        viewApprovalPDF: function (id, media_link) {
            let vm = this;
            vm.$http
                .get(
                    helpers.add_endpoint_json(
                        api_endpoints.approvals,
                        id + '/approval_pdf_view_log'
                    ),
                    {}
                )
                .then(
                    (response) => {},
                    (error) => {
                        console.log(error);
                    }
                );
            window.open(media_link, '_blank');
        },
    },
    mounted: function () {
        window.removeMooringFromAUP = (mooringName) => {
            this.removeMooringFromAUP(mooringName);
        };
    },
};
</script>
<style scoped>
.top-buffer-s {
    margin-top: 10px;
}
.actionBtn {
    cursor: pointer;
}
.hidePopover {
    display: none;
}
</style>
