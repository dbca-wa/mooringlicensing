<template lang="html">
    <div class="container" >
        <Vessel
        :profile=profile
        id="managevessel" 
        ref="managevessel"
        :readonly=false
        :creatingVessel="creatingVessel"
        :editingVessel="editingVessel"
        :key="uuid"
        />
        <div>
            <input type="hidden" name="csrfmiddlewaretoken" :value="csrf_token"/>

            <div class="row" style="margin-bottom: 50px">
                    <div  class="container">
                      <div class="row" style="margin-bottom: 50px">
                          <div class="navbar navbar-fixed-bottom"  style="background-color: #f5f5f5;">
                              <div class="navbar-inner">
                                <div class="container">
                                  <p class="pull-right" style="margin-top:5px">
                                    <button v-if="savingVessel" type="button" class="btn btn-primary" disabled>Save and Exit&nbsp;
                                            <i class="fa fa-circle-o-notch fa-spin fa-fw"></i></button>
                                    <input v-else type="button" @click.prevent="save_exit" class="btn btn-primary" value="Save and Exit" :disabled="savingVessel"/>
                                    <!--span v-if="!creatingVessel"-->
                                        <button v-if="savingVessel" type="button" class="btn btn-primary" disabled>Save and Continue&nbsp;
                                                <i class="fa fa-circle-o-notch fa-spin fa-fw"></i></button>
                                        <input v-else type="button" @click.prevent="save" class="btn btn-primary" value="Save and Continue" :disabled="savingVessel"/>
                                    <!--/span-->

                                    <!--router-link class="btn btn-primary" :to="{name: 'vessels-dashboard'}">Back to Dashboard</router-link-->
                                  </p>
                                </div>
                              </div>
                            </div>
                        </div>
                    </div>
            </div>
        </div>

    </div>
</template>
<script>
import WaitingListApplication from '../form_wla.vue';
import AnnualAdmissionApplication from '../form_aaa.vue';
import AuthorisedUserApplication from '../form_aua.vue';
import MooringLicenceApplication from '../form_mla.vue';
import Vessel from '../common/vessels.vue';
import Vue from 'vue' 
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'
export default {
  name: 'ManageVessel',
  data: function() {
    return {
        profile: {},
        savingVessel: false,
        uuid: 0,
    }
  },
  components: {
      Vessel,
  },
  computed: {
      csrf_token: function() {
        return helpers.getCookie('csrftoken')
      },
      creatingVessel: function() {
          let retVal = false;
          if (this.$route.name === 'new-vessel' && !this.$route.params.vessel_id) {
              retVal = true;
          }
          return retVal;
      },
      editingVessel: function() {
          let retVal = false;
          if (this.$route.name === 'manage-vessel' && this.$route.params.vessel_id) {
              retVal = true;
          }
          return retVal;
      },

      /*
      saveUrl: function() {
          if (this.creating
      },
      updateUrl: function() {
        return (this.proposal) ? `/api/proposal/${this.proposal.id}/draft.json` : '';
          // revert to above
        //return (this.proposal) ? `/api/proposal/${this.proposal.id}/submit.json` : '';
      },
      */

  },
  methods: {
    populateProfile: async function() {
        const response = await this.$http.get(api_endpoints.profile);
        this.profile = Object.assign({}, response.body);
    },
    save: async function(withConfirm=true, url=this.saveUrl) {
        let vm = this;
        vm.savingVessel=true;
        /*
        let payload = {
            vessel: {},
        }
        */
        let payload = {}
        payload.vessel = Object.assign({}, this.$refs.managevessel.vessel);
        try {
            let res = null;
            if (this.creatingVessel) {
                payload.create_vessel = true;
                res = await vm.$http.post(api_endpoints.vessel, payload);
            } else {
                const url = `${api_endpoints.vessel}${payload.vessel.id}/`;
                res = await vm.$http.put(url, payload);
            }
            if (withConfirm) {
                await swal(
                    'Saved',
                    'Your application has been saved',
                    'success'
                );
            };
            // change route if Save and Continue on Add Vessel page
            //console.log(res.body);
            if (this.creatingVessel) {
                this.uuid++;
                vm.$router.push({
                    name: 'manage-vessel',
                    params: { vessel_id: res.body.id }
                });
            }
            vm.savingVessel=false;
            return res;
        } catch(err) {
            await swal({
                title: "Please fix following errors before saving",
                //text: err.bodyText,
                html: helpers.formatError(err),
                type:'error'
            });
            vm.savingVessel=false;
        }
    },
    save_exit: async function() {
        let vm = this;
        const res = await this.save();
        if (res.ok) {
            vm.$router.push({
                name: 'vessels-dashboard'
            });
        }
    },
    /*
    save_wo_confirm: function() {
      this.save(false);
    },
    */

    leaving: function(e) {
      let vm = this;
      var dialogText = 'You have some unsaved changes.';
      if (!vm.proposal_readonly && !vm.submitting){
        e.returnValue = dialogText;
        return dialogText;
      }
      else{
        return null;
      }
    },

  },

  mounted: function() {
    let vm = this;
    this.populateProfile();
    //vm.form = document.forms.new_proposal;
      /* uncomment later - too annoying while making front end changes 
    window.addEventListener('beforeunload', vm.leaving);
    window.addEventListener('onblur', vm.leaving);
    */
  },
}
</script>

<style lang="css" scoped>
</style>
