<template id="proposal_approval">
    <div>
        <div v-if="displayApprovedMsg" class="col-md-12 alert alert-success">
            <p>The approval has been issued and has been emailed to {{ proposal.proposal_applicant.email }}</p>
            <p>Expiry date: {{ approvalExpiryDate }}</p>
            <p>Permit: <a target="_blank" :href="proposal.permit">approval.pdf</a></p>
        </div>
        <div v-if="displayAwaitingPaymentMsg" class="col-md-12 alert alert-success">
            <p>The application has been approved</p>
            <p>Status: Awaiting Payment</p>
        </div>
        <div v-if="displayApprovedAwaitingStickerMsg" class="col-md-12 alert alert-success">
            <p>The approval has been issued and has been emailed to {{ proposal.proposal_applicant.email }}</p>
            <p>Status: Awaiting Sticker</p>
            <p>Expiry date: {{ approvalExpiryDate }}</p>
            <p>Permit: <a target="_blank" :href="proposal.permit">approval.pdf</a></p>
        </div>
        <div v-if="displayDeclinedMsg" class="col-md-12 alert alert-warning">
            <p>The proposal was declined. The decision was emailed to {{ proposal.proposal_applicant.email }}</p>
        </div>

        <FormSection
            :label="isFinalised ? 'Decision' : 'Proposed Decision'"
            :formCollapse="false"
            :Index="proposedDecision"
        >
            <template v-if="!proposal.proposed_decline_status">
                <div class="row"><div :class="title_class_name">{{ decisionTitle }}: </div><div :class="value_class_name">Issue</div></div>
                <div class="row"><div :class="title_class_name">{{ ccEmailTitle }}: </div><div :class="value_class_name">{{ displayCCEmail }}</div></div>
                <div class="row"><div :class="title_class_name">Proposed details: </div><div :class="value_class_name">{{ proposal.proposed_issuance_approval.details }}</div></div>
                <template v-if="proposal.site_licensee_moorings.length > 0">
                    <div class="currently_listed_moorings"><strong>Requested moorings</strong></div>
                    <template v-for="item in proposal.site_licensee_moorings">
                        <div class="mooring_box">
                            <div class="row"><div :class="title_class_name">Selected: </div><div :class="value_class_name"><input type="checkbox" v-model="item.checked" disabled /></div></div>
                            <div class="row"><div :class="title_class_name">Bay: </div><div :class="value_class_name">{{ item.bay }}</div></div>
                            <div class="row"><div :class="title_class_name">Mooring Site ID: </div><div :class="value_class_name">{{ item.mooring_name }}</div></div>
                            <div v-if="item.vessel_weight_limit" class="row"><div :class="title_class_name">Max vessel weight: </div><div :class="value_class_name">{{ (item.vessel_weight_limit) }}</div></div>
                            <div class="row"><div :class="title_class_name">Max vessel draft: </div><div :class="value_class_name">{{ (item.vessel_draft_limit) }}</div></div>
                            <div class="row"><div :class="title_class_name">Max vessel length: </div><div :class="value_class_name">{{ (item.vessel_size_limit) }}</div></div>
                        </div>
                    </template>
                </template>
                <template v-if="proposal.authorised_user_moorings.length > 0">
                    <div class="currently_listed_moorings"><strong>Currently listed moorings</strong></div>
                    <template v-for="item in proposal.authorised_user_moorings">
                        <div class="mooring_box">
                            <div class="row"><div :class="title_class_name">Selected: </div><div :class="value_class_name"><input type="checkbox" v-model="item.checked" disabled /></div></div>
                            <div class="row"><div :class="title_class_name">Bay: </div><div :class="value_class_name">{{ item.bay }}</div></div>
                            <div class="row"><div :class="title_class_name">Mooring Site ID: </div><div :class="value_class_name">{{ item.mooring_name }}</div></div>
                            <div v-if="item.vessel_weight_limit" class="row"><div :class="title_class_name">Max vessel weight: </div><div :class="value_class_name">{{ (item.vessel_weight_limit) }}</div></div>
                            <div class="row"><div :class="title_class_name">Max vessel draft: </div><div :class="value_class_name">{{ (item.vessel_draft_limit) }}</div></div>
                            <div class="row"><div :class="title_class_name">Max vessel length: </div><div :class="value_class_name">{{ (item.vessel_size_limit) }}</div></div>
                        </div>
                    </template>
                </template>
                <template v-if="proposal.mooring_licence_vessels.length > 0">
                    <div class="currently_listed_moorings"><strong>Currently listed vessels</strong></div>
                    <template v-for="item in proposal.mooring_licence_vessels">
                        <div class="mooring_box">
                            <div class="row"><div :class="title_class_name">Selected: </div><div :class="value_class_name"><input type="checkbox" v-model="item.checked" disabled /></div></div>
                            <div class="row"><div :class="title_class_name">Vessel rego: </div><div :class="value_class_name">{{ item.rego }}</div></div>
                            <div class="row"><div :class="title_class_name">Vessel name: </div><div :class="value_class_name">{{ item.vessel_name }}</div></div>
                        </div>
                    </template>
                </template>
                
            </template>
            <template v-else>
                <strong v-if="!isFinalised">Proposed decision: Decline</strong>
                <strong v-else>Decision: Decline</strong>
            </template>
        </FormSection>
    </div>
