"""
核心配置模块
使用 Pydantic Settings 读取环境变量
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    
    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./ecommerce.db"
    
    # OpenAI 配置
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"  # 可替换为代理地址
    
    # 千问 Embedding 配置（可选，不配置时回退到 OPENAI_*）
    QWEN_API_KEY: str = ""
    QWEN_EMBEDDING_MODEL: str = "qwen3-vl-embedding"
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # CORS 配置
    CORS_ORIGINS: str = "http://localhost:5174"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
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
