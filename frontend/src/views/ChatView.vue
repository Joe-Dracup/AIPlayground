<script setup lang="ts">
import { useWebSocket } from '@vueuse/core'
import { env } from '@/env'
import { nextTick, ref, useTemplateRef } from 'vue'
import { RouterLink } from 'vue-router'
import { z } from 'zod'

const props = defineProps<{ id: string }>()

const ChatMessage = z.object({ role: z.enum(['user', 'assistant']), content: z.string() })
type ChatMessage = z.output<typeof ChatMessage>

const ServerMessage = z.discriminatedUnion('type', [
  z.object({ type: z.literal('history'), messages: z.array(ChatMessage) }),
  z.object({ type: z.literal('delta'), text: z.string() }),
  z.object({ type: z.literal('done') }),
  z.object({ type: z.literal('error'), message: z.string() }),
])

// Matches CONVERSATION_NOT_FOUND in the backend's main.py.
const CONVERSATION_NOT_FOUND = 4404

const wsURL = new URL(`ws/${props.id}`, env.VITE_API_BASE_URL)
const input = ref('')
const messages = ref<ChatMessage[]>([])
const loaded = ref(false)
const streaming = ref(false)
const notFound = ref(false)
const error = ref<string | null>(null)
const scroller = useTemplateRef('scroller')

const { send } = useWebSocket(wsURL, {
  onMessage(_ws, event) {
    const result = ServerMessage.safeParse(JSON.parse(event.data))
    if (!result.success) {
      console.error('Unexpected message from server', event.data, result.error)
      return
    }

    switch (result.data.type) {
      case 'history':
        messages.value = result.data.messages
        loaded.value = true
        scrollToBottom()
        break
      case 'delta': {
        // submit() adds an empty assistant message, which the deltas fill in.
        const reply = messages.value.at(-1)
        if (reply?.role === 'assistant') reply.content += result.data.text
        scrollToBottom()
        break
      }
      case 'done':
        streaming.value = false
        break
      case 'error':
        // Drop the reply bubble if nothing arrived; a partial reply stays visible.
        if (messages.value.at(-1)?.content === '') messages.value.pop()
        error.value = result.data.message
        streaming.value = false
        break
    }
  },
  onDisconnected(_ws, event) {
    if (event.code === CONVERSATION_NOT_FOUND) notFound.value = true
  },
})

async function scrollToBottom() {
  await nextTick()
  scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: 'smooth' })
}

function submit() {
  const text = input.value.trim()
  if (!text || !loaded.value || streaming.value) return
  send(text)
  messages.value.push({ role: 'user', content: text }, { role: 'assistant', content: '' })
  streaming.value = true
  error.value = null
  input.value = ''
  scrollToBottom()
}
</script>

<template>
  <div class="mx-auto flex h-dvh max-w-2xl flex-col text-slate-900">
    <div
      ref="scroller"
      role="log"
      aria-label="Conversation"
      class="flex flex-1 flex-col gap-2 overflow-y-auto p-4"
    >
      <p v-if="notFound" class="m-auto text-sm text-slate-500">
        Conversation not found.
        <RouterLink to="/chat" class="text-indigo-600 underline">Start a new one</RouterLink>
      </p>
      <p v-else-if="!messages.length" class="m-auto text-sm text-slate-400">Say something to start.</p>
      <article
        v-for="(message, i) in messages"
        :key="i"
        :aria-label="message.role === 'user' ? 'You' : 'Assistant'"
        :class="[
          'max-w-[80%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2',
          message.role === 'user'
            ? 'self-end rounded-br-sm bg-indigo-600 text-white'
            : 'self-start rounded-bl-sm bg-slate-100 text-slate-800',
        ]"
      >
        {{ message.content || '…' }}
      </article>
    </div>

    <p v-if="error" role="alert" class="px-4 pt-2 text-sm text-red-600">{{ error }}</p>
    <form @submit.prevent="submit" class="flex gap-2 border-t border-slate-200 p-4">
      <input
        v-model="input"
        type="text"
        :disabled="!loaded"
        aria-label="Message"
        placeholder="Message"
        class="flex-1 rounded-full border border-slate-300 px-4 py-2 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 disabled:bg-slate-50"
      />
      <button
        type="submit"
        :disabled="!loaded || streaming"
        class="rounded-full bg-indigo-600 px-4 py-2 font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
      >
        Send
      </button>
    </form>
  </div>
</template>
