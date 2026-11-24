import { createApp } from 'vue';
import 'vite/modulepreload-polyfill';
import App from './App.vue';
import router from './router';
import helpers from '@/utils/helpers';
//import "bootstrap";
import 'bootstrap/dist/css/bootstrap.min.css';

import moment from 'moment';
extendMoment(moment);
window.moment = moment;
import _ from 'lodash';
window._ = _;
import swal from 'sweetalert2';
window.swal = swal;

import { extendMoment } from 'moment-range';

import jsZip from 'jszip';
window.JSZip = jsZip;

import select2 from 'select2';
select2();
import 'jquery-validation';

import 'sweetalert2/dist/sweetalert2.css';
import 'select2/dist/css/select2.min.css';
import 'select2-bootstrap-5-theme/dist/select2-bootstrap-5-theme.min.css';

import 'datatables.net';
import 'datatables.net-bs5';

import 'datatables.net-responsive';
import 'datatables.net-responsive-bs5';
import 'datatables.net-fixedcolumns-bs5';

import '@/../node_modules/datatables.net-bs5/css/dataTables.bootstrap5.min.css';
import '@/../node_modules/datatables.net-responsive-bs5/css/responsive.bootstrap5.min.css';
import '@/../node_modules/datatables.net-fixedcolumns-bs5/css/fixedColumns.bootstrap5.min.css';

import api_endpoints from './api';
import 'font-awesome/css/font-awesome.min.css';

//NOTE/TODO temporary compatibility layer
import http from '@/utils/vue-resource-shim';

const appElement = document.getElementById('app');

if (appElement) {
    const app = createApp(App);

    app.config.globalProperties.$http = http;

    app.use(router);

    app.mount('#app');
}
