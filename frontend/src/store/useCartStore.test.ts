import { beforeEach, describe, expect, it } from 'vitest';

import useCartStore from './useCartStore';

describe('useCartStore', () => {
  beforeEach(() => {
    useCartStore.setState({ items: [] });
  });

  it('addItem: 新增商品成功，重复商品应忽略', () => {
    const state = useCartStore.getState();
    const added = state.addItem({
      productId: 1,
      name: '耳机A',
      cover: '/a.png',
      price: 199,
    });
    const duplicated = useCartStore.getState().addItem({
      productId: 1,
      name: '耳机A',
      cover: '/a.png',
      price: 199,
    });

    expect(added).toBe(true);
    expect(duplicated).toBe(false);
    expect(useCartStore.getState().items).toHaveLength(1);
    expect(useCartStore.getState().items[0].quantity).toBe(1);
  });

  it('updateQuantity: 数量 <= 0 时应移除商品', () => {
    useCartStore.getState().addItem({
      productId: 2,
      name: '音箱B',
      cover: '/b.png',
      price: 399,
    });

    useCartStore.getState().updateQuantity(2, 0);
    expect(useCartStore.getState().items).toHaveLength(0);
  });

  it('totalPrice: 按当前实现仅统计商品种类价格（不累计 quantity）', () => {
    useCartStore.getState().addItem({
      productId: 3,
      name: '手机C',
      cover: '/c.png',
      price: 4999,
    });
    useCartStore.getState().addItem({
      productId: 4,
      name: '手表D',
      cover: '/d.png',
      price: 999,
    });
    useCartStore.getState().updateQuantity(3, 5);

    expect(useCartStore.getState().totalPrice()).toBe(5998);
    expect(useCartStore.getState().totalCount()).toBe(2);
  });
});
