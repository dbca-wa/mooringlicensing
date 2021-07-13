<template lang="html">
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
                    <input :readonly="readonly" class="form-control" type="text" placeholder="" id="site_licensee_email" v-model="siteLicenseeEmail" required=""/>
                </div>
            </div>
            <div class="row form-group">
                <label for="mooring_id" class="col-sm-3 control-label">Mooring site ID</label>
                <div class="col-sm-4">
                    <select 
                        id="mooring_lookup"  
                        name="mooring_lookup"  
                        ref="mooring_lookup" 
                        class="form-control" 
                    />
                    <!--input :readonly="readonly" class="form-control" type="text" placeholder="" id="mooring_site_id" v-model="mooringSiteId" required=""/-->
                </div>
            </div>
        </div>

        <div v-show="mooringAuthPreference==='ria'" class="row form-group">
            <draggable 
            :disabled="readonly" 
            :list="mooringBays"
            tag="ul"
            class="list-group col-sm-5 draggable-class"
            handle=".handle"
            >
                <li
                    class="list-group-item"
                    v-for="(mooring, index) in mooringBays"
                    :key="mooring.name"
                >
                    <i class="fa fa-align-justify handle"></i>
                    <!--i class="fa handle"></i-->
                    <span class="col-sm-1"/>
                    <span class="text">{{ mooring.name }}</span>
                    <span class="pull-right">{{ index }}</span>
                </li>

                 

            <!--tr class="form-control" id="mooringList" v-for="(mooring, index) in mooringBays" :key="mooring.id">
                        <td scope="row">{{ index }}</td>
                        <td>{{ mooring.name }}</td>
                    </tr-->
                    <!--div class="form-control" id="mooringList" v-for="(mooring, index) in mooringBays" :key="mooring.id">
                        <span class="pull-left"> {{ mooring.name }}</span>
                        <span class="pull-right"> {{ index }}</span>
                    </div-->
            </draggable>
        </div>
    </FormSection>
</template>

<script>
import FormSection from '@/components/forms/section_toggle.vue'
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'
import draggable from 'vuedraggable';

    export default {
        name:'MooringAuthorisation',
        components:{
            FormSection,
            draggable,
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
        },
        data:function () {
            return {
                mooringBays: [],
                mooringAuthPreference: null,
                siteLicenseeEmail: null,
                mooringSiteId: null,
                dragging: false,
            }
        },
        computed: {
        },
        watch: {
        },
        methods:{
            fetchMooringBays: async function(){
                const response = await this.$http.get(api_endpoints.mooring_bays);
                // reorder array based on proposal.bay_preferences_numbered
                if (this.proposal.bay_preferences_numbered) {
                    let newArray = [];
                    for (let n of this.proposal.bay_preferences_numbered) {
                        const found = response.body.find(el => el.id === n);
                        newArray.push(found);
                    }
                    // read ordered array into Vue array
                    for (let bay of newArray) {
                        this.mooringBays.push(bay);
                    }
                } else {
                    for (let bay of response.body) {
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
                    ajax: {
                        url: api_endpoints.mooring_lookup,
                        //url: api_endpoints.vessel_rego_nos,
                        dataType: 'json',
                        data: function(params) {
                            var query = {
                                term: params.term,
                                type: 'public',
                                private_moorings: true,
                            }
                            return query;
                        },
                    },
                }).
                on("select2:select", function (e) {
                    var selected = $(e.currentTarget);
                    let data = e.params.data.id;
                    vm.mooringSiteId = data;
                }).
                on("select2:unselect",function (e) {
                    var selected = $(e.currentTarget);
                    vm.mooringSiteId = null;
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
            this.$nextTick(async () => {
                await this.fetchMooringBays();
                if (this.proposal.site_licensee_email) {
                    this.siteLicenseeEmail = this.proposal.site_licensee_email;
                }
                if (this.proposal.mooring_id) {
                    this.mooringSiteId = this.proposal.mooring_id;
                }
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
</style>

