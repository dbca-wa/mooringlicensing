<template>
    <div class="container" id="InvoicesDash">
        <FormSection :formCollapse="false" label="Invoices" Index="invoices">
            <InvoicesTable
                ref="invoice_table"
                level="internal"
            />
        </FormSection>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import InvoicesTable from "@/components/common/table_invoices.vue"
import { v4 as uuidv4 } from 'uuid';

export default {
    name: 'InvoiceDashboard',
    data() {
        let vm = this;
        return {
            uuid: uuidv4()
        }
    },
    components:{
        FormSection,
        InvoicesTable
    },
}
</script>

