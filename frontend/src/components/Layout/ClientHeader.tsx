import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu, Button, Space } from 'antd';
import styled from 'styled-components';
import { post } from '@/utils/request';
import useAuthStore from '@/store/useAuthStore';

const { Header } = Layout;

const menuItems = [
  { key: '/', label: <Link to="/">商品列表</Link> },
  { key: '/cart', label: <Link to="/cart">我的购物车</Link> },
  { key: '/orders', label: <Link to="/orders">我的订单</Link> },
  { key: '/account', label: <Link to="/account">我的账号信息</Link> },
];

const ClientHeader = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, user } = useAuthStore();

  const selectedKey = menuItems.find(item => location.pathname === item.key || location.pathname.startsWith(`${item.key}/`))?.key ?? '/';

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
      <Brand>AI 电商 C端</Brand>
      <Menu mode="horizontal" selectedKeys={[selectedKey]} items={menuItems} />
      <Space>
        <UserText>{user?.username ?? '未登录'}</UserText>
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
  color: #d9480f;
`;

const UserText = styled.span`
  color: #595959;
`;

export default ClientHeader;
