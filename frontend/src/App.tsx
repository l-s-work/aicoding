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

  /* 统一全局滚动条样式，并显式去掉上下两端的三角按钮。 */
  * {
    scrollbar-width: thin;
    scrollbar-color: #bfbfbf #f2f2f2;
  }

  *::-webkit-scrollbar {
    width: 10px;
    height: 10px;
  }

  *::-webkit-scrollbar-track {
    background: #f2f2f2;
    border-radius: 8px;
  }

  *::-webkit-scrollbar-thumb {
    background: #bfbfbf;
    border-radius: 8px;
    border: 2px solid #f2f2f2;
  }

  *::-webkit-scrollbar-thumb:hover {
    background: #a0a0a0;
  }

  *::-webkit-scrollbar-button {
    width: 0;
    height: 0;
    display: none;
    appearance: none;
    -webkit-appearance: none;
    background: transparent;
  }

  *::-webkit-scrollbar-button:single-button,
  *::-webkit-scrollbar-button:start,
  *::-webkit-scrollbar-button:end,
  *::-webkit-scrollbar-button:vertical,
  *::-webkit-scrollbar-button:horizontal,
  *::-webkit-scrollbar-button:vertical:decrement,
  *::-webkit-scrollbar-button:vertical:increment,
  *::-webkit-scrollbar-button:vertical:start:decrement,
  *::-webkit-scrollbar-button:vertical:end:increment,
  *::-webkit-scrollbar-button:horizontal:decrement,
  *::-webkit-scrollbar-button:horizontal:increment,
  *::-webkit-scrollbar-button:horizontal:start:decrement,
  *::-webkit-scrollbar-button:horizontal:end:increment {
    width: 0;
    height: 0;
    display: none;
    appearance: none;
    -webkit-appearance: none;
    background: transparent;
  }

  *::-webkit-scrollbar-corner {
    background: transparent;
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
