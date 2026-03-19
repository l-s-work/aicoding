import { Alert, Button, Result, Space, Typography } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';
import styled from 'styled-components';

const { Text } = Typography;

/** 从本地持久化状态中读取当前角色，避免 C 端用户看到无效后台入口 */
function getCurrentRole(): 'admin' | 'client' | null {
  try {
    const raw = localStorage.getItem('auth-storage');
    if (!raw) return null;
    const role = JSON.parse(raw)?.state?.user?.role;
    return role === 'admin' || role === 'client' ? role : null;
  } catch {
    return null;
  }
}

const NotFound = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const role = getCurrentRole();

  return (
    <PageContainer>
      <ResultCard>
        <Result
          status="404"
          title="页面不存在"
          subTitle="你访问的地址可能已被移除、路径写错，或没有对应的路由页面。"
          extra={
            <Space wrap size={12}>
              <Button type="primary" onClick={() => navigate(role === 'admin' ? '/admin/dashboard' : '/')}>
                {role === 'admin' ? '返回管理后台首页' : '返回商城首页'}
              </Button>
              <Button onClick={() => navigate(-1)}>返回上一页</Button>
              <Button onClick={() => navigate('/login')}>前往登录</Button>
            </Space>
          }
        />
        <PathAlert
          type="warning"
          showIcon
          message={
            <PathText>
              当前路径：<code>{location.pathname}</code>
            </PathText>
          }
        />
      </ResultCard>
    </PageContainer>
  );
};

const PageContainer = styled.div`
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at 18% 25%, rgba(255, 240, 181, 0.42) 0%, rgba(255, 240, 181, 0) 38%),
    radial-gradient(circle at 82% 75%, rgba(177, 235, 255, 0.38) 0%, rgba(177, 235, 255, 0) 38%),
    linear-gradient(140deg, #fffdf5 0%, #f5fbff 100%);
`;

const ResultCard = styled.div`
  width: 100%;
  max-width: 640px;
  background: #ffffff;
  border: 1px solid #f0f0f0;
  border-radius: 16px;
  box-shadow: 0 16px 45px rgba(0, 0, 0, 0.08);
  padding: 6px 10px 20px;
`;

const PathText = styled(Text)`
  color: #595959;

  code {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    background: #f5f5f5;
    color: #262626;
  }
`;

const PathAlert = styled(Alert)`
  margin: 0 18px;
`;

export default NotFound;
