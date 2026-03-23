import { useEffect, useMemo, useRef, useState } from 'react';
import { Avatar, Button, Card, Drawer, Empty, FloatButton, Popconfirm, Space, Spin, Tag, Typography, message } from 'antd';
import { Sender } from '@ant-design/x';
import { XMarkdown } from '@ant-design/x-markdown';
import {
  CustomerServiceOutlined,
  DeleteOutlined,
  HomeOutlined,
  MessageOutlined,
  OrderedListOutlined,
  ShoppingCartOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import useCartStore from '@/store/useCartStore';
import { del, fetchSSE, get } from '@/utils/request';
import { formatAmount, orderStatusMap, saleStatusMap } from '@/utils/dataformat';
import '@ant-design/x-markdown/dist/x-markdown.css';

const { Paragraph, Text, Title } = Typography;

type AssistantCard = ProductAssistantCard | OrderAssistantCard | AddressAssistantCard | AccountAssistantCard | InfoAssistantCard;

interface ProductAssistantCard {
  type: 'product';
  id: number;
  name: string;
  price: number;
  stock: number;
  status: 'on_sale' | 'off_sale';
  image_url?: string | null;
  description?: string;
  category_name?: string | null;
  route?: string;
  reason?: string | null;
  similarity?: number;
}

interface OrderAssistantCard {
  type: 'order';
  id: number;
  order_no: string;
  status: string;
  total_amount: number;
  created_at: string;
  receiver_name?: string | null;
  phone?: string | null;
  address?: string | null;
  route?: string;
  reason?: string | null;
  items: Array<{
    product_id: number;
    product_name: string;
    category_name?: string | null;
    buy_price: number;
    quantity: number;
    route?: string;
  }>;
}

interface AddressAssistantCard {
  type: 'address';
  id: number;
  receiver_name: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  detail_address: string;
  full_address: string;
  is_default: boolean;
  reason?: string | null;
}

interface AccountAssistantCard {
  type: 'account';
  id: number;
  username: string;
  email: string;
  role: string;
  created_at: string;
  reason?: string | null;
}

interface InfoAssistantCard {
  type: 'info';
  title: string;
  description?: string;
}

interface ChatHistoryMessage {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  ui_type?: string | null;
  payload?: string | null;
  created_at: string;
}

interface ChatHistoryResponse {
  total: number;
  messages: ChatHistoryMessage[];
}

interface ChatUiMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  cards: AssistantCard[];
  createdAt: string;
  streaming?: boolean;
  cardsVisible: boolean;
}

function isRenderableRole(role: ChatHistoryMessage['role']): role is 'user' | 'assistant' {
  return role === 'user' || role === 'assistant';
}

const statusColorMap: Record<string, string> = {
  pending: 'orange',
  paid: 'blue',
  shipped: 'cyan',
  completed: 'green',
  cancelled: 'default',
};

function normalizeAssistantCards(rawPayload: unknown): AssistantCard[] {
  if (!Array.isArray(rawPayload)) {
    return [];
  }

  return rawPayload.reduce<AssistantCard[]>((cards, item) => {
    if (!item || typeof item !== 'object') {
      return cards;
    }

    const record = item as Record<string, unknown>;
    if (record.type === 'product') {
      cards.push(record as unknown as ProductAssistantCard);
      return cards;
    }
    if (record.type === 'order') {
      cards.push(record as unknown as OrderAssistantCard);
      return cards;
    }
    if (record.type === 'address') {
      cards.push(record as unknown as AddressAssistantCard);
      return cards;
    }
    if (record.type === 'account') {
      cards.push(record as unknown as AccountAssistantCard);
      return cards;
    }
    if (record.type === 'info') {
      cards.push(record as unknown as InfoAssistantCard);
      return cards;
    }

    // 兼容历史 product_cards 结构：只有 id/name/price/image_url。
    if (typeof record.id === 'number' && typeof record.name === 'string') {
      cards.push({
        type: 'product',
        id: record.id,
        name: record.name,
        price: Number(record.price ?? 0),
        stock: Number(record.stock ?? 0),
        status: record.status === 'off_sale' ? 'off_sale' : 'on_sale',
        image_url: typeof record.image_url === 'string' ? record.image_url : null,
        description: typeof record.description === 'string' ? record.description : '',
        category_name: typeof record.category_name === 'string' ? record.category_name : null,
        route: typeof record.route === 'string' ? record.route : `/product/${record.id}`,
        reason: typeof record.reason === 'string' ? record.reason : null,
        similarity: typeof record.similarity === 'number' ? record.similarity : undefined,
      } satisfies ProductAssistantCard);
    }

    return cards;
  }, []);
}

