import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'

import { ApiError, ApiValidationError, apiFetch } from '../client'

const env = vi.hoisted(() => ({ VITE_API_BASE_URL: 'http://api.test' }))
vi.mock('@/env', () => ({ env }))

function mockFetch(response: Response) {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const MessageSchema = z.object({ message: z.string() })

describe('apiFetch', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    env.VITE_API_BASE_URL = 'http://api.test'
  })

  it('prefixes the path with VITE_API_BASE_URL and returns the parsed body', async () => {
    env.VITE_API_BASE_URL = 'http://api.test/'
    const fetchMock = mockFetch(jsonResponse({ message: 'Hello world' }))

    const data = await apiFetch('/items/1', MessageSchema)

    expect(fetchMock.mock.calls[0]?.[0]).toBe('http://api.test/items/1')
    expect(data).toEqual({ message: 'Hello world' })
  })

  it('returns the schema output, not the raw body', async () => {
    mockFetch(jsonResponse({ message: 'Hello world', extra: true }))

    const data = await apiFetch('/', MessageSchema.transform((d) => d.message.toUpperCase()))

    expect(data).toBe('HELLO WORLD')
  })

  it('passes through request config', async () => {
    const fetchMock = mockFetch(jsonResponse({}))

    await apiFetch('items', z.object({}), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'x' }),
    })

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    const headers = new Headers(init.headers)
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"name":"x"}')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Accept')).toBe('application/json')
  })

  it('throws ApiValidationError when the body does not match the schema', async () => {
    mockFetch(jsonResponse({ Hello: 'World' }))

    const error = await apiFetch('/', MessageSchema).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiValidationError)
    expect(error).toMatchObject({ path: '/', issues: [{ path: ['message'] }] })
  })

  it('throws ApiError with the response body on non-2xx', async () => {
    mockFetch(jsonResponse({ detail: 'Not Found' }, 404))

    const error = await apiFetch('missing', MessageSchema).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, body: { detail: 'Not Found' } })
  })
})
