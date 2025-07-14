import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import ThreadList from './pages/ThreadList'
import ThreadDetail from './pages/ThreadDetail'

// 主App组件，配置路由
function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<ThreadList />} />
        <Route path="/simpcity/threads/:id" element={<ThreadDetail />} />
      </Routes>
    </Router>
  )
}

export default App