function parseAssistantCards(payload?: string | null): AssistantCard[] {
  if (!payload) {
    return [];
  }

  try {
    return normalizeAssistantCards(JSON.parse(payload));
  } catch {
    return [];
  }
}

function buildPageLabel(pageType?: string): string {
  switch (pageType) {
    case 'product':
      return '商品详情页';
    case 'orders':
      return '订单列表页';
    case 'order_detail':
      return '订单详情页';
    case 'addresses':
      return '地址管理页';
    case 'account':
      return '账号页';
    case 'cart':
      return '购物车页';
    case 'checkout':
      return '结算页';
    default:
      return '商城首页';
  }
}

const ClientAiAssistant = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { items: cartItems, addItem } = useCartStore();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [sending, setSending] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [messages, setMessages] = useState<ChatUiMessage[]>([]);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const routeContext = useMemo(() => {
    // 只把“当前页面是谁”与“当前购物车概览”传给后端，
    // 具体订单/地址/账号数据由后端按当前登录用户二次查询，避免前端拼接敏感信息。
    const context: Record<string, unknown> = {
      page_path: location.pathname,
      page_type: 'home',
    };

    if (/^\/product\/\d+$/.test(location.pathname)) {
      context.page_type = 'product';
      context.current_product_id = Number(location.pathname.split('/')[2]);
    } else if (location.pathname === '/orders') {
      context.page_type = 'orders';
    } else if (/^\/orders\/\d+$/.test(location.pathname)) {
      context.page_type = 'order_detail';
      context.current_order_id = Number(location.pathname.split('/')[2]);
    } else if (location.pathname === '/addresses') {
      context.page_type = 'addresses';
    } else if (location.pathname === '/account') {
      context.page_type = 'account';
    } else if (location.pathname === '/cart') {
      context.page_type = 'cart';
    } else if (location.pathname === '/checkout') {
      context.page_type = 'checkout';
    }

    if (cartItems.length > 0) {
      context.cart_snapshot = cartItems.slice(0, 5).map(item => ({
        product_id: item.productId,
        name: item.name,
        price: item.price,
        quantity: item.quantity,
      }));
    }

    return context;
  }, [cartItems, location.pathname]);

  const promptSuggestions = useMemo(() => {
    const pageType = String(routeContext.page_type ?? 'home');
    if (pageType === 'product') {
      return ['这件商品怎么样？', '这件商品适合什么人？', '有没有类似推荐？'];
    }
    if (pageType === 'order_detail') {
      return ['这个订单现在到哪一步了？', '这个订单的收货信息是什么？', '我还能做什么操作？'];
    }
    if (pageType === 'addresses') {
      return ['我的默认地址是什么？', '帮我确认常用收货地址', '我现在有几个地址？'];
    }
    if (pageType === 'account') {
      return ['帮我看看我的账号信息', '我的邮箱是什么？', '我当前是什么角色？'];
    }
    return ['帮我推荐几款商品', '我最近的订单怎么样了？', '帮我看看默认地址'];
  }, [routeContext.page_type]);

  const fetchHistory = async () => {
    setLoadingHistory(true);
    try {
      const data = await get<ChatHistoryResponse>('/ai/history', {
        params: { limit: 50 },
      });
      const historyMessages = data.messages
        .filter(item => isRenderableRole(item.role))
        .map<ChatUiMessage>(item => {
          const cards = parseAssistantCards(item.payload);
          return {
            id: `history-${item.id}`,
            role: item.role as 'user' | 'assistant',
            content: item.content,
            cards,
            createdAt: item.created_at,
            streaming: false,
            cardsVisible: cards.length > 0,
          };
        });
      setMessages(prev => (prev.length > 0 ? [...historyMessages, ...prev] : historyMessages));
      setHistoryLoaded(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'AI 历史记录加载失败');
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (!drawerOpen || historyLoaded) {
      return;
    }
    void fetchHistory();
  }, [drawerOpen, historyLoaded]);

  useEffect(() => {
    if (!drawerOpen) {
      return;
    }
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' });
  }, [drawerOpen, messages]);

  const updateAssistantMessage = (id: string, updater: (current: ChatUiMessage) => ChatUiMessage) => {
    setMessages(prev =>
      prev.map(item => {
        if (item.id !== id) {
          return item;
        }
        return updater(item);
      })
    );
  };

  const handleSendMessage = async (preset?: string) => {
    const content = (preset ?? inputValue).trim();
    if (!content || sending) {
      return;
    }

    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `assistant-${Date.now()}`;
    const createdAt = new Date().toISOString();

    setDrawerOpen(true);
    setMessages(prev => [
      ...prev,
      { id: userMessageId, role: 'user', content, cards: [], createdAt, cardsVisible: false },
      { id: assistantMessageId, role: 'assistant', content: '', cards: [], createdAt, streaming: true, cardsVisible: false },
    ]);
    setInputValue('');
    setSending(true);

    try {
      await fetchSSE({
        url: '/ai/chat/stream',
        body: {
          content,
          context: routeContext,
        },
        getController: controller => {
          controllerRef.current = controller;
        },
        onMessage: raw => {
          // SSE 同时承载两类事件：
          // 1. type=cards：结构化卡片
          // 2. type=delta：流式文本增量
          let parsed: Record<string, unknown> | null = null;
          try {
            parsed = JSON.parse(raw) as Record<string, unknown>;
          } catch {
            parsed = { type: 'delta', content: raw };
          }

          if (parsed.type === 'cards') {
            const cards = normalizeAssistantCards(parsed.cards);
            updateAssistantMessage(assistantMessageId, current => ({
              ...current,
              cards,
              // 前端直接遵循后端 SSE 事件顺序展示：
              // 后端会先输出文本，再输出对应卡片，这里收到卡片事件就立即展示。
              cardsVisible: true,
            }));
            return;
          }

          const chunk = typeof parsed.content === 'string' ? parsed.content : '';
          if (!chunk) {
            return;
          }

          updateAssistantMessage(assistantMessageId, current => ({
            ...current,
            content: `${current.content}${chunk}`,
          }));
        },
        onDone: () => {
          updateAssistantMessage(assistantMessageId, current => ({
            ...current,
            streaming: false,
            cardsVisible: current.cardsVisible,
          }));
        },
        onAbort: () => {
          updateAssistantMessage(assistantMessageId, current => ({
            ...current,
            streaming: false,
            content: current.content || '本次回答已停止生成。',
            cardsVisible: current.cardsVisible,
          }));
        },
        onError: error => {
          updateAssistantMessage(assistantMessageId, current => ({
            ...current,
            streaming: false,
            content: current.content || `生成失败：${error.message}`,
            cardsVisible: current.cardsVisible,
          }));
          message.error(error.message);
        },
      });
    } finally {
      controllerRef.current = null;
      setSending(false);
    }
  };

  const handleStopStreaming = () => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setSending(false);
  };

  const handleClearHistory = async () => {
    if (sending) {
      handleStopStreaming();
    }

    try {
      await del('/ai/history');
      setMessages([]);
      setHistoryLoaded(true);
      message.success('AI 对话记录已清空');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '清空记录失败');
    }
  };

  const renderAssistantCard = (card: AssistantCard, index: number) => {
    if (card.type === 'product') {
      const canAddToCart = card.status === 'on_sale' && card.stock > 0;
      return (
        <AssistantCardBox key={`${card.type}-${card.id}-${index}`} size="small">
          <CardTitleRow>
            <Title level={5}>{card.name}</Title>
            <Space size={6}>
              {card.category_name ? <Tag color="blue">{card.category_name}</Tag> : null}
              <Tag color={card.status === 'on_sale' ? 'green' : 'default'}>{saleStatusMap[card.status]}</Tag>
            </Space>
          </CardTitleRow>
          {card.reason ? <ReasonText>{card.reason}</ReasonText> : null}
          <ProductRow>
            <ProductCover src={card.image_url || 'https://placehold.co/120x120?text=No+Image'} alt={card.name} />
            <div>
              <PriceText>{formatAmount(card.price)}</PriceText>
              <Paragraph style={{ marginBottom: 8 }} ellipsis={{ rows: 2 }}>
                {card.description || '暂无描述'}
              </Paragraph>
              <Text type={card.stock > 0 ? 'secondary' : 'danger'}>库存 {card.stock}</Text>
            </div>
          </ProductRow>
          <Space>
            <Button type="link" onClick={() => navigate(card.route || `/product/${card.id}`)}>
              查看商品
            </Button>
            <Button
              type="link"
              disabled={!canAddToCart}
              onClick={() => {
                const added = addItem({
                  productId: card.id,
                  name: card.name,
                  cover: card.image_url || '',
                  price: card.price,
                });
                message[added ? 'success' : 'info'](added ? '已加入购物车' : '该商品已在购物车中');
              }}
            >
              加入购物车
            </Button>
          </Space>
        </AssistantCardBox>
      );
    }

    if (card.type === 'order') {
      return (
        <AssistantCardBox key={`${card.type}-${card.id}-${index}`} size="small">
          <CardTitleRow>
            <Title level={5}>订单 {card.order_no}</Title>
            <Tag color={statusColorMap[card.status] ?? 'default'}>{orderStatusMap[card.status] ?? card.status}</Tag>
          </CardTitleRow>
          {card.reason ? <ReasonText>{card.reason}</ReasonText> : null}
          <Paragraph style={{ marginBottom: 8 }}>订单金额：{formatAmount(card.total_amount)}</Paragraph>
          <Paragraph style={{ marginBottom: 8 }}>
            收货信息：{card.receiver_name || '未知'} {card.phone || ''}
          </Paragraph>
          <Paragraph style={{ marginBottom: 8 }}>{card.address || '暂无收货地址快照'}</Paragraph>
          <Paragraph style={{ marginBottom: 8 }}>
            商品：
            {card.items.map(item => `${item.product_name}${item.category_name ? `（${item.category_name}）` : ''} x${item.quantity}`).join(' / ') || '暂无商品'}
          </Paragraph>
          <Button type="link" onClick={() => navigate(card.route || `/orders/${card.id}`)}>
            查看订单详情
          </Button>
        </AssistantCardBox>
      );
    }

    if (card.type === 'address') {
      return (
        <AssistantCardBox key={`${card.type}-${card.id}-${index}`} size="small">
          <CardTitleRow>
            <Title level={5}>收货地址</Title>
            {card.is_default ? <Tag color="green">默认地址</Tag> : null}
          </CardTitleRow>
          {card.reason ? <ReasonText>{card.reason}</ReasonText> : null}
          <Paragraph style={{ marginBottom: 8 }}>
            {card.receiver_name} / {card.phone}
          </Paragraph>
          <Paragraph style={{ marginBottom: 0 }}>{card.full_address}</Paragraph>
        </AssistantCardBox>
      );
    }

    if (card.type === 'account') {
      return (
        <AssistantCardBox key={`${card.type}-${card.id}-${index}`} size="small">
          <CardTitleRow>
            <Title level={5}>账号信息</Title>
            <Tag color="purple">{card.role}</Tag>
          </CardTitleRow>
          {card.reason ? <ReasonText>{card.reason}</ReasonText> : null}
          <Paragraph style={{ marginBottom: 8 }}>用户名：{card.username}</Paragraph>
          <Paragraph style={{ marginBottom: 0 }}>邮箱：{card.email}</Paragraph>
        </AssistantCardBox>
      );
    }

    return (
      <AssistantCardBox key={`${card.type}-${index}`} size="small">
        <Title level={5}>{card.title}</Title>
        <Paragraph style={{ marginBottom: 0 }}>{card.description || '暂无补充说明'}</Paragraph>
      </AssistantCardBox>
    );
  };

  return (
    <>
      <FloatButton icon={<MessageOutlined />} type="primary" tooltip="AI 智购助手" onClick={() => setDrawerOpen(true)} />

      <Drawer
        title={
          <DrawerTitle>
            <Avatar icon={<CustomerServiceOutlined />} style={{ backgroundColor: '#1677ff' }} />
            <div>
              <Title level={4} style={{ margin: 0 }}>
                AI 智购助手
              </Title>
              {/* <Text type="secondary">当前上下文：{buildPageLabel(String(routeContext.page_type ?? 'home'))}</Text> */}
            </div>
          </DrawerTitle>
        }
        width="min(560px, 100vw)"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        styles={{
          body: {
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            minHeight: 0,
            overflow: 'hidden',
          },
        }}
        extra={
          <Popconfirm title="确认清空对话记录？" description="清空后无法恢复" okText="确认" cancelText="取消" onConfirm={() => void handleClearHistory()}>
            <Button type="text" icon={<DeleteOutlined />} />
          </Popconfirm>
        }
      >
        <DrawerBody ref={bodyRef}>
          <ContextBar>
            <Tag icon={<MessageOutlined />}>多轮对话</Tag>
            <Tag icon={<ShoppingCartOutlined />}>商品推荐</Tag>
            <Tag icon={<OrderedListOutlined />}>订单答疑</Tag>
            <Tag icon={<HomeOutlined />}>地址识别</Tag>
            <Tag icon={<UserOutlined />}>账号信息</Tag>
          </ContextBar>

          <PromptWrap>
            {promptSuggestions.map(prompt => (
              <PromptButton key={prompt} onClick={() => void handleSendMessage(prompt)}>
                {prompt}
              </PromptButton>
            ))}
          </PromptWrap>

          {loadingHistory ? (
            <LoadingWrap>
              <Spin />
            </LoadingWrap>
          ) : messages.length === 0 ? (
            <Empty description="可以直接问商品推荐、订单进度、默认地址、账号信息等问题" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <MessageList>
              {messages.map(item => {
                const shouldRenderBubble = item.role === 'user' || Boolean(item.content.trim()) || item.streaming || item.cards.length === 0;

                return (
                  <MessageItem key={item.id} $role={item.role}>
                    {shouldRenderBubble ? (
                      <Bubble $role={item.role}>
                        {item.content ? (
                          <MarkdownWrap $role={item.role}>
                            <XMarkdown
                              content={item.content}
                              escapeRawHtml
                              openLinksInNewTab
                              streaming={{
                                hasNextChunk: Boolean(item.streaming),
                                enableAnimation: item.role === 'assistant',
                                tail: item.role === 'assistant' && Boolean(item.streaming),
                              }}
                            />
                          </MarkdownWrap>
                        ) : (
                          <TypingHint>{item.streaming ? '正在思考中...' : '已收到结构化结果'}</TypingHint>
                        )}
                      </Bubble>
                    ) : null}
                    {item.cardsVisible && item.cards.length > 0 ? <CardStack>{item.cards.map(renderAssistantCard)}</CardStack> : null}
                  </MessageItem>
                );
              })}
            </MessageList>
          )}
        </DrawerBody>

        <ComposerWrap>
          <Sender
            value={inputValue}
            autoSize={{ minRows: 2, maxRows: 4 }}
            placeholder="问我商品推荐、订单状态、收货地址或账号信息"
            loading={sending}
            onChange={value => setInputValue(value)}
            onSubmit={content => void handleSendMessage(content)}
            onCancel={handleStopStreaming}
            style={{ width: '100%' }}
            suffix={false}
            footer={actionNode => <ComposerActions>{actionNode}</ComposerActions>}
          />
        </ComposerWrap>
      </Drawer>
    </>
  );
};

