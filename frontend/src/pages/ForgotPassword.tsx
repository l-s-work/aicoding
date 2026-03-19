import { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, MailOutlined, LockOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { post } from '../utils/request';

/** 忘记密码接口请求体 */
interface ForgotPasswordRequest {
  username: string;
  email: string;
  new_password: string;
}

/** 忘记密码表单字段 */
interface ForgotPasswordFormValues {
  username: string;
  email: string;
  newPassword: string;
  confirmPassword: string;
}

/**
 * 忘记密码页面
 *
 * 功能：
 * - 用户通过「用户名 + 邮箱」校验身份
 * - 调用后端 POST /auth/forgot-password 重置密码
 * - 成功后引导回登录页
 */
const ForgotPassword = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (values: ForgotPasswordFormValues) => {
    setLoading(true);
    try {
      const payload: ForgotPasswordRequest = {
        username: values.username,
        email: values.email,
        new_password: values.newPassword,
      };

      await post<void>('/auth/forgot-password', payload);
      message.success('密码已重置，请使用新密码登录');
      navigate('/login', { replace: true });
    } catch (error) {
      message.error(error instanceof Error ? error.message : '重置失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageContainer>
      <AuthCard>
        <Title>找回密码</Title>
        <Subtitle>通过账号信息重置登录密码</Subtitle>

        <Form name="forgot-password" onFinish={handleSubmit} autoComplete="off" size="large">
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
              { max: 50, message: '用户名最多50个字符' },
              { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="请输入用户名" autoComplete="username" />
          </Form.Item>

          <Form.Item
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '邮箱格式不正确' },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder="请输入注册邮箱" autoComplete="email" />
          </Form.Item>

          <Form.Item
            name="newPassword"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 8, message: '新密码至少8位' },
              { max: 20, message: '新密码最多20位' },
              {
                pattern: /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*?&]{8,20}$/,
                message: '新密码必须同时包含字母和数字',
              },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请输入新密码（8-20位，需包含字母和数字）" autoComplete="new-password" />
          </Form.Item>

          <Form.Item
            name="confirmPassword"
            dependencies={['newPassword']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value: string) {
                  if (!value || getFieldValue('newPassword') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的新密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请再次输入新密码" autoComplete="new-password" />
          </Form.Item>

          <Form.Item>
            <SubmitButton type="primary" htmlType="submit" loading={loading} block>
              重置密码
            </SubmitButton>
          </Form.Item>
        </Form>

        <BottomNav>
          <AuthLink to="/login">返回登录</AuthLink>
          <AuthLink to="/register">还没账号？去注册</AuthLink>
        </BottomNav>
      </AuthCard>
    </PageContainer>
  );
};

const PageContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 24px;
  background: linear-gradient(150deg, #dff2ff 0%, #cce6ff 45%, #b6d9ff 100%);
`;

const AuthCard = styled.div`
  width: 100%;
  max-width: 460px;
  padding: 40px 36px;
  background: #ffffff;
  border-radius: 14px;
  box-shadow: 0 14px 40px rgba(0, 53, 128, 0.18);
`;

const Title = styled.h1`
  margin: 0 0 8px;
  text-align: center;
  font-size: 30px;
  color: #1f1f1f;
`;

const Subtitle = styled.p`
  margin: 0 0 28px;
  text-align: center;
  color: #8c8c8c;
  font-size: 14px;
`;

const SubmitButton = styled(Button)`
  height: 46px;
  font-size: 16px;
  font-weight: 500;
`;

const BottomNav = styled.div`
  margin-top: 6px;
  display: flex;
  justify-content: space-between;
`;

const AuthLink = styled(Link)`
  font-size: 14px;
  text-decoration: none;
  color: #1677ff;

  &:hover {
    color: #4096ff;
    text-decoration: underline;
  }
`;

export default ForgotPassword;
