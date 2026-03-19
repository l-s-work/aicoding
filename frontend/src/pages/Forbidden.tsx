import { Alert, Button, Result, Space, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';

const { Text } = Typography;

/** 从本地持久化状态中读取当前角色，用于给 403 页提供正确返回入口 */
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

const Forbidden = () => {
  const navigate = useNavigate();
  const role = getCurrentRole();
  const homePath = role === 'admin' ? '/admin/dashboard' : '/';

  return (
    <PageContainer>
      <ResultCard>
        <Result
          status="403"
          title="无访问权限"
          subTitle="当前账号没有权限访问此页面，可能是角色不匹配或页面已调整。"
          extra={
            <Space wrap size={12}>
              <Button type="primary" onClick={() => navigate(homePath, { replace: true })}>
                返回首页
              </Button>
              <Button onClick={() => navigate(-1)}>返回上一页</Button>
              <Button onClick={() => navigate('/login')}>重新登录</Button>
            </Space>
          }
        />
        <RoleAlert
          type="info"
          showIcon
          message={
            <TipText>
              当前角色：<strong>{role ?? '未登录'}</strong>
            </TipText>
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
    radial-gradient(circle at 15% 20%, rgba(255, 182, 193, 0.35) 0%, rgba(255, 182, 193, 0) 35%),
    radial-gradient(circle at 85% 80%, rgba(173, 216, 230, 0.35) 0%, rgba(173, 216, 230, 0) 35%),
    linear-gradient(135deg, #fff7f5 0%, #f8faff 100%);
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

const TipText = styled(Text)`
  color: #595959;
`;

const RoleAlert = styled(Alert)`
  margin: 0 18px;
`;

export default Forbidden;
