import { beforeEach } from 'vitest';

// jsdom 运行时可能缺少 AbortSignal.any，补一个轻量 polyfill 以匹配浏览器语义
if (typeof AbortSignal.any !== 'function') {
  Object.defineProperty(AbortSignal, 'any', {
    value: (signals: AbortSignal[]) => {
      const controller = new AbortController();

      const abort = () => {
        if (!controller.signal.aborted) {
          controller.abort();
        }
      };

      signals.forEach(signal => {
        if (signal.aborted) {
          abort();
        } else {
          signal.addEventListener('abort', abort, { once: true });
        }
      });

      return controller.signal;
    },
  });
}

// React 18+/19 测试环境标记，避免 act(...) 警告。
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});
