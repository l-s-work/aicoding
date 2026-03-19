import axios from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig, AxiosError, AxiosRequestConfig } from 'axios';

/**
 * 创建 Axios 实例
 * baseURL 使用 vite.config.ts 中配置的代理，开发时自动转发到 FastAPI:8000
 */
const request = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // 允许携带 HttpOnly Cookie（Refresh Token）
});

// ===== 请求取消逻辑（仅支持单点手动取消与生命周期取消） =====

/**
 * 创建一个用于外部手动控制的 controller
 * @param getController 获取 AbortController 引用的回调
 * @param config 可选的额外 Axios 配置
 * @returns 合并了 signal 的请求配置
 *
 * 用法：
 *   // 拿到 controller 手动控制请求生命周期
 *   request.get('/products', controllable((ctrl) => { ctrlRef.current = ctrl }))
 */
export function controllable(getController: (ctrl: AbortController) => void, config?: AxiosRequestConfig): AxiosRequestConfig {
  const controller = new AbortController();
  getController(controller);

  const { signal: externalSignal, ...restConfig } = config ?? {};
  const finalSignal = externalSignal ? AbortSignal.any([controller.signal, externalSignal as AbortSignal]) : controller.signal;

  return { ...restConfig, signal: finalSignal };
}

/**
 * 判断错误是否是由 abort() 主动取消引起的
 * 业务层可据此决定是否弹出错误提示（取消操作通常不需要报错）
 */
export function isAbortError(error: unknown): boolean {
  return axios.isCancel(error) || (error instanceof DOMException && error.name === 'AbortError');
}

/**
 * SSE 流式请求（用于 AI 对话打字机效果）
 * 基于原生 fetch + ReadableStream，支持通过 ctrl.abort() 随时中断
 *
 * @param url   请求路径（会自动拼接 /api 前缀）
 * @param body  POST 请求体
 * @param onMessage  每收到一条 SSE data 时的回调
 * @param onDone     流结束时的回调
 * @param onError    出错时的回调（主动取消不会触发）
 */
