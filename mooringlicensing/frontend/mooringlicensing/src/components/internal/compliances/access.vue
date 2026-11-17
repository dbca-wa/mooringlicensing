<template>
<div class="container" id="internalCompliance">
    <div class="row">
        <h3>Compliance with Requirements {{ compliance.reference }}</h3>
        <div class="col-md-3">
        <CommsLogs :comms_url="comms_url" :logs_url="logs_url" :comms_add_url="comms_add_url" :disable_add_entry="false"/>
            <div class="row">
                <div class="panel panel-default">
                    <div class="panel-heading">
                       Submission 
                    </div>
                    <div class="panel-body panel-collapse">
                        <div class="row">
                            <div class="col-sm-12">
                                <strong>Submitted by</strong><br/>
                                {{ compliance.submitter}}
                            </div>
                            <div class="col-sm-12 top-buffer-s">
                                <strong>Lodged on</strong><br/>
                                {{ compliance.lodgement_date | formatDate}}
                            </div>
                            <div class="col-sm-12 top-buffer-s">
                                <table class="table small-table">
                                    <tr>
                                        <th>Lodgement</th>
                                        <th>Date</th>
                                        <th>Action</th>
                                    </tr>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row">
                <div class="panel panel-default">
                    <div class="panel-heading">
                        Workflow 
                    </div>
                    <div class="panel-body panel-collapse">
                        <div class="row">
                            <div class="col-sm-12">
                                <strong>Status</strong><br/>
                                {{ compliance.processing_status }}
                            </div>
                            <div class="col-sm-12 top-buffer-s">
                                <strong>Currently assigned to</strong><br/>
                                <div class="form-group">
                                    <select v-show="isLoading" class="form-control">
                                        <option value="">Loading...</option>
                                    </select>
                                    <select @change="assignTo" 
                                    :disabled="canViewonly || !check_assessor()" 
                                    v-if="!isLoading" class="form-control" 
                                    v-model="compliance.assigned_to">
                                        <option v-for="member in compliance.allowed_assessors" :value="member.ledger_id">{{member.legal_first_name}} {{member.legal_last_name}}</option>
                                    </select>
                                    <a v-if="!canViewonly && check_assessor()" @click.prevent="assignMyself()" class="actionBtn pull-right">Assign to me</a>
                                </div>
                            </div>
                            <div class="col-sm-12 top-buffer-s" v-if="!canViewonly && check_assessor()">
                                <strong>Action</strong><br/>
                                <button class="btn btn-primary" @click.prevent="acceptCompliance()">Accept</button><br/>
                                <button class="btn btn-primary top-buffer-s" @click.prevent="amendmentRequest()">Request Amendment</button>
                                <button class="btn btn-primary top-buffer-s" @click.prevent="discardCompliance()">Discard</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-md-1"></div>
        <div class="col-md-8">
            <div class="row">
                <div class="panel panel-default">
                    <div class="panel-heading">
                        <h3>Compliance with Requirements</h3> 
                    </div>
                    <div class="panel-body panel-collapse">
                        <div class="row">
                           <div class="col-md-12"> 
                            <form class="form-horizontal" name="complianceForm" method="post">
                                <alert :show.sync="showError" type="danger">
                                    <strong>{{errorString}}</strong>
                                </alert>
                                <div class="row">
                                    <div class="form-group">
                                        <label class="col-sm-3 control-label pull-left"  for="Name">Requirement:</label>
                                        <div class="col-sm-6">
                                            {{compliance.requirement}}
                                        </div>
                                    </div>
                                </div>

                                <div class="row">
                                    <div class="form-group">
                                        <label class="col-sm-3 control-label pull-left"  for="Name">Details:</label>
                                        <div class="col-sm-6">
                                            <textarea :disabled="isFinalised" class="form-control" name="detail" placeholder="" v-model="compliance.text"></textarea>
                                        </div>
                                    </div>
                                </div>

                                <div class="row">
                                    <div v-if="hasDocuments" class="form-group">
                                        <div class="col-sm-3 control-label pull-left" >  
                                            <label  for="Name">Documents:</label>
                                        </div> 
                                        <div class="col-sm-6">
                                            <div class="row" v-for="d in compliance.documents">
                                                <a :href="d[1]" target="_blank" class="control-label pull-left">{{d[0]   }}</a>
                                                <span v-if="!isFinalised && d.can_delete">
                                                    <a @click="delete_document(d)" class="fa fa-trash-o control-label" title="Remove file" style="cursor: pointer; color:red;"></a>
                                                </span>
                                                <span v-else >
                                                    <i class="fa fa-info-circle" aria-hidden="true" title="Previously submitted documents cannot be deleted" style="cursor: pointer;"></i>
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="row">
                                    <div v-if="!isFinalised" class="form-group"> 
                                        <label class="col-sm-3 control-label pull-left"  for="Name">Attachments:</label>
                                    <div class="col-sm-6">
                                        <template v-for="(f,i) in files">
                                            <div :class="'row top-buffer file-row-'+i">
                                                <div class="col-sm-4">
                                                    <span v-if="f.file == null" class="btn btn-info btn-file pull-left" style="margin-bottom: 5px">
                                                        Attach File <input type="file" :name="'file-upload-'+i" :class="'file-upload-'+i" @change="uploadFile($event,f)"/>
                                                    </span>
                                                    <span v-else class="btn btn-info btn-file pull-left" style="margin-bottom: 5px">
                                                        Update File <input type="file" :name="'file-upload-'+i" :class="'file-upload-'+i" @change="uploadFile($event,f)"/>
                                                    </span>
                                                </div>
                                                <div class="col-sm-4">
                                                    <span>{{f.name}}</span>
                                                </div>
                                                <div class="col-sm-4">
                                                    <button @click="removeFile(i)" class="btn btn-danger">Remove</button>
                                                </div>
                                            </div>
                                        </template>
                                        <a href="" @click.prevent="attachAnother"><i class="fa fa-lg fa-plus top-buffer-2x"></i></a>
                                    </div>
                                    </div>
                                </div>

                                <div class="row">
                                    <div class="form-group">
                                        <div class="col-lg-2 pull-right">
                                            <button v-if="!isFinalised" @click.prevent="submit()" class="btn btn-primary">Submit</button>
                                        </div>
                                    </div>
                                </div>
                            </form>
                           </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <ComplianceAmendmentRequest ref="amendment_request" :compliance_id="compliance.id"></ComplianceAmendmentRequest>
