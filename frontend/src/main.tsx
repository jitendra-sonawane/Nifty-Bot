import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './design/index.css'
import App from './App.tsx'

// #region agent log
try {
  fetch('http://127.0.0.1:7242/ingest/89bcb46c-6c02-4cbb-a825-e2a3bde2d465', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: 'fe_main_entry', timestamp: Date.now(), location: 'main.tsx', message: 'Frontend main.tsx executing', data: { hasRoot: !!document.getElementById('root') }, hypothesisId: 'A' }) }).catch(() => {})
} catch (_) {}
// #endregion
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