export async function fetchSSE(options: {
  url: string;
  body: unknown;
  /** 获取 AbortController 引用，可在外部直接调用 ctrl.abort() 取消 */
  getController?: (ctrl: AbortController) => void;
  /** 外部 signal，与内部 controller 合并，任一触发即取消 */
  signal?: AbortSignal;
  onMessage: (data: string) => void;
  onDone?: () => void;
  onError?: (error: Error) => void;
  /** 请求被主动取消时的回调 */
  onAbort?: () => void;
  /** 主动取消时静默返回，不触发 onError（默认 true） */
  silentAbort?: boolean;
}): Promise<void> {
  const { url, body, getController, signal: externalSignal, onMessage, onDone, onError, onAbort, silentAbort = true } = options;

  const controller = new AbortController();
  getController?.(controller);

  // 合并外部 signal（如组件卸载时的 cleanup signal）
  const combinedSignal = externalSignal ? AbortSignal.any([controller.signal, externalSignal]) : controller.signal;

  const token = getAccessToken();

  try {
    const response = await fetch(`/api${url}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      credentials: 'include',
      body: JSON.stringify(body),
      signal: combinedSignal,
    });

    // 非 200 状态码，尝试解析后端错误信息
    if (!response.ok) {
      const errBody = await response.text().catch(() => '');
      let detail = '请求失败';
      try {
        detail = JSON.parse(errBody)?.detail ?? detail;
      } catch {
        // 非 JSON 响应体，使用默认错误文案
      }
      throw new Error(detail);
    }

    // 逐行读取 SSE 流
    const reader = response.body?.getReader();
    if (!reader) throw new Error('浏览器不支持流式响应');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      // SSE 协议：以双换行分割事件
      const parts = buffer.split('\n\n');
      // 最后一段可能不完整，留到下次拼接
      buffer = parts.pop() ?? '';

      for (const part of parts) {
        for (const line of part.split('\n')) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
              return;
            }
            onMessage(data);
          }
        }
      }
    }

    onDone?.();
  } catch (error) {
    // 主动取消：触发 onAbort 回调，silentAbort 时不走 onError
    if (isAbortError(error)) {
      onAbort?.();
      if (!silentAbort) {
        onError?.(new Error('请求已取消'));
      }
      return;
    }
    onError?.(error instanceof Error ? error : new Error('流式请求异常'));
  }
}

// ===== 辅助函数：从 Zustand persist 的 localStorage 中读取 Access Token =====
function getAccessToken(): string | null {
  try {
    const raw = localStorage.getItem('auth-storage');
    if (!raw) return null;
    return JSON.parse(raw)?.state?.token ?? null;
  } catch {
    return null;
  }
}

// ===== 辅助函数：将新 Access Token 写回 Zustand persist 的 localStorage =====
function setAccessToken(newToken: string): void {
  try {
    const raw = localStorage.getItem('auth-storage');
    if (!raw) return;
    const data = JSON.parse(raw);
    if (data?.state) {
      data.state.token = newToken;
      localStorage.setItem('auth-storage', JSON.stringify(data));
    }
  } catch {
    // 静默失败，下次请求会触发 401 → refresh 流程
  }
}

// ===== 联锁清退：清除所有本地授权状态并跳转登录页 =====
function forceLogout(): void {
  localStorage.removeItem('auth-storage');
  window.location.replace('/login');
}

// ===== Refresh Token 无感刷新控制 =====
let isRefreshing = false;
// 刷新期间排队的请求，等拿到新 Token 后统一重试
let pendingQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: Error) => void;
}> = [];

/**
 * 尝试使用 HttpOnly Cookie 中的 Refresh Token 换取新的 Access Token
 * 如果多个请求同时 401，只发起一次刷新，其余排队等待
 */
function handleTokenRefresh(): Promise<string> {
  if (isRefreshing) {
    // 已有刷新请求在进行中，排队等候结果
    return new Promise((resolve, reject) => {
      pendingQueue.push({ resolve, reject });
    });
  }

  isRefreshing = true;

  return new Promise((resolve, reject) => {
    // 直接用 axios（非 request 实例）避免触发自身拦截器
    axios
      .post('/api/auth/refresh', null, { withCredentials: true })
      .then(res => {
        const newToken: string = res.data?.access_token;
        if (!newToken) throw new Error('刷新令牌响应异常');
        // 写回 localStorage，同步 Zustand persist 状态
        setAccessToken(newToken);
        resolve(newToken);
        // 通知所有排队请求使用新 Token 重试
        pendingQueue.forEach(cb => cb.resolve(newToken));
      })
      .catch(err => {
        reject(err);
        pendingQueue.forEach(cb => cb.reject(err));
        // Refresh Token 也失效，彻底清退
        forceLogout();
      })
      .finally(() => {
        isRefreshing = false;
        pendingQueue = [];
      });
  });
}

// ===== 请求拦截器 =====
// 每次发起请求时，从 Zustand persist 的 localStorage 中读取 Token 并注入 Authorization 头
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  error => Promise.reject(error)
);

// ===== 响应拦截器 =====
// 401 时先尝试无感刷新，刷新失败才联锁清退；403 直接清退
request.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const originalRequest = error.config;

    // 403 表示角色越权或账号被封禁，直接清退
    if (status === 403) {
      forceLogout();
      return Promise.reject(new Error('权限不足，已退出登录'));
    }

    // 401 且非刷新接口本身：尝试无感刷新 Access Token
    if (status === 401 && originalRequest && !originalRequest.url?.includes('/auth/refresh')) {
      try {
        const newToken = await handleTokenRefresh();
        // 使用新 Token 重试原请求
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return request(originalRequest);
      } catch {
        // refresh 也失败，forceLogout 已在 handleTokenRefresh 中执行
        return Promise.reject(new Error('登录已过期，请重新登录'));
      }
    }

    // 其他错误：将错误信息以可读格式透传给业务层
    const message = (error.response?.data as { detail?: string })?.detail || error.message || '请求失败，请稍后重试';
    return Promise.reject(new Error(message));
  }
);

// ===== 语义化 API 封装 =====

export interface RequestOptions<T = unknown> extends Omit<AxiosRequestConfig, 'url' | 'method' | 'data'> {
  /** 获取 AbortController 引用 */
  getController?: (ctrl: AbortController) => void;
  /** 类型提示：期望的响应数据类型 */
  __responseType?: T;
}

/**
 * GET 请求
 * @param url 请求路径
 * @param options 可选配置（支持 params 等）
 * @returns Promise<T> 后端返回的 data 字段
 *
 * 用法：
 *   const products = await get<Product[]>('/products', { params: { page: 1 } })
 */
export async function get<T = unknown>(url: string, options?: RequestOptions<T>): Promise<T> {
  const { getController, ...restConfig } = options ?? {};
  const config = getController ? controllable(getController, restConfig) : restConfig;
  return request.get<unknown, T>(url, config);
}

/**
 * POST 请求
 * @param url 请求路径
 * @param data 请求体数据
 * @param options 可选配置
 * @returns Promise<T>
 *
 * 用法：
 *   const order = await post<Order>('/orders', { items: [...] })
 */
export async function post<T = unknown>(url: string, data?: unknown, options?: RequestOptions<T>): Promise<T> {
  const { getController, ...restConfig } = options ?? {};
  const config = getController ? controllable(getController, restConfig) : restConfig;
  return request.post<unknown, T>(url, data, config);
}

/**
 * PUT 请求
 * @param url 请求路径
 * @param data 请求体数据
 * @param options 可选配置
 * @returns Promise<T>
 */
export async function put<T = unknown>(url: string, data?: unknown, options?: RequestOptions<T>): Promise<T> {
  const { getController, ...restConfig } = options ?? {};
  const config = getController ? controllable(getController, restConfig) : restConfig;
  return request.put<unknown, T>(url, data, config);
}

/**
 * PATCH 请求
 * @param url 请求路径
 * @param data 请求体数据
 * @param options 可选配置
 * @returns Promise<T>
 */
export async function patch<T = unknown>(url: string, data?: unknown, options?: RequestOptions<T>): Promise<T> {
  const { getController, ...restConfig } = options ?? {};
  const config = getController ? controllable(getController, restConfig) : restConfig;
  return request.patch<unknown, T>(url, data, config);
}

/**
 * DELETE 请求
 * @param url 请求路径
 * @param options 可选配置
 * @returns Promise<T>
 */
export async function del<T = unknown>(url: string, options?: RequestOptions<T>): Promise<T> {
  const { getController, ...restConfig } = options ?? {};
  const config = getController ? controllable(getController, restConfig) : restConfig;
  return request.delete<unknown, T>(url, config);
}

/**
 * 文件上传（自动处理 FormData，支持进度回调）
 * @param url 上传路径
 * @param file File 对象或 FormData
 * @param options 可选配置（支持 onUploadProgress 进度回调）
 * @returns Promise<T>
 *
 * 用法：
 *   // 单文件上传
 *   const res = await upload<{ url: string }>('/upload', file, {
 *     onUploadProgress: (progress) => setPercent(progress.loaded / progress.total),
 *   })
 */
export async function upload<T = unknown>(
  url: string,
  file: File | FormData,
  options?: RequestOptions<T> & { onUploadProgress?: (progress: ProgressEvent) => void }
): Promise<T> {
  const { getController, onUploadProgress, ...restConfig } = options ?? {};

  // 自动构建 FormData（如果传入的是 File）
  const formData =
    file instanceof FormData
      ? file
      : (() => {
          const fd = new FormData();
          fd.append('file', file);
          return fd;
        })();

  const config = getController ? controllable(getController, restConfig) : restConfig;

  return request.post<unknown, T>(url, formData, {
    ...config,
    headers: { ...config?.headers, 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
  });
}

/**
 * 文件下载（Blob 响应，自动触发浏览器下载）
 * @param url 下载路径
 * @param filename 保存的文件名（默认从响应头 Content-Disposition 中提取）
 * @param options 可选配置
 *
 * 用法：
 *   await download('/orders/123/invoice', 'invoice.pdf')
 */
export async function download(url: string, filename?: string, options?: RequestOptions<Blob>): Promise<void> {
  const { getController, ...restConfig } = options ?? {};
  const config = getController ? controllable(getController, restConfig) : restConfig;

  // 特殊处理：download 需要绕过响应拦截器的 response.data 提取，直接拿原始 response
  const axiosResponse = await axios.get<Blob>(url, {
    ...config,
    baseURL: '/api',
    withCredentials: true,
    responseType: 'blob',
    headers: {
      ...config.headers,
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });

  const blob = axiosResponse.data;
  const finalFilename = filename ?? 'download';

  // 创建 Blob URL 并触发下载
  const blobUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = finalFilename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(blobUrl);
}

export default request;
