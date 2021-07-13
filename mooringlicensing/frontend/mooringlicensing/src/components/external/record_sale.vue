<template lang="html">
    <div id="recordSale">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" title="Record Sale" large>
            <div class="container-fluid">
                <div class="row">
                    <form class="form-horizontal" name="recordSaleForm">
                        <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-9">
                                        Select the date you sold the vessel
                                    </div>
                                </div>
                            </div>
                            <div class="form-group">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-left"  for="Name">Sale Date</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <div class="input-group date" ref="sale_date" style="width: 70%;">
                                            <input type="text" class="form-control" name="due_date" placeholder="DD/MM/YYYY" v-model="saleDate">
                                            <span class="input-group-addon">
                                                <span class="glyphicon glyphicon-calendar"></span>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
            <div slot="footer">
                <button type="button" v-if="saving" disabled class="btn btn-default" @click="ok"><i class="fa fa-spinner fa-spin"></i> Saving</button>
                <button type="button" v-else class="btn btn-default" @click="ok">Save</button>
                <button type="button" class="btn btn-default" @click="cancel">Cancel</button>
            </div>
        </modal>
    </div>
</template>

<script>
//import $ from 'jquery'
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
    },
    data:function () {
        let vm = this;
        return {
            isModalOpen:false,
            errors: false,
            errorString: '',
            successString: '',
            success:false,
            datepickerOptions:{
                format: 'DD/MM/YYYY',
                showClear:true,
                useCurrent:false,
                /*
                keepInvalid:true,
                allowInputToggle:true
                */
            },
            saving: false,
            saleDate: null,
        }
    },
    computed: {
        showError: function() {
            var vm = this;
            return vm.errors;
        },
    },
    /*
    watch: {
        due_date: function(){
            this.validDate = moment(this.requirement.due_date,'DD/MM/YYYY').isValid();
        },
    },
    */
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
            $(this.$refs.sale_date).data('DateTimePicker').clear();
            this.$emit('closeModal');
        },
        sendData: async function(){
            try {
                this.saving = true;
                const url = `${api_endpoints.vesselownership}${this.recordSaleId}/record_sale/`;
                const res = await this.$http.post(url, {
                    "sale_date": this.saleDate,
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
        eventListeners:function () {
            let vm = this;
            // Initialise Date Picker
            $(vm.$refs.sale_date).datetimepicker(vm.datepickerOptions);
            $(vm.$refs.sale_date).on('dp.change', function(e){
                if ($(vm.$refs.sale_date).data('DateTimePicker').date()) {
                    vm.saleDate =  e.date.format('DD/MM/YYYY');
                }
                else if ($(vm.$refs.sale_date).data('date') === "") {
                    vm.saleDate = "";
                }
             });
        },
    },
    mounted:function async () {
        this.$nextTick(async ()=>{
            await this.fetchSaleDate();
            this.eventListeners();
        });
    },
    created: async function() {
    },
}
</script>

<style lang="css">
</style>
