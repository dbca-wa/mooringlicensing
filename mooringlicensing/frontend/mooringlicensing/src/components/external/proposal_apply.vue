<template lang="html">
    <div class="container" >
        <!--button type="button" @click="createML">Mooring Licence Application</button-->
        <div class="row">
            <div class="col-sm-12">
                <form class="form-horizontal" name="personal_form" method="post">
                    <FormSection label="Apply for">
                        <div>
                            <div class="col-sm-12" style="margin-left:20px">
                                <div class="form-group">
                                    <label>Waiting List</label>
                                    <div v-if="wlaApprovals.length<=1">
                                        <div v-for="(application_type, index) in wlaChoices">
                                            <input 
                                            type="radio" 
                                            name="applicationType" 
                                            :id="application_type.code + '_' + index" 
                                            value="application_type" 
                                            @change="selectApplication(application_type)"
                                            />
                                            <label :for="application_type.code + '_' + index" style="font-weight:normal">{{ application_type.new_application_text }}</label>
                                        </div>
                                    </div>
                                    <div v-else>
                                        <div class="row" v-for="application_type in wlaMultiple">
                                            <div class="col-sm-5">
                                                <input 
                                                type="radio" 
                                                name="applicationType" 
                                                :id="application_type.code" 
                                                value="application_type" 
                                                @change="selectApplication(application_type)"
                                                />
                                                <label :for="application_type.code" style="font-weight:normal">{{ application_type.new_application_text }}</label>
                                            </div>
                                            <span class="pull-left col-sm-2" v-if="application_type.multiple">
                                                <select class="form-control" v-model="selectedCurrentProposal">
                                                    <option v-for="approval in wlaApprovals" :value="approval.current_proposal_id">
                                                        {{ approval.lodgement_number }}
                                                    </option>
                                                </select>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label>Annual Admission</label>
                                    <div v-if="aaaApprovals.length<=1">
                                        <div v-for="(application_type, index) in aaaChoices">
                                            <input 
                                            type="radio" 
                                            name="applicationType" 
                                            :id="application_type.code + '_' + index" 
                                            value="application_type" 
                                            @change="selectApplication(application_type)"
                                            />
                                            <label :for="application_type.code + '_' + index" style="font-weight:normal">{{ application_type.new_application_text }}</label>
                                        </div>
                                    </div>
                                    <div v-else>
                                        <div class="row" v-for="application_type in aaaMultiple">
                                            <div class="col-sm-5">
                                                <input 
                                                type="radio" 
                                                name="applicationType" 
                                                :id="application_type.code" 
                                                value="application_type" 
                                                @change="selectApplication(application_type)"
                                                />
                                                <label :for="application_type.code" style="font-weight:normal">{{ application_type.new_application_text }}</label>
                                            </div>
                                            <span class="pull-left col-sm-2" v-if="application_type.multiple">
                                                <select class="form-control" v-model="selectedCurrentProposal">
                                                    <option v-for="approval in aaaApprovals" :value="approval.current_proposal_id">
                                                        {{ approval.lodgement_number }}
                                                    </option>
                                                </select>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label>Authorised User</label>
                                    <div v-if="auaApprovals.length<=1">
                                        <div v-for="(application_type, index) in auaChoices">
                                            <input 
                                            type="radio" 
                                            name="applicationType" 
                                            :id="application_type.code" 
                                            value="application_type" 
                                            @change="selectApplication(application_type)"
                                            />
                                            <label :for="application_type.code + '_' + index" style="font-weight:normal">{{ application_type.new_application_text }}</label>
                                        </div>
                                    </div>
                                    <div v-else>
                                        <div class="row" v-for="application_type in auaMultiple">
                                            <div class="col-sm-5">
                                                <input 
                                                type="radio" 
                                                name="applicationType" 
                                                :id="application_type.code + '_' + index" 
                                                value="application_type" 
                                                @change="selectApplication(application_type)"
                                                />
                                                <label :for="application_type.code" style="font-weight:normal">{{ application_type.new_application_text }}</label>
                                            </div>
                                            <span class="pull-left col-sm-2" v-if="application_type.multiple">
                                                <select class="form-control" v-model="selectedCurrentProposal">
                                                    <option v-for="approval in auaApprovals" :value="approval.current_proposal_id">
                                                        {{ approval.lodgement_number }}
                                                    </option>
                                                </select>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div v-if="mlApprovals.length" class="form-group">
                                    <label>Mooring Licence</label>
                                    <div v-if="mlApprovals.length<=1">
                                        <div v-for="(application_type, index) in mlChoices">
                                            <input 
                                            type="radio" 
                                            name="applicationType" 
                                            :id="application_type.code + '_' + index" 
                                            value="application_type" 
                                            @change="selectApplication(application_type)"
                                            />
                                            <label :for="application_type.code + '_' + index" style="font-weight:normal">{{ application_type.new_application_text }}</label>
                                        </div>
                                    </div>
                                    <div v-else>
                                        <div class="row" v-for="application_type in mlMultiple">
                                            <div class="col-sm-5">
                                                <input 
                                                type="radio" 
                                                name="applicationType" 
                                                :id="application_type.code" 
                                                value="application_type" 
                                                @change="selectApplication(application_type)"
                                                />
                                                <label :for="application_type.code" style="font-weight:normal">{{ application_type.new_application_text }}</label>
                                            </div>
                                            <span class="pull-left col-sm-2" v-if="application_type.multiple">
                                                <select class="form-control" v-model="selectedCurrentProposal">
                                                    <option v-for="approval in mlApprovals" :value="approval.current_proposal_id">
                                                        {{ approval.lodgement_number }}
                                                    </option>
                                                </select>
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                <!--div class="form-group">
                                    <label>Authorised User</label>
                                    <div v-for="application_type in auaChoices">
                                        <input 
                                        type="radio" 
                                        name="applicationType" 
                                        :id="application_type.code" 
                                        value="application_type" 
                                        @change="selectApplication(application_type)"
                                        />
                                        <label :for="application_type.code" style="font-weight:normal">{{ application_type.new_application_text }}</label>
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label>Mooring Licence</label>
                                    <div v-for="application_type in mlChoices">
                                        <input 
                                        type="radio" 
                                        name="applicationType" 
                                        :id="application_type.code" 
                                        value="application_type" 
                                        @change="selectApplication(application_type)"
                                        />
                                        <label :for="application_type.code" style="font-weight:normal">{{ application_type.new_application_text }}</label>
                                    </div>
                                </div-->


                            </div>
                        </div>
                    </FormSection>

                    <!--div class="col-sm-12" v-show="has_active_proposals()">
                        <p style="color:red;"> An active application already exists in the system: </p>
                        <p style="color:red;"> {{ active_proposals() }}</p>
                    </div-->
                    <div class="col-sm-12">
                        <button v-if="!creatingProposal" :disabled="isDisabled" @click.prevent="submit()" class="btn btn-primary pull-right">Continue</button>
                        <button v-else disabled class="pull-right btn btn-primary"><i class="fa fa-spin fa-spinner"></i>&nbsp;Creating</button>
                    </div>
                  </form>
            </div>
        </div>
    </div>
