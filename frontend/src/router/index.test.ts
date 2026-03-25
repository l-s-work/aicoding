import { describe, expect, it } from 'vitest';

import router from './index';

describe('router 配置', () => {
  it('应包含公开路由、C端路由和B端路由入口', () => {
    const routes = (router as unknown as { routes: Array<{ path?: string }> }).routes;
    const paths = routes.map(item => item.path).filter(Boolean);

    expect(paths).toContain('/login');
    expect(paths).toContain('/register');
    expect(paths).toContain('/forgot-password');
    expect(paths).toContain('/admin');
    expect(paths).toContain('*');
  });
});

