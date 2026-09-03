<template lang="html">
    <div id="proposedIssuanceApproval">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <form class="form-horizontal" name="approvalForm">
                        <alert :show.sync="showError" type="danger"><strong>{{ errorString }}</strong></alert>
                        <div class="col-sm-12">
                            <div class="form-group" v-if="displayBayField && siteLicensee">
                                <div class="row col-sm-12">
                                    <datatable ref="requestedMooringsTable" :id="requestedMooringsTableId" :dtOptions="requestedMooringsDtOptions"
                                        :dtHeaders="requestedMooringsDtHeaders" />
                                </div>
                            </div>
                            <div class="form-group" v-if="displayBayField && !siteLicensee">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left" for="mooring_bay">Bay</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <select class="form-control" v-model="approval.mooring_bay_id"
                                            id="mooring_bay_lookup" :disabled="readonly">
                                            <option v-for="bay in mooringBays" v-bind:value="bay.id">
                                                {{ bay.name }}
                                            </option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                            <div class="form-group" v-if="displayMooringSiteIdField && !siteLicensee">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left" for="mooring_site_id">Mooring Site ID</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <select id="mooring_lookup" name="mooring_lookup" ref="mooring_lookup"
                                            class="form-control" style="width:100%" :disabled="readonly"/>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="form-group" v-if="vessel_size_limit">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left">Mooring Vessel Length Limit</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <input class="form-control" disabled :value="vessel_size_limit"/>
                                    </div>
                                </div>
                            </div>
                            <div class="form-group" v-if="vessel_draft_limit">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left">Mooring Vessel Draft Limit</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <input class="form-control" disabled :value="vessel_draft_limit"/>
                                    </div>
                                </div>
                            </div>
                            <div class="form-group" v-if="vessel_weight_limit">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left">Mooring Vessel Weight Limit</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <input class="form-control" disabled :value="vessel_weight_limit"/>
                                    </div>
                                </div>
                            </div>

                            <div class="form-group" v-if="displayMooringSiteIdField">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left">Proposed Vessel Length</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <input class="form-control" disabled :value="proposal.vessel_length"/>
                                    </div>
                                </div>
                            </div>
                            <div class="form-group" v-if="displayMooringSiteIdField">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left">Proposed Vessel Draft</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <input class="form-control" disabled :value="proposal.vessel_draft"/>
                                    </div>
                                </div>
                            </div>
                            <div class="form-group" v-if="displayMooringSiteIdField">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left">Proposed Vessel Weight</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <input class="form-control" disabled :value="proposal.vessel_weight"/>
                                    </div>
                                </div>
                            </div>

                            <div class="form-group" v-if="displayAssociatedMoorings">
                                <div class="row col-sm-12">
                                    <datatable ref="mooringsTable" :id="mooringsTableId" :dtOptions="mooringsDtOptions"
                                        :dtHeaders="mooringsDtHeaders" />
                                </div>

                            </div>
                            <div class="form-group" v-if="displayAssociatedVessels">
                                <div class="row col-sm-12">
                                    <datatable ref="vesselsTable" :id="vesselsTableId" :dtOptions="vesselsDtOptions"
                                        :dtHeaders="vesselsDtHeaders" />
                                </div>
                            </div>

                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left" for="Name">{{ detailsText }}</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <textarea name="approval_details" class="form-control" style="width:70%;"
                                            v-model="approval.details" :readonly="readonly"></textarea>
                                    </div>
                                </div>
                            </div>
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left" for="Name">{{ ccText }}</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <input type="text" class="form-control" name="approval_cc" style="width:70%;"
                                            ref="bcc_email" v-model="approval.cc_email" :readonly="readonly">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
            </div>

            <div slot="footer">
                <button type="button" v-if="issuingApproval" disabled class="btn btn-default" @click="ok"><i
                        class="fa fa-spinner fa-spin"></i> Processing</button>
                <button type="button" v-else class="btn btn-default" @click="ok">Ok</button>
                <button type="button" class="btn btn-default" @click="cancel">Cancel</button>
            </div>
        </modal>
    </div>
