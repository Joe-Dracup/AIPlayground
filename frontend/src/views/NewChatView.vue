<script setup lang="ts">
import { useRouter } from 'vue-router'
import { z } from 'zod'

import { apiFetch } from '@/api/client'

const conversationCreatedSchema = z.object({
  id: z.uuid(),
})

const router = useRouter()
let error: string | null = null

try {
  const { id } = await apiFetch('/conversations', conversationCreatedSchema, { method: 'POST' })
  await router.replace({
    name: 'chat',
    params: { id },
  })
}
catch (e) {
  error = e instanceof Error
    ? e.message
    : String(e)
}
</script>

<template>
  <p class="p-6 text-slate-600">
    {{ error ? `Couldn't start a conversation: ${error}` : 'Starting a conversation…' }}
  </p>
</template>
