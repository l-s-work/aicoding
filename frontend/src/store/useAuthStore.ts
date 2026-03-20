import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/** 后端返回的用户信息结构 */
export interface UserInfo {
  id: number;
  username: string;
  email: string;
  role: 'client' | 'admin';
}

interface AuthState {
  token: string | null;
  user: UserInfo | null;
  /** 登录：存储 token 和用户信息 */
  login: (token: string, user: UserInfo) => void;
  /** 更新用户资料（不改 token） */
  setUser: (user: UserInfo) => void;
  /** 登出：清除全部认证状态（配合 Axios 拦截器的 401 联锁清退） */
  logout: () => void;
  /** 判断当前是否已登录 */
  isAuthenticated: () => boolean;
}

/**
 * 用户认证状态仓库
 * 使用 persist 中间件持久化到 localStorage（key: 'auth-storage'）
 * 注意：PrivateRoute 和 Axios 拦截器中直接读取 localStorage 以避免循环依赖
 */
const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,

      login: (token, user) => set({ token, user }),
      setUser: user => set({ user }),

      logout: () => {
        set({ token: null, user: null });
        // 强制跳转登录页（配合 Axios 响应拦截器一同使用）
        window.location.replace('/login');
      },

      isAuthenticated: () => !!get().token,
    }),
    {
      name: 'auth-storage', // localStorage key，与 Axios 拦截器中保持一致
      // 只持久化 token 和 user，不持久化 Action 函数
      partialize: state => ({ token: state.token, user: state.user }),
    }
  )
);

export default useAuthStore;
