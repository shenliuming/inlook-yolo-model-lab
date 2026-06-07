import { apiFetch, parseApiData } from './client'

export const generateDigitalHumanVideo = async (payload) =>
  parseApiData(
    await apiFetch('/api/v1/digital-human/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )
