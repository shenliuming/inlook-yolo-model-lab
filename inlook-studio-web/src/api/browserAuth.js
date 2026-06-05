import { apiFetch, parseApiData } from './client'

export const startBrowserAuth = async (platform) =>
  parseApiData(await apiFetch(`/api/v1/browser-auth/${platform}/start`, { method: 'POST' }))

export const getBrowserAuthStatus = async (platform) =>
  parseApiData(await apiFetch(`/api/v1/browser-auth/${platform}/status`))

export const clearBrowserAuth = async (platform) =>
  parseApiData(await apiFetch(`/api/v1/browser-auth/${platform}`, { method: 'DELETE' }))
