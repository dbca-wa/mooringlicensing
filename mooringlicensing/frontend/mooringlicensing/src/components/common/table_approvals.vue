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
                    </div>
                </div>
                <div class="col-md-2">
                    <div class="form-group">
                        <label for="">Max Vessel Draft:</label>
                        <input class="form-control" type="number" v-model="maxVesselDraft" id="maxVesselDraft"/>
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
        <ApprovalExtension ref="approval_extension"  @refreshFromResponse="refreshFromResponseApprovalModify"></ApprovalExtension>
        <ApprovalSurrender ref="approval_surrender"  @refreshFromResponse="refreshFromResponseApprovalModify"></ApprovalSurrender>
        <div v-if="approvalHistoryId">
            <ApprovalHistory
                ref="approval_history"
                :key="approvalHistoryId"
                :approvalId="approvalHistoryId"
            />
        </div>
        <CreateNewStickerModal
            ref="create_new_sticker_modal"
            :is_internal="is_internal"
            @sendData="sendDataForCreateNewSticker"
        />
        <RequestNewStickerModal
            ref="request_new_sticker_modal"
            :is_internal="is_internal"
            @sendData="sendDataForNewSticker"
        />
        <RequestStickerAddressModal
            ref="request_sticker_address_modal"
            :is_internal="is_internal"
            @sendData="sendDataForStickerAddress"
        />
        <SwapMooringsModal
            ref="swap_moorings_modal"
            :is_internal="is_internal"
            @sendData="sendDataForSwapMoorings"
        />
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import OfferMooringLicence from '@/components/internal/approvals/offer_mooring_licence.vue'
import ApprovalCancellation from '../internal/approvals/approval_cancellation.vue'
import ApprovalSuspension from '../internal/approvals/approval_suspension.vue'
import ApprovalExtension from '../internal/approvals/approval_extension.vue'
import ApprovalSurrender from '../internal/approvals/approval_surrender.vue'
import ApprovalHistory from '../internal/approvals/approval_history.vue'
import CreateNewStickerModal from "@/components/common/create_new_sticker_modal.vue"
import RequestNewStickerModal from "@/components/common/request_new_sticker_modal.vue"
import RequestStickerAddressModal from "@/components/common/request_sticker_address_modal.vue"
import SwapMooringsModal from "@/components/common/swap_moorings_modal.vue"
import Vue from 'vue'
import { api_endpoints, helpers }from '@/utils/hooks'

