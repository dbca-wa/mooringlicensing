<template>
    <div>
        <div v-if="is_external && wlaDash">
            <div class="row">
                <div class="col-lg-12">
                    <input type="checkbox" id="checkbox_show_expired" v-model="show_expired_surrendered">
                    <label for="checkbox_show_expired">Show expired and/or surrendered waiting list allocations</label>
                </div>
            </div>
        </div>
        <div v-else class="row">
            <div v-if="!wlaDash">
                    <div class="col-md-3">
                        <div class="form-group">
                            <label for="">Type:</label>
                            <select class="form-control" v-model="filterApprovalType">
                                <option value="All">All</option>
                                <option v-for="type in approvalTypes" :value="type.code">{{ type.description }}</option>
                            </select>
                        </div>
                    </div>
                <!--div v-if="is_internal">
                    <div class="col-md-3">
                        <div class="form-group">
                            <label for="">Holder:</label>
                            <select class="form-control" v-model="filterHolder">
                                <option value="All">All</option>
                                <option v-for="h in holderList" :value="h.id">{{ h.full_name }}</option>
                            </select>
                        </div>
                    </div>
                </div-->
            </div>
            <div v-else>
                <div class="col-md-3">
                    <div class="form-group">
                        <label for="">Bay:</label>
                        <select class="form-control" v-model="filterMooringBay">
                            <option value="All">All</option>
                            <option v-for="bay in mooringBays" :value="bay.id">{{ bay.name }}</option>
                        </select>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Status:</label>
                    <select class="form-control" v-model="filterStatus">
                        <option value="All">All</option>
                        <option v-for="status in statusValues" :value="status.code">{{ status.description }}</option>
                    </select>
                </div>
            </div>

            <div v-if="wlaDash">
                <div class="col-md-2">
                    <div class="form-group">
                        <label for="">Max Vessel Length:</label>
                        <input class="form-control" type="number" v-model="maxVesselLength" id="maxVesselLength"/>
                        <!--select class="form-control" v-model="filterStatus">
                            <option value="All">All</option>
                            <option v-for="status in statusValues" :value="status.code">{{ status.description }}</option>
                        </select-->
                    </div>
                </div>
                <div class="col-md-2">
                    <div class="form-group">
                        <label for="">Max Vessel Draft:</label>
                        <input class="form-control" type="number" v-model="maxVesselDraft" id="maxVesselDraft"/>
                        <!--select class="form-control" v-model="filterStatus">
                            <option value="All">All</option>
                            <option v-for="status in statusValues" :value="status.code">{{ status.description }}</option>
                        </select-->
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-12">
                <datatable
                    ref="approvals_datatable"
                    :id="datatable_id"
                    :dtOptions="datatable_options"
                    :dtHeaders="datatable_headers"
                />
            </div>
        </div>
        <div v-if="is_internal && wlaDash && selectedWaitingListAllocationId">
            <OfferMooringLicence
                ref="offer_mooring_licence"
                :key="offerMooringLicenceKey"
                :wlaId="selectedWaitingListAllocationId"
                :mooringBayId="mooringBayId"
                @refreshFromResponse="refreshFromResponse"
            />
        </div>
        <ApprovalCancellation ref="approval_cancellation"  @refreshFromResponse="refreshFromResponseApprovalModify"></ApprovalCancellation>
        <ApprovalSuspension ref="approval_suspension"  @refreshFromResponse="refreshFromResponseApprovalModify"></ApprovalSuspension>
        <ApprovalSurrender ref="approval_surrender"  @refreshFromResponse="refreshFromResponseApprovalModify"></ApprovalSurrender>
        <div v-if="approvalHistoryId">
            <ApprovalHistory
                ref="approval_history"
                :key="approvalHistoryId"
                :approvalId="approvalHistoryId"
            />
        </div>
        <!--ApprovalHistory ref="approval_history" /-->
        <RequestNewStickerModal
            ref="request_new_sticker_modal"
            @sendData="sendData"
        />
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import OfferMooringLicence from '@/components/internal/approvals/offer_mooring_licence.vue'
import ApprovalCancellation from '../internal/approvals/approval_cancellation.vue'
import ApprovalSuspension from '../internal/approvals/approval_suspension.vue'
import ApprovalSurrender from '../internal/approvals/approval_surrender.vue'
import ApprovalHistory from '../internal/approvals/approval_history.vue'
import RequestNewStickerModal from "@/components/common/request_new_sticker_modal.vue"
import Vue from 'vue'
import { api_endpoints, helpers }from '@/utils/hooks'

