<template>
    <div class="container" id="externalDash">
        <FormSection label="Select Applicant" v-if="is_internal">
            <div>
                <div>
                    <label class="col-sm-3">Applicant</label>
                    <div class="col-sm-6">
                        <select 
                            id="person_lookup"  
                            name="person_lookup"  
                            ref="person_lookup" 
                            class="form-control" 
                        />
                    </div>
                </div>
            </div>
        </FormSection>
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
                <label for="" class="col-sm-3 control-label">Season</label>
                <div class="col-sm-6">
                    <select class="form-control" v-model="dcv_permit.season">
                        <option value=""></option>
                        <option v-for="season in season_options" :value="season">{{ season.name }}</option>
                    </select>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Unique Vessel Identifier (UVI)</label>
                <div class="col-sm-9">
                    <select :disabled="readonly" id="vessel_search" name="vessel_registration" ref="dcv_vessel_rego_nos" class="form-control" style="width: 40%">
                    </select>
                </div>
            </div>
            <div class="row form-group">
                <label for="" class="col-sm-3 control-label">Vessel name</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" name="vessel_name" placeholder="" v-model="dcv_permit.dcv_vessel.vessel_name">
                </div>
            </div>
            <div class="row form-group">
                            <label for="" class="col-sm-3 control-label" >
                                <strong>
                                Postal Address
                                </strong>
                            </label>
                            <div class="col-sm-6">
                            <select v-model="dcv_permit.postal_address" class="form-control">
                                <option selected disabled hidden value>Select postal address...</option>
                                <option v-for="option in postal_addresses" :value="option" :key="option.id">
                                    {{ option.line1 }}, {{ option.locality }}, {{ option.state }}, {{ option.postcode }}, {{ option.country }}
                                </option>
                                
                            </select>
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
import FormSection from "@/components/forms/section_toggle.vue"
import { api_endpoints, helpers } from '@/utils/hooks'

import "select2/dist/css/select2.min.css";
import "select2-bootstrap-theme/dist/select2-bootstrap.min.css";

