import { useEffect, useRef, useState } from 'react'
import { removeBackground } from './api'
import { validateFile } from './validation'

export default function RemoveBg() {
  const [file, setFile] = useState(null)
  const [originalUrl, setOriginalUrl] = useState(null)
  const [resultUrl, setResultUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const abortRef = useRef(null)

  // Create/revoke original preview URL
  useEffect(() => {
    if (!file) { setOriginalUrl(null); return }
    const url = URL.createObjectURL(file)
    setOriginalUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  function handleFileChange(e) {
    const selected = e.target.files?.[0] || null
    setError('')
    if (resultUrl) { URL.revokeObjectURL(resultUrl); setResultUrl(null) }

    if (!selected) { setFile(null); return }

    const err = validateFile(selected)
    if (err) { setError(err); setFile(null); return }

    setFile(selected)
    e.target.value = ''
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!file || loading) return

    setLoading(true)
    setError('')
    if (resultUrl) { URL.revokeObjectURL(resultUrl); setResultUrl(null) }

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const { url } = await removeBackground(file, controller.signal)
      if (controller.signal.aborted) {
        URL.revokeObjectURL(url)
        return
      }
      setResultUrl(url)
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || '發生錯誤，請重試。')
      }
    } finally {
      setLoading(false)
      abortRef.current = null
    }
  }

  return (
    <div className="uploader">
      <form className="upload-form" onSubmit={handleSubmit}>
        <label htmlFor="bg-upload" className="file-label">
          <input
            id="bg-upload"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={handleFileChange}
            disabled={loading}
            className="file-input"
          />
          <span className="file-button">選擇圖片</span>
          <span className="file-name">
            {file ? file.name : '未選擇檔案'}
          </span>
        </label>
        <button
          type="submit"
          disabled={!file || loading}
          className="submit-button"
        >
          {loading ? <><span className="spinner" /> 處理中...</> : '移除背景'}
        </button>
      </form>

      {error && <p className="error-message">{error}</p>}

      {(originalUrl || resultUrl) && (
        <div className="preview-grid">
          {originalUrl && (
            <div className="preview-card">
              <h3 className="preview-title">原始圖片</h3>
              <img src={originalUrl} alt="原始圖片" className="preview-image" />
            </div>
          )}
          {resultUrl && (
            <div className="preview-card">
              <h3 className="preview-title">處理結果</h3>
              <img src={resultUrl} alt="去背景結果" className="preview-image checkerboard" />
              <a
                href={resultUrl}
                download={file ? file.name.replace(/\.[^.]+$/, '') + '_no_bg.png' : 'no_bg.png'}
                className="download-button"
              >
                下載
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
