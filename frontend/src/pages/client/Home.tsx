import { useEffect, useMemo, useState } from 'react';
import { Card, Col, Empty, Input, Row, Select, Space, Tag, Typography, Button, Pagination, message } from 'antd';
import { Link } from 'react-router-dom';
import styled from 'styled-components';
import useCartStore from '@/store/useCartStore';
import { get } from '@/utils/request';

const { Title, Text, Paragraph } = Typography;

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

const flattenCategories = (nodes: CategoryNode[], output: Array<{ id: number; name: string; level: number }> = []) => {
  for (const node of nodes) {
    output.push({ id: node.id, name: node.name, level: node.level });
    flattenCategories(node.children ?? [], output);
  }
  return output;
};

const Home = () => {
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<CategoryNode[]>([]);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<'on_sale' | 'off_sale' | undefined>(undefined);
  const [level, setLevel] = useState<number | undefined>(undefined);
  const [categoryId, setCategoryId] = useState<number | undefined>(undefined);

  const { addItem } = useCartStore();

  const categoryOptions = useMemo(() => flattenCategories(categories).map(cat => ({
    label: `${'  '.repeat(Math.max(cat.level - 1, 0))}${cat.name}`,
    value: cat.id,
  })), [categories]);

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
          level,
          category_id: categoryId,
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
  }, [page, pageSize, keyword, status, level, categoryId]);

  return (
    <ContentWrap>
      <Title level={3}>商品列表</Title>
      <Space wrap size={12} style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="按商品名称模糊搜索"
          allowClear
          style={{ width: 260 }}
          onSearch={value => {
            setPage(1);
            setKeyword(value.trim());
          }}
        />
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
        <Select
          allowClear
          placeholder="按分类筛选"
          style={{ width: 280 }}
          value={categoryId}
          onChange={value => {
            setPage(1);
            setCategoryId(value);
          }}
          options={categoryOptions}
        />
      </Space>

      {products.length === 0 && !loading ? (
        <Empty description="暂无符合条件的商品" />
      ) : (
        <Row gutter={[16, 16]}>
          {products.map(product => (
            <Col key={product.id} xs={24} sm={12} lg={8} xl={6}>
              <Card
                loading={loading}
                hoverable
                cover={<Cover src={product.image_url || 'https://placehold.co/600x360?text=No+Image'} alt={product.name} />}
                actions={[
                  <Link key="detail" to={`/product/${product.id}`}>
                    查看详情
                  </Link>,
                  <Button
                    key="cart"
                    type="link"
                    disabled={product.status !== 'on_sale' || product.stock <= 0}
                    onClick={() => {
                      addItem({
                        productId: product.id,
                        name: product.name,
                        cover: product.image_url || '',
                        price: product.price,
                      });
                      message.success('已加入购物车');
                    }}
                  >
                    加入购物车
                  </Button>,
                ]}
              >
                <Title level={5} style={{ marginBottom: 8 }}>
                  {product.name}
                </Title>
                <Paragraph ellipsis={{ rows: 2 }} type="secondary">
                  {product.description || '暂无描述'}
                </Paragraph>
                <Space>
                  <PriceText>¥{product.price.toFixed(2)}</PriceText>
                  <Tag color={product.status === 'on_sale' ? 'green' : 'default'}>{product.status === 'on_sale' ? '在售' : '下架'}</Tag>
                  <Text type={product.stock > 0 ? 'secondary' : 'danger'}>库存 {product.stock}</Text>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <PaginationWrap>
        <Pagination
          current={page}
          pageSize={pageSize}
          total={total}
          showSizeChanger
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

const Cover = styled.img`
  width: 100%;
  height: 180px;
  object-fit: cover;
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

export default Home;
