import { apiFetch, apiUrl } from './client'

const parseChanjingEnvelope = async (response) => {
  const payload = await response.json()
  if (payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'success')) {
    if (!payload.success) {
      const error = new Error(payload.message || '请求失败')
      error.data = payload.data || null
      error.traceId = payload.trace_id || ''
      throw error
    }
    return payload.data
  }
  return payload
}

export const getChanjingConfigStatus = async () =>
  parseChanjingEnvelope(await apiFetch('/api/v1/studio/digital-human/chanjing/config/status'))

export const uploadChanjingTrainingVideo = async (file, payload) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('name', payload.name || '')
  formData.append('train_type', payload.trainType || 'both')
  formData.append('resolution_rate', String(payload.resolutionRate ?? 0))
  formData.append('language', payload.language || 'cn')
  formData.append('error_skip', String(Boolean(payload.errorSkip)))
  return parseChanjingEnvelope(
    await apiFetch('/api/v1/studio/digital-human/chanjing/custom-persons/train-upload', {
      method: 'POST',
      body: formData,
    }),
  )
}

export const getChanjingTrainingJob = async (jobId) =>
  parseChanjingEnvelope(await apiFetch(`/api/v1/studio/digital-human/chanjing/custom-persons/train/${jobId}`))

export const listChanjingPersons = async (params = {}) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  })
  return parseChanjingEnvelope(await apiFetch(`/api/v1/studio/digital-human/chanjing/persons?${query.toString()}`))
}

export const createChanjingVideoJob = async (payload) =>
  parseChanjingEnvelope(
    await apiFetch('/api/v1/studio/digital-human/chanjing/videos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const getChanjingVideoJob = async (jobId) =>
  parseChanjingEnvelope(await apiFetch(`/api/v1/studio/digital-human/chanjing/videos/${jobId}`))

export const listChanjingJobs = async (params = {}) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  })
  return parseChanjingEnvelope(await apiFetch(`/api/v1/studio/digital-human/chanjing/jobs?${query.toString()}`))
}

export const getChanjingJobOutputUrl = (jobId) => apiUrl(`/api/v1/studio/digital-human/chanjing/jobs/${jobId}/output`)
