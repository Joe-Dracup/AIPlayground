import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'

async function startChat(page: Page) {
  await page.goto('/')
  await page.getByRole('link', { name: 'New chat' }).click()
  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/)
}

async function send(page: Page, text: string) {
  const input = page.getByRole('textbox', { name: 'Message' })
  await input.fill(text)
  await input.press('Enter')
}

function conversation(page: Page) {
  return page.getByRole('log', { name: 'Conversation' })
}

test('starts a new, empty chat from the home page', async ({ page }) => {
  await startChat(page)
  await expect(conversation(page)).toContainText('Say something to start.')
})

test('shows the message and the streamed reply', async ({ page }) => {
  await startChat(page)
  await send(page, 'hi')

  await expect(conversation(page).getByRole('article', { name: 'You' })).toHaveText('hi')
  await expect(conversation(page).getByRole('article', { name: 'Assistant' })).toHaveText(
    'Hi, how are you?',
  )
  await expect(page.getByRole('textbox', { name: 'Message' })).toHaveValue('')
})

test('answers using the place tools', async ({ page }) => {
  await startChat(page)
  await send(page, 'pubs near piccadilly')

  await expect(conversation(page).getByRole('article', { name: 'Assistant' })).toContainText(
    'Port Street Beer House',
  )
})

test('keeps the conversation after a reload', async ({ page }) => {
  await startChat(page)
  await send(page, 'hi')
  await expect(conversation(page).getByRole('article', { name: 'Assistant' })).toHaveText(
    'Hi, how are you?',
  )

  await page.reload()

  await expect(conversation(page).getByRole('article')).toHaveText([
    'hi',
    'Hi, how are you?',
  ])
})

test('shows an error and lets the chat carry on', async ({ page }) => {
  await startChat(page)
  await send(page, 'break')

  await expect(page.getByRole('alert')).toHaveText('Something went wrong. Try again in a moment.')
  await expect(conversation(page).getByRole('article', { name: 'Assistant' })).toHaveCount(0)

  await send(page, 'hi')

  await expect(conversation(page).getByRole('article', { name: 'Assistant' })).toHaveText(
    'Hi, how are you?',
  )
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('says when a conversation does not exist', async ({ page }) => {
  await page.goto(`/chat/${crypto.randomUUID()}`)

  await expect(conversation(page)).toContainText('Conversation not found.')
  await page.getByRole('link', { name: 'Start a new one' }).click()
  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/)
})
