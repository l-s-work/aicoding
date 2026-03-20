import { Table, InputNumber, Button, Popconfirm, Space, Typography, Card, Modal, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import useCartStore from '@/store/useCartStore';
import ClientPageHeader from '@/components/Layout/ClientPageHeader';

const { Text } = Typography;

const Cart = () => {
  const navigate = useNavigate();
  const { items, updateQuantity, removeItem, totalPrice } = useCartStore();

  const gotoCheckout = () => {
    if (items.length === 0) return;
    Modal.confirm({
      title: '确认去结算？',
      // content: '下一步需要选择收货地址，并在提交前进行二次确认。',
      okText: '去结算',
      cancelText: '取消',
      onOk: () => {
        navigate('/checkout', {
          state: {
            source: 'cart',
            checkoutItems: items,
          },
        });
      },
    });
  };

  return (
    <ContentWrap>
      <ClientPageHeader title="我的购物车" fallbackPath="/" />
      <Card>
        <Table
          rowKey="productId"
          dataSource={items}
          pagination={false}
          tableLayout="fixed"
          scroll={{ x: 860 }}
          columns={[
            { title: '商品', dataIndex: 'name', width: 280 },
            { title: '单价', width: 120, render: (_, row) => `¥${row.price.toFixed(2)}` },
            {
              title: '数量',
              width: 150,
              render: (_, row) => (
                <InputNumber
                  min={1}
                  controls
                  style={{ width: 108 }}
                  value={row.quantity}
                  onChange={value => {
                    const next = Number(value || 1);
                    updateQuantity(row.productId, next);
                  }}
                />
              ),
            },
            { title: '小计', width: 120, render: (_, row) => `¥${(row.price * row.quantity).toFixed(2)}` },
            {
              title: '操作',
              width: 110,
              render: (_, row) => (
                <Popconfirm
                  title="确认删除该商品？"
                  description="删除后可在商品页重新加入"
                  okText="确认删除"
                  cancelText="取消"
                  onConfirm={() => {
                    removeItem(row.productId);
                    message.success('商品已移除');
                  }}
                >
                  <Button danger type="link">
                    删除
                  </Button>
                </Popconfirm>
              ),
            },
          ]}
        />
        <FooterBar>
          <Space>
            <Text>总计：</Text>
            <TotalText>¥{totalPrice().toFixed(2)}</TotalText>
          </Space>
          <Button type="primary" disabled={items.length === 0} onClick={gotoCheckout}>
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
