import { useEffect, useMemo, useState } from 'react';
import { Table, Button, Popconfirm, Space, Typography, Card, Modal, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import useCartStore from '@/store/useCartStore';
import { formatAmount } from '@/utils/dataformat';
import ClientPageHeader from '@/components/Layout/ClientPageHeader';

const { Text } = Typography;

const Cart = () => {
  const navigate = useNavigate();
  const { items, removeItem, totalPrice } = useCartStore();
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);

  useEffect(() => {
    const itemIds = items.map(item => item.productId);
    setSelectedProductIds(prev => {
      return prev.filter(id => itemIds.includes(id));
    });
  }, [items]);

  const selectedItems = useMemo(() => {
    const selectedSet = new Set(selectedProductIds);
    // 购物车阶段不统计数量，结算时默认每件商品数量为 1
    return items.filter(item => selectedSet.has(item.productId)).map(item => ({ ...item, quantity: 1 }));
  }, [items, selectedProductIds]);

  const selectedTotalPrice = useMemo(() => selectedItems.reduce((sum, item) => sum + item.price, 0), [selectedItems]);

  const gotoCheckout = () => {
    if (items.length === 0) return;
    if (selectedItems.length === 0) {
      message.warning('请至少勾选一个商品再结算');
      return;
    }
    Modal.confirm({
      title: '确认去结算？',
      content: `本次将结算已勾选的 ${selectedItems.length} 件商品`,
      // content: '下一步需要选择收货地址，并在提交前进行二次确认。',
      okText: '去结算',
      cancelText: '取消',
      onOk: () => {
        navigate('/checkout', {
          state: {
            source: 'cart',
            checkoutItems: selectedItems,
            selectedProductIds,
          },
        });
      },
    });
  };

  return (
    <ContentWrap>
      <ClientPageHeader title="我的购物车" />
      <Card>
        <Table
          rowKey="productId"
          dataSource={items}
          rowSelection={{
            selectedRowKeys: selectedProductIds,
            onChange: selectedRowKeys => {
              setSelectedProductIds(selectedRowKeys as number[]);
            },
          }}
          pagination={false}
          tableLayout="fixed"
          scroll={{ x: 860 }}
          columns={[
            { title: '商品', dataIndex: 'name', width: 280 },
            { title: '单价', width: 120, render: (_, row) => formatAmount(row.price) },
            { title: '金额', width: 120, render: (_, row) => formatAmount(row.price) },
            {
              title: '操作',
              width: 180,
              render: (_, row) => (
                <Space size={0}>
                  <Button type="link" onClick={() => navigate(`/product/${row.productId}`)}>
                    查看详情
                  </Button>
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
                </Space>
              ),
            },
          ]}
        />
        <FooterBar>
          <Space>
            <Text>购物车总计：</Text>
            <TotalText>{formatAmount(totalPrice())}</TotalText>
            <Text style={{ marginLeft: 16 }}>已选合计：</Text>
            <TotalText>{formatAmount(selectedTotalPrice)}</TotalText>
          </Space>
          <Button type="primary" disabled={selectedItems.length === 0} onClick={gotoCheckout}>
            结算已选商品
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
