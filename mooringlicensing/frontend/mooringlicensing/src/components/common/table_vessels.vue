<template>
    <div>
        <div class="row">
            <div class="col-sm-10">
            </div>
            <div class="col-sm-2">
                <button type="button" class="btn btn-primary pull-right" @click="addVessel">Add Vessel</button>
            </div>
        </div>

        <div class="row">
            <div class="col-sm-12">
                <datatable 
                    ref="vessels_datatable" 
                    id="vessels_datatable" 
                    :dtOptions="datatable_options" 
                    :dtHeaders="datatable_headers"
                />
            </div>
        </div>

        <div v-if="recordSaleId">
            <RecordSale 
            ref="record_sale" 
            :recordSaleId="recordSaleId"
            :key="recordSaleKey"
            @closeModal="closeModal"
            @refreshDatatable="refreshFromResponse"
            />
        </div>
    </div>
</template>

<script>
import datatable from '@/utils/vue/datatable.vue'
import FormSection from "@/components/forms/section_toggle.vue"
import RecordSale from '@/components/external/record_sale.vue'
import { api_endpoints, helpers } from '@/utils/hooks'

export default {
    name: 'TableVessels',
    props: {
        target_email_user_id: {
            type: Number,
            required: false,
            default: 0,
        }
    },
    data() {
        let vm = this;
        return {
            recordSaleId: null,
            uuid: 0,
            // Datatable settings
            datatable_headers: ['Name', 'Registration', 'Length', 'Draft', 'Type', 'Owner', 'Sale date', 'Action'],
            datatable_options: {
                autoWidth: false,
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                //serverSide: true,
                searching: true,
                ajax: {
                    "url": api_endpoints.vessel_internal_list + '?format=datatables&target_email_user_id=' + vm.target_email_user_id,
                    "dataSrc": 'data',

                    // adding extra GET params for Custom filtering
                    "data": function ( d ) {
                        /*
                        d.filter_application_type = vm.filterApplicationType;
                        d.filter_application_status = vm.filterApplicationStatus;
                        */
                    }
                },
                dom: 'lBfrtip',
                buttons:[
                    //{
                    //    extend: 'excel',
                    //    exportOptions: {
                    //        columns: ':visible'
                    //    }
                    //},
                    //{
                    //    extend: 'csv',
                    //    exportOptions: {
                    //        columns: ':visible'
                    //    }
                    //},
                ],
                columns: [
                    {
                        data: "vessel_details.vessel_name",
                        orderable: false,
                        searchable: false,
                        visible: true,
                        /*
                        'render': function(row, type, full){
                            return full.id
                        }
                        */
                    },
                    {
                        data: "vessel_details.rego_no",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        /*
                        'render': function(row, type, full){
                            return full.lodgement_number
                        }
                        */
                    },
                    {
                        data: "vessel_details.vessel_length",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        /*
                        'render': function(row, type, full){
                            return full.application_type_dict.description
                        }
                        */
                    },
                    {
                        data: "vessel_details.vessel_draft",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        /*
                        'render': function(row, type, full){
                            return full.proposal_type.description
                        }
                        */
                    },
                    {
                        data: "vessel_details.vessel_type",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        /*
                        'render': function(row, type, full){
                            return full.customer_status
                        }
                        */
                    },
                    {
                        data: "owner_name",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        /*
                        'render': function(row, type, full){
                            return full.customer_status
                        }
                        */
                    },
                    {
                        data: "sale_date",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        /*
                        'render': function(row, type, full){
                            return full.customer_status
                        }
                        */
                    },

                    {
                        //data: "vessel_details.vessel_id",
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            let links = '';
                            if (!full.sale_date) {
                                links += `<a href='/external/vesselownership/${full.id}'>View</a><br/>`;
                                links += full.record_sale_link;
                            }
                            return links
                        }
                    },
                ],
                processing: true,
                initComplete: function() {
                    console.log('in initComplete')
                },
            },
        }
    },
    components:{
        FormSection,
        datatable,
        RecordSale,
    },
    watch: {
    },
    computed: {
        recordSaleKey: function() {
            return `${this.recordSaleId}_${this.uuid}`
        },
    },
    methods: {
        closeModal: function() {
            this.uuid++;
        },
        addVessel: function() {
            this.$router.push({
                name: 'new-vessel'
            });
        },
        refreshFromResponse: async function(){
            await this.$refs.vessels_datatable.vmDataTable.ajax.reload();
        },
        openSaleModal: function() {
            this.$nextTick(() => {
                console.log(this.recordSaleId)
                this.$refs.record_sale.isModalOpen = true;
            });
        },
        addEventListeners: function() {
            let vm = this;
            let table = vm.$refs.vessels_datatable.vmDataTable
            /*
            table.on('processing.dt', function(e) {
            })
            */
            table.on('click', 'a[data-id]', async function(e) {
                e.preventDefault();
                var id = $(this).attr('data-id');
                //await vm.actionShortcut(id, 'issue');
                vm.recordSaleId = parseInt(id);
                vm.openSaleModal();
            });
            /*
            let recordSale = $('#record_sale_96');
            recordSale.on('click', () => {
                console.log("record sale")
            })
            */
        }
    },
    mounted: function () {
        this.$nextTick(() => {
            this.addEventListeners();
        });

    },
    created: function() {

    },
}
</script>
<style lang="css" scoped>
    button {
        width: 100%;
        height: 100%;
    }
</style>

