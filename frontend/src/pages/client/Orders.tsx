import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Input, Select, Space, Table, Tag, Typography, message } from 'antd';
import styled from 'styled-components';
import { get } from '@/utils/request';

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
  total_amount: number;
  status: string;
  created_at: string;
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
  const navigate = useNavigate();
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [status, setStatus] = useState<string | undefined>();
  const [productName, setProductName] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const data = await get<OrderListResponse>('/orders', {
        params: {
          page,
          page_size: pageSize,
          status,
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

  useEffect(() => {
    void fetchOrders();
  }, [page, pageSize, status, productName]);

  return (
    <ContentWrap>
      <Title level={3}>我的订单</Title>
      <Space wrap style={{ marginBottom: 14 }}>
        <Input.Search
          allowClear
          style={{ width: 260 }}
          placeholder="按商品名称模糊搜索"
          onSearch={value => {
            setPage(1);
            setProductName(value.trim());
          }}
        />
        <Select
          allowClear
          style={{ width: 160 }}
          placeholder="按订单状态筛选"
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
      </Space>
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
          {
            title: '商品',
            render: (_, row) => row.items.map(item => item.product_name).slice(0, 2).join(' / '),
          },
          { title: '金额', render: (_, row) => `¥${row.total_amount.toFixed(2)}` },
          {
            title: '状态',
            render: (_, row) => <Tag color={statusColorMap[row.status] ?? 'default'}>{row.status}</Tag>,
          },
          { title: '下单时间', dataIndex: 'created_at' },
          {
            title: '操作',
            render: (_, row) => (
              <Button type="link" onClick={() => navigate(`/orders/${row.id}`)}>
                查看详情
              </Button>
            ),
          },
        ]}
      />
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1080px;
  width: 100%;
  margin: 0 auto;
`;

export default Orders;
