<script setup lang="ts">
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
  <p v-if="error">Failed to load: {{ error }}</p>
  <h1 v-else>{{ message }}</h1>
</template>
