<template lang="html">
    <!--div class="container" id="bookingsPermits"-->
    <div id="bookingsPermits">
        <!--table style="width:100%"-->
        <div class="row form-group">
            <div class="col-sm-12">
                <label for="" class="col-sm-2 control-label">Date</label>
                <div class="col-sm-3 input-group date" ref="datePicker">
                    <input type="text" class="form-control text-center" placeholder="DD/MM/YYYY" v-model="selectedDate" id="dateField"/>
                    <span class="input-group-addon">
                        <span class="glyphicon glyphicon-calendar"></span>
                    </span>
                </div>
            </div>
        </div>
        <div class="row form-group">
            <div class="col-sm-12">
                <div id="spinnerLoader" v-if="dataLoading">
                    <i class="fa fa-4x fa-spinner fa-spin"></i>
                </div>
                <div v-else>
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Entity type</th>
                                <th>Number</th>
                                <!--th>Action</th-->
                                <!--th>Contact number</th-->
                                <th>View</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="admission in dcvAdmissions">
                                <td>{{ admission.entity_type }}</td>
                                <td>{{ admission.lodgement_number }}</td>
                                <td></td>
                            </tr>
                            <tr v-for="permit in dcvPermits">
                                <td>{{ permit.entity_type }}</td>
                                <td>{{ permit.lodgement_number }}</td>
                                <td></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import FormSection from '@/components/forms/section_toggle.vue'
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'
    export default {
        name:'DcvAdmissionsPermits',
        components:{
            FormSection,
        },
        props: {
            entity: {
                type: Object,
                required: true,
            },
        },
        data:function () {
            let vm = this;
            return {
                dcvAdmissions: [],
                dcvPermits: [],
                selectedDate: null,
                dataLoading: false,
             }
        },
        computed: {
        },
        methods:{
            addEventListeners: async function () {
                let vm = this;
                let el_fr = $(vm.$refs.datePicker);
                let options = {
                    format: "DD/MM/YYYY",
                    showClear: true ,
                    //useCurrent: false,
                };

                el_fr.datetimepicker(options);

                el_fr.on("dp.change", function(e) {
                    //let selected_date = null;
                    if (e.date) {
                        // Date selected
                        vm.selectedDate = e.date.format('DD/MM/YYYY')  // e.date is moment object
                        //vm.arrival.arrival_date = selected_date;
                    } else {
                        // Date not selected
                        //vm.arrival.arrival_date = selected_date;
                        vm.selectedDate = null;
                    }
                });
                $("#dateField").on("blur", async function(e) {
                    //console.log("watch date")
                    vm.lookupEntities();
                });
            },
            lookupEntities: async function() {
                this.$nextTick(async () => {
                    console.log("lookupEntities");
                    this.dataLoading = true;
                    let payload = {
                        "selected_date": this.selectedDate,
                    }
                    // DCV
                    // TODO: needs to go in separate vue component
                    if (this.entity.type === "vessel") {
                        const admissionRes = await this.$http.post(`/api/dcv_vessel/${this.entity.id}/find_related_admissions.json`, payload);
                        this.dcvAdmissions = [];
                        for (let admission of admissionRes.body) {
                            this.dcvAdmissions.push(admission);
                        }
                        const permitRes = await this.$http.post(`/api/dcv_vessel/${this.entity.id}/find_related_permits.json`, payload);
                        this.dcvPermits = [];
                        for (let permit of permitRes.body) {
                            this.dcvPermits.push(permit);
                        }
                    }
                    this.dataLoading = false;
                });
            },
        },
        mounted: function () {
            this.$nextTick(async () => {
                let vm = this;
                this.addEventListeners();
                var dateNow = new Date();
                let el_fr = $(vm.$refs.datePicker);
                /*
                console.log(el_fr);
                console.log(el_fr.data("DateTimePicker"));
                */
                el_fr.data("DateTimePicker").date(dateNow);
            });
        },
        created: async function() {
            await this.lookupEntities()
        },
    }
</script>

<style lang="css" scoped>
  #spinnerLoader {
    width: 100%;
    text-align: center;
    padding: 1em 0;
  }
</style>