export default {
    name: 'TableApprovals',
    props: {
        approvalTypeFilter: {
            type: Array,
            required: true,
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
        ApprovalExtension,
        ApprovalHistory,
        CreateNewStickerModal,
        RequestNewStickerModal,
        SwapMooringsModal,
        RequestStickerAddressModal,
    },
    watch: {
        show_expired_surrendered: function(value){
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
                    'Allocation number in bay',
                    'Status',
                    'Vessel Rego',
                    'Vessel Name',
                    'Issue Date',
                    'Start Date',
                    'Expiry Date',
                    'Action',
                    'Grace period end date',
                    'Approval letter',
                ]
            } else if (this.is_external) {
                return [
                    'Id',
                    'Number',
                    'Type',
                    'Sticker Number/s',
                    'Sticker Mailed Date',
                    'Status',
                    'Issue Date',
                    'Start Date',
                    'Expiry Date',
                    'Vessel Rego',
                    'Mooring',
                    'Action',
                    'Grace Period End Date',
                    'Approval Letter',
                ]
            } else if (this.is_internal && this.wlaDash) {
                return [
                    'Id',
                    'Number',
                    'Holder',
                    'Status',
                    'Status 2',
                    'Bay',
                    'Allocation number in bay',
                    'Action',
                    'Issue Date',
                    'Start Date',
                    'Expiry Date',
                    'Approval letter',
                    'Vessel length',
                    'Vessel draft',
                    'Vessel Rego',
                    'Grace period end date',
                    'Mooring Site Licence Applications',
                    'Mooring Offered',
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
                    'Mooring',
                    'Issue Date',
                    'Start Date',
                    'Expiry Date',
                    'Approval letter',
                    'Vessel Rego',
                    'Grace period end date',
                    'Action',
                ]
            }
        },
        columnId: function() {
            return {
                        // 1. ID
                        data: "id",
                        orderable: true,
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
                        },
                        name: "current_proposal__lodgement_number"
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
                        },
                        name: "status",
                    }
        },
        columnMooring: function(){
            let vm = this
            return {
                data: "id",
                orderable: false,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    let links = ''
                    for (let mooring of full.moorings){
                        if (vm.is_internal){
                            links += `<a href='/internal/moorings/${mooring.id}' target='_blank'>${mooring.mooring_name}</a><br/>`
                        } else {
                            links += `${mooring.mooring_name}<br/>`
                        }
                    }
                    return links
                },
                name: "moorings__name, mooringlicence__mooring__name",
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
                        },
                        name: "internal_status",
                    }
        },
        columnVesselName: function() {
            return {
                        // 7. Vessel Name
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.vessel_name;
                        },
                        name: "current_proposal__vessel_details__vessel_name"
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
                        },
                        name: "issue_date",
                    }
        },
        columnStartDate: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.start_date_str;
                        },
                        name: "start_date",
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
                        },
                        name: "expiry_date",
                    }
        },
        columnAction: function() {
            let vm = this;
            return {
                        // 10. Action
                        data: "id",
                        orderable: false,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            let links = '';
                            if (vm.is_external && full.can_reissue) {
                                if(full.can_action){
                                    if(full.amend_or_renew === 'amend'){
                                       links +=  `<a href='#${full.id}' data-amend-approval='${full.current_proposal_id}' data-approval-type-name='${full.approval_type_dict.description}'>Amend</a><br/>`;
                                    }
                                    if(full.amend_or_renew === 'renew'){
                                        links +=  `<a href='#${full.id}' data-renew-approval='${full.current_proposal_id}' data-approval-type-name='${full.approval_type_dict.description}'>Renew</a><br/>`;
                                    }
                                    links +=  `<a href='#${full.id}' data-surrender-approval='${full.id}' data-approval-type-name='${full.approval_type_dict.description}'>Surrender</a><br/>`;
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
                                if (full.allowed_assessors_user) {
                                    if(full.can_reissue && full.can_action){
                                        links +=  `<a href='#${full.id}' data-cancel-approval='${full.id}'>Cancel</a><br/>`
                                        links +=  `<a href='#${full.id}' data-surrender-approval='${full.id}' data-approval-type-name='${full.approval_type_dict.description}'>Surrender</a><br/>`
                                    }
                                    if(full.status == 'Current' && full.can_action){
                                        links +=  `<a href='#${full.id}' data-suspend-approval='${full.id}'>Suspend</a><br/>`
                                    }
                                    if(full.can_reinstate){
                                        links +=  `<a href='#${full.id}' data-reinstate-approval='${full.id}'>Reinstate</a><br/>`
                                    }
                                    if(full.can_extend){
                                        links +=  `<a href='#${full.id}' data-extend-approval='${full.id}'>Extend Expiry</a><br/>`
                                    }
                                }
                                if(full.renewal_document && full.renewal_sent){
                                    links += `<a href='${full.renewal_document}' target='_blank'>Renewal Notice</a><br/>`
                                }
                                if(full.approval_type_dict && full.approval_type_dict.code == 'ml'){
                                    if(full.mooring_swappable)
                                        links += `<a href='#${full.id}' data-swap-moorings-approval='${full.id}' data-swap-moorings-approval-lodgement-number='${full.lodgement_number}'>Swap moorings</a><br/>`
                                }
                            }
                            if (full.approval_type_dict.code != 'wla' && full.status == 'Current') {

                                if (full.is_missing_sticker) {
                                    if (vm.is_internal) {
                                        links += `<a href='#${full.id}' data-create-new-sticker='${full.id}' data-missing-sticker-message='${full.missing_sticker_message}'>Create New Sticker</a><br/>`
                                    }
                                } else {
                                    links += `<a href='#${full.id}' data-request-new-sticker='${full.id}'>Request New Sticker</a><br/>`
                                    links += `<a href='#${full.id}' data-request-sticker-address='${full.id}'>Update Sticker Address</a><br/>`
                                }
                            }

                            return links;
                        }
                    }
        },
        columnMooringOffered: function(){
            let vm = this;
            return {
                // 10. Action
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    if (full.mooring_offered.id){
                        return `<a href='/internal/moorings/${full.mooring_offered.id}' target='_blank'>${full.mooring_offered.name}</a>`
                    }
                    return '---'
                }
            }
        },
        columnRiaGeneratedProposals: function() {
            let vm = this;
            return {
                // 10. Action
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    return full.ria_generated_proposals
                }
            }
        },
        columnHolder: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.holder;
                        },
                        name: 'current_proposal__proposal_applicant'
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
                        },
                        name: "current_proposal__preferred_bay__name"
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
                        },
                        name: "wla_order",
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
                        },
                        name: "current_proposal__vessel_details__vessel_length"
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
                        },
                        name: "current_proposal__vessel_details__vessel_draft"
                    }
        },
        columnApprovalType: function() {
            return {
                        data: "id",
                        orderable: false,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
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
                        orderable: false,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            let ret_str = ''
                            for (let sticker of full.stickers){
                                ret_str += sticker.number + ' (' + sticker.vessel_rego_no + ')<br />'
                            }
                            return ret_str
                        },
                        name: 'stickers__number',
                    }
        },
        columnStickerMailedDate: function() {
            return {
                        data: "id",
                        orderable: false,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            let ret_str = ''
                            for (let sticker of full.stickers){
                                if (sticker.mailing_date){
                                    ret_str += moment(sticker.mailing_date).format('DD/MM/YYYY') + '<br />'
                                } else {
                                    ret_str += ''
                                }
                            }
                            return ret_str
                        },
                    }
        },
        columnApprovalLetter: function() {
            return {
                        data: "id",
                        orderable: false,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            let approval_letter_name = ''
                            if (full.approval_type_dict.code === 'aup'){
                                approval_letter_name = 'Authorised User Permit'
                            } else if (full.approval_type_dict.code === 'aap'){
                                approval_letter_name = 'Annual Admission Permit'
                            } else if (full.approval_type_dict.code === 'ml'){
                                approval_letter_name = 'Mooring Site Licence'
                            } else if (full.approval_type_dict.code === 'wla'){
                                approval_letter_name = 'Waiting List Allocation'
                            }
                            let ret_elems = `<div><a href='${full.licence_document}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> ${approval_letter_name}</a></div>`;
                            if (full.authorised_user_summary_document){
                                ret_elems += `<div><a href='${full.authorised_user_summary_document}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> List of Authorised Users</a></div>`;
                            }

                            return ret_elems
                        }
                    }
        },
        columnGracePeriod: function(){
            return {
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    if (full.status === 'Current' && full.grace_period_details.grace_period_end_date){
                        return moment(full.grace_period_details.grace_period_end_date).format('DD/MM/YYYY') + ' (' + full.grace_period_details.days_left + ' days left)'
                    }
                    return 'N/A'
                }
            }
        },
        columnVesselRegos: function() {
            return {
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    let ret = ''
                    for (let rego of full.vessel_regos){
                        ret += rego + '<br/>'
                    }
                    return ret
                },
                name: "current_proposal__vessel_details__vessel__rego_no"
            }
        },
        datatable_options: function() {
            let vm = this;
            let selectedColumns = [];
            if (vm.is_external && this.wlaDash) {
                selectedColumns = [
                    vm.columnId,
                    vm.columnLodgementNumber,
                    vm.columnPreferredMooringBay,
                    vm.columnAllocationNumberInBay,
                    vm.columnStatus,
                    vm.columnVesselRegos,
                    vm.columnVesselName,
                    vm.columnIssueDate,
                    vm.columnStartDate,
                    vm.columnExpiryDate,
                    vm.columnAction,
                    vm.columnGracePeriod,
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
                    vm.columnStartDate,
                    vm.columnExpiryDate,
                    vm.columnVesselRegos,
                    vm.columnMooring,
                    vm.columnAction,
                    vm.columnGracePeriod,
                    vm.columnApprovalLetter,
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
                    vm.columnStartDate,
                    vm.columnExpiryDate,
                    vm.columnApprovalLetter,
                    vm.columnVesselLength,
                    vm.columnVesselDraft,
                    vm.columnVesselRegos,
                    vm.columnGracePeriod,
                    vm.columnRiaGeneratedProposals,
                    vm.columnMooringOffered,
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
                    vm.columnMooring,
                    vm.columnIssueDate,
                    vm.columnStartDate,
                    vm.columnExpiryDate,
                    vm.columnApprovalLetter,
                    vm.columnVesselRegos,
                    vm.columnGracePeriod,
                    vm.columnAction,
                ]
            }
            let buttons = []
            if (vm.is_internal){
                buttons = [
                    {
                        extend: 'excel',
                    },
                    {
                        extend: 'csv',
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
                lengthMenu: [ [10, 25, 50, 100], [10, 25, 50, 100] ],
                searching: true,
                order: [0,'desc'],
                ajax: {
                    "url": api_endpoints.approvals_paginated_list + '/list2/?format=datatables&target_email_user_id=' + vm.target_email_user_id,
                    "dataSrc": 'data',
                    "type": 'POST',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        d.filter_approval_type = vm.approvalTypeFilter.join(',');
                        d.show_expired_surrendered = vm.show_expired_surrendered;
                        d.external_waiting_list = vm.externalWaitingList;
                        d.filter_status = vm.filterStatus;
                        d.filter_approval_type2 = vm.filterApprovalType;
                        d.filter_mooring_bay_id = vm.filterMooringBay;
                        d.filter_holder_id = vm.filterHolder;
                        d.max_vessel_length = vm.maxVesselLength;
                        d.max_vessel_draft = vm.maxVesselDraft;
                        d.csrfmiddlewaretoken = vm.csrf_token;
                        //only use columns necessary for filtering and ordering
                        let keepCols = []
                        let originalCols = d.columns
                        d.columns.forEach((value, index) => {
                            if (value.searchable || value.orderable) {
                                keepCols.push(d.columns[index])
                            }
                        });
                        d.columns = keepCols;

                        //adjust order
                        let nameIndexDict = {}
                        d.columns.forEach((value, index) => {
                                nameIndexDict[value.name] = index;
                            }
                        )
                        let originalNameIndexDict = {}
                        originalCols.forEach((value, index) => {
                                originalNameIndexDict[value.name] = index;
                            }
                        )
                        let newOrder = JSON.parse(JSON.stringify(d.order));
                        d.order.forEach((o_value, o_index) => {
                            Object.entries(originalNameIndexDict).forEach(([key,value]) => {
                                if (o_value.column == value) {
                                    let name = key;
                                    let new_index = nameIndexDict[name];
                                    newOrder[o_index].column = new_index;
                                }
                            })    
                        })
                        d.order = newOrder;
                    }
                },
                dom: 'lBfrtip',
                buttons: buttons,
                columns: selectedColumns,
                processing: true,
                initComplete: function() {

                },
                createdRow: function(row, data, dataIndex){
                    if (data.status === 'Current'){
                        if (data.grace_period_details && data.grace_period_details.days_left){
                            let colour_code = '#ff6961'
                            if (data.grace_period_details.days_left > 0){
                                colour_code = '#ffa07a'
                            }
                            $(row).css({
                                'background-color': colour_code
                            })
                        }
                    }
                }
            }
        },
        offerMooringLicenceKey: function() {
            return 'offer_mooring_licence_' + this.selectedWaitingListAllocationId + '_' + this.uuid;
        },

    },
    methods: {
        sendDataForSwapMoorings: function(params){
            console.log('in sendDataForSwapMoorings')
            let vm = this
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.approvals, params.approval_id + '/swap_moorings'), params).then(
                res => {
                   vm.$router.push('/internal/')
                },
                err => {
                    vm.$refs.swap_moorings_modal.isModalOpen = false
                    swal({
                        title: "Swap Moorings",
                        text: err.body,
                        type: "error",
                    })
                }
            )
        },
        sendDataForCreateNewSticker: function(params){
            let vm = this
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.approvals, params.approval_id + '/create_new_sticker'), params).then(
                res => {
                    helpers.post_and_redirect('/sticker_replacement_fee/', {'csrfmiddlewaretoken' : vm.csrf_token, 'data': JSON.stringify(res.body)});
                },
                err => {
                    vm.$refs.create_new_sticker_modal.processing = false
                    vm.$refs.create_new_sticker_modal.isModalOpen = false
                    vm.$refs.create_new_sticker_modal.replacementFee = false
                    vm.$refs.create_new_sticker_modal.missing_sticker_message = ""
                    swal({
                        title: "Request New Sticker",
                        text: err.body,
                        type: "error",
                    })
                }
            )  
        },
        sendDataForNewSticker: function(params){
            let vm = this
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.approvals, params.approval_id + '/request_new_stickers'), params).then(
                res => {
                    helpers.post_and_redirect('/sticker_replacement_fee/', {'csrfmiddlewaretoken' : vm.csrf_token, 'data': JSON.stringify(res.body)});
                },
                err => {
                    vm.$refs.request_new_sticker_modal.processing = false
                    vm.$refs.request_new_sticker_modal.isModalOpen = false
                    swal({
                        title: "Request New Sticker",
                        text: err.body,
                        type: "error",
                    })
                }
            )
        },
        sendDataForStickerAddress: function(params){
            let vm = this
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.approvals, params.approval_id + '/change_sticker_addresses'), params).then(
                res => {
                    vm.$router.go();
                },
                err => {
                    vm.$refs.request_sticker_address_modal.processing = false
                    vm.$refs.request_sticker_address_modal.isModalOpen = false
                    swal({
                        title: "Request New Sticker",
                        text: err.body,
                        type: "error",
                    })
                }
            )
        },
        fetchProfile: function(){
            let vm = this;
            Vue.http.get(api_endpoints.profile).then((response) => {
                vm.profile = response.body

            },(error) => {

            })
        },
        offerMooringLicence: function(id){
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
                text: 'Mooring Site Licence Application ' + lodgementNumber + ' has been created',
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
                });
            });
            $('#maxVesselDraft').on("blur", async function(e) {
                vm.$nextTick(() => {
                    vm.$refs.approvals_datatable.vmDataTable.ajax.reload();
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

            //Internal Extend listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-extend-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-extend-approval');
                vm.extendApproval(id);
            });


            //Internal Swap moorings listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-swap-moorings-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-swap-moorings-approval');
                var lodgement_number = $(this).attr('data-swap-moorings-approval-lodgement-number');
                vm.swapMoorings(id, lodgement_number);
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
                let approval_type_name = $(this).attr('data-approval-type-name');
                vm.surrenderApproval(id, approval_type_name); 
            });

            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-create-new-sticker]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-create-new-sticker');
                var message = $(this).attr('data-missing-sticker-message');
                vm.createNewSticker(id, message);
            });

            //External Request New Sticker listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-request-new-sticker]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-request-new-sticker');
                vm.requestNewSticker(id);
            });

            //External Request Sticker Address Change listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-request-sticker-address]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-request-sticker-address');
                vm.requestStickerAddress(id);
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
                let approval_type_name = $(this).attr('data-approval-type-name');
                vm.amendApproval(id, approval_type_name);
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
            for (let b of mooringBayRes.body.results) {
                this.mooringBays.push(b);
            }
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
            swal({
                title: "Reinstate Approval",
                text: "Are you sure you want to reinstate this approval?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Reinstate approval',
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
        extendApproval: function(approval_id){
            this.$refs.approval_extension.approval = {};
            this.$refs.approval_extension.approval_id = approval_id;
            this.$refs.approval_extension.isModalOpen = true;
        },
        swapMoorings: function(approval_id, lodgement_number){
            this.$refs.swap_moorings_modal.approval_id = approval_id
            this.$refs.swap_moorings_modal.approval_lodgement_number = lodgement_number
            this.$refs.swap_moorings_modal.isModalOpen = true
        },
        surrenderApproval: function(approval_id, approval_type_name){
            this.$refs.approval_surrender.approval_id = approval_id;
            this.$refs.approval_surrender.approval_type_name = approval_type_name
            this.$refs.approval_surrender.isModalOpen = true;
        },
        createNewSticker: function(approval_id, message){
            this.$refs.create_new_sticker_modal.approval_id = approval_id
            this.$refs.create_new_sticker_modal.isModalOpen = true
            this.$refs.create_new_sticker_modal.replacementFee = true
            this.$refs.create_new_sticker_modal.missing_sticker_message = message
        },
        requestNewSticker: function(approval_id){
            this.$refs.request_new_sticker_modal.approval_id = approval_id
            this.$refs.request_new_sticker_modal.isModalOpen = true
        },
        requestStickerAddress: function(approval_id){
            this.$refs.request_sticker_address_modal.approval_id = approval_id
            this.$refs.request_sticker_address_modal.isModalOpen = true
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
            swal({
                title: "Renew Approval",
                text: "Are you sure you want to renew this approval?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Renew approval',
            }).then(() => {
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal,(proposal_id+'/renew_amend_approval_wrapper')) + '?type=renew', {

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

        amendApproval:function (proposal_id, approval_type_name) {
            let vm = this;
            swal({
                title: "Amend " + approval_type_name,
                text: "Are you sure you want to amend this " + approval_type_name + "?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Amend',
            }).then(() => {
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal,(proposal_id+'/renew_amend_approval_wrapper')) + '?type=amend', {

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