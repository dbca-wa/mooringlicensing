<template lang="html">
    <div class="container" >
        <Vessel
        :profile=profile
        id="managevessel" 
        ref="managevessel"
        :readonly=true
        :key="uuid"
        />
        <div>
            <div class="row" style="margin-bottom: 50px">
                    <div  class="container">
                      <div class="row" style="margin-bottom: 50px">
                          <div class="navbar navbar-fixed-bottom"  style="background-color: #f5f5f5;">
                              <div class="navbar-inner">
                                <div class="container">
                                  <p class="pull-right" style="margin-top:5px">
                                    <router-link class="btn btn-primary" :to="{name: 'vessels-dashboard'}">Back to Dashboard</router-link>
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
  methods: {
    populateProfile: async function() {
        const response = await this.$http.get(api_endpoints.profile);
        this.profile = Object.assign({}, response.body);
    },
  },

  mounted: function() {
    let vm = this;
    this.populateProfile();
  },
}
</script>

<style lang="css" scoped>
</style>
