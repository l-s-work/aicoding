import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Cascader, Col, Empty, Input, Modal, Pagination, Row, Select, Skeleton, Space, Tag, Typography, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import useCartStore from '@/store/useCartStore';
import { get } from '@/utils/request';
import { formatAmount, saleStatusMap } from '@/utils/dataformat';
import { buildCategoryCascaderOptions } from '@/utils/category';
import ClientPageHeader from '@/components/Layout/ClientPageHeader';

const { Text, Paragraph, Title } = Typography;

interface CategoryNode {
  id: number;
  name: string;
  level: number;
  children: CategoryNode[];
}

interface ProductItem {
  id: number;
  name: string;
  description: string | null;
  price: number;
  stock: number;
  category_id: number | null;
  image_url: string | null;
  status: 'on_sale' | 'off_sale';
}

interface ProductListResponse {
  total: number;
  items: ProductItem[];
}

const Home = () => {
  const navigate = useNavigate();
  const { addItem } = useCartStore();

  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<CategoryNode[]>([]);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(8);
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<'on_sale' | 'off_sale' | undefined>(undefined);
  // 多选分类：每一项都是一个完整路径（如 [1, 3, 9]）
  const [categoryPaths, setCategoryPaths] = useState<number[][]>([]);

  const selectedCategoryIds = useMemo(() => {
    const leafIds = categoryPaths
      .map(path => path[path.length - 1])
      .filter((id): id is number => typeof id === 'number');
    return Array.from(new Set(leafIds));
  }, [categoryPaths]);
  const cascaderOptions = useMemo(() => buildCategoryCascaderOptions(categories), [categories]);

  const fetchCategories = async () => {
    const data = await get<CategoryNode[]>('/products/categories');
    setCategories(data);
  };

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const data = await get<ProductListResponse>('/products', {
        params: {
          page,
          page_size: pageSize,
          keyword: keyword || undefined,
          status,
          category_ids: selectedCategoryIds.length > 0 ? selectedCategoryIds : undefined,
        },
        paramsSerializer: {
          serialize: params => {
            const searchParams = new URLSearchParams();
            Object.entries(params).forEach(([key, value]) => {
              if (value === undefined || value === null || value === '') return;
              if (Array.isArray(value)) {
                value.forEach(item => searchParams.append(key, String(item)));
                return;
              }
              searchParams.append(key, String(value));
            });
            return searchParams.toString();
          },
        },
      });
      setProducts(data.items);
      setTotal(data.total);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '商品加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchCategories();
  }, []);

  useEffect(() => {
    void fetchProducts();
  }, [page, pageSize, keyword, status, selectedCategoryIds]);

  const handleAddToCart = (product: ProductItem) => {
    const added = addItem({
      productId: product.id,
      name: product.name,
      cover: product.image_url || '',
      price: product.price,
    });
    if (added) {
      message.success('已加入购物车');
    } else {
      message.info('该商品已在购物车中，可直接去结算调整数量');
    }
  };

  const handleBuyNow = (product: ProductItem) => {
    if (product.status !== 'on_sale' || product.stock <= 0) {
      message.warning('当前商品不可购买');
      return;
    }

    Modal.confirm({
      title: '确认立即购买？',
      // content: '下一步将进入结算页，请选择收货地址并在提交前进行二次确认。',
      okText: '去结算',
      cancelText: '取消',
      onOk: () => {
        navigate('/checkout', {
          state: {
            source: 'buy_now',
            checkoutItems: [
              {
                productId: product.id,
                name: product.name,
                cover: product.image_url || '',
                price: product.price,
                quantity: 1,
              },
            ],
          },
        });
      },
    });
  };

  return (
    <ContentWrap>
      <ClientPageHeader title="商品列表" />

      <FilterRow>
        <FilterItem>
          <FilterLabel>关键词</FilterLabel>
          <Input.Search
            placeholder="按商品名称模糊搜索"
            allowClear
            style={{ width: 260 }}
            onSearch={value => {
              setPage(1);
              setKeyword(value.trim());
            }}
          />
        </FilterItem>
        <FilterItem>
          <FilterLabel>状态</FilterLabel>
          <Select
            allowClear
            placeholder="按状态筛选"
            style={{ width: 150 }}
            value={status}
            onChange={value => {
              setPage(1);
              setStatus(value);
            }}
            options={[
              { label: '在售', value: 'on_sale' },
              { label: '下架', value: 'off_sale' },
            ]}
          />
        </FilterItem>
        {/* <FilterItem>
          <FilterLabel>层级</FilterLabel>
          <Select
            allowClear
            placeholder="按级别筛选"
            style={{ width: 150 }}
            value={level}
            onChange={value => {
              setPage(1);
              setLevel(value);
            }}
            options={[
              { label: '一级分类', value: 1 },
              { label: '二级分类', value: 2 },
              { label: '三级分类', value: 3 },
            ]}
          />
        </FilterItem> */}
        <FilterItem>
          <FilterLabel>分类</FilterLabel>
          <Cascader
            allowClear
            multiple
            placeholder="按分类多选筛选"
            style={{ width: 280 }}
            options={cascaderOptions}
            value={categoryPaths}
            onChange={value => {
              setPage(1);
              const nextPaths = ((value as Array<Array<string | number>>) ?? []).map(path => path.map(id => Number(id)));
              setCategoryPaths(nextPaths);
            }}
          />
        </FilterItem>
      </FilterRow>

      {loading && products.length === 0 ? (
        <Row gutter={[16, 16]}>
          {Array.from({ length: Math.min(pageSize, 8) }).map((_, index) => (
            <ProductCol key={`skeleton-${index}`} xs={24} sm={12} lg={8} xl={6}>
              <ProductCard>
                <Skeleton.Image active style={{ width: '100%', height: 180 }} />
                <div style={{ paddingTop: 12 }}>
                  <Skeleton active title={false} paragraph={{ rows: 2 }} />
                </div>
              </ProductCard>
            </ProductCol>
          ))}
        </Row>
      ) : products.length === 0 ? (
        <Empty description="暂无符合条件的商品" />
      ) : (
        <Row gutter={[16, 16]}>
          {products.map(product => (
            <ProductCol key={product.id} xs={24} sm={12} lg={8} xl={6}>
              <ProductCard
                hoverable
                onClick={() => navigate(`/product/${product.id}`)}
                cover={
                  <CoverWrap>
                    <Cover src={product.image_url || 'https://placehold.co/600x360?text=No+Image'} alt={product.name} />
                  </CoverWrap>
                }
                actions={[
                  <ActionButton
                    key="detail"
                    type="link"
                    className="action-btn"
                    onClick={event => {
                      event.stopPropagation();
                      navigate(`/product/${product.id}`);
                    }}
                  >
                    查看详情
                  </ActionButton>,
                  <ActionButton
                    key="cart"
                    type="link"
                    className="action-btn"
                    disabled={product.status !== 'on_sale' || product.stock <= 0}
                    onClick={event => {
                      event.stopPropagation();
                      handleAddToCart(product);
                    }}
                  >
                    加入购物车
                  </ActionButton>,
                  <ActionButton
                    key="buy_now"
                    type="link"
                    className="action-btn"
                    disabled={product.status !== 'on_sale' || product.stock <= 0}
                    onClick={event => {
                      event.stopPropagation();
                      handleBuyNow(product);
                    }}
                  >
                    立即购买
                  </ActionButton>,
                ]}
              >
                <CardTitle level={5}>{product.name}</CardTitle>
                <CardDesc ellipsis={{ rows: 2 }} type="secondary">
                  {product.description || '暂无描述'}
                </CardDesc>
                <MetaRow>
                  <PriceText>{formatAmount(product.price)}</PriceText>
                  <Tag color={product.status === 'on_sale' ? 'green' : 'default'}>{saleStatusMap[product.status]}</Tag>
                  <Text type={product.stock > 0 ? 'secondary' : 'danger'}>库存 {product.stock}</Text>
                </MetaRow>
              </ProductCard>
            </ProductCol>
          ))}
        </Row>
      )}

      <PaginationWrap>
        <Pagination
          current={page}
          pageSize={pageSize}
          total={total}
          showSizeChanger
          pageSizeOptions={[8, 16, 24, 32]}
          onChange={(current, size) => {
            setPage(current);
            setPageSize(size);
          }}
        />
      </PaginationWrap>
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1240px;
  width: 100%;
  margin: 0 auto;
`;

const FilterRow = styled(Space)`
  display: flex;
  flex-wrap: wrap;
  margin-bottom: 16px;
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

const ProductCol = styled(Col)`
  display: flex;
`;

const ProductCard = styled(Card)`
  width: 100%;

  .ant-card-body {
    min-height: 150px;
    display: flex;
    flex-direction: column;
  }

  .ant-card-actions > li {
    margin: 0;
  }

  .ant-card-actions > li > span {
    display: flex;
    justify-content: center;
  }

  .action-btn {
    height: 40px;
    padding: 0;
    line-height: 40px;
  }
`;

const Cover = styled.img`
  width: 100%;
  height: 180px;
  object-fit: contain;
`;

const CoverWrap = styled.div`
  height: 180px;
  background: #fafafa;
  padding: 8px;
`;

const CardTitle = styled(Title)`
  && {
    margin-bottom: 8px;
    min-height: 56px;
    line-height: 28px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
`;

const CardDesc = styled(Paragraph)`
  && {
    margin-bottom: 10px;
    min-height: 44px;
  }
`;

const MetaRow = styled(Space)`
  margin-top: auto;
`;

const PriceText = styled(Text)`
  color: #cf1322;
  font-size: 18px;
  font-weight: 700;
`;

const PaginationWrap = styled.div`
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
`;

const ActionButton = styled(Button)`
  && {
    height: 40px;
    padding: 0;
    line-height: 40px;
  }
`;

export default Home;
