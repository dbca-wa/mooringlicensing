<template>
    <div id="bookingsPermits">
        <div class="row mb-3">
            <div class="d-flex align-items-center gap-2 mb-3">
                <label class="mb-0">
                    Date
                </label>

                <input
                    type="date"
                    class="form-control"
                    style="width: 200px;"
                    name="selectedDate"
                    v-model="selectedDate"
                    :max="today"
                >
            </div>
        </div>
        <div class="row mb-3">
            <div class="col-sm-12">
                <div id="spinnerLoader" v-if="dataLoading">
                    <i class="fa fa-4x fa-spinner fa-spin"></i>
                </div>
                <div class="booking-permits-wrapper" v-else>
                    <table class="table booking-permits-table">
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
                                    <a :href="'#'+approval.id" v-if="approval.approval_type_dict.code == 'aup'"  v-on:click="removeAUPFromMooring(entity.id,approval.id)">Remove</a>
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
import $ from 'jquery'
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
        lookupEntities: async function() {
            this.$nextTick(async () => {

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

                    const res = await this.$http.post(`/api/vessel/${this.entity.id}/find_related_bookings.json`, payload);
                    this.bookings = [];


                    for (let booking of res.body) {
                        this.bookings.push(booking);
                    }
                } else if (this.entity.type === "mooring") {

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
    computed: {
        today() {
            return new Date().toISOString().split('T')[0];
        }
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

    .booking-permits-wrapper {
        overflow-x: auto;
    }

    .booking-permits-table {
        min-width: 1000px;
    }

    .booking-permits-table th:first-child,
    .booking-permits-table td:first-child {
        position: sticky;
        left: 0;
        background: #fff;
        z-index: 2;
    }

    .booking-permits-table th:last-child,
    .booking-permits-table td:last-child {
        position: sticky;
        right: 0;
        background: #fff;
        z-index: 2;
    }

    .booking-permits-table thead th {
        z-index: 3;
    }

    .booking-permits-table td:nth-child(5),
    .booking-permits-table th:nth-child(5) {
        min-width: 300px;
    }
</style>
