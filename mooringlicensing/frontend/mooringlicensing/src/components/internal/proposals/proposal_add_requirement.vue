<template>
    <div id="proposalRequirementDetail">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" title="Requirement" large>
            <div class="container-fluid">
                <div class="row">
                    <form   name="requirementForm">
                        <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="row mb-3">
                                <label class="form-check-label form-label"><input class="form-check-input" type="radio" name="requirementType" :value="true" v-model="requirement.standard">Standard Requirement</label>
                                <label class="form-check-label"><input class="form-check-input" type="radio" name="requirementType" :value="false" v-model="requirement.standard">Free Text Requirement</label>
                            </div>
                        </div>
                        <div class="col-sm-12">
                            <div class="row mb-3">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="form-label float-start"  for="Name">Requirement</label>
                                    </div>
                                    <div class="col-sm-9" v-show="requirement.standard">
                                        <div>
                                            <select class="form-control" ref="standard_req" name="standard_requirement" v-model="requirement.standard_requirement" style="width:70%">
                                                <option v-for="r in requirements" :value="r.id">{{r.code}}: {{r.text}}</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div class="col-sm-9" v-show="!requirement.standard">
                                        <textarea style="width: 70%;" class="form-control" name="free_requirement" v-model="requirement.free_requirement"></textarea>
                                    </div>
                                </div>
                            </div>
                            <div class="row mb-3">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <label class="form-label float-start"  for="Name">Due Date</label>
                                    </div>
                                    <div class="col-sm-9">
                                        <div style="width: 70%;">
                                            <input
                                                type="date"
                                                class="form-control"
                                                name="due_date"
                                                v-model="requirement.due_date"
                                                :min="today"
                                            >
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <template v-if="validDate">
                                <div class="row mb-3">
                                    <div class="row">
                                        <div class="col-sm-3">
                                            <label class="form-label float-start"  for="Name">Recurrence</label>
                                        </div>
                                        <div class="col-sm-9">
                                            <label class="form-check-inline"><input type="checkbox" v-model="requirement.recurrence"></label>
                                        </div>
                                    </div>
                                </div>
                                <template v-if="requirement.recurrence">
                                    <div class="row mb-3">
                                        <div class="row">
                                            <div class="col-sm-3">
                                                <label class="form-label float-start"  for="Name">Recurrence pattern</label>
                                            </div>
                                            <div class="col-sm-9">
                                                <label class="form-check-label form-label"><input class="form-check-input" type="radio" name="recurrenceSchedule" value="1" v-model="requirement.recurrence_pattern">Weekly</label>
                                                <label class="form-check-label form-label"><input class="form-check-input" type="radio" name="recurrenceSchedule" value="2" v-model="requirement.recurrence_pattern">Monthly</label>
                                                <label class="form-check-label form-label"><input class="form-check-input" type="radio" name="recurrenceSchedule" value="3" v-model="requirement.recurrence_pattern">Yearly</label>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="row mb-3">
                                        <div class="row">
                                            <div class="col-sm-12">
                                                <label class="form-label"  for="Name">
                                                    <strong class="float-start">Recur every</strong> 
                                                    <input class="float-start" style="width:10%; margin-left:10px;" type="number" name="schedule" v-model="requirement.recurrence_schedule"/> 
                                                    <strong v-if="requirement.recurrence_pattern == '1'" class="float-start" style="margin-left:10px;">week(s)</strong>
                                                    <strong v-else-if="requirement.recurrence_pattern == '2'" class="float-start" style="margin-left:10px;">month(s)</strong>
                                                    <strong v-else-if="requirement.recurrence_pattern == '3'" class="float-start" style="margin-left:10px;">year(s)</strong>
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                </template>
                            </template>
                        </div>
                    </form>
                </div>
            </div>
            <div slot="footer">
                <template v-if="requirement.id">
                    <button type="button" v-if="updatingRequirement" disabled class="btn btn-primary me-2" @click="ok"><i class="fa fa-spinnner fa-spin"></i> Updating</button>
                    <button type="button" v-else class="btn btn-primary me-2" @click="ok">Update</button>
                </template>
                <template v-else>
                    <button type="button" v-if="addingRequirement" disabled class="btn btn-primary me-2" @click="ok"><i class="fa fa-spinner fa-spin"></i> Adding</button>
                    <button type="button" v-else class="btn btn-primary me-2" @click="ok">Add</button>
                </template>
                <button type="button" class="btn btn-secondary me-2" @click="cancel">Cancel</button>
            </div>
        </modal>
    </div>
</template>

