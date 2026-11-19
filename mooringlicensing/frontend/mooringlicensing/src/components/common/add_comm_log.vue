<template>
  <div id="AddComms">
    <modal
      transition="modal fade"
      @ok="ok()"
      @cancel="cancel()"
      okText="Add"
      title="Communication Log - Add Entry"
      large
    >
      <div class="container-fluid">
        <div class="row">
          <form
            class="form-horizontal needs-validation"
            name="commsForm"
            @submit.prevent
          >
            <alert v-if="showError" type="danger"
              ><strong>{{ errorString }}</strong></alert
            >
            <div class="col-sm-12">
              <div class="form-group">
                <div class="row mb-3">
                  <div class="col-sm-3">
                    <label class="form-label float-start" for="Name">To</label>
                  </div>
                  <div class="col">
                    <input
                      ref="to"
                      type="text"
                      class="form-control"
                      name="to"
                      v-model="to"
                      required
                    />
                  </div>
                </div>
              </div>
              <div class="form-group">
                <div class="row mb-3">
                  <div class="col-sm-3">
                    <label class="form-label float-start" for="Name"
                      >From</label
                    >
                  </div>
                  <div class="col">
                    <textarea
                      class="form-control"
                      name="from"
                      maxlength="200"
                      v-model="from"
                      required
                    ></textarea>
                  </div>
                </div>
              </div>
              <div class="form-group">
                <div class="row mb-3">
                  <div class="col-sm-3">
                    <label class="form-label float-start" for="Name"
                      >Type</label
                    >
                  </div>
                  <div class="col">
                    <select
                      class="form-select"
                      name="type"
                      v-model="log_type"
                      required
                    >
                      <option value="">Select Type</option>
                      <option value="email">Email</option>
                      <option value="mail">Mail</option>
                      <option value="phone">Phone</option>
                    </select>
                  </div>
                </div>
              </div>
              <div class="form-group">
                <div class="row mb-3">
                  <div class="col-sm-3">
                    <label class="form-label float-start" for="Name"
                      >Subject/Description</label
                    >
                  </div>
                  <div class="col">
                    <textarea
                      class="form-control"
                      name="subject"
                      maxlength="200"
                      v-model="subject"
                      required
                    ></textarea>
                  </div>
                </div>
              </div>
              <div class="form-group">
                <div class="row mb-3">
                  <div class="col-sm-3">
                    <label class="form-label float-start" for="Name"
                      >Text</label
                    >
                  </div>
                  <div class="col">
                    <textarea
                      name="text"
                      class="form-control"
                      v-model="text"
                      required
                    ></textarea>
                  </div>
                </div>
              </div>
              <div class="form-group">
                <div class="row mb-3 border-top pt-3">
                  <div class="col-sm-3">
                    <label class="form-label float-start" for="Name"
                      >Attachments</label
                    >
                  </div>
                  <div class="col-sm-9">
                    <button
                      class="btn btn-primary btn-sm"
                      @click.prevent="attachAnother"
                    >
                      <i class="bi bi-plus-lg"></i> Add Another File
                    </button>
                    <hr class="my-3" />
                    <div v-for="(f, i) in files" :key="f.id">
                      <div class="input-group mb-2">
                        <span
                          class="btn btn-primary btn-file"
                          :title="f.file ? 'Change file' : 'Select file'"
                        >
                          <i class="bi bi-upload"></i>
                          {{ f.file ? "Change" : "Attach" }}
                          <input type="file" @change="uploadFile($event, f)" />
                        </span>
                        <input
                          type="text"
                          class="form-control"
                          :value="f.name"
                          readonly
                          placeholder="No file selected"
                        />
                        <button
                          v-if="i > 0 || f.file"
                          class="btn btn-danger"
                          type="button"
                          @click="removeFile(i)"
                          title="Remove file"
                        >
                          <i class="bi bi-trash"></i>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </form>
        </div>
      </div>
    </modal>
  </div>
</template>

