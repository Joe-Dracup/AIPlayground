<script setup lang="ts">
import { useWebSocket } from '@vueuse/core';
import {env} from '@/env'
import { ref } from 'vue';

const wsURL = new URL('ws', env.VITE_API_BASE_URL)
const message = ref('')
const {data, send} = useWebSocket(wsURL)
</script>

<template>
  <div class="mx-auto flex max-w-2xl flex-col gap-4 p-6 text-slate-900">
    <div class="flex flex-col gap-2">
      <label for="input" class="text-sm font-medium text-slate-700">Input Value</label>
      <div class="flex gap-2">
        <input
          id="input"
          type="text"
          v-model="message"
          class="flex-1 rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
        />
        <button
          @click="send(message)"
          class="rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white transition hover:bg-indigo-500"
        >
          Send
        </button>
      </div>
    </div>

    <div class="min-h-12 whitespace-pre-wrap break-words rounded-lg bg-slate-100 p-4 text-slate-800">
      {{ data }}
    </div>
  </div>
</template>