</template>

<script>
import modal from '@vue-utils/bootstrap-modal.vue'
import alert from '@vue-utils/alert.vue'
import datatable from '@vue-utils/datatable.vue'
import { helpers, api_endpoints, constants } from "@/utils/hooks.js"

export default {
    name: 'Proposed-Approval',
    components: {
        modal,
        alert,
        datatable,
    },
    props: {
        enable_col_checkbox: {
            type: Boolean,
            default: true,
        },
        proposal_id: {
            type: Number,
            required: true
        },
        proposal: {
            type: Object,
        },
        processing_status: {
            type: String,
            required: true
        },
        proposal_type: {
            type: String,
            required: true
        },
        submitter_email: {
            type: String,
            required: true
        },
        applicant_email: {
            type: String,
        },
        mooringBays: {
            type: Array,
        },
        readonly:{
            type: Boolean,
            default: true,
        },
    },
    data: function () {
        let vm = this;
        return {
            isModalOpen: false,
            form: null,
            approval: {
                mooring_id: null,
                mooring_bay_id: null,
            },
            vessel_weight_limit: null,
            vessel_size_limit: null,
            vessel_draft_limit: null,
            state: 'proposed_approval',
            issuingApproval: false,
            validation_form: null,
            errors: false,
            toDateError: false,
            startDateError: false,
            errorString: '',
            toDateErrorString: '',
            startDateErrorString: '',
            successString: '',
            success: false,
            datepickerOptions: {
                format: 'DD/MM/YYYY',
                showClear: true,
                useCurrent: false,
                keepInvalid: true,
                allowInputToggle: true
            },
            warningString: 'Please attach Level of Approval document before issuing Approval',
            mooringsTableId: 'moorings_table' + vm._uid,
            requestedMooringsTableId: 'requested_moorings_table' + vm._uid,
            vesselsTableId: 'vessels_table' + vm._uid,
            mooringsDtHeaders: [
                'Id',
                '',
                'Currently listed moorings',
                'Bay',
                '',
                'Status',
                'Length limit',
                'Draft limit',
                'Weight limit',
            ],
            mooringsDtOptions: {
                serverSide: false,
                searching: false,
                searchDelay: 1000,
                lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
                order: [
                    [1, 'desc'], [0, 'desc'],
                ],
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: false,
                scrollX: true,
                fixedColumns: {
                    leftColumns: 1,
                    rightColumns: 1
                },
                processing: true,
                createdRow: function (row, data, index) {
                    $(row).attr('data-mooring-on-approval-id', data.id)

                    if (vm.proposal && (
                        vm.proposal.vessel_length > data.vessel_size_limit ||
                        vm.proposal.vessel_draft > data.vessel_draft_limit ||
                        (data.vessel_weight_limit > 0 && vm.proposal.vessel_weight > data.vessel_weight_limit)
                    )) {
                        $(row).css({
                            'background-color': '#ff6961'
                        })
                    }
                },
                columns: [
                    {
                        // Id (database id)
                        visible: false,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.id;
                        }
                    },
                    {
                        // Checkbox
                        data: 'id',
                        mRender: function (data, type, full) {
                            let disabled_str = ''
                            if (vm.readonly) {
                                disabled_str = ' disabled '
                            }
                            if (full.checked) {
                                return '<input type="checkbox" class="mooring_on_approval_checkbox" data-mooring-on-approval-id="' + full.id + '"'  + disabled_str +  ' checked/>'
                            } else {
                                return '<input type="checkbox" class="mooring_on_approval_checkbox" data-mooring-on-approval-id="' + full.id + '"'  + disabled_str +  '/>'
                            }
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {                            
                            return full.mooring_name;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.bay;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.site_licensee;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.status;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            
                            return full.vessel_size_limit;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            
                            return full.vessel_draft_limit;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            if (full.vessel_weight_limit > 0) {
                                return full.vessel_weight_limit;
                            } else {
                                return "N/A"
                            }
                        }
                    },
                ],
            },

            requestedMooringsDtHeaders: [
                'Id',
                '',
                'Requested moorings',
                'Bay',
                'Site Licensee',
                'Endorsement',
                'Length limit',
                'Draft limit',
                'Weight limit',
                
            ],
            requestedMooringsDtOptions: {
                serverSide: false,
                searching: false,
                searchDelay: 1000,
                lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
                order: [
                    [1, 'desc'], [0, 'desc'],
                ],
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: false,
                scrollX: true,
                fixedColumns: {
                    leftColumns: 1,
                    rightColumns: 1
                },
                processing: true,
                createdRow: function (row, data, index) {
                    $(row).attr('data-requested-mooring-on-approval-id', data.id)
                    if (vm.proposal && (
                        vm.proposal.vessel_length > data.vessel_size_limit ||
                        vm.proposal.vessel_draft > data.vessel_draft_limit ||
                        (data.vessel_weight_limit > 0 && vm.proposal.vessel_weight > data.vessel_weight_limit)
                    )) {
                        $(row).css({
                            'background-color': '#ff6961'
                        })
                    } else if (data.endorsement == "Declined" || data.endorsement == "Not Actioned") {
                        $(row).css({
                            'background-color': '#ffa07a'
                        })
                    }
                },
                columns: [
                    {
                        // Id (database id)
                        visible: false,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.id;
                        }
                    },
                    {
                        // Checkbox
                        data: 'id',
                        mRender: function (data, type, full) {
                            let disabled_str = ''
                            if (vm.readonly) {
                                disabled_str = ' disabled '
                            }
                            if (full.checked) {
                                return '<input type="checkbox" class="requested_mooring_on_approval_checkbox" data-requested-mooring-on-approval-id="' + full.id + '"'  + disabled_str +  ' checked/>'
                            } else {
                                return '<input type="checkbox" class="requested_mooring_on_approval_checkbox" data-requested-mooring-on-approval-id="' + full.id + '"'  + disabled_str +  '/>'
                            }
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {                            
                            return full.mooring_name;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.bay;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.site_licensee;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.endorsement
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {                            
                            return full.vessel_size_limit;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {                            
                            return full.vessel_draft_limit;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {                            
                            if (full.weight_draft_limit > 0) {
                                return full.weight_draft_limit;
                            } else {
                                return "N/A"
                            }
                        }
                    },
                    
                ],
            },
            vesselsDtHeaders: [
                'Id',
                '',
                'Currently listed vessels',
                'Vessel name',
                'Status',
            ],
            vesselsDtOptions: {
                serverSide: false,
                searching: false,
                searchDelay: 1000,
                lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
                order: [
                    [1, 'desc'], [0, 'desc'],
                ],
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: false,
                scrollX: true,
                fixedColumns: {
                    leftColumns: 1,
                    rightColumns: 1
                },
                processing: true,
                createdRow: function (row, data, index) {
                    $(row).attr('data-vessel-ownership-id', data.id)
                },
                columns: [
                    {
                        // Id (database id)
                        visible: false,
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.id;
                        }
                    },
                    {
                        // Checkbox
                        data: 'id',
                        mRender: function (data, type, full) {
                            let disabled_str = ''
                            if (vm.readonly) {
                                disabled_str = ' disabled '
                            }
                            if (full.checked) {
                                return '<input type="checkbox" class="mooring_on_approval_checkbox" data-vessel-ownership-id="' + full.id + '"' + disabled_str + ' checked/>'
                            } else {
                                return '<input type="checkbox" class="mooring_on_approval_checkbox" data-vessel-ownership-id="' + full.id + '"' + disabled_str + '/>'
                            }
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.rego;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.vessel_name;
                        }
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            return full.status;
                        }
                    },
                ],
            },

        }
    },
    computed: {
        siteLicensee: function () {
            let licensee = false;
            if (this.proposal && this.proposal.mooring_authorisation_preference === 'site_licensee') {
                licensee = true;
            }
            return licensee;
        },
        mooringLicenceApplication: function () {
            let app = false;
            if ([constants.ML_PROPOSAL].includes(this.proposal.application_type_dict.code)) {
                app = true;
            }
            return app;
        },
        authorisedUserApplication: function () {
            let app = false;
            if ([constants.AU_PROPOSAL].includes(this.proposal.application_type_dict.code)) {
                app = true;
            }
            return app;
        },
        requestedMoorings: function () {
            if (this.proposal.site_licensee_moorings.length > 0) {
                return this.proposal.site_licensee_moorings;
            }
            return []
        },
        authorisedUserMoorings: function () {
            if (this.proposal.authorised_user_moorings.length > 0) {
                return this.proposal.authorised_user_moorings;
            }
            return []
        },
        mooringLicenceVessels: function () {
            if (this.proposal.mooring_licence_vessels.length > 0) {
                return this.proposal.mooring_licence_vessels;
            }
        },
        displayAssociatedMoorings: function () {
            return this.authorisedUserApplication && this.authorisedUserMoorings;
        },
        displayAssociatedVessels: function () {
            return this.mooringLicenceApplication && this.mooringLicenceVessels;
        },
        displayBayField: function () {
            return this.authorisedUserApplication;
        },
        displayMooringSiteIdField: function () {
            return this.authorisedUserApplication;
        },
        display_sticker_number_field: function () {
            if ([constants.WL_PROPOSAL].includes(this.proposal.application_type_dict.code)) {
                return false
            }
            return true
        },
        showError: function () {
            var vm = this;
            return vm.errors;
        },
        showtoDateError: function () {
            var vm = this;
            return vm.toDateError;
        },
        showstartDateError: function () {
            var vm = this;
            return vm.startDateError;
        },
        detailsText: function () {
            let details = 'Proposed details';
            if (this.proposal && ['wla', 'aaa'].includes(this.proposal.application_type_code) || this.proposal.processing_status === "With Assessor") {
                details = 'Details';
            }
            return details
        },
        ccText: function () {
            let details = 'Proposed CC Email';
            if (this.proposal && ['wla', 'aaa'].includes(this.proposal.application_type_code) || this.proposal.processing_status === "With Assessor") {
                details = 'CC Email';
            }
            return details
        },

        title: function () {
            let title = this.processing_status == 'With Approver' ? 'Grant' : 'Propose grant';
            if (this.proposal && ['wla', 'aaa'].includes(this.proposal.application_type_code)) {
                title = 'Grant';
            }
            return title;
        },
        is_amendment: function () {
            return this.proposal_type == 'Amendment' ? true : false;
        },
        csrf_token: function () {
            return helpers.getCookie('csrftoken')
        },
    },
    methods: {
        ok: function () {
            let vm = this;
            if ($(vm.form).valid()) {
                vm.sendData();
            }
        },
        cancel: function () {
            this.close()
        },
        close: function () {
            this.isModalOpen = false;
            this.approval = {};
            this.errors = false;
            this.toDateError = false;
            this.startDateError = false;
            $('.has-error').removeClass('has-error');
            this.validation_form.resetForm();
        },

        fetchContact: function (id) {
            let vm = this;
            vm.$http.get(api_endpoints.contact(id)).then((response) => {
                vm.contact = response.body; vm.isModalOpen = true;
            }, (error) => {
                console.log(error);
            });
        },
        sendData: function () {
            console.log('%cin sendData', 'color: #c33;')
            let vm = this;
            vm.errors = false;
            this.$nextTick(() => {
                // ensure mooring_on_approval is not null
                if (!this.approval.mooring_on_approval) {
                    this.approval.mooring_on_approval = [];
                }
                if (!this.approval.requested_mooring_on_approval) {
                    this.approval.requested_mooring_on_approval = [];
                }
                // ensure vessel_ownership is not null
                if (!this.approval.vessel_ownership) {
                    this.approval.vessel_ownership = [];
                }
                if (this.authorisedUserApplication && this.authorisedUserMoorings) {
                    for (let moa of this.authorisedUserMoorings) {
                        this.approval.mooring_on_approval.push({ "id": moa.id, "checked": moa.checked });
                    }
                }
                if (this.authorisedUserApplication && this.requestedMoorings && this.siteLicensee) {
                    for (let moa of this.requestedMoorings) {
                        this.approval.requested_mooring_on_approval.push({ "id": moa.mooring_id, "checked": moa.checked });
                    }
                }
                if (this.mooringLicenceApplication && this.mooringLicenceVessels) {
                    for (let vo of this.mooringLicenceVessels) {
                        this.approval.vessel_ownership.push({ "id": vo.id, "checked": vo.checked });
                    }
                }
                let approval = JSON.parse(JSON.stringify(vm.approval));

                vm.issuingApproval = true;
                if (vm.state == 'proposed_approval') {
                    vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, vm.proposal_id + '/proposed_approval'), JSON.stringify(approval), {
                        emulateJSON: true,
                    }).then((response) => {
                        vm.issuingApproval = false;
                        vm.close();
                        vm.$emit('refreshFromResponse', response);
                        vm.$router.push({ path: '/internal' }); //Navigate to dashboard page after Propose issue.

                    }, (error) => {
                        vm.errors = true;
                        vm.issuingApproval = false;
                        vm.errorString = helpers.apiVueResourceError(error);
                    });
                }
                else if (vm.state == 'final_approval') {
                    console.log('final_approval in proposed_issuance.vue')
                    vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, vm.proposal_id + '/final_approval'), JSON.stringify(approval), {
                        emulateJSON: true,
                    }).then((response) => {
                        vm.issuingApproval = false;
                        vm.close();
                        vm.$emit('refreshFromResponse', response);
                        vm.$router.push({ path: '/internal' }); //Navigate to dashboard page after final approval.
                    }, (error) => {
                        vm.errors = true;
                        vm.issuingApproval = false;
                        vm.errorString = helpers.apiVueResourceError(error);
                    });
                }
            });

        },
        addFormValidations: function () {
            let vm = this;
            vm.validation_form = $(vm.form).validate({
                showErrors: function (errorMap, errorList) {
                    $.each(this.validElements(), function (index, element) {
                        var $element = $(element);
                        $element.attr("data-original-title", "").parents('.form-group').removeClass('has-error');
                    });
                    // destroy tooltips on valid elements
                    $("." + this.settings.validClass).tooltip("destroy");
                    // add or update tooltips
                    for (var i = 0; i < errorList.length; i++) {
                        var error = errorList[i];
                        $(error.element)
                            .tooltip({
                                trigger: "focus"
                            })
                            .attr("data-original-title", error.message)
                            .parents('.form-group').addClass('has-error');
                    }
                }
            });
        },
        constructMooringsTable: function () {
            console.log('in constructMooringsTable()')
            // update checkboxes
            if (this.authorisedUserMoorings && this.approval.mooring_on_approval && this.approval.mooring_on_approval.length > 0) {
                console.log('construct 1')
                for (let moa1 of this.approval.mooring_on_approval) {
                    for (let moa2 of this.authorisedUserMoorings) {
                        if (moa1.id === moa2.id) {
                            console.log('inside if')
                            moa2.checked = moa1.checked;
                        }
                    }
                }
            } else {
                console.log('construct 2')
            }
            // now draw table
            if (this.$refs.mooringsTable) {
                // Clear table
                this.$refs.mooringsTable.vmDataTable.clear().draw();
                // Construct table
                if (this.authorisedUserMoorings.length > 0) {
                    for (let mooring of this.authorisedUserMoorings) {
                        this.addMooringToTable(mooring);
                    }
                }
            }
        },
        constructRequestedMooringsTable: function () {
            console.log('in constructRequestedMooringsTable()')
            // update checkboxes
            if (this.requestedMoorings && this.approval.requested_mooring_on_approval && this.approval.requested_mooring_on_approval.length > 0) {
                console.log('construct 1')
                for (let moa1 of this.approval.requested_mooring_on_approval) {
                    for (let moa2 of this.requestedMoorings) {
                        if (moa1.id === moa2.id) {
                            console.log('inside if')
                            moa2.checked = moa1.checked;
                        }
                    }
                }
            } else {
                console.log('construct 2')
            }
            // now draw table
            if (this.$refs.requestedMooringsTable) {
                // Clear table
                this.$refs.requestedMooringsTable.vmDataTable.clear().draw();
                // Construct table
                if (this.requestedMoorings.length > 0) {
                    for (let mooring of this.requestedMoorings) {
                        this.addRequestedMooringToTable(mooring);
                    }
                }
            }
        },
        addMooringToTable: function (mooring) {
            this.$refs.mooringsTable.vmDataTable.row.add(mooring).draw();
        },
        addRequestedMooringToTable: function (mooring) {
            this.$refs.requestedMooringsTable.vmDataTable.row.add(mooring).draw();
        },
        getMooringOnApprovalIdFromEvent(e) {
            let mooringOnApprovalId = e.target.getAttribute("data-mooring-on-approval-id");
            if (!(mooringOnApprovalId)) {
                mooringOnApprovalId = e.target.getElementsByTagName('span')[0].getAttribute('data-mooring-on-approval-id');
            }
            return mooringOnApprovalId;
        },
        getRequestedMooringOnApprovalIdFromEvent(e) {
            let requestedMooringOnApprovalId = e.target.getAttribute("data-requested-mooring-on-approval-id");
            if (!(requestedMooringOnApprovalId)) {
                requestedMooringOnApprovalId = e.target.getElementsByTagName('span')[0].getAttribute('data-requested-mooring-on-approval-id');
            }
            return requestedMooringOnApprovalId;
        },
        mooringsCheckboxClicked: function (e) {
            let vm = this;
            let mooringOnApprovalId = this.getMooringOnApprovalIdFromEvent(e);
            let checked_status = e.target.checked;
            for (let mooring of this.authorisedUserMoorings) {
                if (mooring.id == mooringOnApprovalId) {
                    mooring.checked = checked_status;
                }
            }
            e.stopPropagation();
        },
        requestedMooringsCheckboxClicked: function (e) {
            let vm = this;
            let requestedMooringOnApprovalId = this.getRequestedMooringOnApprovalIdFromEvent(e);
            let checked_status = e.target.checked;
            for (let mooring of this.requestedMoorings) {
                if (mooring.id == requestedMooringOnApprovalId) {
                    mooring.checked = checked_status;
                }
            }
            e.stopPropagation();
        },
        constructVesselsTable: function () {
            // update checkboxes
            if (this.mooringLicenceVessels && this.approval.vessel_ownership && this.approval.vessel_ownership.length > 0) {
                for (let vo1 of this.approval.vessel_ownership) {
                    for (let vo2 of this.mooringLicenceVessels) {
                        if (vo1.id === vo2.id) {
                            vo2.checked = vo1.checked;
                        }
                    }
                }
            }
            // now draw table
            if (this.$refs.vesselsTable) {
                // Clear table
                this.$refs.vesselsTable.vmDataTable.clear().draw();
                // Construct table
                if (this.mooringLicenceVessels.length > 0) {
                    for (let vo of this.mooringLicenceVessels) {
                        console.log('addVesselToTable')
                        console.log({vo})
                        this.addVesselToTable(vo);
                    }
                }
            }
        },
        addVesselToTable: function (vo) {
            this.$refs.vesselsTable.vmDataTable.row.add(vo).draw();
        },

        getVesselOwnershipIdFromEvent(e) {
            let vesselOwnershipId = e.target.getAttribute("data-vessel-ownership-id");
            if (!(vesselOwnershipId)) {
                vesselOwnershipId = e.target.getElementsByTagName('span')[0].getAttribute('data-vessel-ownership-id');
            }
            return vesselOwnershipId;
        },
        vesselsCheckboxClicked: function (e) {
            let vm = this;
            let vesselOwnershipId = this.getVesselOwnershipIdFromEvent(e);
            console.log(vesselOwnershipId);
            let checked_status = e.target.checked;
            for (let vo of this.mooringLicenceVessels) {
                if (vo.id == vesselOwnershipId) {
                    console.log(e.target.checked)
                    vo.checked = checked_status;
                }
            }
            e.stopPropagation();
        },

        addEventListeners: function () {
            $("#" + this.mooringsTableId).on('click', 'input[type="checkbox"]', this.mooringsCheckboxClicked);
            $("#" + this.requestedMooringsTableId).on('click', 'input[type="checkbox"]', this.requestedMooringsCheckboxClicked);
            $("#" + this.vesselsTableId).on('click', 'input[type="checkbox"]', this.vesselsCheckboxClicked);
        },
        initialiseMooringLookup: function () {
            let vm = this;
            $(vm.$refs.mooring_lookup).select2({
                minimumInputLength: 2,
                "theme": "bootstrap",
                allowClear: true,
                placeholder: "Select Mooring",
                ajax: {
                    url: api_endpoints.mooring_lookup_per_bay,
                    dataType: 'json',
                    data: function (params) {
                        var query = {
                            term: params.term,
                            type: 'public',
                            mooring_bay_id: vm.approval.mooring_bay_id,
                            vessel_length:vm.proposal.vessel_length,
                            vessel_draft:vm.proposal.vessel_draft,
                            vessel_weight:vm.proposal.vessel_weight,
                            aup_id: vm.proposal.approval_id,
                        }
                        console.log('in data()')
                        return query;
                    },
                },
            }).
                on("select2:select", function (e) {
                    let data = e.params.data.id;
                    vm.approval.mooring_id = data;
                    vm.vessel_size_limit = e.params.data.vessel_size_limit;
                    vm.vessel_weight_limit = e.params.data.vessel_weight_limit;
                    vm.vessel_draft_limit = e.params.data.vessel_draft_limit;
                }).
                on("select2:unselect", function (e) {
                    vm.approval.mooring_id = null;
                    vm.vessel_size_limit = null;
                }).
                on("select2:open", function (e) {
                    const searchField = $('[aria-controls="select2-mooring_lookup-results"]')
                    // move focus to select2 field
                    searchField[0].focus();
                });
            vm.readRiaMooring();
            // clear mooring lookup on Mooring Bay change
            $('#mooring_bay_lookup').on('change', function () {
                $(vm.$refs.mooring_lookup).val(null).trigger('change');
            });
        },
        readRiaMooring: function () {
            let vm = this;
            if (vm.approval.ria_mooring_name) {
                var option = new Option(vm.approval.ria_mooring_name, vm.approval.ria_mooring_name, true, true);
                $(vm.$refs.mooring_lookup).append(option).trigger('change');
            } else {

            }
        },
    },
    watch: {
        isModalOpen: function() {
            this.$nextTick(() => {
                if (this.$refs.mooringsTable) {
                    this.$refs.mooringsTable.vmDataTable.columns.adjust().responsive.recalc();
                }
                if (this.$refs.requestedMooringsTable) {
                    this.$refs.requestedMooringsTable.vmDataTable.columns.adjust().responsive.recalc();
                }
            })
        }
    },
    mounted: function () {
        let vm = this;
        vm.form = document.forms.approvalForm;
        vm.addFormValidations();
        this.$nextTick(() => {
            this.initialiseMooringLookup();
            this.addEventListeners();
            if (this.authorisedUserApplication) {
                this.constructMooringsTable();
                if (this.siteLicensee) {
                    this.constructRequestedMooringsTable();
                }
            }
            if (this.mooringLicenceApplication) {
                this.constructVesselsTable();
            }
        });
    },
}
</script>

<style lang="css">
.site_checkbox {
    text-align: center;
}
</style>
