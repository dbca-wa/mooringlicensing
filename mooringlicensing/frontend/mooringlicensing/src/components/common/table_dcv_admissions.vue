<template>
    <div>
        <div class="row">
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Type</label>
                    <select class="form-control" v-model="filterApplicationType">
                        <option value="All">All</option>
                        <option v-for="type in application_types" :value="type.code">{{ type.description }}</option>
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
            datatable_id: 'admissions-datatable-' + vm._uid,

            // selected values for filtering
            filterApplicationType: null,
            filterApplicationStatus: null,
            filterApplicant: null,

            // filtering options
            application_types: [],
            application_statuses: [],
            applicants: [],
        }
    },
    components:{
        datatable
    },
    watch: {
        filterApplicationStatus: function() {
            let vm = this;
            vm.$refs.application_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
            //if (vm.filterApplicationStatus != 'All') {
            //    vm.$refs.application_datatable.vmDataTable.column('status:name').search('').draw();
            //} else {
            //    vm.$refs.application_datatable.vmDataTable.column('status:name').search(vm.filterApplicationStatus).draw();
            //}
        },
        filterApplicationType: function() {
            let vm = this;
            vm.$refs.application_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
        },
        filterApplicant: function(){
            let vm = this;
            vm.$refs.application_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
        }
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
            return ['id', 'Number', 'Invoice / Confirmation',/* 'Organisation',*/ 'UIV Vessel Identifier',/* 'Status',*/ 'Date', 'Action']
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
                    return full.lodgement_number
                },
                name: 'lodgement_number',
            }
        },
        column_invoice_confirmation: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return 'not implemented';
                }
            }
        },
        /*
        column_organisation: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.dcv_organisation_name;
                    //return '';
                }
            }
        },
        */
        column_uiv: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.dcv_vessel_uiv;
                    //return '';
                }
            }
        },
        /*
        column_status: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.status;
                }
            }
        },
        */
        column_date: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.lodgement_date;
                }
            }
        },

        /*
        column_invoice: function(){
            let vm = this
            return {
                // 7. Invoice
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    let links = '';
                    if (full.invoices){
                        for (let invoice of full.invoices){
                            links += '<div>'
                            links +=  `<a href='/payments/invoice-pdf/${invoice.reference}.pdf' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> #${invoice.reference}</a>`;
                            if (!vm.is_external){
                                links +=  `&nbsp;&nbsp;&nbsp;<a href='/ledger/payments/invoice/payment?invoice=${invoice.reference}' target='_blank'>View Payment</a><br/>`;
                            }
                            links += '</div>'
                        }
                    }
                    return links
                }
            }
        },
        */
        column_action: function(){
            let vm = this
            return {
                // 8. Action
                data: "id",
                orderable: true,
                searchable: true,
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
                    return 'not implemented';
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
                vm.column_uiv,
                //vm.column_status,
                vm.column_date,
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
                        /*
                        d.filter_application_type = vm.filterApplicationType
                        d.filter_application_status = vm.filterApplicationStatus
                        d.filter_applicant = vm.filterApplicant
                        */
                    }
                },
                dom: 'lBfrtip',
                buttons:[ ],
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
        discardProposal: function(proposal_id) {
            let vm = this;
            swal({
                title: "Discard Application",
                text: "Are you sure you want to discard this proposal?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Discard Application',
                confirmButtonColor:'#dc3545'
            }).then(() => {
                vm.$http.delete(api_endpoints.discard_proposal(proposal_id))
                .then((response) => {
                    console.log('response: ')
                    console.log(response)
                    swal(
                        'Discarded',
                        'Your proposal has been discarded',
                        'success'
                    )
                    //vm.$refs.application_datatable.vmDataTable.ajax.reload();
                    vm.$refs.admissions_datatable.vmDataTable.draw();
                }, (error) => {
                    console.log(error);
                });
            },(error) => {

            });
        },
        fetchFilterLists: function(){
            let vm = this;

            // Application Types
            vm.$http.get(api_endpoints.application_types_dict+'?apply_page=False').then((response) => {
                vm.application_types = response.body
            },(error) => {
                console.log(error);
            })

            // Application Statuses
            vm.$http.get(api_endpoints.application_statuses_dict).then((response) => {
                vm.application_statuses = response.body
            },(error) => {
                console.log(error);
            })

            // Applicant
            if (vm.is_internal){
                vm.$http.get(api_endpoints.applicants_dict).then((response) => {
                    console.log(response.body)
                    vm.applicants = response.body
                },(error) => {
                    console.log(error);
                })
            }
        },
        addEventListeners: function(){
            let vm = this
            vm.$refs.admissions_datatable.vmDataTable.on('click', 'a[data-discard-proposal]', function(e) {
                e.preventDefault();
                let id = $(this).attr('data-discard-proposal');
                vm.discardProposal(id)
            });
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
