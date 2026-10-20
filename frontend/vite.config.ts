import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

import { parseEnv } from './src/env.schema.ts'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Fail fast in the terminal on bad env. Skipped for tests, which mock the env.
  if (mode !== 'test') parseEnv(loadEnv(mode, process.cwd()))

  return {
    plugins: [
      vue(),
      vueDevTools(),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
  }
})
