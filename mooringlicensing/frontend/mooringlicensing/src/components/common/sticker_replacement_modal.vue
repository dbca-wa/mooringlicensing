<template>
    <div id="change-contact">
        <modal
            v-model:show="isModalOpen"
            transition="modal fade"
            @ok="ok()"
            @cancel="cancel()"
            :title="title"
            large
        >
            <div class="container-fluid">
                <alert v-model:show="showError" type="danger"
                    ><strong>{{ errorString }}</strong></alert
                >
                <div class="row mb-3">
                    <label class="col-sm-2 col-form-label" for="reason"
                        >Reason</label
                    >
                    <div class="col-sm-10">
                        <textarea
                            class="col-sm-9 form-control"
                            name="reason"
                            v-model="details.reason"
                        ></textarea>
                    </div>
                </div>
                <div v-show="showDateOfLost" class="row mb-3">
                    <label class="col-sm-2 col-form-label">Date of Lost</label>
                    <div class="col-sm-3">
                        <div style="width: 70%">
                            <input
                                type="date"
                                class="form-control"
                                name="lostDatePicker"
                                v-model="details.date_of_lost_sticker"
                                :max="today"
                            />
                        </div>
                    </div>
                </div>
                <div v-show="showDateOfReturned" class="row mb-3">
                    <label class="col-sm-2 col-form-label"
                        >Date of Returned</label
                    >
                    <div class="col-sm-3">
                        <div style="width: 70%">
                            <input
                                type="date"
                                class="form-control"
                                name="returnedDatePicker"
                                v-model="details.date_of_returned_sticker"
                                :max="today"
                            />
                        </div>
                    </div>
                </div>
            </div>
            <template v-slot:footer>
                <div class="row w-100">
                    <div class="col-md-6 text-end">
                        <span v-if="showWaiveFeeCheckbox">
                            <strong
                                ><input
                                    type="checkbox"
                                    v-model="waive_the_fee"
                                />
                                Waive the fee</strong
                            >
                        </span>
                    </div>
                    <div class="col-md-6 text-end">
                        <button
                            type="button"
                            v-if="processing"
                            disabled
                            class="btn btn-primary me-2"
                            @click="ok"
                        >
                            <i class="fa fa-spinner fa-spin"></i> Processing
                        </button>
                        <button
                            type="button"
                            v-else
                            class="btn btn-primary me-2"
                            @click="ok"
                            :disabled="!okButtonEnabled"
                        >
                            Ok
                        </button>
                        <button
                            type="button"
                            class="btn btn-secondary me-2"
                            @click="cancel"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            </template>
        </modal>
    </div>
</template>

<script>
import $ from 'jquery';
import modal from '@vue-utils/bootstrap-modal.vue';
import alert from '@vue-utils/alert.vue';

export default {
    name: 'ModalForSticker',
    emits: ['sendData'],
    components: {
        modal,
        alert,
    },
    props: {},
    data: function () {
        let vm = this;
        return {
            isModalOpen: false,
            action: '',
            sticker: {},
            details: vm.getDefaultDetails(),
            processing: false,
            errors: false,
            errorString: '',
            waive_the_fee: false,
        };
    },
    computed: {
        okButtonEnabled: function () {
            if (this.action === 'record_lost') {
                if (this.details.reason && this.details.date_of_lost_sticker) {
                    return true;
                }
                return false;
            } else if (this.action === 'record_returned') {
                if (
                    this.details.reason &&
                    this.details.date_of_returned_sticker
                ) {
                    return true;
                }
                return false;
            } else if (this.action === 'request_replacement') {
                if (this.details.reason) {
                    return true;
                }
                return false;
            } else if (this.action === 'cancel') {
                if (this.details.reason) {
                    return true;
                }
                return false;
            } else {
                return false;
            }
        },
        showError: function () {
            var vm = this;
            return vm.errors;
        },
        title: function () {
            if (this.action === 'record_lost') {
                return 'Record Sticker Lost';
            } else if (this.action === 'record_returned') {
                return 'Record Sticker Returned';
            } else if (this.action === 'request_replacement') {
                return 'Request Sticker Replacement';
            } else if (this.action === 'cancel') {
                return 'Cancel';
            } else {
                return '---';
            }
        },
        showWaiveFeeCheckbox: function () {
            let show = false;
            if (this.action === 'request_replacement') {
                show = true;
            }
            return show;
        },
        showDateOfLost: function () {
            if (this.action === 'record_lost') {
                return true;
            }
            return false;
        },
        showDateOfReturned: function () {
            if (this.action === 'record_returned') {
                return true;
            }
            return false;
        },
        today() {
            return new Date().toISOString().split('T')[0];
        },
    },
    methods: {
        getDefaultDetails: function () {
            return {
                reason: '',
                date_of_lost_sticker: null,
                date_of_returned_sticker: null,
            };
        },
        ok: function () {
            let vm = this;
            vm.errors = false;
            vm.processing = true;
            vm.$emit('sendData', {
                details: vm.details,
                sticker: vm.sticker,
                action: vm.action,
                waive_the_fee: vm.waive_the_fee,
            });
        },
        cancel: function () {
            this.close();
        },
        close: function () {
            this.details = this.getDefaultDetails();
            this.errors = false;
            this.processing = false;
            this.isModalOpen = false;
        },
    },
};
</script>

<style scoped>
.modal-footer > * {
    width: 100%;
}
</style>
