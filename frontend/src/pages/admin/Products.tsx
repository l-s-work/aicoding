import { useEffect, useMemo, useState } from 'react';
import { Button, Cascader, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, Typography, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { get, post } from '@/utils/request';
import { formatAmount, saleStatusMap } from '@/utils/dataformat';
import { buildCategoryCascaderOptions, buildCategoryPathMap, type CategoryNode } from '@/utils/category';

const { Title } = Typography;

interface ProductItem {
  id: number;
  name: string;
  price: number;
  stock: number;
  status: 'on_sale' | 'off_sale';
  hot_score: number;
  image_url?: string | null;
  category?: { id: number; name: string; level: number };
}

interface ProductListResponse {
  total: number;
  items: ProductItem[];
}

interface CategoryCreateFormValues {
  name: string;
  parent_path?: number[];
  sort_order: number;
}

const Products = () => {
  const navigate = useNavigate();
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<CategoryNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const [status, setStatus] = useState<'on_sale' | 'off_sale' | undefined>(undefined);
  const [keyword, setKeyword] = useState('');
  const [level, setLevel] = useState<number | undefined>(undefined);
  // 多选分类：每项都是完整级联路径（如 [1, 3, 9]）
  const [categoryPaths, setCategoryPaths] = useState<number[][]>([]);

  const [categoryModalOpen, setCategoryModalOpen] = useState(false);
  const [categoryForm] = Form.useForm<CategoryCreateFormValues>();

  const categoryPathMap = useMemo(() => buildCategoryPathMap(categories), [categories]);
  const categoryFilterOptions = useMemo(() => buildCategoryCascaderOptions(categories), [categories]);
  const parentCategoryOptions = useMemo(() => buildCategoryCascaderOptions(categories, 2), [categories]);

  const selectedCategoryIds = useMemo(() => {
    const leafIds = categoryPaths
      .map(path => path[path.length - 1])
      .filter((id): id is number => typeof id === 'number');
    return Array.from(new Set(leafIds));
  }, [categoryPaths]);

  const fetchCategories = async () => {
    try {
      const data = await get<CategoryNode[]>('/products/categories');
      setCategories(data);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '分类加载失败');
    }
  };

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const data = await get<ProductListResponse>('/products', {
        params: {
          page,
          page_size: pageSize,
          status,
          keyword: keyword || undefined,
          level,
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
  }, [page, pageSize, status, keyword, level, selectedCategoryIds]);

  const createCategory = async () => {
    try {
      const values = await categoryForm.validateFields();
      const parentPath = values.parent_path ?? [];
      const payload = {
        name: values.name,
        parent_id: parentPath.length > 0 ? parentPath[parentPath.length - 1] : undefined,
        sort_order: values.sort_order ?? 0,
      };
      await post('/products/categories', payload);
      message.success('分类创建成功');
      setCategoryModalOpen(false);
      categoryForm.resetFields();
      await fetchCategories();
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    }
  };

  return (
    <ContentWrap>
      <Title level={3}>商品管理</Title>
      <Toolbar>
        <FilterRow>
          <FilterItem>
            <FilterLabel>关键词</FilterLabel>
            <Input.Search
              placeholder="按商品名称模糊搜索"
              allowClear
              style={{ width: 240 }}
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
              style={{ width: 150 }}
              placeholder="请选择状态"
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
          <FilterItem>
            <FilterLabel>层级</FilterLabel>
            <Select
              allowClear
              style={{ width: 150 }}
              placeholder="请选择层级"
              value={level}
              onChange={value => {
                setPage(1);
                setLevel(value);
              }}
              options={[
                { label: '一级', value: 1 },
                { label: '二级', value: 2 },
                { label: '三级', value: 3 },
              ]}
            />
          </FilterItem>
          <FilterItem>
            <FilterLabel>分类</FilterLabel>
            <Cascader
              allowClear
              style={{ width: 300 }}
              placeholder="请选择分类（支持多选）"
              options={categoryFilterOptions}
              multiple
              value={categoryPaths}
              onChange={value => {
                setPage(1);
                const nextPaths = ((value as Array<Array<string | number>>) ?? []).map(path => path.map(id => Number(id)));
                setCategoryPaths(nextPaths);
              }}
            />
          </FilterItem>
        </FilterRow>
        <Space>
          <Button onClick={() => setCategoryModalOpen(true)}>新建分类</Button>
          <Button type="primary" onClick={() => navigate('/admin/products/new')}>
            新建商品
          </Button>
        </Space>
      </Toolbar>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={products}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (current, size) => {
            setPage(current);
            setPageSize(size);
          },
        }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 80 },
          { title: '商品名称', dataIndex: 'name', width: 220 },
          {
            title: '一级分类',
            render: (_, row) => (row.category?.id ? categoryPathMap.get(row.category.id)?.[0] ?? '-' : '-'),
            width: 130,
          },
          {
            title: '二级分类',
            render: (_, row) => (row.category?.id ? categoryPathMap.get(row.category.id)?.[1] ?? '-' : '-'),
            width: 130,
          },
          {
            title: '三级分类',
            render: (_, row) => (row.category?.id ? categoryPathMap.get(row.category.id)?.[2] ?? '-' : '-'),
            width: 140,
          },
          { title: '价格', render: (_, row) => formatAmount(row.price), width: 120 },
          { title: '库存', dataIndex: 'stock', width: 90 },
          { title: '热度', dataIndex: 'hot_score', width: 90 },
          {
            title: '状态',
            width: 100,
            render: (_, row) => <Tag color={row.status === 'on_sale' ? 'green' : 'default'}>{saleStatusMap[row.status]}</Tag>,
          },
          {
            title: '操作',
            width: 120,
            render: (_, row) => (
              <Button type="link" onClick={() => navigate(`/admin/products/${row.id}/edit`)}>
                编辑
              </Button>
            ),
          },
        ]}
        scroll={{ x: 1280 }}
      />

      <Modal
        title="新建分类"
        open={categoryModalOpen}
        onOk={() => void createCategory()}
        onCancel={() => setCategoryModalOpen(false)}
        destroyOnClose
      >
        <Form form={categoryForm} layout="vertical" initialValues={{ sort_order: 0 }}>
          <Form.Item label="分类名称" name="name" rules={[{ required: true, message: '请输入分类名称' }]}>
            <Input placeholder="例如：智能手机" />
          </Form.Item>
          <Form.Item label="父级分类（可选一级/二级）" name="parent_path">
            <Cascader
              allowClear
              changeOnSelect
              options={parentCategoryOptions}
              placeholder="不选则创建一级分类"
            />
          </Form.Item>
          <Form.Item label="排序权重" name="sort_order">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1320px;
  margin: 0 auto;
`;

const Toolbar = styled.div`
  margin-bottom: 14px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
`;

const FilterRow = styled(Space)`
  display: flex;
  flex-wrap: wrap;
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

export default Products;
