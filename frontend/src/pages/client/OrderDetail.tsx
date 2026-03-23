import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Card, Descriptions, Space, Table, Tag, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import dayjs from 'dayjs';
import { get, post } from '@/utils/request';
import { formatAmount, orderStatusMap } from '@/utils/dataformat';
import ClientPageHeader from '@/components/Layout/ClientPageHeader';

interface OrderItem {
  id: number;
  product_name: string;
  category_name?: string | null;
  quantity: number;
  buy_price: number;
}

interface OrderDetail {
  id: number;
  order_no: string;
  total_amount: number;
  status: string;
  created_at: string;
  receiver_info: string;
  items: OrderItem[];
}

const statusColorMap: Record<string, string> = {
  pending: 'orange',
  paid: 'blue',
  shipped: 'cyan',
  completed: 'green',
  cancelled: 'default',
};

const OrderDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const receiverInfo = useMemo(() => {
    if (!order) return null;
    try {
      return JSON.parse(order.receiver_info) as Record<string, string>;
    } catch {
      return null;
    }
  }, [order]);

  const fetchOrder = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await get<OrderDetail>(`/orders/${id}`);
      setOrder(data);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '订单详情加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchOrder();
  }, [id]);

  const handleConfirmReceipt = async () => {
    if (!id) return;
    try {
      await post(`/orders/${id}/confirm-receipt`);
      message.success('确认收货成功，订单已完成');
      await fetchOrder();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '确认收货失败');
    }
  };

  return (
    <ContentWrap>
      <ClientPageHeader title="订单详情" fallbackPath="/orders" showBack />
      <Card loading={loading}>
        {order && (
          <>
            <Descriptions bordered column={2}>
              <Descriptions.Item label="订单号">{order.order_no}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColorMap[order.status] ?? 'default'}>{orderStatusMap[order.status] ?? order.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="总金额">{formatAmount(order.total_amount)}</Descriptions.Item>
              <Descriptions.Item label="下单时间">{dayjs(order.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
              <Descriptions.Item label="收货人">{receiverInfo?.receiver_name ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="手机号">{receiverInfo?.phone ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="收货地址" span={2}>
                {[receiverInfo?.province, receiverInfo?.city, receiverInfo?.district, receiverInfo?.detail_address].filter(Boolean).join(' ')}
              </Descriptions.Item>
            </Descriptions>

            {order.status === 'shipped' ? (
              <ActionRow>
                <Space>
                  <Button onClick={() => navigate('/orders')}>返回订单列表</Button>
                  <Button type="primary" onClick={() => void handleConfirmReceipt()}>
                    确认收货
                  </Button>
                </Space>
              </ActionRow>
            ) : null}

            <Table
              style={{ marginTop: 16 }}
              rowKey="id"
              dataSource={order.items}
              pagination={false}
              columns={[
                { title: '商品名称', dataIndex: 'product_name' },
                {
                  title: '分类',
                  dataIndex: 'category_name',
                  render: value => (value ? <Tag color="blue">{value}</Tag> : '-'),
                },
                { title: '数量', dataIndex: 'quantity' },
                { title: '成交单价', render: (_, row) => formatAmount(row.buy_price) },
                { title: '小计', render: (_, row) => formatAmount(row.buy_price * row.quantity) },
              ]}
            />
          </>
        )}
      </Card>
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1080px;
  width: 100%;
  margin: 0 auto;
`;

const ActionRow = styled.div`
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
`;

export default OrderDetailPage;
