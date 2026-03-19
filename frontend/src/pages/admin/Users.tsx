import { useEffect, useState } from 'react';
import { Button, Input, Modal, Select, Space, Table, Tag, Typography, message } from 'antd';
import styled from 'styled-components';
import { get, patch, post } from '@/utils/request';

const { Title } = Typography;

interface UserItem {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: number;
  created_at: string;
}

interface UserListResponse {
  total: number;
  items: UserItem[];
}

const Users = () => {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [keyword, setKeyword] = useState('');
  const [isActive, setIsActive] = useState<number | undefined>(undefined);
  const [loading, setLoading] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await get<UserListResponse>('/admin/users', {
        params: {
          page,
          page_size: pageSize,
          keyword: keyword || undefined,
          is_active: isActive,
        },
      });
      setUsers(data.items);
      setTotal(data.total);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '用户数据加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchUsers();
  }, [page, pageSize, keyword, isActive]);

  const handleToggleStatus = async (row: UserItem) => {
    const nextStatus = row.is_active === 1 ? 0 : 1;
    try {
      await patch(`/admin/users/${row.id}/status`, { is_active: nextStatus });
      message.success(nextStatus === 1 ? '已解封用户' : '已封禁用户');
      await fetchUsers();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '操作失败');
    }
  };

  const handleResetPassword = async (row: UserItem) => {
    let pwd = '';
    Modal.confirm({
      title: `重置密码：${row.username}`,
      content: (
        <Input.Password
          placeholder="输入新密码（8-20位，需字母+数字）"
          onChange={e => {
            pwd = e.target.value;
          }}
        />
      ),
      onOk: async () => {
        try {
          await post(`/admin/users/${row.id}/reset-password`, { new_password: pwd });
          message.success('密码重置成功');
        } catch (error) {
          message.error(error instanceof Error ? error.message : '密码重置失败');
        }
      },
    });
  };

  return (
    <ContentWrap>
      <Title level={3}>用户管理</Title>
      <Space wrap style={{ marginBottom: 14 }}>
        <Input.Search
          allowClear
          style={{ width: 250 }}
          placeholder="用户名/邮箱模糊搜索"
          onSearch={value => {
            setPage(1);
            setKeyword(value.trim());
          }}
        />
        <Select
          allowClear
          style={{ width: 180 }}
          placeholder="账号状态筛选"
          value={isActive}
          onChange={value => {
            setPage(1);
            setIsActive(value);
          }}
          options={[
            { label: '正常', value: 1 },
            { label: '封禁', value: 0 },
          ]}
        />
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={users}
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
          { title: '用户名', dataIndex: 'username' },
          { title: '邮箱', dataIndex: 'email' },
          { title: '角色', dataIndex: 'role', width: 120 },
          {
            title: '状态',
            render: (_, row) => <Tag color={row.is_active === 1 ? 'green' : 'red'}>{row.is_active === 1 ? '正常' : '封禁'}</Tag>,
          },
          { title: '创建时间', dataIndex: 'created_at' },
          {
            title: '操作',
            render: (_, row) => (
              <Space>
                {row.role !== 'admin' && (
                  <Button size="small" onClick={() => void handleToggleStatus(row)}>
                    {row.is_active === 1 ? '封禁' : '解封'}
                  </Button>
                )}
                <Button size="small" onClick={() => void handleResetPassword(row)}>
                  重置密码
                </Button>
              </Space>
            ),
          },
        ]}
      />
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 1240px;
  margin: 0 auto;
`;

export default Users;
