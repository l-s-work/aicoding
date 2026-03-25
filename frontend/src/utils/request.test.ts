import axios from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import request, { controllable, del, download, fetchSSE, get, isAbortError, patch, post, put, upload } from './request';

describe('request 工具函数', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('controllable: 应提供可手动 abort 的 signal', () => {
    let controller: AbortController | undefined;
    const config = controllable(ctrl => {
      controller = ctrl;
    });

    expect(config.signal).toBeDefined();
    expect(config.signal?.aborted).toBe(false);

    expect(controller).toBeDefined();
    controller!.abort();
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

  it('get/post/put/patch/del: 应调用 axios 实例对应方法', async () => {
    const getSpy = vi.spyOn(request, 'get').mockResolvedValueOnce({ ok: true } as never);
    const postSpy = vi.spyOn(request, 'post').mockResolvedValueOnce({ created: true } as never);
    const putSpy = vi.spyOn(request, 'put').mockResolvedValueOnce({ updated: true } as never);
    const patchSpy = vi.spyOn(request, 'patch').mockResolvedValueOnce({ patched: true } as never);
    const deleteSpy = vi.spyOn(request, 'delete').mockResolvedValueOnce({ removed: true } as never);

    await expect(get('/products')).resolves.toEqual({ ok: true });
    await expect(post('/orders', { id: 1 })).resolves.toEqual({ created: true });
    await expect(put('/orders/1', { status: 'paid' })).resolves.toEqual({ updated: true });
    await expect(patch('/orders/1', { status: 'shipped' })).resolves.toEqual({ patched: true });
    await expect(del('/orders/1')).resolves.toEqual({ removed: true });

    expect(getSpy).toHaveBeenCalled();
    expect(postSpy).toHaveBeenCalled();
    expect(putSpy).toHaveBeenCalled();
    expect(patchSpy).toHaveBeenCalled();
    expect(deleteSpy).toHaveBeenCalled();
  });

  it('upload: File 入参应自动封装为 FormData 并走 multipart', async () => {
    const postSpy = vi.spyOn(request, 'post').mockResolvedValueOnce({ url: '/uploads/a.png' } as never);
    const file = new File([new Uint8Array([1, 2, 3])], 'a.png', { type: 'image/png' });

    const result = await upload<{ url: string }>('/products/upload-image', file);

    expect(result.url).toBe('/uploads/a.png');
    expect(postSpy).toHaveBeenCalledTimes(1);
    const [, body, config] = postSpy.mock.calls[0];
    expect(body).toBeInstanceOf(FormData);
    expect((config as { headers?: Record<string, string> })?.headers?.['Content-Type']).toBe('multipart/form-data');
  });

  it('download: 应创建 Blob URL 并触发下载', async () => {
    const blob = new Blob(['test'], { type: 'text/plain' });
    const axiosSpy = vi.spyOn(axios, 'get').mockResolvedValueOnce({ data: blob } as never);
    if (!('createObjectURL' in URL)) {
      Object.defineProperty(URL, 'createObjectURL', {
        value: () => 'blob:test',
        writable: true,
      });
    }
    if (!('revokeObjectURL' in URL)) {
      Object.defineProperty(URL, 'revokeObjectURL', {
        value: () => undefined,
        writable: true,
      });
    }
    const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValueOnce('blob:test');
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);

    await download('/download/report', 'report.txt');

    expect(axiosSpy).toHaveBeenCalled();
    expect(createObjectURLSpy).toHaveBeenCalledWith(blob);
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeSpy).toHaveBeenCalledWith('blob:test');
  });

  it('fetchSSE: 应按 SSE 协议解析 delta 与 DONE', async () => {
    localStorage.setItem(
      'auth-storage',
      JSON.stringify({ state: { token: 'token-123' } })
    );

    const encoder = new TextEncoder();
    const bodyStream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"delta","content":"你好"}\n\n'));
        controller.enqueue(encoder.encode('data: [DONE]\n\n'));
        controller.close();
      },
    });

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: bodyStream,
    });
    vi.stubGlobal('fetch', fetchMock as unknown as typeof fetch);

    const onMessage = vi.fn();
    const onDone = vi.fn();

    await fetchSSE({
      url: '/ai/chat/stream',
      body: { content: 'hello' },
      onMessage,
      onDone,
    });

    expect(fetchMock).toHaveBeenCalled();
    expect(onMessage).toHaveBeenCalledWith('{"type":"delta","content":"你好"}');
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});