<script>
import $ from 'jquery'
import modal from '@vue-utils/bootstrap-modal.vue'
import alert from '@vue-utils/alert.vue'
import {helpers,api_endpoints} from "@/utils/hooks.js"
export default {
    name:'Requirement-Detail',
    components:{
        modal,
        alert
    },
    props:{
            proposal_id:{
                type:Number,
                required: true
            },
            requirements: {
                type: Array,
                required: true
            },
            sitetransfer_approval_id:{
                type:Number,
                required: false
            },
    },
    data:function () {
        let vm = this;

        let tomorrow = new Date()
        tomorrow.setDate(tomorrow.getDate() + 1)

        return {
            isModalOpen:false,
            form:null,
            requirement: {
                due_date: '',
                standard: true,
                recurrence: false,
                recurrence_pattern: '1',
                proposal: vm.proposal_id,
                sitetransfer_approval: vm.sitetransfer_approval_id,
            },
            addingRequirement: false,
            updatingRequirement: false,
            validation_form: null,
            type: '1',
            errors: false,
            errorString: '',
            successString: '',
            success:false,
            validDate: false
        }
    },
    computed: {
        showError: function() {
            var vm = this;
            return vm.errors;
        },
        due_date: {
            cache: false,
            get(){
                if (this.requirement.due_date == undefined  || this.requirement.due_date == '' || this.requirement.due_date ==  null){
                    return '';
                }
                else{
                    return this.requirement.due_date;
                }
            }
        },
        today() {
            return new Date().toISOString().split('T')[0];
        }
    },
    watch: {
        due_date: function(){
            this.validDate = moment(this.requirement.due_date,'DD/MM/YYYY').isValid();
        },
    },
    methods:{
        initialiseRequirement: function(){
            this.requirement = {
                due_date: '',
                standard: true,
                recurrence: false,
                recurrence_pattern: '1',
                proposal: vm.proposal_id
            }
        },
        ok:function () {
            let vm =this;
            if($(vm.form).valid()){
                vm.sendData();
            }
        },
        cancel:function () {
            this.close()
        },
        close:function () {
            this.isModalOpen = false;
            $(this.$refs.standard_req).val(null).trigger('change');
            this.requirement = {
                standard: true,
                recurrence: false,
                due_date: '',
                recurrence_pattern: '1',
                proposal: this.proposal_id
            };
            this.errors = false;
            $('.has-error').removeClass('has-error');
            this.validation_form.resetForm();
        },
        fetchContact: function(id){
            let vm = this;
            vm.$http.get(api_endpoints.contact(id)).then((response) => {
                vm.contact = response.body; vm.isModalOpen = true;
            },(error) => {
                console.log(error);
            } );
        },
        sendData:function(){
            let vm = this;
            vm.errors = false;
            let requirement = JSON.parse(JSON.stringify(vm.requirement));
            if (requirement.standard){
                requirement.free_requirement = '';
            }
            else{
                requirement.standard_requirement = '';
                $(this.$refs.standard_req).val(null).trigger('change');
            }
            if (!requirement.due_date){
                requirement.due_date = null;
                requirement.recurrence = false;
                delete requirement.recurrence_pattern;
                requirement.recurrence_schedule ? delete requirement.recurrence_schedule : '';
            }
            if (vm.requirement.id){
                vm.updatingRequirement = true;
                vm.$http.put(helpers.add_endpoint_json(api_endpoints.proposal_requirements,requirement.id),JSON.stringify(requirement),{
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.updatingRequirement = false;
                        vm.$parent.updatedRequirements();
                        vm.close();
                    },(error)=>{
                        vm.errors = true;
                        vm.errorString = helpers.apiVueResourceError(error);
                        vm.updatingRequirement = false;
                    });
            } else {
                vm.addingRequirement = true;
                vm.$http.post(api_endpoints.proposal_requirements,JSON.stringify(requirement),{
                        emulateJSON:true,
                    }).then((response)=>{
                        vm.addingRequirement = false;
                        vm.close();
                        vm.$parent.updatedRequirements();
                    },(error)=>{
                        vm.errors = true;
                        vm.addingRequirement = false;
                        vm.errorString = helpers.apiVueResourceError(error);
                    });
            }
        },
        addFormValidations: function() {
            let vm = this;
            vm.validation_form = $(vm.form).validate({
                rules: {
                    standard_requirement:{
                        required: {
                            depends: function(el){
                                return vm.requirement.standard;
                            }
                        }
                    },
                    free_requirement:{
                        required: {
                            depends: function(el){
                                return !vm.requirement.standard;
                            }
                        }
                    },
                    schedule:{
                        required: {
                            depends: function(el){
                                return vm.requirement.recurrence;
                            }
                        }
                    }
                },
                messages: {
                    arrival:"field is required",
                    departure:"field is required",
                    campground:"field is required",
                    campsite:"field is required"
                },
                showErrors: function(errorMap, errorList) {
                    helpers.showValidationErrors.call(
                        this,
                        errorMap,
                        errorList
                    );
                },
            });
       },
       eventListeners:function () {
            let vm = this;
            // Intialise select2
            $(vm.$refs.standard_req).select2({
                theme: "bootstrap-5",
                allowClear: true,
                placeholder:"Select Requirement",
                dropdownParent: $(vm.$refs.standard_req).parent(),
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.requirement.standard_requirement = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.requirement.standard_requirement = selected.val();
            }).
            on("select2:open",function (e) {
                const searchField = $(".select2-search__field")
                // move focus to select2 field
                searchField[0].focus();
            });
       }
   },
   mounted:function () {
        let vm =this;
        vm.form = document.forms.requirementForm;
        vm.addFormValidations();
        this.$nextTick(()=>{
            vm.eventListeners();
        });
   }
}
</script>