<template>
    <transition>
        <div v-if="shown" class="panel panel-default">
            <div class="panel-body">
                <div class="delete_arrival_icon">
                    <i class="fa fa-times-circle fa-2x" style="color:coral" @click="delete_arrival_icon_clicked"></i>
                </div>

                <div class="row form-group">
                    <label for="" class="col-sm-2 control-label">Arrival</label>
                    <div class="col-sm-3 input-group date" ref="arrivalDatePicker">
                        <input type="text" class="form-control text-center" placeholder="DD/MM/YYYY"/>
                        <span class="input-group-addon">
                            <span class="glyphicon glyphicon-calendar"></span>
                        </span>
                    </div>
                </div>
                <div class="row form-group">
                    <label class="col-sm-2 control-label">Private visit</label>
                    <div class="col-sm-2">
                        <input :disabled="!radio_private_visit_enabled" type="radio" :id="radio_yes_id" :name="radio_buttons_name" :value="true" v-model="arrival.private_visit"/>
                        <label class="radio-inline control-label" :for="radio_yes_id">Yes</label>
                    </div>
                    <div class="col-sm-2">
                        <input :disabled="!radio_private_visit_enabled" type="radio" :id="radio_no_id" :name="radio_buttons_name" :value="false" v-model="arrival.private_visit"/>
                        <label class="radio-inline control-label" :for="radio_no_id">No</label>
                    </div>
                </div>

                <template v-if="arrival.private_visit">
                    <div v-if="has_aap_aup_ml" class="row">
                        <div class="col-sm-12">
                            <div><strong>You have an AAP/AUP/ML for the vessel.  Please submit the DCV Admission.</strong></div>
                        </div>
                    </div>
                    <div v-else class="row">
                        <div class="col-sm-12">
                            <div><strong>You do not have an annual admission permit, authorised user permit or mooring licence for the vessel.  Please click <a href="https://mooring-ria.dbca.wa.gov.au/admissions/ria/" target="_blank">here</a> to pay for a daily admission permit.</strong></div>
                            <div><strong>After paying for your daily admission please click Submit to complete this DCV Admission.</strong></div>
                        </div>
                    </div>
                </template>
                <template v-else>
                    <div class="row form-group">
                        <div class="col-sm-2"></div>
                        <div class="col-sm-2 text-center"><label>Landing</label></div>
                        <div class="col-sm-2 text-center"><label>Extended stay</label></div>
                        <div class="col-sm-2 text-center"><label>Not landing</label></div>
                        <div class="col-sm-2 text-center"><label>Approved events</label></div>
                        <div class="col-sm-2 text-center"><label>Fee (AU$)</label></div>
                    </div>
                    <div class="row form-group">
                        <div class="col-sm-2"><label>Number of Adults</label><br />(12 and over)</div>
                        <div class="col-sm-2">
                            <input :disabled="!column_landing_enabled" type="number" min="0" max="100" step="1" class="form-control text-center" name="adults-landing" placeholder="" v-model="arrival.adults.landing">
                        </div>
                        <div class="col-sm-2">
                            <input :disabled="!column_extended_stay_enabled" type="number" min="0" max="100" step="1" class="form-control text-center" name="adults-extended-stay" placeholder="" v-model="arrival.adults.extended_stay">
                        </div>
                        <div class="col-sm-2">
                            <input :disabled="!has_dcv_permit" type="number" min="0" max="100" step="1" class="form-control text-center" name="adults-not-landing" placeholder="" v-model="arrival.adults.not_landing">
                        </div>
                        <div class="col-sm-2">
                            <input :disabled="!column_approved_events_enabled" type="number" min="0" max="100" step="1" class="form-control text-center" name="adults-approved-events" placeholder="" v-model="arrival.adults.approved_events">
                        </div>
                        <div class="col-sm-2">
                            <div class="total_fee text-right">
                                {{ total_fee_adults }}
                            </div>
                        </div>
                    </div>
                    <div class="row form-group">
                        <div class="col-sm-2"><label>Number of Children</label><br />(4 - 12)</div>
                        <div class="col-sm-2">
                            <input :disabled="!column_landing_enabled" type="number" min="0" max="100" step="1" class="form-control text-center" name="children-landing" placeholder="" v-model="arrival.children.landing">
                        </div>
                        <div class="col-sm-2">
                            <input :disabled="!column_approved_events_enabled" type="number" min="0" max="100" step="1" class="form-control text-center" name="children-extended-stay" placeholder="" v-model="arrival.children.extended_stay">
                        </div>
                        <div class="col-sm-2">
                            <input :disabled="!has_dcv_permit" type="number" min="0" max="100" step="1" class="form-control text-center" name="children-not-landing" placeholder="" v-model="arrival.children.not_landing">
                        </div>
                        <div class="col-sm-2">
                            <input :disabled="!column_approved_events_enabled" type="number" min="0" max="100" step="1" class="form-control text-center" name="children-approved-events" placeholder="" v-model="arrival.children.approved_events">
                        </div>
                        <div class="col-sm-2">
                            <div class="total_fee text-right">
                                {{ total_fee_children }}
                            </div>
                        </div>
                    </div>
                </template>
            </div>
        </div>
    </transition>
