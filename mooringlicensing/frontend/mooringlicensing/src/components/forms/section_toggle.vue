<template lang="html">
    <div class="panel panel-default" >
        <div v-if="!hideHeader" class="panel-heading">
            <h3 class="panel-title">{{label}} <span class="subtitle">{{ subtitle }}</span>
                <a :href="'#'+section_id" class="panelClicker" :id="custom_id" data-toggle="collapse" expanded="true" :aria-controls="section_id">
                    <span v-if="!noChevron" :class="panel_chevron_class"></span>
                </a>
            </h3>
        </div>
        <div :class="panel_collapse_class" :id="section_id">
            <slot></slot>
        </div>
    </div>
</template>

<script>
import uuid from 'uuid';

export default {
    name:"FormSection",
    props: {
        label: {}, 
        subtitle: {
            type: String,
            default: '',
        },
        Index: {}, 
        formCollapse: {}, 
        hideHeader: {},
        treeHeight: {},
        noChevron: {
            default: false,
        },
    },
    data:function () {
        return {
            title:"Section title",
            panel_chevron_class: null,
            custom_id: uuid(),
        }
    },
    computed:{
        section_id: function () {
            return "section_"+this.Index
        },
        panel_collapse_class: function() {
            if (this.formCollapse) {
                this.panel_chevron_class = "glyphicon glyphicon-chevron-down pull-right";
                return "panel-body collapse";
            } else {
                if (this.treeHeight) {
                    this.panel_chevron_class = "glyphicon glyphicon-chevron-up pull-right";
                    return "panel-body collapse in flex-container";
                } else {
                    this.panel_chevron_class = "glyphicon glyphicon-chevron-up pull-right";
                    return "panel-body collapse in";
                }
            }
        },
    },
    mounted: function() {
        let vm = this;
        $('#' + vm.custom_id).on('click',function () {
            var chev = $(this).children()[0];
            window.setTimeout(function () {
                $(chev).toggleClass("glyphicon-chevron-up glyphicon-chevron-down");
            }, 100);
        });
    },
    updated:function () {
    },
}
</script>

<style lang="css">
    h3.panel-title{
        font-weight: bold;
        font-size: 25px;
        padding:20px;
    }
    .flex-container {
        display: flex;
        flex-direction: column;
        min-height: 325px;
    }
    .subtitle {
        font-size: 0.6em;
    }
</style>
