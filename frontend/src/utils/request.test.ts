import { describe, expect, it } from 'vitest';

import { controllable, isAbortError } from './request';

describe('request 工具函数', () => {
  it('controllable: 应提供可手动 abort 的 signal', () => {
    let controller: AbortController | null = null;
    const config = controllable(ctrl => {
      controller = ctrl;
    });

    expect(config.signal).toBeDefined();
    expect(config.signal?.aborted).toBe(false);

    controller?.abort();
    expect(config.signal?.aborted).toBe(true);
  });

  it('controllable: 传入外部 signal 时应合并取消状态', () => {
    const external = new AbortController();
    let internal: AbortController | null = null;

    const config = controllable(
      ctrl => {
        internal = ctrl;
      },
      { signal: external.signal }
    );

    expect(config.signal).toBeDefined();
    external.abort();
    expect(config.signal?.aborted).toBe(true);
    expect(internal).not.toBeNull();
  });

  it('isAbortError: 应识别 AbortError 与 axios cancel', () => {
    expect(isAbortError(new DOMException('aborted', 'AbortError'))).toBe(true);
    expect(isAbortError({ __CANCEL__: true } as never)).toBe(true);
    expect(isAbortError(new Error('network error'))).toBe(false);
  });
});
