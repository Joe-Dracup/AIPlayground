<script setup lang="ts">
import { useWebSocket } from '@vueuse/core';
import {env} from '@/env'
import { ref } from 'vue';

const wsURL = new URL('ws', env.VITE_API_BASE_URL)
const message = ref('')
const {data, send} = useWebSocket(wsURL)
</script>

<template>
    <label for="input">Input Value</label>
    <input id="input" type="text" v-model="message"/>
    <button @click="send(message)">Send</button>

    {{ data }}
</template>