</template>
<script>
import Vue from 'vue'
import FormSection from '@/components/forms/section_toggle.vue'
//require('bootstrap/dist/css/bootstrap.css')
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'
import utils from './utils'
export default {
  data: function() {
    let vm = this;
    return {
        "proposal": null,
        profile: {
        },
        "loading": [],
        form: null,
        selectedApplication: {},
        selectedCurrentProposal: null,
        //selected_application_name: '',
        application_types: [],
        wlaChoices: [],
        aaaChoices: [],
        auaChoices: [],
        mlChoices: [],
        wlaApprovals: [],
        aaaApprovals: [],
        auaApprovals: [],
        mlApprovals: [],
        wlaMultiple: [],
        aaaMultiple: [],
        auaMultiple: [],
        mlMultiple: [],
        creatingProposal: false,
        //site_url: (api_endpoints.site_url.endsWith("/")) ? (api_endpoints.site_url): (api_endpoints.site_url + "/"),
    }
  },
  components: {
      FormSection
  },
  computed: {
    isLoading: function() {
      return this.loading.length > 0
    },
    isDisabled: function() {
        /*
        let vm = this;
        if ((vm.org_applicant == '' && vm.yourself=='') ||( vm.selected_application_id == '')){
                return true;
            }
            */
        let disabled = true;
        if (this.selectedApplication && this.selectedApplication.code) {
            disabled = false;
        }
        return disabled;
    },
    alertText: function() {
        let text = '';
        if (this.selectedApplication && this.selectedApplication.description) {
            text = this.selectedApplication.description;
        }
		if (this.selectedApplication.code == 'wla') {
            text = "a " + text;
		} else {
        	//return "a Filming";
            text = "an "+ text;
        }
        return text
	},

  },
  methods: {
      parseApprovals: function() {
          this.application_types.forEach(app => {
              if (app.code === 'wla' && app.lodgement_number) {
                  this.wlaApprovals.push({
                      lodgement_number: app.lodgement_number,
                      current_proposal_id: app.current_proposal_id,
                  });
              } else if (app.code === 'aap' && app.lodgement_number) {
                  this.aaaApprovals.push({
                      lodgement_number: app.lodgement_number,
                      current_proposal_id: app.current_proposal_id,
                  });
              } else if (app.code === 'aup' && app.lodgement_number) {
                  this.auaApprovals.push({
                      lodgement_number: app.lodgement_number,
                      current_proposal_id: app.current_proposal_id,
                  });
              } else if (app.code === 'ml' && app.lodgement_number) {
                  this.mlApprovals.push({
                      lodgement_number: app.lodgement_number,
                      current_proposal_id: app.current_proposal_id,
                  });
              }
          });
      },
      parseWla: function() {
          if (this.wlaApprovals.length>1) {
              // new app
              for (let app of this.application_types) {
                  if (app.code === 'wla' && !app.approval_id) {
                      this.wlaMultiple.push(app)
                  }
              }
              // add generic
              this.wlaMultiple.push({
                  new_application_text: "I want to amend or renew my current waiting list allocation",
                  description: "Waiting List Application",
                  code: "wla_multiple",
                  multiple: true
              })
          } else {
              // add wla approval to wlaChoices
              for (let app of this.application_types) {
                  if (app.code === 'wla') {
                      this.wlaChoices.push(app);
                  }
              }
          }
      },
      parseAaa: function() {
          if (this.aaaApprovals.length>1) {
              // new app
              for (let app of this.application_types) {
                  if (['aaa','aap'].includes(app.code) && !app.approval_id) {
                  //if (app.code === 'wla' && !app.approval_id) {
                      this.aaaMultiple.push(app)
                  }
              }
              // add generic
              this.aaaMultiple.push({
                  new_application_text: "I want to amend or renew my current annual admission permit",
                  description: "Annual Admission Application",
                  code: "aaa_multiple",
                  multiple: true
              })
          } else {
              // add wla approval to wlaChoices
              for (let app of this.application_types) {
                  //if (app.code === 'wla') {
                  if (['aaa','aap'].includes(app.code)) {
                      this.aaaChoices.push(app);
                  }
              }
          }
      },
      parseAua: function() {
          if (this.auaApprovals.length>1) {
              // new app
              for (let app of this.application_types) {
                  if (['aua','aup'].includes(app.code) && !app.approval_id) {
                  //if (app.code === 'wla' && !app.approval_id) {
                      this.auaMultiple.push(app)
                  }
              }
              // add generic
              this.auaMultiple.push({
                  new_application_text: "I want to amend or renew my current authorised user permit",
                  description: "Authorised User Application",
                  code: "aua_multiple",
                  multiple: true
              })
          } else {
              // add wla approval to wlaChoices
              for (let app of this.application_types) {
                  //if (app.code === 'wla') {
                  if (['aua','aup'].includes(app.code)) {
                      this.auaChoices.push(app);
                  }
              }
          }
      },
      parseMl: function() {
          if (this.mlApprovals.length>1) {
              /*
              // new app
              for (let app of this.application_types) {
                  if (['aua','aup'].includes(app.code) && !app.approval_id) {
                  //if (app.code === 'wla' && !app.approval_id) {
                      this.auaMultiple.push(app)
                  }
              }
              */
              // add generic
              this.mlMultiple.push({
                  new_application_text: "I want to amend or renew my current mooring licence",
                  description: "Mooring Licence Application",
                  code: "ml_multiple",
                  multiple: true
              })
          } else {
              // add wla approval to wlaChoices
              for (let app of this.application_types) {
                  //if (app.code === 'wla') {
                  if (app.code==="ml") {
                      this.mlChoices.push(app);
                  }
              }
          }
      },
    selectApplication(applicationType) {
        this.selectedCurrentProposal = null;
        this.selectedApplication = Object.assign({}, applicationType)
        if (this.selectedApplication.current_proposal_id) {
            this.selectedCurrentProposal = this.selectedApplication.current_proposal_id;
        }
    },
    submit: function() {
        //let vm = this;
        swal({
            title: "Create " + this.selectedApplication.description,
            text: "Are you sure you want to create " + this.alertText + "?",
            type: "question",
            showCancelButton: true,
            confirmButtonText: 'Accept'
        }).then(() => {
            this.createProposal();
            /*
            if (!vm.has_active_proposals()) {
         	    vm.createProposal();
            }
            */
        },(error) => {
        });
    },
      /*
    createML: async function() {
        const res = await this.$http.post(api_endpoints.mooringlicenceapplication);
        const proposal = res.body;
		this.$router.push({
			name:"draft_proposal",
			params:{proposal_id:proposal.id}
		});
        this.creatingProposal = false;
    },
    */
    createProposal: async function () {
        this.$nextTick(async () => {
            let res = null;
            try {
                this.creatingProposal = true;
                const url = helpers.add_endpoint_json(api_endpoints.proposal,(
                    this.selectedCurrentProposal+'/renew_amend_approval_wrapper')
                )
                if (this.selectedApplication && ['wla', 'wla_multiple'].includes(this.selectedApplication.code)) {
                    if (this.selectedCurrentProposal) {
                        res = await this.$http.get(url);
                    } else {
                        res = await this.$http.post(api_endpoints.waitinglistapplication);
                    }
                } else if (this.selectedApplication && ['aaa','aap','aaa_multiple'].includes(this.selectedApplication.code)) {
                    if (this.selectedCurrentProposal) {
                        res = await this.$http.get(url);
                    } else {
                        res = await this.$http.post(api_endpoints.annualadmissionapplication);
                    }
                } else if (this.selectedApplication && ['aua','aup','aua_multiple'].includes(this.selectedApplication.code)) {
                    if (this.selectedCurrentProposal) {
                        res = await this.$http.get(url);
                    } else {
                        res = await this.$http.post(api_endpoints.authoriseduserapplication);
                    }
                } else if (this.selectedApplication && ['ml','ml_multiple'].includes(this.selectedApplication.code)) {
                    res = await this.$http.get(url);
                } 
                const proposal = res.body;
                this.$router.push({
                    name:"draft_proposal",
                    params:{proposal_id:proposal.id}
                });
                this.creatingProposal = false;
            } catch(error) {
                console.log(error)
                await swal({
                title: "Renew/Amend Approval",
                text: error.body,
                type: "error",
                });
                this.$router.go();
            }
        });
    },
	searchList: function(id, search_list){
        /* Searches for dictionary in list */
        for (var i = 0; i < search_list.length; i++) {
            if (search_list[i].value == id) {
                return search_list[i];
            }
        }
        return [];
    },
    fetchApplicationTypes: async function(){
        const response = await this.$http.get(api_endpoints.application_types_dict+'?apply_page=True');
        for (let app_type of response.body) {
            this.application_types.push(app_type)
        }
    },
      /*
    fetchExistingMooringLicences: async function(){
        const response = await this.$http.get(api_endpoints.existing_mooring_licences);
        for (let ml of response.body) {
            this.application_types.push(ml)
        }
    },
    */
    fetchExistingLicences: async function(){
        const response = await this.$http.get(api_endpoints.existing_licences);
        for (let l of response.body) {
            this.application_types.push(l)
        }
    },

  },
  mounted: async function() {
    //let vm = this;
    await this.fetchApplicationTypes();
    //await this.fetchExistingMooringLicences();
    await this.fetchExistingLicences();
    this.parseApprovals();
    this.parseWla();
    this.parseAaa();
    this.parseAua();
    this.parseMl();
    this.form = document.forms.new_proposal;
  },
  beforeRouteEnter: function(to, from, next) {

    let initialisers = [
        utils.fetchProfile(),
        
        //utils.fetchProposal(to.params.proposal_id)
    ]
    next(vm => {
        vm.loading.push('fetching profile')
        Promise.all(initialisers).then(data => {
            vm.profile = data[0];
            //vm.proposal = data[1];
            vm.loading.splice('fetching profile', 1)
        })
    })
    
  }
}
</script>

<style lang="css">
input[type=text], select{
    width:40%;
    box-sizing:border-box;

    min-height: 34px;
    padding: 0;
    height: auto;
}

.group-box {
	border-style: solid;
	border-width: thin;
	border-color: #FFFFFF;
}
.radio-buttons {
    padding: 5px;
}
</style>
