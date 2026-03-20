import { ArrowLeftOutlined } from '@ant-design/icons';
import { Button, Space, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';

const { Title } = Typography;

interface ClientPageHeaderProps {
  title: string;
  /** 当历史栈不足时的兜底返回路径 */
  fallbackPath?: string;
  /** 是否显示返回按钮（菜单首页默认不显示） */
  showBack?: boolean;
}

/**
 * C 端页面标题栏
 * - 支持按页面场景显示/隐藏返回按钮
 * - 避免各页面重复实现导航逻辑
 */
const ClientPageHeader = ({ title, fallbackPath = '/', showBack = false }: ClientPageHeaderProps) => {
  const navigate = useNavigate();

  const handleBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate(fallbackPath);
  };

  return (
    <HeaderRow align="center">
      <Space align="center" size={12}>
        {showBack ? (
          <Button icon={<ArrowLeftOutlined />} onClick={handleBack}>
            返回
          </Button>
        ) : null}
        <Title level={3} style={{ margin: 0 }}>
          {title}
        </Title>
      </Space>
    </HeaderRow>
  );
};

const HeaderRow = styled(Space)`
  display: flex;
  width: 100%;
  margin-bottom: 14px;
`;

export default ClientPageHeader;
