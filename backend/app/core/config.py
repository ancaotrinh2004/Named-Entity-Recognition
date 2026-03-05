from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")
    
    # KServe endpoint qua NGINX gateway
    GATEWAY_URL: str = "http://35.240.244.150"
    GATEWAY_HOST: str = "api.phobert-medical.example.com"
    KSERVE_PATH: str = "/api/v1/predict"

    # API Keys hợp lệ, comma-separated
    # VD: VALID_API_KEYS="sk-admin-abc123,sk-client-xyz456"
    VALID_API_KEYS: str = ""

    # Timeout gọi KServe (giây)
    KSERVE_TIMEOUT: int = 30

    # CORS origins - string format (sẽ parse thành list trong main.py)
    # Có thể là "*" hoặc "http://localhost:3000,http://localhost"
    CORS_ORIGINS: str = "*"

    @property
    def valid_keys_set(self) -> set[str]:
        """Hỗ trợ cả 2 format: newline (từ K8s Secret) và comma (từ .env local)"""
        raw = self.VALID_API_KEYS
        keys = set()
        for k in raw.replace(",", "\n").splitlines():
            k = k.strip()
            if k:
                keys.add(k)
        return keys
    
    def get_cors_origins(self) -> list[str]:
        """Parse CORS_ORIGINS string thành list"""
        if isinstance(self.CORS_ORIGINS, str):
            if self.CORS_ORIGINS == "*":
                return ["*"]
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return self.CORS_ORIGINS


settings = Settings()