export default {
    name: 'TableApprovals',
    props: {
        approvalTypeFilter: {
            type: Array,
            required: true,
            /*
            validator: function(val) {
                let options = ['wla', 'ml', 'aap', 'aup'];
                return options.indexOf(val) != -1 ? true: false;
            }
            */
        },
        level:{
            type: String,
            required: true,
            validator: function(val) {
                let options = ['internal', 'referral', 'external'];
                return options.indexOf(val) != -1 ? true: false;
            }
        },
        target_email_user_id: {
            type: Number,
            required: false,
            default: 0,
        }
    },
    data() {
        let vm = this;
        return {
            datatable_id: 'waiting_lists-datatable-' + vm._uid,
            //approvalTypesToDisplay: ['wla'],
            show_expired_surrendered: false,
            selectedWaitingListAllocationId: null,
            approvalHistoryId: null,
            uuid: 0,
            mooringBayId: null,
            filterStatus: null,
            statusValues: [],
            filterApprovalType: null,
            approvalTypes: [],
            filterMooringBay: null,
            mooringBays: [],
            filterHolder: null,
            holderList: [],
            maxVesselLength: null,
            maxVesselDraft: null,
            profile: {},
        }
    },
    components:{
        datatable,
        OfferMooringLicence,
        ApprovalCancellation,
        ApprovalSuspension,
        ApprovalSurrender,
        ApprovalHistory,
        RequestNewStickerModal,
    },
    watch: {
        show_expired_surrendered: function(value){
            console.log(value)
            this.$refs.approvals_datatable.vmDataTable.ajax.reload()
        },
        filterStatus: function(){
            this.$refs.approvals_datatable.vmDataTable.ajax.reload()
        },
        filterApprovalType: function(){
            this.$refs.approvals_datatable.vmDataTable.ajax.reload()
        },
        filterMooringBay: function(){
            this.$refs.approvals_datatable.vmDataTable.ajax.reload()
        },
        filterHolder: function(){
            this.$refs.approvals_datatable.vmDataTable.ajax.reload()
        },
    },
    computed: {
        csrf_token: function() {
          return helpers.getCookie('csrftoken')
        },
        debug: function(){
            if (this.$route.query.debug){
                return this.$route.query.debug === 'Tru3'
            }
            return false
        },
        externalWaitingList: function() {
            let extWLA = false;
            if (this.is_external && this.wlaDash) {
                extWLA = true;
            }
            return extWLA;
        },
        wlaDash: function() {
            let returnVal = false;
            if (this.approvalTypeFilter.includes('wla')) {
                returnVal = true;
            }
            return returnVal;
        },
        is_external: function() {
            return this.level == 'external'
        },
        is_internal: function() {
            return this.level == 'internal'
        },
        // Datatable settings
        datatable_headers: function() {
            if (this.is_external && this.wlaDash) {
                return [
                    'Id',
                    'Number',
                    'Bay',
                    //'Application number in Bay',
                    'Allocation number in bay',
                    'Status',
                    'Vessel Registration',
                    'Vessel Name',
                    'Issue Date',
                    'Expiry Date',
                    'Action',
                    'Approval letter',
                ]
            } else if (this.is_external) {
                return [
                    'Id',
                    'Number',
                    'Type',
                    'Sticker number/s',
                    'Sticker mailed date',
                    'Status',
                    'Issue Date',
                    'Expiry Date',
                    'Vessel',
                    'Action',
                    'Approval letter',
                    //'Mooring Licence Vessels',
                    //'Authorised User Permit Moorings',
                ]
            } else if (this.is_internal && this.wlaDash) {
                return [
                    'Id',
                    'Number',
                    'Holder',
                    'Status',
                    'Status 2',
                    //'Mooring area',
                    'Bay',
                    'Allocation number in bay',
                    'Action',
                    'Issue Date',
                    'Expiry Date',
                    'Approval letter',
                    'Vessel length',
                    'Vessel draft',
                    'Vessel Rego',
                    'Mooring Licence Applications',
                ]
            } else if (this.is_internal) {
                return [
                    'Id',
                    'Number',
                    'Type',
                    'Sticker Number/s',
                    'Sticker mailed date',
                    'Holder',
                    'Status',
                    'Issue Date',
                    'Expiry Date',
                    'Approval letter',
                    'Vessel Regos',
                    'Action',
                    //'Mooring Licence Vessels',
                    //'Authorised User Permit Moorings',
                ]
            }
        },
        columnId: function() {
            return {
                        // 1. ID
                        data: "id",
                        orderable: false,
                        searchable: false,
                        visible: false,
                        'render': function(row, type, full){
                            return full.id
                        }
                    }
        },
        columnLodgementNumber: function() {
            return {
                        // 2. Lodgement Number
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            if (full.migrated){
                                return full.lodgement_number + ' (M)'
                            } else {
                                return full.lodgement_number
                            }
                        },
                        name: 'lodgement_number',
                    }
        },
        columnApplicationNumberInBay: function() {
            return {
                        // 4. Application number in Bay
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.current_proposal_number;
                        }
                    }
        },
        columnStatus: function() {
            return {
                        // 5. Status
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.status
                        }
                    }
        },
        columnStatusInternal: function() {
            return {
                        // 5. Status
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.internal_status
                        }
                    }
        },
        columnVesselRegistration: function() {
            return {
                        // 6. Vessel Registration
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.vessel_registration;
                        }
                    }
        },
        columnVesselName: function() {
            return {
                        // 7. Vessel Name
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.vessel_name;
                        }
                    }
        },
        columnIssueDate: function() {
            return {
                        // 8. Issue Date
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.issue_date_str;
                        }
                    }
        },
        columnExpiryDate: function() {
            return {
                        // 9. Expiry Date
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.expiry_date_str;
                        }
                    }
        },
        columnAction: function() {
            let vm = this;
            return {
                        // 10. Action
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            console.log(full)
                            let links = '';
                            if(vm.debug){
                                links +=  `<a href='#${full.id}' data-request-new-sticker='${full.id}'>Request New Sticker</a><br/>`;
                            }
                            /*
                            if (vm.is_internal && vm.wlaDash) {
                                links += full.offer_link;
                            } else
                            */
                            if (vm.is_external && full.can_reissue) {
                                if(full.can_action || vm.debug){
                                    if(full.amend_or_renew === 'amend' || vm.debug){
                                       links +=  `<a href='#${full.id}' data-amend-approval='${full.current_proposal_id}'>Amend</a><br/>`;
                                    }
                                    if(full.amend_or_renew === 'renew' || vm.debug){
                                        links +=  `<a href='#${full.id}' data-renew-approval='${full.current_proposal_id}'>Renew</a><br/>`;
                                    }
                                    links +=  `<a href='#${full.id}' data-surrender-approval='${full.id}'>Surrender</a><br/>`;
                                }

                                if (full.approval_type_dict.code != 'wla') {
                                    links +=  `<a href='#${full.id}' data-request-new-sticker='${full.id}'>Request New Sticker</a><br/>`;
                                }

                            } else if (!vm.is_external){
                                links +=  `<a href='/internal/approval/${full.id}'>View</a><br/>`;
                                links +=  `<a href='#${full.id}' data-history-approval='${full.id}'>History</a><br/>`;
                                if(full.can_reissue && full.current_proposal_id && full.is_assessor && full.current_proposal_approved){
                                    links +=  `<a href='#${full.id}' data-reissue-approval='${full.current_proposal_id}'>Reissue</a><br/>`;
                                }
                                if (vm.is_internal && vm.wlaDash) {
                                    links += full.offer_link;
                                }
                                //if(vm.check_assessor(full)){
                                //if (full.allowed_assessors.includes(vm.profile.id)) {
                                if (full.allowed_assessors_user) {
                                //if (true) {
                                    if(full.can_reissue && full.can_action){
                                        links +=  `<a href='#${full.id}' data-cancel-approval='${full.id}'>Cancel</a><br/>`;
                                        links +=  `<a href='#${full.id}' data-surrender-approval='${full.id}'>Surrender</a><br/>`;
                                    }
                                    if(full.status == 'Current' && full.can_action){
                                        links +=  `<a href='#${full.id}' data-suspend-approval='${full.id}'>Suspend</a><br/>`;
                                    }
                                    if(full.can_reinstate)
                                    {
                                        links +=  `<a href='#${full.id}' data-reinstate-approval='${full.id}'>Reinstate</a><br/>`;
                                    }
                                }
                                if(full.renewal_document && full.renewal_sent){
                                  links +=  `<a href='${full.renewal_document}' target='_blank'>Renewal Notice</a><br/>`;
                                }
                            }

                            return links;
                        }
                    }
        },
        columnRiaGeneratedProposals: function() {
            let vm = this;
            return {
                        // 10. Action
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.ria_generated_proposals;
                        }
                    }
        },
        columnHolder: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.holder;
                        },
                        name: 'submitter__first_name, submitter__last_name',
                    }
        },
        columnPreferredMooringBay: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.preferred_mooring_bay;
                        }
                    }
        },
        columnAllocationNumberInBay: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.wla_order;
                        }
                    }
        },

        columnVesselLength: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.vessel_length;
                        }
                    }
        },
        columnVesselDraft: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.vessel_draft;
                        }
                    }
        },
        columnApprovalType: function() {
            //let vm = this;
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            //return full.vessel_draft;
                            let approvalType = '';
                            if (full.approval_type_dict) {
                                approvalType = full.approval_type_dict.description;
                            }
                            return approvalType;
                        }
                    }
        },
        columnStickerNumber: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            let ret_str = ''
                            for (let sticker of full.stickers){
                                ret_str += sticker.number + '<br />'
                            }
                            return ret_str
                        },
                        name: 'stickers__number',
                    }
        },
        columnStickerMailedDate: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            let ret_str = ''
                            for (let sticker of full.stickers){
                                console.log(sticker.mailing_date)
                                if (sticker.mailing_date){
                                    ret_str += moment(sticker.mailing_date).format('DD/MM/YYYY') + '<br />'
                                } else {
                                    ret_str += ''
                                }
                            }
                            return ret_str
                        }
                    }
        },
        columnApprovalLetter: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            let approval_letter_name = ''
                            if (full.approval_type_dict.code === 'aup'){
                                approval_letter_name = 'Authorised User Permit'
                            } else if (full.approval_type_dict.code === 'aap'){
                                approval_letter_name = 'Annual Admission Permit'
                            } else if (full.approval_type_dict.code === 'ml'){
                                approval_letter_name = 'Mooring Licence'
                            }
                            let ret_elems = `<div><a href='${full.licence_document}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> ${approval_letter_name}</a></div>`;
                            if (full.authorised_user_summary_document){
                                ret_elems += `<div><a href='${full.authorised_user_summary_document}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> List of Authorised Users</a></div>`;
                            }

                            return ret_elems
                        }
                    }
        },
        /*
        columnMooringLicenceVessels: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.mooring_licence_vessels;
                        }
                    }
        },
        columnAuthorisedUserMoorings: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.authorised_user_moorings;
                        }
                    }
        },
        */
        columnVesselRegos: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.vessel_regos;
                            //return '';
                        }
                    }
        },
        datatable_options: function() {
            let vm = this;
            let selectedColumns = [];
            if (vm.is_external && this.wlaDash) {
                selectedColumns = [
                    vm.columnId,
                    vm.columnLodgementNumber,
                    //vm.columnBay,
                    vm.columnPreferredMooringBay,
                    //vm.columnApplicationNumberInBay,
                    vm.columnAllocationNumberInBay,
                    vm.columnStatus,
                    vm.columnVesselRegistration,
                    vm.columnVesselName,
                    vm.columnIssueDate,
                    vm.columnExpiryDate,
                    vm.columnAction,
                    vm.columnApprovalLetter,
                ]
            } else if (this.is_external) {
                selectedColumns = [
                    vm.columnId,
                    vm.columnLodgementNumber,
                    vm.columnApprovalType,
                    vm.columnStickerNumber,
                    vm.columnStickerMailedDate,
                    vm.columnStatus,
                    vm.columnIssueDate,
                    vm.columnExpiryDate,
                    vm.columnVesselRegistration,
                    vm.columnAction,
                    vm.columnApprovalLetter,
                    /*
                    vm.columnMooringLicenceVessels,
                    vm.columnAuthorisedUserMoorings,
                    */
                ]
            } else if (vm.is_internal && this.wlaDash) {
                selectedColumns = [
                    vm.columnId,
                    vm.columnLodgementNumber,
                    vm.columnHolder,
                    vm.columnStatus,
                    vm.columnStatusInternal,
                    vm.columnPreferredMooringBay,
                    vm.columnAllocationNumberInBay,
                    vm.columnAction,
                    vm.columnIssueDate,
                    vm.columnExpiryDate,
                    vm.columnApprovalLetter,
                    vm.columnVesselLength,
                    vm.columnVesselDraft,
                    vm.columnVesselRegos,
                    vm.columnRiaGeneratedProposals,
                ]
            } else if (vm.is_internal) {
                selectedColumns = [
                    vm.columnId,
                    vm.columnLodgementNumber,
                    vm.columnApprovalType,
                    vm.columnStickerNumber,
                    vm.columnStickerMailedDate,
                    vm.columnHolder,
                    vm.columnStatus,
                    vm.columnIssueDate,
                    vm.columnExpiryDate,
                    vm.columnApprovalLetter,
                    vm.columnVesselRegos,
                    vm.columnAction,
                    /*
                    vm.columnMooringLicenceVessels,
                    vm.columnAuthorisedUserMoorings,
                    */
                ]
            }
            let buttons = []
            if (vm.is_internal){
                buttons = [
                    {
                        extend: 'excel',
                        exportOptions: {
                            columns: ':visible'
                        }
                    },
                    {
                        extend: 'csv',
                        exportOptions: {
                            columns: ':visible'
                        }
                    },
                ]
            }

            return {
                autoWidth: false,
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                serverSide: true,
                //searching: false,
                searching: true,
                ajax: {
                    "url": api_endpoints.approvals_paginated_list + '?format=datatables&target_email_user_id=' + vm.target_email_user_id,
                    //"url": api_endpoints.approvals,
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        //d.filter_approval_type = vm.approvalTypesToDisplay.join(',');
                        d.filter_approval_type = vm.approvalTypeFilter.join(',');
                        d.show_expired_surrendered = vm.show_expired_surrendered;
                        d.external_waiting_list = vm.externalWaitingList;
                        d.filter_status = vm.filterStatus;
                        d.filter_approval_type2 = vm.filterApprovalType;
                        d.filter_mooring_bay_id = vm.filterMooringBay;
                        d.filter_holder_id = vm.filterHolder;
                        d.max_vessel_length = vm.maxVesselLength;
                        d.max_vessel_draft = vm.maxVesselDraft;
                        d.is_internal = vm.is_internal;
                    }
                },
                //dom: 'frt', //'lBfrtip',
                dom: 'lBfrtip',
                buttons: buttons,
                columns: selectedColumns,
                processing: true,
                initComplete: function() {
                    console.log('in initComplete')
                },
            }
        },
        offerMooringLicenceKey: function() {
            return 'offer_mooring_licence_' + this.selectedWaitingListAllocationId + '_' + this.uuid;
        },

    },
    methods: {
        sendData: function(params){
            console.log(params)
            let vm = this
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.approvals, params.approval_id + '/request_new_stickers'), params).then(
                res => {
                    helpers.post_and_redirect('/sticker_replacement_fee/', {'csrfmiddlewaretoken' : vm.csrf_token, 'data': JSON.stringify(res.body)});
                },
                err => {
                    console.log(err)
                }
            )
        },
        fetchProfile: function(){
            let vm = this;
            Vue.http.get(api_endpoints.profile).then((response) => {
                vm.profile = response.body

            },(error) => {
                console.log(error);

            })
        },
        /*
        check_assessor: function(proposal){
            let vm = this;
            //console.log(proposal.id, proposal.can_approver_reissue);
            var assessor = proposal.allowed_assessors.filter(function(elem){
                    return(elem.id==vm.profile.id)

                });

            if (assessor.length > 0){
                //console.log(proposal.id, assessor)
                return true;
            }
            else
                return false;

            return false;
        },
        */

        offerMooringLicence: function(id){
            console.log('offerMooringLicence')
            console.log(id)
            this.selectedWaitingListAllocationId = parseInt(id);
            this.uuid++;
            this.$nextTick(() => {
                this.$refs.offer_mooring_licence.isModalOpen = true;
            });
        },
        refreshFromResponseApprovalModify: function(){
            this.$refs.approvals_datatable.vmDataTable.ajax.reload();
        },
        refreshFromResponse: async function(lodgementNumber){
            console.log("refreshFromResponse");
            await swal({
                title: "Saved",
                text: 'Mooring Licence Application ' + lodgementNumber + ' has been created',
                type:'success'
            });
            await this.$refs.approvals_datatable.vmDataTable.ajax.reload();
        },
        addEventListeners: function(){
            let vm = this;
            //Internal Action shortcut listeners
            let table = vm.$refs.approvals_datatable.vmDataTable
            table.on('processing.dt', function(e) {
            })
            table.on('click', 'a[data-offer]', async function(e) {
                e.preventDefault();
                var id = $(this).attr('data-offer');
                vm.mooringBayId = parseInt($(this).attr('data-mooring-bay'));
                await vm.offerMooringLicence(id);
            }).on('responsive-display.dt', function () {
                var tablePopover = $(this).find('[data-toggle="popover"]');
                if (tablePopover.length > 0) {
                    tablePopover.popover();
                    // the next line prevents from scrolling up to the top after clicking on the popover.
                    $(tablePopover).on('click', function (e) {
                        e.preventDefault();
                        return true;
                    });
                }
            }).on('draw.dt', function () {
                var tablePopover = $(this).find('[data-toggle="popover"]');
                if (tablePopover.length > 0) {
                    tablePopover.popover();
                    // the next line prevents from scrolling up to the top after clicking on the popover.
                    $(tablePopover).on('click', function (e) {
                        e.preventDefault();
                        return true;
                    });
                }
            });
            $('#maxVesselLength').on("blur", async function(e) {
                vm.$nextTick(() => {
                    vm.$refs.approvals_datatable.vmDataTable.ajax.reload();
                    /*
                    if (vm.maxVesselLength) {
                        vm.$refs.approvals_datatable.vmDataTable.ajax.reload();
                    }
                    */
                });
            });
            $('#maxVesselDraft').on("blur", async function(e) {
                vm.$nextTick(() => {
                    vm.$refs.approvals_datatable.vmDataTable.ajax.reload();
                    /*
                    if (vm.maxVesselDraft) {
                        vm.$refs.approvals_datatable.vmDataTable.ajax.reload();
                    }
                    */
                });
            });
            // Internal Reissue listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-reissue-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-reissue-approval');
                vm.reissueApproval(id);
            });

            //Internal Cancel listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-cancel-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-cancel-approval');
                vm.cancelApproval(id);
            });

            //Internal Suspend listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-suspend-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-suspend-approval');
                vm.suspendApproval(id);
            });

            // Internal Reinstate listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-reinstate-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-reinstate-approval');
                vm.reinstateApproval(id);
            });

            //Internal/ External Surrender listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-surrender-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-surrender-approval');
                vm.surrenderApproval(id);
            });

            //External Request New Sticker listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-request-new-sticker]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-request-new-sticker');
                vm.requestNewSticker(id);
            });

            // External renewal listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-renew-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-renew-approval');
                vm.renewApproval(id);
            });

            // External amend listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-amend-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-amend-approval');
                vm.amendApproval(id);
            });

            // Internal history listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-history-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-history-approval');
                vm.approvalHistory(id);
            });

        },
        fetchFilterLists: async function(){
            // Status values
            const statusRes = await this.$http.get(api_endpoints.approval_statuses_dict);
            for (let s of statusRes.body) {
                if (this.wlaDash && !(['extended', 'awaiting_payment', 'approved'].includes(s.code))) {
                    this.statusValues.push(s);
                //} else if (!(['extended', 'awaiting_payment', 'offered', 'approved'].includes(s.code))) {
                } else if (!(['extended', 'awaiting_payment', 'offered', 'approved'].includes(s.code))) {
                    this.statusValues.push(s);
                }
            }
            // Approval types
            const approvalRes = await this.$http.get(api_endpoints.approval_types_dict + '?include_codes=' + this.approvalTypeFilter.join(','));
            for (let t of approvalRes.body) {
                if (t.code !== 'wla') {
                    this.approvalTypes.push(t);
                }
            }
            // Mooring bays
            const mooringBayRes = await this.$http.get(api_endpoints.mooring_bays);
            for (let b of mooringBayRes.body) {
                this.mooringBays.push(b);
            }
            /*
            // Holder list
            const holderListRes = await this.$http.get(api_endpoints.holder_list);
            for (let h of holderListRes.body) {
                this.holderList.push(h);
            }
            */
        },
        reissueApproval:function (proposal_id) {
            let vm = this;
            let new_status = 'with_assessor'
            let data = {'status': new_status}
            swal({
                title: "Reissue Approval",
                text: "Are you sure you want to reissue this approval?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Reissue approval',
                //confirmButtonColor:'#d9534f'
            }).then(() => {
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal,(proposal_id+'/reissue_approval')),JSON.stringify(data),{
                emulateJSON:true,
                })
                .then((response) => {

                    vm.$router.push({
                    name:"internal-proposal",
                    params:{proposal_id:proposal_id}
                    });
                }, (error) => {
                    console.log(error);
                    swal({
                    title: "Reissue Approval",
                    text: error.body,
                    type: "error",
                    })
                });
            },(error) => {

            });
        },

        reinstateApproval:function (approval_id) {
            let vm = this;
            let status= 'with_approver'
            //let data = {'status': status}
            swal({
                title: "Reinstate Approval",
                text: "Are you sure you want to reinstate this approval?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Reinstate approval',
                //confirmButtonColor:'#d9534f'
            }).then(() => {
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.approvals,(approval_id+'/approval_reinstate')),{

                })
                .then((response) => {
                    swal(
                        'Reinstate',
                        'Your approval has been reinstated',
                        'success'
                    )
                    vm.$refs.approvals_datatable.vmDataTable.ajax.reload();

                }, (error) => {
                    console.log(error);
                    swal({
                    title: "Reinstate Approval",
                    text: error.body,
                    type: "error",
                    })
                });
            },(error) => {

            });
        },
        cancelApproval: function(approval_id){
            this.$refs.approval_cancellation.approval_id = approval_id;
            this.$refs.approval_cancellation.isModalOpen = true;
        },

        suspendApproval: function(approval_id){
            this.$refs.approval_suspension.approval = {};
            this.$refs.approval_suspension.approval_id = approval_id;
            this.$refs.approval_suspension.isModalOpen = true;
        },

        surrenderApproval: function(approval_id){
            this.$refs.approval_surrender.approval_id = approval_id;
            this.$refs.approval_surrender.isModalOpen = true;
        },
        requestNewSticker: function(approval_id){
            this.$refs.request_new_sticker_modal.approval_id = approval_id
            this.$refs.request_new_sticker_modal.isModalOpen = true
        },
        approvalHistory: function(id){
            this.approvalHistoryId = parseInt(id);
            this.uuid++;
            this.$nextTick(() => {
                this.$refs.approval_history.isModalOpen = true;
            });
        },

        renewApproval:function (proposal_id) {
            let vm = this;
            let status= 'with_approver'
            //let data = {'status': status}
            swal({
                title: "Renew Approval",
                text: "Are you sure you want to renew this approval?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Renew approval',
                //confirmButtonColor:'#d9534f'
            }).then(() => {
                //vm.$http.get(helpers.add_endpoint_json(api_endpoints.proposal,(proposal_id+'/renew_approval')),{
                //vm.$http.get(helpers.add_endpoint_json(api_endpoints.proposal,(proposal_id+'/renew_amend_approval_wrapper')), {
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal,(proposal_id+'/renew_amend_approval_wrapper')) + '?debug=' + vm.debug + '&type=renew', {

                })
                .then((response) => {
                    vm.$router.push({
                        name:"draft_proposal",
                        params:{proposal_id: response.body.id}
                   });

                }, (error) => {
                    console.log(error);
                    swal({
                    title: "Renew Approval",
                    text: error.body,
                    type: "error",
                    })
                });
            },(error) => {

            });
        },

        amendApproval:function (proposal_id) {
            let vm = this;
            swal({
                title: "Amend Approval",
                text: "Are you sure you want to amend this approval?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Amend approval',
                //confirmButtonColor:'#d9534f'
            }).then(() => {
                //vm.$http.get(helpers.add_endpoint_json(api_endpoints.proposal,(proposal_id+'/renew_amend_approval_wrapper')),{
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal,(proposal_id+'/renew_amend_approval_wrapper')) + '?debug=' + vm.debug + '&type=amend', {

                })
                .then((response) => {
                   vm.$router.push({
                        name:"draft_proposal",
                        params:{proposal_id: response.body.id}
                   });

                }, (error) => {
                    console.log(error);
                    swal({
                    title: "Amend Approval",
                    text: error.body,
                    type: "error",
                    })

                });
            },(error) => {

            });
        },


    },
    created: async function(){
        await this.fetchFilterLists();
        await this.fetchProfile();
    },
    mounted: function(){
        this.$nextTick(() => {
            this.addEventListeners();
        });
    }
}
</script>
