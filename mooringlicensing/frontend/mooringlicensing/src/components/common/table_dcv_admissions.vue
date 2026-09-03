<template>
    <div>
        <div class="row">
            <div class="col-md-3">
                <div class="form-group">
                    <label for="organisation_lookup">Organisation</label>
                        <select
                            id="organisation_lookup"  
                            name="organisation_lookup"  
                            ref="organisation_lookup" 
                            class="form-control">
                            <option v-for="org in dcv_organisations" :key="org.id" :value="org.id">
                                {{ org.name }}
                            </option>
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

        <div class="row">
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
import { api_endpoints } from '@/utils/hooks'

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
            return ['id', 'Number', 'Invoice / Confirmation', 'Arrival Date', 'Lodgement Date', 'Action']
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
                            links +=  `<div><a href='${invoice.invoice_url}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> #${invoice.reference}</a></div>`;
                            if (!vm.is_external){
                                links +=  `<div><a href='${invoice.ledger_payment_url}' target='_blank'>Ledger Payment</a></div>`;
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
                    let links = '';
                    if (full.invoices){
                        for (let invoice of full.invoices){

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
                responsive: false,
                scrollX: true,
                fixedColumns: {
                    leftColumns: 1,
                    rightColumns: 1
                },
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
            $(vm.$refs.organisation_lookup).select2({
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
        new_application_button_clicked: function(){
            if (this.is_internal){
                this.$router.push({
                name: 'internal-dcv-admission-form'
            })
            }
            if (this.is_external){
            this.$router.push({
                name: 'apply_proposal'
            })
        }
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
    mounted: function(){
        let vm = this;
        this.$nextTick(() => {
            vm.addEventListeners();
            vm.initialiseOrganisationLookup();
        });
    }
}
</script>
