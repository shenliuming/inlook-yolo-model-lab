import { apiFetch, parseApiData } from './client'

export const createStudioProject = async (payload = {}) =>
  parseApiData(
    await apiFetch('/api/v1/studio/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const getStudioProject = async (projectId) =>
  parseApiData(await apiFetch(`/api/v1/studio/projects/${projectId}`))

export const listStudioTasks = async () =>
  parseApiData(await apiFetch('/api/v1/studio/tasks'))

export const extractStudioMaterial = async (projectId, payload) =>
  parseApiData(
    await apiFetch(`/api/v1/studio/projects/${projectId}/materials/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const uploadStudioMaterial = async (projectId, formData) =>
  parseApiData(
    await apiFetch(`/api/v1/studio/projects/${projectId}/materials/upload`, {
      method: 'POST',
      body: formData,
    }),
  )

export const uploadStudioVoiceAudio = async (projectId, formData) =>
  parseApiData(
    await apiFetch(`/api/v1/studio/projects/${projectId}/voice-audio/upload`, {
      method: 'POST',
      body: formData,
    }),
  )

export const createStudioTranscription = async (projectId, payload) =>
  parseApiData(
    await apiFetch(`/api/v1/studio/projects/${projectId}/transcriptions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const rewriteStudioCopy = async (projectId, payload) =>
  parseApiData(
    await apiFetch(`/api/v1/studio/projects/${projectId}/copy/rewrite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const createStudioSynthesis = async (projectId, payload) =>
  parseApiData(
    await apiFetch(`/api/v1/studio/projects/${projectId}/tts/synthesis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const getStudioSynthesis = async (projectId, synthesisId) =>
  parseApiData(await apiFetch(`/api/v1/studio/projects/${projectId}/tts/synthesis/${synthesisId}`))

export const generateStudioDigitalHumanVideo = async (projectId, payload) =>
  parseApiData(
    await apiFetch(`/api/v1/studio/projects/${projectId}/digital-human/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )

export const getStudioDigitalHumanTask = async (projectId, taskId) =>
  parseApiData(await apiFetch(`/api/v1/studio/projects/${projectId}/digital-human/${taskId}`))
