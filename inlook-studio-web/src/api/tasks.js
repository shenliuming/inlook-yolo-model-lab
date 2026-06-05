import { apiFetch, parseApiData } from './client'

export const listTasks = async () => parseApiData(await apiFetch('/api/v1/tasks'))
export const getTask = async (taskId) => parseApiData(await apiFetch(`/api/v1/tasks/${taskId}`))
