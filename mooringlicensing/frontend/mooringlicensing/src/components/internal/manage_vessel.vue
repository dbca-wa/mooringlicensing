<template>
    <div class="container" >
        <Vessel
        :profile=profile
        id="managevessel" 
        ref="managevessel"
        :readonly=true
        :key="uuid"
        />
    </div>
</template>
<script>
import Vessel from '../common/vessels.vue';
import {
  api_endpoints
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
