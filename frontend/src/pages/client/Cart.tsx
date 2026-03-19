import { Table, InputNumber, Button, Space, Typography, Card } from 'antd';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import useCartStore from '@/store/useCartStore';

const { Title, Text } = Typography;

const Cart = () => {
  const navigate = useNavigate();
  const { items, updateQuantity, removeItem, totalPrice } = useCartStore();

  return (
    <ContentWrap>
      <Title level={3}>我的购物车</Title>
      <Card>
        <Table
          rowKey="productId"
          dataSource={items}
          pagination={false}
          columns={[
            { title: '商品', dataIndex: 'name' },
            { title: '单价', render: (_, row) => `¥${row.price.toFixed(2)}` },
            {
              title: '数量',
              render: (_, row) => (
                <InputNumber min={1} value={row.quantity} onChange={value => updateQuantity(row.productId, Number(value || 1))} />
              ),
            },
            { title: '小计', render: (_, row) => `¥${(row.price * row.quantity).toFixed(2)}` },
            {
              title: '操作',
              render: (_, row) => (
                <Button danger type="link" onClick={() => removeItem(row.productId)}>
                  删除
                </Button>
              ),
            },
          ]}
        />
        <FooterBar>
          <Space>
            <Text>总计：</Text>
            <TotalText>¥{totalPrice().toFixed(2)}</TotalText>
          </Space>
          <Button type="primary" disabled={items.length === 0} onClick={() => navigate('/checkout')}>
            去结算
          </Button>
        </FooterBar>
      </Card>
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1080px;
  width: 100%;
  margin: 0 auto;
`;

const FooterBar = styled.div`
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const TotalText = styled.span`
  font-size: 20px;
  font-weight: 700;
  color: #cf1322;
`;

export default Cart;
