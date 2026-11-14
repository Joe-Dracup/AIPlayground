import { mount, RouterLinkStub } from '@vue/test-utils'

import { describe, expect, it } from 'vitest'
import HomeView from '../HomeView.vue'

function mountHome() {
  // No router is installed in tests, so swap RouterLink for a stub that just records its props.
  return mount(HomeView, {
    global: {
      stubs: { RouterLink: RouterLinkStub },
    },
  })
}

describe('home page', () => {
  it('shows the app name', () => {
    expect(mountHome().find('h1').text()).toBe('AIPlayground')
  })

  it('links to a new chat', () => {
    expect(mountHome().findComponent(RouterLinkStub).props('to')).toEqual({ name: 'new-chat' })
  })
})
