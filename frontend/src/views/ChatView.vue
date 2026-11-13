<script setup lang="ts">
import { useWebSocket } from '@vueuse/core'
import { env } from '@/env'
import { nextTick, ref, useTemplateRef } from 'vue'
import { z } from 'zod'

type ChatMessage = { role: 'user' | 'assistant'; content: string }

const ServerMessage = z.discriminatedUnion('type', [
  z.object({ type: z.literal('delta'), text: z.string() }),
  z.object({ type: z.literal('done') }),
])

const wsURL = new URL('ws', env.VITE_API_BASE_URL)
const input = ref('')
const messages = ref<ChatMessage[]>([])
const streaming = ref(false)
const scroller = useTemplateRef('scroller')

const { send } = useWebSocket(wsURL, {
  onMessage(_ws, event) {
    const result = ServerMessage.safeParse(JSON.parse(event.data))
    if (!result.success) {
      console.error('Unexpected message from server', event.data, result.error)
      return
    }

    if (result.data.type === 'delta') {
      // submit() adds an empty assistant message, which the deltas fill in.
      const reply = messages.value.at(-1)
      if (reply?.role === 'assistant') reply.content += result.data.text
      scrollToBottom()
    } else {
      streaming.value = false
    }
  },
})

async function scrollToBottom() {
  await nextTick()
  scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: 'smooth' })
}

function submit() {
  const text = input.value.trim()
  if (!text || streaming.value) return
  send(text)
  messages.value.push({ role: 'user', content: text }, { role: 'assistant', content: '' })
  streaming.value = true
  input.value = ''
  scrollToBottom()
}
</script>

<template>
  <div class="mx-auto flex h-dvh max-w-2xl flex-col text-slate-900">
    <div ref="scroller" class="flex flex-1 flex-col gap-2 overflow-y-auto p-4">
      <p v-if="!messages.length" class="m-auto text-sm text-slate-400">Say something to start.</p>
      <div
        v-for="(message, i) in messages"
        :key="i"
        :class="[
          'max-w-[80%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2',
          message.role === 'user'
            ? 'self-end rounded-br-sm bg-indigo-600 text-white'
            : 'self-start rounded-bl-sm bg-slate-100 text-slate-800',
        ]"
      >
        {{ message.content || '…' }}
      </div>
    </div>

    <form @submit.prevent="submit" class="flex gap-2 border-t border-slate-200 p-4">
      <input
        v-model="input"
        type="text"
        aria-label="Message"
        placeholder="Message"
        class="flex-1 rounded-full border border-slate-300 px-4 py-2 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
      />
      <button
        type="submit"
        :disabled="streaming"
        class="rounded-full bg-indigo-600 px-4 py-2 font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
      >
        Send
      </button>
    </form>
  </div>
</template>
