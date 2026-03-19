import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Cascader, Form, Input, InputNumber, Select, Space, Typography, Upload, message } from 'antd';
import type { UploadFile, UploadProps } from 'antd/es/upload/interface';
import { ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import styled from 'styled-components';
import { get, post, put, upload } from '@/utils/request';
import { buildCategoryCascaderOptions, type CategoryNode } from '@/utils/category';

const { Title, Text } = Typography;

interface ProductDetail {
  id: number;
  name: string;
  description: string | null;
  price: number;
  stock: number;
  status: 'on_sale' | 'off_sale';
  hot_score: number;
  image_url: string | null;
  category_id: number | null;
}

interface ProductFormValues {
  name: string;
  description?: string;
  price: number;
  stock: number;
  status: 'on_sale' | 'off_sale';
  hot_score: number;
  category_path: number[];
  image_url?: string;
}

const buildCategoryIdPathMap = (
  nodes: CategoryNode[],
  parentPath: number[] = [],
  output: Map<number, number[]> = new Map()
): Map<number, number[]> => {
  for (const node of nodes) {
    const path = [...parentPath, node.id];
    output.set(node.id, path);
    buildCategoryIdPathMap(node.children ?? [], path, output);
  }
  return output;
};

const ProductEditor = () => {
  const navigate = useNavigate();
  const params = useParams<{ id: string }>();
  const parsedId = params.id ? Number(params.id) : NaN;
  const editingId = Number.isFinite(parsedId) ? parsedId : null;
  const isEditMode = editingId !== null;

  const [form] = Form.useForm<ProductFormValues>();
  const [categories, setCategories] = useState<CategoryNode[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [pageLoading, setPageLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [imageUrl, setImageUrl] = useState<string>('');

  const categoryOptions = useMemo(() => buildCategoryCascaderOptions(categories), [categories]);
  const categoryIdPathMap = useMemo(() => buildCategoryIdPathMap(categories), [categories]);

  const uploadFileList = useMemo<UploadFile[]>(
    () =>
      imageUrl
        ? [
            {
              uid: '-1',
              name: imageUrl.split('/').pop() || 'image',
              status: 'done',
              url: imageUrl,
            },
          ]
        : [],
    [imageUrl]
  );

  const fetchCategories = async () => {
    const data = await get<CategoryNode[]>('/products/categories');
    setCategories(data);
  };

  const fetchProductDetail = async (id: number) => {
    const data = await get<ProductDetail>(`/products/${id}`);
    const categoryPath = data.category_id ? categoryIdPathMap.get(data.category_id) ?? [] : [];

    form.setFieldsValue({
      name: data.name,
      description: data.description ?? '',
      price: data.price,
      stock: data.stock,
      status: data.status,
      hot_score: data.hot_score,
      category_path: categoryPath,
      image_url: data.image_url ?? undefined,
    });
    setImageUrl(data.image_url ?? '');
  };

  useEffect(() => {
    const initPage = async () => {
      setPageLoading(true);
      try {
        await fetchCategories();
      } catch (error) {
        message.error(error instanceof Error ? error.message : '分类加载失败');
      } finally {
        setPageLoading(false);
      }
    };
    void initPage();
  }, []);

  useEffect(() => {
    // 分类加载完成后再回填编辑数据，确保可正确匹配级联路径
    if (!isEditMode || !editingId || categories.length === 0) return;
    const loadDetail = async () => {
      setPageLoading(true);
      try {
        await fetchProductDetail(editingId);
      } catch (error) {
        message.error(error instanceof Error ? error.message : '商品详情加载失败');
      } finally {
        setPageLoading(false);
      }
    };
    void loadDetail();
  }, [isEditMode, editingId, categories]);

  const handleUploadImage: UploadProps['customRequest'] = async options => {
    const file = options.file;
    if (!(file instanceof File)) {
      options.onError?.(new Error('无效的上传文件'));
      return;
    }

    setUploading(true);
    try {
      const data = await upload<{ url: string }>('/products/upload-image', file);
      setImageUrl(data.url);
      form.setFieldValue('image_url', data.url);
      options.onSuccess?.(data);
      message.success('图片上传成功');
    } catch (error) {
      const uploadError = error instanceof Error ? error : new Error('图片上传失败');
      options.onError?.(uploadError);
      message.error(uploadError.message);
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const values = await form.validateFields();
      const payload = {
        name: values.name.trim(),
        description: values.description?.trim() || null,
        price: values.price,
        stock: values.stock,
        status: values.status,
        hot_score: values.hot_score ?? 0,
        category_id: values.category_path[values.category_path.length - 1],
        image_url: values.image_url || null,
      };

      if (isEditMode && editingId) {
        await put(`/products/${editingId}`, payload);
        message.success('商品更新成功');
      } else {
        await post('/products', payload);
        message.success('商品创建成功');
      }

      navigate('/admin/products', { replace: true });
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ContentWrap>
      <TopBar>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/admin/products')}>
          返回商品列表
        </Button>
        <Title level={3} style={{ margin: 0 }}>
          {isEditMode ? '编辑商品' : '新建商品'}
        </Title>
      </TopBar>

      <Card loading={pageLoading}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            status: 'on_sale',
            hot_score: 0,
            stock: 0,
            price: 0,
          }}
        >
          <Form.Item label="商品名称" name="name" rules={[{ required: true, message: '请输入商品名称' }]}>
            <Input maxLength={200} placeholder="请输入商品名称" />
          </Form.Item>

          <Form.Item label="商品描述" name="description">
            <Input.TextArea rows={4} placeholder="请输入商品描述（可选）" />
          </Form.Item>

          <InlineGrid>
            <Form.Item label="价格" name="price" rules={[{ required: true, message: '请输入价格' }]}>
              <InputNumber min={0} precision={2} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="库存" name="stock" rules={[{ required: true, message: '请输入库存' }]}>
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="热度" name="hot_score">
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </InlineGrid>

          <InlineGrid>
            <Form.Item
              label="商品分类（必须三级）"
              name="category_path"
              rules={[
                { required: true, message: '请选择三级分类' },
                {
                  validator: (_, value: number[] | undefined) => {
                    if (!value || value.length !== 3) {
                      return Promise.reject(new Error('必须选择到三级分类'));
                    }
                    return Promise.resolve();
                  },
                },
              ]}
            >
              <Cascader options={categoryOptions} changeOnSelect placeholder="请选择一级/二级/三级分类" />
            </Form.Item>

            <Form.Item label="状态" name="status">
              <Select
                options={[
                  { label: '在售', value: 'on_sale' },
                  { label: '下架', value: 'off_sale' },
                ]}
              />
            </Form.Item>
          </InlineGrid>

          <Form.Item label="商品图片（单图上传）">
            <Space direction="vertical" style={{ width: '100%' }} size={8}>
              <Upload
                listType="picture-card"
                maxCount={1}
                accept="image/*"
                customRequest={handleUploadImage}
                fileList={uploadFileList}
                onRemove={() => {
                  setImageUrl('');
                  form.setFieldValue('image_url', undefined);
                  return true;
                }}
              >
                {uploadFileList.length >= 1 ? null : (
                  <UploadTrigger>
                    <PlusOutlined />
                    <span>上传图片</span>
                  </UploadTrigger>
                )}
              </Upload>
              <Text type="secondary">支持 JPG/PNG/WEBP/GIF，单图最大 5MB</Text>
              {imageUrl ? <PreviewImage src={imageUrl} alt="商品图片预览" /> : null}
            </Space>
          </Form.Item>
          <Form.Item name="image_url" hidden>
            <Input />
          </Form.Item>

          <ActionRow>
            <Space>
              <Button onClick={() => navigate('/admin/products')}>取消</Button>
              <Button type="primary" loading={submitting || uploading} onClick={() => void handleSubmit()}>
                {isEditMode ? '保存修改' : '创建商品'}
              </Button>
            </Space>
          </ActionRow>
        </Form>
      </Card>
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 980px;
  margin: 0 auto;
`;

const TopBar = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  gap: 12px;
`;

const InlineGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
`;

const UploadTrigger = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
`;

const PreviewImage = styled.img`
  width: 180px;
  height: 180px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
`;

const ActionRow = styled.div`
  display: flex;
  justify-content: flex-end;
`;

export default ProductEditor;
