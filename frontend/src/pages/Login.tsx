import { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import styled from 'styled-components';
import useAuthStore from '../store/useAuthStore';
import { post } from '../utils/request';

/** 登录请求体 */
interface LoginRequest {
  username: string;
  password: string;
}

/** 登录响应数据 */
interface LoginResponse {
  access_token: string;
  user: {
    id: number;
    username: string;
    email: string;
    role: 'client' | 'admin';
  };
}

/**
 * 登录页面组件
 *
 * 功能：
 * - 用户名密码表单验证
 * - 调用后端 POST /auth/login 接口
 * - 成功后存储 Token 到 Zustand（自动持久化到 localStorage）
 * - 自动跳转到登录前访问的页面或默认首页
 * - 失败时显示后端返回的错误信息（包括锁定提示）
 */
const Login = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuthStore();
  const [loading, setLoading] = useState(false);

  // 获取登录前用户尝试访问的页面（从 PrivateRoute 传递的 state）
  const from = (location.state as { from?: string })?.from || '/';

  /**
   * 表单提交处理
   * - 失败5次后账号会被临时锁定10分钟（后端自动处理）
   * - 成功后解析 Token 和用户信息，调用 Zustand 登录方法
   */
  const handleSubmit = async (values: LoginRequest) => {
    setLoading(true);

    try {
      const response = await post<LoginResponse>('/auth/login', values);

      // 存储 Access Token 和用户信息到 Zustand（自动持久化）
      login(response.access_token, response.user);

      message.success(`欢迎回来，${response.user.username}！`);

      // 跳转到登录前访问的页面，避免用户重复导航
      navigate(from, { replace: true });
    } catch (error) {
      // 后端错误信息已通过 Axios 拦截器处理，直接展示
      message.error(error instanceof Error ? error.message : '登录失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <LoginContainer>
      <LoginCard>
        <Title>AI 电商平台</Title>
        <Subtitle>欢迎登录</Subtitle>

        <Form name="login" onFinish={handleSubmit} autoComplete="off" size="large">
          {/* 用户名输入框 */}
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
              { max: 20, message: '用户名最多20个字符' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="请输入用户名" autoComplete="username" />
          </Form.Item>

          {/* 密码输入框 */}
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
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码（8-20位，需包含字母和数字）" autoComplete="current-password" />
          </Form.Item>

          {/* 登录按钮 */}
          <Form.Item>
            <LoginButton type="primary" htmlType="submit" loading={loading} block>
              登录
            </LoginButton>
          </Form.Item>
        </Form>

        {/* 开发期提示信息 */}
        <DevHint>
          <p>💡 开发测试账号：</p>
          <p>管理员：admin / admin123</p>
          <p>⚠️ 连续登录失败 5 次将锁定 10 分钟</p>
        </DevHint>
      </LoginCard>
    </LoginContainer>
  );
};

// ===== Styled Components（禁止使用 Tailwind） =====

/** 页面容器：全屏居中布局 */
const LoginContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
`;

/** 登录卡片：白色圆角卡片，带阴影 */
const LoginCard = styled.div`
  width: 100%;
  max-width: 400px;
  padding: 48px 40px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
`;

/** 标题 */
const Title = styled.h1`
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
  text-align: center;
`;

/** 副标题 */
const Subtitle = styled.p`
  margin: 0 0 32px;
  font-size: 14px;
  color: #8c8c8c;
  text-align: center;
`;

/** 登录按钮：增强视觉权重 */
const LoginButton = styled(Button)`
  height: 48px;
  font-size: 16px;
  font-weight: 500;
  margin-top: 8px;
`;

/** 开发提示信息：浅灰色提示框 */
const DevHint = styled.div`
  margin-top: 24px;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.8;
  color: #595959;

  p {
    margin: 0;
  }

  p:first-child {
    font-weight: 500;
    margin-bottom: 4px;
  }
`;

export default Login;
