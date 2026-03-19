import { lazy, Suspense } from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { Spin } from 'antd';
import PrivateRoute from './PrivateRoute';

// ===== 懒加载：C端页面（打包时独立 Chunk，不发给 B端管理员） =====
const ClientHome = lazy(() => import('@/pages/client/Home'));
const ClientProduct = lazy(() => import('@/pages/client/Product'));
const ClientCart = lazy(() => import('@/pages/client/Cart'));
const ClientCheckout = lazy(() => import('@/pages/client/Checkout'));

// ===== 懒加载：B端页面（打包时独立 Chunk，不发给普通买家） =====
const AdminDashboard = lazy(() => import('@/pages/admin/Dashboard'));
const AdminProducts = lazy(() => import('@/pages/admin/Products'));
const AdminOrders = lazy(() => import('@/pages/admin/Orders'));

// 通用页面（无需登录）
const Login = lazy(() => import('@/pages/Login'));
const NotFound = lazy(() => import('@/pages/NotFound'));
const Forbidden = lazy(() => import('@/pages/Forbidden'));

// 懒加载全局 Loading 占位
const PageFallback = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
    <Spin size="large" />
  </div>
);

const router = createBrowserRouter([
  // ===== 公开路由 =====
  {
    path: '/login',
    element: (
      <Suspense fallback={<PageFallback />}>
        <Login />
      </Suspense>
    ),
  },
  {
    path: '/403',
    element: (
      <Suspense fallback={<PageFallback />}>
        <Forbidden />
      </Suspense>
    ),
  },

  // ===== C端买家路由（仅需登录，role=client） =====
  {
    element: <PrivateRoute requiredRole="client" />,
    children: [
      {
        path: '/',
        element: (
          <Suspense fallback={<PageFallback />}>
            <ClientHome />
          </Suspense>
        ),
      },
      {
        path: '/product/:id',
        element: (
          <Suspense fallback={<PageFallback />}>
            <ClientProduct />
          </Suspense>
        ),
      },
      {
        path: '/cart',
        element: (
          <Suspense fallback={<PageFallback />}>
            <ClientCart />
          </Suspense>
        ),
      },
      {
        path: '/checkout',
        element: (
          <Suspense fallback={<PageFallback />}>
            <ClientCheckout />
          </Suspense>
        ),
      },
    ],
  },

  // ===== B端管理员路由（必须 role=admin） =====
  {
    path: '/admin',
    element: <PrivateRoute requiredRole="admin" />,
    children: [
      {
        path: 'dashboard',
        element: (
          <Suspense fallback={<PageFallback />}>
            <AdminDashboard />
          </Suspense>
        ),
      },
      {
        path: 'products',
        element: (
          <Suspense fallback={<PageFallback />}>
            <AdminProducts />
          </Suspense>
        ),
      },
      {
        path: 'orders',
        element: (
          <Suspense fallback={<PageFallback />}>
            <AdminOrders />
          </Suspense>
        ),
      },
    ],
  },

  // ===== 404 兜底 =====
  {
    path: '*',
    element: (
      <Suspense fallback={<PageFallback />}>
        <NotFound />
      </Suspense>
    ),
  },
]);

export default router;
