<template id="bootstrap-modal">
  <div v-show="show" :transition="transition">
    <div class="modal" data-bs-keyboard="false" data-bs-backdrop="static">
      <div class="modal-dialog" :class="modalClass" role="document">
        <div class="modal-content">
          <!--Header-->
          <slot name="header">
            <div class="modal-header">
              <!-- <a type="button" class="close" @click="cancel">x</a> -->
              <h4 class="modal-title">
                <slot name="title">
                  {{ title }}
                </slot>
              </h4>
              <button
                type="button"
                class="btn-close btn-close-white"
                aria-label="Close"
                @click="cancel"
              ></button>
            </div>
          </slot>
          <!--Container-->
          <div class="modal-body">
            <slot></slot>
          </div>
          <!--Footer-->
          <div class="modal-footer">
            <slot name="footer">
            <button
                v-if="showOK && processing"
                id="okBtn"
                type="button"
                :class="okClass"
                @click="ok"
                disabled
              >
                <i class="fa fa-spinner fa-spin"></i>
                Processing
              </button>
              <button
                v-else-if="showOK"
                id="okBtn"
                type="button"
                :class="okClass"
                @click="ok"
                :disabled="okButtonDisabled"
              >
                {{ okText }}
              </button>
              <button
                v-if="showCancel"
                type="button"
                :class="cancelClass"
                @click="cancel"
              >
                {{ cancelText }}
              </button>
            </slot>
          </div>
        </div>
      </div>
    </div>
    <div class="modal-backdrop show"></div>
  </div>
</template>

<script>
/**
 * Bootstrap Style Modal Component for Vue
 * Depend on Bootstrap.css
 */

export default {
  props: {
    title: {
      type: String,
      default: "Modal",
    },
    small: {
      type: Boolean,
      default: false,
    },
    large: {
      type: Boolean,
      default: false,
    },
    xlarge: {
      type: Boolean,
      default: false,
    },
    xxlarge: {
      type: Boolean,
      default: false,
    },
    full: {
      type: Boolean,
      default: false,
    },
    force: {
      type: Boolean,
      default: false,
    },
    transition: {
      type: String,
      default: "modal",
    },
    okText: {
      type: String,
      default: "OK",
    },
    cancelText: {
      type: String,
      default: "Cancel",
    },
    okClass: {
      type: String,
      default: "btn btn-primary",
    },
    cancelClass: {
      type: String,
      default: "btn btn-secondary",
    },
    closeWhenOK: {
      type: Boolean,
      default: false,
    },
    showOK: {
      type: Boolean,
      default: true,
    },
    showCancel: {
      type: Boolean,
      default: true,
    },
    okButtonDisabled: {
        type: Boolean,
        default: false,
    },
    processing: {
        type: Boolean,
        default: false,
    },
    show: {
        type: Boolean,
        default: false,
    },
  },
  emits: ['ok', 'cancel', 'update:show'],
  data() {
    return {
      duration: null,
    };
  },
  computed: {
    modalClass() {
      return {
        "modal-xxl": this.xxlarge,
        "modal-xl": this.xlarge,
        "modal-lg": this.large,
        "modal-sm": this.small,
        "modal-full": this.full,
      };
    },
  },
  created() {
    if (this.show) {
      document.body.className += " modal-open";
    }
  },
  beforeUnmount() {
    document.body.className = document.body.className.replace(
      /\s?modal-open/,
      "",
    );
  },
  watch: {
    show(value) {
      if (value) {
        document.body.className += " modal-open";
      } else {
        window.setTimeout(() => {
          document.body.className = document.body.className.replace(
            /\s?modal-open/,
            "",
          );
        }, this.duration || 0);
      }
    },
  },
  methods: {
    ok() {
        this.$emit("ok");
        if (this.closeWhenOK) {
            this.$emit("update:show", false);
        }
    },
    cancel() {
        this.$emit("cancel");
        this.$emit("update:show", false);
    },
    clickMask() {
      if (!this.force) {
        this.cancel();
      }
    },
  },
};
</script>

<style scoped>
.modal {
  display: block;
  z-index: 1055 !important;
}

.modal-backdrop {
  z-index: 1050 !important;
}

.modal .btn {
  margin-bottom: 0px;
}

.modal-header {
  border-top-left-radius: 0.3rem;
  border-top-right-radius: 0.3rem;
  background-color: #226fbb;
  color: #fff;
  background: #3580ca url("/static/disturbance_vue/src/parks-bg-banner.gif")
    repeat-x center bottom;
}

.btn-close {
  color: #eee;
}

.modal-footer {
  border-bottom-left-radius: 0.3rem;
  border-bottom-right-radius: 0.3rem;
}

.modal-body {
  background-color: #fff;
  color: #333333;
}

.modal-footer {
  /*background-color: #F5F5F5;
            color: #333333;*/
  background-color: #efefef;
  color: #333333;
}

.modal-transition {
  transition: all 0.6s ease;
}

.modal-leave {
  border-radius: 1px !important;
}

.modal-transition .modal-dialog,
.modal-transition .modal-backdrop {
  transition: all 0.5s ease;
}

.modal-enter .modal-dialog,
.modal-leave .modal-dialog {
  opacity: 0;
  transform: translateY(-30%);
}

.modal-enter .modal-backdrop,
.modal-leave .modal-backdrop {
  opacity: 0;
}

.close {
  font-size: 2.5rem;
  opacity: 0.3;
}

.close:hover {
  opacity: 0.7;
}

#okBtn {
  margin-bottom: 0px;
}

/* Custom XXL Modal with responsive step-downs */

/* 1. Ultra-wide screens (Desktop monitors) */
@media (min-width: 1400px) {
  .modal-dialog.modal-xxl {
    max-width: 1320px !important;
  }
}

/* 2. Extra-large screens (Laptops / Small desktops) */
@media (min-width: 1200px) and (max-width: 1399.98px) {
  .modal-dialog.modal-xxl {
    max-width: 1140px !important;
  }
}

/* 3. Large screens (Tablets in landscape / Small laptops) */
@media (min-width: 992px) and (max-width: 1199.98px) {
  .modal-dialog.modal-xxl {
    max-width: 800px !important;
  }
}

/* 4. Medium screens (Tablets in portrait) */
@media (min-width: 768px) and (max-width: 991.98px) {
  .modal-dialog.modal-xxl {
    max-width: 500px !important;
  }
}
</style>