</template>
<script>
import {
    api_endpoints
}
from '@/utils/hooks'
import FormSection from "@/components/forms/section_toggle.vue"
import { v4 as uuidv4 } from 'uuid';
import { constants } from '@/utils/hooks'

export default {
    name: 'InternalProposalApproval',
    props: {
        mooringBays: Array,
        proposal: Object,
        siteLicenseeMooring: Object,
    },
    data: function() {
        let vm = this;
        return {
            proposedDecision: "proposal-decision-"+vm.$.uid,
            proposedLevel: "proposal-level-"+vm.$.uid,
            uploadedFile: null,
            component_site_selection_key: '',
            mooring: {},
            title_class_name: 'col-sm-3 proposed-decision-title',
            value_class_name: 'col-sm-9 proposed-decision-value',
        }
    },
    watch:{
    },
    components:{
        FormSection,
    },
    computed:{
        decisionTitle: function(){
            if (this.isFinalised){
                return 'Decision'
            } else {
                return 'Proposed decision'
            }
        },
        ccEmailTitle: function(){
            if (this.isFinalised){
                return 'CC emails'
            } else {
                return 'Proposed cc emails'
            }
        },
        targetMooringBayDetails: function(){
            let mooringBayDetail = {}
            if (this.proposal.mooring_authorisation_preference == 'ria'){
                console.log('RIA')
                mooringBayDetail = {
                    'bay_name': this.proposal.proposed_issuance_approval.bay_name,
                    'mooring_name': this.proposal.proposed_issuance_approval.ria_mooring_name,
                    'vessel_draft_limit': this.mooring.vessel_draft_limit,
                    'vessel_size_limit': this.mooring.vessel_size_limit
                }
            } else if (this.proposal.mooring_authorisation_preference == 'site_licensee'){
                console.log('SITE LICENSEE')
                mooringBayDetail = {
                    'bay_name': this.siteLicenseeMooring.mooring_bay_name,
                    'mooring_name': this.siteLicenseeMooring.name,
                    'vessel_draft_limit': this.siteLicenseeMooring.vessel_draft_limit,
                    'vessel_size_limit': this.siteLicenseeMooring.vessel_size_limit
                }                       
            } else {                    
                console.log('ELSE')
                mooringBayDetail = {
                    'bay_name': this.mooring.mooring_bay_name,
                    'mooring_name': this.mooring.name,
                    'vessel_draft_limit': this.mooring.vessel_draft_limit,
                    'vessel_size_limit': this.mooring.vessel_size_limit
                }
            }
            return mooringBayDetail
        },
        displayCCEmail: function() {
            let ccEmail = ''
            if (this.proposal && this.proposal.proposed_issuance_approval) {
                ccEmail = this.proposal.proposed_issuance_approval.cc_email;
            }
            return ccEmail;
        },
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
    },
    methods:{
        stripHtmlTag: function(myString){
            let html = myString
            let div = document.createElement("div")
            div.innerHTML = html
            let text = div.textContent || div.innerText || ''
            return text
        },
        retrieveMooringDetails: async function(){
            console.log('%cAHO', 'color: #370;')
            let mooring_id = null
            if (this.proposal.proposed_issuance_approval && this.proposal.proposed_issuance_approval.mooring_id){
                mooring_id = this.proposal.proposed_issuance_approval.mooring_id
            } else if (this.proposal.allocated_mooring){
                mooring_id = this.proposal.allocated_mooring
            }
            if (mooring_id){
                const res = await this.$http.get(`${api_endpoints.mooring}${mooring_id}`);
                this.mooring = res.body
            }
        },
        updateComponentSiteSelectionKey: function(){
            console.log('in updateComponentSiteSelectionKey')
            this.component_site_selection_key = uuidv4()
        },
    },
    mounted: function(){
        this.updateComponentSiteSelectionKey()
        this.retrieveMooringDetails()
    }
}
</script>
<style scoped>
.proposed-decision-title {
    font-weight: bold;
    text-align: right;
}
.proposed-decision-value {
    font-weight: bold;
}
.currently_listed_moorings {
    margin: 2em 0 0 0;
}
.mooring_box {
    border: 1px solid lightgray;
    border-radius: 0.5em;
}
</style>
