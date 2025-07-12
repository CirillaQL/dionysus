import { useState, useEffect } from 'react'
import './App.css'
import ThreadDetail from './ThreadDetail'

// 定义线程数据类型 - 适配新的数据库结构
interface ThreadInfo {
  id: number
  thread_title: string
  thread_url: string
  thread_uuid: string
  categories: string[] | null
  tags: string[] | null
  avatar_img: string | null
  description: string | null
  create_time: string
  update_time: string
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
  const [selectedThread, setSelectedThread] = useState<ThreadInfo | null>(null)
  const [currentView, setCurrentView] = useState<'list' | 'detail'>('list')
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
    try {
      // 检查是否为 Unix 时间戳（纯数字字符串）
      if (/^\d+$/.test(dateString)) {
        const timestamp = parseInt(dateString)
        // 如果是秒级时间戳（10位数字），转换为毫秒级
        const milliseconds = timestamp.toString().length === 10 ? timestamp * 1000 : timestamp
        return new Date(milliseconds).toLocaleString('zh-CN')
      }
      // 处理标准日期字符串
      return new Date(dateString).toLocaleString('zh-CN')
    } catch {
      return '无效日期'
    }
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

  // 处理线程详情查看（模态框）
  const handleThreadClick = (thread: ThreadInfo) => {
    setSelectedThread(thread)
  }

  // 关闭详情模态框
  const closeModal = () => {
    setSelectedThread(null)
  }

  // 查看线程详情页面
  const viewThreadDetail = (thread: ThreadInfo) => {
    setSelectedThread(thread)
    setCurrentView('detail')
  }

  // 返回到线程列表
  const backToList = () => {
    setCurrentView('list')
    setSelectedThread(null)
  }

  // 如果是详情页面，显示ThreadDetail组件
  if (currentView === 'detail' && selectedThread) {
    return (
      <ThreadDetail
        threadId={selectedThread.id}
        threadTitle={selectedThread.thread_title}
        threadUrl={selectedThread.thread_url}
        onBack={backToList}
      />
    )
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
              <div 
                key={thread.thread_uuid} 
                className="thread-card"
                onClick={() => handleThreadClick(thread)}
              >
                <div className="thread-header">
                  <div className="thread-title-section">
                    {thread.avatar_img && (
                      <img 
                        src={thread.avatar_img} 
                        alt="Thread Avatar" 
                        className="thread-avatar"
                        onError={(e) => {
                          e.currentTarget.style.display = 'none'
                        }}
                      />
                    )}
                    <h3 className="thread-title">{thread.thread_title}</h3>
                  </div>
                  <span className="thread-index">#{(currentPage - 1) * itemsPerPage + index + 1}</span>
                </div>

                {/* Categories 显示 */}
                {thread.categories && thread.categories.length > 0 && (
                  <div className="thread-categories">
                    {thread.categories.map((category, idx) => (
                      <span key={idx} className="category-tag">{category}</span>
                    ))}
                  </div>
                )}

                {/* Description 显示 */}
                {thread.description && (
                  <div className="thread-description">
                    <p>{thread.description}</p>
                  </div>
                )}

                {/* Tags 显示 */}
                {thread.tags && thread.tags.length > 0 && (
                  <div className="thread-tags">
                    <strong>标签: </strong>
                    {thread.tags.slice(0, 5).map((tag, idx) => (
                      <span key={idx} className="tag-item">{tag}</span>
                    ))}
                    {thread.tags.length > 5 && (
                      <span className="more-tags">+{thread.tags.length - 5}个标签</span>
                    )}
                  </div>
                )}
                
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
                      <strong>创建时间:</strong> {formatDate(thread.create_time)}
                    </div>
                    <div className="date-item">
                      <strong>最新回复:</strong> {formatDate(thread.latest_post_timestamp)}
                    </div>
                  </div>
                </div>
                
                <div className="thread-actions">
                  <a 
                    href={thread.thread_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="thread-link"
                    onClick={(e) => e.stopPropagation()}
                  >
                    查看原帖
                  </a>
                  <button 
                    className="view-posts-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      viewThreadDetail(thread)
                    }}
                  >
                    查看帖子
                  </button>
                  <span className="view-details">点击查看详情</span>
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

      {/* 线程详情模态框 */}
      {selectedThread && currentView === 'list' && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{selectedThread.thread_title}</h2>
              <button className="close-btn" onClick={closeModal}>×</button>
            </div>
            
            <div className="modal-body">
              {selectedThread.avatar_img && (
                <div className="modal-avatar">
                  <img src={selectedThread.avatar_img} alt="Thread Avatar" />
                </div>
              )}

              {selectedThread.description && (
                <div className="modal-description">
                  <h4>描述</h4>
                  <p>{selectedThread.description}</p>
                </div>
              )}

              <div className="modal-metadata">
                <div className="metadata-item">
                  <strong>UUID:</strong> {selectedThread.thread_uuid}
                </div>
                <div className="metadata-item">
                  <strong>创建时间:</strong> {formatDate(selectedThread.create_time)}
                </div>
                <div className="metadata-item">
                  <strong>更新时间:</strong> {formatDate(selectedThread.update_time)}
                </div>
                <div className="metadata-item">
                  <strong>帖子数:</strong> {selectedThread.posts_count}
                </div>
                <div className="metadata-item">
                  <strong>参与者数:</strong> {selectedThread.authors_count}
                </div>
              </div>

              {selectedThread.categories && selectedThread.categories.length > 0 && (
                <div className="modal-categories">
                  <h4>分类</h4>
                  <div className="categories-list">
                    {selectedThread.categories.map((category, idx) => (
                      <span key={idx} className="category-tag">{category}</span>
                    ))}
                  </div>
                </div>
              )}

              {selectedThread.tags && selectedThread.tags.length > 0 && (
                <div className="modal-tags">
                  <h4>标签</h4>
                  <div className="tags-list">
                    {selectedThread.tags.map((tag, idx) => (
                      <span key={idx} className="tag-item">{tag}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button 
                className="view-posts-btn"
                onClick={() => {
                  closeModal()
                  viewThreadDetail(selectedThread)
                }}
              >
                查看帖子列表
              </button>
              <a 
                href={selectedThread.thread_url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="visit-thread-btn"
              >
                访问原帖
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
