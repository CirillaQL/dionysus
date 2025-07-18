import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
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
  Col,
  Modal,
  Form,
  Input,
  Switch
} from 'antd'
import { 
  ReloadOutlined,
  EyeOutlined,
  LinkOutlined,
  UserOutlined,
  CalendarOutlined,
  MessageOutlined,
  PlusOutlined,
  SyncOutlined
} from '@ant-design/icons'

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

// 爬取请求接口
interface CrawlerRequest {
  thread_url: string
  thread_title?: string
  enable_reactions: boolean
  save_to_db: boolean
  config_path: string
}

// 主列表页面组件
function ThreadList() {
  const [threads, setThreads] = useState<ThreadInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [crawlerModalVisible, setCrawlerModalVisible] = useState(false)
  const [crawlerLoading, setCrawlerLoading] = useState(false)
  const [crawlerForm] = Form.useForm()
  const [syncModalVisible, setSyncModalVisible] = useState(false)
  const [syncLoading, setSyncLoading] = useState(false)
  const [syncForm] = Form.useForm()
  const [currentSyncThread, setCurrentSyncThread] = useState<ThreadInfo | null>(null)
  const [syncingThreads, setSyncingThreads] = useState<Set<number>>(new Set())
  const navigate = useNavigate()
  
  const itemsPerPage = 20

  // 获取线程列表
  const fetchThreads = async (page: number = 1) => {
    try {
      setLoading(true)
      setError(null)
      
      const offset = (page - 1) * itemsPerPage
      const response = await fetch(`/api/threads/list?limit=${itemsPerPage}&offset=${offset}`)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data: ThreadsResponse = await response.json()
      
      if (data.success) {
        setThreads(data.data)
        setTotalCount(data.total_count)
      } else {
        throw new Error(data.message || '获取数据失败')
      }
    } catch (err) {
      console.error('获取线程列表失败:', err)
      setError(err instanceof Error ? err.message : '获取数据失败')
    } finally {
      setLoading(false)
    }
  }

  // 组件挂载时获取数据
  useEffect(() => {
    fetchThreads(currentPage)
  }, [currentPage])

  // 格式化日期
  const formatDate = (dateString: string | null) => {
    if (!dateString) return '未知'
    
    try {
      const date = new Date(dateString)
      return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    } catch {
      return '未知'
    }
  }

  // 处理页码变化
  const handlePageChange = (page: number) => {
    setCurrentPage(page)
  }

  // 刷新数据
  const handleRefresh = () => {
    fetchThreads(currentPage)
  }

  // 查看线程详情 - 改为路由跳转
  const viewThreadDetail = (thread: ThreadInfo) => {
    navigate(`/simpcity/threads/${thread.id}`)
  }

  // 处理新建爬取
  const handleCreateCrawler = () => {
    setCrawlerModalVisible(true)
    // 设置表单默认值
    crawlerForm.setFieldsValue({
      enable_reactions: true,
      save_to_db: true,
      config_path: 'config.yaml'
    })
  }

  // 提交爬取请求
  const handleCrawlerSubmit = async (values: CrawlerRequest) => {
    try {
      setCrawlerLoading(true)
      
      const response = await fetch('/api/crawler', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(values)
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      
      if (result.success) {
        message.success('爬取任务已启动，正在后台执行')
        setCrawlerModalVisible(false)
        crawlerForm.resetFields()
        // 可以考虑刷新列表
        setTimeout(() => {
          handleRefresh()
        }, 2000)
      } else {
        throw new Error(result.message || '爬取任务启动失败')
      }
    } catch (err) {
      console.error('爬取任务启动失败:', err)
      message.error(err instanceof Error ? err.message : '爬取任务启动失败')
    } finally {
      setCrawlerLoading(false)
    }
  }

  // 取消爬取弹窗
  const handleCrawlerCancel = () => {
    setCrawlerModalVisible(false)
    crawlerForm.resetFields()
  }

  // 处理线程同步 - 修改为显示弹窗
  const handleSync = (thread: ThreadInfo) => {
    setCurrentSyncThread(thread)
    setSyncModalVisible(true)
    // 设置表单默认值
    syncForm.setFieldsValue({
      thread_url: thread.thread_url,
      thread_title: thread.thread_title,
      enable_reactions: true,
      save_to_db: true,
      config_path: 'config.yaml'
    })
  }

  // 提交同步请求
  const handleSyncSubmit = async (values: CrawlerRequest) => {
    if (!currentSyncThread) return

    try {
      setSyncLoading(true)
      // 添加到同步中的线程集合
      setSyncingThreads(prev => new Set([...prev, currentSyncThread.id]))
      
      const response = await fetch('/api/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(values)
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      
      if (result.success) {
        message.success(`线程 "${currentSyncThread.thread_title}" 同步成功`)
        setSyncModalVisible(false)
        syncForm.resetFields()
        setCurrentSyncThread(null)
        // 刷新列表以获取最新数据
        await fetchThreads(currentPage)
      } else {
        throw new Error(result.message || '同步失败')
      }
    } catch (err) {
      console.error('同步失败:', err)
      message.error(err instanceof Error ? err.message : '同步失败')
    } finally {
      setSyncLoading(false)
      // 从同步中的线程集合中移除
      if (currentSyncThread) {
        setSyncingThreads(prev => {
          const newSet = new Set(prev)
          newSet.delete(currentSyncThread.id)
          return newSet
        })
      }
    }
  }

  // 取消同步弹窗
  const handleSyncCancel = () => {
    setSyncModalVisible(false)
    syncForm.resetFields()
    setCurrentSyncThread(null)
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
            <Space>
              <Button 
                type="primary" 
                icon={<PlusOutlined />}
                onClick={handleCreateCrawler}
              >
                新建爬取
              </Button>
              <Button 
                type="default" 
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                loading={loading}
              >
                刷新
              </Button>
            </Space>
          </div>
        </div>
      </div>

      {/* 新建爬取弹窗 */}
      <Modal
        title="新建爬取任务"
        open={crawlerModalVisible}
        onOk={crawlerForm.submit}
        onCancel={handleCrawlerCancel}
        confirmLoading={crawlerLoading}
        width={600}
        okText="开始爬取"
        cancelText="取消"
      >
        <Form
          form={crawlerForm}
          layout="vertical"
          onFinish={handleCrawlerSubmit}
        >
          <Form.Item
            label="帖子URL"
            name="thread_url"
            rules={[
              { required: true, message: '请输入帖子URL' },
              { type: 'url', message: '请输入有效的URL' }
            ]}
          >
            <Input 
              placeholder="请输入帖子的完整URL，例如：https://simpcity.su/threads/xxx"
              size="large"
            />
          </Form.Item>

          <Form.Item
            label="帖子标题"
            name="thread_title"
            help="可选，如果不填写将自动从页面获取"
          >
            <Input 
              placeholder="请输入帖子标题（可选）"
              size="large"
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="启用reactions抓取"
                name="enable_reactions"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="保存到数据库"
                name="save_to_db"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="配置文件路径"
            name="config_path"
            help="配置文件的路径，包含cookies和其他配置信息"
          >
            <Input 
              placeholder="config.yaml"
              size="large"
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 同步线程弹窗 */}
      <Modal
        title={`同步线程 - ${currentSyncThread?.thread_title || ''}`}
        open={syncModalVisible}
        onOk={syncForm.submit}
        onCancel={handleSyncCancel}
        confirmLoading={syncLoading}
        width={600}
        okText="开始同步"
        cancelText="取消"
      >
        <Form
          form={syncForm}
          layout="vertical"
          onFinish={handleSyncSubmit}
        >
          <Form.Item
            label="帖子URL"
            name="thread_url"
            rules={[
              { required: true, message: '请输入帖子URL' },
              { type: 'url', message: '请输入有效的URL' }
            ]}
          >
            <Input 
              placeholder="请输入帖子的完整URL，例如：https://simpcity.su/threads/xxx"
              size="large"
              disabled
            />
          </Form.Item>

          <Form.Item
            label="帖子标题"
            name="thread_title"
            help="将同步此线程的最新内容"
          >
            <Input 
              placeholder="帖子标题"
              size="large"
              disabled
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="启用reactions抓取"
                name="enable_reactions"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="保存到数据库"
                name="save_to_db"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="配置文件路径"
            name="config_path"
            help="配置文件的路径，包含cookies和其他配置信息"
          >
            <Input 
              placeholder="config.yaml"
              size="large"
            />
          </Form.Item>
        </Form>
      </Modal>

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
                      </Tooltip>,
                      <Tooltip title="同步线程">
                        <SyncOutlined 
                          key="sync" 
                          onClick={() => handleSync(thread)}
                          spin={syncingThreads.has(thread.id)}
                          style={{ 
                            color: syncingThreads.has(thread.id) ? '#1677ff' : undefined 
                          }}
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

export default ThreadList 