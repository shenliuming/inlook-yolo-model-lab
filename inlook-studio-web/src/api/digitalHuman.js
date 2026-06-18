import { apiFetch, parseApiData } from './client'

export const listDigitalHumanTemplates = async () =>
  parseApiData(await apiFetch('/api/v1/digital-human/templates'))

export const importDigitalHumanTemplate = async (file, payload = {}) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('name', payload.name || '')
  formData.append('trainingType', payload.trainingType || 'full')
  formData.append('resolution', payload.resolution || '1080p')
  return parseApiData(
    await apiFetch('/api/v1/digital-human/templates/import', {
      method: 'POST',
      body: formData,
    }),
  )
}

export const syncDigitalHumanTemplates = async () =>
  parseApiData(
    await apiFetch('/api/v1/digital-human/templates/sync', {
      method: 'POST',
    }),
  )

export const listDigitalHumanTasks = async (params = {}) => {
  const query = new URLSearchParams()
  if (params.projectId) query.set('projectId', params.projectId)
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return parseApiData(await apiFetch(`/api/v1/digital-human/tasks${suffix}`))
}

export const getDigitalHumanTask = async (taskId) =>
  parseApiData(await apiFetch(`/api/v1/digital-human/tasks/${taskId}`))

export const generateDigitalHumanVideo = async (payload) =>
  parseApiData(
    await apiFetch('/api/v1/digital-human/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )
