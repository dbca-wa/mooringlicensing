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
            <div class="col-md-3" v-if="is_internal">
                <div class="form-group">
                    <label for="">Applicant</label>
                    <select class="form-control" v-model="filterApplicant">
                        <option value="All">All</option>
                        <option v-for="applicant in applicants" :value="applicant.id">{{ applicant.first_name }} {{ applicant.last_name }}</option>
                    </select>
                </div>
            </div>
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Status</label>
                    <select class="form-control" v-model="filterApplicationStatus">
                        <option value="All">All</option>
                        <option v-for="status in application_statuses" :value="status.code">{{ status.description }}</option>
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
                    ref="application_datatable"
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
    name: 'TableApplications',
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
            if (this.is_external){
                return ['id', 'Lodgement Number', 'Type', 'Application Type', 'Status', 'Lodged on', 'Invoice', 'Action']
            }
            if (this.is_internal){
                return ['id', 'Lodgement Number', 'Type', 'Applicant', 'Status', 'Lodged on', 'Invoice', 'Assigned To', 'Payment Status', 'Action']
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
                    return full.lodgement_number
                },
                name: 'lodgement_number',
            }
        },
        column_type: function(){
            return {
                // 3. Type (This corresponds to the 'ApplicationType' at the backend)
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    if (full.application_type_dict){
                        return full.application_type_dict.description
                    } else {
                        // Should not reach here
                        return ''
                    }
                }
            }
        },
        column_application_type: function(){
            return {
                // 4. Application Type (This corresponds to the 'ProposalType' at the backend)
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    if (full.proposal_type){
                        return full.proposal_type.description
                    } else {
                        // Should not reach here
                        return ''
                    }
                }
            }
        },
        column_status: function(){
            let vm = this
            return {
                // 5. Status
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    if (vm.is_internal){
                        return full.processing_status
                    }
                    return full.customer_status
                }
            }
        },
        column_lodged_on: function(){
            return {
                // 6. Lodged
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    if (full.lodgement_date){
                        return moment(full.lodgement_date).format('DD/MM/YYYY')
                    }
                    return ''
                }
            }
        },
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
                            links +=  `<div><a href='/payments/invoice-pdf/${invoice.reference}.pdf' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i> #${invoice.reference}</a></div>`;
                            if (vm.is_internal){
                                links +=  `<div><a href='/ledger/payments/invoice/payment?invoice=${invoice.reference}' target='_blank'>View Payment</a></div>`;
                            }
                            links += '</div>'
                        }
                    }
                    return links
                }
            }
        },
        column_action: function(){
            let vm = this
            return {
                // 8. Action
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    let links = '';
                    if (vm.is_internal){
                        if(full.assessor_process){
                            links +=  `<a href='/internal/proposal/${full.id}'>Process</a><br/>`;
                        } else {
                            links +=  `<a href='/internal/proposal/${full.id}'>View</a><br/>`;
                        }
                    }
                    if (vm.is_external){
                        if (full.can_user_edit) {
                            links +=  `<a href='/external/proposal/${full.id}'>Continue</a><br/>`;
                            links +=  `<a href='#${full.id}' data-discard-proposal='${full.id}'>Discard</a><br/>`;
                        }
                        else if (full.can_user_view) {
                            links +=  `<a href='/external/proposal/${full.id}'>View</a><br/>`;
                        }
                        for (let invoice of full.invoices){
                            if (invoice.payment_status === 'unpaid'){
                                links +=  `<a href='/application_fee_existing/${full.id}'>Pay</a>`
                            }
                        }
                    }
                    return links;
                }
            }
        },
        column_applicant: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    if (full.submitter){
                        return `${full.submitter.first_name} ${full.submitter.last_name}`
                    }
                    return ''
                },
                name: 'submitter__first_name, submitter__last_name',
            }
        },
        column_assigned_to: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    let ret_str = ''
                    if (full.assigned_officer){
                        ret_str += full.assigned_officer
                    }
                    if (full.assigned_approver){
                        ret_str += full.assigned_approver
                    }
                    return ret_str
                },
                name: 'assigned_officer__first_name, assigned_officer__last_name, assigned_approver__first_name, assigned_approver__last_name',
            }
        },
        column_payment_status: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    if (full.invoices){
                        let ret_str = ''
                        for (let item of full.invoices){
                            ret_str += '<div>' + item.payment_status + '</div>'
                        }
                        return ret_str
                    } else {
                        return ''
                    }
                }
            }
        },
        datatable_options: function(){
            let vm = this

            let columns = []
            let search = null
            if(vm.is_external){
                columns = [
                    vm.column_id,
                    vm.column_lodgement_number,
                    vm.column_type,
                    vm.column_application_type,
                    vm.column_status,
                    vm.column_lodged_on,
                    vm.column_invoice,
                    vm.column_action,
                ]
                search = false
            }
            if(vm.is_internal){
                columns = [
                    vm.column_id,
                    vm.column_lodgement_number,
                    vm.column_type,
                    vm.column_applicant,
                    vm.column_status,
                    vm.column_lodged_on,
                    vm.column_invoice,
                    vm.column_assigned_to,
                    vm.column_payment_status,
                    vm.column_action,
                ]
                search = true
            }

            return {
                autoWidth: false,
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                serverSide: true,
                searching: search,
                ajax: {
                    "url": api_endpoints.proposals_paginated_list + '?format=datatables',
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        d.filter_application_type = vm.filterApplicationType
                        d.filter_application_status = vm.filterApplicationStatus
                        d.filter_applicant = vm.filterApplicant
                        d.level = vm.level
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
                    vm.$refs.application_datatable.vmDataTable.draw();
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
                if (vm.is_internal){
                    vm.application_statuses = response.body.internal_statuses
                } else {
                    vm.application_statuses = response.body.external_statuses
                }
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
            vm.$refs.application_datatable.vmDataTable.on('click', 'a[data-discard-proposal]', function(e) {
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
