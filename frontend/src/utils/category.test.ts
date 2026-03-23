import { describe, expect, it } from 'vitest';

import { buildCategoryCascaderOptions, buildCategoryPathMap, type CategoryNode } from './category';

const categoryTree: CategoryNode[] = [
  {
    id: 1,
    name: '数码',
    level: 1,
    children: [
      {
        id: 11,
        name: '耳机',
        level: 2,
        parent_id: 1,
        children: [
          {
            id: 111,
            name: '蓝牙耳机',
            level: 3,
            parent_id: 11,
            children: [],
          },
        ],
      },
    ],
  },
];

describe('category 工具函数', () => {
  it('buildCategoryPathMap 应构建完整路径映射', () => {
    const pathMap = buildCategoryPathMap(categoryTree);
    expect(pathMap.get(1)).toEqual(['数码']);
    expect(pathMap.get(11)).toEqual(['数码', '耳机']);
    expect(pathMap.get(111)).toEqual(['数码', '耳机', '蓝牙耳机']);
  });

  it('buildCategoryCascaderOptions 应按层级禁用选项', () => {
    const options = buildCategoryCascaderOptions(categoryTree, 2);
    const level1 = options[0];
    const level2 = level1.children?.[0];
    const level3 = level2?.children?.[0];

    expect(level1.disabled).toBe(false);
    expect(level2?.disabled).toBe(false);
    expect(level3?.disabled).toBe(true);
  });
});
