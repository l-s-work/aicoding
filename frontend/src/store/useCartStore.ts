import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/** 购物车中单个商品条目（含下单时固化的快照价格） */
export interface CartItem {
  productId: number;
  /** 商品名称（展示用，来自前端缓存） */
  name: string;
  /** 商品封面图 */
  cover: string;
  /** 加入购物车时的当前售价快照（防止价格变动影响展示） */
  price: number;
  /**
   * 购物车不再统计数量，统一在结算页选择数量。
   * 该字段保留用于兼容历史持久化数据与结算页初始化，固定为 1。
   */
  quantity: number;
}

interface CartState {
  items: CartItem[];
  /** 加入购物车，已存在则忽略（不重复累计数量） */
  addItem: (item: Omit<CartItem, 'quantity'>) => boolean;
  /** 更新指定商品数量（设为 0 则等同于移除） */
  updateQuantity: (productId: number, quantity: number) => void;
  /** 移除单个商品 */
  removeItem: (productId: number) => void;
  /** 结账成功后清空购物车 */
  clearCart: () => void;
  /** 计算购物车总价（用于展示，实际下单价格以后端为准） */
  totalPrice: () => number;
  /** 购物车商品总数（角标显示） */
  totalCount: () => number;
}

/**
 * 购物车状态仓库
 * 使用 persist 持久化到 localStorage，刷新或多开 Tab 不丢失数据
 * 结账时再向后端发起校验，以后端价格为最终结算价格
 */
const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      items: [],

      addItem: newItem => {
        const exists = get().items.find(i => i.productId === newItem.productId);
        if (exists) {
          // 购物车按“商品集合”管理，已存在则不重复添加
          return false;
        } else {
          set({ items: [...get().items, { ...newItem, quantity: 1 }] });
          return true;
        }
      },

      updateQuantity: (productId, quantity) => {
        if (quantity <= 0) {
          // 数量归零时直接移除
          set({ items: get().items.filter(i => i.productId !== productId) });
        } else {
          set({
            items: get().items.map(i => (i.productId === productId ? { ...i, quantity } : i)),
          });
        }
      },

      removeItem: productId => {
        set({ items: get().items.filter(i => i.productId !== productId) });
      },

      clearCart: () => set({ items: [] }),

      // 购物车阶段不统计数量，统一按 1 件展示金额；结算页再按用户选择数量计算
      totalPrice: () => get().items.reduce((sum, item) => sum + item.price, 0),

      // 购物车数量角标按“商品种类数”统计
      totalCount: () => get().items.length,
    }),
    {
      name: 'cart-storage', // localStorage key
    }
  )
);

export default useCartStore;
