#!/bin/bash

# 数据库备份脚本
# 使用方法: ./backup_db.sh

# 配置
BACKUP_DIR="../data/backups"
DB_FILE="../data/ecommerce.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/ecommerce_$TIMESTAMP.db"
KEEP_DAYS=7

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 检查数据库文件是否存在
if [ ! -f "$DB_FILE" ]; then
    echo "❌ 错误: 数据库文件不存在: $DB_FILE"
    exit 1
fi

# 使用 SQLite 的在线备份命令（更安全）
echo "🔄 开始备份数据库..."
sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"

if [ $? -eq 0 ]; then
    echo "✅ 备份成功: $BACKUP_FILE"
    
    # 清理旧备份（保留最近 N 天）
    echo "🧹 清理 $KEEP_DAYS 天前的备份..."
    find "$BACKUP_DIR" -name "ecommerce_*.db" -mtime +$KEEP_DAYS -delete
    
    # 显示备份文件大小
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "📦 备份文件大小: $SIZE"
    
    # 显示当前备份列表
    echo "📋 当前备份列表:"
    ls -lh "$BACKUP_DIR"/ecommerce_*.db | tail -5
else
    echo "❌ 备份失败"
    exit 1
fi