</div>
</template>
<script>
import $ from 'jquery'
import Vue from 'vue'
import datatable from '@vue-utils/datatable.vue'
import CommsLogs from '@common-utils/comms_logs.vue'
import ComplianceAmendmentRequest from './compliance_amendment_request.vue'
import alert from '@vue-utils/alert.vue'
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'
export default {
  name: 'complianceAccess',
  data() {
    let vm = this;
    return {
        form: null,
        loading: [],
        profile:{},
        compliance: {
            requester: {}
        },
        DATE_TIME_FORMAT: 'DD/MM/YYYY HH:mm:ss',
        members: [],
        // Filters
        logs_url: helpers.add_endpoint_json(api_endpoints.compliances,vm.$route.params.compliance_id+'/action_log'),
        comms_url: helpers.add_endpoint_json(api_endpoints.compliances,vm.$route.params.compliance_id+'/comms_log'),
        comms_add_url: helpers.add_endpoint_json(api_endpoints.compliances,vm.$route.params.compliance_id+'/add_comms_log'),
        errorString: '',
        errors: false,
        files: [
            {
                'file': null,
                'name': ''
            }
        ]
    }
  },
  filters: {
    formatDate: function(data){
        return data ? moment(data).format('DD/MM/YYYY'): '';    }
  },
  beforeRouteEnter: function(to, from, next){
    Vue.http.get(helpers.add_endpoint_json(api_endpoints.compliances,to.params.compliance_id+'/internal_compliance')).then((response) => {
        next(vm => {
            vm.compliance = response.body
            vm.members = vm.compliance.allowed_assessors
        })
    },(error) => {
        console.log(error);
    })
  },
  components: {
    datatable,
    CommsLogs,
    ComplianceAmendmentRequest,
    alert,
  },
  computed: {
    isLoading: function () {
      return this.loading.length > 0;
    },
    canViewonly: function(){
        return this.compliance.processing_status == 'Due' || this.compliance.processing_status == 'Future' || this.compliance.processing_status == 'Approved' || this.compliance.processing_status == 'Discarded';
    },
    showError: function() {
        var vm = this;
        return vm.errors;
    },
    isDiscarded: function(){         
        return this.compliance && (this.compliance.customer_status == "Discarded");
    },
    isFinalised: function(){             
        return this.compliance && (this.compliance.processing_status == "With Assessor" || this.compliance.processing_status == "Approved");
    },
    hasDocuments: function(){             
        return this.compliance && this.compliance.documents;
    }
  },
  methods: {
    delete_document: function(doc){
        let vm= this;
        let data = {'document': doc}
        if(doc)
        {
          vm.$http.post(helpers.add_endpoint_json(api_endpoints.compliances,vm.compliance.id+'/delete_document'),JSON.stringify(data),{
                emulateJSON:true
                }).then((response)=>{               
                    vm.compliance = response.body;       
                },(error)=>{
                    vm.errors = true;
                    vm.errorString = helpers.apiVueResourceError(error);
                });              
        }
    },
    uploadFile(event,file_obj){
            let vm = this;
            let _file = null;
            if (event.target.files && event.target.files[0]) {
                var reader = new FileReader();
                reader.readAsDataURL(event.target.files[0]); 
                reader.onload = function(e) {
                    _file = e.target.result;
                };
                _file = event.target.files[0];
            }
            file_obj.file = _file;
            file_obj.name = _file.name;
    },
    removeFile(index){
            let length = this.files.length;
            $('.file-row-'+index).remove();
            this.files.splice(index,1);
            this.$nextTick(() => {
                length == 1 ? this.attachAnother() : '';
            });
    },
    attachAnother(){
            this.files.push({
                'file': null,
                'name': ''
            })
    },
    submit:function () {
            let vm =this;
            if($(vm.form).valid()){
                vm.sendData();
            }                
    },
    sendData:function(){
            let vm = this;
            vm.errors = false;
            let data = new FormData(vm.form);
            vm.addingComms = true;            
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.compliances,vm.compliance.id+'/submit'),data,{
                emulateJSON:true
                }).then((response)=>{
                    vm.addingCompliance = false;                
                    vm.compliance = response.body;
                    swal(
                        'Submitted',
                        'Compliance has been submitted on the holder\'s behalf',
                        'success'
                    );
                    vm.$router.push({ path: '/internal/compliances' });
                        
                },(error)=>{
                    vm.errors = true;
                    vm.addingCompliance = false;
                    vm.errorString = helpers.apiVueResourceError(error);
                });     
    },

    commaToNewline(s){
        return s.replace(/[,;]/g, '\n');
    },
  
    assignMyself: function(){
        let vm = this;
        vm.$http.get(helpers.add_endpoint_json(api_endpoints.compliances,(vm.compliance.id+'/assign_request_user')))
        .then((response) => {            
            vm.compliance = response.body;
        }, (error) => {
            console.log(error);
        });
    },
    assignTo: function(){
        let vm = this;
        if ( vm.compliance.assigned_to !== null && vm.compliance.assigned_to !== undefined){
            let data = {'user_id': vm.compliance.assigned_to};
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.compliances,(vm.compliance.id+'/assign_to')),JSON.stringify(data),{
                emulateJSON:true
            }).then((response) => {                
                vm.compliance = response.body;
            }, (error) => {
                console.log(error);
            });
            
        }
        else if (vm.compliance.assigned_to !== undefined) {
            vm.$http.get(helpers.add_endpoint_json(api_endpoints.compliances,(vm.compliance.id+'/unassign')))
            .then((response) => {
                console.log(response);
                vm.compliance = response.body;
            }, (error) => {
                console.log(error);
            });
        }
    },
    acceptCompliance: function() {
        let vm = this;
        swal({
            title: "Accept Compliance with requirements",
            text: "Are you sure you want to accept this compliance with requirements?",
            type: "question",
            showCancelButton: true,
            confirmButtonText: 'Accept'
        }).then(() => {
            vm.$http.get(helpers.add_endpoint_json(api_endpoints.compliances,(vm.compliance.id+'/accept')))
            .then((response) => {
                console.log(response);
                vm.compliance = response.body;
                vm.$router.push({ name: 'internal-compliances-dash'}); //Navigate to dashboard
            }, (error) => {
                console.log(error);
            });
        },(error) => {

        });

    },
    amendmentRequest: function(){   
            this.$refs.amendment_request.amendment.compliance = this.compliance.id;                     
            this.$refs.amendment_request.isModalOpen = true;
    },
    discardCompliance: function() {
        let vm = this;
        swal({
            title: "Discard Compliance with",
            text: "Are you sure you want to discard this compliance?",
            type: "question",
            showCancelButton: true,
            confirmButtonText: 'Discard'
        }).then(() => {
            vm.$http.get(helpers.add_endpoint_json(api_endpoints.compliances,(vm.compliance.id+'/discard')))
            .then((response) => {
                console.log(response);
                vm.compliance = response.body;
                vm.$router.push({ name: 'internal-compliances-dash'}); //Navigate to dashboard
            }, (error) => {
                console.log(error);
            });
        },(error) => {

        });

    },

    fetchProfile: function(){
        let vm = this;
        Vue.http.get(api_endpoints.profile).then((response) => {
            vm.profile = response.body
                              
         },(error) => {
            console.log(error);
                
        })
        },

    check_assessor: function(){
        let vm = this;
        
        var assessor = vm.members.filter(function(elem){
                    return(elem.id==vm.profile.id);
                });
                if (assessor.length > 0)
                    return true;
                else
                    return false;
     },
  },
  mounted: function () {
    let vm = this;
    
    this.fetchProfile();
    vm.form = document.forms.complianceForm;
  }
}
</script>
<style scoped>
.top-buffer-s {
    margin-top: 10px;
}
.actionBtn {
    cursor: pointer;
}
.hidePopover {
    display: none;
}
</style>
