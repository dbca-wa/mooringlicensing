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
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import OfferMooringLicence from '@/components/internal/approvals/offer_mooring_licence.vue'
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
    },
    data() {
        let vm = this;
        return {
            datatable_id: 'waiting_lists-datatable-' + vm._uid,
            //approvalTypesToDisplay: ['wla'],
            show_expired_surrendered: false,
            selectedWaitingListAllocationId: null,
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
        }
    },
    components:{
        datatable,
        OfferMooringLicence,
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
                    'Action'
                ]
            } else if (this.is_external) {
                return [
                    'Id',
                    'Number',
                    'Type',
                    'Sticker number',
                    'Status',
                    'Issue Date',
                    'Expiry Date',
                    'Vessel',
                    'Action',
                    'Mooring Licence Vessels',
                    'Authorised User Permit Moorings',
                ]
            } else if (this.is_internal && this.wlaDash) {
                return [
                    'Id',
                    'Number',
                    'Holder',
                    'Status',
                    //'Mooring area',
                    'Bay',
                    'Allocation number in bay',
                    'Action',
                    'Issue Date',
                    'Expiry Date',
                    'Vessel length',
                    'Vessel draft',
                    'Mooring Licence Applications',
                ]
            } else if (this.is_internal) {
                return [
                    'Id',
                    'Number',
                    'Type',
                    'Sticker Number',
                    'Holder',
                    'Status',
                    'Issue Date',
                    'Expiry Date',
                    'Approval letter',
                    'Action',
                    'Mooring Licence Vessels',
                    'Authorised User Permit Moorings',
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
                            return full.lodgement_number
                        }
                    }
        },
        /*
        columnBay: function() {
            return {
                        // 3. Bay
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return 'not implemented'
                        }
                    }
        },
        */
        columnApplicationNumberInBay: function() {
            return {
                        // 4. Application number in Bay
                        data: "id",
                        orderable: true,
                        searchable: true,
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
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.status
                        }
                    }
        },
        columnVesselRegistration: function() {
            return {
                        // 6. Vessel Registration
                        data: "id",
                        orderable: true,
                        searchable: true,
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
                        searchable: true,
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
                        searchable: true,
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
                        searchable: true,
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
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            let links = '';
                            if (vm.is_internal && vm.wlaDash) {
                                links += full.offer_link;
                            } else if (vm.is_external && full.can_reissue) {
                                // approval has no view
                                //links +=  `<a href='/external/approval/${full.id}'>View</a><br/>`;
                                if(full.can_action){
                                    links +=  `<a href='#${full.id}' data-surrender-approval='${full.id}'>Surrender</a><br/>`;
                                    if(full.amend_or_renew === 'amend'){
                                       links +=  `<a href='#${full.id}' data-amend-approval='${full.current_proposal_id}'>Amend</a><br/>`;
                                   }
                                }
                                if(full.amend_or_renew === 'renew'){
                                //if(full.renewal_document && full.renewal_sent && full.can_renew) {
                                    links +=  `<a href='#${full.id}' data-renew-approval='${full.current_proposal_id}'>Renew</a><br/>`;
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
                        searchable: true,
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
                        }
                    }
        },
        columnPreferredMooringBay: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: true,
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
                        searchable: true,
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
                        searchable: true,
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
                        searchable: true,
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
                        searchable: true,
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
                            //return full.vessel_draft;
                            return '';
                        }
                    }
        },
        columnApprovalLetter: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            //return full.vessel_draft;
                            return '';
                        }
                    }
        },
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
                ]
            } else if (this.is_external) {
                selectedColumns = [
                    vm.columnId,
                    vm.columnLodgementNumber,
                    vm.columnApprovalType,
                    vm.columnStickerNumber,
                    vm.columnStatus,
                    vm.columnIssueDate,
                    vm.columnExpiryDate,
                    vm.columnVesselRegistration,
                    vm.columnAction,
                    vm.columnMooringLicenceVessels,
                    vm.columnAuthorisedUserMoorings,
                ]
            } else if (vm.is_internal && this.wlaDash) {
                selectedColumns = [
                    vm.columnId,
                    vm.columnLodgementNumber,
                    vm.columnHolder,
                    vm.columnStatus,
                    vm.columnPreferredMooringBay,
                    vm.columnAllocationNumberInBay,
                    vm.columnAction,
                    vm.columnIssueDate,
                    vm.columnExpiryDate,
                    vm.columnVesselLength,
                    vm.columnVesselDraft,
                    vm.columnRiaGeneratedProposals,
                ]
            } else if (vm.is_internal) {
                selectedColumns = [
                    vm.columnId,
                    vm.columnLodgementNumber,
                    vm.columnApprovalType,
                    vm.columnStickerNumber,
                    vm.columnHolder,
                    vm.columnStatus,
                    vm.columnIssueDate,
                    vm.columnExpiryDate,
                    vm.columnApprovalLetter,
                    vm.columnAction,
                    vm.columnMooringLicenceVessels,
                    vm.columnAuthorisedUserMoorings,
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
                    "url": api_endpoints.approvals_paginated_list + '?format=datatables',
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        //d.filter_approval_type = vm.approvalTypesToDisplay.join(',');
                        d.filter_approval_type = vm.approvalTypeFilter.join(',');
                        d.show_expired_surrendered = vm.show_expired_surrendered;
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
                buttons:[
                    //{
                    //    extend: 'excel',
                    //    exportOptions: {
                    //        columns: ':visible'
                    //    }
                    //},
                    //{
                    //    extend: 'csv',
                    //    exportOptions: {
                    //        columns: ':visible'
                    //    }
                    //},
                ],
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
        offerMooringLicence: function(id){
            console.log('offerMooringLicence')
            console.log(id)
            this.selectedWaitingListAllocationId = parseInt(id);
            this.uuid++;
            this.$nextTick(() => {
                this.$refs.offer_mooring_licence.isModalOpen = true;
            });
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

            //Internal/ External Surrender listener
            vm.$refs.approvals_datatable.vmDataTable.on('click', 'a[data-surrender-approval]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-surrender-approval');
                vm.surrenderApproval(id);
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

        surrenderApproval: function(approval_id){

            this.$refs.approval_surrender.approval_id = approval_id;
            this.$refs.approval_surrender.isModalOpen = true;
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
                vm.$http.get(helpers.add_endpoint_json(api_endpoints.proposal,(proposal_id+'/renew_amend_approval_wrapper')),{

                })
                .then((response) => {
                   let proposal = {}
                   proposal = response.body
                   vm.$router.push({
                    name:"draft_proposal",
                    params:{proposal_id: proposal.id}
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
                vm.$http.get(helpers.add_endpoint_json(api_endpoints.proposal,(proposal_id+'/renew_amend_approval_wrapper')),{

                })
                .then((response) => {
                   let proposal = {}
                   proposal = response.body
                   vm.$router.push({
                    name:"draft_proposal",
                    params:{proposal_id: proposal.id}
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
    },
    mounted: function(){
        this.$nextTick(() => {
            this.addEventListeners();
        });
    }
}
</script>
