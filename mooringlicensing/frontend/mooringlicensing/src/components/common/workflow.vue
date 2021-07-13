<template>
            <div class="row">
                <div class="panel panel-default">
                    <div class="panel-heading">
                        Workflow
                    </div>
                    <div class="panel-body panel-collapse">
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
                                <div class="form-group">
                                    <template v-if="proposal.processing_status == 'With Approver'">
                                            <select ref="assigned_officer" :disabled="!canAction" class="form-control" v-model="proposal.assigned_approver">
                                                <option v-for="member in proposal.allowed_assessors" :value="member.id">{{ member.first_name }} {{ member.last_name }}</option>
                                            </select>
                                            <a v-if="canAssess && proposal.assigned_approver != proposal.current_assessor.id" @click.prevent="assignRequestUser()" class="actionBtn pull-right">Assign to me</a>
                                    </template>
                                    <template v-else>
                                            <select ref="assigned_officer" :disabled="!canAction" class="form-control" v-model="proposal.assigned_officer">
                                                <option v-for="member in proposal.allowed_assessors" :value="member.id">{{ member.first_name }} {{ member.last_name }}</option>
                                            </select>
                                            <a v-if="canAssess && proposal.assigned_officer != proposal.current_assessor.id" @click.prevent="assignRequestUser()" class="actionBtn pull-right">Assign to me</a>
                                    </template>
                                </div>
                            </div>

                            <template v-if="proposal.processing_status == 'With Assessor (Requirements)' || proposal.processing_status == 'With Approver' || isFinalised">
                                <div class="col-sm-12">
                                    <strong>Proposal</strong><br/>
                                    <a class="actionBtn" v-if="!showingProposal" @click.prevent="toggleProposal()">Show Proposal</a>
                                    <a class="actionBtn" v-else @click.prevent="toggleProposal()">Hide Proposal</a>
                                </div>
                                <div class="col-sm-12">
                                    <div class="separator"></div>
                                </div>
                            </template>
                            <template v-if="proposal.processing_status == 'With Approver' || isFinalised">
                                <div class="col-sm-12">
                                    <strong>Requirements</strong><br/>
                                    <a class="actionBtn" v-if="!showingRequirements" @click.prevent="toggleRequirements()">Show Requirements</a>
                                    <a class="actionBtn" v-else @click.prevent="toggleRequirements()">Hide Requirements</a>
                                </div>
                                <div class="col-sm-12">
                                    <div class="separator"></div>
                                </div>
                            </template>
                            <div class="col-sm-12 top-buffer-s" v-if="display_actions">
                                <div class="row">
                                    <div class="col-sm-12">
                                        <strong>Action</strong>
                                    </div>
                                </div>
<!--
                                <template v-if="proposal.processing_status == 'With Assessor'">
-->
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
<!--
                                </template>
                                <template v-else-if="proposal.processing_status == 'With Assessor (Requirements)'">
-->
                                    <div class="row" v-if="display_action_back_to_application">
                                        <div class="col-sm-12">
                                            <button 
                                                class="btn btn-primary top-buffer-s w-btn" 
                                                :disabled="can_user_edit" 
                                                @click.prevent="switchStatus('with_assessor')"
                                            >Back To Application</button>
                                        </div>
                                    </div>

<!--
                                        <div class="col-sm-12" v-if="requirementsComplete">
                                        <div class="col-sm-12" v-if="proposal.requirements_completed">
-->
                                    <div class="row" v-if="display_action_propose_grant">
                                        <div class="col-sm-12">
                                            <button 
                                                class="btn btn-primary top-buffer-s w-btn" 
                                                :disabled="can_user_edit" 
                                                @click.prevent="proposedApproval()"
                                            >Propose Grant</button>
                                        </div>
                                    </div>
<!--
                                </template>
                                <template v-else-if="proposal.processing_status == 'With Approver'">
                                    <div class="row" v-if="display_action_back_to_assessor">
                                        <div class="col-sm-12" v-if="proposal.proposed_decline_status">
-->
                                    <div class="row" v-if="display_action_back_to_assessor">
                                        <div class="col-sm-12">
                                            <button 
                                                class="btn btn-primary top-buffer-s w-btn" 
                                                :disabled="can_user_edit" 
                                                @click.prevent="switchStatus('with_assessor')"
                                            ><!-- Back To Processing -->Back To Assessor</button>
                                        </div>
                                    </div>

<!--
                                        <div class="col-sm-12" v-else>
-->
                                    <div class="row" v-if="display_action_back_to_assessor_requirements">
                                        <div class="col-sm-12">
                                            <button 
                                                class="btn btn-primary top-buffer-s w-btn" 
                                                :disabled="can_user_edit" 
                                                @click.prevent="switchStatus('with_assessor_requirements')"
                                            ><!-- Back To Requirements -->Back To Assessor</button><br/>
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
<!--
                                </template>
-->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
</template>

<script>
import { constants } from '@/utils/hooks'

export default {
    name: 'Submission',
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
        //display_status: {
        //    type: String,
        //    default: '',
        //},
        //processing_status: {
        //    type: String,
        //    default: '',
        //},
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
        //proposed_decline_status: {
        //    type: Boolean,
        //    default: false,
        //},
    },
    computed: {
        display_actions: function(){
            return !this.isFinalised && this.canAction
        },
        display_action_request_amendment: function(){
            let display = false
            try {
                if(this.proposal.processing_status === constants.WITH_ASSESSOR){
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
                    //if(this.proposal.requirements_completed){
                    //    display = true
                    //}
                    if(this.proposal.processing_status === constants.WITH_ASSESSOR_REQUIREMENTS){
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
                if(this.proposal.processing_status === constants.WITH_APPROVER){
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
    filters: {
        formatDate: function(data){
            return data ? moment(data).format('DD/MM/YYYY HH:mm:ss'): '';
        }
    },
    methods: {
        assignRequestUser: function(){
            this.$emit('assignRequestUser')
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
