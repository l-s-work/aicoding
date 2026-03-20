import { useEffect, useMemo, useState } from 'react';
import { Button, Drawer, Input, Select, Space, Table, Tag, Typography, message } from 'antd';
import styled from 'styled-components';
import { get, put } from '@/utils/request';
import { formatAmount, orderStatusMap } from '@/utils/dataformat';

const { Title } = Typography;

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
  receiver_info: string;
  items: OrderItem[];
}

interface OrderListResponse {
  total: number;
  items: Order[];
}

const statusColorMap: Record<string, string> = {
  pending: 'orange',
  paid: 'blue',
  shipped: 'cyan',
  completed: 'green',
  cancelled: 'default',
};

const Orders = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [status, setStatus] = useState<string | undefined>();
  const [receiverName, setReceiverName] = useState('');
  const [productName, setProductName] = useState('');
  const [loading, setLoading] = useState(false);
  const [detailOrder, setDetailOrder] = useState<Order | null>(null);
  const [statusUpdatingId, setStatusUpdatingId] = useState<number | null>(null);

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const data = await get<OrderListResponse>('/orders/admin/all', {
        params: {
          page,
          page_size: pageSize,
          status,
          receiver_name: receiverName || undefined,
          product_name: productName || undefined,
        },
      });
      setOrders(data.items);
      setTotal(data.total);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '订单加载失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchOrderDetail = async (id: number) => {
    try {
      const data = await get<Order>(`/orders/admin/${id}`);
      setDetailOrder(data);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '订单详情加载失败');
    }
  };

  useEffect(() => {
    void fetchOrders();
  }, [page, pageSize, status, receiverName, productName]);

  const detailReceiverInfo = useMemo(() => {
    if (!detailOrder) return null;
    try {
      return JSON.parse(detailOrder.receiver_info) as Record<string, string>;
    } catch {
      return null;
    }
  }, [detailOrder]);

  const handleStatusUpdate = async (orderId: number, nextStatus: string) => {
    setStatusUpdatingId(orderId);
    try {
      await put(`/orders/admin/${orderId}/status`, { status: nextStatus });
      message.success('订单状态已更新');
      await fetchOrders();
      if (detailOrder?.id === orderId) {
        await fetchOrderDetail(orderId);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '状态更新失败');
    } finally {
      setStatusUpdatingId(null);
    }
  };

  return (
    <ContentWrap>
      <Title level={3}>订单管理</Title>
      <FilterRow>
        <FilterItem>
          <FilterLabel>收货人/用户名</FilterLabel>
          <Input.Search
            style={{ width: 220 }}
            allowClear
            placeholder="输入后回车搜索"
            onSearch={value => {
              setPage(1);
              setReceiverName(value.trim());
            }}
          />
        </FilterItem>
        <FilterItem>
          <FilterLabel>商品名称</FilterLabel>
          <Input.Search
            style={{ width: 220 }}
            allowClear
            placeholder="输入后回车搜索"
            onSearch={value => {
              setPage(1);
              setProductName(value.trim());
            }}
          />
        </FilterItem>
        <FilterItem>
          <FilterLabel>订单状态</FilterLabel>
          <Select
            allowClear
            style={{ width: 180 }}
            placeholder="请选择状态"
            value={status}
            onChange={value => {
              setPage(1);
              setStatus(value);
            }}
            options={[
              { label: '待支付', value: 'pending' },
              { label: '已支付', value: 'paid' },
              { label: '已发货', value: 'shipped' },
              { label: '已完成', value: 'completed' },
              { label: '已取消', value: 'cancelled' },
            ]}
          />
        </FilterItem>
      </FilterRow>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={orders}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (current, size) => {
            setPage(current);
            setPageSize(size);
          },
        }}
        columns={[
          { title: '订单号', dataIndex: 'order_no' },
          { title: '用户', render: (_, row) => row.username ?? '-' },
          {
            title: '商品名称',
            render: (_, row) => {
              const names = row.items.map(item => item.product_name).filter(Boolean);
              if (names.length === 0) return '-';
              if (names.length <= 2) return names.join(' / ');
              return `${names.slice(0, 2).join(' / ')} 等${names.length}件`;
            },
            width: 280,
          },
          {
            title: '收货人',
            render: (_, row) => {
              try {
                return JSON.parse(row.receiver_info)?.receiver_name ?? '-';
              } catch {
                return '-';
              }
            },
          },
          { title: '金额', render: (_, row) => formatAmount(row.total_amount) },
          {
            title: '状态',
            render: (_, row) => <Tag color={statusColorMap[row.status] ?? 'default'}>{orderStatusMap[row.status] ?? row.status}</Tag>,
          },
          {
            title: '快捷改状态',
            render: (_, row) => (
              <Select
                size="small"
                value={row.status}
                loading={statusUpdatingId === row.id}
                disabled={row.status === 'completed' || row.status === 'cancelled'}
                style={{ width: 130 }}
                options={[
                  { label: orderStatusMap.pending, value: 'pending' },
                  { label: orderStatusMap.paid, value: 'paid' },
                  { label: orderStatusMap.shipped, value: 'shipped' },
                  { label: orderStatusMap.cancelled, value: 'cancelled' },
                  { label: orderStatusMap.completed, value: 'completed' },
                ]}
                onChange={value => void handleStatusUpdate(row.id, value)}
              />
            ),
          },
          {
            title: '操作',
            render: (_, row) => (
              <Button type="link" onClick={() => void fetchOrderDetail(row.id)}>
                查看详情
              </Button>
            ),
          },
        ]}
      />
      <Drawer width={620} title="订单详情" open={!!detailOrder} onClose={() => setDetailOrder(null)} destroyOnClose>
        {detailOrder ? (
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <div>订单号：{detailOrder.order_no}</div>
            <div>用户：{detailOrder.username ?? '-'}</div>
            <div>状态：{orderStatusMap[detailOrder.status] ?? detailOrder.status}</div>
            <div>收货人：{detailReceiverInfo?.receiver_name ?? '-'}</div>
            <div>
              收货地址：
              {[detailReceiverInfo?.province, detailReceiverInfo?.city, detailReceiverInfo?.district, detailReceiverInfo?.detail_address]
                .filter(Boolean)
                .join(' ')}
            </div>
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={detailOrder.items}
              columns={[
                { title: '商品', dataIndex: 'product_name' },
                { title: '数量', dataIndex: 'quantity', width: 80 },
                { title: '成交单价', render: (_, row) => formatAmount(row.buy_price) },
              ]}
            />
          </Space>
        ) : null}
      </Drawer>
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1240px;
  margin: 0 auto;
`;

const FilterRow = styled(Space)`
  margin-bottom: 14px;
  display: flex;
  flex-wrap: wrap;
`;

const FilterItem = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 8px;
`;

const FilterLabel = styled.span`
  font-size: 13px;
  color: #595959;
  white-space: nowrap;
`;

export default Orders;
