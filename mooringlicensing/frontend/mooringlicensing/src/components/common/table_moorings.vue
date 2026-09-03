<template>
    <div>
        <div class="row">
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Status:</label>
                    <select class="form-control" v-model="filterMooringStatus">
                        <option value="All">All</option>
                        <option v-for="status in mooringStatuses" :value="status">{{ status }}</option>
                    </select>
                </div>
            </div>
            <div class="col-md-3">
                <div class="form-group">
                    <label for="">Bay:</label>
                    <select class="form-control" v-model="filterMooringBay">
                        <option value="All">All</option>
                        <option v-for="bay in mooringBays" :value="bay.id">{{ bay.name }}</option>
                    </select>
                </div>
            </div>

        </div>

        <div class="row">
            <div class="col-lg-12">
                <datatable ref="moorings_datatable" :id="datatable_id" :dtOptions="mooringsOptions"
                    :dtHeaders="mooringsHeaders" />
            </div>
        </div>
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import Vue from 'vue'
import { api_endpoints, helpers } from '@/utils/hooks'
export default {
    name: 'TableMoorings',
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
    components: {
        datatable
    },
    watch: {
        filterMooringStatus: function () {
            this.$refs.moorings_datatable.vmDataTable.ajax.reload()
        },
        filterMooringBay: function () {
            this.$refs.moorings_datatable.vmDataTable.ajax.reload()
        },
    },
    computed: {
        is_external: function () {
            return this.level == 'external'
        },
        mooringsHeaders: function () {
            return ['Mooring', 'Bay', 'Type', 'Status', 'Holder', 'Authorised User Permits<br/>(RIA/LIC)', 'Max Vessel<br/>Length', 'Max Vessel<br/>Draft', 'Action'];
        },
        holderColumn: function () {
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function (row, type, full) {
                    return full.holder;
                },
                name: 'name',
            }
        },
        mooringNameColumn: function () {
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function (row, type, full) {
                    return full.name;
                },
                name: 'name',
            }
        },
        mooringBayColumn: function () {
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function (row, type, full) {
                    return full.mooring_bay_name;
                },
                name: 'mooring_bay__name',
            }
        },
        mooringTypeColumn: function () {
            return {
                // 2. Lodgement Number
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function (row, type, full) {
                    return 'Mooring';
                }
            }
        },
        statusColumn: function () {
            return {
                // 3. Licence/Permit
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function (row, type, full) {
                    return full.status;
                }
            }
        },
        authorisedUserPermitsColumn: function () {
            return {
                // 4. Condition
                data: "id",
                orderable: false,
                searchable: false,
                createdCell: function (td, cellData, rowData, row, col) {
                    $(td).css("text-align", "center")
                },
                visible: true,
                'render': function (row, type, full) {
                    let total = full.authorised_user_permits.ria + full.authorised_user_permits.site_licensee
                    return total + ' (' + full.authorised_user_permits.ria + '/' + full.authorised_user_permits.site_licensee + ')'
                }
            }
        },
        maxVesselLengthColumn: function () {
            return {
                // 5. Due Date
                data: "vessel_size_limit",
                orderable: true,
                searchable: true,
                createdCell: function (td, cellData, rowData, row, col) {
                    $(td).css("text-align", "right").css("padding", "0 1em 0 0")
                },
                visible: true,
                'render': function (row, type, full) {
                    return full.vessel_size_limit;
                },
                name:'vessel_size_limit'
            }
        },
        maxVesselDraftColumn: function () {
            return {
                // 6. Status
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                createdCell: function (td, cellData, rowData, row, col) {
                    $(td).css("text-align", "right").css("padding", "0 1em 0 0")
                },
                'render': function (row, type, full) {
                    return full.vessel_draft_limit;
                },
                name: 'vessel_draft_limit'
            }
        },
        actionColumn: function () {
            let vm = this;
            return {
                // 7. Action
                data: "id",
                orderable: false,
                searchable: false,
                visible: true,
                'render': function (row, type, full) {
                    return `<a href='/internal/moorings/${full.id}'>View</a><br/>`;
                }
            }
        },

        applicableColumns: function () {
            let columns = [
                this.mooringNameColumn,
                this.mooringBayColumn,
                this.mooringTypeColumn,
                this.statusColumn,
                this.holderColumn,
                this.authorisedUserPermitsColumn,
                this.maxVesselLengthColumn,
                this.maxVesselDraftColumn,
                this.actionColumn,
            ]
            return columns;
        },
        mooringsOptions: function () {
            let vm = this;
            return {
                columns: vm.applicableColumns,
                columnDefs: [{
                    targets: [0],
                    render: function(data, type, full, meta) {
                        console.log({data})
                        return '<div>' + data + '</div>';
                    }
                }],
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
                lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
                searching: true,
                searchDelay: 500,

                ajax: {
                    "url": api_endpoints.moorings_paginated + '?format=datatables',
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function (d) {
                        // Add filters selected
                        d.filter_mooring_status = vm.filterMooringStatus;
                        d.filter_mooring_bay = vm.filterMooringBay;
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
                buttons: [
                    {
                        extend: 'excel',
                    },
                    {
                        extend: 'csv',
                    },
                ],
                processing: true,
                initComplete: function () {
                    console.log('in initComplete')
                },
            }
        },

    },
    methods: {
        fetchFilterLists: function () {
            let vm = this;

            // Statuses
            vm.$http.get(api_endpoints.mooring_statuses_dict).then((response) => {
                vm.mooringStatuses = response.body
            }, (error) => {
                console.log(error);
            })
            // Mooring Bays
            vm.$http.get(api_endpoints.mooring_bays).then((response) => {
                vm.mooringBays = response.body.results
            }, (error) => {
                console.log(error);
            })

        },
    },
    created: function () {
        this.fetchFilterLists()
    },
}
</script>
