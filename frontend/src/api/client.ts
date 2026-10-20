import type { z } from 'zod'

import { env } from '@/env'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
  }
}

export class ApiValidationError extends Error {
  constructor(
    public readonly path: string,
    public readonly issues: z.core.$ZodIssue[],
  ) {
    super(`Unexpected response shape from ${path}`)
    this.name = 'ApiValidationError'
  }
}

function buildUrl(path: string): string {
  return `${env.VITE_API_BASE_URL.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const contentType = response.headers.get('Content-Type') ?? ''
  return contentType.includes('application/json') ? response.json() : response.text()
}

/**
 * Fetch a path relative to VITE_API_BASE_URL and validate the response body with `schema`.
 * Accepts the same options as `fetch`. Throws ApiError on non-2xx responses and
 * ApiValidationError if the body doesn't match the schema.
 */
export async function apiFetch<Schema extends z.ZodType>(
  path: string,
  schema: Schema,
  init: RequestInit = {},
): Promise<z.output<Schema>> {
  const headers = new Headers(init.headers)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')

  const response = await fetch(buildUrl(path), { ...init, headers })
  const body = await parseBody(response)

  if (!response.ok) throw new ApiError(response.status, body)

  const result = schema.safeParse(body)
  if (!result.success) throw new ApiValidationError(path, result.error.issues)
  return result.data
}
