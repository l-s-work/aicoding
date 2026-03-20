import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu, Button, Space } from 'antd';
import styled from 'styled-components';
import { post } from '@/utils/request';
import useAuthStore from '@/store/useAuthStore';

const { Header } = Layout;

const menuItems = [
  { key: '/admin/dashboard', label: <Link to="/admin/dashboard">首页</Link> },
  { key: '/admin/todos', label: <Link to="/admin/todos">我的待办</Link> },
  { key: '/admin/orders', label: <Link to="/admin/orders">订单管理</Link> },
  { key: '/admin/products', label: <Link to="/admin/products">商品管理</Link> },
  { key: '/admin/users', label: <Link to="/admin/users">用户管理</Link> },
];

const AdminHeader = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, user } = useAuthStore();

  const selectedKey = menuItems.find(item => location.pathname === item.key || location.pathname.startsWith(`${item.key}/`))?.key ?? '/admin/dashboard';

  const handleLogout = async () => {
    try {
      await post('/auth/logout');
    } catch {
      // 忽略后端异常，确保前端本地态清理
    }
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <StyledHeader>
      <Brand>AI 电商后台</Brand>
      <Menu mode="horizontal" selectedKeys={[selectedKey]} items={menuItems} />
      <Space>
        <UserText>{user?.username ?? '管理员'}</UserText>
        <Button onClick={handleLogout}>退出登录</Button>
      </Space>
    </StyledHeader>
  );
};

const StyledHeader = styled(Header)`
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: 180px 1fr auto;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  padding: 0 20px;
  z-index: 10;

  .ant-menu {
    border-bottom: none;
  }
`;

const Brand = styled.div`
  font-weight: 700;
  font-size: 18px;
  color: #0050b3;
`;

const UserText = styled.span`
  color: #595959;
`;

export default AdminHeader;
