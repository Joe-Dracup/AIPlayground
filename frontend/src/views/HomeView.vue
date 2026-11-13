<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { z } from 'zod'

import { apiFetch } from '@/api/client'

const RootResponse = z.object({ message: z.string() })

let message: string | null = null
let error: string | null = null

try {
  const data = await apiFetch('/', RootResponse)
  message = data.message
} catch (e) {
  error = e instanceof Error ? e.message : String(e)
}
</script>

<template>
  <div class="mx-auto flex max-w-2xl flex-col items-start gap-4 p-6 text-slate-900">
    <p v-if="error">Failed to load: {{ error }}</p>
    <h1 v-else class="text-2xl font-semibold">{{ message }}</h1>
    <RouterLink
      :to="{ name: 'new-chat' }"
      class="rounded-full bg-indigo-600 px-4 py-2 font-medium text-white transition hover:bg-indigo-500"
    >
      New chat
    </RouterLink>
  </div>
</template>
