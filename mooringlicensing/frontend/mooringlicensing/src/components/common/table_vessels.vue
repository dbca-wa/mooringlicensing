<template>
    <div>
        <div class="row">
            <div class="col-sm-10">
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
            :level="level"
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
import { api_endpoints } from '@/utils/hooks'

export default {
    name: 'TableVessels',
    props: {
        target_email_user_id: {
            type: Number,
            required: false,
            default: 0,
        },
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
            recordSaleId: null,
            uuid: 0,
            // Datatable settings
            datatable_headers: ['Name', 'Registration', 'Length', 'Draft', 'Type', 'Owner', 'Sale date', 'Action'],
            datatable_options: {
                autoWidth: true,
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: false,
                scrollX: true,
                fixedColumns: {
                    leftColumns: 1,
                    rightColumns: 1
                },
                searching: true,
                ajax: {
                    "url": api_endpoints.vessel_internal_list + '?format=datatables&target_email_user_id=' + vm.target_email_user_id,
                    "dataSrc": 'data',
                },
                dom: 'lBfrtip',
                buttons:[],
                columns: [
                    {
                        data: "vessel_details.vessel_name",
                        orderable: false,
                        searchable: false,
                        visible: true,
                    },
                    {
                        data: "vessel_details.rego_no",
                        orderable: true,
                        searchable: true,
                        visible: true,
                    },
                    {
                        data: "vessel_details.vessel_length",
                        orderable: true,
                        searchable: true,
                        visible: true,
                    },
                    {
                        data: "vessel_details.vessel_draft",
                        orderable: true,
                        searchable: true,
                        visible: true,
                    },
                    {
                        data: "vessel_details.vessel_type",
                        orderable: true,
                        searchable: true,
                        visible: true,
                    },
                    {
                        data: "owner_name",
                        orderable: true,
                        searchable: true,
                        visible: true,
                    },
                    {
                        data: "sale_date",
                        orderable: true,
                        searchable: true,
                        visible: true,
                    },

                    {
                        data: "id",
                        orderable: true,
                        searchable: true,
                        visible: true,
                        'render': function(row, type, full){
                            let links = '';
                            // internal/external view
                            if (vm.level === 'internal') {
                                links += `<a href='/internal/vesselownership/${full.id}'>View</a><br/>`;
                            } else {
                                links += `<a href='/external/vesselownership/${full.id}'>View</a><br/>`;
                            }
                            // record sale
                            if (!full.sale_date) {
                                links += full.record_sale_link;
                            }
                            return links
                        }
                    },
                ],
                processing: true,
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
        adjust_vessel_table: function() {
            let vm = this;
            setTimeout(function () {
                vm.adjust_table_width();
            }, 200);
        },
        adjust_table_width: function() {
            let vm = this;
            vm.$refs.vessels_datatable.vmDataTable.columns.adjust().responsive.recalc();
        },
        closeModal: function() {
            this.uuid++;
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
            table.on('click', 'a[data-id]', async function(e) {
                e.preventDefault();
                var id = $(this).attr('data-id');
                vm.recordSaleId = parseInt(id);
                vm.openSaleModal();
            });
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

