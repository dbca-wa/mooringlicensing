<template lang="html">
    <div class="container" >
        <div class="row">
            <div class="col-sm-12">
                <div class="row">
                    <div v-if="isProposal" class="col-sm-offset-3 col-sm-6 borderDecoration">
                      <div v-if="proposal.application_type==application_type_filming">
                        <strong>Your commercial filming application has been successfully submitted.</strong>
                        <br/>
                        
                      </div>
                      <div v-else>
                        <strong>Your application for a ............... has been successfully submitted.</strong>
                        <br/>
                      </div>
                        <!-- <strong>Your application for a commercial operations licence has been successfully submitted.</strong>
                        <br/> -->
                        <table>
                            <tr>
                                <td><strong>Application:</strong></td>
                                <td><strong>{{proposal.lodgement_number}}</strong></td>
                            </tr>
                            <tr>
                                <td><strong>Date/Time:</strong></td>
                                <td><strong> {{proposal.lodgement_date|formatDate}}</strong></td>
                            </tr>
                        </table>
                        <br/>
                        <label>You will receive a notification email if there is any incomplete information or documents missing from the application.</label>
                        <router-link :to="{name:'external-proposals-dash'}" style="margin-top:15px;" class="btn btn-primary">Back to home</router-link>
                    </div>
                    <div v-else class="col-sm-offset-3 col-sm-6 borderDecoration">
                        <strong>Sorry it looks like there isn't any application currently in your session.</strong>
                        <br /><router-link :to="{name:'external-proposals-dash'}" style="margin-top:15px;" class="btn btn-primary">Back to home</router-link>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
import Vue from 'vue'
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
        "proposal": {},
    }
  },
  components: {
  },
  computed: {
    isProposal: function(){
      return this.proposal && this.proposal.id ? true : false;
    },
    application_type_tclass: function(){
      return api_endpoints.t_class;
    },
    application_type_filming: function(){
      return api_endpoints.filming;
    },
    application_type_event: function(){
      return api_endpoints.event;
    }
  },
  methods: {
  },
  filters:{
        formatDate: function(data){
            return data ? moment(data).format('DD/MM/YYYY HH:mm:ss'): '';
        }
  },
  mounted: function() {
    let vm = this;
    vm.form = document.forms.new_proposal;
  },
  beforeRouteEnter: function(to, from, next) {
    next(vm => {
        vm.proposal = to.params.proposal;
    })
  }
}
</script>

<style lang="css" scoped>
.borderDecoration {
    border: 1px solid;
    border-radius: 5px;
    padding: 50px;
    margin-top: 70px;
}
</style>
