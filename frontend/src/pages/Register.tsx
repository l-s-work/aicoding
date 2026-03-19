import { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, MailOutlined, LockOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { post } from '../utils/request';

/** 注册表单请求体 */
interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

/** 注册表单 UI 字段 */
interface RegisterFormValues extends RegisterRequest {
  confirmPassword: string;
}

/** 注册成功后返回用户信息 */
interface RegisterResponse {
  id: number;
  username: string;
  email: string;
  role: 'client' | 'admin';
  created_at: string;
}

/**
 * 注册页面
 *
 * 功能：
 * - 调用后端 POST /auth/register 创建账号
 * - 前端二次校验密码确认
 * - 成功后跳回登录页，继续登录流程
 */
const Register = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (values: RegisterFormValues) => {
    setLoading(true);
    try {
      const payload: RegisterRequest = {
        username: values.username,
        email: values.email,
        password: values.password,
      };
      const response = await post<RegisterResponse>('/auth/register', payload);

      message.success(`账号创建成功：${response.username}，请登录`);
      navigate('/login', { replace: true });
    } catch (error) {
      message.error(error instanceof Error ? error.message : '注册失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageContainer>
      <AuthCard>
        <Title>创建账号</Title>
        <Subtitle>注册后即可开始使用 AI 电商平台</Subtitle>

        <Form name="register" onFinish={handleSubmit} autoComplete="off" size="large">
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
            <Input prefix={<MailOutlined />} placeholder="请输入邮箱" autoComplete="email" />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, message: '密码至少8位' },
              { max: 20, message: '密码最多20位' },
              {
                pattern: /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*?&]{8,20}$/,
                message: '密码必须同时包含字母和数字',
              },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码（8-20位，需包含字母和数字）" autoComplete="new-password" />
          </Form.Item>

          <Form.Item
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请再次输入密码' },
              ({ getFieldValue }) => ({
                validator(_, value: string) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请再次输入密码" autoComplete="new-password" />
          </Form.Item>

          <Form.Item>
            <SubmitButton type="primary" htmlType="submit" loading={loading} block>
              注册账号
            </SubmitButton>
          </Form.Item>
        </Form>

        <BottomNav>
          <AuthLink to="/login">已有账号？去登录</AuthLink>
          <AuthLink to="/forgot-password">忘记密码</AuthLink>
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
  background: linear-gradient(140deg, #ffe8d2 0%, #ffd8bf 45%, #ffc8b7 100%);
`;

const AuthCard = styled.div`
  width: 100%;
  max-width: 460px;
  padding: 40px 36px;
  background: #ffffff;
  border-radius: 14px;
  box-shadow: 0 14px 40px rgba(191, 80, 16, 0.18);
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

export default Register;
