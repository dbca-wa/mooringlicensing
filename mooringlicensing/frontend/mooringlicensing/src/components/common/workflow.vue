<template>
     <div class="">
        <div class="card mb-3">
            <div class="card-header">
                Workflow
            </div>
            <div class="card-body border-bottom">
                <div class="row">
                    <div class="col-sm-12">
                        <strong>Status</strong><br/>
                        {{ proposal.processing_status }}
                    </div>
                    <div class="col-sm-12">
                        <div class="separator"></div>
                    </div>
                    
                    <div v-if="!isFinalised" class="col-sm-12 top-buffer-s">
                        <strong>Currently assigned to</strong><br/>
                        <div class="mb-3">
                            <template v-if="proposal.processing_status == 'With Approver'">
                                    <select 
                                        ref="assigned_officer" 
                                        :disabled="!canAction" 
                                        class="form-select" 
                                        v-model="proposal.assigned_approver"
                                        @change="assignTo()">
                                        <option v-for="member in proposal.allowed_assessors" :value="member.ledger_id">{{ member.first_name }} {{ member.last_name }}</option>
                                    </select>
                                    <a v-if="canAssess && proposal.assigned_approver != proposal.current_assessor.id" @click.prevent="assignRequestUser()" class="actionBtn float-end">Assign to me</a>
                            </template>
                            <template v-else>
                                    <select 
                                        ref="assigned_officer" 
                                        :disabled="!canAction" 
                                        class="form-select" 
                                        v-model="proposal.assigned_officer"
                                        @change="assignTo()">
                                        <option v-for="member in proposal.allowed_assessors" :value="member.ledger_id">{{ member.first_name }} {{ member.last_name }}</option>
                                    </select>
                                    <a v-if="canAssess && proposal.assigned_officer != proposal.current_assessor.id" @click.prevent="assignRequestUser()" class="actionBtn float-end">Assign to me</a>
                            </template>
                        </div>
                    </div>

                    <template v-if="proposal.processing_status == 'With Assessor (Requirements)' || proposal.processing_status == 'With Approver' || isFinalised">
                    </template>
                    <template v-if="proposal.processing_status == 'With Approver' || isFinalised">
                    </template>
                        <div class="col-sm-12">
                            <div class="separator"></div>
                        </div>
                    <div class="col-sm-12 top-buffer-s" v-if="display_actions">
                        <div class="row">
                            <div class="col-sm-12">
                                <strong>Action</strong>
                            </div>
                        </div>
                            <div class="row" v-if="display_action_enter_conditions">
                                <div class="col-sm-12">
                                    <button 
                                        class="btn btn-primary w-btn" 
                                        :disabled="can_user_edit" 
                                        @click.prevent="switchStatus('with_assessor_requirements')"
                                    >Enter Conditions</button><br/>
                                </div>
                            </div>

                            <div class="row" v-if="display_action_request_amendment">
                                <div class="col-sm-12">
                                    <button 
                                        class="btn btn-primary top-buffer-s w-btn" 
                                        :disabled="can_user_edit" 
                                        @click.prevent="amendmentRequest()"
                                    >Request Amendment</button><br/>
                                </div>
                            </div>

                            <div class="row" v-if="display_action_propose_decline">
                                <div class="col-sm-12">
                                    <button 
                                        class="btn btn-primary top-buffer-s w-btn" 
                                        :disabled="can_user_edit" 
                                        @click.prevent="proposedDecline()"
                                    >Propose Decline</button>
                                </div>
                            </div>

                            <div class="row" v-if="display_action_back_to_application">
                                <div class="col-sm-12">
                                    <button 
                                        class="btn btn-primary top-buffer-s w-btn" 
                                        :disabled="can_user_edit" 
                                        @click.prevent="switchStatus('with_assessor')"
                                    >Back To Application</button>
                                </div>
                            </div>

                            <div class="row" v-if="display_action_propose_grant">
                                <div class="col-sm-12">
                                    <button 
                                        class="btn btn-primary top-buffer-s w-btn" 
                                        :disabled="can_user_edit" 
                                        @click.prevent="proposedApproval()"
                                    >Propose Grant</button>
                                </div>
                            </div>

                            <div class="row" v-if="display_bypass_endorsement">
                                <div class="col-sm-12">
                                    <button 
                                        class="btn btn-primary top-buffer-s w-btn" 
                                        :disabled="can_user_edit" 
                                        @click.prevent="bypassEndorsement()"
                                    >Bypass Endorsement</button>
                                </div>
                            </div>

                            <div class="row" v-if="display_action_back_to_assessor">
                                <div class="col-sm-12">
                                    <button 
                                        class="btn btn-primary top-buffer-s w-btn" 
                                        :disabled="can_user_edit" 
                                        @click.prevent="switchStatus('with_assessor')"
                                    >Back To Assessor</button>
                                </div>
                            </div>

                            <div class="row" v-if="display_action_back_to_assessor_requirements">
                                <div class="col-sm-12">
                                    <button 
                                        class="btn btn-primary top-buffer-s w-btn" 
                                        :disabled="can_user_edit" 
                                        @click.prevent="backToAssessorRequirements()"
                                    >Back To Assessor</button><br/>
                                </div>
                            </div>

                            <div class="row" v-if="display_action_grant">
                                <div class="col-sm-12" >
                                    <button 
                                        class="btn btn-primary top-buffer-s w-btn" 
                                        @click.prevent="issueProposal()"
                                    >Grant</button><br/>
                                </div>
                            </div>

                            <div class="row" v-if="display_action_decline">
                                <div class="col-sm-12">
                                    <button 
                                        class="btn btn-primary top-buffer-s w-btn" 
                                        @click.prevent="declineProposal()"
                                    >Decline</button><br/>
                                </div>
                            </div>

                            <div class="row" v-if="display_request_endorsement">
                                <div class="col-sm-12">
                                    <button 
                                        class="btn btn-primary top-buffer-s w-btn" 
                                        @click.prevent="requestEndorsement()"
                                    >Request Endorsement</button><br/>
                                </div>
                            </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { constants } from '@/utils/hooks'

