<template>
    <div>
        <div class="row">
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Fee Source Type</label>
                    <select class="form-control" v-model="filterFeeSourceType">
                        <option value="All">All</option>
                        <option v-for="type in fee_source_types" :value="type.code">{{ type.description }}</option>
                    </select>
                </div>
            </div>
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Status</label>
                    <select class="form-control" v-model="filterStatus">
                        <option value="All">All</option>
                        <option v-for="invoice_status in invoice_statuses" :value="invoice_status.code">{{ invoice_status.description }}</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-12">
                <datatable
                    ref="invoices_datatable"
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
    name: 'TableInvoices',
    data() {
        let vm = this;
        return {
            datatable_id: 'invoices-datatable-' + vm._uid,

            // selected values for filtering
            filterFeeSourceType: null,
            filterStatus: null,

            // filtering options
            fee_source_types: [
                {'code':'application','description':'Application'},
                {'code':'sticker_action','description':'Sticker Action'}
            ],
            invoice_statuses: [
                {'code':'settled','description':'Settled'},
                {'code':'not_settled','description':'Not Settled'},
                {'code':'voided','description':'Voided'}
            ],
        }
    },
    components:{
        datatable
    },
    watch: {
        filterFeeSourceType: function() {
            this.$refs.invoices_datatable.vmDataTable.draw();
        },
        filterStatus: function(){
            this.$refs.invoices_datatable.vmDataTable.draw();
        },
    },
    computed: {
        number_of_columns: function() {
            return this.datatable_headers.length
        },
        datatable_headers: function(){
            return ['id', 'Invoice Reference','Fee Source', 'Fee Source Type', 'Status','Created At', 'Settled At', 'Amount', 'Description']
        },
        column_id: function(){
            return {
                data: "id",
                orderable: true,
                searchable: false,
                visible: false,
                name: 'id',
                'render': function(row, type, full){
                    return full.id
                }
            }
        },
        column_reference: function(){
            return {
                data: "reference",
                orderable: true,
                searchable: true,
                visible: true,
                name: 'reference',
                'render': function(row, type, full){
                    return `<a target='_blank' href='/ledger-toolkit-api/invoice-pdf/${full.reference}'>${full.reference}</a><br/>
                            <a target='_blank' href='${full.ledger_link}'>Ledger Payment</a>`;
                }
            }
        },
        column_fee_source: function(){
            return {
                data: "fee_source",
                orderable: false,
                searchable: false,
                visible: true,
                name: 'fee_source',
                'render': function(row, type, full){
                    if (full.fee_source_type == "Application") {
                        return `<a target='_blank' href='/internal/proposal/${full.fee_source_id}'>${full.fee_source}</a>`
                    } else if (full.fee_source_type == "Sticker Action") {
                        return `<a target='_blank' href='/internal/approval/${full.fee_source_id}'>${full.fee_source}</a>`
                    }
                    return full.fee_source
                }
            }
        },
        column_fee_source_type: function(){
            return {
                data: "fee_source_type",
                orderable: false,
                searchable: false,
                visible: true,
                name: 'fee_source_type',
                'render': function(row, type, full){
                    return full.fee_source_type
                }
            }
        },
        column_created: function(){
            return {
                data: "created",
                orderable: true,
                searchable: true,
                visible: true,
                name: 'created',
                'render': function(row, type, full){
                    return full.created_str
                }
            }
        },
        column_settled: function(){
            return {
                data: "settlement_date",
                orderable: true,
                searchable: true,
                visible: true,
                name: 'settlement_date',
                'render': function(row, type, full){
                    return full.settlement_date_str
                }
            }
        },
        column_amount: function(){
            return {
                data: "amount",
                orderable: true,
                searchable: true,
                visible: true,
                name: 'amount',
                'render': function(row, type, full){
                    return "$"+full.amount
                }
            }
        },
        column_status: function(){
            return {
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                name: 'status',
                'render': function(row, type, full){
                    if (full.settlement_date) {
                        return "Settled"
                    } else if (full.voided) {
                        return "Voided"
                    } else {
                        return "Not Settled"
                    }
                }
            }
        },
        column_description: function(){
            return {
                data: "text",
                orderable: false,
                searchable: true,
                visible: true,
                name: 'text',
                'render': function(row, type, full){
                    return full.text
                }
            }
        },
        datatable_options: function(){
            let vm = this

            let columns = [
                vm.column_id,
                vm.column_reference,
                vm.column_fee_source,
                vm.column_fee_source_type,
                vm.column_status,
                vm.column_created,
                vm.column_settled,
                vm.column_amount,
                vm.column_description,
            ]
            let search = true

            return {
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                rowCallback: function (row, invoice){
                    let row_jq = $(row)
                    row_jq.attr('id', 'invoice_id_' + invoice.id)
                    row_jq.children().first().addClass(vm.td_expand_class_name)

                },
                autoWidth: true,
                responsive: false,
                scrollX: true,
                fixedColumns: {
                    leftColumns: 1,
                    rightColumns: 1
                },
                serverSide: true,
                paging: true,
                lengthMenu: [ [10, 25, 50, 100], [10, 25, 50, 100] ],
                searching: search,
                ordering: true,
                order: [[0, 'desc']],  // Default order [[column_index, 'asc/desc'], ...]
                ajax: {
                    "url": api_endpoints.invoices_paginated_list + '?format=datatables',
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        d.filter_fee_source_type = vm.filterFeeSourceType
                        d.filter_status = vm.filterStatus

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
                        console.log(newOrder)
                    }
                },
                dom: 'lBfrtip',
                columns: columns,
                processing: true,
            }
        }
    },
}
</script>
