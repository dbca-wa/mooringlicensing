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
import { api_endpoints }from '@/utils/hooks'
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
        target_email_user_id: {
            type: Number,
            required: false,
            default: 0,
        },
    },
    data() {
        let vm = this;
        return {
            datatable_id: 'compliances-datatable-' + vm._uid,

            // selected values for filtering
            filterComplianceStatus: null,
            compliance_statuses: [],
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
        is_internal: function() {
            return this.level == 'internal'
        },
        compliancesHeaders: function() {
            let headers = ['Number', 'Licence/Permit', 'Condition', 'Due Date', 'Status', 'Action'];
            if (this.level === 'internal') {
                headers = ['Number', 'Type', 'Approval Number', 'Holder', 'Status', 'Due Date', 'Assigned to', 'Action'];
            }
            return headers;
        },
        approvalHolderColumn: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.approval_holder;
                        },
                        name: 'approval_holder'
                    }
        },
        approvalTypeColumn: function() {
            return {
                        data: "id",
                        orderable: false,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.approval_type;
                        },
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
                        },
                        name: "lodgement_number"
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
                        },
                        name: "approval__lodgement_number",
                    }
        },
        conditionColumn: function() {
            return {
                        // 4. Condition
                        data: "id",
                        orderable: false,
                        searchable: false,
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
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            let dueDate = '';
                            if (full.due_date_display) {
                                dueDate = full.due_date_display;
                            }
                            return dueDate;
                        },
                        name: "due_date"
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
                        },
                        name: "processing_status"
                    }
        },
        actionColumn: function() {
            let vm = this;
            return {
                        // 7. Action
                        data: "id",
                        orderable: false,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            let links = '';
                            if (!vm.is_external){
                                if (full.can_process && full.status !== 'Approved') {
                                    links +=  `<a href='/internal/compliance/${full.id}'>Process</a><br/>`;
                                } else {
                                    links +=  `<a href='/internal/compliance/${full.id}'>View</a><br/>`;
                                }
                            }
                            else{
                                if (full.can_user_view) {
                                    // When the compliance is not in the editable status for external user
                                    links +=  `<a href='/external/compliance/${full.id}'>View</a><br/>`;
                                } else {
                                    // Otherwise external user can edit
                                    links +=  `<a href='/external/compliance/${full.id}'>Continue</a><br/>`;
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
                        orderable: false,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.assigned_to_name;
                        },
                        name: 'assigned_to__first_name, assigned_to__last_name',
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
                    this.approvalHolderColumn,
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
            let buttons = []
            if (this.level === 'internal'){
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
                responsive: false,
                scrollX: true,
                fixedColumns: {
                    leftColumns: 1,
                    rightColumns: 1
                },
                serverSide: true,
                lengthMenu: [ [10, 25, 50, 100], [10, 25, 50, 100] ],
                searching: true,
                searchDelay: 500,
                order: [
                    [0, 'desc']
                ],

                ajax: {
                    "url": api_endpoints.compliances_paginated + '?format=datatables&target_email_user_id=' + vm.target_email_user_id,
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        // Add filters selected
                        d.filter_compliance_status = vm.filterComplianceStatus;
                        d.level = vm.level;
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
                columns: vm.applicableColumns,
                processing: true,
            }
        },

    },
    methods: {
        fetchFilterLists: function(){
            let vm = this;
            // Compliance Statuses
            vm.$http.get(api_endpoints.compliance_statuses_dict).then((response) => {
                if (vm.is_internal){
                    vm.compliance_statuses = response.body.internal_statuses
                } else {
                    vm.compliance_statuses = response.body.external_statuses
                }
            },(error) => {
            })
        },
    },
    created: function(){
        this.fetchFilterLists()
    },
}
</script>
