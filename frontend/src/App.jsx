import { useState } from 'react'
import RemoveBg from './RemoveBg'
import ImageTo3D from './ImageTo3D'

function TabPanel({ id, labelledBy, active, children }) {
  return (
    <div role="tabpanel" id={id} aria-labelledby={labelledBy} style={{ display: active ? 'block' : 'none' }}>
      {children}
    </div>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState('remove-bg')

  return (
    <div className="app">
      <header className="app-header">
        <h1>2D 轉 3D 工具</h1>
        <nav className="nav-tabs" role="tablist">
          <button
            role="tab"
            id="tab-remove-bg"
            aria-selected={activeTab === 'remove-bg'}
            aria-controls="panel-remove-bg"
            className={`nav-tab${activeTab === 'remove-bg' ? ' active' : ''}`}
            onClick={() => setActiveTab('remove-bg')}
          >
            移除背景
          </button>
          <button
            role="tab"
            id="tab-image-to-3d"
            aria-selected={activeTab === 'image-to-3d'}
            aria-controls="panel-image-to-3d"
            className={`nav-tab${activeTab === 'image-to-3d' ? ' active' : ''}`}
            onClick={() => setActiveTab('image-to-3d')}
          >
            圖片轉 3D
          </button>
        </nav>
      </header>
      <main>
        <TabPanel id="panel-remove-bg" labelledBy="tab-remove-bg" active={activeTab === 'remove-bg'}>
          <RemoveBg />
        </TabPanel>
        <TabPanel id="panel-image-to-3d" labelledBy="tab-image-to-3d" active={activeTab === 'image-to-3d'}>
          <ImageTo3D />
        </TabPanel>
      </main>
    </div>
  )
}