<script>
import $ from "jquery";
import modal from "@vue-utils/bootstrap-modal.vue";
import alert from "@vue-utils/alert.vue";
import { helpers } from "@/utils/hooks";
export default {
  name: "Add-Comms",
  components: {
    modal,
    alert,
  },
  props: {
    url: {
      type: String,
      required: true,
    },
  },
  data: function () {
    return {
      isModalOpen: false,
      form: null,
      comms: {},
      state: "proposed_approval",
      addingComms: false,
      validation_form: null,
      errors: false,
      errorString: "",
      successString: "",
      success: false,
      datepickerOptions: {
        format: "DD/MM/YYYY",
        showClear: true,
        useCurrent: false,
        keepInvalid: true,
        allowInputToggle: true,
      },
      to: "",
      from: "",
      log_type: "",
      subject: "",
      text: "",
      files: [
        {
          id: 1,
          file: null,
          name: "",
        },
      ],
      fileIdCounter: 1,
    };
  },
  watch: {
    isModalOpen: function () {
      this.$nextTick(function () {
        if (this.isModalOpen) {
          this.$refs.to.focus();
        }
      });
    },
  },
  computed: {
    showError: function () {
      var vm = this;
      return vm.errors;
    },
    title: function () {
      return this.processing_status == "With Approver"
        ? "Issue Comms"
        : "Propose to issue approval";
    },
  },
  methods: {
    ok: function () {
      let vm = this;
      if (vm.addingComms) {
        return;
      }
      if ($(vm.form).valid()) {
        vm.errors = false;
        vm.sendData();
      } else {
        vm.errorString = "Missing required fields.";
        vm.errors = true;
      }
    },
    uploadFile(e, file_obj) {
      let _file = null;
      var input = e.target;
      if (input.files && input.files[0]) {
        var reader = new FileReader();
        reader.readAsDataURL(input.files[0]);
        reader.onload = function (e) {
          _file = e.target.result;
        };
        _file = input.files[0];
      }
      file_obj.file = _file;
      file_obj.name = _file ? _file.name : "";
    },
    removeFile(index) {
      if (index === 0) {
        this.fileIdCounter += 1;
        this.files[0] = {
          id: this.fileIdCounter,
          file: null,
          name: "",
        };
        return;
      }
      this.files.splice(index, 1);
      if (this.files.length === 0) {
        this.attachAnother();
      }
    },
    attachAnother() {
      this.fileIdCounter += 1;
      this.files.push({
        id: this.fileIdCounter,
        file: null,
        name: "",
      });
    },
    cancel: function () {
      this.close();
    },
    close: function () {
      this.isModalOpen = false;
      this.comms = {};
      this.errors = false;
      $(".has-error").removeClass("has-error");
      this.validation_form.resetForm();

      this.to = "";
      this.from = "";
      this.log_type = "";
      this.subject = "";
      this.text = "";

      this.files = [];
      this.attachAnother();
    },
    sendData: function () {
        let vm = this;
        vm.errors = false;

        let comms = new FormData();
        comms.append("to", this.to);
        comms.append("fromm", this.from);
        comms.append("type", this.log_type);
        comms.append("subject", this.subject);
        comms.append("text", this.text);

        for (let i = 0; i < vm.files.length; i++) {
            if (vm.files[i].file) {
                comms.append("files", vm.files[i].file);
            }
        }

        vm.addingComms = true;

        vm.$http.post(vm.url, comms)
            .then((response) => {
                vm.addingComms = false;
                vm.close();
                vm.$emit("added");
            }, (error) => {
                vm.errors = true;
                vm.addingComms = false;
                vm.errorString = helpers.apiVueResourceError(error);
            });
    },
    addFormValidations: function () {
      let vm = this;
      vm.validation_form = $(vm.form).validate({
        rules: {
          to: "required",
          from: "required",
          type: "required",
          subject: "required",
          text: "required",
        },
      });
    },
  },
  mounted: function () {
    let vm = this;
    vm.form = document.forms.commsForm;
    vm.addFormValidations();
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

input[type="text"],
select {
  width: 100%;
  padding: 0.375rem 2.25rem 0.375rem 0.75rem;
}

.truncate-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

label.error {
  color: red;
  margin-top: 8px;
  font-weight: normal;
}
</style>