import { Layout } from 'antd';
import { Outlet } from 'react-router-dom';
import styled from 'styled-components';
import ClientAiAssistant from '@/components/ai/ClientAiAssistant';
import ClientHeader from './ClientHeader';

const { Content } = Layout;

/**
 * C端公共壳布局
 * - Header 统一放在路由壳层
 * - 页面仅维护业务内容，避免每个页面重复写 Header + Layout
 */
const ClientAppLayout = () => {
  return (
    <PageLayout>
      <ClientHeader />
      <ScrollContent>
        <Outlet />
      </ScrollContent>
      <ClientAiAssistant />
    </PageLayout>
  );
};

const PageLayout = styled(Layout)`
  height: 100dvh;
  overflow: hidden;
  background: #ffffff;
`;

const ScrollContent = styled(Content)`
  width: 100%;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 16px 28px;
`;

export default ClientAppLayout;
