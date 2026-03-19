/** 商品分类树节点（与后端 /products/categories 响应结构对齐） */
export interface CategoryNode {
  id: number;
  name: string;
  level: number;
  parent_id?: number | null;
  children: CategoryNode[];
}

/** Antd Cascader 选项结构（数值 ID） */
export interface CategoryCascaderOption {
  value: number;
  label: string;
  disabled?: boolean;
  children?: CategoryCascaderOption[];
}

/**
 * 将分类树转换为路径映射：分类ID -> [一级名称, 二级名称, 三级名称]
 * 用于商品列表直接回显一级/二级/三级列，避免重复递归查找。
 */
export function buildCategoryPathMap(
  nodes: CategoryNode[],
  parentPath: string[] = [],
  output: Map<number, string[]> = new Map()
): Map<number, string[]> {
  for (const node of nodes) {
    const path = [...parentPath, node.name];
    output.set(node.id, path);
    buildCategoryPathMap(node.children ?? [], path, output);
  }
  return output;
}

/**
 * 构建 Cascader 选项
 * @param maxSelectableLevel 最大可选层级。若设置为 2，则三级分类会被禁用（但仍展示层级结构）。
 */
export function buildCategoryCascaderOptions(
  nodes: CategoryNode[],
  maxSelectableLevel?: number
): CategoryCascaderOption[] {
  return nodes.map(node => ({
    value: node.id,
    label: node.name,
    disabled: typeof maxSelectableLevel === 'number' ? node.level > maxSelectableLevel : false,
    children: buildCategoryCascaderOptions(node.children ?? [], maxSelectableLevel),
  }));
}

