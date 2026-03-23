import { beforeEach, describe, expect, it } from 'vitest';

import useAuthStore from './useAuthStore';

describe('useAuthStore', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null });
  });

  it('login: 应写入 token 和用户信息，并变为已登录', () => {
    useAuthStore.getState().login('token-123', {
      id: 1,
      username: 'tester',
      email: 'tester@example.com',
      role: 'client',
    });

    const state = useAuthStore.getState();
    expect(state.token).toBe('token-123');
    expect(state.user?.username).toBe('tester');
    expect(state.isAuthenticated()).toBe(true);
  });

  it('setUser: 应仅更新用户信息，不改 token', () => {
    useAuthStore.getState().login('token-456', {
      id: 1,
      username: 'old',
      email: 'old@example.com',
      role: 'client',
    });

    useAuthStore.getState().setUser({
      id: 1,
      username: 'new_name',
      email: 'new@example.com',
      role: 'client',
    });

    const state = useAuthStore.getState();
    expect(state.token).toBe('token-456');
    expect(state.user?.username).toBe('new_name');
  });

  it('isAuthenticated: 无 token 时应返回 false', () => {
    expect(useAuthStore.getState().isAuthenticated()).toBe(false);
  });
});
