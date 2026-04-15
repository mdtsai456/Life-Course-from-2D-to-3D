async function postForBlob(url, formData, fallbackMessage, signal) {
  let response
  try {
    response = await fetch(url, {
      method: 'POST',
      body: formData,
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error(fallbackMessage)
  }

  if (!response.ok) {
    let message = fallbackMessage
    try {
      const errorData = await response.json()
      if (typeof errorData.detail === 'string') {
        message = errorData.detail
      } else if (Array.isArray(errorData.detail)) {
        message = errorData.detail.map(e => e.msg ?? e.message ?? String(e)).join('; ')
      }
    } catch (err) {
      if (err.name === 'AbortError') throw err
    }
    throw new Error(message)
  }

  const blob = await response.blob()
  if (blob.size === 0) {
    throw new Error('伺服器回應為空。')
  }
  return { url: URL.createObjectURL(blob), blob }
}

export async function convertTo3D(file, signal) {
  const formData = new FormData()
  formData.append('file', file)
  return postForBlob('/api/image-to-3d', formData, '3D 轉換失敗。', signal)
}
