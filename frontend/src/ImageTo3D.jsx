import { useEffect, useRef, useState } from 'react'
import { removeBackground, convertTo3D } from './api'
import { validateFile } from './validation'

export default function ImageTo3D() {
  const [file, setFile] = useState(null)
  const [originalUrl, setOriginalUrl] = useState(null)
  const [removedBgUrl, setRemovedBgUrl] = useState(null)
  const [removedBgBlob, setRemovedBgBlob] = useState(null)
  const [model3dUrl, setModel3dUrl] = useState(null)
  const [step, setStep] = useState('idle') // idle | removing | removed | converting | done
  const [error, setError] = useState('')
  const abortRef = useRef(null)
  const removedBgUrlRef = useRef(null)
  const model3dUrlRef = useRef(null)

  // Keep refs in sync for unmount cleanup
  useEffect(() => { removedBgUrlRef.current = removedBgUrl }, [removedBgUrl])
  useEffect(() => { model3dUrlRef.current = model3dUrl }, [model3dUrl])

  // Create/revoke original preview URL
  useEffect(() => {
    if (!file) { setOriginalUrl(null); return }
    const url = URL.createObjectURL(file)
    setOriginalUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  // Cleanup URLs on unmount
  useEffect(() => {
    return () => {
      if (removedBgUrlRef.current) URL.revokeObjectURL(removedBgUrlRef.current)
      if (model3dUrlRef.current) URL.revokeObjectURL(model3dUrlRef.current)
    }
  }, [])

  function resetResults() {
    if (removedBgUrl) URL.revokeObjectURL(removedBgUrl)
    if (model3dUrl) URL.revokeObjectURL(model3dUrl)
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    setModel3dUrl(null)
    setStep('idle')
    setError('')
  }

  function handleFileChange(e) {
    const selected = e.target.files?.[0] || null
    resetResults()

    if (!selected) { setFile(null); return }

    const err = validateFile(selected)
    if (err) { setError(err); setFile(null); return }

    setFile(selected)
  }

  async function handleRemoveBg(e) {
    e.preventDefault()
    if (!file) return

    setStep('removing')
    setError('')
    if (removedBgUrl) URL.revokeObjectURL(removedBgUrl)
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    if (model3dUrl) URL.revokeObjectURL(model3dUrl)
    setModel3dUrl(null)

    const controller = new AbortController()
    abortRef.current = controller

    let succeeded = false
    try {
      const result = await removeBackground(file, controller.signal)
      setRemovedBgUrl(result.url)
      setRemovedBgBlob(result.blob)
      setStep('removed')
      succeeded = true
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || '發生錯誤，請重試。')
      }
    } finally {
      if (!succeeded) setStep('idle')
      abortRef.current = null
    }
  }

  async function handleConvertTo3D() {
    if (!removedBgBlob) return

    setStep('converting')
    setError('')
    if (model3dUrl) URL.revokeObjectURL(model3dUrl)
    setModel3dUrl(null)

    const pngFile = new File([removedBgBlob], 'removed_bg.png', { type: 'image/png' })
    const controller = new AbortController()
    abortRef.current = controller

    let succeeded = false
    try {
      const result = await convertTo3D(pngFile, controller.signal)
      setModel3dUrl(result.url)
      setStep('done')
      succeeded = true
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || '發生錯誤，請重試。')
      }
    } finally {
      if (!succeeded) setStep('removed')
      abortRef.current = null
    }
  }

  const isRemoving = step === 'removing'
  const isConverting = step === 'converting'
  const showRemovedResult = step === 'removed' || step === 'converting' || step === 'done'
  const show3dResult = step === 'done'

  return (
    <div className="uploader">
      <form className="upload-form" onSubmit={handleRemoveBg}>
        <label htmlFor="img3d-upload" className="file-label">
          <input
            id="img3d-upload"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={handleFileChange}
            disabled={isRemoving || isConverting}
            className="file-input"
          />
          <span className="file-button">選擇圖片</span>
          <span className="file-name">
            {file ? file.name : '未選擇檔案'}
          </span>
        </label>
        <button
          type="submit"
          disabled={!file || isRemoving || isConverting}
          className="submit-button"
        >
          {isRemoving ? <><span className="spinner" /> 移除背景中...</> : '移除背景'}
        </button>
      </form>

      {error && <p className="error-message">{error}</p>}

      {(originalUrl || showRemovedResult) && (
        <div className="preview-grid">
          {originalUrl && (
            <div className="preview-card">
              <h3 className="preview-title">原始圖片</h3>
              <img src={originalUrl} alt="原始圖片" className="preview-image" />
            </div>
          )}
          {showRemovedResult && removedBgUrl && (
            <div className="preview-card">
              <h3 className="preview-title">去背景結果</h3>
              <img
                src={removedBgUrl}
                alt="去背景結果"
                className="preview-image checkerboard"
              />
              <a
                href={removedBgUrl}
                download={file ? file.name.replace(/\.[^.]+$/, '') + '_no_bg.png' : 'no_bg.png'}
                className="download-button"
              >
                下載 PNG
              </a>
              <button
                onClick={handleConvertTo3D}
                disabled={isConverting}
                className="submit-button"
              >
                {isConverting ? <><span className="spinner" /> 轉換 3D 中...</> : '轉換 3D'}
              </button>
            </div>
          )}
        </div>
      )}

      {show3dResult && model3dUrl && (
        <div className="preview-card model-viewer-card">
          <h3 className="preview-title">3D 模型</h3>
          <model-viewer
            src={model3dUrl}
            auto-rotate
            camera-controls
          />
          <a
            href={model3dUrl}
            download={file ? file.name.replace(/\.[^.]+$/, '') + '.glb' : 'model.glb'}
            className="download-button"
          >
            下載 GLB
          </a>
        </div>
      )}
    </div>
  )
}
