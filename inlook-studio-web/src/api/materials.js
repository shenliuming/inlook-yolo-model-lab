import { apiFetch, parseApiData } from './client'

export const extractMaterial = async (payload) =>
  parseApiData(
    await apiFetch('/api/v1/materials/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const uploadMaterial = async (formData) =>
  parseApiData(await apiFetch('/api/v1/materials/upload', { method: 'POST', body: formData }))

export const getMaterial = async (materialId) => parseApiData(await apiFetch(`/api/v1/materials/${materialId}`))
