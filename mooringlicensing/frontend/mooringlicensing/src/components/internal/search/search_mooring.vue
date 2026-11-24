<template>
    <FormSection label="Search Mooring" Index="search_mooring">
        <div class="row mb-3">
            <label for="mooring_lookup" class="col-sm-3 col-form-label"
                >Mooring</label
            >
            <div class="col-sm-6">
                <select
                    id="mooring_lookup"
                    name="mooring_lookup"
                    ref="mooring_lookup"
                    class="form-control"
                />
            </div>
            <div class="col-sm-3">
                <input
                    type="button"
                    @click.prevent="openMooring"
                    class="btn btn-primary"
                    value="View Details"
                />
            </div>
        </div>
    </FormSection>
</template>

<script>
import $ from 'jquery';
import FormSection from '@/components/forms/section_toggle.vue';
import { api_endpoints } from '@/utils/hooks';
export default {
    name: 'SearchMooring',
    components: {
        FormSection,
    },
    data: function () {
        return {
            selectedMooring: null,
        };
    },
    methods: {
        openMooring: function () {
            this.$nextTick(() => {
                if (this.selectedMooring) {
                    this.$router.push({
                        name: 'internal-mooring-detail',
                        params: { mooring_id: this.selectedMooring },
                    });
                }
            });
        },
        initialiseMooringLookup: function () {
            let vm = this;
            $(vm.$refs.mooring_lookup)
                .select2({
                    minimumInputLength: 2,
                    theme: 'bootstrap-5',
                    allowClear: true,
                    placeholder: 'Select Mooring',
                    pagination: true,
                    ajax: {
                        url: api_endpoints.mooring_lookup,
                        dataType: 'json',
                        data: function (params) {
                            return {
                                search_term: params.term,
                                page_number: params.page || 1,
                                type: 'public',
                            };
                        },
                        processResults: function (data) {
                            return {
                                results: data.results,
                                pagination: {
                                    more: data.pagination.more,
                                },
                            };
                        },
                    },
                })
                .on('select2:select', function (e) {
                    let data = e.params.data.id;
                    vm.selectedMooring = data;
                })
                .on('select2:unselect', function (e) {
                    vm.selectedMooring = null;
                })
                .on('select2:open', function (e) {
                    const searchField = $(
                        '[aria-controls="select2-mooring_lookup-results"]'
                    );
                    // move focus to select2 field
                    searchField[0].focus();
                });
        },
    },
    mounted: function () {
        this.$nextTick(async () => {
            this.initialiseMooringLookup();
        });
    },
};
</script>
