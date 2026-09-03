<template lang="html">
    <div id="approvalHistory">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                    <div class="col-sm-12">
                        <div class="form-group">
                            <div class="row">
                                <div v-if="approvalId" class="col-lg-12">
                                    <datatable
                                        ref="history_datatable"
                                        :id="datatable_id"
                                        :dtOptions="datatable_options"
                                        :dtHeaders="datatable_headers"
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div slot="footer">
                <button type="button" class="btn btn-default" @click="ok">Ok</button>
                <button type="button" class="btn btn-default" @click="cancel">Cancel</button>
            </div>
        </modal>
    </div>
</template>

<script>
import modal from '@vue-utils/bootstrap-modal.vue'
import alert from '@vue-utils/alert.vue'
import { helpers, api_endpoints, constants } from "@/utils/hooks.js"
import datatable from '@/utils/vue/datatable.vue'

export default {
    name:'approvalHistory',
    components:{
        modal,
        alert,
        datatable,
    },
    props:{
        approvalId: {
            type: Number,
            required: true,
        },
    },
    data:function () {
        let vm = this;
        return {
            datatable_id: 'history-datatable-' + vm._uid,
            approvalDetails: {
                approvalLodgementNumber: null,
            },
            messageDetails: '',
            ccEmail: '',
            isModalOpen:false,
            validation_form: null,
            errors: false,
            errorString: '',
            successString: '',
            success:false,
        }
    },
    computed: {
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        title: function(){
            let title = "History for ";
            if (this.approvalDetails && this.approvalDetails.approvalLodgementNumber) {
                title += this.approvalDetails.approvalType + ' ';
                title += this.approvalDetails.approvalLodgementNumber;
            }
            return title;
        },
        csrf_token: function() {
          return helpers.getCookie('csrftoken')
        },
        datatable_headers: function(){
            return ['id', 'Lodgement Number', 'Type', 'Sticker Number/s', 'Holder', 'Status', 'Issue Date', 'Reason', 'Approval Letter']
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
                    return full.approval_lodgement_number
                },
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
                    return full.approval_type_description;
                }
            }
        },
        column_sticker_numbers: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.sticker_numbers;
                }
            }
        },

        column_holder: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.holder;
                }
            }
        },
        column_approval_status: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.approval_status;
                }
            }
        },
        column_start_date: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.start_date_str
                }
            }
        },
        column_reason: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return full.reason;
                }
            }
        },
        column_approval_letter: function(){
            return {
                data: "id",
                orderable: true,
                searchable: true,
                visible: true,
                'render': function(row, type, full){
                    return `<div><a href='${full.approval_letter}' target='_blank'><i style='color:red;' class='fa fa-file-pdf-o'></i></a></div>`;
                }
            }
        },

        datatable_options: function(){
            let vm = this
            let columns = [
                vm.column_id,
                vm.column_lodgement_number,
                vm.column_type,
                vm.column_sticker_numbers,
                vm.column_holder,
                vm.column_approval_status,
                vm.column_start_date,
                vm.column_reason,
                vm.column_approval_letter,
            ]

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
                searching: true,
                ordering: true,
                order: [[0, 'desc']],
                ajax: {
                    "url": api_endpoints.lookupApprovalHistory(this.approvalId),
                    "dataSrc": 'data',
                },
                dom: 'lBfrtip',
                buttons:[ ],
                columns: columns,
                processing: true,
            }
        }

    },
    methods:{
        ok: async function() {
            this.close()
        },
        cancel:function () {
            this.close()
        },
        close: function () {
            this.isModalOpen = false;
            this.errors = false;
            $('.has-error').removeClass('has-error');
        },
        fetchApprovalDetails: async function() {
            const res = await this.$http.get(api_endpoints.lookupApprovalDetails(this.approvalId));
            if (res.ok) {
                this.approvalDetails = Object.assign({}, res.body);
            }
        },

    },
    created: function() {
        this.$nextTick(()=>{
            this.fetchApprovalDetails();
        });
    },
}
</script>