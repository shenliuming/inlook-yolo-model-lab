import { apiFetch, parseApiData } from './client'

export const createTranscription = async (payload) =>
  parseApiData(
    await apiFetch('/api/v1/transcriptions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const getTranscription = async (transcriptionId) =>
  parseApiData(await apiFetch(`/api/v1/transcriptions/${transcriptionId}`))

export const getSubtitleBundle = async (subtitleId) =>
  parseApiData(await apiFetch(`/api/v1/subtitles/${subtitleId}`))
