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
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Category</label>
                    <select class="form-control" v-model="filterApplicationCategory">
                        <option value="All">All</option>
                        <option v-for="category in application_categories" :value="category.code">{{ category.description }}</option>
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

        <div class="row">
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

        <BypassPayment ref="bypass_payment"  @refreshFromResponse="refreshFromResponseProposalModify"></BypassPayment>
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import { api_endpoints, helpers } from '@/utils/hooks'
import BypassPayment from '@/components/internal/proposals/proposal_bypass_payment.vue'
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
        target_email_user_id: {
            type: Number,
            required: false,
            default: 0,
        }
    },
    data() {
        let vm = this;
        return {
            datatable_id: 'applications-datatable-' + vm._uid,

            // selected values for filtering
            filterApplicationType: null,
            filterApplicationCategory: null,
            filterApplicationStatus: null,

            // filtering options
            application_types: [],
            application_categories: [],
            application_statuses: [],
        }
    },
    components:{
        datatable,
        BypassPayment
    },
    watch: {
        filterApplicationStatus: function() {
            let vm = this;
            vm.$refs.application_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
        },
        filterApplicationType: function() {
            let vm = this;
            vm.$refs.application_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
        },
        filterApplicationCategory: function() {
            let vm = this;
            vm.$refs.application_datatable.vmDataTable.draw();  // This calls ajax() backend call.  This line is enough to search?  Do we need following lines...?
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
                orderable: true,
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
                data: "lodgement_number",
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
        column_type: function(){
            return {
                // 3. Type (This corresponds to the 'ApplicationType' at the backend)
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    if (full.application_type_dict){
                        return full.application_type_dict.description + ' (' + full.proposal_type.code + ')'
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
                orderable: false,
                searchable: false,
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
                        if (full.processing_status === 'Declined' && full.application_type_dict.code === 'aua'){
                            if (full.declined_by_endorser){
                                return 'Declined (Licensee)'
                            } else {
                                return 'Declined (RIA)'
                            }
                        }
                        return full.processing_status
                    }
                    return full.customer_status
                },
                name: "processing_status",
            }
        },
        column_lodged_on: function(){
            return {
                // 6. Lodged
                data: "lodgement_date",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    if (full.lodgement_date){
                        return moment(full.lodgement_date).format('DD/MM/YYYY')
                    }
                    return ''
                },
                name: "lodgement_date",
            }
        },
        column_invoice: function(){
            let vm = this
            return {
                // 7. Invoice
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    return full.invoice_links
                }
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

                        if(full.assessor_process){
                            links +=  `<a href='/internal/proposal/${full.id}'>Process</a><br/>`;
                        } else {
                            links +=  `<a href='/internal/proposal/${full.id}'>View</a><br/>`;
                        }

                        if (full.can_user_edit && full.processing_status === 'Draft' && full.application_type_dict.code !== 'mla') {
                            links +=  `<a href='#${full.id}' oncontextmenu="return false;" data-discard-proposal='${full.id}' data-application-type-code='${full.application_type_dict.code}' data-proposal-type-code='${full.proposal_type.code}'>Discard</a><br/>`;
                        }
                        
                        if (full.application_type_dict.code === 'mla' && full.processing_status === 'Draft'){
                            // Only ML draft application can be withdrawn
                            links +=  `<a href='#${full.id}' oncontextmenu="return false;" data-withdraw-proposal='${full.id}'>Withdraw</a><br/>`
                        }
                        if (full.application_type_dict.code === 'mla' && full.processing_status === 'Discarded'){
                            // Only ML discarded application can make originated WL allocation reinstated
                            links +=  `<a href='#${full.id}' oncontextmenu="return false;" data-reinstate-wl-allocation='${full.id}'>Reinstate WL allocation</a><br/>`
                        }
                    }
                    if (vm.is_external){
                        if (full.can_user_edit) {
                            links +=  `<a href='/external/proposal/${full.id}'>Continue</a><br/>`;
                            links +=  `<a href='#${full.id}' oncontextmenu="return false;" data-discard-proposal='${full.id}' data-application-type-code='${full.application_type_dict.code}' data-proposal-type-code='${full.proposal_type.code}'>Discard</a><br/>`;
                        }
                        else if (full.can_user_view) {
                            links +=  `<a href='/external/proposal/${full.id}'>View</a><br/>`;
                        }                                          
                    }
                    if (full.can_user_cancel_payment) {
                        links +=  `<a href='#${full.id}' oncontextmenu="return false;" data-discard-proposal='${full.id}' data-application-type-code='${full.application_type_dict.code}' data-proposal-type-code='${full.proposal_type.code}'>Discard</a><br/>`;
                    }
                    for (let invoice of full.invoices){
                            if (
                                (invoice.payment_status.toLowerCase() === 'unpaid' || 
                                invoice.payment_status.toLowerCase() === 'partially paid') &&
                                full.processing_status !== 'Expired'
                            ){
                                links +=  `<a href='/application_fee_existing/${invoice.reference}/'>Pay</a><br/>`    
                            }
                            if (full.processing_status === 'Awaiting Payment' && full.can_user_bypass_payment) {
                                links +=  `<a href='#${full.id}' oncontextmenu="return false;" data-bypass-payment='${full.id}' data-bypass-payment-invoice-ref='${invoice.reference}'>Bypass Payment</a><br/>`
                            }
                        }     
                    if (full.document_upload_url){
                        links +=  `<a href='${full.document_upload_url}'>Upload Documents</a>`
                    }
                    return links;
                }
            }
        },
        column_applicant: function(){
            return {
                data: "id",
                orderable: true,
                searchable: false, //special functionality for searching this field required
                visible: true,
                'render': function(row, type, full){
                    if (full.applicant){
                        if (full.applicant.legal_first_name) {
                            return `${full.applicant.legal_first_name} ${full.applicant.legal_last_name}`
                        } else {
                            return `${full.applicant.first_name} ${full.applicant.last_name}`
                        }
                    }
                    return ''
                },
                name: 'proposal_applicant'
            }
        },
        column_assigned_to: function(){
            return {
                data: "id",
                orderable: false,
                searchable: false,
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
                orderable: false,
                searchable: false,
                visible: true,
                'render': function(row, type, full){
                    if (full.invoices){
                        let ret_str = ''
                        for (let item of full.invoices){
                            ret_str += '<span>' + item.payment_status + ' </span>'
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
            let buttons = []
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
                buttons = []
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
                buttons = [
                    {
                        extend: 'excel',
                    },
                    {
                        extend: 'csv',
                    },
                ]
            }

            return {
                autoWidth: false,
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                serverSide: true,
                lengthMenu: [ [10, 25, 50, 100], [10, 25, 50, 100] ],
                searching: search,
                order: [0,'desc'],
                ajax: {
                    "url": api_endpoints.proposals_paginated_list + '?format=datatables&target_email_user_id=' + vm.target_email_user_id,
                    "dataSrc": 'data',
                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        d.filter_application_type = vm.filterApplicationType
                        d.filter_application_category = vm.filterApplicationCategory
                        d.filter_application_status = vm.filterApplicationStatus
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
                buttons: buttons,

                columns: columns,
                processing: true,
                initComplete: function() {
                },
            }
        }
    },
    methods: {
        bypassPayment: function(proposal_id, invoice_ref){
            this.$refs.bypass_payment.approval = {};
            this.$refs.bypass_payment.proposal_id = proposal_id;
            this.$refs.bypass_payment.invoice_ref = invoice_ref;
            this.$refs.bypass_payment.isModalOpen = true;
        },
        refreshFromResponseProposalModify: function(){
            this.$refs.application_datatable.vmDataTable.ajax.reload();
        },
        new_application_button_clicked: function(){
            if (this.is_internal) {
                this.$router.push({
                    name: 'internal_apply_proposal'
                })
            } else {
                this.$router.push({
                    name: 'apply_proposal'
                })
            }
        },
        reinstateWLAllocation: function(proposal_id){
            let vm = this;
            swal({
                title: "Reinstate Waiting List Allocation",
                text: "Are you sure you want to put the originated waiting list allocation back on the waiting list?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Reinstate WL Allocation',
                confirmButtonColor:'#dc3545'
            }).then(() => {
                vm.$http.put('/api/proposal/' + proposal_id + '/reinstate_wl_allocation/')
                .then((response) => {
                    console.log({response})
                    swal(
                        'Reinstated',
                        'Originated waiting list allocation has been reinstated',
                        'success'
                    )
                    vm.$refs.application_datatable.vmDataTable.draw();
                }, (error) => {
                    helpers.processError(error)
                });
            },(error) => {

            });

        },
        withdrawProposal: function(proposal_id){
            let vm = this;
            swal({
                title: "Withdraw Application",
                text: "Are you sure you want to withdraw this application?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Withdraw Application',
                confirmButtonColor:'#dc3545'
            }).then(() => {
                vm.$http.delete(api_endpoints.discard_proposal(proposal_id), {params: {'action': 'withdraw'}})
                .then((response) => {
                    swal(
                        'Withdrawn',
                        'Application has been discarded',
                        'success'
                    )
                    vm.$refs.application_datatable.vmDataTable.draw();
                }, (error) => {
                });
            },(error) => {

            });
        },
        discardProposal: function(proposal_id, application_type_code, proposal_type_code) {
            let vm = this;
            swal({
                title: "Discard Application",
                text: "Are you sure you want to discard this application?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Discard Application',
                confirmButtonColor:'#dc3545'
            }).then(() => {
                if (application_type_code === 'mla' && proposal_type_code === 'new'){
                    swal({
                        title: "Are you sure you want to discard this offer?",
                        text: "Please note this will withdraw your offer and you will lose your current position on the waiting list.",
                        type: "warning",
                        showCancelButton: true,
                        confirmButtonText: 'Discard Application',
                        confirmButtonColor:'#dc3545'
                    }).then(()=>{
                        vm.$http.delete(api_endpoints.discard_proposal(proposal_id), {params: {'action': 'discard'}})
                        .then((response) => {
                            swal(
                                'Discarded',
                                'Your application has been discarded',
                                'success'
                            )
                            vm.$refs.application_datatable.vmDataTable.draw();
                        }, (error) => {

                        });
                    }), (error) => {
                        // Cancelled at the 2nd warning
                    }
                } else {
                    vm.$http.delete(api_endpoints.discard_proposal(proposal_id), {params: {'action': 'discard'}})
                    .then((response) => {
                        swal(
                            'Discarded',
                            'Your application has been discarded',
                            'success'
                        )
                        vm.$refs.application_datatable.vmDataTable.draw();
                    }, (error) => {

                    });
                }
            },(error) => {
                // Cancelled at the 1st warning
            });
        },
        fetchFilterLists: function(){
            let vm = this;

            // Application Types
            vm.$http.get(api_endpoints.application_types_dict+'?apply_page=False').then((response) => {
                vm.application_types = response.body
            },(error) => {
            })

            // Application Categories
            vm.$http.get(api_endpoints.application_categories_dict+'?apply_page=False').then((response) => {
                vm.application_categories = response.body
            },(error) => {
            })

            // Application Statuses
            vm.$http.get(api_endpoints.application_statuses_dict).then((response) => {
                if (vm.is_internal){
                    vm.application_statuses = response.body.internal_statuses
                } else {
                    vm.application_statuses = response.body.external_statuses
                }
            },(error) => {
            })
        },
        addEventListeners: function(){
            let vm = this
            vm.$refs.application_datatable.vmDataTable.on('click', 'a[data-discard-proposal]', function(e) {
                e.preventDefault()
                let id = $(this).attr('data-discard-proposal')
                let application_type_code = $(this).attr('data-application-type-code')
                let proposal_type_code = $(this).attr('data-proposal-type-code')
                vm.discardProposal(id, application_type_code, proposal_type_code)
            })
            vm.$refs.application_datatable.vmDataTable.on('click', 'a[data-withdraw-proposal]', function(e) {
                e.preventDefault()
                let id = $(this).attr('data-withdraw-proposal')
                vm.withdrawProposal(id)
            })
            vm.$refs.application_datatable.vmDataTable.on('click', 'a[data-reinstate-wl-allocation]', function(e) {
                e.preventDefault()
                let id = $(this).attr('data-reinstate-wl-allocation')
                vm.reinstateWLAllocation(id)
            })
            vm.$refs.application_datatable.vmDataTable.on('click', 'a[data-bypass-payment]', function(e) {
                e.preventDefault();
                var id = $(this).attr('data-bypass-payment');
                var invoice_ref = $(this).attr('data-bypass-payment-invoice-ref');
                vm.bypassPayment(id,invoice_ref);
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
