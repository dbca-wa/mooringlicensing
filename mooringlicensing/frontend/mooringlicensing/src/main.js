import Vue from 'vue'
import resource from 'vue-resource'
import 'vite/modulepreload-polyfill';
import App from './App.vue'
import router from './router'
import bs from 'bootstrap'
import helpers from '@/utils/helpers'

import moment from 'moment'
extendMoment(moment);
window.moment = moment
import _ from 'lodash'
window._ = _
import swal from 'sweetalert2'
window.swal = swal

import { extendMoment } from 'moment-range';

import 'datatables.net-buttons-bs';
import 'datatables.net-responsive-bs';
import 'datatables.net-fixedcolumns-bs';

import jsZip from 'jszip';
window.JSZip = jsZip;

import 'select2';
import 'jquery-validation';

import 'sweetalert2/dist/sweetalert2.css';
import 'select2/dist/css/select2.min.css';
import 'select2-bootstrap-theme/dist/select2-bootstrap.min.css';


import api_endpoints from './api'
import 'eonasdan-bootstrap-datetimepicker/build/css/bootstrap-datetimepicker.min.css'
import 'font-awesome/css/font-awesome.min.css'

import '@/../node_modules/datatables.net-bs/css/dataTables.bootstrap.min.css';
import '@/../node_modules/datatables.net-responsive-bs/css/responsive.bootstrap.min.css';
import '@/../node_modules/datatables.net-buttons-bs/css/buttons.bootstrap.min.css';
import 'datatables.net-fixedcolumns-bs/css/fixedColumns.bootstrap.min.css';

Vue.config.devtools = true;
Vue.config.productionTip = false
Vue.use( resource );

// Add CSRF Token to every request
Vue.http.interceptors.push( function ( request, next ) {
  // modify headers
  if ( request.url != api_endpoints.countries ) {
    request.headers.set( 'X-CSRFToken', helpers.getCookie( 'csrftoken' ) );
  }

  // continue to next interceptor
  next();
} );

const appElement = document.getElementById( 'app' );

if ( appElement ) {
  /* eslint-disable no-new */
  new Vue( {
    el: '#app',
    router,
    template: '<App/>',
    components: {
      App
    }
  } )
}
