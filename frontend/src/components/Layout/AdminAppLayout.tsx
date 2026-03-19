import { Layout } from 'antd';
import { Outlet } from 'react-router-dom';
import styled from 'styled-components';
import AdminHeader from './AdminHeader';

const { Content } = Layout;

/**
 * B端公共壳布局
 * - Header 固定在页面顶部
 * - 仅内容区域滚动
 * - 统一滚动条样式，避免每个页面重复定义
 */
const AdminAppLayout = () => {
  return (
    <PageLayout>
      <AdminHeader />
      <ScrollContent>
        <Outlet />
      </ScrollContent>
    </PageLayout>
  );
};

const PageLayout = styled(Layout)`
  height: 100dvh;
  overflow: hidden;
  background: #f5f5f5;
`;

const ScrollContent = styled(Content)`
  width: 100%;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 16px 28px;
  scrollbar-width: thin;
  scrollbar-color: #bfbfbf #f2f2f2;

  &::-webkit-scrollbar {
    width: 10px;
  }

  &::-webkit-scrollbar-track {
    background: #f2f2f2;
    border-radius: 8px;
  }

  &::-webkit-scrollbar-thumb {
    background: #bfbfbf;
    border-radius: 8px;
    border: 2px solid #f2f2f2;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #a0a0a0;
  }
`;

export default AdminAppLayout;

