import { RouterProvider } from 'react-router-dom';
import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { createGlobalStyle } from 'styled-components';
import router from '@/router';

const GlobalBaseStyle = createGlobalStyle`
  html,
  body,
  #root {
    height: 100%;
  }

  body {
    margin: 0;
    overflow-x: hidden;
  }
`;

/**
 * 根组件
 * - ConfigProvider：全局注入 Ant Design 中文语言包和主题 Token
 * - AntdApp：开启全局静态方法（message、notification、modal）的 React 19 兼容模式
 * - RouterProvider：挂载 React Router v6 路由树
 */
const App = () => {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          // 电商主色调：偏暖橙红色，可按品牌色调整
          colorPrimary: '#ff4d00',
        },
      }}
    >
      <GlobalBaseStyle />
      <AntdApp>
        <RouterProvider router={router} />
      </AntdApp>
    </ConfigProvider>
  );
};

export default App;
