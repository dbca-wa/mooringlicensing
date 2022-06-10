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
                    <label for="">Date from</label>
                    <div class="input-group date" ref="dateFromPicker">
                        <input type="text" class="form-control text-center" placeholder="DD/MM/YYYY" v-model="filterDateFrom" id="dateFromField"/>
                        <span class="input-group-addon">
                            <span class="glyphicon glyphicon-calendar"></span>
                        </span>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Date to</label>
                    <div class="input-group date" ref="dateToPicker">
                        <input type="text" class="form-control text-center" placeholder="DD/MM/YYYY" v-model="filterDateTo" id="dateToField"/>
                        <span class="input-group-addon">
                            <span class="glyphicon glyphicon-calendar"></span>
                        </span>
                    </div>
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
                    ref="admissions_datatable"
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
    name: 'TableDcvAdmissions',
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
            datatable_id: 'admissions-datatable-' + vm._uid,

            // selected values for filtering
            filterDcvOrganisation: null,
            filterDateFrom: null,
            filterDateTo: null,

            // filtering options
            dcv_organisations: [],
        }
    },
    components:{
        datatable
    },
    watch: {
        filterDcvOrganisation: function() {
            let vm = this;
            vm.$refs.admissions_datatable.vmDataTable.draw();
        },
        filterDateFrom: function() {
            let vm = this;
            vm.$refs.admissions_datatable.vmDataTable.draw();
        },
        filterDateTo: function() {
            let vm = this;
            vm.$refs.admissions_datatable.vmDataTable.draw();
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
            /*
            if (this.is_external){
                return ['id', 'Lodgement Number', 'Type', 'Application Type', 'Status', 'Lodged on', 'Invoice', 'Action']
            }
            if (this.is_internal){
                return ['id', 'Lodgement Number', 'Type', 'Applicant', 'Status', 'Lodged on', 'Assigned To', 'Payment Status', 'Action']
            }
            */
            return ['id', 'Number', 'Invoice / Confirmation',/* 'Organisation', 'Status',*/'Arrival Date', 'Lodgement Date', 'Action']
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
                    return full.lodgement_number
                },
                name: 'lodgement_number',
            }
        },
        column_invoice_confirmation: function(){
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
                            links +=  `<div><a href='/payments/invoice-pdf/${invoice.reference}.pdf' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> #${invoice.reference}</a></div>`;
                            if (!vm.is_external){
                                links +=  `&nbsp;&nbsp;&nbsp;<a href='/ledger/payments/invoice/payment?invoice=${invoice.reference}' target='_blank'>View Payment</a><br/>`;
                            }
                        }
                    }
                    if (full.admission_urls){
                        for (let admission_url of full.admission_urls){
                            links +=  `<div><a href='${admission_url}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> Confirmation</a></div>`;
                        }
                    }
                    return links
                }
            }
        },
        column_arrival_date: function(){
            return {
                data: "id",
                orderable: true,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    let ret = ''
                    for (let arrival of full.arrivals){
                        if (arrival){
                            ret += '<div>' + moment(arrival.arrival_date).format('DD/MM/YYYY') + '</div>'
                        }
                        else {
                            ret += ''
                        }

                    }
                    return ret
                },
                name: 'dcv_admission_arrivals__arrival_date',
            }
        },
        column_lodgement_date: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.lodgement_date;
                },
                name: 'lodgement_datetime',
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
                    /*
                    let links = '';
                    if (!vm.is_external){
                        if(full.assessor_process){
                            links +=  `<a href='/internal/proposal/${full.id}'>Process</a><br/>`;
                        } else {
                            links +=  `<a href='/internal/proposal/${full.id}'>View</a><br/>`;
                        }
                    }
                    else{
                        if (full.can_user_edit) {
                            links +=  `<a href='/external/proposal/${full.id}'>Continue</a><br/>`;
                            links +=  `<a href='#${full.id}' data-discard-proposal='${full.id}'>Discard</a><br/>`;
                        }
                        else if (full.can_user_view) {
                            links +=  `<a href='/external/proposal/${full.id}'>View</a><br/>`;
                        }
                    }
                    return links;
                    */
                    let links = '';
                    if (full.invoices){
                        for (let invoice of full.invoices){
                            //links += '<div>'
                            //if (!vm.is_external){
                            //    links +=  `&nbsp;&nbsp;&nbsp;<a href='/ledger/payments/invoice/payment?invoice=${invoice.reference}' target='_blank'>View Payment</a><br/>`;
                            //}
                            //links += '</div>'
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
                vm.column_invoice_confirmation,
                //vm.column_organisation,
                //vm.column_status,
                vm.column_arrival_date,
                vm.column_lodgement_date,
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
                    "url": api_endpoints.dcvadmissions_paginated_list + '?format=datatables',
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        d.filter_dcv_organisation_id = vm.filterDcvOrganisation
                        d.filter_date_from = vm.filterDateFrom
                        d.filter_date_to = vm.filterDateTo
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
        },
        addEventListeners: function(){
            let vm = this

            let el_fr = $(vm.$refs.dateFromPicker);
            let el_to = $(vm.$refs.dateToPicker);

            let options = {
                format: "DD/MM/YYYY",
                showClear: true ,
                useCurrent: false,
            };

            el_fr.datetimepicker(options)
            el_to.datetimepicker(options)

            el_fr.on("dp.change", function(e) {
                let selected_date = null;
                if (e.date){
                    // Date selected
                    selected_date = e.date.format('DD/MM/YYYY')  // e.date is moment object
                    vm.filterDateFrom = selected_date;
                    el_to.data('DateTimePicker').minDate(selected_date)
                } else {
                    // Date not selected
                    vm.filterDateFrom = selected_date;
                    el_to.data('DateTimePicker').minDate(false)
                }
            })

            el_to.on("dp.change", function(e){
                let selected_date = null;
                if (e.date){
                    // Date selected
                    selected_date = e.date.format('DD/MM/YYYY')  // e.date is moment object
                    vm.filterDateTo = selected_date;
                    el_fr.data('DateTimePicker').maxDate(selected_date)
                } else {
                    // Date not selected
                    vm.filterDateTo = selected_date;
                    el_fr.data('DateTimePicker').maxDate(false)
                }
            })
        },
    },
    created: function(){
        console.log('table_applications created')
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
