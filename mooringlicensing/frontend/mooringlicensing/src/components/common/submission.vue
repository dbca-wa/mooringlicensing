<template>
    <div class="">
        <div class="card mb-3">
            <div class="card-header">
               Submission
            </div>
            <div class="card-body border-bottom">
                <div class="col-sm-12">
                    <strong>Submitted by</strong><br/>
                    {{ submitter_first_name }}
                    {{ submitter_last_name }}
                </div>
                <div class="col-sm-12 top-buffer-s">
                    <strong>Lodged on</strong><br/>
                    {{ formatDate(lodgement_date) }}
                </div>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    name: 'Submission',
    props: {
        submitter_first_name: {
            type: String,
            default: '',
        },
        submitter_last_name: {
            type: String,
            default: '',
        },
        lodgement_date: {
            type: String,
            default: null,
        },
    },
    filters: {
        formatDate: function(data){
            return data ? moment(data).format('DD/MM/YYYY HH:mm:ss'): '';
        }
    },
}
</script>
