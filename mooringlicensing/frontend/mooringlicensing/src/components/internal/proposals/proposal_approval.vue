<template id="proposal_requirements">
    <div>
        <div v-if="displayApprovedMsg" class="col-md-12 alert alert-success">
            <p>The approval has been issued and has been emailed to {{ proposal.submitter.email }}</p>
            <p>Expiry date: {{ approvalExpiryDate }}</p>
            <p>Permit: <a target="_blank" :href="proposal.permit">approval.pdf</a></p>
        </div>
        <div v-if="displayAwaitingPaymentMsg" class="col-md-12 alert alert-success">
            <p>The application has been approved</p>
            <p>Status: Awaiting Payment</p>
        </div>
        <div v-if="displayApprovedAwaitingStickerMsg" class="col-md-12 alert alert-success">
            <p>The approval has been issued and has been emailed to {{ proposal.submitter.email }}</p>
            <p>Status: Awaiting Sticker</p>
            <p>Expiry date: {{ approvalExpiryDate }}</p>
            <p>Permit: <a target="_blank" :href="proposal.permit">approval.pdf</a></p>
        </div>
        <div v-if="displayDeclinedMsg" class="col-md-12 alert alert-warning">
            <p>The proposal was declined. The decision was emailed to {{ proposal.submitter.email }}</p>
        </div>

<!--
        <template v-if="proposal.proposal_apiary">
            <FormSection :formCollapse="false" label="Site(s)" Index="sites">
                <ComponentSiteSelection
                    :apiary_sites="apiary_sites_prop"
                    :is_internal="true"
                    :is_external="false"
                    :key="component_site_selection_key"
                    :show_col_checkbox="showColCheckbox"
                    :enable_col_checkbox="false"
                    :show_col_site="false"
                    :show_col_site_when_submitted="true"
                    :show_col_status_when_submitted="true"
                />
            </FormSection>
        </template>
        <template v-else>
            <div class="col-md-12">
                <div class="row">
                    <div class="panel panel-default">
                        <div class="panel-heading">
                            <h3 class="panel-title">Level of Approval
                                <a class="panelClicker" :href="'#'+proposedLevel" data-toggle="collapse"  data-parent="#userInfo" expanded="false" :aria-controls="proposedLevel">
                                    <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                                </a>
                            </h3>
                        </div>
                        <div class="panel-body panel-collapse collapse in" :id="proposedLevel">

                            <div class="row">
                                <div class="col-sm-12">
                                        <template v-if="!isFinalised">
                                            <p><strong>Level of approval: {{proposal.approval_level}}</strong></p>

                                        <div v-if="isApprovalLevel">
                                            <p v-if="proposal.approval_level_document"><strong>Attach documents:</strong> <a :href="proposal.approval_level_document[1]" target="_blank">{{proposal.approval_level_document[0]}}</a>
                                            <span>
                                            <a @click="removeFile()" class="fa fa-trash-o" title="Remove file" style="cursor: pointer; color:red;"></a>
                                            </span></p>
                                            <div v-else>
                                                <p><strong>Attach documents:</strong></p>
                                                <div class="col-sm-12">
                                                <span class="btn btn-info btn-file pull-left">
                                                Attach File <input type="file" ref="uploadedFile" @change="readFile()"/>
                                                </span>
                                                <span class="pull-left" style="margin-left:10px;margin-top:10px;">{{uploadedFileName()}}</span>

                                                </div>
                                                <div class="row"><p></p></div>
                                                <div class="row"><p></p></div>
                                                <div class="row"><p></p></div>

                                                <p>
                                                <strong>Comments (if no approval attached)</strong>
                                                </p>
                                                <p>
                                                <textarea name="approval_level_comments"  v-model="proposal.approval_level_comment" class="form-control" style="width:70%;"></textarea>
                                                </p>
                                            </div>

                                        </div>
                                        </template>

                                        <template v-if="isFinalised">
                                            <p><strong>Level of approval: {{proposal.approval_level}}</strong></p>

                                            <div v-if="isApprovalLevel">
                                                <p v-if="proposal.approval_level_document"><strong>Attach documents: </strong><a :href="proposal.approval_level_document[1]" target="_blank">{{proposal.approval_level_document[0]}}</a>
                                                </p>
                                                <p v-if="proposal.approval_level_comment"><strong>Comments: {{proposal.approval_level_comment}}</strong>
                                                </p>
                                            </div>
                                        </template>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>
