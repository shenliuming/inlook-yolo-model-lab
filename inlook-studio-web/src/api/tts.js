import { apiFetch, parseApiData } from './client'

export const listVoices = async () => parseApiData(await apiFetch('/api/v1/tts/voices'))

export const listVoiceProfiles = async () => parseApiData(await apiFetch('/api/v1/voices'))

export const getVoiceProfile = async (voiceId) =>
  parseApiData(await apiFetch(`/api/v1/voices/${voiceId}`))

export const updateVoiceProfile = async (voiceId, payload) =>
  parseApiData(
    await apiFetch(`/api/v1/voices/${voiceId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const deleteVoiceProfile = async (voiceId) =>
  parseApiData(await apiFetch(`/api/v1/voices/${voiceId}`, { method: 'DELETE' }))

export const createVoiceProfile = async (formData) =>
  parseApiData(await apiFetch('/api/v1/voices', { method: 'POST', body: formData }))

export const createVoiceFromMaterial = async (payload) =>
  parseApiData(
    await apiFetch('/api/v1/voices/from-material', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const createVoicePreview = async (voiceId, payload) =>
  parseApiData(
    await apiFetch(`/api/v1/voices/${voiceId}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const createTraining = async (formData) =>
  parseApiData(await apiFetch('/api/v1/tts/trainings', { method: 'POST', body: formData }))

export const getTraining = async (trainingId) =>
  parseApiData(await apiFetch(`/api/v1/tts/trainings/${trainingId}`))

export const createSynthesis = async (payload) =>
  parseApiData(
    await apiFetch('/api/v1/tts/synthesis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const getSynthesis = async (synthesisId) =>
  parseApiData(await apiFetch(`/api/v1/tts/synthesis/${synthesisId}`))
