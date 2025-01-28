<template>
    <div>
        <div class="row">
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Organisation</label>
                    <select
                            id="organisation_lookup1"  
                            name="organisation_lookup1"  
                            ref="organisation_lookup1" 
                            class="form-control">
                            <option v-for="org in dcv_organisations" :key="org.id" :value="org.id">
                                {{ org.name }}
                            </option>
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

        <div v-if="is_external || is_internal" class="row">
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
            @sendData="sendDataForCreateNewSticker"
        />
        <RequestNewDCVStickerModal
            ref="request_new_dcv_sticker_modal"
            @sendData="sendDataForRequestNewSticker"
        />
        <RequestDCVStickerAddressModal
            ref="request_dcv_sticker_address_modal"
            @sendData="sendDataForStickerAddress"
        />
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import Vue from 'vue'
import { api_endpoints, helpers } from '@/utils/hooks'
import CreateNewStickerModal from "@/components/common/create_new_sticker_modal.vue"
import RequestNewDCVStickerModal from "@/components/common/request_new_dcv_sticker_modal.vue"
import RequestDCVStickerAddressModal from "@/components/common/request_dcv_sticker_address_modal.vue"

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
        RequestNewDCVStickerModal,
        RequestDCVStickerAddressModal,
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
                return ['id', 'Number', 'Invoice / Permit', 'Organisation', 'Status', 'Payment Status', 'Season', 'Sticker', 'Vessel Rego', 'Action']
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
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    let links = ''
                    if (full.invoices){
                        for (let invoice of full.invoices){
                            links +=  `<div><a href='${invoice.invoice_url}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> #${invoice.reference}</a></div>`;
                            if (!vm.is_external){
                                links +=  `<div><a href='${invoice.ledger_payment_url}' target='_blank'>Ledger Payment</a></div>`;
                            }
                        }
                    }
                    if (full.dcv_permit_documents){
                        for (let permit_url of full.dcv_permit_documents){
                            links +=  `<div><a href='${permit_url}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> Dcv Permit</a></div>`;
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
                },
                name: 'dcv_organisation__name',
            }
        },
        column_status: function(){
            return {
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    return full.status;
                },
                name: 'status',
            }
        },
        column_payment_status: function(){
            return {
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    return full.payment_status;
                },
            }
        },
        column_year: function(){
            return {
                data: "id",
                orderable: true,
                searchable: false,
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
                name: 'stickers__number',
            }
        },
        column_vessel_rego: function(){
            return {
                data: "id",
                orderable: false,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.vessel_rego
                },
                name: 'dcv_vessel__rego_no',
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
                    let links = '';
                    if (vm.is_internal){
                        if (full.display_create_sticker_action){
                            links +=  `<a href='#${full.id}' data-create-new-sticker='${full.id}'>Create New Sticker</a><br/>`;
                        }
                        if (full.display_request_sticker_action){
                            links += `<a href='#${full.id}' data-request-new-sticker='${full.id}'>Request New Sticker</a><br/>`
                        }
                        if (full.display_update_sticker_address_action){
                            links += `<a href='#${full.id}' data-request-sticker-address='${full.id}'>Update Sticker Address</a><br/>`
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
                vm.column_payment_status,
                vm.column_year,
                vm.column_sticker,
                vm.column_vessel_rego,
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
        initialiseOrganisationLookup: function(){
            let vm = this;
            $(vm.$refs.organisation_lookup1).select2({
                minimumInputLength: 2,
                theme: "bootstrap",
                allowClear: true,
                placeholder: "",
                ajax: {
                    url: api_endpoints.dcv_organisations,
                    dataType: 'json',
                    data: function(params) {
                        return {
                            search_term: params.term,
                        }
                    },
                    processResults: function(data) {
                        const results = data.results.map(org => ({
                            id: org.id,   
                            text: org.name
                        }));
                        return {
                            results: results, 
                        };
                    },
                },
            })
            .on("select2:select", function (e) {
                vm.filterDcvOrganisation = e.params.data.id;
            })
            .on("select2:unselect", function (e) {
                vm.filterDcvOrganisation = null;
            })
            .on("select2:open", function (e) {
                const searchField = $('[aria-controls="select2-organisation_lookup-results"]');
                searchField[0].focus();
            });
        },
        sendDataForCreateNewSticker: function(params){
            let vm = this
            vm.$http.post('/api/internal_dcv_permit/' + params.approval_id + '/create_new_sticker/', params).then(
                res => {
                    // Retrieve the element clicked on
                    let elem_clicked = $("a[data-create-new-sticker='" + params.approval_id + "']")

                    // Retrieve the row index clicked on
                    let row_index_clicked = elem_clicked.closest('tr').index()

                    // Retrieve whole data in the row
                    let row_data = vm.$refs.dcv_permits_datatable.vmDataTable.row(row_index_clicked).data()

                    // Update the row data
                    row_data.stickers.push({'number': res.body.number})
                    row_data.display_create_sticker_action = false
                    row_data.display_request_sticker_action = true
                    row_data.display_update_sticker_address_action = true

                    // Apply the updated data to the row
                    vm.$refs.dcv_permits_datatable.vmDataTable.row(row_index_clicked).data(row_data).invalidate()
                    vm.$refs.create_new_sticker_modal.processing = false
                    vm.$refs.create_new_sticker_modal.isModalOpen = false
                    vm.$refs.create_new_sticker_modal.change_sticker_address= false
                    vm.$refs.create_new_sticker_modal.postal_address_line1 = ''
                    vm.$refs.create_new_sticker_modal.postal_address_line2 = ''
                    vm.$refs.create_new_sticker_modal.postal_address_line3 = ''
                    vm.$refs.create_new_sticker_modal.postal_address_locality = ''
                    vm.$refs.create_new_sticker_modal.postal_address_state = ''
                    vm.$refs.create_new_sticker_modal.postal_address_country = ''
                    vm.$refs.create_new_sticker_modal.postal_address_postcode = ''
                },
                err => {
                    console.log(err)
                    vm.$refs.create_new_sticker_modal.errors = true
                    vm.$refs.create_new_sticker_modal.errorString = helpers.apiVueResourceError(err);
                    vm.$refs.create_new_sticker_modal.processing = false
                }
            )
        },
        sendDataForRequestNewSticker: function(params){
            let vm = this
            vm.$http.post('/api/internal_dcv_permit/' + params.dcv_permit_id + '/request_new_stickers/', params).then(
                res => {
                    vm.$refs.request_new_dcv_sticker_modal.processing = false
                    vm.$refs.request_new_dcv_sticker_modal.isModalOpen = false
                    vm.$refs.request_new_dcv_sticker_modal.change_sticker_address= false
                    vm.$refs.request_new_dcv_sticker_modal.postal_address_line1 = ''
                    vm.$refs.request_new_dcv_sticker_modal.postal_address_line2 = ''
                    vm.$refs.request_new_dcv_sticker_modal.postal_address_line3 = ''
                    vm.$refs.request_new_dcv_sticker_modal.postal_address_locality = ''
                    vm.$refs.request_new_dcv_sticker_modal.postal_address_state = ''
                    vm.$refs.request_new_dcv_sticker_modal.postal_address_country = ''
                    vm.$refs.request_new_dcv_sticker_modal.postal_address_postcode = ''
                },
                err => {
                    console.log(err)
                    vm.$refs.request_new_dcv_sticker_modal.errors = true
                    vm.$refs.request_new_dcv_sticker_modal.errorString = helpers.apiVueResourceError(err);
                    vm.$refs.request_new_dcv_sticker_modal.processing = false
                }
            )
        },
        sendDataForStickerAddress: function(params){
            let vm = this
            vm.$http.post('/api/internal_dcv_permit/' + params.dcv_permit_id + '/change_sticker_addresses/', params).then(
                res => {
                    vm.$refs.request_dcv_sticker_address_modal.processing = false
                    vm.$refs.request_dcv_sticker_address_modal.isModalOpen = false
                    vm.$refs.request_dcv_sticker_address_modal.change_sticker_address= false
                    vm.$refs.request_dcv_sticker_address_modal.postal_address_line1 = ''
                    vm.$refs.request_dcv_sticker_address_modal.postal_address_line2 = ''
                    vm.$refs.request_dcv_sticker_address_modal.postal_address_line3 = ''
                    vm.$refs.request_dcv_sticker_address_modal.postal_address_locality = ''
                    vm.$refs.request_dcv_sticker_address_modal.postal_address_state = ''
                    vm.$refs.request_dcv_sticker_address_modal.postal_address_country = ''
                    vm.$refs.request_dcv_sticker_address_modal.postal_address_postcode = ''
                },
                err => {
                    console.log(err)
                    vm.$refs.request_dcv_sticker_address_modal.errors = true
                    vm.$refs.request_dcv_sticker_address_modal.errorString = helpers.apiVueResourceError(err);
                    vm.$refs.request_dcv_sticker_address_modal.processing = false
                }
            )
        },
        createNewSticker: function(dcv_permit_id){
            console.log('dcv_permit_id: ' + dcv_permit_id)
            this.$refs.create_new_sticker_modal.approval_id = dcv_permit_id
            this.$refs.create_new_sticker_modal.isModalOpen = true
        },
        requestNewSticker: function(dcv_permit_id){
            this.$refs.request_new_dcv_sticker_modal.dcv_permit_id = dcv_permit_id
            this.$refs.request_new_dcv_sticker_modal.isModalOpen = true
        },
        requestStickerAddress: function(dcv_permit_id){
            this.$refs.request_dcv_sticker_address_modal.dcv_permit_id = dcv_permit_id
            this.$refs.request_dcv_sticker_address_modal.isModalOpen = true
        },
        new_application_button_clicked: function(){
            if (this.is_internal) {
                this.$router.push({
                    name: 'internal_dcv_permit'
                })
            } else {
                this.$router.push({
                    name: 'dcv_permit'
                })
            }
        },
        fetchFilterLists: function(){
            let vm = this;
            // FeeSeason list
            vm.$http.get(api_endpoints.fee_seasons_dict + '?application_type_codes=dcvp').then((response) => {
                vm.fee_seasons = response.body
            },(error) => {
                console.log(error);
            })
        },
        addEventListeners: function(){
            let vm = this

            vm.$refs.dcv_permits_datatable.vmDataTable.on('click', 'a[data-create-new-sticker]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-create-new-sticker');
                vm.createNewSticker(id);
            });
            vm.$refs.dcv_permits_datatable.vmDataTable.on('click', 'a[data-request-new-sticker]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-request-new-sticker');
                vm.requestNewSticker(id);
            });
            vm.$refs.dcv_permits_datatable.vmDataTable.on('click', 'a[data-request-sticker-address]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-request-sticker-address');
                vm.requestStickerAddress(id);
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
            vm.initialiseOrganisationLookup()
        });
    }
}
</script>