</template>

<script>
import 'eonasdan-bootstrap-datetimepicker';
require("moment");
    //require("select2/dist/css/select2.min.css");
    //require("select2-bootstrap-theme/dist/select2-bootstrap.min.css");
    //import select2 from "select2/dist/js/select2.full.js";
require('eonasdan-bootstrap-datetimepicker/build/css/bootstrap-datetimepicker.min.css');
require('eonasdan-bootstrap-datetimepicker/build/js/bootstrap-datetimepicker.min.js');
import datatable from '@/utils/vue/datatable.vue'
import FormSection from "@/components/forms/section_toggle.vue"
import { api_endpoints, helpers } from '@/utils/hooks'
  
export default {
    name: 'DcvAdmissionArrivalPanel',
    props: {
        level: {
            type: String,
            default: 'external',
        },
        uuid: null,
        arrival: null,
        dcv_vessel: null,
        fee_configurations: null,
        column_landing_enabled: {
            type: Boolean,
            default: true,
        },
        column_extended_stay_enabled: {
            type: Boolean,
            default: true,
        },
        column_not_landing_enabled: {
            type: Boolean,
            default: false,
        },
        column_approved_events_enabled: {
            type: Boolean,
            default: true,
        },
        radio_private_visit_enabled: {
            type: Boolean,
            default: true,
        },
    },
    data() {
        let vm = this
        return {
            shown: false,  // Hidden first to make fade-in work
            paySubmitting: false,
        }
    },
    components:{
        FormSection,
    },
    watch: {

    },
    computed: {
        radio_buttons_name: function() {
            return 'private_yes_no_' + this.uuid
        },
        radio_yes_id: function() {
            return 'private_yes_' + this.uuid
        },
        radio_no_id: function() {
            return 'private_no_' + this.uuid
        },
        is_external: function() {
            return this.level == 'external'
        },
        csrf_token: function() {
          return helpers.getCookie('csrftoken')
        },
        has_dcv_permit: function() {
            if (this.arrival && this.arrival.arrival_date){
                let arrival_date = moment(this.arrival.arrival_date, 'DD/MM/YYYY')
                if (this.dcv_vessel && this.dcv_vessel.dcv_permits){
                    for (let dcv_permit of this.dcv_vessel.dcv_permits){
                        let start_date = moment(dcv_permit.start_date, 'YYYY-MM-DD')
                        let end_date = moment(dcv_permit.end_date, 'YYYY-MM-DD')
                        if (start_date <= arrival_date && arrival_date <= end_date){
                            return true
                        }
                    }
                }
            }
            if (this.arrival && this.arrival.adults){
                this.arrival.adults.not_landing = 0
            }
            if (this.arrival && this.arrival.children){
                this.arrival.children.not_landing = 0
            }
            return false
        },
        has_aap_aup_ml: function() {

            // TODO: calc

            return false
        },
        total_fee_adults: function() {
            let total_fee = 0
            let target_fee_configuration = null
            if (this.arrival.arrival_date && !this.arrival.private_visit){
                let arrival_date = moment(this.arrival.arrival_date, 'DD/MM/YYYY')
                for (let fee_configuration of this.fee_configurations){
                    let start_date = moment(fee_configuration.start_date, 'YYYY-MM-DD')
                    let end_date = moment(fee_configuration.end_date, 'YYYY-MM-DD')
                    if (start_date <= arrival_date && arrival_date <= end_date){
                        target_fee_configuration = fee_configuration
                        break
                    }
                }
                if (!target_fee_configuration){
                    return '---'
                } else {
                    for(let key in this.arrival.adults) {
                        if(this.arrival.adults.hasOwnProperty(key) ) {
                            console.log(key + ': ' + this.arrival.adults[key] );
                            console.log(target_fee_configuration.fee_items.adult[key])
                            total_fee += this.arrival.adults[key] * target_fee_configuration.fee_items.adult[key]
                        }
                    }
                    return (Math.round(total_fee * 100) / 100).toFixed(2);
                }
            } else {
                return '---'
            }
        },
        total_fee_children: function() {
            let total_fee = 0
            let target_fee_configuration = null
            if (this.arrival.arrival_date && !this.arrival.private_visit){
                let arrival_date = moment(this.arrival.arrival_date, 'DD/MM/YYYY')
                for (let fee_configuration of this.fee_configurations){
                    let start_date = moment(fee_configuration.start_date, 'YYYY-MM-DD')
                    let end_date = moment(fee_configuration.end_date, 'YYYY-MM-DD')
                    if (start_date <= arrival_date && arrival_date <= end_date){
                        target_fee_configuration = fee_configuration
                        break
                    }
                }
                if (!target_fee_configuration){
                    return '---'
                } else {
                    for(let key in this.arrival.children) {
                        if(this.arrival.children.hasOwnProperty(key) ) {
                            console.log(key + ': ' + this.arrival.children[key] );
                            console.log(target_fee_configuration.fee_items.child[key])
                            total_fee += this.arrival.children[key] * target_fee_configuration.fee_items.child[key]
                        }
                    }
                    return (Math.round(total_fee * 100) / 100).toFixed(2);
                }
            } else {
                return '---'
            }
        },
    },
    methods: {
        delete_arrival_icon_clicked: function() {
            this.shown = false
            this.$emit('delete_arrival', this.arrival.uuid)
        },
        addEventListeners: function () {
            let vm = this;
            let el_fr = $(vm.$refs.arrivalDatePicker);
            let options = {
                format: "DD/MM/YYYY",
                showClear: true ,
                useCurrent: false,
            };

            el_fr.datetimepicker(options);

            el_fr.on("dp.change", function(e) {
                let selected_date = null;
                if (e.date){
                    // Date selected
                    selected_date = e.date.format('DD/MM/YYYY')  // e.date is moment object
                    vm.arrival.arrival_date = selected_date;
                } else {
                    // Date not selected
                    vm.arrival.arrival_date = selected_date;
                }
            });
        },
    },
    mounted: function () {
        this.shown = true  // Show the panel once
    },
    created: function() {

        this.$nextTick(() => {
            this.addEventListeners();
        });
    },
}
</script>

<style>
.mb-1 {
    margin: 0 0 1em 0;
}
.mb-2 {
    margin: 0 0 2em 0;
}
.panel-body {
    position: relative;
}
.delete_arrival_icon {
    position: absolute;
    top: 0;
    right: 0;
    cursor: pointer;
}
.v-enter, .v-leave-to {
    opacity: 0;
}
.v-enter-active, .v-leave-active {
    transition: 0.8s;
}
.v-enter-to, .v-leave {
    opacity: 1;
}
.total_fee {
    padding-right: 1em;
}
</style>
