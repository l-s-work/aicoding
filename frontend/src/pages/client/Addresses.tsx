import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, Modal, Popconfirm, Space, Switch, Table, Tag, message } from 'antd';
import styled from 'styled-components';
import { del, get, post, put } from '@/utils/request';
import ClientPageHeader from '@/components/Layout/ClientPageHeader';

interface AddressItem {
  id: number;
  user_id: number;
  receiver_name: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  detail_address: string;
  is_default: number;
  created_at: string;
}

interface AddressFormValues {
  receiver_name: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  detail_address: string;
  is_default: boolean;
}

const Addresses = () => {
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [addresses, setAddresses] = useState<AddressItem[]>([]);
  const [editingAddress, setEditingAddress] = useState<AddressItem | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm<AddressFormValues>();

  const fetchAddresses = async () => {
    setLoading(true);
    try {
      const data = await get<AddressItem[]>('/addresses');
      setAddresses(data);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '地址加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchAddresses();
  }, []);

  const openCreateModal = () => {
    setEditingAddress(null);
    form.resetFields();
    form.setFieldsValue({ is_default: false });
    setModalOpen(true);
  };

  const openEditModal = (address: AddressItem) => {
    setEditingAddress(address);
    form.setFieldsValue({
      receiver_name: address.receiver_name,
      phone: address.phone,
      province: address.province,
      city: address.city,
      district: address.district,
      detail_address: address.detail_address,
      is_default: address.is_default === 1,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const payload = {
        receiver_name: values.receiver_name.trim(),
        phone: values.phone.trim(),
        province: values.province.trim(),
        city: values.city.trim(),
        district: values.district.trim(),
        detail_address: values.detail_address.trim(),
        is_default: values.is_default ? 1 : 0,
      };

      if (editingAddress) {
        await put(`/addresses/${editingAddress.id}`, payload);
        message.success('地址更新成功');
      } else {
        await post('/addresses', payload);
        message.success('地址创建成功');
      }

      setModalOpen(false);
      await fetchAddresses();
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSetDefault = async (id: number) => {
    try {
      await post(`/addresses/${id}/set-default`);
      message.success('默认地址已更新');
      await fetchAddresses();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '设置默认地址失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/addresses/${id}`);
      message.success('地址删除成功');
      await fetchAddresses();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '地址删除失败');
    }
  };

  return (
    <ContentWrap>
      <ClientPageHeader title="地址管理" fallbackPath="/" />
      <Card
        extra={
          <Button type="primary" onClick={openCreateModal}>
            新增地址
          </Button>
        }
      >
        <Table
          rowKey="id"
          loading={loading}
          dataSource={addresses}
          pagination={false}
          columns={[
            { title: '收货人', dataIndex: 'receiver_name', width: 110 },
            { title: '手机号', dataIndex: 'phone', width: 130 },
            {
              title: '地址',
              render: (_, row) => `${row.province} ${row.city} ${row.district} ${row.detail_address}`,
            },
            {
              title: '默认',
              width: 90,
              render: (_, row) => (row.is_default === 1 ? <Tag color="green">默认</Tag> : '-'),
            },
            {
              title: '操作',
              width: 220,
              render: (_, row) => (
                <Space>
                  <Button type="link" onClick={() => openEditModal(row)}>
                    编辑
                  </Button>
                  <Button type="link" disabled={row.is_default === 1} onClick={() => void handleSetDefault(row.id)}>
                    设为默认
                  </Button>
                  <Popconfirm
                    title="确认删除该地址？"
                    description="删除后不可恢复"
                    okText="确认删除"
                    cancelText="取消"
                    onConfirm={() => void handleDelete(row.id)}
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
      </Card>

      <Modal
        title={editingAddress ? '编辑地址' : '新增地址'}
        open={modalOpen}
        onOk={() => void handleSubmit()}
        onCancel={() => setModalOpen(false)}
        okButtonProps={{ loading: submitting }}
        destroyOnClose
      >
        <Form form={form} layout="vertical" initialValues={{ is_default: false }}>
          <Form.Item label="收货人" name="receiver_name" rules={[{ required: true, message: '请输入收货人姓名' }]}>
            <Input maxLength={50} />
          </Form.Item>
          <Form.Item label="手机号" name="phone" rules={[{ required: true, message: '请输入手机号' }]}>
            <Input maxLength={11} />
          </Form.Item>
          <AddressRow>
            <Form.Item label="省份" name="province" rules={[{ required: true, message: '请输入省份' }]}>
              <Input maxLength={50} />
            </Form.Item>
            <Form.Item label="城市" name="city" rules={[{ required: true, message: '请输入城市' }]}>
              <Input maxLength={50} />
            </Form.Item>
            <Form.Item label="区县" name="district" rules={[{ required: true, message: '请输入区县' }]}>
              <Input maxLength={50} />
            </Form.Item>
          </AddressRow>
          <Form.Item label="详细地址" name="detail_address" rules={[{ required: true, message: '请输入详细地址' }]}>
            <Input.TextArea rows={2} maxLength={200} />
          </Form.Item>
          <Form.Item label="设为默认地址" name="is_default" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1080px;
  width: 100%;
  margin: 0 auto;
`;

const AddressRow = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
`;

export default Addresses;
