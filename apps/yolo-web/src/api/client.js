const appBase = import.meta.env.BASE_URL || '/'
const internalApiKey = import.meta.env.VITE_INTERNAL_API_KEY || ''

export const withBase = (path) => `${appBase}${String(path || '').replace(/^\/+/, '')}`

export const apiHeaders = () => {
  if (!internalApiKey) return {}
  return {
    'X-INLOOK-Key': internalApiKey,
  }
}

export const normalizeError = async (response) => {
  if (response.status === 413) {
    return '上传文件过大，请换一个更小的文件再试。'
  }
  try {
    const payload = await response.json()
    return payload.message || payload.detail || `请求失败（HTTP ${response.status}）`
  } catch {
    return `请求失败（HTTP ${response.status}）`
  }
}

export const apiFetch = async (path, options = {}) => {
  const response = await fetch(withBase(path), {
    ...options,
    headers: {
      ...apiHeaders(),
      ...(options.headers || {}),
    },
  })
  if (!response.ok) {
    throw new Error(await normalizeError(response))
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
