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
  Tooltip,
  Space,
  Typography,
  Divider,
  Row,
  Col
} from 'antd'
import { 
  ReloadOutlined,
  EyeOutlined,
  LinkOutlined,
  UserOutlined,
  CalendarOutlined,
  MessageOutlined
} from '@ant-design/icons'
import ThreadDetail from './ThreadDetail'

const { Title, Text } = Typography

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
      const errorMessage = err instanceof Error ? err.message : '未知错误'
      setError(errorMessage)
      message.error(errorMessage)
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
      if (/^\d+$/.test(dateString)) {
        const timestamp = parseInt(dateString)
        const milliseconds = timestamp.toString().length === 10 ? timestamp * 1000 : timestamp
        return new Date(milliseconds).toLocaleString('zh-CN')
      }
      return new Date(dateString).toLocaleString('zh-CN')
    } catch {
      return '无效日期'
    }
  }

  // 处理分页
  const handlePageChange = (page: number) => {
    fetchThreads(page)
  }

  // 刷新数据
  const handleRefresh = () => {
    fetchThreads(currentPage)
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
            <Title level={2} style={{ margin: 0, color: '#1677ff' }}>
              SimpCity 帖子列表
            </Title>
            <Button 
              type="primary" 
              icon={<ReloadOutlined />}
              onClick={handleRefresh}
              loading={loading}
            >
              刷新
            </Button>
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

        {/* 线程列表 */}
        {!loading && !error && threads.length > 0 && (
          <div style={{ marginBottom: '24px' }}>
            <Row gutter={[16, 16]}>
              {threads.map((thread) => (
                <Col xs={24} sm={12} lg={8} key={thread.id}>
                  <Card
                    hoverable
                    actions={[
                      <Tooltip title="查看详情">
                        <EyeOutlined 
                          key="detail" 
                          onClick={() => viewThreadDetail(thread)}
                        />
                      </Tooltip>,
                      <Tooltip title="访问原帖">
                        <LinkOutlined 
                          key="link" 
                          onClick={() => window.open(thread.thread_url, '_blank')}
                        />
                      </Tooltip>
                    ]}
                  >
                    <div style={{ textAlign: 'center', marginBottom: '16px' }}>
                      <Avatar 
                        src={thread.avatar_img} 
                        icon={<UserOutlined />}
                        size={80}
                        style={{ marginBottom: '12px' }}
                      />
                      <div>
                        <Text 
                          ellipsis={{ tooltip: thread.thread_title }}
                          style={{ fontSize: '16px', fontWeight: 'bold', display: 'block' }}
                        >
                          {thread.thread_title}
                        </Text>
                      </div>
                    </div>
                    
                    {/* 分类标签 */}
                    {thread.categories && thread.categories.length > 0 && (
                      <div style={{ marginBottom: '8px', textAlign: 'center' }}>
                        {thread.categories.map((category, index) => (
                          <Tag key={index} color="blue" style={{ marginBottom: '4px' }}>
                            {category}
                          </Tag>
                        ))}
                      </div>
                    )}
                    
                    {/* 标签 */}
                    {thread.tags && thread.tags.length > 0 && (
                      <div style={{ marginBottom: '16px', textAlign: 'center' }}>
                        {thread.tags.map((tag, index) => (
                          <Tag key={index} color="green" style={{ marginBottom: '4px' }}>
                            {tag}
                          </Tag>
                        ))}
                      </div>
                    )}
                    
                    <Divider />
                    
                    {/* 统计信息 */}
                    <Space split={<Divider type="vertical" />} style={{ width: '100%', justifyContent: 'center' }}>
                      <Space>
                        <MessageOutlined style={{ color: '#1677ff' }} />
                        <Text type="secondary">{thread.posts_count}</Text>
                      </Space>
                      <Space>
                        <CalendarOutlined style={{ color: '#faad14' }} />
                        <Text type="secondary">
                          {formatDate(thread.latest_post_timestamp)}
                        </Text>
                      </Space>
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>
          </div>
        )}

        {/* 空状态 */}
        {!loading && !error && threads.length === 0 && (
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

export default App
