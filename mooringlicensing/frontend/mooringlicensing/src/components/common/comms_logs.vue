<template id="comms_logs">
  <div class="">
    <div class="card mb-3">
      <div class="card-header">Logs</div>
      <div class="card-body border-bottom">
        <label for="assigned-to" class="form-label">Communication Logs</label>
        <div class="rounded border py-2">
          <span class="ps-3 pe-2"><i class="bi bi-card-list"></i> </span>
          <a
            ref="showCommsBtn"
            href="#"
            class="pe-5"
            @click.prevent="showComms()"
            >Show</a
          >
          <template v-if="!disable_add_entry">
            <span class="pe-2">
              <i class="bi bi-plus-circle"></i>
            </span>
            <a ref="addCommsBtn" href="#" @click.prevent="addComm()"
              >Add Entry</a
            >
          </template>
        </div>
      </div>
      <div class="card-body">
        <label for="assigned-to" class="form-label">Action Logs</label>
        <div class="rounded border py-2">
          <span class="ps-3 pe-2"><i class="bi bi-card-list"></i> </span>
          <a ref="showActionBtn" href="#" @click.prevent="showActions()"
            >Show</a
          >
        </div>
      </div>
    </div>
    <AddCommLog ref="add_comm" :url="comms_add_url" @added="onCommAdded" />
    <ShowCommsLogs ref="show_comms" :url="comms_url" />
    <ShowActionLogs ref="show_actions" :url="logs_url" />
  </div>
</template>

<script>
import AddCommLog from "./add_comm_log.vue";
import ShowCommsLogs from "./show_comms_logs.vue";
import ShowActionLogs from "./show_action_logs.vue";
import { v4 as uuid } from "uuid";

export default {
  name: "CommsLogSection",
  components: {
    AddCommLog,
    ShowCommsLogs,
    ShowActionLogs,
  },
  props: {
    comms_url: {
      type: String,
      required: true,
    },
    logs_url: {
      type: String,
      required: true,
    },
    comms_add_url: {
      type: String,
      required: true,
    },
    disable_add_entry: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      uuid: uuid(),
      dateFormat: "DD/MM/YYYY HH:mm:ss",
      actionsTable: null,
      popoversInitialised: false,
    };
  },
  methods: {
    addComm() {
      this.$refs.add_comm.isModalOpen = true;
    },
    showComms() {
      this.$refs.show_comms.isModalOpen = true;
    },
    showActions() {
      this.$refs.show_actions.isModalOpen = true;
    },
    onCommAdded() {
      // refresh the comms datatable if present
      try {
        if (
          this.$refs.show_comms &&
          typeof this.$refs.show_comms.reload === "function"
        ) {
          this.$refs.show_comms.reload();
        }
      } catch (e) {
        console.error("Error refreshing comms after add", e);
      }
    },
  },
};
</script>