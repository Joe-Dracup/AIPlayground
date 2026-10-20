import { afterEach, describe, it, expect, vi } from 'vitest'
import { h, Suspense } from 'vue'

import { flushPromises, mount } from '@vue/test-utils'
import { apiFetch } from '@/api/client'
import HomeView from '../HomeView.vue'

vi.mock('@/api/client', () => ({ apiFetch: vi.fn<typeof apiFetch>() }))

// HomeView is an async component, so it has to render inside <Suspense>
function mountWithSuspense() {
  return mount({
    render: () =>
      h(Suspense, null, {
        default: () => h(HomeView),
        fallback: () => h('p', 'Loading…'),
      }),
  })
}

describe('HomeView', () => {
  afterEach(() => {
    vi.mocked(apiFetch).mockReset()
  })

  it('shows the message from the API', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ message: 'Hello world' })

    const wrapper = mountWithSuspense()
    expect(wrapper.text()).toContain('Loading')

    await flushPromises()
    expect(apiFetch).toHaveBeenCalledWith('/', expect.anything())
    expect(wrapper.find('h1').text()).toBe('Hello world')
  })

  it('shows an error if the request fails', async () => {
    vi.mocked(apiFetch).mockRejectedValue(new Error('Network down'))

    const wrapper = mountWithSuspense()
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load: Network down')
  })
})
