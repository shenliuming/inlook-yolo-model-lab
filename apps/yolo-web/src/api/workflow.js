import { apiFetch, parseApiData } from './client'

export const getWorkflowHealth = async () => {
  const response = await apiFetch('api/v1/content-lab/health')
  return parseApiData(response)
}

export const createMaterialTask = async (formData) => {
  const response = await apiFetch('api/v1/content-lab/materials/tasks', {
    method: 'POST',
    body: formData,
  })
  return parseApiData(response)
}

export const getMaterialTask = async (taskId) => {
  const response = await apiFetch(`api/v1/content-lab/materials/tasks/${taskId}`)
  return parseApiData(response)
}

export const createSubtitleTask = async (formData) => {
  const response = await apiFetch('api/v1/content-lab/subtitles/tasks', {
    method: 'POST',
    body: formData,
  })
  return parseApiData(response)
}

export const getSubtitleTask = async (taskId) => {
  const response = await apiFetch(`api/v1/content-lab/subtitles/tasks/${taskId}`)
  return parseApiData(response)
}

export const reburnSubtitleTask = async (taskId, formData) => {
  const response = await apiFetch(`api/v1/content-lab/subtitles/tasks/${taskId}/reburn`, {
    method: 'POST',
    body: formData,
  })
  return parseApiData(response)
}
