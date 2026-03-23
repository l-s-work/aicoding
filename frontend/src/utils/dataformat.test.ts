import { describe, expect, it } from 'vitest';

import { formatAmount, orderStatusMap, saleStatusMap } from './dataformat';

describe('dataformat 工具函数', () => {
  it('应返回正确的状态映射', () => {
    expect(saleStatusMap.on_sale).toBe('在售');
    expect(orderStatusMap.cancelled).toBe('已取消');
  });

  it('formatAmount 应按人民币格式输出两位小数', () => {
    expect(formatAmount(1234567.8)).toBe('¥1,234,567.80');
    expect(formatAmount(0)).toBe('¥0.00');
  });

  it('formatAmount 在 NaN/Infinity 时应回退为 0', () => {
    expect(formatAmount(Number.NaN)).toBe('¥0.00');
    expect(formatAmount(Number.POSITIVE_INFINITY)).toBe('¥0.00');
  });
});
