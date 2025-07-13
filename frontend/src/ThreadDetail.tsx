import { useState, useEffect } from 'react'
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
      const errorMessage = err instanceof Error ? err.message : '未知错误'
      setError(errorMessage)
      message.error(errorMessage)
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
  const handlePageChange = (page: number) => {
    fetchPosts(page)
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
                onClick={onBack}
              >
                返回列表
              </Button>
              <Title level={3} style={{ margin: 0 }} ellipsis={{ tooltip: threadTitle }}>
                {threadTitle}
              </Title>
            </div>
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                loading={loading}
              >
                刷新
              </Button>
              <Button
                type="primary"
                icon={<LinkOutlined />}
                onClick={() => window.open(threadUrl, '_blank')}
              >
                访问原帖
              </Button>
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
                              <Image
                                src={url}
                                alt={`图片 ${index + 1}`}
                                width="100%"
                                height="120px"
                                style={{ objectFit: 'cover' }}
                                fallback="/api/placeholder/120/120"
                              />
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