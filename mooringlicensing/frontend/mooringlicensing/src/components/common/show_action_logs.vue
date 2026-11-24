<template>
  <div id="ShowComms">
    <modal
      v-model:show="isModalOpen"  
      transition="modal fade"
      :showOK="false"
      :showCancel="false"
      title="Action logs"
      :xxlarge="true"
    >
      <div class="container-fluid">
        <datatable
          id="actionLogId"
          :dtOptions="actionsDtOptions"
          :dtHeaders="actionsDtHeaders"
        ></datatable>
      </div>
    </modal>
  </div>
</template>

<script>
import modal from "@vue-utils/bootstrap-modal.vue";
import datatable from "@vue-utils/datatable.vue";
import { constants } from "@/utils/hooks";
import { v4 as uuid } from "uuid";

export default {
  name: "Show-Actions",
  components: {
    modal,
    datatable,
  },
  props: {
    url: {
      type: String,
      required: true,
    },
  },
  data: function () {
    return {
      dom: 'lBfrtip',
      actionLogId: "action-log-table" + uuid(),
      isModalOpen: false,
      actionsDtHeaders: ["Who", "What", "When"],
      actionsDtOptions: {
        language: {
          processing: constants.DATATABLE_PROCESSING_HTML,
        },
        // Disable responsive mode and enable scrollX with fixed columns
        responsive: false,
        scrollX: true,
        fixedColumns: {
          leftColumns: 1,
        },
        deferRender: true,
        autowidth: true,
        order: [[3, "desc"]], // order the non-formatted date as a hidden column
        dom:
          "<'row'<'col-sm-4'l><'col-sm-8'f>>" +
          "<'row'<'col-sm-12'tr>>" +
          "<'row'<'col-sm-5'i><'col-sm-7'p>>",
        processing: true,
        ajax: {
          url: this.url,
          dataSrc: "",
        },
        columns: [
          {
            title: "Who",
            data: "who",
            orderable: false,
          },
          {
            title: "What",
            data: "what",
            orderable: false,
            render: function (data, type) {
              // Combine it with the div wrapper to guarantee the browser forces the wrap
              if (type === "display" && data) {
                return '<div class="forced-wrap-col">' + data + "</div>";
              }
              return data;
            },
          },
          {
            title: "When",
            data: "when",
            className: "all",
            orderable: true,
            mRender: function (data) {
              return moment(data).format("DD/MM/YYYY HH:mm:ss");
            },
          },
          {
            title: "Created",
            data: "when",
            visible: false,
          },
        ],
      },
      commsTable: null,
    };
  },
  methods: {
    close: function () {
      this.isModalOpen = false;
    },
  },
};
</script>

<style lang="css">
.btn-file {
  position: relative;
  overflow: hidden;
}
.btn-file input[type="file"] {
  position: absolute;
  top: 0;
  right: 0;
  min-width: 100%;
  min-height: 100%;
  font-size: 100px;
  text-align: right;
  filter: alpha(opacity=0);
  opacity: 0;
  outline: none;
  background: white;
  cursor: inherit;
  display: block;
}
.top-buffer {
  margin-top: 5px;
}
.top-buffer-2x {
  margin-top: 10px;
}

.forced-wrap-col {
  width: auto;
  max-width: none;
  white-space: normal;
  word-break: break-all;
  overflow-wrap: break-word;
}
</style>