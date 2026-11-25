<template>
   <div id="DataTable" >
      <table class="hover table table-striped table-bordered dt-responsive nowrap" cellspacing="0" width="100%" :id="id">
            <thead>
                <tr>
                    <th
                        v-for="(header,i) in dtHeaders"
                        :key="i"
                        :data-class="i === 0 ? 'expand' : null"
                    >
                        <div class="html-header" v-html="header"></div>
                    </th>
                </tr>
            </thead>
            <tbody>
            </tbody>
        </table>
   </div>

</template>
<script>
import $ from 'jquery'
export default {
   name : 'DataTable',
   props:{
      dtHeaders:{
         type:Array,
         required:true
      },
      dtOptions: {
         type:Object,
         required:true
     },
     id:{
         required:true
     }
   },
   data() {
        return {
            table: null,
            vmDataTable: null,
            resizeHandler: null,
        }
    },
   methods:{
       initEvents: function () {
            let vm =this;

            const options = Object.assign({}, vm.dtOptions);
            vm.vmDataTable = $(vm.table).DataTable(options);

            vm.resizeHandler = function () {
                if (vm.vmDataTable) {
                    vm.vmDataTable.columns.adjust();

                    if (vm.vmDataTable.responsive) {
                        vm.vmDataTable.responsive.recalc();
                    }
                }
            }

            window.addEventListener('resize', vm.resizeHandler);
            $(vm.table).on('drawDatatable', function(){
                vm.vmDataTable.draw();
            });
       }
   },
   mounted:function () {
      let vm = this;
      vm.table =$('#'+vm.id);
      $.fn.dataTable.ext.errMode = 'throw';
      vm.initEvents();
   },
   beforeUnmount() {
        if (this.resizeHandler) {
            window.removeEventListener('resize', this.resizeHandler);
        }

        if (this.vmDataTable) {
            this.vmDataTable.destroy(true);
            this.vmDataTable = null;
        }
    }
}
</script>

<style lang="css">

    table.dataTable.dtr-inline.collapsed > tbody > tr > td.dtr-control:before,
    table.dataTable.dtr-inline.collapsed > tbody > tr > th.dtr-control:before {
        content: "+" !important;

        display: inline-flex !important;
        align-items: center;
        justify-content: center;

        width: 16px;
        height: 16px;

        margin-right: 0.5em;
        box-sizing: border-box;

        border: .15em solid #fff;
        border-radius: 50%;

        background: #337ab7 !important;
        color: #fff;

        font-size: 14px;
        font-weight: bold;

        line-height: 1;

        padding-bottom: 2px;

        box-shadow: 0 0 .2em #444;

        border-top: 1px solid #fff !important;
        border-right: 1px solid #fff !important;
        border-bottom: 1px solid #fff !important;
        border-left: 1px solid #fff !important;
    }

    table.dataTable.dtr-inline.collapsed > tbody > tr.parent > td.dtr-control:before,
    table.dataTable.dtr-inline.collapsed > tbody > tr.parent > th.dtr-control:before,
    table.dataTable.dtr-inline.collapsed > tbody > tr.dtr-expanded > td.dtr-control:before,
    table.dataTable.dtr-inline.collapsed > tbody > tr.dtr-expanded > th.dtr-control:before {
        content: "-" !important;
        background: #d9534f !important;
    }

    div.dataTables_processing div {
      display: none;
    }

    table { table-layout: auto; }

    td {
        word-wrap: break-word;
    }

    td > a{
        border: none;
        border-radius: 2px;
        position: relative;
        padding: 8px 10px;
        margin: 10px 1px;
        font-weight: 500;
        text-transform: capitalize;
        letter-spacing: 0;
        will-change: box-shadow, transform;
        -webkit-transition: -webkit-box-shadow 0.2s cubic-bezier(0.4, 0, 1, 1), background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        -o-transition: box-shadow 0.2s cubic-bezier(0.4, 0, 1, 1), background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        transition: box-shadow 0.2s cubic-bezier(0.4, 0, 1, 1), background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        outline: 0;
        cursor: pointer;
        text-decoration: none;
        background: transparent;
        color: #03a9f4;
    }

    table.table-bordered {
        border-top: 1px solid #dee2e6;
    }

    table.table-bordered.dataTable tbody th,
    table.table-bordered.dataTable tbody td {
        border-bottom-width: 0;
        vertical-align: middle;
        text-align: left;
    }

    .schedule-button {
        width: 80px;
    }

    table.dataTable thead .dt-column-order {
        background: none;
    }

    .table.rowlink td:not(.rowlink-skip),
    .table .rowlink td:not(.rowlink-skip) {
        cursor: pointer;
    }

    table.collapsed > tbody > tr > td > span.responsiveExpander,
    table.has-columns-hidden > tbody > tr > td > span.responsiveExpander {
        background: url("/static/mooringlicensing/img/plus.png") no-repeat 5px center;
        padding-left: 32px;
        cursor: pointer;
    }

    table.collapsed > tbody > tr.parent > td span.responsiveExpander,
    table.has-columns-hidden > tbody > tr.detail-show > td span.responsiveExpander {
        background: url("/static/mooringlicensing/img/minus.png") no-repeat 5px center;
    }

    table.collapsed > tbody > tr > td.child,
    table.has-columns-hidden > tbody > tr > td.child {
        background: #eee;
    }

    table.collapsed > tbody > tr > td > ul,
    table.has-columns-hidden > tbody > tr > td > ul {
        list-style: none;
        margin: 0;
        padding: 0;
    }

    table.collapsed > tbody > tr > td > ul > li > span.dtr-title,
    table.has-columns-hidden > tbody > tr > td > ul > li > span.columnTitle {
        font-weight: bold;
    }

    .table > tbody > tr > td,
    .table > tbody > tr > th,
    .table > tfoot > tr > td,
    .table > tfoot > tr > th,
    .table > thead > tr > td,
    .table > thead > tr > th {
        vertical-align: middle;
    }

    div.dt-search input {
        margin-left: 10px;
        margin-right: 10px;
        display: inline-block;
    }

    div.dt-search {
        margin-bottom: 15px;
    }

    div.dt-length select {
        margin-left: 10px;
        margin-right: 10px;
        display: inline-block;
        margin-bottom: 15px;
    }

    .dt-scroll {
        margin-bottom: 15px;
    }

    .dt-info {
        float: left;
    }

    .dt-paging {
        float: right;
    }

    @media screen and (max-width: 767px)
    {
        div.dt-length,
        div.dt-info {
            float: left;
            width: auto;
        }

        div.dt-search,
        div.dt-paging {
            float: right;
        }
    }

    .html-header {
        text-align: center;
    }
</style>
