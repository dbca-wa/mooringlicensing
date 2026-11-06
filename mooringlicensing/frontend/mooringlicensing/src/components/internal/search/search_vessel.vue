<template>
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
import {
  api_endpoints,
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
        methods:{
            openVessel: function() {
                console.log("open vessel");
                this.$nextTick(() => {
                    if (this.selectedVessel) {
                        if (this.selectedVessel.entity_type === 'ml') {
                            this.$router.push({
                                name: 'internal-vessel-detail',
                                params: {"vessel_id": this.selectedVessel.id},
                            });
                        } else if (this.selectedVessel.entity_type === 'dcv') {
                            this.$router.push({
                                name: 'internal-dcv-vessel-detail',
                                params: {"dcv_vessel_id": this.selectedVessel.id},
                            });
                        }
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
                    pagination: true,
                    ajax: {
                        url: api_endpoints.vessel_lookup,
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
                    let data = e.params.data;
                    vm.selectedVessel = Object.assign({}, data);
                }).
                on("select2:unselect",function (e) {
                    vm.selectedVessel = null;
                }).
                on("select2:open",function (e) {
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
    }
</script>

<style lang="css" scoped>
</style>

