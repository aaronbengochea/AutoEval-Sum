/**
 * Typed frontend environment contract.
 * Import `env` instead of accessing process.env directly.
 * Throws at module load time if any required var is missing.
 */

function requireEnv(key: string): string {
  const value = process.env[key];
  if (!value) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value;
}

export const env = {
  apiUrl: requireEnv("NEXT_PUBLIC_API_URL"),
} as const;

export type Env = typeof env;
