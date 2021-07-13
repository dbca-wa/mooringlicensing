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
                    <label for="">Year</label>
                    <select class="form-control" v-model="filterYear">
                        <option value="All">All</option>
                        <option v-for="season in fee_seasons" :value="season.id">{{ season.name }}</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-12">
                <datatable
                    ref="stickers_datatable"
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
import Vue from 'vue'
import { api_endpoints, helpers } from '@/utils/hooks'
export default {
    name: 'TableStickers',
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

            // filtering options
            approval_types: [],
            fee_seasons: [],

            sticker_details_tr_class_name: 'sticker_details',

            td_expand_class_name: 'expand-icon',
            td_collapse_class_name: 'collapse-icon',
        }
    },
    components:{
        datatable
    },
    watch: {
        filterYear: function() {
            let vm = this;
            vm.$refs.stickers_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
            //if (vm.filterApplicationStatus != 'All') {
            //    vm.$refs.stickers_datatable.vmDataTable.column('status:name').search('').draw();
            //} else {
            //    vm.$refs.stickers_datatable.vmDataTable.column('status:name').search(vm.filterApplicationStatus).draw();
            //}
        },
        filterApprovalType: function() {
            let vm = this;
            vm.$refs.stickers_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
        },
    },
    computed: {
        debug: function(){
            if (this.$route.query.debug){
                return ['true', 't', 'yes', 'y'].includes(this.$route.query.debug.toLowerCase())
            }
            return false
        },
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
                return ['id', 'Number', 'Permit or Licence', 'Date sent / printed / mailed', 'Status', 'Year', 'Action']
            }
        },
        column_id: function(){
            return {
                // 1. ID
                data: "id",
                orderable: false,
                searchable: false,
                visible: this.debug,
                'render': function(row, type, full){
                    return full.id
                }
            }
        },
        column_number: function(){
            return {
                // 2. Number
                data: "number",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.number
                },
                name: 'number',
            }
        },
        column_permit_or_licence: function(){
            return {
                data: "approval",
                orderable: true,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    return '<a href="/internal/approval/' + full.approval.id + '">' + full.approval.lodgement_number + '</a>'
                }
            }
        },
        column_printing_company: function(){
            return {
                // 4. Application Type (This corresponds to the 'ProposalType' at the backend)
                data: "id",
                orderable: true,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    let lines = `
                                 <table>
                                     <tr><td style="text-align:right;">Sent:</td><td> ${full.sent_date ? moment(full.sent_date, 'YYYY-MM-DD').format('DD/MM/YYYY') : '---'}</td></tr>
                                     <tr><td style="text-align:right;">Printed:</td><td> ${full.printing_date ? moment(full.printing_date, 'YYYY-MM-DD').format('DD/MM/YYYY') : '---'}</td></tr>
                                     <tr><td style="text-align:right;">Mailed:</td><td> ${full.mailing_date ? moment(full.mailing_date, 'YYYY-MM-DD').format('DD/MM/YYYY') : '---'}</td></tr>
                                 </table>
                                 `
                    return lines
                }
            }
        },
        column_status: function(){
            let vm = this
            return {
                // 5. Status
                data: "status",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return '<span id="status_cell_contents_id_' + full.id + '">' + full.status.display + '</span>'
                },
                name: 'status'
            }
        },
        column_year: function(){
            return {
                // 6. Lodged
                data: "id",
                orderable: true,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    if (full.fee_constructor){
                        if (full.fee_constructor.fee_season){
                            return full.fee_constructor.fee_season.name
                        }
                    }
                    return ''
                }
            }
        },
        column_action: function(){
            let vm = this
            return {
                // 8. Action
                data: "id",
                orderable: true,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    return vm.getActionCellContents(full)
                    //let links =  `<a href='#${full.id}' data-replacement='${full.id}'>Request Sticker Replacement</a><br/>`
                    //links += `<a href='#${full.id}' data-record-returned='${full.id}'>Record Returned Sticker</a><br/>`
                    //links += `<a href='#${full.id}' data-record-lost='${full.id}'>Record Sticker Lost</a><br/>`
                    //links += `<a href='#${full.id}' data-view-details='${full.id}'>Show/Hide Details</a><br/>`
                    //return '<span id="action_cell_contents_id_' + full.id + '">' + links + '</span>'
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
                    vm.column_number,
                    vm.column_permit_or_licence,
                    vm.column_printing_company,
                    vm.column_status,
                    vm.column_year,
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
                //responsive: true,
                responsive: true,
                serverSide: true,
                searching: search,
                ordering: true,
                order: [[1, 'desc']],  // Default order [[column_index, 'asc/desc'], ...]
                ajax: {
                    "url": api_endpoints.stickers_paginated_list + '?format=datatables&debug=' + vm.debug,
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        d.filter_approval_type = vm.filterApprovalType
                        d.filter_year = vm.filterYear
                        d.level = vm.level
                    }
                },
                dom: 'lBfrtip',
                buttons:['csv'],
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
            if (this.debug){
                links += `<a href='#${sticker.id}' data-replacement='${sticker.id}'>Request Sticker Replacement</a><br/>`
                links += `<a href='#${sticker.id}' data-record-lost='${sticker.id}'>Record Sticker Lost</a><br/>`
                links += `<a href='#${sticker.id}' data-record-returned='${sticker.id}'>Record Returned Sticker</a><br/>`
                //links += `<a href='#${sticker.id}' data-view-details='${sticker.id}'>Show/Hide Details</a><br/>`
                return '<span id="action_cell_contents_id_' + sticker.id + '">' + links + '</span>'
            }

            switch(sticker.status.code){
                case 'ready':
                    break
                case 'printing':
                    break
                case 'current':
                    links += `<a href='#${sticker.id}' data-replacement='${sticker.id}'>Request Sticker Replacement</a><br/>`
                    links += `<a href='#${sticker.id}' data-record-lost='${sticker.id}'>Record Sticker Lost</a><br/>`
                    break
                case 'lost':
                    break
                case 'to_be_returned':
                    links += `<a href='#${sticker.id}' data-record-returned='${sticker.id}'>Record Returned Sticker</a><br/>`
                    links += `<a href='#${sticker.id}' data-record-lost='${sticker.id}'>Record Sticker Lost</a><br/>`
                    break
                case 'returned':
                    break
                case 'expired':
                    break

            }

            //links += `<a href='#${sticker.id}' data-view-details='${sticker.id}'>Show/Hide Details</a><br/>`
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
        //discardProposal: function(proposal_id) {
        //    let vm = this;
        //    swal({
        //        title: "Discard Application",
        //        text: "Are you sure you want to discard this proposal?",
        //        type: "warning",
        //        showCancelButton: true,
        //        confirmButtonText: 'Discard Application',
        //        confirmButtonColor:'#dc3545'
        //    }).then(() => {
        //        vm.$http.delete(api_endpoints.discard_proposal(proposal_id))
        //        .then((response) => {
        //            console.log('response: ')
        //            console.log(response)
        //            swal(
        //                'Discarded',
        //                'Your proposal has been discarded',
        //                'success'
        //            )
        //            //vm.$refs.stickers_datatable.vmDataTable.ajax.reload();
        //            vm.$refs.stickers_datatable.vmDataTable.draw();
        //        }, (error) => {
        //            console.log(error);
        //        });
        //    },(error) => {

        //    });
        //},
        fetchFilterLists: function(){
            let vm = this;

            let include_codes = vm.approvalTypesToDisplay.join(',');
            //vm.$http.get(api_endpoints.approval_types_dict + '?include_codes=' + include_codes).then((response) => {

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
            vm.$refs.stickers_datatable.vmDataTable.on('click', 'a[data-replacement]', function(e) {
                e.preventDefault()

                // Get <a> element as jQuery object
                let a_link = $(this)
                // Get sticker id from <a> element
                let id = a_link.attr('data-replacement');

                vm.$emit("actionClicked", {"action": "request_replacement", "id": id})
            });

            // Listener for the <a> link for recording returned
            vm.$refs.stickers_datatable.vmDataTable.on('click', 'a[data-record-returned]', function(e) {
                e.preventDefault();

                let a_link = $(this)
                let id = a_link.attr('data-record-returned');
                vm.$emit("actionClicked", {"action": "record_returned", "id": id})
            });

            // Listener for the <a> link for recording lost
            vm.$refs.stickers_datatable.vmDataTable.on('click', 'a[data-record-lost]', function(e) {
                e.preventDefault();

                let a_link = $(this)
                let id = a_link.attr('data-record-lost');
                vm.$emit("actionClicked", {"action": "record_lost", "id": id})
            });

            // Listener for thr row
            vm.$refs.stickers_datatable.vmDataTable.on('click', 'td', function(e) {
                e.preventDefault();

                let td_link = $(this)

                if (!(td_link.hasClass(vm.td_expand_class_name) || td_link.hasClass(vm.td_collapse_class_name))){
                    return
                }

                // Get <tr> element as jQuery object
                let tr = td_link.closest('tr')

                // Retrieve sticker id from the id of the <tr>
                let tr_id = tr.attr('id')
                let sticker_id = tr_id.replace('sticker_id_', '')

                let first_td = tr.children().first()
                if(first_td.hasClass(vm.td_expand_class_name)){
                    // Expand
                    vm.$http.get(helpers.add_endpoint_json(api_endpoints.stickers, sticker_id)).then(
                        res => {
                            let sticker = res.body
                            let table_inside = vm.getActionDetailTable(sticker)
                            let details_elem = $('<tr class="' + vm.sticker_details_tr_class_name + '"><td colspan="' + vm.number_of_columns + '">' + table_inside + '</td></tr>')
                            details_elem.hide()
                            details_elem.insertAfter(tr)

                            // Make this sticker action details table Datatable
                            let my_table = $('#table-sticker-details-' + sticker.id)
                            my_table.DataTable({
                                lengthChange: false,
                                searching: false,
                                info: false,
                                paging: false,
                                order: [[0, 'desc']],
                            })

                            details_elem.fadeIn(1000)
                        },
                        err => {

                        }
                    )
                    // Change icon class name to vm.td_collapse_class_name
                    first_td.removeClass(vm.td_expand_class_name).addClass(vm.td_collapse_class_name)
                } else {
                    let nextElem = tr.next()
                    // Collapse
                    if(nextElem.is('tr') & nextElem.hasClass(vm.sticker_details_tr_class_name)){
                        // Sticker details row is already shown.  Remove it.
                        nextElem.fadeOut(500, function(){
                            nextElem.remove()
                        })
                    }
                    // Change icon class name to vm.td_expand_class_name
                    // Change icon class name to vm.td_collapse_class_name
                    first_td.removeClass(vm.td_collapse_class_name).addClass(vm.td_expand_class_name)
                }
                //////

         //       let nextElem = tr.next()
         //       if(nextElem.is('tr') & nextElem.hasClass(vm.sticker_details_tr_class_name)){
         //           // Sticker details row is already shown.  Remove it.
         //           nextElem.fadeOut(500, function(){
         //               nextElem.remove()
         //           })
         //       } else {
         //           // Display sticker details

         //           // Convert jquery <tr> element to the Datatable row object
         //           //let row = vm.$refs.stickers_datatable.vmDataTable.row(tr)
         //           //row.child('<span>AHO</span>').show()
         //           //return

         //           vm.$http.get(helpers.add_endpoint_json(api_endpoints.stickers, sticker_id)).then(
         //               res => {
         //                   let sticker = res.body
         //                   let table_inside = vm.getActionDetailTable(sticker)
         //                   let details_elem = $('<tr class="' + vm.sticker_details_tr_class_name + '"><td colspan="' + vm.number_of_columns + '">' + table_inside + '</td></tr>')
         //                   details_elem.hide()
         //                   details_elem.insertAfter(tr)

         //                   // Make this sticker action details table Datatable
         //                   let my_table = $('#table-sticker-details-' + sticker.id)
         //                   my_table.DataTable({
         //                       lengthChange: false,
         //                       searching: false,
         //                       info: false,
         //                       paging: false,
         //                       order: [[0, 'desc']],
         //                   })

         //                   details_elem.fadeIn(1000)
         //               },
         //               err => {

         //               }
         //           )
         //       }

                // Get row object as datatable API
                //var row = vm.$refs.stickers_datatable.vmDataTable.row(tr);

                //if (row.child.isShown()) {
                //    row.child.hide();
                //} else {
                //    row.child('<span>AHO</span>').show()
                //}

                //console.log(row.data()['number'])

            })
        },
    },
    created: function(){
        this.fetchFilterLists()
        //if (this.$route.query && this.$route.query.debug){
        //    this.debug = this.$route.query.debug
        //}
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
.table-sticker-details {
}
.collapse-icon {
    cursor: pointer;
}
.collapse-icon::before {
    top: 5px;
    left: 4px;
    height: 14px;
    width: 14px;
    border-radius: 14px;
    line-height: 14px;
    border: 2px solid white;
    line-height: 14px;
    content: '-';
    color: white;
    background-color: #d33333;
    display: inline-block;
    box-shadow: 0px 0px 3px #444;
    box-sizing: content-box;
    text-align: center;
    text-indent: 0 !important;
    font-family: 'Courier New', Courier monospace;
    margin: 5px;
}
.expand-icon {
    cursor: pointer;
}
.expand-icon::before {
    top: 5px;
    left: 4px;
    height: 14px;
    width: 14px;
    border-radius: 14px;
    line-height: 14px;
    border: 2px solid white;
    line-height: 14px;
    content: '+';
    color: white;
    background-color: #337ab7;
    display: inline-block;
    box-shadow: 0px 0px 3px #444;
    box-sizing: content-box;
    text-align: center;
    text-indent: 0 !important;
    font-family: 'Courier New', Courier monospace;
    margin: 5px;
}
</style>
