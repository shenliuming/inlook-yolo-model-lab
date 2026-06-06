import { apiFetch, parseApiData } from './client'

export const getAiStatus = async () => {
  const response = await apiFetch('/api/v1/ai/status')
  return parseApiData(response)
}

export const rewriteCopy = async (payload) => {
  const response = await apiFetch('/api/v1/copy/rewrite', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return parseApiData(response)
}
