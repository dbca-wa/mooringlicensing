<template>
    <div>
        <div class="row">
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Permit or licence type</label>
                    <select class="form-control" v-model="filterApprovalType">
                        <option value="All">All</option>
                        <option v-for="type in approval_types" :value="type.code">{{ type.description }}</option>
                    </select>
                </div>
            </div>
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Status</label>
                    <select class="form-control" v-model="filterStickerStatus">
                        <option value="All">All</option>
                        <option v-for="sticker_status in sticker_statuses" :value="sticker_status.id">{{ sticker_status.display }}</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-12">
                <datatable
                    ref="non_exported_stickers_datatable"
                    :id="datatable_id"
                    :dtOptions="datatable_options"
                    :dtHeaders="datatable_headers"
                />
            </div>
        </div>
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import { api_endpoints, helpers } from '@/utils/hooks'
export default {
    name: 'NonExportedTableStickers',
    props: {
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
            datatable_id: 'applications-datatable-' + vm._uid,
            approvalTypesToDisplay: ['aap', 'aup', 'ml'],

            // selected values for filtering
            filterApprovalType: null,
            filterYear: null,
            filterStickerStatus: null,

            // filtering options
            approval_types: [],
            fee_seasons: [],
            sticker_statuses: [],

            sticker_details_tr_class_name: 'sticker_details',
        }
    },
    components:{
        datatable
    },
    watch: {
        filterYear: function() {
            this.$refs.non_exported_stickers_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
        },
        filterApprovalType: function() {
            this.$refs.non_exported_stickers_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
        },
        filterStickerStatus: function(){
            this.$refs.non_exported_stickers_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
        },
    },
    computed: {
        number_of_columns: function() {
            return this.datatable_headers.length
        },
        is_external: function() {
            return this.level == 'external'
        },
        is_internal: function() {
            return this.level == 'internal'
        },
        datatable_headers: function(){
            if (this.is_external){
                return []
            }
            if (this.is_internal){
                return ['id', 'Date Updated', 'Permit or Licence', 'Vessel rego', 'Holder', 'Status' ,'Action']
            }
        },
        column_id: function(){
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
        column_date_updated: function(){
            return {
                data: "date_updated",
                orderable: true,
                searchable: false,
                visible: false,
                'render': function(row, type, full){
                    return full.date_updated
                }
            }
        },
        column_vessel_rego_no: function(){
            return {
                // 2. Number
                data: "vessel_rego_no",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    // return full.vessel.rego_no
                    return '<a href="/internal/vessel/' + full.vessel.id + '" target="_blank">' + full.vessel.rego_no + '</a>'
                },
                name: 'vessel_ownership__vessel__rego_no',
            }
        },
        column_holder: function(){
            return {
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    if (full.approval){
                        return full.approval.applicant
                    } else if (full.dcv_permit) {
                        return full.dcv_permit.dcv_organisation_name
                    } else {
                        return ''
                    }
                },
                name: 'approval__current_proposal__proposal_applicant__first_name, approval__current_proposal__proposal_applicant__last_name, approval__current_proposal__proposal_applicant__email'
            }
        },
        column_permit_or_licence: function(){
            return {
                data: "approval",
                orderable: false,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    let migrated = '';
                    if (full.migrated)
                        migrated = ' (Migrated)';
                    if (full.approval){
                        return '<a href="/internal/approval/' + full.approval.id + '" target="_blank">' + full.approval.lodgement_number + migrated + '</a>'
                    } else if (full.dcv_permit) {
                        return '<span class="dcv_permit_lodgement_number">' + full.dcv_permit.lodgement_number + migrated + '</span>'
                    } else {
                        return ''
                    }

                },
                name: 'approval__lodgement_number'
            }
        },
        column_status: function(){
            let vm = this
            return {
                // 5. Status
                data: "status",
                orderable: false,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return '<span id="status_cell_contents_id_' + full.id + '">' + full.status.display + '</span>'
                },
                name: 'status'
            }
        },
        column_action: function(){
            let vm = this
            return {
                // 8. Action
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    return vm.getActionCellContents(full)
                }
            }
        },
        datatable_options: function(){
            let vm = this

            let columns = []
            let search = null
            if(vm.is_external){
                columns = []
                search = false
            }
            if(vm.is_internal){
                columns = [
                    vm.column_id,
                    vm.column_date_updated,
                    vm.column_permit_or_licence,
                    vm.column_vessel_rego_no,
                    vm.column_holder,
                    vm.column_status,
                    vm.column_action,
                ]
                search = true
            }

            return {
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                rowCallback: function (row, sticker){
                    let row_jq = $(row)
                    row_jq.attr('id', 'sticker_id_' + sticker.id)
                    row_jq.children().first().addClass(vm.td_expand_class_name)

                },
                autoWidth: true,
                responsive: true,
                serverSide: true,
                paging: true,
                lengthMenu: [ [10, 25, 50, 100], [10, 25, 50, 100] ],
                searching: search,
                ordering: true,
                order: [[1, 'desc']],  // Default order [[column_index, 'asc/desc'], ...]
                ajax: {
                    "url": api_endpoints.non_exported_stickers_paginated_list + '?format=datatables',
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        d.filter_approval_type = vm.filterApprovalType
                        d.filter_year = vm.filterYear
                        d.filter_sticker_status = vm.filterStickerStatus
                        d.level = vm.level
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
                buttons:[
                    {
                        extend: 'excel',
                    },
                    {
                        extend: 'csv',
                    },
                ],

                columns: columns,
                processing: true,
                initComplete: function() {
                    console.log('in initComplete')
                },
            }
        }
    },
    methods: {
        getActionCellContents: function(sticker){
            let links = ''

            switch(sticker.status.code){
                case 'ready':
                    links += `<a href='#${sticker.id}' oncontextmenu="return false;" data-cancel='${sticker.id}'>Cancel</a><br/>`
                    break;
                case 'not_ready_yet':
                    links += `<a href='#${sticker.id}' oncontextmenu="return false;" data-cancel='${sticker.id}'>Cancel</a><br/>`
                    break;
                case 'cancelled':
                    break;
            }
            return '<span id="action_cell_contents_id_' + sticker.id + '">' + links + '</span>'
        },
        getActionDetailTable: function(sticker){
            let thead = `<thead>
                            <tr>
                                <th scope="col">Date</th>
                                <th scope="col">User</th>
                                <th scope="col">Action</th>
                                <th scope="col">Date of Lost</th>
                                <th scope="col">Date of Returned</th>
                                <th scope="col">Reason</th>
                            </tr>
                        <thead>`
            let tbody = ''
            for (let detail of sticker.sticker_action_details){
                tbody += `<tr>
                    <td>${moment(detail.date_updated).format('DD/MM/YYYY')}</td>
                    <td>${detail.user_detail ? detail.user_detail.first_name : ''} ${detail.user_detail ? detail.user_detail.last_name : ''} </td>
                    <td>${detail.action ? detail.action : ''}</td>
                    <td>${detail.date_of_lost_sticker ? moment(detail.date_of_lost_sticker, 'YYYY-MM-DD').format('DD/MM/YYYY') : ''}</td>
                    <td>${detail.date_of_returned_sticker ? moment(detail.date_of_returned_sticker, 'YYYY-MM-DD').format('DD/MM/YYYY') : ''}</td>
                    <td>${detail.reason}</td>
                </tr>`
            }
            tbody = '<tbody>' + tbody + '</tbody>'

            let details = '<table class="table table-striped table-bordered table-sm table-sticker-details" id="table-sticker-details-' + sticker.id + '">' + thead + tbody + '</table>'
            return details
        },
        fetchFilterLists: function(){
            let vm = this;

            let include_codes = vm.approvalTypesToDisplay.join(',');

            // Application Types
            vm.$http.get(api_endpoints.approval_types_dict+'?include_codes=' + include_codes).then((response) => {
                vm.approval_types = response.body
            },(error) => {
                console.log(error);
            })

            // Years (FeeSeason)
            vm.$http.get(api_endpoints.fee_seasons_dict+'?include_codes=' + include_codes).then((response) => {
                vm.fee_seasons = response.body
            },(error) => {
                console.log(error);
            })

            // Sticker statuses
            vm.$http.get(api_endpoints.sticker_non_exported_status_dict+'?include_codes=' + include_codes).then((response) => {
                vm.sticker_statuses = response.body
            },(error) => {
                console.log(error);
            })
        },
        updateActionCell: function(sticker){
            let elem = $('#action_cell_contents_id_' + sticker.id)
            let contents = this.getActionCellContents(sticker)
            elem.fadeOut(function(){
                elem.html(contents).fadeIn()
            })

        },
        updateStatusCell: function(sticker){
            let elem = $('#status_cell_contents_id_' + sticker.id)
            elem.fadeOut(function(){
                elem.text(sticker.status.display).fadeIn()
            })
        },
        updateDetailsRow: function(sticker){
            let vm = this
            let elem = $('#action_cell_contents_id_' + sticker.id)

            // Remove details table if shown
            let tr = elem.closest('tr')
            let nextElem = tr.next()
            if(nextElem.is('tr') & nextElem.hasClass(vm.sticker_details_tr_class_name)){
                // Sticker details row is already shown.  Replace the contents.
                let td = nextElem.find("td:eq(0)")
                let table_inside = vm.getActionDetailTable(sticker)
                nextElem.fadeOut(500, function(){
                    td.html(table_inside)
                    let my_table = $('#table-sticker-details-' + sticker.id)
                    my_table.DataTable({
                        lengthChange: false,
                        searching: false,
                        autoWidth: true,
                        info: false,
                        paging: false,
                        order: [[0, 'desc']],
                    })
                    nextElem.fadeIn(1000)
                })
            }
        },
        updateRow: function(sticker){
            this.updateStatusCell(sticker)
            this.updateActionCell(sticker)
            this.updateDetailsRow(sticker)
        },
        addEventListeners: function(){
            let vm = this

            // Listener for the <a> link for replacement
            vm.$refs.non_exported_stickers_datatable.vmDataTable.on('click', 'a[data-cancel]', function(e) {
                e.preventDefault()

                // Get <a> element as jQuery object
                let a_link = $(this)
                // Get sticker id from <a> element
                let id = a_link.attr('data-cancel');

                vm.$emit("actionClicked", {"action": "cancel", "id": id})
            });
        },
    },
    created: function(){
        this.fetchFilterLists()
    },
    mounted: function(){
        let vm = this;
        this.$nextTick(() => {
            vm.addEventListeners();
        });
    }
}
</script>

<style>
.dcv_permit_lodgement_number {
    padding: 8px 10px;
}
</style>
