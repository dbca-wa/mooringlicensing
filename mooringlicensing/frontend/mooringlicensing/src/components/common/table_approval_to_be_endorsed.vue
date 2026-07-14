<template>
    <div>
        <div class="row">

        </div>

        <div class="row">
            <div class="col-lg-12">
                <datatable 
                    ref="to_be_endorsed_datatable" 
                    :id="datatable_id" 
                    :dtOptions="to_be_endorsed_options" 
                    :dtHeaders="to_be_endorsed_headers"
                />
            </div>
        </div>
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import { api_endpoints, constants } from '@/utils/hooks'
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
        let buttons = []
        if (vm.is_internal){
            buttons = [
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
            ]
        }

        return {
            datatable_id: 'to_be_endorsed-datatable-' + vm._uid,
            approvalTypesToDisplay: ['aua'],

            // selected values for filtering
            filterApplicationType: null,
            filterApplicationStatus: null,
            filter_by_endorsement: true,

            // Datatable settings
            to_be_endorsed_headers: ['Id', 'Proposal Id', 'Proposal', 'Mooring', 'Applicant', 'Status', 'Action','uuid','declined','endored'],
            to_be_endorsed_options: {
                autoWidth: false,
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                serverSide: true,
                searching: true,
                order: [1,'desc'],
                ajax: {
                    "url": api_endpoints.site_licensee_mooring_requests + '?format=datatables',
                    "dataSrc": 'data',
                    "data": function ( d ) {
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
                dom: 'lBfrtp',
                buttons: buttons,
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
                        data: "proposal_id",
                        orderable: true,
                        searchable: false,
                        visible: false,
                        'render': function(row, type, full){
                            return full.proposal_id
                        }
                    },
                    {
                        // 2. Lodgement Number
                        data: "proposal_number",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.proposal_number
                        },
                        name: "proposal__lodgement_number",
                    },
                    {
                        // 3. Mooring
                        data: "mooring_name",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            return full.mooring_name
                        },
                        name: "mooring__name",
                    },
                    {
                        // 4. Applicant
                        data: "applicant_name",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            return full.applicant_name
                        },
                        name: "proposal__proposal_applicant",
                    },
                    {
                        // 5. Status
                        data: "proposal_status",
                        orderable: true,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            if (full.approved_by_endorser) {
                                return full.proposal_status + " - Endorsed for " + full.mooring_name
                            } else if (full.declined_by_endorser) {
                                return full.proposal_status + " - Declined for " + full.mooring_name
                            } else {
                                return full.proposal_status
                            }
                        },
                        name: "proposal__customer_status",
                    },
                    {
                        // 10. Action
                        data: "can_endorse",
                        orderable: false,
                        searchable: false,
                        visible: true,
                        'render': function(row, type, full){
                            let links = '';
                            links +=  `<a href='/external/proposal/${full.uuid}/'>View</a><br/>`;
                            if(full.proposal_status === constants.AWAITING_ENDORSEMENT 
                                && full.can_endorse
                                && !full.declined_by_endorser 
                                && !full.approved_by_endorser
                            ){
                                links +=  `<a href='#${full.id}' oncontextmenu="return false;" data-approve-endorsement='${full.uuid}' data-approve-endorsement-mooring='${full.mooring_name}'>Endorse</a><br/>`
                                links +=  `<a href='#${full.id}' oncontextmenu="return false;" data-decline-endorsement='${full.uuid}' data-approve-endorsement-mooring='${full.mooring_name}'>Decline</a><br/>`
                            }
                            return links
                        }
                    },
                    {
                        data: "uuid",
                        orderable: false,
                        searchable: false,
                        visible: false,
                        'render': function(row, type, full){
                            return full.uuid
                        }
                    },
                    {
                        data: "declined_by_endorser",
                        orderable: false,
                        searchable: false,
                        visible: false,
                        'render': function(row, type, full){
                            return full.declined_by_endorser
                        }
                    },
                    {
                        data: "approved_by_endorser",
                        orderable: false,
                        searchable: false,
                        visible: false,
                        'render': function(row, type, full){
                            return full.approved_by_endorser
                        }
                    },
                ],
                processing: true,
            },
        }
    },
    components:{
        datatable
    },
    computed: {
        is_external: function() {
            return this.level === 'external'
        },
        is_internal: function() {
            return this.level === 'internal'
        },
    },
    methods: {
        addEventListeners: function(){
            let vm = this
            vm.$refs.to_be_endorsed_datatable.vmDataTable.on('click', 'a[data-approve-endorsement]', function(e) {
                e.preventDefault();
                var uuid = $(this).attr('data-approve-endorsement');
                var mooring_name = $(this).attr('data-approve-endorsement-mooring');
                vm.approveEndorsement(uuid,mooring_name);
            })
            vm.$refs.to_be_endorsed_datatable.vmDataTable.on('click', 'a[data-decline-endorsement]', function(e) {
                e.preventDefault();
                var uuid = $(this).attr('data-decline-endorsement');
                var mooring_name = $(this).attr('data-approve-endorsement-mooring');
                vm.declineEndorsement(uuid,mooring_name);
            })
        },
        approveEndorsement: function(uuid,mooring_name){
            let vm = this
            swal({
                title: "Endorse Application",
                text: "Are you sure you want to endorse this application?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Endorse Application',
                confirmButtonColor:'#dc3545'
            }).then(() => {
                vm.$http.get('/aua_for_endorsement/' + uuid + '/endorse/?mooring_name=' + mooring_name)
                .then((response) => {
                    swal(
                        'Endorsed',
                        'Application has been endorsed',
                        'success'
                    )
                    vm.$refs.to_be_endorsed_datatable.vmDataTable.draw();
                }, (error) => {

                });
            },(error) => {

            });
        },
        declineEndorsement: function(uuid,mooring_name){
            let vm = this
            swal({
                title: "Decline approval",
                text: "Are you sure you want to decline approval?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Decline Approval',
                confirmButtonColor:'#dc3545'
            }).then(() => {
                vm.$http.get('/aua_for_endorsement/' + uuid + '/decline/?mooring_name=' + mooring_name)
                .then((response) => {
                    swal(
                        'Declined',
                        'Application has been declined',
                        'success'
                    )
                    vm.$refs.to_be_endorsed_datatable.vmDataTable.draw();
                }, (error) => {

                });
            },(error) => {

            });

        },
    },
    mounted: function(){
        this.$nextTick(() => {
            this.addEventListeners();
        })
    }
}
</script>
