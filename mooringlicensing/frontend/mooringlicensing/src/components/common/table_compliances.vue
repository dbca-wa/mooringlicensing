<template>
    <div>
        <div class="row">
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Status</label>
                    <select class="form-control" v-model="filterComplianceStatus">
                        <option value="All">All</option>
                        <option v-for="status in compliance_statuses" :value="status.code">{{ status.description }}</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-12">
                <datatable 
                    ref="compliances_datatable" 
                    :id="datatable_id" 
                    :dtOptions="compliancesOptions" 
                    :dtHeaders="compliancesHeaders"
                />
            </div>
        </div>
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import Vue from 'vue'
import { api_endpoints, helpers }from '@/utils/hooks'
export default {
    name: 'TableCompliances',
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
            datatable_id: 'compliances-datatable-' + vm._uid,

            // selected values for filtering
            filterComplianceStatus: null,
            compliance_statuses: [],

            // Datatable settings
            /*
            compliances_headers: ['Id', 'Number', 'Licence/Permit', 'Condition', 'Due Date', 'Status', 'Action'],
            compliances_options: {
                searching: false,
                autoWidth: false,
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                serverSide: true,

                ajax: {
                    "url": api_endpoints.compliances_paginated_external + '?format=datatables',
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        // Add filters selected
                        d.filter_compliance_status = vm.filterComplianceStatus;
                    }
                },
                dom: 'lBfrtip',
                buttons:[
                    //{
                    //    extend: 'csv',
                    //    exportOptions: {
                    //        columns: ':visible'
                    //    }
                    //},
                ],
                columns: [
                    {
                        // 1. ID
                        data: "id",
                        orderable: false,
                        searchable: false,
                        visible: false,
                        'render': function(row, type, full){
                            return full.id
                        }
                    },
                    {
                        // 2. Lodgement Number
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.lodgement_number
                        }
                    },
                    {
                        // 3. Licence/Permit
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.approval_number
                        }
                    },
                    {
                        // 4. Condition
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            let requirement = '';
                            if (full.requirement) {
                                requirement = full.requirement.requirement;
                            }
                            return requirement;
                        }
                    },
                    {
                        // 5. Due Date
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            let dueDate = '';
                            if (full.requirement) {
                                dueDate = full.requirement.read_due_date;
                            }
                            return dueDate;
                        }
                    },
                    {
                        // 6. Status
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.status
                        }
                    },
                    {
                        // 7. Action
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return 'not implemented'
                        }
                    },
                ],
                processing: true,
                initComplete: function() {
                    console.log('in initComplete')
                },

            },
            */
        }
    },
    components:{
        datatable
    },
    watch: {
        filterComplianceStatus: function(){
            this.$refs.compliances_datatable.vmDataTable.ajax.reload()
        }
    },
    computed: {
        is_external: function() {
            return this.level == 'external'
        },
        compliancesHeaders: function() {
            let headers = ['Number', 'Licence/Permit', 'Condition', 'Due Date', 'Status', 'Action'];
            if (this.level === 'internal') {
                headers = ['Number', 'Type', 'Approval Number', 'Holder', 'Status', 'Due Date', 'Assigned to', 'Action'];
            }
            return headers;
        },
        approvalSubmitterColumn: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.approval_submitter;
                        }
                    }
        },
        approvalTypeColumn: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.approval_type;
                        }
                    }
        },
        lodgementNumberColumn: function() {
            return {
                        // 2. Lodgement Number
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.lodgement_number
                        }
                    }
        },
        licenceNumberColumn: function() {
            return {
                        // 3. Licence/Permit
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.approval_number
                        }
                    }
        },
        conditionColumn: function() {
            return {
                        // 4. Condition
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            let requirement = '';
                            if (full.requirement) {
                                requirement = full.requirement.requirement;
                            }
                            return requirement;
                        }
                    }
        },
        dueDateColumn: function() {
            return {
                        // 5. Due Date
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            let dueDate = '';
                            if (full.requirement) {
                                dueDate = full.requirement.read_due_date;
                            }
                            return dueDate;
                        }
                    }
        },
        statusColumn: function() {
            return {
                        // 6. Status
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.status
                        }
                    }
        },
        actionColumn: function() {
            let vm = this;
            return {
                        // 7. Action
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            //return 'not implemented'
                            let links = '';
                            if (!vm.is_external){
                                //if (full.processing_status=='With Assessor' && vm.check_assessor(full)) {
                                if (full.can_process) {
                                    links +=  `<a href='/internal/compliance/${full.id}'>Process</a><br/>`;

                                }
                                else {
                                    links +=  `<a href='/internal/compliance/${full.id}'>View</a><br/>`;
                                }
                            }
                            else{
                                if (full.can_user_view) {
                                    links +=  `<a href='/external/compliance/${full.id}'>View</a><br/>`;

                                }
                                else {
                                    links +=  `<a href='/external/compliance/${full.id}'>Submit</a><br/>`;
                                }
                            }
                            return links;

                        }
                    }
        },
        assignedToNameColumn: function() {
            return {
                        // 7. Action
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.assigned_to_name;
                        }
                    }
        },

        applicableColumns: function() {
            let columns = [
                this.lodgementNumberColumn,
                this.licenceNumberColumn,
                this.conditionColumn,
                this.dueDateColumn,
                this.statusColumn,
                this.actionColumn,
                ]
            if (this.level === 'internal') {
                columns = [
                    this.lodgementNumberColumn,
                    this.approvalTypeColumn,
                    this.licenceNumberColumn,
                    this.approvalSubmitterColumn,
                    //this.conditionColumn,
                    this.statusColumn,
                    this.dueDateColumn,
                    this.assignedToNameColumn,
                    this.actionColumn,
                    ]
            }
            return columns;
        },
        compliancesOptions: function() {
            let vm = this;
            return {
                searching: false,
                autoWidth: false,
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                serverSide: true,
                searching: true,

                ajax: {
                    "url": api_endpoints.compliances_paginated_external + '?format=datatables',
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        // Add filters selected
                        d.filter_compliance_status = vm.filterComplianceStatus;
                    }
                },
                dom: 'lBfrtip',
                buttons:[
                    //{
                    //    extend: 'csv',
                    //    exportOptions: {
                    //        columns: ':visible'
                    //    }
                    //},
                ],
                columns: vm.applicableColumns,
                processing: true,
                initComplete: function() {
                    console.log('in initComplete')
                },
            }
        },

    },
    methods: {
        fetchFilterLists: function(){
            let vm = this;

            // Statuses
            vm.$http.get(api_endpoints.compliance_statuses_dict).then((response) => {
                vm.compliance_statuses = response.body
            },(error) => {
                console.log(error);
            })
        },
    },
    created: function(){
        this.fetchFilterLists()
    },
    mounted: function(){

    }
}
</script>
