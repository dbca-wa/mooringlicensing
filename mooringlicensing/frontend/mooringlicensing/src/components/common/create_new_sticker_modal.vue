<template lang="html">
    <div id="change-contact">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <alert :show.sync="showError" type="danger"><strong>{{ errorString }}</strong></alert>
                <alert v-if="missing_sticker_message" type="warning"><strong>{{ missing_sticker_message }}</strong></alert>
                <div v-if="!replacementFee" class="row form-group">
                    <label class="col-sm-2 control-label">Mailed Date</label>
                    <div class="col-sm-3">
                        <div class="input-group date" ref="mailedDatePicker">
                            <input type="text" class="form-control text-center" placeholder="DD/MM/YYYY" id="mailed_date_elem"/>
                            <span class="input-group-addon">
                                <span class="glyphicon glyphicon-calendar"></span>
                            </span>
                        </div>
                    </div>
                </div>    
                <div class="row form-group">
                    <label class="col-sm-5 control-label" for="change_sticker_address">Change Sticker Address</label>
                    <div class="col-md-6">
                        <input type="checkbox" v-model="change_sticker_address" />
                    </div>
                </div>
                <div v-if="change_sticker_address" class="row form-group">
                    <label for="" class="col-sm-3 control-label">Street</label>
                    <div class="col-sm-6">
                        <input type="text" class="form-control" name="street" placeholder="" v-model="postal_address_line1">
                    </div>
                </div>
                <div v-if="change_sticker_address" class="row form-group">
                    <label for="" class="col-sm-3 control-label" >Town/Suburb</label>
                    <div class="col-sm-6">
                        <input type="text" class="form-control" name="surburb" placeholder="" v-model="postal_address_locality">
                    </div>
                </div>
                <div v-if="change_sticker_address" class="row form-group">
                    <label for="" class="col-sm-3 control-label">State</label>
                    <div class="col-sm-2">
                        <input type="text" class="form-control" name="state" placeholder="" v-model="postal_address_state">
                    </div>
                    <label for="" class="col-sm-2 control-label">Postcode</label>
                    <div class="col-sm-2">
                        <input type="text" class="form-control" name="postcode" placeholder="" v-model="postal_address_postcode">
                    </div>
                </div>
                <div v-if="change_sticker_address" class="row form-group">
                    <label for="" class="col-sm-3 control-label" >Country</label>
                    <div class="col-sm-4">
                        <select v-model="postal_address_country" class="form-control" name="country">
                            <option selected></option>
                            <option v-for="c in countries" :value="c.code">{{ c.name }}</option>
                        </select>
                    </div>
                </div>
                <div v-if="replacementFee" class="row form-group">
                    <label class="col-sm-2 control-label" for="reason">Reason</label>
                    <div class="col-sm-9">
                        <textarea class="col-sm-9 form-control" name="reason" v-model="details.reason"></textarea>
                    </div>
                </div>
            </div>
            <div slot="footer">
                <div class="row">
                    <div class="col-md-7" v-if="replacementFee">
                        <span v-if="is_internal"><strong><input type="checkbox" v-model="waive_the_fee" /> Waive the fee</strong></span>
                    </div>
                    <div class="col-md-5">
                        <span v-if="replacementFee"><strong>Sticker replacement cost ${{ total_fee }}</strong></span>
                        <button type="button" v-if="processing" disabled class="btn btn-default" @click="ok"><i class="fa fa-spinner fa-spin"></i> Processing</button>
                        <button type="button" v-else class="btn btn-default" @click="ok" :disabled="!okButtonEnabled">Ok</button>
                        <button type="button" class="btn btn-default" @click="cancel">Cancel</button>
                    </div>
                </div>
            </div>
        </modal>
    </div>
</template>

<script>
import modal from '@vue-utils/bootstrap-modal.vue'
import alert from '@vue-utils/alert.vue'
import { api_endpoints } from "@/utils/hooks.js"

export default {
    name:'CreateNewStickerModal',
    components:{
        modal,
        alert,
    },
    data:function () {
        let vm = this;
        return {
            details: vm.getDefaultDetails(),
            approval_id: null,
            isModalOpen:false,
            processing: false,
            replacementFee: false,
            fee_item: null,
            waive_the_fee: false,
            countries: [],
            errors: false,
            mailed_date: null,
            errorString: '',
            change_sticker_address: false,
            postal_address_line1: '',
            postal_address_line2: '',
            postal_address_line3: '',
            postal_address_locality: '',
            postal_address_state: '',
            postal_address_country: '',
            postal_address_postcode: '',
            missing_sticker_message: '',
        }
    },
    props:{
        is_internal: {
            type: Boolean,
            default: false,
        },
    },
    computed: {
        okButtonEnabled: function(){
            if (this.details.reason){
                return true
            }
            return false
        },
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        title: function() {
            return 'Create New Sticker'
        },
        total_fee: function() {
            let vm = this
            let amount = 0

            if (!vm.waive_the_fee){
                amount = vm.fee_item.amount;
            }

            return amount
        },
    },
    methods:{
        getDefaultDetails: function(){
            return {
                reason: '',
                date_of_lost_sticker: null,
                date_of_returned_sticker: null,
            }
        },
        ok:function () {
            let vm =this;
            vm.errors = false
            vm.processing = true
            vm.$emit("sendData", {
                "waive_the_fee": vm.waive_the_fee,
                "approval_id": vm.approval_id,
                "mailed_date": vm.mailed_date,
                "change_sticker_address": vm.change_sticker_address,
                "postal_address_line1": vm.postal_address_line1,
                "postal_address_line2": vm.postal_address_line2,
                "postal_address_line3": vm.postal_address_line3,
                "postal_address_locality": vm.postal_address_locality,
                "postal_address_state": vm.postal_address_state,
                "postal_address_country": vm.postal_address_country,
                "postal_address_postcode": vm.postal_address_postcode,
                "details": vm.details,
            })
        },
        cancel:function () {
            this.close();
        },
        close:function () {
            this.details = this.getDefaultDetails()
            this.isModalOpen = false
            this.errors = false
            this.processing = false
            this.approval_id = null
        },
        addEventListeners: function () {
            let vm = this;
            let options = {
                format: "DD/MM/YYYY",
                showClear: true ,
                useCurrent: false,
            };

            // Mailed Date
            let el_mailed = $(vm.$refs.mailedDatePicker);
            el_mailed.datetimepicker(options);
            el_mailed.on("dp.change", function(e) {
                let selected_date = null;
                if (e.date){
                    selected_date = e.date.format('DD/MM/YYYY')
                }
                vm.mailed_date = selected_date;
            });
        },
        fetchData: function(){
            let vm = this

            vm.$http.get(api_endpoints.fee_item_sticker_replacement).then(
                (response) => {
                    vm.fee_item = response.body
                },
                (error) => {
                    console.log(error)
                }
            )
        },
        fetchCountries: function () {
            let vm = this;
            vm.$http.get(api_endpoints.countries).then((response) => {
                vm.countries = response.body;
            });
        },
    },
    mounted: function () {
        this.fetchCountries();
    },
    created:function () {
        this.fetchData();
        this.$nextTick(() => {
            this.addEventListeners();
        });
    }
}
</script>