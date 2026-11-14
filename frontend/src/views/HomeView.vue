<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="mx-auto flex max-w-2xl flex-col items-start gap-4 p-6 text-slate-900">
    <h1 class="text-2xl font-semibold">
      AIPlayground
    </h1>
    <RouterLink
      :to="{ name: 'new-chat' }"
      class="rounded-full bg-indigo-600 px-4 py-2 font-medium text-white transition hover:bg-indigo-500"
    >
      New chat
    </RouterLink>
  </div>
</template>
