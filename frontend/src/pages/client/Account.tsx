import { useEffect } from 'react';
import { Button, Card, Form, Input, Space, message } from 'antd';
import styled from 'styled-components';
import useAuthStore, { type UserInfo } from '@/store/useAuthStore';
import { get, post, put } from '@/utils/request';
import ClientPageHeader from '@/components/Layout/ClientPageHeader';

const Account = () => {
  const { setUser, logout } = useAuthStore();
  const [profileForm] = Form.useForm<{ username: string; email: string; role: string }>();
  const [passwordForm] = Form.useForm<{ current_password: string; new_password: string; confirm_password: string }>();

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

  const fetchUserInfo = async () => {
    try {
      const data = await get<UserInfo>('/auth/me');
      setUser(data);
      profileForm.setFieldsValue({
        username: data.username,
        email: data.email,
        role: data.role,
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : '用户信息加载失败');
    }
  };

  useEffect(() => {
    void fetchUserInfo();
  }, []);

  const handleUpdateProfile = async () => {
    try {
      const values = await profileForm.validateFields();
      const data = await put<UserInfo>('/auth/me', {
        username: values.username.trim(),
        email: values.email.trim(),
      });
      setUser(data);
      profileForm.setFieldsValue({
        username: data.username,
        email: data.email,
        role: data.role,
      });
      message.success('账号信息已更新');
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    }
  };

  const handleChangePassword = async () => {
    try {
      const values = await passwordForm.validateFields();
      await post('/auth/change-password', {
        current_password: values.current_password,
        new_password: values.new_password,
      });
      message.success('密码修改成功，请重新登录');
      logout();
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    }
  };

  return (
    <ContentWrap>
      <ClientPageHeader title="我的账号信息" fallbackPath="/" />

      <Card title="账号资料">
        <Form form={profileForm} layout="vertical">
          <Form.Item
            label="用户名"
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, max: 50, message: '用户名长度需在 3-50 之间' },
              { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名仅支持字母、数字、下划线' },
            ]}
          >
            <Input maxLength={50} />
          </Form.Item>
          <Form.Item
            label="邮箱"
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '邮箱格式不正确' },
            ]}
          >
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item label="角色（不可修改）" name="role">
            <Input disabled />
          </Form.Item>
          <Space>
            <Button type="primary" onClick={() => void handleUpdateProfile()}>
              保存账号信息
            </Button>
          </Space>
        </Form>
      </Card>

      <Card title="修改密码" style={{ marginTop: 16 }}>
        <Form form={passwordForm} layout="vertical">
          <Form.Item label="当前密码" name="current_password" rules={[{ required: true, message: '请输入当前密码' }]}>
            <Input.Password maxLength={20} />
          </Form.Item>
          <Form.Item
            label="新密码"
            name="new_password"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 8, max: 20, message: '新密码长度需在 8-20 之间' },
              { pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/, message: '新密码必须同时包含字母和数字' },
            ]}
          >
            <Input.Password maxLength={20} />
          </Form.Item>
          <Form.Item
            label="确认新密码"
            name="confirm_password"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value: string) {
                  if (!value || getFieldValue('new_password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的新密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password maxLength={20} />
          </Form.Item>
          <Space>
            <Button type="primary" danger onClick={() => void handleChangePassword()}>
              修改密码并重新登录
            </Button>
            <Button danger onClick={handleLogoutAll}>
              退出所有设备
            </Button>
          </Space>
        </Form>
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
