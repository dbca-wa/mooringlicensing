<template lang="html">
    <div v-if="newAua || changeMooring || (changeMooring && noMoorings)" id="mooring_authorisation">
        <FormSection label="Mooring details" Index="mooring_authorisation">
            <div class="row form-group">
                <label for="" class="col-sm-9 control-label">Do you want to be authorised
                </label>
            </div>
            <div class="form-group">
                <div class="row">
                    <div class="col-sm-9">
                        <input :disabled="readonly" type="radio" id="site_licensee" value="site_licensee" v-model="mooringAuthPreference" required=""/>
                        <label for="site_licensee" class="control-label">By a mooring site licensee for their mooring</label>
                    </div>
                </div>
                <div class="row">
                    <div class="col-sm-9">
                        <input :disabled="readonly" type="radio" id="ria" value="ria" v-model="mooringAuthPreference" required=""/>
                        <label for="ria" class="control-label">By Rottnest Island Authority for a mooring allocated by the Authority</label>
                    </div>
                </div>
            </div>

            <div v-show="mooringAuthPreference==='site_licensee'">
                <div class="row form-group">
                    <label for="site_licensee_email" class="col-sm-3 control-label">Site licensee email</label>
                    <div class="col-sm-9">
                        <input :readonly="readonly" class="form-control" type="text" placeholder="" id="site_licensee_email" v-model="siteLicenseeEmail"/>
                    </div>
                </div>
                <div class="row form-group">
                    <label for="mooring_id" class="col-sm-3 control-label">Mooring site ID</label>
                    <div class="col-sm-9">
                        <select 
                            id="mooring_lookup"  
                            name="mooring_lookup"  
                            ref="mooring_lookup" 
                            class="form-control" 
                            style="width: 40%"
                        />
                    </div>
                </div>
                <div class="col-lg-2 pull-right" v-if="!readonly">
                    <button @click.prevent="addSiteLicensee()" class="btn btn-primary">Add</button>
                </div>
                <div class="row form-group">
                    <div class="col-sm-12">
                        <datatable
                            ref="site_licensee_datatable"
                            :id="site_licensee_datatable_id"
                            :dtOptions="datatable_options"
                            :dtHeaders="site_licensee_datatable_headers"
                            :key="site_licensee_datatable_key"
                        />
                    </div>
                </div>
            </div>

            <div v-show="mooringAuthPreference==='ria'" class="row form-group">
                <div class="col-sm-9">
                <label for="ria_draggable" class="draggable-label-class control-label">Order the bays in your preferred order with most preferred bay on top</label>
                <draggable 
                id="ria_draggable"
                :disabled="readonly" 
                :list="mooringBays"
                tag="ul"
                class="list-group col-sm-5 draggable-class"
                handle=".handle"
                >
                    <li
                        class="list-group-item"
                        v-for="mooring in mooringBays"
                        :key="mooring.name"
                    >
                        <i class="fa fa-align-justify handle"></i>
                        <span class="col-sm-1"/>
                        <span class="text">{{ mooring.name }}</span>
                    </li>
                </draggable>
                </div>
            </div>
        </FormSection>
    </div>
</template>

