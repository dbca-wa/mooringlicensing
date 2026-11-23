<template>
    <div id="recordSale">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" title="Record Sale" large>
            <div class="container-fluid">
                <div class="row">
                    <form   name="recordSaleForm">
                        <alert v-model:show="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="row mb-3">
                                <div class="row">
                                    <div class="col-sm-9">
                                        Select the date you sold the vessel
                                    </div>
                                </div>
                            </div>
                            <div class="row mb-3">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="form-label float-start"  for="Name">Sale Date</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <div style="width: 70%;">
                                            <input
                                                type="date"
                                                class="form-control"
                                                name="saleDate"
                                                v-model="saleDate"
                                                :max="today"
                                            >
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
            <template v-slot:footer>

                <input v-if="is_internal" type="checkbox" v-model="noEmail" id="noEmail" />
                <label v-if="is_internal" for="noEmail">
                    &nbsp;Do not send email notification for this record of sale &nbsp;
                </label>

                <button type="button" v-if="saving" disabled class="btn btn-primary me-3" @click="ok"><i class="fa fa-spinner fa-spin"></i> Saving</button>
                <button type="button" v-else class="btn btn-primary me-2" @click="ok">Save</button>
                <button type="button" class="btn btn-secondary me-2" @click="cancel">Cancel</button>
            </template>
        </modal>
    </div>
</template>

<script>
import $ from 'jquery'
import modal from '@vue-utils/bootstrap-modal.vue'
import alert from '@vue-utils/alert.vue'
import {helpers,api_endpoints} from "@/utils/hooks.js"
export default {
    name:'Record-Sale',
    components:{
        modal,
        alert
    },
    props:{
            recordSaleId:{
                type:Number,
                required: true
            },
            level:{
                type:String,
                default: "external"
            },
    },
    data:function () {
        let vm = this;
        return {
            noEmail: false,
            isModalOpen:false,
            errors: false,
            errorString: '',
            successString: '',
            success:false,
            saving: false,
            saleDate: null,
        }
    },
    computed: {
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        is_internal: function() {
            var vm = this;
            return vm.level == "internal";
        },
        today() {
            return new Date().toISOString().split('T')[0];
        }
    },
    methods:{
        ok:function () {
            this.$nextTick(()=>{
                this.sendData();
            });
        },
        cancel:function () {
            this.close()
        },
        close:function () {
            this.isModalOpen = false;
            this.errors = false;
            $('.has-error').removeClass('has-error');
            this.saleDate = "";
            this.$emit('closeModal');
        },
        sendData: async function(){
            try {
                this.saving = true;
                const url = `${api_endpoints.vesselownership}${this.recordSaleId}/record_sale/`;
                const res = await this.$http.post(url, {
                    "sale_date": this.saleDate,
                    "no_email": this.noEmail,
                });
                if (res.ok) {
                    await swal(
                        'Saved',
                        'Your sale date has been saved',
                        'success'
                    );
                }
                this.close()
                this.saving = false;
                this.$emit('refreshDatatable');
            } catch(error) {
                this.errors = true;
                this.saving = false;
                this.errorString = helpers.apiVueResourceError(error);
            }
        },
        fetchSaleDate: async function(){
            try {
                const url = `${api_endpoints.vesselownership}${this.recordSaleId}/fetch_sale_date/`;
                const res = await this.$http.get(url);
                if (res.ok && res.body.end_date) {
                    console.log(res.body)
                    this.saleDate = res.body.end_date;
                }
            } catch(error) {
                this.errors = true;
                this.errorString = helpers.apiVueResourceError(error);
            }
        },
    },
    mounted:function async () {
        this.$nextTick(async ()=>{
            await this.fetchSaleDate();
        });
    },
    created: async function() {
    },
}
</script>