<template lang="html">
    <FormSection label="Search Vessels" Index="search_vessel">
        <div class="row form-group">
                <label for="vessel_lookup" class="col-sm-3 control-label">Search Vessel by registration number or name</label>
                <div class="col-sm-6">
                    <select 
                        id="vessel_lookup"  
                        ref="vessel_lookup" 
                        class="form-control" 
                    />
                </div>
                <div class="col-sm-3">
                    <input 
                    type="button" 
                    @click.prevent="openVessel" 
                    class="btn btn-primary" 
                    value="View Details"
                    />
                </div>
        </div>

    </FormSection>
</template>

<script>
import FormSection from '@/components/forms/section_toggle.vue'
/*
var select2 = require('select2');
require("select2/dist/css/select2.min.css");
require("select2-bootstrap-theme/dist/select2-bootstrap.min.css");
*/
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'
    export default {
        name:'SearchVessel',
        components:{
            FormSection,
        },
         data:function () {
            return {
                selectedVessel: null,
             }
        },
        computed: {
        },
        methods:{
            openVessel: function() {
                console.log("open vessel");
                this.$nextTick(() => {
                    if (this.selectedVessel) {
                        this.$router.push({
                            name: 'internal-vessel-detail',
                            params: {"vessel_id": this.selectedVessel},
                        });
                    }
                });

            },
            initialiseVesselLookup: function(){
                let vm = this;
                $(vm.$refs.vessel_lookup).select2({
                    minimumInputLength: 2,
                    "theme": "bootstrap",
                    allowClear: true,
                    placeholder:"Select Vessel",
                    ajax: {
                        url: api_endpoints.vessel_lookup,
                        //url: api_endpoints.vessel_rego_nos,
                        dataType: 'json',
                        data: function(params) {
                            var query = {
                                term: params.term,
                                type: 'public',
                            }
                            return query;
                        },
                    },
                }).
                on("select2:select", function (e) {
                    var selected = $(e.currentTarget);
                    let data = e.params.data.id;
                    vm.selectedVessel = data;
                }).
                on("select2:unselect",function (e) {
                    var selected = $(e.currentTarget);
                    vm.selectedVessel = null;
                }).
                on("select2:open",function (e) {
                    //const searchField = $(".select2-search__field")
                    const searchField = $('[aria-controls="select2-vessel_lookup-results"]')
                    // move focus to select2 field
                    searchField[0].focus();
                });
            },
        },
        mounted: function () {
            this.$nextTick(async () => {
                this.initialiseVesselLookup();
            });
        },
        created: async function() {
        },
    }
</script>

<style lang="css" scoped>
</style>

