<template>
    <div id="bookingsPermits">
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
                                <th>Allocated by</th>
                                <th>Contact number</th>
                                <th></th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="approval in approvals">
                                <td>{{ approval.approval_type_dict.description }}</td>
                                <td><a :href=approval.url>{{ approval.lodgement_number }}</a></td>
                                <td>{{ approval.allocated_by }}</td>
                                <td>{{ approval.submitter_phone_number }}</td>
                                <td>
                                    <table class="table">
                                        <thead>
                                            <tr>
                                                <th>Registration number</th>
                                                <th>Vessel Name</th>
                                            </tr>
                                        </thead>
                                        <tr v-for="vessel in approval.vessel_data">
                                            <td><a :href="'/internal/vessel/' + vessel.id">{{ vessel.rego_no }}</a></td>
                                            <td>{{ vessel.vessel_name }}</td>
                                        </tr>
                                    </table>
                                </td>
                                <td>
                                    <a v-if="approval.approval_type_dict.code == 'aup'"  v-on:click="removeAUPFromMooring(entity.id,approval.id)">Remove</a>
                                </td>
                            </tr>

                            <tr v-for="booking in bookings">
                                <td>Booking</td>
                                <td>{{ booking.booking_id_pf }}</td>
                                <td></td>
                                <td>{{ booking.customer_phone_number }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
//import $ from 'jquery'
import 'eonasdan-bootstrap-datetimepicker'
import FormSection from '@/components/forms/section_toggle.vue'

export default {
    name:'BookingsPermits',
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
            approvals: [],
            bookings: [],
            selectedDate: null,
            dataLoading: false,
            }
    },
    methods:{
        addEventListeners: async function () {
            let vm = this;
            let el_fr = $(vm.$refs.datePicker);
            let options = {
                format: "DD/MM/YYYY",
                showClear: true ,
            };

            el_fr.datetimepicker(options);

            el_fr.on("dp.change", function(e) {
                if (e.date) {
                    // Date selected
                    vm.selectedDate = e.date.format('DD/MM/YYYY')
                } else {
                    // Date not selected
                    vm.selectedDate = null;
                }
            });
            $("#dateField").on("blur", async function(e) {
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
                // Approvals
                if (this.entity.type === "vessel") {
                    const res = await this.$http.post(`/api/vessel/${this.entity.id}/find_related_approvals.json`, payload);
                    this.approvals = [];
                    for (let approval of res.body) {
                        this.approvals.push(approval);
                    }
                } else if (this.entity.type === "mooring") {
                    const res = await this.$http.post(`/api/mooring/${this.entity.id}/find_related_approvals.json`, payload);
                    this.approvals = [];
                    for (let approval of res.body) {
                        this.approvals.push(approval);
                    }
                }
                // Bookings
                if (this.entity.type === "vessel") {
                    console.log('vessel')
                    const res = await this.$http.post(`/api/vessel/${this.entity.id}/find_related_bookings.json`, payload);
                    this.bookings = [];
                    console.log('res.body: ')
                    console.log(res.body)
                    for (let booking of res.body) {
                        this.bookings.push(booking);
                    }
                } else if (this.entity.type === "mooring") {
                    console.log('mooring')
                    const res = await this.$http.post(`/api/mooring/${this.entity.id}/find_related_bookings.json`, payload);
                    this.bookings = [];
                    for (let booking of res.body) {
                        this.bookings.push(booking);
                    }
                }
                this.dataLoading = false;
            });
        },
        removeAUPFromMooring: async function(mooring_id, approval_id) {
            let vm=this;
            swal({
                title: "Remove Authorised User Permit",
                text: "Are you sure you want to Remove the Authorised User Permit?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Remove',
                confirmButtonColor:'#dc3545',
                allowOutsideClick: false,
                preConfirm: function () {
                    return new Promise(async function () {
                        try {
                            let payload = {
                                "approval_id": approval_id,
                            }
                            const resp = await vm.$http.post(`/api/mooring/${mooring_id}/removeAUPFromMooring/`, payload);
                            if (resp.status === 200) { 
                                vm.approvals = vm.approvals.filter(item => item.id !== approval_id);
                                swal("Removed!", "The User Permit has been removed successfully.", "success")
                            }
                        } catch (error) {
                            console.error(error);
                            swal("Error!", error.bodyText, "error")
                        }
                    })
                }
            })
        },
    },
    mounted: function () {
        this.$nextTick(async () => {
            let vm = this;
            this.addEventListeners();
            var dateNow = new Date();
            let el_fr = $(vm.$refs.datePicker);
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