<script>
import FormSection from '@/components/forms/section_toggle.vue'
import datatable from '@/utils/vue/datatable.vue'
import {
  api_endpoints
}
from '@/utils/hooks'
import draggable from 'vuedraggable';

    export default {
        name:'MooringAuthorisation',
        components:{
            FormSection,
            draggable,
            datatable,
        },
        props:{
            proposal:{
                type: Object,
                required:true
            },
            readonly:{
                type: Boolean,
                default: true,
            },
            changeMooring: {
              type: Boolean,
            },
            newAua: {
              type: Boolean,
            },
            noMoorings: {
              type: Boolean,
            },
        },
        data:function () {
            let vm = this;
            return {
                mooringBays: [],
                mooringAuthPreference: null,
                siteLicenseeEmail: null,
                mooringSiteId: null,
                mooringSiteName: null,
                dragging: false,
                site_licensee_datatable_id: 'site-licensee-datatable-' + vm._uid,
                site_licensee_datatable_headers: ["Site Licensee Email", "Mooring", "Action"],
                site_licensee_datatable_key: 1,
                actioningRequest: false,
            }
        },
        computed: {
            datatable_options: function(){
                let vm = this

                let columns = [
                    {
                        data: "email",
                    },
                    {
                        data: "mooring_name",
                        'render': function(row, type, full){
                            if (full.endorsement === undefined || full.endorsement == "Not Actioned") {
                                return full.mooring_name
                            } else {
                                return full.mooring_name + " - " + full.endorsement
                            }                            
                        }
                    },
                    {
                        data: "mooring_id",
                        'render': function(row, type, full){
                            let links = '';
                            links += `<a href='/internal/moorings/${full.mooring_id}/'  target="_blank" style="cursor: pointer;">View</a><br/>`;
                            if (!vm.readonly) {
                                links += `<a onclick="window.removeSiteLicenseeMooring('${full.mooring_id}')" style="cursor: pointer;">Remove</a><br/>`;
                            }

                            if ((vm.proposal.processing_status == "Awaiting Endorsement" || vm.proposal.processing_status == "With Assessor" || vm.proposal.processing_status == "With Assessor (Requirements)") && full.endorsement !== undefined) {
                                if (full.endorsement == "Not Actioned") {
                                    links += `<a onclick="window.internalEndorse('${full.id}')" style="cursor: pointer;">Endorse on Licensee Behalf</a><br/>`;
                                    links += `<a onclick="window.internalDecline('${full.id}')" style="cursor: pointer;">Decline on Licensee Behalf</a><br/>`;
                                } else if (full.endorsement == "Declined") {
                                    links += `<a onclick="window.internalEndorse('${full.id}')" style="cursor: pointer;">Change to Endorsed</a><br/>`;
                                } else if (full.endorsement == "Endorsed") {
                                    links += `<a onclick="window.internalDecline('${full.id}')" style="cursor: pointer;">Change to Declined</a><br/>`;
                                }
                            }

                            return links;    
                        },
                    },
                ];
                let data = vm.proposal.site_licensee_moorings;

                return {
                    searching: false,
                    autoWidth: true,
                    responsive: true,
                    data: data,
                    dom: 'lBfrtip',
                    buttons: [],
                    columns: columns,
                    processing: true,
                }
            }
        },
        watch: {
            proposal: function() {
                this.$nextTick(async () => {
                    let vm = this;
                    vm.site_licensee_datatable_key++;
                })
            }
        },
        methods:{
            addSiteLicensee: function() {
                let vm = this;
                if (vm.siteLicenseeEmail && vm.mooringSiteId) {
                    let newSiteLicensee = {
                        email: vm.siteLicenseeEmail,
                        mooring_id: vm.mooringSiteId,
                        mooring_name: vm.mooringSiteName,
                    }
                    if (!vm.proposal.site_licensee_moorings.find(e => e.mooring_id === newSiteLicensee.mooring_id)) {
                        vm.proposal.site_licensee_moorings.push(newSiteLicensee);
                        vm.site_licensee_datatable_key++;
                    }
                }
            },
            internalEndorse: function(id) {
                console.log("internalEndorse", id)
                let vm = this;

                if (!vm.actioningRequest) {
                    vm.actioningRequest=true;

                    let payload = {
                        site_licensee_mooring_request_id: id,
                    }

                    return vm.$http.post(
                        "/api/proposal/"+vm.proposal.id+"/internal_endorse/", 
                        payload, {}
                    ).then((res)=>{
                        swal(
                            'Saved',
                            'Site Licensee Mooring Request Endorsed',
                            'success'
                        );                   
                        vm.$parent.$emit("updateProposal", res.body);
                        this.$nextTick(async () => {
                            vm.site_licensee_datatable_key++;
                            vm.actioningRequest=false;  
                        })        
                    },(err)=>{
                        swal({
                            title: "Please fix following errors before saving",
                            text: err.bodyText,
                            type:'error'
                        });
                        vm.actioningRequest=false;  
                    })
                }
            },
            internalDecline: function(id) {
                console.log("internalDecline", id)
                let vm = this;

                if (!vm.actioningRequest) {
                    vm.actioningRequest=true;

                    let payload = {
                        site_licensee_mooring_request_id: id,
                    }

                    return vm.$http.post(
                        "/api/proposal/"+vm.proposal.id+"/internal_decline/", 
                        payload, {}
                    ).then((res)=>{
                        swal(
                            'Saved',
                            'Site Licensee Mooring Request Declined',
                            'success'
                        );                   
                        vm.$parent.$emit("updateProposal", res.body);
                        vm.site_licensee_datatable_key++;
                        vm.actioningRequest=false;          
                    },(err)=>{
                        swal({
                            title: "Please fix following errors before saving",
                            text: err.bodyText,
                            type:'error'
                        });
                        vm.actioningRequest=false;  
                    })
                }
            },
            removeSiteLicenseeMooring: function(mooring_id) {
                let vm = this;
                vm.proposal.site_licensee_moorings.splice(
                    vm.proposal.site_licensee_moorings.findIndex(e => e.mooring_id == mooring_id),1
                )
                vm.site_licensee_datatable_key++;
            },
            fetchMooringBays: async function(){
                const response = await this.$http.get(api_endpoints.mooring_bays);
                // reorder array based on proposal.bay_preferences_numbered
                if (this.proposal.bay_preferences_numbered) {
                    let newArray = [];
                    for (let n of this.proposal.bay_preferences_numbered) {
                        const found = response.body.results.find(el => el.id === n);
                        newArray.push(found);
                    }
                    // read ordered array into Vue array
                    for (let bay of newArray) {
                        if (bay != undefined) {
                            this.mooringBays.push(bay);
                        }
                    }
                } else {
                    for (let bay of response.body.results) {
                        this.mooringBays.push(bay);
                    }
                }
            },
            initialiseMooringLookup: function(){
                let vm = this;
                $(vm.$refs.mooring_lookup).select2({
                    minimumInputLength: 2,
                    "theme": "bootstrap",
                    allowClear: true,
                    placeholder:"Select Mooring",
                    pagination: true,
                    ajax: {
                        url: api_endpoints.mooring_lookup_by_site_licensee,
                        dataType: 'json',
                        data: function(params) {
                            var query = {
                                search_term: params.term,
                                site_licensee_email: vm.siteLicenseeEmail,
                                type: 'public',
                                private_moorings: true,
                                page_number: params.page || 1,
                            }
                            return query;
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
                    var selected = $(e.currentTarget);
                    let data = e.params.data.id;
                    vm.mooringSiteId = data;
                    vm.mooringSiteName = e.params.data.text;
                }).
                on("select2:unselect",function (e) {
                    var selected = $(e.currentTarget);
                    vm.mooringSiteId = null;
                    vm.mooringSiteName = null;
                }).
                on("select2:open",function (e) {
                    const searchField = $(".select2-search__field")
                    // move focus to select2 field
                    searchField[0].focus();
                });
                vm.readMooringSiteId();
            },
            readMooringSiteId: async function() {
                let vm = this;
                if (vm.proposal.mooring_id) {
                    const res = await vm.$http.get(`${api_endpoints.mooring}${vm.proposal.mooring_id}/fetch_mooring_name`);
                    var option = new Option(res.body.name, vm.proposal.mooring_id, true, true);
                    $(vm.$refs.mooring_lookup).append(option).trigger('change');
                }
            },


        },
        mounted:function () {
            window.removeSiteLicenseeMooring = (mooring_id) => {
                this.removeSiteLicenseeMooring(mooring_id);
            };
            window.internalDecline = (id) => {
                this.internalDecline(id);
            };
            window.internalEndorse = (id) => {
                this.internalEndorse(id);
            };
            this.$nextTick(async () => {
                await this.fetchMooringBays();
                if (this.proposal.mooring_authorisation_preference) {
                    this.mooringAuthPreference = this.proposal.mooring_authorisation_preference;
                }
                this.initialiseMooringLookup();
            });

        },
    }
</script>

<style lang="css" scoped>
.handle {
    float: left;
    padding-top: 8px;
    padding-bottom: 8px;
    cursor: pointer;
}
.draggable-class {
    padding-left: 3%;
}
.draggable-label-class {
    padding-left: 3%;
    padding-bottom: 3%;
}
</style>

