import { useState, useEffect } from 'react'
import './App.css'

// 定义线程数据类型
interface ThreadInfo {
  thread_title: string
  thread_url: string
  posts_count: number
  latest_post_timestamp: string | null
  first_post_timestamp: string | null
  authors_count: number
}

interface ThreadsResponse {
  success: boolean
  message: string
  data: ThreadInfo[]
  total_count: number
}

function App() {
  const [threads, setThreads] = useState<ThreadInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const itemsPerPage = 20

  // 获取线程列表
  const fetchThreads = async (page: number = 1) => {
    try {
      setLoading(true)
      setError(null)
      
      const offset = (page - 1) * itemsPerPage
      const response = await fetch(`/api/threads/?limit=${itemsPerPage}&offset=${offset}`)
      
      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`)
      }
      
      const data: ThreadsResponse = await response.json()
      
      if (data.success) {
        setThreads(data.data)
        setTotalCount(data.total_count)
        setCurrentPage(page)
      } else {
        throw new Error(data.message || '获取线程列表失败')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }

  // 组件加载时获取数据
  useEffect(() => {
    fetchThreads(1)
  }, [])

  // 格式化时间
  const formatDate = (dateString: string | null) => {
    if (!dateString) return '无'
    return new Date(dateString).toLocaleString('zh-CN')
  }

  // 处理分页
  const totalPages = Math.ceil(totalCount / itemsPerPage)
  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      fetchThreads(page)
    }
  }

  // 刷新数据
  const handleRefresh = () => {
    fetchThreads(currentPage)
  }

  return (
    <div className="app">
      <header className="header">
        <h1>SimpCity 线程列表</h1>
        <div className="header-actions">
          <button onClick={handleRefresh} disabled={loading} className="refresh-btn">
            {loading ? '刷新中...' : '刷新'}
          </button>
        </div>
      </header>

      {error && (
        <div className="error-message">
          <p>错误: {error}</p>
          <button onClick={handleRefresh} className="retry-btn">重试</button>
        </div>
      )}

      {loading && !error && (
        <div className="loading">
          <p>加载中...</p>
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="threads-stats">
            <p>共 {totalCount} 个线程</p>
          </div>

          <div className="threads-list">
            {threads.map((thread, index) => (
              <div key={thread.thread_url} className="thread-card">
                <div className="thread-header">
                  <h3 className="thread-title">{thread.thread_title}</h3>
                  <span className="thread-index">#{(currentPage - 1) * itemsPerPage + index + 1}</span>
                </div>
                
                <div className="thread-meta">
                  <div className="thread-stats">
                    <span className="stat">
                      <strong>帖子数:</strong> {thread.posts_count}
                    </span>
                    <span className="stat">
                      <strong>参与者:</strong> {thread.authors_count}
                    </span>
                  </div>
                  
                  <div className="thread-dates">
                    <div className="date-item">
                      <strong>首贴时间:</strong> {formatDate(thread.first_post_timestamp)}
                    </div>
                    <div className="date-item">
                      <strong>最新回复:</strong> {formatDate(thread.latest_post_timestamp)}
                    </div>
                  </div>
                </div>
                
                <div className="thread-url">
                  <a href={thread.thread_url} target="_blank" rel="noopener noreferrer">
                    查看原帖
                  </a>
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="pagination">
              <button 
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                className="page-btn"
              >
                上一页
              </button>
              
              <div className="page-info">
                <span>第 {currentPage} 页，共 {totalPages} 页</span>
              </div>
              
              <button 
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="page-btn"
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default App
