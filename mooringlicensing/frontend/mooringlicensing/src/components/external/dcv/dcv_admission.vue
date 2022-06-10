<template>
    <div class="container" id="externalDash">
        <FormSection :formCollapse="false" label="DCV Admission Fees" Index="dcv_admission">
            <div class="row mb-2">
                <div class="col-sm-12">
                    <strong>Collection and remittance of admission fees is required prior to entering the Rottnest Island Reserve.  Penalties do apply for non compliance.</strong>
                </div>
            </div>
            <div class="row form-group">
                <label for="vessel_search" class="col-sm-3 control-label">Vessel registration number</label>
                <div class="col-sm-9">
                    <select :disabled="readonly" id="vessel_search" name="vessel_registration" ref="dcv_vessel_rego_nos" class="form-control" style="width: 40%">
                        <option></option>
                    </select>
                    <!--
                    <span v-if="is_valid_rego_no"><i class="fa fa-check-circle"></i></span>
                    -->
                </div>
            </div>
            <div class="row form-group">
                <label for="vessel_name" class="col-sm-3 control-label">Vessel name</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" name="vessel_name" placeholder="" v-model="dcv_admission.dcv_vessel.vessel_name">
                </div>
            </div>
            <div class="row form-group">
                <label for="skipper" class="col-sm-3 control-label">Skipper</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" name="skipper" placeholder="" v-model="dcv_admission.skipper">
                </div>
            </div>
            <div class="row form-group">
                <label for="contact_number" class="col-sm-3 control-label">Contact number</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" name="contact_number" placeholder="" v-model="dcv_admission.contact_number">
                </div>
            </div>

            <div v-if="show_dcv_organisation_fields" class="row form-group">
                <label for="" class="col-sm-3 control-label">Organisation</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" name="organisation" placeholder="" v-model="dcv_admission.organisation_name">
                </div>
            </div>

            <div v-if="show_dcv_organisation_fields" class="row form-group">
                <label for="" class="col-sm-3 control-label">ABN / ACN</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" name="abn_acn" placeholder="" v-model="dcv_admission.organisation_abn">
                </div>
            </div>

            <div v-if="show_email_fields" class="row form-group">
                <label for="email_address" class="col-sm-3 control-label">Email address</label>
                <div class="col-sm-6">
                    <input type="email" class="form-control" name="email_address" placeholder="" v-model="dcv_admission.email_address">
                </div>
            </div>
            <div v-if="show_email_fields" class="row form-group">
                <label for="email_address_confirmation" class="col-sm-3 control-label">Email address (Confirm)</label>
                <div class="col-sm-6">
                    <input type="email" class="form-control" name="email_address_confirmation" placeholder="" v-model="dcv_admission.email_address_confirmation">
                </div>
            </div>

            <template class="" id="arrival_panels" v-for="arrival in dcv_admission.arrivals">
                <PanelArrival
                    level="external"
                    :uuid="arrival.uuid"
                    :arrival="arrival"
                    @delete_arrival="delete_arrival"
                    :key="arrival.uuid"
                    :dcv_vessel="dcv_admission.dcv_vessel"
                    :fee_configurations="fee_configurations"
                    :column_approved_events_shown=false
                />
            </template>

            <div class="row">
                <div class="col-sm-12">
                    <div class="pull-right">
                        <label>Click <span @click="add_another_date_clicked" class="add_another_date_text">here</span> to add another date</label>
                    </div>
                </div>
            </div>
        </FormSection>

        <div>
            <input type="hidden" name="csrfmiddlewaretoken" :value="csrf_token"/>

            <div class="row" style="margin-bottom: 50px">
                <div  class="container">
                    <div class="row" style="margin-bottom: 50px">
                        <div class="navbar navbar-fixed-bottom"  style="background-color: #f5f5f5;">
                            <div class="navbar-inner">
                                <div class="container">
                                    <p class="pull-right" style="margin-top:5px">
                                        <input v-if="pay_submit_button_enabled" type="button" @click.prevent="pay_and_submit" class="btn btn-primary" :value="pay_submit_button_text"/>
                                        <button v-else type="button" class="btn btn-primary" disabled>{{ pay_submit_button_text }}<i v-if="paySubmitting" class="fa fa-circle-o-notch fa-spin fa-fw"></i></button>
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
//import 'eonasdan-bootstrap-datetimepicker';
import datatable from '@/utils/vue/datatable.vue'
import FormSection from "@/components/forms/section_toggle.vue"
import PanelArrival from "@/components/common/panel_dcv_admission_arrival.vue"
import { api_endpoints, helpers } from '@/utils/hooks'
import uuid from 'uuid'

var select2 = require('select2');
require("select2/dist/css/select2.min.css");
require("select2-bootstrap-theme/dist/select2-bootstrap.min.css");

