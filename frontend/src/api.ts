export type AuthConfig = {
  oauth_configured: boolean
  dev_login: boolean
  app_configured: boolean
  app_slug: string | null
  app_install_url: string | null
  webhook_configured: boolean
  banner: string | null
}

export type Me = {
  id: number
  github_user_id: number
  login: string
  avatar_url: string
  dev: boolean
  installations: Installation[]
  repo_count: number
  enabled_count: number
  banner: string | null
}

export type Installation = {
  installation_id: number
  account_login: string
  account_type: string
}

export type Repo = {
  id: number
  installation_id: number
  owner: string
  name: string
  github_repo_id: number
  enabled: boolean
  full_name: string
}

async function readDetail(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
    }
  } catch {
    /* ignore */
  }
  return res.statusText || 'request failed'
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: 'include' })
  if (!res.ok) {
    throw new Error(await readDetail(res))
  }
  return (await res.json()) as T
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(await readDetail(res))
  }
  return (await res.json()) as T
}

export async function fetchMe(): Promise<Me | null> {
  const res = await fetch('/api/me', { credentials: 'include' })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(await readDetail(res))
  return (await res.json()) as Me
}

export async function fetchAuthConfig(): Promise<AuthConfig> {
  return apiGet<AuthConfig>('/api/auth/config')
}

export async function fetchRepos(): Promise<{
  repos: Repo[]
  mock: boolean
  banner: string | null
  installations: Installation[]
}> {
  return apiGet('/api/repos')
}

export async function patchRepo(id: number, enabled: boolean): Promise<Repo> {
  const body = await apiPatch<{ repo: Repo }>('/api/repos', { id, enabled })
  return body.repo
}