export default {
    name: 'Workflow',
    emits: [
        'amendmentRequest',
        'assignRequestUser',
        'assignTo',
        'backToAssessorRequirements',
        'bypassEndorsement',
        'declineProposal',
        'issueProposal',
        'proposedApproval',
        'proposedDecline',
        'requestEndorsement',
        'switchStatus',
        'toggleProposal',
        'toggleRequirements',
    ],
    data: function() {
        let vm = this;
        return {
            showingProposal: false,
            showingRequirements: false,
        }
    },
    props: {
        proposal: {
            type: Object,
            default: null,
        },
        isFinalised: {
            type: Boolean,
            default: false,
        },
        canAction: {
            type: Boolean,
            default: false,
        },
        canAssess: {
            type: Boolean,
            default: false,
        },
        can_user_edit: {
            type: Boolean,
            default: false,
        },
    },
    computed: {
        display_actions: function(){
            return !this.isFinalised && this.canAction
        },
        display_action_request_amendment: function(){
            let display = false
            try {
                if(this.proposal.processing_status === constants.WITH_ASSESSOR && !this.proposal.reissued){
                    display = true
                }
            } catch(err) {}
            return display
        },
        display_action_enter_conditions: function(){
            let display = false
            try {
                if(this.proposal.processing_status === constants.WITH_ASSESSOR){
                    display = true
                }
            } catch(err) {}
            return display
        },
        display_action_propose_decline: function(){
            let display = false
            try {
                if([constants.AU_PROPOSAL, constants.ML_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                    if(this.proposal.processing_status === constants.WITH_ASSESSOR){
                        display = true
                    }
                }
            } catch(err) {}
            return display
        },
        display_action_back_to_application: function(){
            let display = false
            try {
                if(this.proposal.processing_status === constants.WITH_ASSESSOR_REQUIREMENTS){
                    display = true
                }
            } catch(err) {}
            return display
        },
        display_action_propose_grant: function(){
            let display = false
            try {
                if([constants.AU_PROPOSAL, constants.ML_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                    if(this.proposal.processing_status === constants.WITH_ASSESSOR_REQUIREMENTS){
                        display = true
                    }
                }
            } catch(err) {}
            return display
        },
        display_bypass_endorsement: function(){
            let display = false
            try {
                if([constants.AU_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                    if(this.proposal.processing_status === constants.AWAITING_ENDORSEMENT){
                        display = true
                    }
                }
            } catch(err) {}
            return display
        },
        display_request_endorsement: function(){
            let display = false
            try {
                if([constants.AU_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                    if(this.proposal.processing_status === constants.WITH_ASSESSOR && 
                    this.proposal.has_unactioned_endorsements){
                        display = true
                    }
                }
            } catch(err) {}
            return display
        },
        display_action_back_to_assessor: function(){
            let display = false
            try {
                if(this.proposal.processing_status === constants.WITH_APPROVER && this.proposal.proposed_decline_status){
                    display = true
                }
            } catch(err) {}
            console.log('display_action_back_to_assessor: ' + display)
            return display
        },
        display_action_back_to_assessor_requirements: function(){
            let display = false
            try {
                if(this.proposal.processing_status === constants.WITH_APPROVER && !this.proposal.proposed_decline_status){
                    display = true
                }
            } catch(err) {}
            console.log('display_action_back_to_assessor_requirements: ' + display)
            return display
        },
        display_action_grant: function(){
            let display = false
            try {
                if(this.proposal.processing_status === constants.WITH_APPROVER && !this.proposal.proposed_decline_status){
                    display = true
                }
                if([constants.WL_PROPOSAL, constants.AA_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                    if(this.proposal.processing_status === constants.WITH_ASSESSOR_REQUIREMENTS){
                        display = true
                    }
                }
            } catch(err) {}
            return display
        },
        display_action_decline: function(){
            let display = false
            try {
                if(this.proposal.processing_status === constants.WITH_APPROVER){
                    display = true
                }
                if(this.proposal.processing_status === constants.WITH_ASSESSOR){
                    if([constants.WL_PROPOSAL, constants.AA_PROPOSAL].includes(this.proposal.application_type_dict.code)){
                        display = true
                    }
                }
            } catch(err) {}
            return display
        },
    },
    methods: {
        formatDate: function(data){
            return data ? moment(data).format('DD/MM/YYYY HH:mm:ss'): '';
        },
        bypassEndorsement: function(){
            this.$emit('bypassEndorsement')
        },
        requestEndorsement: function(){
            this.$emit('requestEndorsement')
        },
        backToAssessorRequirements: function(){
            this.$emit('backToAssessorRequirements')
        },
        assignRequestUser: function(){
            this.$emit('assignRequestUser')
        },
        assignTo: function(){
            this.$emit('assignTo')
        },
        toggleProposal:function(){
            this.showingProposal = !this.showingProposal;
            this.$emit('toggleProposal', this.showingProposal)
        },
        toggleRequirements:function(){
            this.showingRequirements = !this.showingRequirements;
            this.$emit('toggleRequirements', this.showingRequirements)
        },
        switchStatus: function(value){
            this.$emit('switchStatus', value)
        },
        amendmentRequest: function(){
            this.$emit('amendmentRequest')
        },
        proposedDecline: function(){
            this.$emit('proposedDecline')
        },
        proposedApproval: function(){
            this.$emit('proposedApproval')
        },
        issueProposal: function(){
            this.$emit('issueProposal')
        },
        declineProposal: function(){
            this.$emit('declineProposal')
        },
    }
}
</script>

<style>
.top-buffer-s {
    margin-top: 10px;
}
.actionBtn {
    cursor: pointer;
}
.separator {
    border: 1px solid;
    margin-top: 15px;
    margin-bottom: 10px;
    width: 100%;
}
.w-btn {
    width: 80%;
}
</style>
