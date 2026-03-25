"""
核心配置模块
使用 Pydantic Settings 读取环境变量
"""
from typing import Optional

from pydantic import field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """应用配置类"""
    
    # 应用基础配置
    APP_NAME: str = "AI电商平台"
    DEBUG: bool = False
    
    # JWT 配置
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2小时
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7      # 7天
    # Cookie 安全策略：生产环境建议开启（HTTPS 下生效）
    COOKIE_SECURE: bool = False
    
    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./ecommerce.db"
    
    # OpenAI 配置
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"  # 可替换为代理地址
    PEXELS_API_KEY: str = ""  # 商品种子图片抓取脚本可选配置
    
    # 千问 Embedding 配置（可选，不配置时回退到 OPENAI_*）
    QWEN_API_KEY: str = ""
    QWEN_EMBEDDING_MODEL: str = "qwen3-vl-embedding"
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MULTIMODAL_EMBEDDING_URL: str = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding"
    QWEN_EMBEDDING_DIMENSION: Optional[int] = 1024
    
    # CORS 配置
    CORS_ORIGINS: str = "http://localhost:5174"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        """
        本项目优先读取 .env，避免本机/IDE 注入的同名环境变量覆盖开发配置。
        加载顺序：初始化参数 > .env > 系统环境变量 > secrets 文件。
        """
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    @field_validator("DEBUG", mode="before")
    @classmethod
    def validate_debug_bool(cls, value):
        """
        兼容多种 DEBUG 写法：
        - true/false, 1/0, yes/no
        - debug/dev/development
        - release/prod/production
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value

    @field_validator("COOKIE_SECURE", mode="before")
    @classmethod
    def validate_cookie_secure_bool(cls, value):
        """
        兼容 COOKIE_SECURE 的多种写法，避免部署环境传值差异导致行为异常。
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return value
    
    @property
    def cors_origins_list(self) -> list[str]:
        """将 CORS_ORIGINS 字符串转为列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def embedding_api_key(self) -> str:
        """
        Embedding 专用 API Key。
        优先使用千问 QWEN_API_KEY，未配置时回退到 OPENAI_API_KEY。
        """
        return self.QWEN_API_KEY or self.OPENAI_API_KEY

    @property
    def embedding_model(self) -> str:
        """
        Embedding 专用模型名。
        优先使用千问 QWEN_EMBEDDING_MODEL，未配置时回退到 OPENAI_EMBEDDING_MODEL。
        """
        return self.QWEN_EMBEDDING_MODEL or self.OPENAI_EMBEDDING_MODEL

    @property
    def embedding_base_url(self) -> str:
        """
        Embedding 专用 Base URL。
        优先使用千问 QWEN_BASE_URL，未配置时回退到 OPENAI_BASE_URL。
        """
        return self.QWEN_BASE_URL or self.OPENAI_BASE_URL


# 全局配置实例
settings = Settings()
