import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Space, Statistic, Table, Tag, Typography, message } from 'antd';
import styled from 'styled-components';
import { get, put } from '@/utils/request';
import { formatAmount, orderStatusMap } from '@/utils/dataformat';

const { Title } = Typography;

interface RecoveryRequestItem {
  id: number;
  user_id: number;
  username: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
}

interface RecoveryRequestListResponse {
  total: number;
  items: RecoveryRequestItem[];
}

interface OrderItem {
  id: number;
  product_name: string;
  quantity: number;
  buy_price: number;
}

interface Order {
  id: number;
  order_no: string;
  username?: string;
  total_amount: number;
  status: string;
  created_at: string;
  items: OrderItem[];
}

interface OrderListResponse {
  total: number;
  items: Order[];
}

const Todos = () => {
  const [loading, setLoading] = useState(false);
  const [recoveryRequests, setRecoveryRequests] = useState<RecoveryRequestItem[]>([]);
  const [paidOrders, setPaidOrders] = useState<Order[]>([]);
  const [processingRecoveryId, setProcessingRecoveryId] = useState<number | null>(null);
  const [shippingOrderId, setShippingOrderId] = useState<number | null>(null);

  const fetchTodos = async () => {
    setLoading(true);
    try {
      const [recoveryData, ordersData] = await Promise.all([
        get<RecoveryRequestListResponse>('/admin/recovery-requests', {
          params: { page: 1, page_size: 20, status: 'pending' },
        }),
        get<OrderListResponse>('/orders/admin/all', {
          params: { page: 1, page_size: 20, status: 'paid' },
        }),
      ]);
      setRecoveryRequests(recoveryData.items);
      setPaidOrders(ordersData.items);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '待办加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchTodos();
  }, []);

  const todoTotal = useMemo(() => recoveryRequests.length + paidOrders.length, [recoveryRequests, paidOrders]);

  const handleProcessRecovery = async (id: number, nextStatus: 'approved' | 'rejected') => {
    setProcessingRecoveryId(id);
    try {
      await put(`/admin/recovery-requests/${id}/process`, {
        status: nextStatus,
        admin_note: nextStatus === 'approved' ? '管理员已通过恢复申请' : '管理员驳回恢复申请',
      });
      message.success(nextStatus === 'approved' ? '已通过恢复申请' : '已驳回恢复申请');
      await fetchTodos();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '处理恢复申请失败');
    } finally {
      setProcessingRecoveryId(null);
    }
  };

  const handleShipOrder = async (orderId: number) => {
    setShippingOrderId(orderId);
    try {
      await put(`/orders/admin/${orderId}/status`, { status: 'shipped' });
      message.success('订单已标记为已发货');
      await fetchTodos();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '发货操作失败');
    } finally {
      setShippingOrderId(null);
    }
  };

  return (
    <ContentWrap>
      <Title level={3}>我的待办</Title>

      <SummaryRow>
        <Card size="small">
          <Statistic title="待办总数" value={todoTotal} />
        </Card>
        <Card size="small">
          <Statistic title="待处理恢复申请" value={recoveryRequests.length} />
        </Card>
        <Card size="small">
          <Statistic title="待发货订单" value={paidOrders.length} />
        </Card>
      </SummaryRow>

      <Card title="账号恢复申请" style={{ marginBottom: 16 }}>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={recoveryRequests}
          pagination={false}
          locale={{ emptyText: '暂无待处理恢复申请' }}
          columns={[
            { title: '申请ID', dataIndex: 'id', width: 90 },
            { title: '用户名', dataIndex: 'username', width: 160 },
            { title: '申请原因', dataIndex: 'reason' },
            {
              title: '状态',
              width: 120,
              render: () => <Tag color="orange">待处理</Tag>,
            },
            {
              title: '操作',
              width: 170,
              render: (_, row) => (
                <Space size={0}>
                  <Button
                    type="link"
                    loading={processingRecoveryId === row.id}
                    onClick={() => void handleProcessRecovery(row.id, 'approved')}
                  >
                    通过
                  </Button>
                  <Button
                    type="link"
                    danger
                    loading={processingRecoveryId === row.id}
                    onClick={() => void handleProcessRecovery(row.id, 'rejected')}
                  >
                    驳回
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Card title="待发货订单">
        <Table
          rowKey="id"
          loading={loading}
          dataSource={paidOrders}
          pagination={false}
          locale={{ emptyText: '暂无待发货订单' }}
          columns={[
            { title: '订单号', dataIndex: 'order_no' },
            { title: '用户', render: (_, row) => row.username ?? '-' },
            { title: '金额', width: 120, render: (_, row) => formatAmount(row.total_amount) },
            {
              title: '状态',
              width: 120,
              render: (_, row) => <Tag color="blue">{orderStatusMap[row.status] ?? row.status}</Tag>,
            },
            {
              title: '操作',
              width: 120,
              render: (_, row) => (
                <Button type="link" loading={shippingOrderId === row.id} onClick={() => void handleShipOrder(row.id)}>
                  标记发货
                </Button>
              ),
            },
          ]}
        />
      </Card>
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1240px;
  margin: 0 auto;
`;

const SummaryRow = styled.div`
  margin-bottom: 16px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;

  @media (max-width: 980px) {
    grid-template-columns: 1fr;
  }
`;

export default Todos;
