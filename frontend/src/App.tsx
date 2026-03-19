import { RouterProvider } from 'react-router-dom';
import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import router from '@/router';

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
      <AntdApp>
        <RouterProvider router={router} />
      </AntdApp>
    </ConfigProvider>
  );
};

export default App;
