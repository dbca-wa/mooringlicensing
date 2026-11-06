<template>
    <div id="offerMooringLicence">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" :title="title" large>
            <div class="container-fluid">
                <div class="row">
                    <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                    <div class="col-sm-12">
                        <div class="form-group">
                            <div class="row">
                                <div class="col-sm-3">
                                    <label class="control-label pull-left" for="mooring_bay_lookup">Bay</label>
                                </div>
                                <div class="col-sm-6">
                                    <select class="form-control" v-model="selectedMooringBayId" id="mooring_bay_lookup" disabled>
                                        <option v-for="bay in mooringBays" v-bind:value="bay.id">
                                        {{ bay.name }}
                                        </option>
                                    </select>
                                </div>
                            </div>
                        </div>
                        <div class="form-group">
                            <div class="row">
                                <div class="col-sm-3">
                                    <label class="control-label pull-left" for="mooring_site_id">Mooring Site ID</label>
                                </div>
                                <div class="col-sm-6">
                                    <select
                                        id="mooring_lookup"
                                        name="mooring_lookup"
                                        ref="mooring_lookup"
                                        class="form-control"
                                        style="width: 100%"
                                    />
                                </div>
                            </div>
                        </div>
                        <div class="form-group">
                            <div class="row">
                                <div class="col-sm-3">
                                    <label class="control-label pull-left"  for="Name">Details</label>
                                </div>
                                <div class="col-sm-9">
                                    <textarea name="approval_details" class="form-control" style="width:70%;" v-model="messageDetails"></textarea>
                                </div>
                            </div>
                        </div>
                        <div class="form-group">
                            <div class="row">
                                <div class="col-sm-3">
                                    <label class="control-label pull-left"  for="Name">BCC email</label>
                                </div>
                                <div class="col-sm-9">
                                        <input type="text" class="form-control" name="approval_cc" style="width:70%;" ref="bcc_email" v-model="ccEmail">
                                </div>
                            </div>
                        </div>
                        <div class="row form-group">
                            <label for="" class="col-sm-3 control-label">Document</label>
                            <div class="col-sm-9">
                                <FileField
                                    ref="waiting_list_offer_documents"
                                    name="waiting-list-offer-documents"
                                    :isRepeatable="true"
                                    :documentActionUrl="waitingListOfferDocumentUrl"
                                    :replace_button_by_text="true"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div slot="footer">
                <p class="pull-right" style="margin-top:5px">
                    <input type="checkbox" v-model="noEmails" id="noEmails" />
                    <label for="noEmails">
                        &nbsp;Do not send email notifications for this application &nbsp;
                    </label>
                <button type="button" v-if="savingOffer" disabled class="btn btn-default" @click="ok"><i class="fa fa-spinner fa-spin"></i> Processing</button>
                <button type="button" v-else class="btn btn-default" @click="ok" :disabled="!ok_button_enabled">Ok</button>
                <button type="button" class="btn btn-default" @click="cancel">Cancel</button>
                </p>
            </div>
        </modal>
    </div>
</template>

<script>
import modal from '@vue-utils/bootstrap-modal.vue'
import FileField from '@/components/forms/filefield_immediate.vue'
import alert from '@vue-utils/alert.vue'
import { helpers, api_endpoints } from "@/utils/hooks.js"

export default {
    name:'OfferMooringLicence',
    components:{
        modal,
        alert,
        FileField,
    },
    props:{
        wlaId: {
            type: Number,
            required: true,
        },
        mooringBayId: {
            type: Number,
            required: true,
        },
    },
    data:function () {
        let vm = this;
        return {
            messageDetails: '',
            ccEmail: '',
            selectedMooringBayId: null,
            selectedMooringId: null,
            isModalOpen:false,
            state: 'proposed_approval',
            savingOffer: false,
            validation_form: null,
            errors: false,
            errorString: '',
            successString: '',
            success:false,
            mooringBays: [],
            noEmails: false,
        }
    },
    computed: {
        ok_button_enabled: function(){
            if (this.selectedMooringBayId && this.selectedMooringId){
                return true
            }
            return false
        },
        waitingListOfferSubmitUrl: function() {
          return `/api/waitinglistallocation/${this.wlaId}/create_mooring_licence_application.json`;
        },
        waitingListOfferDocumentUrl: function() {
            let url = '';
            if (this.wlaId) {
                url = helpers.add_endpoint_join(
                    api_endpoints.approvals,
                    this.wlaId + '/process_waiting_list_offer_document/'
                )
            }
            return url;
        },

        showError: function() {
            var vm = this;
            return vm.errors;
        },
        title: function(){
            return "Offer Mooring Site Licence";
        },
        csrf_token: function() {
          return helpers.getCookie('csrftoken')
        },
    },
    methods:{
        ok: async function() {
            await this.sendData();
        },
        cancel:function () {
            this.close()
            this.$refs.waiting_list_offer_documents.delete_all_documents()
        },
        close: function () {
            this.isModalOpen = false;
            this.errors = false;
            $('.has-error').removeClass('has-error');
        },
        fetchMooringBays: async function() {
            const res = await this.$http.get(api_endpoints.mooring_bays);
            for (let bay of res.body.results) {
                this.mooringBays.push(bay)
            }
        },
        sendData: async function(){
            let payload = {
                "message_details": this.messageDetails,
                "cc_email": this.ccEmail,
                "selected_mooring_bay_id": this.selectedMooringBayId,
                "selected_mooring_id": this.selectedMooringId,
                "no_emails": this.noEmails,
            }
            this.errors = false;
            this.savingOffer = true;
            try {
                const res = await this.$http.post(this.waitingListOfferSubmitUrl, payload);
                await this.$emit('refreshFromResponse', res.body.proposal_created);
            } catch(error) {
                console.error(error);
                this.errors = true;
                this.savingOffer = false;
                this.errorString = helpers.apiVueResourceError(error);
            }
            this.close();
        },
       eventListeners:function () {
            let vm = this;
       },
        initialiseMooringLookup: function(){
            let vm = this;
            $(vm.$refs.mooring_lookup).select2({
                minimumInputLength: 2,
                "theme": "bootstrap",
                allowClear: true,
                placeholder:"Select Mooring",
                ajax: {
                    url: api_endpoints.mooring_lookup_per_bay,
                    dataType: 'json',
                    data: function(params) {
                        var query = {
                            term: params.term,
                            type: 'public',
                            available_moorings: true,
                            mooring_bay_id: vm.selectedMooringBayId,
                            wla_id: vm.wlaId,
                        }
                        return query;
                    },
                },
            }).
            on("select2:select", function (e) {
                var selected = $(e.currentTarget);
                let data = e.params.data.id;
                vm.selectedMooringId = data;
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.selectedMooringId = null;
            }).
            on("select2:open",function (e) {
                const searchField = $('[aria-controls="select2-mooring_lookup-results"]')
                // move focus to select2 field
                searchField[0].focus();
            });
            // clear mooring lookup on Mooring Bay change
            $('#mooring_bay_lookup').on('change', function() {
                $(vm.$refs.mooring_lookup).val(null).trigger('change');
            });
        },
    },
    mounted:function () {
        this.$nextTick(()=>{
            this.initialiseMooringLookup();

        });
    },
    created: function() {
        this.$nextTick(()=>{
            this.fetchMooringBays();
            this.selectedMooringBayId = this.mooringBayId;
        });
    },
}
</script>