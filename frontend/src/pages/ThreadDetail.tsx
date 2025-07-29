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
  Col,
  Modal,
  List
} from 'antd'
import { 
  ArrowLeftOutlined,
  ReloadOutlined,
  LinkOutlined,
  UserOutlined,
  CalendarOutlined,
  HeartOutlined,
  DownloadOutlined,
  CloudDownloadOutlined
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

// 下载响应类型
interface DownloadResponse {
  success: boolean
  message: string
  post_id: string
  thread_url: string
  bunkr_links_found: number
  download_results: Array<{
    url: string
    result: {
      success: boolean
      error?: string
      files_downloaded?: number
      downloaded_files?: string[]
    }
  }>
  errors: string[]
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

  // 下载相关状态
  const [downloadingPosts, setDownloadingPosts] = useState<Set<string>>(new Set())
  const [showDownloadModal, setShowDownloadModal] = useState(false)
  const [downloadResults, setDownloadResults] = useState<DownloadResponse | null>(null)

  // 检查是否为bunkr链接
  const isBunkrLink = (url: string): boolean => {
    return /bunkr\.\w+/.test(url)
  }

  // 获取bunkr链接数量
  const getBunkrLinksCount = (externalLinks: string[]): number => {
    return externalLinks.filter(isBunkrLink).length
  }

  // 下载帖子的bunkr链接
  const downloadPostBunkrLinks = async (post: PostInfo, useSync: boolean = false) => {
    if (!post.post_id || !threadInfo?.thread_url) {
      message.error('帖子信息不完整，无法下载')
      return
    }

    const bunkrCount = getBunkrLinksCount(post.external_links)
    if (bunkrCount === 0) {
      message.info('该帖子没有bunkr链接可供下载')
      return
    }

    const postId = post.post_id
    setDownloadingPosts(prev => new Set(prev).add(postId))

    try {
      const endpoint = useSync ? '/api/threads/download-sync' : '/api/threads/download'
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          thread_url: threadInfo.thread_url,
          post_id: postId,
          download_dir: 'downloads'
        }),
      })

      if (!response.ok) {
        throw new Error(`下载请求失败: ${response.status}`)
      }

      const result: DownloadResponse = await response.json()

      if (result.success) {
        if (useSync) {
          // 同步下载，显示详细结果
          setDownloadResults(result)
          setShowDownloadModal(true)
          const successCount = result.download_results.filter(r => r.result.success).length
          message.success(`下载完成！成功: ${successCount}/${result.bunkr_links_found}`)
        } else {
          // 异步下载，只显示启动消息
          message.success(`找到 ${result.bunkr_links_found} 个bunkr链接，下载已在后台启动`)
        }
      } else {
        throw new Error(result.message || '下载失败')
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '下载失败'
      message.error(errorMessage)
      console.error('下载错误:', err)
    } finally {
      setDownloadingPosts(prev => {
        const newSet = new Set(prev)
        newSet.delete(postId)
        return newSet
      })
    }
  }

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
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center', 
                        marginBottom: '8px' 
                      }}>
                        <Text type="secondary">
                          外部链接：
                          {getBunkrLinksCount(post.external_links) > 0 && (
                            <Tag color="green" style={{ marginLeft: '8px' }}>
                              {getBunkrLinksCount(post.external_links)} 个bunkr链接
                            </Tag>
                          )}
                        </Text>
                        {/* 下载按钮 */}
                        {post.post_id && getBunkrLinksCount(post.external_links) > 0 && (
                          <Space>
                            <Button
                              type="primary"
                              size="small"
                              icon={<CloudDownloadOutlined />}
                              onClick={() => downloadPostBunkrLinks(post, false)}
                              loading={downloadingPosts.has(post.post_id)}
                            >
                              后台下载
                            </Button>
                            <Button
                              size="small"
                              icon={<DownloadOutlined />}
                              onClick={() => downloadPostBunkrLinks(post, true)}
                              loading={downloadingPosts.has(post.post_id)}
                            >
                              同步下载
                            </Button>
                          </Space>
                        )}
                      </div>
                      <Space wrap>
                        {post.external_links.map((link, index) => (
                          <Tag 
                            key={index} 
                            color={isBunkrLink(link) ? "orange" : "cyan"}
                            style={{ cursor: 'pointer' }}
                            onClick={() => window.open(link, '_blank')}
                          >
                            <LinkOutlined /> 
                            {isBunkrLink(link) ? `Bunkr ${index + 1}` : `链接 ${index + 1}`}
                          </Tag>
                        ))}
                      </Space>
                    </div>
                  )}

                  {/* 下载按钮 - 当没有外部链接时的备用位置 */}
                  {post.post_id && (!post.external_links || post.external_links.length === 0) && (
                    <div style={{ marginTop: '16px', textAlign: 'center' }}>
                      <Text type="secondary">该帖子没有外部链接可供下载</Text>
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

      {/* 下载结果模态框 */}
      <Modal
        title="下载结果"
        open={showDownloadModal}
        onCancel={() => setShowDownloadModal(false)}
        footer={[
          <Button key="close" onClick={() => setShowDownloadModal(false)}>
            关闭
          </Button>,
        ]}
      >
        {downloadResults && (
          <List
            dataSource={downloadResults.download_results}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={item.url}
                  description={
                                         item.result.success ? (
                       <>
                         成功下载 {item.result.files_downloaded || 0} 个文件
                         {item.result.downloaded_files && item.result.downloaded_files.length > 0 && (
                           <span>（下载文件: {item.result.downloaded_files.join(', ')}）</span>
                         )}
                       </>
                     ) : (
                       <>
                         失败: {item.result.error || '未知错误'}
                         {item.result.files_downloaded && item.result.files_downloaded > 0 && (
                           <span>（已下载 {item.result.files_downloaded} 个文件）</span>
                         )}
                       </>
                     )
                  }
                />
              </List.Item>
            )}
          />
        )}
        {downloadResults && downloadResults.errors && downloadResults.errors.length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <Text type="danger">下载失败链接：</Text>
            <Space wrap>
              {downloadResults.errors.map((error, index) => (
                <Tag key={index} color="red">
                  {error}
                </Tag>
              ))}
            </Space>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default ThreadDetail 