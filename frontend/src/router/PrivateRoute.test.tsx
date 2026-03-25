import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/utils/request', () => ({
  get: vi.fn(),
}));

import { get } from '@/utils/request';
import PrivateRoute from './PrivateRoute';

function setAuthStorage(value: unknown) {
  localStorage.setItem('auth-storage', JSON.stringify({ state: value }));
}

function GuardedApp(requiredRole: 'admin' | 'client') {
  return (
    <MemoryRouter initialEntries={['/admin']}>
      <Routes>
        <Route path="/login" element={<div>LOGIN_PAGE</div>} />
        <Route path="/403" element={<div>FORBIDDEN_PAGE</div>} />
        <Route element={<PrivateRoute requiredRole={requiredRole} />}>
          <Route path="/admin" element={<div>ADMIN_PAGE</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe('PrivateRoute', () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement('div');
    document.body.appendChild(host);
    root = createRoot(host);
    vi.clearAllMocks();
  });

  afterEach(async () => {
    await act(async () => {
      root.unmount();
    });
    host.remove();
  });

  it('无 token 时应重定向到登录页', async () => {
    localStorage.removeItem('auth-storage');

    await act(async () => {
      root.render(GuardedApp('admin'));
    });

    expect(host.textContent).toContain('LOGIN_PAGE');
  });

  it('角色不匹配时应重定向到 403', async () => {
    setAuthStorage({
      token: 'token-client',
      user: { role: 'client' },
    });

    await act(async () => {
      root.render(GuardedApp('admin'));
    });

    expect(host.textContent).toContain('FORBIDDEN_PAGE');
    // 当前实现会先触发会话校验 effect，再执行角色分支渲染。
    expect(get).toHaveBeenCalledWith('/auth/me');
  });

  it('token 与角色匹配且会话验证通过时应放行', async () => {
    setAuthStorage({
      token: 'token-admin',
      user: { role: 'admin' },
    });
    vi.mocked(get).mockResolvedValueOnce({
      id: 1,
      username: 'admin',
      role: 'admin',
    } as never);

    await act(async () => {
      root.render(GuardedApp('admin'));
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(get).toHaveBeenCalledWith('/auth/me');
    expect(host.textContent).toContain('ADMIN_PAGE');
  });
});