export default {
    name: 'DcvAdmissionPage',
    props: {
        level: {
            type: String,
            default: 'external',
        },
        readonly:{
            type: Boolean,
            default: false,
        },
    },
    data() {
        let vm = this;
        return {
            dcv_admission: {
                id: null,
                dcv_vessel: {
                    id: null,
                    rego_no: '',
                    vessel_name: '',
                },
                email_address: '',
                email_address_confirmation: '',
                skipper: '',
                contact_number: '',
                arrivals: [
                    {
                        uuid: uuid(),
                        arrival_date: null,
                        private_visit: false,
                        adults: {
                            landing: 0,
                            extended_stay: 0,
                            not_landing: 0,
                            approved_events: 0,
                        },
                        children: {
                            landing: 0,
                            extended_stay: 0,
                            not_landing: 0,
                            approved_events: 0,
                        }
                    },
                ],
                annual_admission_permit: [],
                authorised_user_permit: [],
                mooring_licence: [],
                dcv_permit: [],
            },
            paySubmitting: false,
            fee_configurations: null,
        }
    },
    components:{
        PanelArrival,
        FormSection,
    },
    watch: {

    },
    computed: {
        pay_submit_button_enabled: function(){
            return this.valid_form
        },
        is_valid_rego_no: function(){
            if(this.dcv_admission.dcv_vessel.rego_no)
                return true
            return false
        },
        is_valid_vessel_name: function(){
            if(this.dcv_admission.dcv_vessel.vessel_name)
                return true
            return false
        },
        is_valid_skipper: function(){
            if(this.dcv_admission.skipper)
                return true
            return false
        },
        is_valid_email_address: function(){
            if(this.validateEmail(this.dcv_admission.email_address)){
                console.log('email_address: true')
                return true
            }
            console.log('email_address: false')
            return false
        },
        is_valid_email_address_confirmation: function(){
            if(this.validateEmail(this.dcv_admission.email_address_confirmation)){
                console.log('email_address_confirmation: true')
                return true
            }
            console.log('email_address_confirmation: false')
            return false
        },
        is_valid_email_addresses: function(){
            if(this.dcv_admission.email_address == this.dcv_admission.email_address_confirmation)
                return true
            return false
        },
        does_dcv_permit_exist: function(){
            if(this.dcv_admission.dcv_vessel.hasOwnProperty('dcv_permits')){
                if(this.dcv_admission.dcv_vessel.dcv_permits.length > 0){
                    return true
                }
            }
            return false
        },
        valid_form: function(){
            console.log('start validate')
            let enabled = true
            if(this.paySubmitting)
                enabled = false
            //if(!this.is_valid_rego_no)
            //    enabled = false
            if(!this.is_valid_vessel_name)
                enabled = false
            if(!this.dcv_admission.skipper)
                enabled = false
            if(!this.dcv_admission.contact_number)
                enabled = false
            if(this.is_authenticated){
                // Authenticated
            } else {
                // Not authenticated
                if(!this.does_dcv_permit_exist){
                    if(!this.is_valid_email_address)
                        enabled = false
                    if(!this.is_valid_email_address_confirmation)
                        enabled = false
                    if(!this.is_valid_email_addresses)
                        enabled = false
                }
            }
            console.log('end validate')
            return enabled
        },
        is_authenticated: function() {
            if (this.$route.fullPath.includes('external')){
                return true
            }
            return false
        },
        show_email_fields: function(){
            if (!this.is_authenticated && !this.does_dcv_permit_exist)
                return true
            return false
        },
        show_dcv_organisation_fields: function(){
            if (!this.does_dcv_permit_exist)
                return true
            return false
        },
        is_external: function() {
            return this.level == 'external'
        },
        csrf_token: function() {
          return helpers.getCookie('csrftoken')
        },
        dcv_admission_fee_url: function() {
          return `/dcv_admission_fee/${this.dcv_admission.id}/`
        },
        pay_submit_button_text: function() {
            let button_text = 'Submit'
            for (let arrival of this.dcv_admission.arrivals){
                if (!arrival.private_visit){
                    button_text = 'Pay and Submit'
                }
            }
            return button_text
        }
    },
    methods: {
        validateEmail: function(email) {
            console.log('in validateEmail')
            const re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/
            return re.test(email)
        },
        lookupDcvVessel: async function(id) {
            console.log('in lookupDcvVessel')
            const res = await this.$http.get(api_endpoints.lookupDcvVessel(id));
            const vesselData = res.body;
            console.log('existing dcv_vessel: ')
            console.log(vesselData);
            if (vesselData && vesselData.rego_no) {
                this.dcv_admission.dcv_vessel = Object.assign({}, vesselData);
            }
        },
        validateRegoNo: function(data) {
            console.log('in validateRegoNo')
            // force uppercase and no whitespace
            data = data.toUpperCase();
            data = data.replace(/\s/g,"");
            data = data.replace(/\W/g,"");
            return data;
        },

        initialiseSelects: function(){
            console.log('in initialiseSelects')
            let vm = this;
            $(vm.$refs.dcv_vessel_rego_nos).select2({
                minimumInputLength: 2,
                "theme": "bootstrap",
                //allowClear: true,
                //placeholder:"Select Vessel Registration",
                placeholder: "",
                tags: true,
                createTag: function (tag) {
                    return {
                        id: tag.term,
                        text: tag.term,
                        isNew: true,
                    };
                },
                ajax: {
                    url: api_endpoints.dcv_vessel_rego_nos,
                    dataType: 'json',
                },
                templateSelection: function(data) {
                    return vm.validateRegoNo(data.text);
                },
            }).
            on('select2:clear', function(e){
                console.log('clear')
            }).
            on("select2:select",function (e) {
                console.log('in select')
                if (!e.params.data.selected) {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log("No selection");
                    return false;
                }
                var selected = $(e.currentTarget);
                //vm.vessel.rego_no = selected.val();
                let id = selected.val();
                vm.$nextTick(() => {
                    //if (!isNew) {
                    if (e.params.data.isNew) {
                        // fetch the selected vessel from the backend
                        console.log("new");
                        id = vm.validateRegoNo(id);
                        vm.dcv_admission.dcv_vessel =
                        {
                            id: id,
                            rego_no: id,
                            vessel_name: '',
                        }
                        //vm.dcv_admission.dcv_vessel = Object.assign({},
                        //    {
                        //        rego_no: id,
                        //    });
                    } else {
                        // fetch the selected vessel from the backend
                        console.log('existing')
                        vm.lookupDcvVessel(id);
                    }
                });
            }).
            on("select2:unselect",function (e) {
                console.log('select2:unselect')
                var selected = $(e.currentTarget);
                vm.dcv_admission.dcv_vessel.rego_no = '';
                vm.dcv_admission.dcv_vessel = Object.assign({},
                    {
                        id: null,
                        rego_no: '',
                        vessel_name: '',
                    }
                );
                $(vm.$refs.dcv_vessel_rego_nos).empty().trigger('change')

                //vm.selectedRego = ''
            }).
            on("select2:open",function (e) {
                const searchField = $(".select2-search__field")
                // move focus to select2 field
                searchField[0].focus();
                // prevent spacebar from being used
                searchField.on("keydown",function (e) {
                    //console.log(e.which);
                    if ([32,].includes(e.which)) {
                        e.preventDefault();
                        return false;
                    }
                });
            });
            // read vessel.rego_no if exists on vessel.vue open
            //vm.readRegoNo();
        },
        pay_and_submit: function(){
            // pay_and_submit() --> save_and_pay() --> post_and_redirect()
            let vm = this
            vm.paySubmitting = true;

            swal({
                title: "DCV Admission",
                text: "Are you sure you want to pay and submit for this application?",
                type: "question",
                showCancelButton: true,
                confirmButtonText: vm.pay_submit_button_text,
            }).then(
                (res)=>{
                    vm.save_and_pay();
                    //this.paySubmitting = false
                },
                (res)=>{
                    this.paySubmitting = false
                },
            )
        },
        save_and_pay: async function() {
            try{
                const res = await this.save(false, '/api/dcv_admission/')
                console.log('res: ')
                console.log(res)
                this.dcv_admission.id = res.body.id
                await helpers.post_and_redirect(this.dcv_admission_fee_url, {'csrfmiddlewaretoken' : this.csrf_token});
                //this.paySubmitting = false
            } catch(err) {
                helpers.processError(err)
                this.paySubmitting = false
            }
        },
        save: async function(withConfirm=true, url){
            try{
                const res = await this.$http.post(url, this.dcv_admission)
                if (withConfirm) {
                    swal(
                        'Saved',
                        'Your application has been saved',
                        'success'
                    );
                };
                return res;
            } catch(err){
                helpers.processError(err)
            }
        },
        delete_arrival: function(uuid){
            for (let i=0; i < this.dcv_admission.arrivals.length; i++){
                if (this.dcv_admission.arrivals[i].uuid === uuid){
                    this.dcv_admission.arrivals.splice(i, 1)
                    break
                }
            }
        },
        add_another_date_clicked: function() {
            this.dcv_admission.arrivals.push(
                {
                    uuid: uuid(),
                    arrival_date: null,
                    private_visit: false,
                    adults: {
                        landing: 0,
                        extended_stay: 0,
                        not_landing: 0,
                        approved_events: 0,
                    },
                    children: {
                        landing: 0,
                        extended_stay: 0,
                        not_landing: 0,
                        approved_events: 0,
                    }
                }
            )
        },
    },
    mounted: function () {
        console.log('in mounted')
        this.$nextTick(() => {
            this.initialiseSelects()
        });
    },
    created: async function() {
        console.log('in created')
        const res = await this.$http.get(api_endpoints.fee_configurations)
        console.log(res.body)
        this.fee_configurations = res.body
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
.add_another_date_text {
    cursor: pointer;
    color: #337ab7;
}
</style>
