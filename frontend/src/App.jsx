import { useState } from 'react'
import RemoveBg from './RemoveBg'
import ImageTo3D from './ImageTo3D'

function TabPanel({ active, children }) {
  return (
    <div style={{ display: active ? 'block' : 'none' }}>
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
        <nav className="nav-tabs">
          <button
            className={`nav-tab${activeTab === 'remove-bg' ? ' active' : ''}`}
            onClick={() => setActiveTab('remove-bg')}
          >
            移除背景
          </button>
          <button
            className={`nav-tab${activeTab === 'image-to-3d' ? ' active' : ''}`}
            onClick={() => setActiveTab('image-to-3d')}
          >
            圖片轉 3D
          </button>
        </nav>
      </header>
      <main>
        <TabPanel active={activeTab === 'remove-bg'}>
          <RemoveBg />
        </TabPanel>
        <TabPanel active={activeTab === 'image-to-3d'}>
          <ImageTo3D />
        </TabPanel>
      </main>
    </div>
  )
}
