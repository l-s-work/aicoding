import { useEffect, useState } from 'react';
import { Card, Col, Progress, Row, Statistic, Table, Tag, Typography, message } from 'antd';
import styled from 'styled-components';
import { get } from '@/utils/request';
import { saleStatusMap } from '@/utils/dataformat';

const { Title } = Typography;

interface StatusCount {
  status: string;
  count: number;
}
interface CategoryCount {
  category_id: number;
  category_name: string;
  product_count: number;
}
interface HotProduct {
  id: number;
  name: string;
  hot_score: number;
  stock: number;
  status: string;
}
interface DashboardStats {
  product_total: number;
  on_sale_total: number;
  off_sale_total: number;
  low_stock_total: number;
  out_of_stock_total: number;
  category_total: number;
  status_distribution: StatusCount[];
  top_categories: CategoryCount[];
  top_hot_products: HotProduct[];
}

const Dashboard = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true);
      try {
        const data = await get<DashboardStats>('/admin/dashboard/stats');
        setStats(data);
      } catch (error) {
        message.error(error instanceof Error ? error.message : '统计数据加载失败');
      } finally {
        setLoading(false);
      }
    };
    void fetchStats();
  }, []);

  return (
    <ContentWrap>
      <Title level={3}>Dashboard 商品统计</Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={8}>
          <Card loading={loading}>
            <Statistic title="商品总数" value={stats?.product_total ?? 0} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card loading={loading}>
            <Statistic title="在售商品" value={stats?.on_sale_total ?? 0} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card loading={loading}>
            <Statistic title="下架商品" value={stats?.off_sale_total ?? 0} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card loading={loading}>
            <Statistic title="低库存商品(<=10)" value={stats?.low_stock_total ?? 0} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card loading={loading}>
            <Statistic title="缺货商品" value={stats?.out_of_stock_total ?? 0} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card loading={loading}>
            <Statistic title="分类总数" value={stats?.category_total ?? 0} />
          </Card>
        </Col>
      </Row>

      <PanelGrid>
        <Card title="商品状态分布" loading={loading}>
          {(stats?.status_distribution ?? []).map(item => {
            const percent = stats?.product_total ? Math.round((item.count / stats.product_total) * 100) : 0;
            return (
              <StatusRow key={item.status}>
                <span>{saleStatusMap[item.status]}</span>
                <Progress percent={percent} size="small" />
              </StatusRow>
            );
          })}
        </Card>
        <Card title="分类商品数 Top 8" loading={loading}>
          <Table
            rowKey="category_id"
            dataSource={stats?.top_categories ?? []}
            pagination={false}
            size="small"
            columns={[
              { title: '分类', dataIndex: 'category_name' },
              { title: '商品数量', dataIndex: 'product_count', width: 120 },
            ]}
          />
        </Card>
        <Card title="热门商品 Top 10" loading={loading}>
          <Table
            rowKey="id"
            dataSource={stats?.top_hot_products ?? []}
            pagination={false}
            size="small"
            columns={[
              { title: '商品名称', dataIndex: 'name' },
              { title: '热度', dataIndex: 'hot_score', width: 90 },
              { title: '库存', dataIndex: 'stock', width: 90 },
              {
                title: '状态',
                dataIndex: 'status',
                width: 110,
                render: (_, row) => <Tag color={row.status === 'on_sale' ? 'green' : 'default'}>{saleStatusMap[row.status]}</Tag>,
              },
            ]}
          />
        </Card>
      </PanelGrid>
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1240px;
  margin: 0 auto;
`;

const PanelGrid = styled.div`
  margin-top: 16px;
  display: grid;
  gap: 16px;
`;

const StatusRow = styled.div`
  margin-bottom: 12px;
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 10px;
  align-items: center;
`;

export default Dashboard;
