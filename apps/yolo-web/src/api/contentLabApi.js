import { apiFetch, parseApiData } from './client'

export const healthTts = async () => {
  const response = await apiFetch('api/v1/content-lab/tts/health')
  return parseApiData(response)
}

export const createTtsTask = async (formData) => {
  const response = await apiFetch('api/v1/content-lab/tts/tasks', {
    method: 'POST',
    body: formData,
  })
  return parseApiData(response)
}

export const getTtsTask = async (taskId) => {
  const response = await apiFetch(`api/v1/content-lab/tts/tasks/${taskId}`)
  return parseApiData(response)
}

export const downloadTtsFile = (taskId, filename) => `api/v1/content-lab/tts/tasks/${taskId}/files/${filename}`
