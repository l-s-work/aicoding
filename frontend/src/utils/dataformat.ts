export const saleStatusMap: Record<string, string> = {
  on_sale: '在售',
  off_sale: '下架',
};

export const orderStatusMap: Record<string, string> = {
  pending: '待支付',
  paid: '已支付',
  shipped: '已发货',
  completed: '已完成',
  cancelled: '已取消',
};

/**
 * 金额格式化：统一两位小数 + 千分位
 * 示例：1234567.8 -> ¥1,234,567.80
 */
export const formatAmount = (amount: number): string => {
  const normalized = Number.isFinite(amount) ? amount : 0;
  return `¥${normalized.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};
