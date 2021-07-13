import Vue from 'vue'
import Router from 'vue-router'
import Profile from '@/components/user/profile.vue'
import external_routes from '@/components/external/routes'
import internal_routes from '@/components/internal/routes'
import MooringLicenceDocumentsUpload from '@/components/external/mooring_licence_documents_upload'

Vue.use(Router)

export default new Router({
    mode: 'history',
    routes: [
        {
          path: '/firsttime',
          name: 'first-time',
          component: Profile
        },
        {
          path: '/account',
          name: 'account',
          component: Profile
        },
        external_routes,
        internal_routes,
        {
            path: '/mla_documents_upload/:uuid',
            name: 'mla-documents-upload',
            component: MooringLicenceDocumentsUpload
        }
    ]
})
