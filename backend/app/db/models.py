"""
SQLAlchemy ORM 模型定义
所有数据库表的映射对象
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, Index, text
from sqlalchemy.orm import relationship

from app.db.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="client")  # client / admin
    token_version = Column(Integer, nullable=False, default=1)  # 用于强制踢出
    is_active = Column(Integer, nullable=False, default=1)  # 1=正常，0=封禁
    
    # 登录安全字段
    failed_login_attempts = Column(Integer, default=0)
    lockout_until = Column(String(50), nullable=True)  # ISO格式时间字符串
    
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    
    # 关系映射
    addresses = relationship("UserAddress", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    recovery_requests = relationship(
        "AccountRecoveryRequest",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="AccountRecoveryRequest.user_id",
    )


class RefreshToken(Base):
    """Refresh Token 黑名单表 (用于主动登出/踢出)"""
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 哈希
    expires_at = Column(String(50), nullable=False)  # ISO格式
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())


class AccessTokenBlocklist(Base):
    """Access Token 拦截表（用于主动登出后立即失效）"""
    __tablename__ = "access_token_blocklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(String(50), nullable=False)  # ISO格式
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())


class AccountRecoveryRequest(Base):
    """账号恢复申请表（用于封禁用户发起解封申请）"""
    __tablename__ = "account_recovery_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)
    reason = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending/approved/rejected
    admin_note = Column(String(500), nullable=True)
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat(), index=True)
    processed_at = Column(String(50), nullable=True)

    # 关系映射
    user = relationship("User", foreign_keys=[user_id], back_populates="recovery_requests")


class ProductCategory(Base):
    """商品分类表 (三级树形结构)"""
    __tablename__ = "product_categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_code = Column(String(20), unique=True, nullable=False, index=True)  # 业务编码: 01, 01-01, 01-01-01
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    level = Column(Integer, nullable=False)  # 1/2/3 级
    sort_order = Column(Integer, default=0)
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    
    # 关系映射
    children = relationship("ProductCategory", backref="parent", remote_side=[id])
    products = relationship("Product", back_populates="category")


class Product(Base):
    """商品主表"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    image_url = Column(String(500), nullable=True)
    tags = Column(Text, nullable=True)  # JSON 字符串数组: ["男款", "夏季"]
    hot_score = Column(Integer, default=0)  # 热度分数 (后台人工设定)
    status = Column(String(20), default="on_sale")  # on_sale / off_sale
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String(50), nullable=True)
    
    # 关系映射
    category = relationship("ProductCategory", back_populates="products")
    embedding = relationship("ProductEmbedding", uselist=False, back_populates="product", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="product")


class ProductEmbedding(Base):
    """商品向量表 (OpenAI Embeddings)"""
    __tablename__ = "product_embeddings"
    
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    embedding = Column(Text, nullable=False)  # JSON 存储 1536 维向量
    content_hash = Column(String(64), nullable=False)  # SHA-256(name + description)
    updated_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    
    # 关系映射
    product = relationship("Product", back_populates="embedding")


class UserAddress(Base):
    """用户收货地址表"""
    __tablename__ = "user_addresses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    province = Column(String(50), nullable=False)
    city = Column(String(50), nullable=False)
    district = Column(String(50), nullable=False)
    detail_address = Column(String(200), nullable=False)
    is_default = Column(Integer, default=0)  # 0 / 1
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    
    # 关系映射
    user = relationship("User", back_populates="addresses")
    
    # 索引
    __table_args__ = (
        Index("idx_user_default", user_id, is_default),
        # SQLite 部分唯一索引：同一用户只能有一个默认地址
        Index(
            "uq_user_default_address",
            user_id,
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )


class Order(Base):
    """订单主表"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(20), default="pending")  # pending/paid/shipped/completed/cancelled
    receiver_info = Column(Text, nullable=False)  # 地址快照 (JSON)
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String(50), nullable=True)
    
    # 关系映射
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """订单明细表"""
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_name = Column(String(200), nullable=False)  # 商品名称快照
    buy_price = Column(Float, nullable=False)  # 下单时价格快照
    quantity = Column(Integer, nullable=False)
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    
    # 关系映射
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class ChatMessage(Base):
    """AI 对话记录表"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    ui_type = Column(String(50), nullable=True)  # text / product_cards / order_card
    payload = Column(Text, nullable=True)  # 功能数据 (JSON)
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    
    # 关系映射
    user = relationship("User", back_populates="chat_messages")
    
    # 索引
    __table_args__ = (
        Index("idx_user_created", user_id, created_at),
    )