const DrawerTitle = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const DrawerBody = styled.div`
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
`;

const ContextBar = styled(Space)`
  display: flex;
  flex-wrap: wrap;
  margin-bottom: 12px;
`;

const PromptWrap = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
`;

const PromptButton = styled(Button)`
  border-radius: 999px;
`;

const LoadingWrap = styled.div`
  display: flex;
  justify-content: center;
  padding: 48px 0;
`;

const MessageList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 14px;
`;

const MessageItem = styled.div<{ $role: 'user' | 'assistant' }>`
  display: flex;
  flex-direction: column;
  align-items: ${({ $role }) => ($role === 'user' ? 'flex-end' : 'flex-start')};
  gap: 8px;
`;

const Bubble = styled.div<{ $role: 'user' | 'assistant' }>`
  max-width: 88%;
  padding: 12px 14px;
  border-radius: 18px;
  background: ${({ $role }) => ($role === 'user' ? '#1677ff' : '#f5f7fa')};
  color: ${({ $role }) => ($role === 'user' ? '#ffffff' : '#1f1f1f')};
`;

const MarkdownWrap = styled.div<{ $role: 'user' | 'assistant' }>`
  color: inherit;

  .x-markdown,
  .x-markdown p,
  .x-markdown li,
  .x-markdown strong,
  .x-markdown em,
  .x-markdown blockquote,
  .x-markdown h1,
  .x-markdown h2,
  .x-markdown h3,
  .x-markdown h4,
  .x-markdown h5,
  .x-markdown h6 {
    color: inherit;
  }

  .x-markdown p,
  .x-markdown ul,
  .x-markdown ol,
  .x-markdown pre,
  .x-markdown blockquote {
    margin: 0;
  }

  .x-markdown p + p,
  .x-markdown p + ul,
  .x-markdown p + ol,
  .x-markdown ul + p,
  .x-markdown ol + p,
  .x-markdown pre + p,
  .x-markdown blockquote + p,
  .x-markdown p + pre {
    margin-top: 8px;
  }

  .x-markdown a {
    color: ${({ $role }) => ($role === 'user' ? '#d6e4ff' : '#1677ff')};
  }

  .x-markdown code {
    padding: 2px 6px;
    border-radius: 6px;
    background: ${({ $role }) => ($role === 'user' ? 'rgba(255, 255, 255, 0.18)' : '#eef2ff')};
    color: inherit;
  }

  .x-markdown pre {
    overflow-x: auto;
    padding: 10px 12px;
    border-radius: 10px;
    background: ${({ $role }) => ($role === 'user' ? 'rgba(0, 0, 0, 0.18)' : '#111827')};
  }

  .x-markdown pre code {
    padding: 0;
    background: transparent;
    color: ${({ $role }) => ($role === 'user' ? '#ffffff' : '#f9fafb')};
  }
`;

const TypingHint = styled.div`
  white-space: pre-wrap;
`;

const CardStack = styled.div`
  width: min(100%, 88%);
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const AssistantCardBox = styled(Card)`
  border-radius: 14px;
`;

const CardTitleRow = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;

  .ant-typography {
    margin-bottom: 0;
  }
`;

const ReasonText = styled(Text)`
  display: inline-block;
  margin: 6px 0 10px;
`;

const ProductRow = styled.div`
  display: grid;
  grid-template-columns: 92px 1fr;
  gap: 12px;
  margin-bottom: 10px;
`;

const ProductCover = styled.img`
  width: 92px;
  height: 92px;
  object-fit: cover;
  border-radius: 10px;
  background: #f5f5f5;
`;

const PriceText = styled.div`
  color: #cf1322;
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 6px;
`;

const ComposerWrap = styled.div`
  flex-shrink: 0;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
`;

const ComposerActions = styled.div`
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
`;

export default ClientAiAssistant;
