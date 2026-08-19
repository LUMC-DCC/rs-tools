import { Route, Routes } from 'react-router-dom'

import CenteredState from './components/common/CenteredState'
import HomePage from './pages/HomePage'
import WorkspacePage from './pages/WorkspacePage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/w/:workspaceId" element={<WorkspacePage />} />
      <Route
        path="*"
        element={
          <CenteredState title="This page does not exist" eyebrow="404">
            <a className="button button-primary" href="/">
              Return home
            </a>
          </CenteredState>
        }
      />
    </Routes>
  )
}
