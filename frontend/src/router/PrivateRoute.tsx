import { Navigate, Outlet } from 'react-router-dom';

interface PrivateRouteProps {
  /** 需要具备该角色才能访问，不传则仅验证是否登录 */
  requiredRole?: 'admin' | 'client';
}

/**
 * 路由权限守卫组件
 *
 * 用法：
 *   <Route element={<PrivateRoute />}>               // 仅登录校验
 *   <Route element={<PrivateRoute requiredRole="admin" />}> // 必须是管理员
 *
 * 逻辑：
 *   1. 未登录 → 重定向到 /login
 *   2. 已登录但角色不符（普通用户访问 /admin/*） → 重定向到 /403
 *   3. 校验通过 → 渲染子路由 <Outlet />
 */
const PrivateRoute = ({ requiredRole }: PrivateRouteProps) => {
  // 从 zustand persist 存储中读取用户信息（此处直接读 localStorage 避免循环依赖）
  const raw = localStorage.getItem('auth-storage');
  const authState = raw ? JSON.parse(raw)?.state : null;
  const token: string | null = authState?.token ?? null;
  const role: string | null = authState?.user?.role ?? null;

  // 未登录，跳转到登录页
  if (!token) {
    return <Navigate to="/login" replace />;
  }

  // 已登录但角色不匹配，跳转到无权限页
  if (requiredRole && role !== requiredRole) {
    return <Navigate to="/403" replace />;
  }

  return <Outlet />;
};

export default PrivateRoute;