export default {
    name: 'DcvTablePage',
    data() {
        let vm = this;
        return {
            dcv_permit: {
                id: null,
                applicant: '',
                organisation: '',
                abn_acn: '',
                season: null,
                dcv_vessel: {
                    id: null,
                    rego_no: '',
                    vessel_name: '',
                },
                postal_address: null,
            },
            paySubmitting: false,
            season_options: [],
            postal_addresses: [],
        }
    },
    props: {
        readonly:{
            type: Boolean,
            default: false,
        },
        is_internal: {
            type: Boolean,
            required: false,
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
        initialisePersonLookup: function(){
            let vm = this;
            $(vm.$refs.person_lookup).select2({
                minimumInputLength: 2,
                "theme": "bootstrap",
                allowClear: true,
                placeholder:"Select Person",
                pagination: true,
                ajax: {
                    url: api_endpoints.person_lookup,
                    dataType: 'json',
                    data: function(params) {
                        return {
                            search_term: params.term,
                            page_number: params.page || 1,
                            type: 'public',
                        }
                    },
                    processResults: function(data){
                        return {
                            'results': data.results,
                            'pagination': {
                                'more': data.pagination.more
                            }
                        }
                    },
                },
            }).
            on("select2:select", function (e) {
                vm.dcv_permit.applicant = e.params.data.ledger_id;
                if(e.params.data.postal_address_list){
                    vm.postal_addresses = e.params.data.postal_address_list
                }
            }).
            on("select2:unselect",function (e) {
                vm.dcv_permit.applicant  = null;
            }).
            on("select2:open",function (e) {
                const searchField = $('[aria-controls="select2-person_lookup-results"]')
                // move focus to select2 field
                searchField[0].focus();
            });
        },
        populatePostalAddresses: async function(){
            let vm = this;
            try{
                const res = await this.$http.get(api_endpoints.profile);
                vm.postal_addresses = res.body.postal_address_list
                return res;
            } catch(err){
                this.processError(err)
            }
            
        },
        lookupDcvVessel: async function(id) {
            try {
                const res = await this.$http.get(api_endpoints.lookupDcvVessel(id));
                const vesselData = res.body;
                console.log('existing dcv_vessel: ')
                console.log(vesselData);
                    if (vesselData && vesselData.rego_no) {
                        this.dcv_permit.dcv_vessel = Object.assign({}, vesselData);
                        console.log(this.dcv_permit.dcv_vessel)
                    }
            } catch(e) {
                if (e.status == '400'){
                    //empty the search
                    var searchValue = "";
                    var err = "The selected vessel is already listed with RIA under another owner";
                    swal({
                        title: 'Selection Error',
                        text: err,
                        type: "error",
                    })
                    
                    var option = new Option(searchValue, searchValue, true, true);
                    $(this.$refs.dcv_vessel_rego_nos).append(option).trigger('change');                    
                }
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
                var selected = $(e.currentTarget);
                let id = selected.val();
                vm.$nextTick(() => {
                    if (e.params.data.isNew) {
                        // fetch the selected vessel from the backend
                        id = vm.validateRegoNo(id);
                        vm.dcv_permit.dcv_vessel =
                        {
                            id: id,
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
                var selected = $(e.currentTarget);
                vm.dcv_permit.dcv_vessel = Object.assign({},
                    {
                        id: null,
                        rego_no: '',
                        vessel_name: '',
                    }
                );
                $(vm.$refs.dcv_vessel_rego_nos).empty().trigger('change')
            }).
            on("select2:open",function (e) {
                const searchField = $(".select2-search__field")
                // move focus to select2 field
                searchField[0].focus();
                // prevent spacebar from being used
                searchField.on("keydown",function (e) {
                    if ([32,].includes(e.which)) {
                        e.preventDefault();
                        return false;
                    }
                });
            });
        },

        pay_and_submit: function(){
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
                },
                (res)=>{
                    this.paySubmitting = false
                },
            )
        },
        save_and_pay: async function() {
            try{
                let res;
                if(this.is_internal){
                    res = await this.save(false, '/api/internal_dcv_permit/')
                }
                else{
                    res = await this.save(false, '/api/dcv_permit/')
                }
                this.dcv_permit.id = res.body.id
                await helpers.post_and_redirect(this.dcv_permit_fee_url, {'csrfmiddlewaretoken' : this.csrf_token});
                this.paySubmitting = false
            } catch(err) {
                this.processError(err)
                this.paySubmitting = false
            }
        },
        processError: async function(err){
            console.log({err})
            let errorText = '';
            if (err.hasOwnProperty('body')){
                if (err.body.hasOwnProperty('non_field_errors')) {
                    // When non field errors raised
                    for (let i=0; i<err.body.non_field_errors.length; i++){
                        errorText += err.body.non_field_errors[i] + '<br />'
                    }
                } else if(Array.isArray(err.body)) {
                    // When serializers.ValidationError raised
                    for (let i=0; i<err.body.length; i++){
                        errorText += err.body[i] + '<br />'
                    }
                } else {
                    // When field errors raised
                    for (let field_name in err.body){
                        if (err.body.hasOwnProperty(field_name)){
                            for (let j=0; j<err.body[field_name].length; j++){
                                errorText += err.body[field_name][j] + '<br />'
                            }
                        }
                    }
                }
                await swal("Error", errorText, "error")
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
                console.log(res)
                return res;
            } catch(err){
                this.processError(err)
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
        if (this.is_internal) {
            //must select user to load for
            this.$nextTick(async () => {
                this.initialisePersonLookup();
            });
        }
        else {  
            this.populatePostalAddresses();
        }
    },
    created: function() {
        this.fetchFilterLists()
    },
}
</script>