-->

        <div class="col-md-12">
            <div class="row">
                <div class="panel panel-default">
                    <div class="panel-heading">
                        <h3 v-if="!isFinalised" class="panel-title">Proposed Decision
                            <a class="panelClicker" :href="'#'+proposedDecision" data-toggle="collapse"  data-parent="#userInfo" expanded="false" :aria-controls="proposedDecision">
                                <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                            </a>
                        </h3>
                        <h3 v-else class="panel-title">Decision
                            <a class="panelClicker" :href="'#'+proposedDecision" data-toggle="collapse"  data-parent="#userInfo" expanded="false" :aria-controls="proposedDecision">
                                <span class="glyphicon glyphicon-chevron-down pull-right "></span>
                            </a>
                        </h3>
                    </div>
                    <div class="panel-body panel-collapse collapse in" :id="proposedDecision">
                        <div class="row">
                            <div class="col-sm-12">
                                <template v-if="!proposal.proposed_decline_status">
                                    <template v-if="isFinalised">
                                        <p><strong>Decision: Issue</strong></p>
                                        <p><strong>Start date: {{proposal.proposed_issuance_approval.start_date}}</strong></p>
                                        <p><strong>Expiry date: {{proposal.proposed_issuance_approval.expiry_date}}</strong></p>
                                        <p><strong>CC emails: {{proposal.proposed_issuance_approval.cc_email}}</strong></p>
                                    </template>
                                    <template v-else>
                                        <p><strong>Proposed decision: Issue</strong></p>
<!--
                                        <p><strong>Proposed start date: {{proposal.proposed_issuance_approval.start_date}}</strong></p>
                                        <p><strong>Proposed expiry date: {{proposal.proposed_issuance_approval.expiry_date}}</strong></p>
-->
                                        <p><strong>Proposed cc emails: {{proposal.proposed_issuance_approval.cc_email}}</strong></p>
                                    </template>
                                </template>
                                <template v-else>
                                    <strong v-if="!isFinalised">Proposed decision: Decline</strong>
                                    <strong v-else>Decision: Decline</strong>
                                </template>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
import {
    api_endpoints,
    helpers
}
from '@/utils/hooks'
import datatable from '@vue-utils/datatable.vue'
import RequirementDetail from './proposal_add_requirement.vue'
//import ComponentSiteSelection from '@/components/common/apiary/component_site_selection.vue'
import FormSection from "@/components/forms/section_toggle.vue"
import uuid from 'uuid'
import { constants } from '@/utils/hooks'

