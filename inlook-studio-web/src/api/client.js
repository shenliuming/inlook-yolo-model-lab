const apiBase = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:7860'

export const apiUrl = (path) => `${apiBase}${String(path || '').startsWith('/') ? path : `/${path}`}`

export const apiFetch = async (path, options = {}) => {
  const response = await fetch(apiUrl(path), options)
  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`
    let data = null
    try {
      const payload = await response.json()
      message = payload.message || payload.detail || message
      data = payload.data || null
    } catch {
      // ignore parse failure
    }
    const error = new Error(message)
    error.status = response.status
    error.data = data
    throw error
  }
  return response
}

export const parseApiData = async (response) => {
  const payload = await response.json()
  if (payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'code')) {
    return payload.data
  }
  return payload
}
