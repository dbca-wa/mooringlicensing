<template>
    <FormSection label="Search Sticker" Index="search_sticker">
        <div class="row form-group">
            <label for="sticker_lookup" class="col-sm-3 control-label">Sticker</label>
            <div class="col-sm-6">
                <select 
                    id="sticker_lookup"  
                    name="sticker_lookup"  
                    ref="sticker_lookup" 
                    class="form-control" 
                />
            </div>
            <div class="col-sm-3">
                <input 
                type="button" 
                @click.prevent="openApproval" 
                class="btn btn-primary" 
                value="View Details"
                />
            </div>
        </div>
    </FormSection>
</template>

<script>
import FormSection from '@/components/forms/section_toggle.vue'
require("select2/dist/css/select2.min.css");
require("select2-bootstrap-theme/dist/select2-bootstrap.min.css");
import {
  api_endpoints,
}
from '@/utils/hooks'
    export default {
        name:'SearchSticker',
        components:{
            FormSection,
        },
         data:function () {
            return {
                approval_id: null,
             }
        },
        methods:{
            openApproval: function() {
                console.log("open approval: " + this.approval_id);
                this.$nextTick(() => {
                    if (this.approval_id) {
                        this.$router.push({
                            name: 'internal-approval-detail',
                            params: {"approval_id": this.approval_id},
                        });
                    }
                });

            },
            initialiseStickerLookup: function(){
                let vm = this;
                $(vm.$refs.sticker_lookup).select2({
                    minimumInputLength: 2,
                    "theme": "bootstrap",
                    allowClear: true,
                    placeholder:"Select Sticker",
                    pagination: true,
                    ajax: {
                        url: api_endpoints.sticker_lookup,
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
                    let data = e.params.data.approval_id;
                    vm.approval_id = data;
                }).
                on("select2:unselect",function (e) {
                    vm.approval_id = null;
                }).
                on("select2:open",function (e) {
                    const searchField = $('[aria-controls="select2-sticker_lookup-results"]')
                    // move focus to select2 field
                    searchField[0].focus();
                });
            },
        },
        mounted: function () {
            this.$nextTick(async () => {
                this.initialiseStickerLookup();
            });
        },
    }
</script>