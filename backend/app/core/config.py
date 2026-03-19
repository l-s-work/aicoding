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


# 全局配置实例
settings = Settings()
