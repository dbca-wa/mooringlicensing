<template>
    <div>
        <div class="row">
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Status:</label>
                    <select class="form-control" v-model="filterMooringStatus">
                        <option value="All">All</option>
                        <!--option v-for="status in mooring_statuses" :value="status.code">{{ status.description }}</option-->
                        <option v-for="status in mooringStatuses" :value="status">{{ status }}</option>
                    </select>
                </div>
            </div>
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Bay:</label>
                    <select class="form-control" v-model="filterMooringBay">
                        <option value="All">All</option>
                        <!--option v-for="status in mooring_statuses" :value="status.code">{{ status.description }}</option-->
                        <option v-for="bay in mooringBays" :value="bay.id">{{ bay.name }}</option>
                    </select>
                </div>
            </div>

        </div>

        <div class="row">
            <div class="col-lg-12">
                <datatable 
                    ref="moorings_datatable" 
                    :id="datatable_id" 
                    :dtOptions="mooringsOptions" 
                    :dtHeaders="mooringsHeaders"
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
    name: 'TableMoorings',
    /*
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
    */
    data() {
        let vm = this;
        return {
            datatable_id: 'moorings-datatable-' + vm._uid,

            // selected values for filtering
            filterMooringStatus: null,
            filterMooringBay: null,
            mooringStatuses: [],
            mooringBays: [],

        }
    },
    components:{
        datatable
    },
    watch: {
        filterMooringStatus: function(){
            this.$refs.moorings_datatable.vmDataTable.ajax.reload()
        },
        filterMooringBay: function(){
            this.$refs.moorings_datatable.vmDataTable.ajax.reload()
        },
    },
    computed: {
        is_external: function() {
            return this.level == 'external'
        },
        mooringsHeaders: function() {
            /*
            let headers = ['Number', 'Licence/Permit', 'Condition', 'Due Date', 'Status', 'Action'];
            if (this.level === 'internal') {
                headers = ['Number', 'Type', 'Approval Number', 'Holder', 'Status', 'Due Date', 'Assigned to', 'Action'];
            }
            */
            return ['Mooring', 'Bay', 'Type', 'Status', 'Authorised User Permits', 'Max Vessel Length', 'Max Vessel Draft', 'Action'];
        },
        mooringNameColumn: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.name;
                        }
                    }
        },
        mooringBayColumn: function() {
            return {
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.mooring_bay_name;
                        }
                    }
        },
        mooringTypeColumn: function() {
            return {
                        // 2. Lodgement Number
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return 'Mooring';
                        }
                    }
        },
        statusColumn: function() {
            return {
                        // 3. Licence/Permit
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            //return 'not implemented';
                            return full.status;
                        }
                    }
        },
        authorisedUserPermitsColumn: function() {
            return {
                        // 4. Condition
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            //return 'not implemented';
                            return full.authorised_user_permits;
                        }
                    }
        },
        maxVesselLengthColumn: function() {
            return {
                        // 5. Due Date
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.vessel_size_limit;
                        }
                    }
        },
        maxVesselDraftColumn: function() {
            return {
                        // 6. Status
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.vessel_draft_limit;
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
                            return `<a href='/internal/moorings/${full.id}'>View</a><br/>`;
                        }
                    }
        },

        applicableColumns: function() {
            let columns = [
                this.mooringNameColumn,
                this.mooringBayColumn,
                this.mooringTypeColumn,
                this.statusColumn,
                this.authorisedUserPermitsColumn,
                this.maxVesselLengthColumn,
                this.maxVesselDraftColumn,
                this.actionColumn,
                ]
            return columns;
        },
        mooringsOptions: function() {
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
                    //"url": `${api_endpoints.mooring}internal_list.json?format=datatables`,
                    //"url": `${api_endpoints.mooring}internal_list?format=datatables`,
                    "url": api_endpoints.moorings_paginated_internal + '?format=datatables',
                    //"url": `${api_endpoints.mooring}internal_list.json`,
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        // Add filters selected
                        d.filter_mooring_status = vm.filterMooringStatus;
                        d.filter_mooring_bay = vm.filterMooringBay;
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
            vm.$http.get(api_endpoints.mooring_statuses_dict).then((response) => {
                vm.mooringStatuses = response.body
            },(error) => {
                console.log(error);
            })
            // Mooring Bays
            vm.$http.get(api_endpoints.mooring_bays).then((response) => {
                //for (let bay of response.body) {
                vm.mooringBays = response.body
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
