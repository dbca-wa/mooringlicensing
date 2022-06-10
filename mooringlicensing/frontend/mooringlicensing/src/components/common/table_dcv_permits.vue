<template>
    <div>
        <div class="row">
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Organisation</label>
                    <select class="form-control" v-model="filterDcvOrganisation">
                        <option value="All">All</option>
                        <option v-for="org in dcv_organisations" :value="org.id">{{ org.name }}</option>
                    </select>
                </div>
            </div>
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Season</label>
                    <select class="form-control" v-model="filterFeeSeason">
                        <option value="All">All</option>
                        <option v-for="fee_season in fee_seasons" :value="fee_season.id">{{ fee_season.name }}</option>
                    </select>
                </div>
            </div>
        </div>

        <div v-if="is_external" class="row">
            <div class="col-md-12">
                <button type="button" class="btn btn-primary pull-right" @click="new_application_button_clicked">New Application</button>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-12">
                <datatable
                    ref="dcv_permits_datatable"
                    :id="datatable_id"
                    :dtOptions="datatable_options"
                    :dtHeaders="datatable_headers"
                />
            </div>
        </div>
        <CreateNewStickerModal
            ref="create_new_sticker_modal"
            @sendData="sendData"
        />
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import Vue from 'vue'
import { api_endpoints, helpers } from '@/utils/hooks'
import CreateNewStickerModal from "@/components/common/create_new_sticker_modal.vue"

export default {
    name: 'TableDcvPermits',
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

            // selected values for filtering
            filterDcvOrganisation: null,
            filterFeeSeason: null,

            // filtering options
            dcv_organisations: [],
            fee_seasons: [],
        }
    },
    components:{
        datatable,
        CreateNewStickerModal,
    },
    watch: {
        filterDcvOrganisation: function() {
            let vm = this;
            vm.$refs.dcv_permits_datatable.vmDataTable.draw();
        },
        filterFeeSeason: function() {
            let vm = this;
            vm.$refs.dcv_permits_datatable.vmDataTable.draw();
        },
    },
    computed: {
        is_external: function() {
            return this.level == 'external'
        },
        is_internal: function() {
            return this.level == 'internal'
        },
        datatable_headers: function(){
            if (this.is_internal){
                return ['id', 'Number', 'Invoice / Permit', 'Organisation', 'Status', 'Season', 'Sticker', 'Action']
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
                    console.log(full)
                    return full.id
                }
            }
        },
        column_lodgement_number: function(){
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
        column_invoice_approval: function(){
            let vm = this

            return {
                data: "id",
                orderable: false,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    let links = ''
                    if (full.invoices){
                        for (let invoice of full.invoices){
                            links +=  `<div><a href='/payments/invoice-pdf/${invoice.reference}.pdf' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> #${invoice.reference}</a></div>`;
                            if (!vm.is_external){
                                links +=  `&nbsp;&nbsp;&nbsp;<a href='/ledger/payments/invoice/payment?invoice=${invoice.reference}' target='_blank'>View Payment</a><br/>`;
                            }
                        }
                    }
                    if (full.permits){
                        for (let permit_url of full.permits){
                            links +=  `<div><a href='${permit_url}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> Permit</a></div>`;
                        }
                    }
                    return links
                }
            }
        },
        column_organisation: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.dcv_organisation_name;
                    //return '';
                },
                name: 'dcv_organisation__name',
            }
        },
        column_status: function(){
            return {
                data: "id",
                orderable: false,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.status;
                },
                name: 'status',
            }
        },
        column_year: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.fee_season;
                },
                name: 'fee_season__name',

            }
        },
        column_sticker: function(){
            return {
                data: "id",
                orderable: false,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    let ret_str = ''
                    for(let sticker of full.stickers){
                        ret_str += sticker.number + '<br />'
                    }
                    return ret_str
                },
                name: 'sticker_number',
            }
        },
        column_action: function(){
            let vm = this
            return {
                // 8. Action
                data: "id",
                orderable: false,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    let links = '';
                    if (vm.is_internal){
                        //if (full.invoices){
                        //    for (let invoice of full.invoices){
                        //        links += '<div>'
                        //        if (!vm.is_external){
                        //            links +=  `&nbsp;&nbsp;&nbsp;<a href='/ledger/payments/invoice/payment?invoice=${invoice.reference}' target='_blank'>View Payment</a><br/>`;
                        //        }
                        //        links += '</div>'
                        //    }
                        //}
                        if (full.display_create_sticker_action){
                            links +=  `<a href='#${full.id}' data-create-new-sticker='${full.id}'>Create New Sticker</a><br/>`;
                        }
                    }
                    return links
                }
            }
        },
        datatable_options: function(){
            let vm = this

            let columns = [
                vm.column_id,
                vm.column_lodgement_number,
                vm.column_invoice_approval,
                vm.column_organisation,
                vm.column_status,
                vm.column_year,
                vm.column_sticker,
                vm.column_action,
            ]
            let search = true

            return {
                autoWidth: false,
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                serverSide: true,
                searching: search,
                ajax: {
                    "url": api_endpoints.dcvpermits_paginated_list + '?format=datatables',
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        d.filter_dcv_organisation_id = vm.filterDcvOrganisation
                        d.filter_fee_season_id = vm.filterFeeSeason
                    }
                },
                dom: 'lBfrtip',
                //buttons:[ ],
                buttons:[
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
        sendData: function(params){
            let vm = this
            vm.$http.post('/api/dcv_permit/' + params.dcv_permit_id + '/create_new_sticker/', params).then(
                res => {
                    // Retrieve the element clicked on
                    let elem_clicked = $("a[data-create-new-sticker='" + params.dcv_permit_id + "']")

                    // Retrieve the row index clicked on
                    let row_index_clicked = elem_clicked.closest('tr').index()

                    // Retrieve whole data in the row
                    let row_data = vm.$refs.dcv_permits_datatable.vmDataTable.row(row_index_clicked).data()

                    // Update the row data
                    row_data.stickers.push({'number': res.body.number})
                    row_data.display_create_sticker_action = false

                    // Apply the updated data to the row
                    vm.$refs.dcv_permits_datatable.vmDataTable.row(row_index_clicked).data(row_data).invalidate()

                    vm.$refs.create_new_sticker_modal.isModalOpen = false
                },
                err => {
                    console.log(err)
                    vm.$refs.create_new_sticker_modal.isModalOpen = false
                }
            )
        },
        createNewSticker: function(dcv_permit_id){
            console.log('dcv_permit_id: ' + dcv_permit_id)
            this.$refs.create_new_sticker_modal.dcv_permit_id = dcv_permit_id
            this.$refs.create_new_sticker_modal.isModalOpen = true
        },
        new_application_button_clicked: function(){
            this.$router.push({
                name: 'apply_proposal'
            })
        },
        fetchFilterLists: function(){
            let vm = this;

            // DcvOrganisation list
            vm.$http.get(api_endpoints.dcv_organisations).then((response) => {
                vm.dcv_organisations = response.body
            },(error) => {
                console.log(error);
            })
            // FeeSeason list
            //vm.$http.get(api_endpoints.fee_seasons_dict + '?application_type_codes=dcvp').then((response) => {
            vm.$http.get(api_endpoints.fee_seasons_dict + '?application_type_codes=dcvp').then((response) => {
                vm.fee_seasons = response.body
            },(error) => {
                console.log(error);
            })
        },
        addEventListeners: function(){
            let vm = this

            //External Request New Sticker listener
            vm.$refs.dcv_permits_datatable.vmDataTable.on('click', 'a[data-create-new-sticker]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-create-new-sticker');
                vm.createNewSticker(id);
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
