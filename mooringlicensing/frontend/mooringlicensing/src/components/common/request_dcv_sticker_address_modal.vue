<template>
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
                                <th scope="col">Status</th>
                                <th scope="col">Postal Address</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="sticker in stickers" :key="sticker.id">
                                <td><input v-if="sticker.status.code == 'ready' || sticker.status.code == 'not_yet_ready'" type="checkbox" v-model="sticker.checked" /></td>
                                <td v-if="sticker.number">{{ sticker.number }}</td>
                                <td v-else>Not Assigned</td>
                                <td>{{ sticker.vessel.rego_no }}</td>
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
                    <label for="" class="col-sm-3 control-label">Street</label>
                    <div class="col-sm-6">
                        <input type="text" class="form-control" name="street" placeholder="" v-model="new_postal_address_line1">
                    </div>
                </div>
                <div class="row form-group">
                    <label for="" class="col-sm-3 control-label" >Town/Suburb</label>
                    <div class="col-sm-6">
                        <input type="text" class="form-control" name="surburb" placeholder="" v-model="new_postal_address_locality">
                    </div>
                </div>
                <div class="row form-group">
                    <label for="" class="col-sm-3 control-label">State</label>
                    <div class="col-sm-2">
                        <input type="text" class="form-control" name="state" placeholder="" v-model="new_postal_address_state">
                    </div>
                    <label for="" class="col-sm-2 control-label">Postcode</label>
                    <div class="col-sm-2">
                        <input type="text" class="form-control" name="postcode" placeholder="" v-model="new_postal_address_postcode">
                    </div>
                </div>
                <div class="row form-group">
                    <label for="" class="col-sm-3 control-label" >Country</label>
                    <div class="col-sm-4">
                        <select v-model="new_postal_address_country" class="form-control" name="country">
                            <option selected></option>
                            <option v-for="c in countries" :value="c.code">{{ c.name }}</option>
                        </select>
                    </div>
                </div>
            </div>
            <div slot="footer">
                <div class="row">
                    <div class="col-md-12">
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
    name:'RequestDCVStickerAddressModal',
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
        return {
            dcv_permit_id: null,
            stickers: [],
            isModalOpen:false,
            action: '',
            processing: false,
            countries: [],
            errors: false,
            errorString: '',
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
        dcv_permit_id: async function(){
            let vm = this
            // Whenever dcv_permit_id is changed, update this.stickers
            if (vm.dcv_permit_id){
                const ret = await vm.$http.get(helpers.add_endpoint_json('/api/internal_dcv_permit/', vm.dcv_permit_id + '/stickers'))
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
            for (let sticker of this.stickers){
                if (sticker.checked === true){
                    return true
                }
            }
            return false
        },
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        title: function() {
            return 'Update Sticker Address'
        },
    },
    methods:{
        ok:function () {
            let vm =this;
            vm.errors = false
            vm.processing = true
            vm.$emit("sendData", {
                "dcv_permit_id": vm.dcv_permit_id,
                "stickers": vm.stickers,
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
            this.errors = false
            this.processing = false
            this.dcv_permit_id = null
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
}
</script>