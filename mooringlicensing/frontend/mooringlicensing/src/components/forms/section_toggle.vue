<template>
  <div :id="custom_id" class="card section-wrapper">
    <div class="card-header h4 fw-bold p-4">
      <div
        :id="'show_hide_switch_' + section_body_id"
        class="row show_hide_switch"
        :class="{ collapsed: isCollapsed }"
        :aria-expanded="(!isCollapsed).toString()"
        :aria-controls="section_body_id"
        @click="toggle_show_hide"
      >
        <div class="col-11" :style="'color:' + customColor">
          {{ label }}
          <span v-if="subtitle" class="h6" :class="subtitleClass">{{
            subtitle
          }}</span>
          <!-- to display the assessor and referral comments textboxes -->
          <template v-if="displayCommentSection">
            <template v-if="!isShowComment">
              <a
                v-if="has_comment_value"
                href=""
                @click.stop.prevent="toggleComment"
                ><i style="color: red" class="far fa-comment">&nbsp;</i></a
              >
              <a v-else href="" @click.stop.prevent="toggleComment"
                ><i class="far fa-comment">&nbsp;</i></a
              >
            </template>
            <a
              v-else-if="isShowComment"
              href=""
              @click.stop.prevent="toggleComment"
              ><i class="fa fa-ban">&nbsp;</i></a
            >
          </template>
        </div>
        <div class="col-1 text-end">
          <i
            :id="chevron_elem_id"
            class="bi fw-bold chevron-toggle"
            :class="isCollapsed ? 'bi-chevron-down' : 'bi-chevron-up'"
          >
          </i>
        </div>
      </div>
    </div>
    <div
      :id="section_body_id"
      :class="detailsClass"
      :style="'color:' + customColor"
    >
      <slot></slot>
    </div>
  </div>
</template>

<script>
import { v4 as uuid } from "uuid";

export default {
  name: "FormSection",
  props: {
    label: {
      type: String,
      default: "",
    },
    subtitle: {
      type: String,
      default: "",
    },
    subtitleClass: {
      type: String,
      default: "text-muted",
    },
    Index: {
      type: String,
      default: "",
    },
    hideHeader: {
      type: Boolean,
      default: false,
    },
    customColor: {
      type: String,
      default: "",
    },
    formCollapse: {
      type: Boolean,
      default: false,
    },
    isShowComment: {
      type: Boolean,
      required: false,
    },
    has_comment_value: {
      type: Boolean,
      required: false,
    },
    displayCommentSection: {
      type: Boolean,
      default: false,
    },
  },
  data: function () {
    return {
      custom_id: uuid(),
      chevron_elem_id: "chevron_elem_" + uuid(),
      isCollapsed: this.formCollapse,
    };
  },
  computed: {
    detailsClass: function () {
      return {
        "card-body": true,
        collapse: true,
        show: !this.isCollapsed,
      };
    },
    section_header_id: function () {
      return "section_header_" + this.Index;
    },
    section_body_id: function () {
      return "section_body_" + this.Index;
    },
  },
  methods: {
    toggle_show_hide: function () {
      this.isCollapsed = !this.isCollapsed;
      this.$emit("toggle-collapse");
    },
    toggleComment: function () {
      this.$emit("toggleComment", !this.isShowComment);
    },
  },
};
</script>

<style scoped>
.section-wrapper {
  margin-bottom: 20px;
  padding: 0;
}

.show_hide_switch {
  cursor: pointer;
}

.rotate_icon {
  transition: 0.5s;
}

.chev_rotated {
  transform: rotate(90deg);
}
</style>