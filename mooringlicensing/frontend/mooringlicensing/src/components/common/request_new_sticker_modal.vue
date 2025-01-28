<template lang="html">
    <div id="change-contact">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <alert :show.sync="showError" type="danger"><strong>{{ errorString }}</strong></alert>
                <div class="row form-group">
                    <table class="table table-striped table-bordered">
                        <thead>
                            <tr>
                                <th scope="col"></th>
                                <th scope="col">Number</th>
                                <th scope="col">Vessel</th>
                                <th scope="col">Mooring</th>
                                <th scope="col">Status</th>
                                <th scope="col">Postal Address</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="sticker in stickers" :key="sticker.id">
                                <td><input v-if="sticker.status.code == 'current'" type="checkbox" v-model="sticker.checked" /></td>
                                <td v-if="sticker.number">{{ sticker.number }}</td>
                                <td v-else>Not Assigned</td>
                                <td>{{ sticker.vessel.rego_no }}</td>
                                <td>
                                    <span v-for="mooring in sticker.moorings">
                                        {{ mooring.name }} ({{ mooring.mooring_bay_name }})
                                    </span>
                                </td>
                                <td>{{ sticker.status.display }}</td>
                                <td>
                                    <span>{{sticker.postal_address_line1}}</span>
                                    <span>{{sticker.postal_address_locality}}</span>
                                    <span>{{sticker.postal_address_state}}</span>
                                    <span>{{sticker.postal_address_country}}</span>
                                    <span>{{sticker.postal_address_postcode}}</span>
                                </td>
                            </tr>
                        </tbody>
                    </table>
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
                        <input type="text" class="form-control" name="street" placeholder="" v-model="new_postal_address_line1">
                    </div>
                </div>
                <div v-if="change_sticker_address" class="row form-group">
                    <label for="" class="col-sm-3 control-label" >Town/Suburb</label>
                    <div class="col-sm-6">
                        <input type="text" class="form-control" name="surburb" placeholder="" v-model="new_postal_address_locality">
                    </div>
                </div>
                <div v-if="change_sticker_address" class="row form-group">
                    <label for="" class="col-sm-3 control-label">State</label>
                    <div class="col-sm-2">
                        <input type="text" class="form-control" name="state" placeholder="" v-model="new_postal_address_state">
                    </div>
                    <label for="" class="col-sm-2 control-label">Postcode</label>
                    <div class="col-sm-2">
                        <input type="text" class="form-control" name="postcode" placeholder="" v-model="new_postal_address_postcode">
                    </div>
                </div>
                <div v-if="change_sticker_address" class="row form-group">
                    <label for="" class="col-sm-3 control-label" >Country</label>
                    <div class="col-sm-4">
                        <select v-model="new_postal_address_country" class="form-control" name="country">
                            <option selected></option>
                            <option v-for="c in countries" :value="c.code">{{ c.name }}</option>
                        </select>
                    </div>
                </div>
                <div class="row form-group">
                    <label class="col-sm-2 control-label" for="reason">Reason</label>
                    <div class="col-sm-9">
                        <textarea class="col-sm-9 form-control" name="reason" v-model="details.reason"></textarea>
                    </div>
                </div>
            </div>
            <div slot="footer">
                <div class="row">
                    <div class="col-md-7">
                        <span v-if="is_internal"><strong><input type="checkbox" v-model="waive_the_fee" /> Waive the fee</strong></span>
                    </div>
                    <div class="col-md-5">
                        <span><strong>Sticker replacement cost ${{ total_fee }}</strong></span>
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
import { helpers, api_endpoints } from "@/utils/hooks.js"

export default {
    name:'RequestNewStickerModal',
    components:{
        modal,
        alert,
    },
    props:{
        is_internal: {
            type: Boolean,
            default: false,
        }
    },
    data:function () {
        let vm = this;
        return {
            approval_id: null,
            stickers: [],
            isModalOpen:false,
            action: '',
            details: vm.getDefaultDetails(),
            processing: false,
            fee_item: null,
            countries: [],
            errors: false,
            errorString: '',
            waive_the_fee: false,
            change_sticker_address: false,
            new_postal_address_line1: '',
            new_postal_address_line2: '',
            new_postal_address_line3: '',
            new_postal_address_locality: '',
            new_postal_address_state: '',
            new_postal_address_country: '',
            new_postal_address_postcode: '',
        }
    },
    watch: {
        approval_id: async function(){
            let vm = this
            // Whenever approval_id is changed, update this.stickers
            if (vm.approval_id){
                const ret = await vm.$http.get(helpers.add_endpoint_json(api_endpoints.approvals, vm.approval_id + '/stickers'))
                for (let sticker of ret.body.stickers){
                    sticker.checked = false
                }
                vm.stickers = ret.body.stickers
                console.log('vm.stickers')
                console.log(vm.stickers)

            } else {
                vm.stickers = []
            }
        }
    },
    computed: {
        okButtonEnabled: function(){
            if (this.details.reason){
                for (let sticker of this.stickers){
                    if (sticker.checked === true){
                        return true
                    }
                }
            }
            return false
        },
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        title: function() {
            return 'New Sticker'
        },
        total_fee: function() {
            let vm = this
            let amount = 0

            if (!vm.waive_the_fee){
                for (let sticker of this.stickers){
                    if (sticker.checked){
                        amount += vm.fee_item.amount
                    }
                }
            }

            return amount
        }
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
                "details": vm.details,
                "approval_id": vm.approval_id,
                "stickers": vm.stickers,
                "waive_the_fee": vm.waive_the_fee,
                "change_sticker_address": vm.change_sticker_address,
                "new_postal_address_line1": vm.new_postal_address_line1,
                "new_postal_address_line2": vm.new_postal_address_line2,
                "new_postal_address_line3": vm.new_postal_address_line3,
                "new_postal_address_locality": vm.new_postal_address_locality,
                "new_postal_address_state": vm.new_postal_address_state,
                "new_postal_address_country": vm.new_postal_address_country,
                "new_postal_address_postcode": vm.new_postal_address_postcode,
            })
        },
        cancel:function () {
            this.close();
        },
        close:function () {
            this.isModalOpen = false
            this.details = this.getDefaultDetails()
            $('#returned_date_elem').val('')
            $('#lost_date_elem').val('')
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

            // Date of Lost
            let el_lost = $(vm.$refs.lostDatePicker);
            el_lost.datetimepicker(options);
            el_lost.on("dp.change", function(e) {
                let selected_date = null;
                if (e.date){
                    // Date selected
                    selected_date = e.date.format('DD/MM/YYYY')  // e.date is moment object
                    vm.details.date_of_lost_sticker = selected_date;
                } else {
                    // Date not selected
                    vm.details.date_of_lost_sticker = selected_date;
                }
            });

            // Date of Returned
            let el_returned = $(vm.$refs.returnedDatePicker)
            el_returned.datetimepicker(options);
            el_returned.on("dp.change", function(e) {
                let selected_date = null;
                if (e.date){
                    // Date selected
                    selected_date = e.date.format('DD/MM/YYYY')  // e.date is moment object
                    vm.details.date_of_returned_sticker = selected_date;
                } else {
                    // Date not selected
                    vm.details.date_of_returned_sticker = selected_date;
                }
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