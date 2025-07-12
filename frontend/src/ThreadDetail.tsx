import { useState, useEffect } from 'react'
import './ThreadDetail.css'

// 定义帖子数据类型
interface PostInfo {
  id: number
  uuid: string
  thread_uuid: string
  post_id: string | null
  author_name: string | null
  author_id: string | null
  author_profile_url: string | null
  post_timestamp: number | null
  content_text: string | null
  content_html: string | null
  image_urls: string[]
  external_links: string[]
  iframe_urls: string[]
  floor: number | null
  reactions: number | null
  create_time: string
  update_time: string
}

interface PostsResponse {
  success: boolean
  message: string
  data: PostInfo[]
  total_count: number
}

interface ThreadDetailProps {
  threadId: number
  threadTitle: string
  threadUrl: string
  onBack: () => void
}

function ThreadDetail({ threadId, threadTitle, threadUrl, onBack }: ThreadDetailProps) {
  const [posts, setPosts] = useState<PostInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const itemsPerPage = 10

  // 获取帖子列表
  const fetchPosts = async (page: number = 1) => {
    try {
      setLoading(true)
      setError(null)
      
      const offset = (page - 1) * itemsPerPage
      const response = await fetch(`/api/threads/id/${threadId}/posts?limit=${itemsPerPage}&offset=${offset}`)
      
      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`)
      }
      
      const data: PostsResponse = await response.json()
      
      if (data.success) {
        setPosts(data.data)
        setTotalCount(data.total_count)
        setCurrentPage(page)
      } else {
        throw new Error(data.message || '获取帖子列表失败')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }

  // 组件加载时获取数据
  useEffect(() => {
    fetchPosts(1)
  }, [threadId])

  // 格式化时间
  const formatDate = (timestamp: number | null) => {
    if (!timestamp) return '无'
    try {
      return new Date(timestamp * 1000).toLocaleString('zh-CN')
    } catch {
      return '无效日期'
    }
  }

  // 处理分页
  const totalPages = Math.ceil(totalCount / itemsPerPage)
  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      fetchPosts(page)
    }
  }

  // 刷新数据
  const handleRefresh = () => {
    fetchPosts(currentPage)
  }

  // 渲染帖子内容
  const renderPostContent = (post: PostInfo) => {
    if (post.content_html) {
      return (
        <div 
          className="post-content-html"
          dangerouslySetInnerHTML={{ __html: post.content_html }}
        />
      )
    } else if (post.content_text) {
      return (
        <div className="post-content-text">
          {post.content_text.split('\n').map((line, idx) => (
            <p key={idx}>{line}</p>
          ))}
        </div>
      )
    }
    return <div className="post-content-empty">无内容</div>
  }

  return (
    <div className="thread-detail">
      <header className="thread-detail-header">
        <button onClick={onBack} className="back-btn">
          ← 返回列表
        </button>
        <div className="thread-detail-title">
          <h1>{threadTitle}</h1>
          <div className="thread-detail-actions">
            <button onClick={handleRefresh} disabled={loading} className="refresh-btn">
              {loading ? '刷新中...' : '刷新'}
            </button>
            <a href={threadUrl} target="_blank" rel="noopener noreferrer" className="visit-original">
              访问原帖
            </a>
          </div>
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
          <div className="posts-stats">
            <p>共 {totalCount} 个帖子</p>
          </div>

          <div className="posts-list">
            {posts.map((post) => (
              <div key={post.uuid} className="post-card">
                <div className="post-header">
                  <div className="post-author">
                    {post.author_profile_url ? (
                      <a href={post.author_profile_url} target="_blank" rel="noopener noreferrer">
                        {post.author_name || '匿名用户'}
                      </a>
                    ) : (
                      <span>{post.author_name || '匿名用户'}</span>
                    )}
                  </div>
                  <div className="post-meta">
                    <span className="post-floor">#{post.floor}</span>
                    <span className="post-time">{formatDate(post.post_timestamp)}</span>
                    {post.reactions && post.reactions > 0 && (
                      <span className="post-reactions">👍 {post.reactions}</span>
                    )}
                  </div>
                </div>

                <div className="post-content">
                  {renderPostContent(post)}
                </div>

                {/* 显示图片 */}
                {post.image_urls && post.image_urls.length > 0 && (
                  <div className="post-images">
                    {post.image_urls.map((url, idx) => (
                      <div key={idx} className="post-image">
                        <img 
                          src={url} 
                          alt={`图片 ${idx + 1}`}
                          loading="lazy"
                          onError={(e) => {
                            e.currentTarget.style.display = 'none'
                          }}
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* 显示外部链接 */}
                {post.external_links && post.external_links.length > 0 && (
                  <div className="post-links">
                    <h5>外部链接:</h5>
                    {post.external_links.map((link, idx) => (
                      <a key={idx} href={link} target="_blank" rel="noopener noreferrer" className="external-link">
                        {link}
                      </a>
                    ))}
                  </div>
                )}

                {/* 显示视频/嵌入内容 */}
                {post.iframe_urls && post.iframe_urls.length > 0 && (
                  <div className="post-embeds">
                    <h5>嵌入内容:</h5>
                    {post.iframe_urls.map((url, idx) => (
                      <div key={idx} className="embed-container">
                        <iframe 
                          src={url} 
                          title={`嵌入内容 ${idx + 1}`}
                          loading="lazy"
                          sandbox="allow-scripts allow-same-origin"
                        />
                      </div>
                    ))}
                  </div>
                )}

                <div className="post-footer">
                  <small>UUID: {post.uuid}</small>
                  {post.post_id && (
                    <small>Post ID: {post.post_id}</small>
                  )}
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

export default ThreadDetail 