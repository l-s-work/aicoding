import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Descriptions, Table, Tag, message } from 'antd';
import styled from 'styled-components';
import { get } from '@/utils/request';
import { orderStatusMap } from '@/utils/dataformat';
import ClientPageHeader from '@/components/Layout/ClientPageHeader';

interface OrderItem {
  id: number;
  product_name: string;
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

  useEffect(() => {
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
    void fetchOrder();
  }, [id]);

  return (
    <ContentWrap>
      <ClientPageHeader title="订单详情" fallbackPath="/orders" />
      <Card loading={loading}>
        {order && (
          <>
            <Descriptions bordered column={2}>
              <Descriptions.Item label="订单号">{order.order_no}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColorMap[order.status] ?? 'default'}>{orderStatusMap[order.status] ?? order.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="总金额">¥{order.total_amount.toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="下单时间">{order.created_at}</Descriptions.Item>
              <Descriptions.Item label="收货人">{receiverInfo?.receiver_name ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="手机号">{receiverInfo?.phone ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="收货地址" span={2}>
                {[receiverInfo?.province, receiverInfo?.city, receiverInfo?.district, receiverInfo?.detail_address].filter(Boolean).join(' ')}
              </Descriptions.Item>
            </Descriptions>

            <Table
              style={{ marginTop: 16 }}
              rowKey="id"
              dataSource={order.items}
              pagination={false}
              columns={[
                { title: '商品名称', dataIndex: 'product_name' },
                { title: '数量', dataIndex: 'quantity' },
                { title: '成交单价', render: (_, row) => `¥${row.buy_price.toFixed(2)}` },
                { title: '小计', render: (_, row) => `¥${(row.buy_price * row.quantity).toFixed(2)}` },
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

export default OrderDetailPage;
