import { defineConfig } from 'vite'
import { createVuePlugin } from 'vite-plugin-vue2'
import { viteStaticCopy } from 'vite-plugin-static-copy'
import path from 'path'

const port = process.env.PORT ? parseInt(process.env.PORT) : 5173
const host = process.env.HOST || '0.0.0.0'

export default defineConfig({
    plugins: [
        createVuePlugin(),
        viteStaticCopy({
            targets: [
                {
                    src: 'node_modules/font-awesome/fonts/*',
                    dest: 'node_modules/font-awesome/fonts',
                },
            ],
        })
    ],

    resolve: {
        alias: {
            '@': path.resolve(__dirname, 'src'),
            '@vue-utils': path.resolve(__dirname, 'src/utils/vue'),
            '@common-utils': path.resolve(
                __dirname,
                'src/components/common'
            ),
            '@static-root': path.resolve(
                __dirname,
                '../../../staticfiles_ml'
            ),
            datetimepicker: path.resolve(
                __dirname,
                'eonasdan-bootstrap-datetimepicker/build/js/bootstrap-datetimepicker.min.js'
            ),
            moment: path.resolve(
                __dirname,
                'node_modules/moment/moment.js'
            ),
        },
    },

    server: {
        host: host,
        port: port,
        strictPort: true,
        open: false,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers':
                'Origin, X-Requested-With, Content-Type, Accept',
        },
        hmr: {
            protocol: 'ws',
            host: 'localhost',
            port: port,
        },
    },

    build: {
        manifest: 'manifest.json',
        commonjsOptions: { transformMixedEsModules: true },
        outDir: path.resolve(
            __dirname,
            `../../static/mooringlicensing_vue`
        ),
        sourcemap: false,
        rollupOptions: {
            input: {
                main: path.resolve(__dirname, 'src/main.js'),
            },
        },
        emptyOutDir: true,
    },

    base: '/static/mooringlicensing_vue/',
})