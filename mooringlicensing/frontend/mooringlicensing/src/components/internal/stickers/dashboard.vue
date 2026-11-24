<template>
    <div class="container" id="StickersDash">
        <FormSection :formCollapse="false" label="Stickers" Index="stickers">
            <StickersTable
                ref="stickers_table"
                level="internal"
                @actionClicked="actionClicked"
            />
        </FormSection>
        <FormSection :formCollapse="false" label="Non-exported Stickers" Index="non_exported_stickers">
            <NonExportedStickersTable
                ref="non_exported_stickers_table"
                level="internal"
                @actionClicked="actionClicked"
            />
        </FormSection>
        <ModalDetails
            ref="modal_details"
            @sendData="sendData"
        />
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import StickersTable from "@/components/common/table_stickers.vue"
import NonExportedStickersTable from "@/components/common/non_exported_table_stickers.vue"
import ModalDetails from "@/components/common/sticker_replacement_modal.vue"
import { api_endpoints, helpers } from '@/utils/hooks'
import { v4 as uuidv4 } from 'uuid';

export default {
    name: 'InternalStickersDashboard',
    data() {
        let vm = this;
        return {
            uuid: uuidv4()
        }
    },
    components:{
        FormSection,
        StickersTable,
        NonExportedStickersTable,
        ModalDetails,
    },
    computed: {
        csrf_token: function() {
          return helpers.getCookie('csrftoken')
        },
    },
    methods: {
        actionClicked: function(param){
            console.log('actionClicked() in dashboard')
            this.$refs.modal_details.action = param.action
            this.$refs.modal_details.sticker.id = param.id
            this.$refs.modal_details.close()
            this.$refs.modal_details.isModalOpen = true
        },
        sendData: function(params){
            let vm = this
            let action = params.action
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.stickers, params.sticker.id + '/' + action), params).then(
                res => {
                    if (action == 'request_replacement'){
                        // Sticker replacement requires payments
                        helpers.post_and_redirect('/sticker_replacement_fee/', {'csrfmiddlewaretoken' : vm.csrf_token, 'data': JSON.stringify(res.body)});
                    } else if (action == 'cancel'){
                        vm.updateNonExportedTableRow(res.body.sticker)
                        vm.$refs.modal_details.close()
                    } else {
                        vm.updateTableRow(res.body.sticker)
                        vm.$refs.modal_details.close()
                    }
                },
                err => {
                    console.log(err)
                    vm.$refs.modal_details.close()
                }
            )
        },
        updateTableRow: function(sticker){
            this.$refs.stickers_table.updateRow(sticker)
        },
        updateNonExportedTableRow: function(sticker){
            this.$refs.non_exported_stickers_table.updateRow(sticker)
        }
    },
}
</script>

