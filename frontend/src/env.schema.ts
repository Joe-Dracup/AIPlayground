import { z } from 'zod'

// Add new VITE_* vars here (and to .env.example).
const envSchema = z.object({
  VITE_API_BASE_URL: z.url(),
})

export type Env = z.output<typeof envSchema>

// Shared by the app and vite.config.ts, so bad config is reported both in the terminal and the browser.
export function parseEnv(source: Record<string, unknown>): Env {
  const result = envSchema.safeParse(source)
  if (!result.success) {
    throw new Error(
      `Invalid environment variables:\n${z.prettifyError(result.error)}\n\n` +
        'Check frontend/.env (see .env.example for the expected values).',
    )
  }
  return result.data
}
