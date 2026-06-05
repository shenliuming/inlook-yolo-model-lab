import { apiFetch, parseApiData } from './client'

export const getHealth = async () => {
  const response = await apiFetch('api/v1/health')
  return parseApiData(response)
}

export const getVisionHealth = async () => {
  const response = await apiFetch('api/v1/vision/health')
  return parseApiData(response)
}

export const getVisionModels = async () => {
  const response = await apiFetch('api/v1/vision/models')
  return parseApiData(response)
}

export const detectImage = async (formData) => {
  const response = await apiFetch('api/v1/vision/images/detect', {
    method: 'POST',
    body: formData,
  })
  return parseApiData(response)
}

export const detectVideo = async (formData) => {
  const response = await apiFetch('api/v1/vision/videos/detect', {
    method: 'POST',
    body: formData,
  })
  return parseApiData(response)
}

export const detectRealtime = async (formData) => {
  const response = await apiFetch('api/v1/vision/realtime/detect', {
    method: 'POST',
    body: formData,
  })
  return parseApiData(response)
}
