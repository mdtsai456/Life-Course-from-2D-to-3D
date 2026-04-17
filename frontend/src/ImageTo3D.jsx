import { useEffect, useRef, useState } from 'react'
import { convertTo3D } from './api'
import { EXAMPLES } from './examples'
import { validateFile } from './validation'

export default function ImageTo3D() {
  const [file, setFile] = useState(null)
  const [originalUrl, setOriginalUrl] = useState(null)
  const [model3dUrl, setModel3dUrl] = useState(null)
  const [step, setStep] = useState('idle') // idle | converting | done
  const [selectedExampleId, setSelectedExampleId] = useState(null)
  const [loadingExampleId, setLoadingExampleId] = useState(null)
  const [error, setError] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const abortRef = useRef(null)
  const dragCounterRef = useRef(0)
  const model3dUrlRef = useRef(null)

  useEffect(() => { model3dUrlRef.current = model3dUrl }, [model3dUrl])

  useEffect(() => {
    if (!file) {
      setOriginalUrl(null)
      return
    }

    const url = URL.createObjectURL(file)
    setOriginalUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      if (model3dUrlRef.current) URL.revokeObjectURL(model3dUrlRef.current)
    }
  }, [])

  function resetResult() {
    if (model3dUrl) URL.revokeObjectURL(model3dUrl)
    setModel3dUrl(null)
    setStep('idle')
    setError('')
  }

  function applySelectedFile(selected, exampleId = null) {
    resetResult()

    if (!selected) {
      setFile(null)
      setSelectedExampleId(null)
      return false
    }

    const err = validateFile(selected)
    if (err) {
      setError(err)
      setFile(null)
      setSelectedExampleId(null)
      return false
    }

    setFile(selected)
    setSelectedExampleId(exampleId)
    return true
  }

  function handleFileChange(e) {
    applySelectedFile(e.target.files?.[0] || null)
    e.target.value = ''
  }

  async function runConversion(selectedFile) {
    resetResult()
    setStep('converting')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const result = await convertTo3D(selectedFile, controller.signal)
      setModel3dUrl(result.url)
      setStep('done')
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || '發生錯誤，請重試。')
        setStep('idle')
      }
    } finally {
      abortRef.current = null
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!file || isBusy) return
    await runConversion(file)
  }

  async function handleExampleClick(example) {
    if (isBusy) return

    setError('')
    setLoadingExampleId(example.id)
    try {
      const response = await fetch(example.src)
      if (!response.ok) throw new Error('範例圖片載入失敗，請重試。')

      const blob = await response.blob()
      const exampleFile = new File([blob], example.filename, {
        type: example.mimeType,
      })

      if (!applySelectedFile(exampleFile, example.id)) return
      await runConversion(exampleFile)
    } catch (err) {
      setError(err.message || '範例圖片載入失敗，請重試。')
      setStep('idle')
    } finally {
      setLoadingExampleId(null)
    }
  }

  const isBusy = step === 'converting' || loadingExampleId !== null

  function handleDragEnter(e) {
    e.preventDefault()
    if (isBusy) return
    dragCounterRef.current++
    setDragOver(true)
  }

  function handleDragLeave(e) {
    e.preventDefault()
    if (isBusy) return
    dragCounterRef.current--
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0
      setDragOver(false)
    }
  }

  function handleDragOver(e) {
    e.preventDefault()
  }

  function handleDrop(e) {
    e.preventDefault()
    dragCounterRef.current = 0
    setDragOver(false)
    if (isBusy) return
    applySelectedFile(e.dataTransfer.files?.[0] || null)
  }

  return (
    <div className="uploader">
      <section className="examples-section">
        <h2 className="section-title">範例圖片</h2>
        <p className="section-description">點一張圖片即可直接開始 2D 轉 3D。</p>
        <div className="example-grid">
          {EXAMPLES.map((example) => (
            <button
              key={example.id}
              type="button"
              className={`example-card${selectedExampleId === example.id ? ' active' : ''}`}
              onClick={() => handleExampleClick(example)}
              disabled={isBusy}
            >
              <img src={example.src} alt={example.label} className="example-image" />
              <span className="example-label">
                {loadingExampleId === example.id ? '載入中…' : example.label}
              </span>
            </button>
          ))}
        </div>
      </section>

      <form
        className={`upload-form${dragOver ? ' drag-over' : ''}`}
        onSubmit={handleSubmit}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <label htmlFor="img3d-upload" className="file-label">
          <input
            id="img3d-upload"
            type="file"
            accept="image/png,image/jpeg"
            onChange={handleFileChange}
            disabled={isBusy}
            className="file-input"
          />
          <span className="file-button">選擇圖片</span>
          <span className="file-name">
            {file ? file.name : '未選擇檔案'}
          </span>
        </label>
        <button
          type="submit"
          disabled={!file || isBusy}
          className="submit-button"
        >
          {isBusy ? <><span className="spinner" /> 正在轉換 3D 模型…</> : '轉換 3D'}
        </button>
      </form>

      {error && <p className="error-message">{error}</p>}

      {originalUrl && (
        <div className="preview-grid">
          <div className="preview-card">
            <h3 className="preview-title">原始圖片</h3>
            <img src={originalUrl} alt="原始圖片" className="preview-image" />
          </div>
        </div>
      )}

      {step === 'done' && model3dUrl && (
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
