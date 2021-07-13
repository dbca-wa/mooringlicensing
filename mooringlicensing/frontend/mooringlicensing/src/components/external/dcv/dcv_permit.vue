<template>
    <div class="container" id="externalDash">
        <FormSection :formCollapse="false" label="DCV Permit" Index="dcv_permit">
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Organisation</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" name="organisation" placeholder="" v-model="dcv_permit.organisation">
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">ABN / ACN</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" name="abn_acn" placeholder="" v-model="dcv_permit.abn_acn">
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Year</label>
                <div class="col-sm-6">
                    <select class="form-control" v-model="dcv_permit.season">
                        <option value=""></option>
                        <option v-for="season in season_options" :value="season">{{ season.name }}</option>
                    </select>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">UVI vessel identifier</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" name="uvi_vessel_identifier" placeholder="" v-model="dcv_permit.dcv_vessel.uvi_vessel_identifier">
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel registration number</label>
                <div class="col-sm-9">
                    <select :disabled="readonly" id="vessel_search" name="vessel_registration" ref="dcv_vessel_rego_nos" class="form-control" style="width: 40%">
                    </select>
                    <!--input type="text" class="form-control" name="rego_no" placeholder="" v-model="dcv_permit.rego_no"-->
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel name</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" name="vessel_name" placeholder="" v-model="dcv_permit.dcv_vessel.vessel_name">
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
                                        <button v-if="paySubmitting" type="button" class="btn btn-primary" disabled>Pay and Submit&nbsp;<i class="fa fa-circle-o-notch fa-spin fa-fw"></i></button>
                                        <input v-else type="button" @click.prevent="pay_and_submit" class="btn btn-primary" value="Pay and Submit" :disabled="paySubmitting"/>
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
import datatable from '@/utils/vue/datatable.vue'
import FormSection from "@/components/forms/section_toggle.vue"
import { api_endpoints, helpers } from '@/utils/hooks'

var select2 = require('select2');
require("select2/dist/css/select2.min.css");
require("select2-bootstrap-theme/dist/select2-bootstrap.min.css");

export default {
    name: 'DcvTablePage',
    data() {
        let vm = this;
        return {
            dcv_permit: {
                id: null,
                organisation: '',
                abn_acn: '',
                season: null,
                //uvi_vessel_identifier: '',
                //rego_no: '',
                //vessel_name: '',
                dcv_vessel: {
                    id: null,
                    uvi_vessel_identifier: '',
                    rego_no: '',
                    vessel_name: '',
                },
            },
            paySubmitting: false,
            season_options: [],
        }
    },
    props: {
        /*
        level: {
            type: String,
            default: 'external',
        },
        */
        readonly:{
            type: Boolean,
            default: false,
        },
    },

    components:{
        FormSection,
    },
    watch: {

    },
    computed: {
        is_external: function() {
            return this.level == 'external'
        },
        csrf_token: function() {
          return helpers.getCookie('csrftoken')
        },
        dcv_permit_fee_url: function() {
          return `/dcv_permit_fee/${this.dcv_permit.id}/`
        },
    },
    methods: {
        lookupDcvVessel: async function(id) {
            console.log('in lookupDcvVessel')
            const res = await this.$http.get(api_endpoints.lookupDcvVessel(id));
            const vesselData = res.body;
            console.log('existing dcv_vessel: ')
            console.log(vesselData);
            if (vesselData && vesselData.rego_no) {
                this.dcv_permit.dcv_vessel = Object.assign({}, vesselData);
            }
        },
        validateRegoNo: function(data) {
            // force uppercase and no whitespace
            data = data.toUpperCase();
            data = data.replace(/\s/g,"");
            data = data.replace(/\W/g,"");
            return data;
        },

        initialiseSelects: function(){
            let vm = this;
            $(vm.$refs.dcv_vessel_rego_nos).select2({
                minimumInputLength: 2,
                "theme": "bootstrap",
                allowClear: true,
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
            on("select2:select",function (e) {
                console.log('in select')
                var selected = $(e.currentTarget);
                //vm.vessel.rego_no = selected.val();
                let id = selected.val();
                vm.$nextTick(() => {
                    //if (!isNew) {
                    if (e.params.data.isNew) {
                        // fetch the selected vessel from the backend
                        console.log("new");
                        id = vm.validateRegoNo(id);
                        vm.dcv_permit.dcv_vessel =
                        {
                            id: id,
                            uvi_vessel_identifier: '',
                            rego_no: id,
                            vessel_name: '',
                        }
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
                vm.dcv_permit.dcv_vessel = Object.assign({},
                    {
                        id: null,
                        uvi_vessel_identifier: '',
                        rego_no: '',
                        vessel_name: '',
                    }
                );

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
                title: "DCV Permit Application",
                text: "Are you sure you want to pay and submit for this application?",
                type: "question",
                showCancelButton: true,
                confirmButtonText: "Pay and Submit",
            }).then(
                (res)=>{
                    vm.save_and_pay();
                    this.paySubmitting = false
                },
                (res)=>{
                    this.paySubmitting = false
                },
            )
        },
        save_and_pay: async function() {
            try{
                const res = await this.save(false, '/api/dcv_permit/')
                this.dcv_permit.id = res.body.id
                await helpers.post_and_redirect(this.dcv_permit_fee_url, {'csrfmiddlewaretoken' : this.csrf_token});
            } catch(err) {
                helpers.processError(err)
            }
        },
        save: async function(withConfirm=true, url){
            try{
                const res = await this.$http.post(url, this.dcv_permit)
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
        fetchFilterLists: function(){
            let vm = this;

            // Seasons
            vm.$http.get(api_endpoints.seasons_for_dcv_dict + '?apply_page=False').then((response) => {
                vm.season_options = response.body
            },(error) => {
                console.log(error);
            })
        },
    },
    mounted: function () {
        this.$nextTick(() => {
            this.initialiseSelects()
        });
    },
    created: function() {
        this.fetchFilterLists()
    },
}
</script>