export default {
    name: 'InternalProposalRequirements',
    props: {
        proposal: Object
    },
    data: function() {
        let vm = this;
        return {
            proposedDecision: "proposal-decision-"+vm._uid,
            proposedLevel: "proposal-level-"+vm._uid,
            uploadedFile: null,
            component_site_selection_key: '',
        }
    },
    watch:{
    },
    components:{
        FormSection,
        //ComponentSiteSelection,
    },
    computed:{
        displayAwaitingPaymentMsg: function(){
            let display = false
            console.log(this.proposal.processing_status)
            if (this.proposal.processing_status === constants.AWAITING_PAYMENT){
                display = true
            }
            return display
        },
        displayApprovedMsg: function(){
            let display = false
            if (this.proposal.processing_status === constants.APPROVED){
                display = true
            }
            return display
        },
        displayApprovedAwaitingStickerMsg: function(){
            let display = false
            if (this.proposal.processing_status === constants.AWAITING_STICKER){
                display = true
            }
            return display
        },
        displayDeclinedMsg: function(){
            let display = false
            if (this.proposal.processing_status === constants.DECLINED){
                display = true
            }
            return display
        },
        /*
        approvalStartDate: function() {
            let returnDate = null;
            if (this.proposal && this.proposal.approval) {
                returnDate = moment(this.proposal.approval.start_date, 'YYYY-MM-DD').format('DD/MM/YYYY');
            }
            return returnDate;
        },
        */
        approvalExpiryDate: function() {
            let returnDate = null;
            if (this.proposal && this.proposal.end_date) {
                returnDate = moment(this.proposal.end_date, 'YYYY-MM-DD').format('DD/MM/YYYY');
            }
            return returnDate;
        },
        hasAssessorMode(){
            return this.proposal.assessor_mode.has_assessor_mode;
        },
        isFinalised: function(){
            return this.proposal.processing_status == 'Approved' || this.proposal.processing_status == 'Declined';
        },
        isApprovalLevel:function(){
            return this.proposal.approval_level != null ? true : false;
        },
        apiary_sites: function() {
            if (this.proposal && this.proposal.proposal_apiary) {
                return this.proposal.proposal_apiary.apiary_sites;
            }
        },
        apiary_sites_prop: function() {
            let apiary_sites = [];
            if (this.proposal.application_type === 'Site Transfer') {
                for (let site of this.proposal.proposal_apiary.site_transfer_apiary_sites) {
                    if (site.selected) {
                        apiary_sites.push(site.apiary_site);
                    }
                }
            } else {
                apiary_sites = this.proposal.proposal_apiary.apiary_sites;
            }
            return apiary_sites;
        },
        showColCheckbox: function() {
            let checked = true;
            if (this.proposal.proposal_apiary.application_type !== 'Site Transfer') {
                checked = false;
            }
            return checked;
        },

    },
    methods:{
        updateComponentSiteSelectionKey: function(){
            console.log('in updateComponentSiteSelectionKey')
            this.component_site_selection_key = uuid()
        },
        readFile: function() {
            let vm = this;
            let _file = null;
            var input = $(vm.$refs.uploadedFile)[0];
            if (input.files && input.files[0]) {
                var reader = new FileReader();
                reader.readAsDataURL(input.files[0]);
                reader.onload = function(e) {
                    _file = e.target.result;
                };
                _file = input.files[0];
            }
            vm.uploadedFile = _file;
            vm.save()
        },
        removeFile: function(){
            let vm = this;
            vm.uploadedFile = null;
            vm.save()
        },
        save: function(){
            let vm = this;
                let data = new FormData(vm.form);
                data.append('approval_level_document', vm.uploadedFile)
                if (vm.proposal.approval_level_document) {
                    data.append('approval_level_document_name', vm.proposal.approval_level_document[0])
                }
                vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposals,vm.proposal.id+'/approval_level_document'),data,{
                emulateJSON:true
            }).then(res=>{
                vm.proposal = res.body;
                vm.$emit('refreshFromResponse',res);

                },err=>{
                swal(
                    'Submit Error',
                    helpers.apiVueResourceError(err),
                    'error'
                )
            });


        },
        uploadedFileName: function() {
            return this.uploadedFile != null ? this.uploadedFile.name: '';
        },
        addRequirement(){
            this.$refs.requirement_detail.isModalOpen = true;
        },
        removeRequirement(_id){
            let vm = this;
            swal({
                title: "Remove Requirement",
                text: "Are you sure you want to remove this requirement?",
                type: "warning",
                showCancelButton: true,
                confirmButtonText: 'Remove Requirement',
                confirmButtonColor:'#d9534f'
            }).then(() => {
                vm.$http.delete(helpers.add_endpoint_json(api_endpoints.proposal_requirements,_id))
                .then((response) => {
                    vm.$refs.requirements_datatable.vmDataTable.ajax.reload();
                }, (error) => {
                    console.log(error);
                });
            },(error) => {
            });
        },
    },
    mounted: function(){
        let vm = this;
        this.updateComponentSiteSelectionKey()
    }
}
</script>
<style scoped>
</style>
