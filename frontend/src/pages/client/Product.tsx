import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Card, Descriptions, Skeleton, Space, Tag, Typography, message } from 'antd';
import styled from 'styled-components';
import { get } from '@/utils/request';
import useCartStore from '@/store/useCartStore';

const { Title, Paragraph } = Typography;

interface ProductDetail {
  id: number;
  name: string;
  description: string | null;
  price: number;
  stock: number;
  status: 'on_sale' | 'off_sale';
  image_url: string | null;
  category?: { id: number; name: string; level: number };
}

const ProductPage = () => {
  const { id } = useParams();
  const { addItem } = useCartStore();
  const [loading, setLoading] = useState(false);
  const [product, setProduct] = useState<ProductDetail | null>(null);

  useEffect(() => {
    const fetchDetail = async () => {
      if (!id) return;
      setLoading(true);
      try {
        const data = await get<ProductDetail>(`/products/${id}`);
        setProduct(data);
      } catch (error) {
        message.error(error instanceof Error ? error.message : '商品详情加载失败');
      } finally {
        setLoading(false);
      }
    };
    void fetchDetail();
  }, [id]);

  return (
    <ContentWrap>
      {loading || !product ? (
        <Skeleton active />
      ) : (
        <Card>
          <MainArea>
            <Cover src={product.image_url || 'https://placehold.co/800x520?text=No+Image'} alt={product.name} />
            <InfoArea>
              <Title level={3}>{product.name}</Title>
              <Space size={10}>
                <Price>¥{product.price.toFixed(2)}</Price>
                <Tag color={product.status === 'on_sale' ? 'green' : 'default'}>{product.status === 'on_sale' ? '在售' : '下架'}</Tag>
                <Tag color={product.stock > 0 ? 'blue' : 'red'}>库存 {product.stock}</Tag>
              </Space>
              <Paragraph style={{ marginTop: 12 }}>{product.description || '暂无描述'}</Paragraph>
              <Button
                type="primary"
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
              </Button>
            </InfoArea>
          </MainArea>
          <Descriptions bordered size="small" column={1} style={{ marginTop: 20 }}>
            <Descriptions.Item label="商品ID">{product.id}</Descriptions.Item>
            <Descriptions.Item label="分类">{product.category?.name ?? '未分类'}</Descriptions.Item>
            <Descriptions.Item label="状态">{product.status}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1120px;
  width: 100%;
  margin: 0 auto;
`;

const MainArea = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
`;

const Cover = styled.img`
  width: 100%;
  max-height: 420px;
  object-fit: cover;
  border-radius: 8px;
`;

const InfoArea = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const Price = styled.span`
  color: #cf1322;
  font-size: 28px;
  font-weight: 700;
`;

export default ProductPage;
