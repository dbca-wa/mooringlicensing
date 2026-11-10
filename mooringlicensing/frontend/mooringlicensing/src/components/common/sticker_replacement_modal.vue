<template>
    <div id="change-contact">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <alert :show.sync="showError" type="danger"><strong>{{ errorString }}</strong></alert>
                <div class="row form-group">
                    <label class="col-sm-2 control-label" for="reason">Reason</label>
                    <div class="col-sm-10">
                        <textarea class="col-sm-9 form-control" name="reason" v-model="details.reason"></textarea>
                    </div>
                </div>
                <div v-show="showDateOfLost" class="row form-group">
                    <label class="col-sm-2 control-label">Date of Lost</label>
                    <div class="col-sm-3">
                        <div class="input-group date" id="lost_date_elem" ref="lostDatePicker">
                            <input type="text" class="form-control text-center" placeholder="DD/MM/YYYY" />
                            <span class="input-group-addon">
                                <span class="glyphicon glyphicon-calendar"></span>
                            </span>
                        </div>
                    </div>
                </div>
                <div v-show="showDateOfReturned" class="row form-group">
                    <label class="col-sm-2 control-label">Date of Returned</label>
                    <div class="col-sm-3">
                        <div class="input-group date" id="returned_date_elem" ref="returnedDatePicker">
                            <input type="text" class="form-control text-center" placeholder="DD/MM/YYYY" />
                            <span class="input-group-addon">
                                <span class="glyphicon glyphicon-calendar"></span>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div slot="footer">
                <div class="row">
                    <div class="col-md-7">
                        <span v-if="showWaiveFeeCheckbox">
                            <strong><input type="checkbox" v-model="waive_the_fee" /> Waive the fee</strong>
                        </span>
                    </div>
                    <div class="col-md-5">
                        <button type="button" v-if="processing" disabled class="btn btn-default" @click="ok"><i class="fa fa-spinner fa-spin"></i> Processing</button>
                        <button type="button" v-else class="btn btn-default" @click="ok" :disabled="!okButtonEnabled">Ok</button>
                        <button type="button" class="btn btn-default" @click="cancel">Cancel</button>
                    </div>
                </div>
            </div>
        </modal>
    </div>
</template>

<script>
//import $ from 'jquery'
import 'eonasdan-bootstrap-datetimepicker'
import modal from '@vue-utils/bootstrap-modal.vue'
import alert from '@vue-utils/alert.vue'

export default {
    name:'ModalForSticker',
    components:{
        modal,
        alert,
    },
    props:{

    },
    data:function () {
        let vm = this;
        return {
            isModalOpen:false,
            action: '',
            sticker: {},
            details: vm.getDefaultDetails(),
            processing: false,
            errors: false,
            errorString: '',
            waive_the_fee: false,
        }
    },
    computed: {
        okButtonEnabled: function(){
            if (this.action === 'record_lost'){
               if(this.details.reason && this.details.date_of_lost_sticker){
                  return true
               }
               return false
            } else if (this.action === 'record_returned'){
               if(this.details.reason && this.details.date_of_returned_sticker){
                  return true
               }
               return false
            } else if (this.action === 'request_replacement'){
               if(this.details.reason){
                  return true
               }
               return false
            } else if (this.action === 'cancel'){
               if(this.details.reason){
                  return true
               }
               return false
            } else {
                return false
            }
        },
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        title: function() {
            if (this.action === 'record_lost'){
                return 'Record Sticker Lost'
            } else if (this.action === 'record_returned'){
                return 'Record Sticker Returned'
            } else if (this.action === 'request_replacement'){
                return 'Request Sticker Replacement'
            } else if (this.action === 'cancel'){
                return 'Cancel'
            } else {
                return '---'
            }
        },
        showWaiveFeeCheckbox: function(){
            let show = false
            if (this.action === 'request_replacement'){
                show = true
            }
            return show
        },
        showDateOfLost: function(){
            if (this.action === 'record_lost'){
                return true
            }
            return false
        },
        showDateOfReturned: function(){
            if (this.action === 'record_returned'){
                return true
            }
            return false
        },
    },
    methods:{
        getDefaultDetails: function(){
            return {
                reason: '',
                date_of_lost_sticker: null,
                date_of_returned_sticker: null,
            }
        },
        ok:function () {
            let vm =this;
            vm.errors = false
            vm.processing = true
            vm.$emit("sendData", {
                "details": vm.details,
                "sticker": vm.sticker,
                "action": vm.action,
                "waive_the_fee": vm.waive_the_fee,
            })
        },
        cancel:function () {
            this.close();
        },
        close:function () {
            this.details = this.getDefaultDetails()
            $('#returned_date_elem').data('DateTimePicker').clear();
            $('#lost_date_elem').data('DateTimePicker').clear();
            this.errors = false
            this.processing = false
            this.isModalOpen = false
        },
        addEventListeners: function () {
            let vm = this;
            let options = {
                format: "DD/MM/YYYY",
                showClear: true ,
                useCurrent: false,
            };

            // Date of Lost
            let el_lost = $(vm.$refs.lostDatePicker);
            el_lost.datetimepicker(options);
            el_lost.on("dp.change", function(e) {
                let selected_date = null;
                if (e.date){
                    // Date selected
                    selected_date = e.date.format('DD/MM/YYYY')  // e.date is moment object
                }
                vm.details.date_of_lost_sticker = selected_date;
            });

            // Date of Returned
            let el_returned = $(vm.$refs.returnedDatePicker)
            el_returned.datetimepicker(options);
            el_returned.on("dp.change", function(e) {
                let selected_date = null;
                if (e.date){
                    // Date selected
                    selected_date = e.date.format('DD/MM/YYYY')  // e.date is moment object
                    vm.details.date_of_returned_sticker = selected_date;
                } else {
                    // Date not selected
                    vm.details.date_of_returned_sticker = selected_date;
                }
            });
        },
    },
    created:function () {
        this.$nextTick(() => {
            this.addEventListeners();
        });
    }
}
</script>