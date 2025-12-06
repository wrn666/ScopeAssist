"""
文档处理器基类

提供统一的文档处理接口和基础功能
"""

import os
from abc import ABC, abstractmethod
from typing import Any


class DocumentProcessorException(Exception):
    """文档处理器异常基类"""

    def __init__(self, message: str, service_name: str | None = None, error_code: str | None = None):
        super().__init__(message)
        self.service_name = service_name
        self.error_code = error_code


class BaseDocumentProcessor(ABC):
    """文档处理器基类"""

    def __init__(self, **kwargs):
        """初始化处理器"""
        pass

    @abstractmethod
    def get_service_name(self) -> str:
        """返回服务名称"""
        pass

    @abstractmethod
    def get_supported_extensions(self) -> list[str]:
        """返回支持的文件扩展名列表"""
        pass

    def supports_file_type(self, file_ext: str) -> bool:
        """检查是否支持指定的文件类型"""
        return file_ext.lower() in self.get_supported_extensions()

    @abstractmethod
    def check_health(self) -> dict[str, Any]:
        """
        检查服务健康状态

        Returns:
            dict: 包含以下字段的字典：
                - status: "healthy" | "unhealthy" | "timeout" | "unavailable" | "error"
                - message: 状态描述信息
                - details: 详细状态信息（可选）
        """
        pass

    @abstractmethod
    def process_file(self, file_path: str, params: dict[str, Any] | None = None) -> str:
        """
        处理文件并返回文本内容

        Args:
            file_path: 文件路径
            params: 处理参数

        Returns:
            str: 提取的文本内容

        Raises:
            DocumentProcessorException: 处理失败时抛出
        """
        pass

    def validate_file(self, file_path: str) -> None:
        """验证文件是否存在且可读"""
        if not os.path.exists(file_path):
            raise DocumentProcessorException(
                f"文件不存在: {file_path}", self.get_service_name(), "file_not_found"
            )

        if not os.path.isfile(file_path):
            raise DocumentProcessorException(
                f"路径不是文件: {file_path}", self.get_service_name(), "not_a_file"
            )

        if not os.access(file_path, os.R_OK):
            raise DocumentProcessorException(
                f"文件不可读: {file_path}", self.get_service_name(), "file_not_readable"
            )

