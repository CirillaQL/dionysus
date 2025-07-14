import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  Card, 
  Button, 
  Tag, 
  Avatar, 
  Spin,
  Pagination,
  message,
  Empty,
  Image,
  Divider,
  Space,
  Typography,
  Row,
  Col
} from 'antd'
import { 
  ArrowLeftOutlined,
  ReloadOutlined,
  LinkOutlined,
  UserOutlined,
  CalendarOutlined,
  HeartOutlined
} from '@ant-design/icons'

const { Title, Text, Paragraph } = Typography

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

// 定义线程信息类型
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

interface ThreadResponse {
  success: boolean
  message: string
  data: ThreadInfo
}

function ThreadDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  
  const [threadInfo, setThreadInfo] = useState<ThreadInfo | null>(null)
  const [posts, setPosts] = useState<PostInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [threadLoading, setThreadLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const itemsPerPage = 10

  // 获取线程信息
  const fetchThreadInfo = async (threadId: string) => {
    try {
      setThreadLoading(true)
      const response = await fetch(`/api/threads/id/${threadId}`)
      
      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`)
      }
      
      const data: ThreadResponse = await response.json()
      
      if (data.success) {
        setThreadInfo(data.data)
      } else {
        throw new Error(data.message || '获取线程信息失败')
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '未知错误'
      setError(errorMessage)
      message.error(errorMessage)
    } finally {
      setThreadLoading(false)
    }
  }

  // 获取帖子列表
  const fetchPosts = async (page: number = 1) => {
    if (!id) return
    
    try {
      setLoading(true)
      setError(null)
      
      const offset = (page - 1) * itemsPerPage
      const response = await fetch(`/api/threads/id/${id}/posts?limit=${itemsPerPage}&offset=${offset}`)
      
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
      const errorMessage = err instanceof Error ? err.message : '未知错误'
      setError(errorMessage)
      message.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  // 组件加载时获取数据
  useEffect(() => {
    if (id) {
      fetchThreadInfo(id)
      fetchPosts(1)
    }
  }, [id])

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
  const handlePageChange = (page: number) => {
    fetchPosts(page)
  }

  // 刷新数据
  const handleRefresh = () => {
    if (id) {
      fetchThreadInfo(id)
      fetchPosts(currentPage)
    }
  }

  // 返回列表
  const handleBack = () => {
    navigate('/')
  }

  // 渲染帖子内容
  const renderPostContent = (post: PostInfo) => {
    if (post.content_html) {
      return (
        <div 
          style={{ 
            maxWidth: '100%', 
            wordBreak: 'break-word',
            lineHeight: '1.6'
          }}
          dangerouslySetInnerHTML={{ __html: post.content_html }}
        />
      )
    } else if (post.content_text) {
      return (
        <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
          {post.content_text}
        </Paragraph>
      )
    }
    return (
      <Text type="secondary" italic>
        无内容
      </Text>
    )
  }

  // 如果没有ID参数，显示错误
  if (!id) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <Empty description="无效的线程ID" />
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f5f5f5' }}>
      {/* 头部 */}
      <div style={{ 
        backgroundColor: '#fff', 
        borderBottom: '1px solid #e8e8e8',
        position: 'sticky',
        top: 0,
        zIndex: 1000
      }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            padding: '16px 0' 
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <Button
                icon={<ArrowLeftOutlined />}
                onClick={handleBack}
              >
                返回列表
              </Button>
              {threadLoading ? (
                <Spin size="small" />
              ) : (
                <Title level={3} style={{ margin: 0 }} ellipsis={{ tooltip: threadInfo?.thread_title }}>
                  {threadInfo?.thread_title || '加载中...'}
                </Title>
              )}
            </div>
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                loading={loading || threadLoading}
              >
                刷新
              </Button>
              {threadInfo && (
                <Button
                  type="primary"
                  icon={<LinkOutlined />}
                  onClick={() => window.open(threadInfo.thread_url, '_blank')}
                >
                  访问原帖
                </Button>
              )}
            </Space>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
        {/* 统计信息 */}
        {!loading && !error && (
          <div style={{ marginBottom: '24px' }}>
            <Text type="secondary">共 {totalCount} 个帖子</Text>
          </div>
        )}

        {/* 加载状态 */}
        {loading && (
          <div style={{ textAlign: 'center', padding: '80px 0' }}>
            <Spin size="large" tip="加载中..." />
          </div>
        )}

        {/* 错误状态 */}
        {error && !loading && (
          <Empty 
            description={`错误: ${error}`}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button type="primary" onClick={handleRefresh}>
              重试
            </Button>
          </Empty>
        )}

        {/* 帖子列表 */}
        {!loading && !error && posts.length > 0 && (
          <div style={{ marginBottom: '24px' }}>
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              {posts.map((post) => (
                <Card key={post.uuid} style={{ width: '100%' }}>
                  {/* 帖子头部 */}
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    marginBottom: '16px' 
                  }}>
                    <Space>
                      <Avatar
                        size="large"
                        icon={<UserOutlined />}
                      />
                      <div>
                        {post.author_profile_url ? (
                          <a
                            href={post.author_profile_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: '#1677ff', fontWeight: 'bold' }}
                          >
                            {post.author_name || '匿名用户'}
                          </a>
                        ) : (
                          <Text strong>{post.author_name || '匿名用户'}</Text>
                        )}
                        <div>
                          <Space>
                            <Text type="secondary" style={{ fontSize: '12px' }}>
                              <CalendarOutlined /> {formatDate(post.post_timestamp)}
                            </Text>
                            {post.floor && (
                              <Tag color="blue">#{post.floor}</Tag>
                            )}
                          </Space>
                        </div>
                      </div>
                    </Space>
                    
                    {post.reactions && post.reactions > 0 && (
                      <Space>
                        <HeartOutlined style={{ color: '#ff4d4f' }} />
                        <Text type="secondary">{post.reactions}</Text>
                      </Space>
                    )}
                  </div>

                  <Divider />

                  {/* 帖子内容 */}
                  <div style={{ marginBottom: '16px' }}>
                    {renderPostContent(post)}
                  </div>

                  {/* 图片展示 */}
                  {post.image_urls && post.image_urls.length > 0 && (
                    <div style={{ marginBottom: '16px' }}>
                      <Image.PreviewGroup>
                        <Row gutter={[8, 8]}>
                          {post.image_urls.map((url, index) => (
                            <Col xs={12} sm={8} md={6} key={index}>
                              <div style={{ 
                                border: '1px solid #e8e8e8',
                                borderRadius: '6px',
                                overflow: 'hidden',
                                height: '120px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                backgroundColor: '#f9f9f9'
                              }}>
                                <Image
                                  src={url}
                                  alt={`图片 ${index + 1}`}
                                  style={{ 
                                    maxWidth: '100%',
                                    maxHeight: '100%',
                                    objectFit: 'contain'
                                  }}
                                />
                              </div>
                            </Col>
                          ))}
                        </Row>
                      </Image.PreviewGroup>
                    </div>
                  )}

                  {/* 外部链接 */}
                  {post.external_links && post.external_links.length > 0 && (
                    <div style={{ marginBottom: '8px' }}>
                      <Text type="secondary">外部链接：</Text>
                      <Space wrap>
                        {post.external_links.map((link, index) => (
                          <Tag 
                            key={index} 
                            color="cyan" 
                            style={{ cursor: 'pointer' }}
                            onClick={() => window.open(link, '_blank')}
                          >
                            <LinkOutlined /> 链接 {index + 1}
                          </Tag>
                        ))}
                      </Space>
                    </div>
                  )}
                </Card>
              ))}
            </Space>
          </div>
        )}

        {/* 空状态 */}
        {!loading && !error && posts.length === 0 && (
          <Empty description="暂无帖子数据" />
        )}

        {/* 分页 */}
        {!loading && !error && totalCount > itemsPerPage && (
          <div style={{ textAlign: 'center', marginTop: '24px' }}>
            <Pagination
              current={currentPage}
              total={totalCount}
              pageSize={itemsPerPage}
              onChange={handlePageChange}
              showSizeChanger={false}
              showQuickJumper
              showTotal={(total, range) => 
                `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
              }
            />
          </div>
        )}
      </div>
    </div>
  )
}

export default ThreadDetail 