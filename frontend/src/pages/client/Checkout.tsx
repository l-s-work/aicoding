import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Alert, Button, Card, Empty, Modal, Radio, Space, Table, Tag, Typography, message } from 'antd';
import styled from 'styled-components';
import useCartStore, { type CartItem } from '@/store/useCartStore';
import { get, post } from '@/utils/request';
import ClientPageHeader from '@/components/Layout/ClientPageHeader';

const { Text } = Typography;

interface AddressItem {
  id: number;
  receiver_name: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  detail_address: string;
  is_default: number;
}

interface OrderCreateResponse {
  id: number;
  order_no: string;
}

interface CheckoutLocationState {
  source?: 'cart' | 'buy_now';
  checkoutItems?: CartItem[];
}

const Checkout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { items: cartItems, clearCart } = useCartStore();
  const state = (location.state as CheckoutLocationState | null) ?? null;

  const [loading, setLoading] = useState(false);
  const [creatingOrder, setCreatingOrder] = useState(false);
  const [addresses, setAddresses] = useState<AddressItem[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<number | undefined>(undefined);
  const [checkoutItems, setCheckoutItems] = useState<CartItem[]>([]);

  useEffect(() => {
    if (state?.checkoutItems && state.checkoutItems.length > 0) {
      setCheckoutItems(state.checkoutItems);
      return;
    }
    setCheckoutItems(cartItems);
  }, [state?.checkoutItems, cartItems]);

  const totalAmount = useMemo(() => checkoutItems.reduce((sum, item) => sum + item.price * item.quantity, 0), [checkoutItems]);

  const selectedAddress = useMemo(() => addresses.find(addr => addr.id === selectedAddressId), [addresses, selectedAddressId]);

  const fetchAddresses = async () => {
    setLoading(true);
    try {
      const data = await get<AddressItem[]>('/addresses');
      setAddresses(data);
      const defaultAddress = data.find(item => item.is_default === 1);
      setSelectedAddressId(defaultAddress?.id ?? data[0]?.id);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '地址加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchAddresses();
  }, []);

  const submitOrder = async () => {
    if (checkoutItems.length === 0) {
      message.warning('当前没有可结算商品');
      return;
    }
    if (!selectedAddressId || !selectedAddress) {
      message.warning('请先选择收货地址');
      return;
    }

    Modal.confirm({
      title: '确认提交订单',
      content: (
        <ConfirmBlock>
          <Text>收货人：{selectedAddress.receiver_name}</Text>
          <Text>手机号：{selectedAddress.phone}</Text>
          <Text>
            地址：
            {[selectedAddress.province, selectedAddress.city, selectedAddress.district, selectedAddress.detail_address].filter(Boolean).join(' ')}
          </Text>
          <Text strong>订单金额：¥{totalAmount.toFixed(2)}</Text>
        </ConfirmBlock>
      ),
      okText: '确认下单',
      cancelText: '取消',
      onOk: async () => {
        setCreatingOrder(true);
        try {
          const order = await post<OrderCreateResponse>('/orders', {
            address_id: selectedAddressId,
            items: checkoutItems.map(item => ({
              product_id: item.productId,
              quantity: item.quantity,
            })),
          });

          // 来自购物车结算时，提交成功后清空购物车
          if ((state?.source ?? 'cart') === 'cart') {
            clearCart();
          }

          message.success('下单成功');
          navigate(`/orders/${order.id}`, { replace: true });
        } catch (error) {
          message.error(error instanceof Error ? error.message : '下单失败');
        } finally {
          setCreatingOrder(false);
        }
      },
    });
  };

  return (
    <ContentWrap>
      <ClientPageHeader title="订单结算" fallbackPath="/cart" />

      {checkoutItems.length === 0 ? (
        <Card>
          <Empty description="暂无可结算商品" />
          <ActionRow>
            <Button type="primary" onClick={() => navigate('/cart')}>
              返回购物车
            </Button>
          </ActionRow>
        </Card>
      ) : (
        <>
          <Card title="待结算商品" loading={loading}>
            <Table
              rowKey="productId"
              dataSource={checkoutItems}
              pagination={false}
              columns={[
                { title: '商品', dataIndex: 'name' },
                { title: '单价', width: 120, render: (_, row) => `¥${row.price.toFixed(2)}` },
                { title: '数量', dataIndex: 'quantity', width: 90 },
                { title: '小计', width: 120, render: (_, row) => `¥${(row.price * row.quantity).toFixed(2)}` },
              ]}
            />
            <SummaryRow>
              <Space>
                <Text>应付总额：</Text>
                <TotalText>¥{totalAmount.toFixed(2)}</TotalText>
              </Space>
            </SummaryRow>
          </Card>

          <Card title="选择收货地址" style={{ marginTop: 16 }} loading={loading}>
            {addresses.length === 0 ? (
              <Alert
                type="warning"
                showIcon
                message="你还没有收货地址，请先去地址管理新增。"
                action={
                  <Button size="small" type="primary" onClick={() => navigate('/addresses')}>
                    去管理地址
                  </Button>
                }
              />
            ) : (
              <Radio.Group value={selectedAddressId} onChange={event => setSelectedAddressId(event.target.value)} style={{ width: '100%' }}>
                <AddressGroup>
                  {addresses.map(address => (
                    <AddressOption key={address.id} value={address.id}>
                      <AddressLine>
                        <Space size={8}>
                          <Text strong>{address.receiver_name}</Text>
                          <Text>{address.phone}</Text>
                          {address.is_default === 1 ? <Tag color="green">默认</Tag> : null}
                        </Space>
                      </AddressLine>
                      <AddressLine>{[address.province, address.city, address.district, address.detail_address].filter(Boolean).join(' ')}</AddressLine>
                    </AddressOption>
                  ))}
                </AddressGroup>
              </Radio.Group>
            )}
          </Card>

          <ActionRow>
            <Space>
              <Button onClick={() => navigate(-1)}>返回</Button>
              <Button type="primary" loading={creatingOrder} disabled={checkoutItems.length === 0} onClick={() => void submitOrder()}>
                提交订单
              </Button>
            </Space>
          </ActionRow>
        </>
      )}
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1080px;
  width: 100%;
  margin: 0 auto;
`;

const SummaryRow = styled.div`
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
`;

const TotalText = styled.span`
  font-size: 20px;
  font-weight: 700;
  color: #cf1322;
`;

const AddressGroup = styled(Space)`
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const AddressOption = styled(Radio)`
  display: block;
  width: 100%;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 10px 12px;
`;

const AddressLine = styled.div`
  margin-left: 24px;
  color: #595959;
`;

const ActionRow = styled.div`
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
`;

const ConfirmBlock = styled(Space)`
  width: 100%;
  display: flex;
  flex-direction: column;
`;

export default Checkout;
