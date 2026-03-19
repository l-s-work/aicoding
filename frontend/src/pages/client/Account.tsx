import { useMemo } from 'react';
import { Button, Card, Descriptions, Space, Typography, message } from 'antd';
import styled from 'styled-components';
import useAuthStore from '@/store/useAuthStore';
import { post } from '@/utils/request';

const { Title } = Typography;

const Account = () => {
  const { user, logout } = useAuthStore();
  const createdAt = useMemo(() => new Date().toLocaleString(), []);

  const handleLogoutAll = async () => {
    try {
      await post('/auth/logout-all');
      message.success('已退出所有设备');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '操作失败');
    } finally {
      logout();
    }
  };

  return (
    <ContentWrap>
      <Title level={3}>我的账号信息</Title>
      <Card>
        <Descriptions bordered column={1}>
          <Descriptions.Item label="用户名">{user?.username ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="邮箱">{user?.email ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="角色">{user?.role ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="最近登录时间">{createdAt}</Descriptions.Item>
        </Descriptions>
        <Space style={{ marginTop: 16 }}>
          <Button danger onClick={handleLogoutAll}>
            退出所有设备
          </Button>
        </Space>
      </Card>
    </ContentWrap>
  );
};

const ContentWrap = styled.div`
  max-width: 880px;
  width: 100%;
  margin: 0 auto;
`;

export default Account;
