import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Alert, Button, Card, Empty, Flex, InputNumber, Modal, Radio, Space, Table, Tag, Typography, message } from 'antd';
import styled from 'styled-components';
import useCartStore, { type CartItem } from '@/store/useCartStore';
import { get, post } from '@/utils/request';
import { formatAmount } from '@/utils/dataformat';
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
  /** 来自购物车时本次被勾选的商品 ID（下单成功后仅移除这些） */
  selectedProductIds?: number[];
}

const formatAddressText = (address: AddressItem) => [address.province, address.city, address.district, address.detail_address].filter(Boolean).join(' ');

const Checkout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { items: cartItems, clearCart, removeItem } = useCartStore();
  const state = (location.state as CheckoutLocationState | null) ?? null;
  const locationCheckoutItems = state?.checkoutItems;

  const [loading, setLoading] = useState(false);
  const [creatingOrder, setCreatingOrder] = useState(false);
  const [addresses, setAddresses] = useState<AddressItem[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<number | undefined>(undefined);
  const [checkoutItems, setCheckoutItems] = useState<CartItem[]>([]);
  const [addressModalOpen, setAddressModalOpen] = useState(false);
  const [tempSelectedAddressId, setTempSelectedAddressId] = useState<number | undefined>(undefined);

  useEffect(() => {
    if (locationCheckoutItems && locationCheckoutItems.length > 0) {
      setCheckoutItems(locationCheckoutItems);
      return;
    }
    setCheckoutItems(cartItems);
  }, [locationCheckoutItems, cartItems]);

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

  const openAddressSelector = () => {
    if (addresses.length === 0) {
      message.warning('暂无可选地址，请先去地址管理新增');
      return;
    }
    setTempSelectedAddressId(selectedAddressId ?? addresses[0]?.id);
    setAddressModalOpen(true);
  };

  const confirmAddressSelection = () => {
    if (!tempSelectedAddressId) {
      message.warning('请选择一个收货地址');
      return;
    }
    setSelectedAddressId(tempSelectedAddressId);
    setAddressModalOpen(false);
  };

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
      width: 560,
      content: (
        <ConfirmList>
          <ConfirmRow>
            <ConfirmLabel>收货人：</ConfirmLabel>
            <ConfirmValue>{selectedAddress.receiver_name}</ConfirmValue>
          </ConfirmRow>
          <ConfirmRow>
            <ConfirmLabel>手机号：</ConfirmLabel>
            <ConfirmValue>{selectedAddress.phone}</ConfirmValue>
          </ConfirmRow>
          <ConfirmRow>
            <ConfirmLabel>收货地址：</ConfirmLabel>
            <ConfirmValue>{formatAddressText(selectedAddress)}</ConfirmValue>
          </ConfirmRow>
          <ConfirmRow>
            <ConfirmLabel>订单金额：</ConfirmLabel>
            <ConfirmValue>
              <ConfirmAmount>{formatAmount(totalAmount)}</ConfirmAmount>
            </ConfirmValue>
          </ConfirmRow>
        </ConfirmList>
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
            if (state?.selectedProductIds && state.selectedProductIds.length > 0) {
              state.selectedProductIds.forEach(id => removeItem(id));
            } else {
              clearCart();
            }
          }

          message.success('下单成功，订单状态为已支付');
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
      <ClientPageHeader title="订单结算" fallbackPath="/cart" showBack={false} />

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
                { title: '单价', width: 120, render: (_, row) => formatAmount(row.price) },
                {
                  title: '数量',
                  width: 140,
                  render: (_, row) => (
                    <InputNumber
                      min={1}
                      controls
                      style={{ width: 108 }}
                      value={row.quantity}
                      onChange={value => {
                        const nextQuantity = Number(value || 1);
                        setCheckoutItems(prev =>
                          prev.map(item =>
                            item.productId === row.productId
                              ? {
                                  ...item,
                                  quantity: nextQuantity,
                                }
                              : item
                          )
                        );
                      }}
                    />
                  ),
                },
                { title: '小计', width: 120, render: (_, row) => formatAmount(row.price * row.quantity) },
                {
                  title: '操作',
                  width: 120,
                  render: (_, row) => (
                    <Button type="link" onClick={() => navigate(`/product/${row.productId}`)}>
                      查看详情
                    </Button>
                  ),
                },
              ]}
            />
            <SummaryRow>
              <Space>
                <Text>应付总额：</Text>
                <TotalText>{formatAmount(totalAmount)}</TotalText>
              </Space>
            </SummaryRow>
          </Card>

          <Card title="收货地址" style={{ marginTop: 16 }} loading={loading}>
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
              <>
                {selectedAddress ? (
                  <SelectedAddressCard>
                    <AddressHead>
                      <Flex justify="space-between" gap={8}>
                        <Text strong>收货人姓名：{selectedAddress.receiver_name}</Text>
                        {selectedAddress.is_default === 1 ? <Tag color="green">默认地址</Tag> : null}
                      </Flex>
                    </AddressHead>
                    <AddressText>
                      <Text>电话：{selectedAddress.phone}</Text>
                    </AddressText>
                    <AddressText>收货地址：{formatAddressText(selectedAddress)}</AddressText>
                  </SelectedAddressCard>
                ) : (
                  <Empty description="请选择收货地址" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
                <AddressActions>
                  <Space>
                    <Button onClick={openAddressSelector}>选择其他地址</Button>
                    <Button type="link" onClick={() => navigate('/addresses')}>
                      去地址管理
                    </Button>
                  </Space>
                </AddressActions>
              </>
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

      <Modal
        title="选择收货地址"
        open={addressModalOpen}
        onOk={confirmAddressSelection}
        onCancel={() => setAddressModalOpen(false)}
        okText="使用该地址"
        cancelText="取消"
      >
        <ModalActionRow>
          <Button type="link" onClick={() => navigate('/addresses')}>
            前往地址管理
          </Button>
        </ModalActionRow>
        <Radio.Group
          value={tempSelectedAddressId}
          onChange={event => {
            setTempSelectedAddressId(event.target.value as number);
          }}
          style={{ width: '100%' }}
        >
          <AddressList>
            {addresses.map(address => (
              <AddressOption key={address.id} value={address.id}>
                <AddressLine>
                  <Flex justify="space-between" gap={8}>
                    <Text strong>收货人姓名：{address.receiver_name}</Text>
                    {address.is_default === 1 ? <Tag color="green">默认</Tag> : null}
                  </Flex>
                </AddressLine>
                <AddressLine>
                  <Text>电话：{address.phone}</Text>
                </AddressLine>
                <AddressLine>收货地址：{formatAddressText(address)}</AddressLine>
              </AddressOption>
            ))}
          </AddressList>
        </Radio.Group>
      </Modal>
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

const SelectedAddressCard = styled.div`
  border: 1px solid #ffd591;
  background: #fff7e6;
  border-radius: 10px;
  padding: 14px 16px;
`;

const AddressHead = styled.div`
  margin-bottom: 8px;
`;

const AddressText = styled.div`
  color: #434343;
  line-height: 1.7;
  word-break: break-all;
`;

const AddressActions = styled.div`
  margin-top: 12px;
`;

const AddressList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const AddressOption = styled(Radio)`
  && {
    width: 100%;
    margin-inline-start: 0;
    border: 1px solid #f0f0f0;
    border-radius: 10px;
    padding: 10px 12px;
    align-items: flex-start;
  }

  &&.ant-radio-wrapper-checked {
    border-color: #ffbb96;
    background: #fff7e6;
  }

  /* 关键：让 Radio 的文本区域撑满整行，内部 Flex 才能真正 space-between */
  .ant-radio-label {
    display: block;
    width: 100%;
  }
`;

const AddressLine = styled.div`
  width: 100%;
  margin-left: 12px;
  color: #595959;
  line-height: 1.7;
  word-break: break-all;
`;

const ActionRow = styled.div`
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
`;

const ModalActionRow = styled.div`
  margin-bottom: 10px;
  display: flex;
  justify-content: flex-end;
`;

const ConfirmList = styled.div`
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const ConfirmRow = styled.div`
  display: grid;
  grid-template-columns: 90px 1fr;
  align-items: center;
`;

const ConfirmLabel = styled.span`
  text-align: right;
  color: #8c8c8c;
`;

const ConfirmValue = styled.span`
  text-align: left;
  color: #262626;
  line-height: 1.7;
  word-break: break-all;
`;

const ConfirmAmount = styled.span`
  font-size: 18px;
  font-weight: 700;
  color: #cf1322;
`;

export default Checkout;
