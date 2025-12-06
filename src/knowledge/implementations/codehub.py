"""CodeHub知识库实现 - 用于索引代码仓库结构到知识图谱"""

import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from src import config
from src.knowledge.base import KnowledgeBase
from src.knowledge.codehub_graph import CodeHubGraphBuilder
from src.utils import logger


class CodeHubKB(KnowledgeBase):
    """基于知识图谱的CodeHub知识库实现，用于索引代码仓库结构"""

    def __init__(self, work_dir: str, **kwargs):
        """
        初始化 CodeHub 知识库

        Args:
            work_dir: 工作目录
            **kwargs: 其他配置参数
        """
        super().__init__(work_dir)
        self.graph_builder = CodeHubGraphBuilder()
        logger.info("CodeHubKB initialized")

    @property
    def kb_type(self) -> str:
        """知识库类型标识"""
        return "codehub"

    async def _create_kb_instance(self, db_id: str, kb_config: dict) -> Any:
        """创建知识库实例（CodeHub不需要底层实例，使用图数据库）"""
        return None

    async def _initialize_kb_instance(self, instance: Any) -> None:
        """初始化知识库实例"""
        pass

    async def add_content(self, db_id: str, items: list[str], params: dict | None = None) -> list[dict]:
        """
        添加代码仓库到知识库（构建知识图谱）

        Args:
            db_id: 数据库ID
            items: 仓库名称列表（相对于codehub目录）
            params: 处理参数

        Returns:
            处理结果列表
        """
        if db_id not in self.databases_meta:
            raise ValueError(f"Database {db_id} not found")

        processed_items_info = []
        # 延迟导入避免循环导入
        from src.agents.common.agent_context import get_user_id
        user_id = get_user_id()
        
        # 转换用户ID类型（可能是字符串）
        if user_id:
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                user_id = None

        for repo_name in items:
            try:
                # 获取仓库路径
                if user_id:
                    codehub_dir = Path(config.save_dir) / "codehub" / f"user_{user_id}"
                else:
                    codehub_dir = Path(config.save_dir) / "codehub"

                repo_path = codehub_dir / repo_name

                if not repo_path.exists() or not repo_path.is_dir():
                    logger.warning(f"Repository {repo_name} not found at {repo_path}")
                    processed_items_info.append(
                        {
                            "file_id": f"repo_{repo_name}",
                            "filename": repo_name,
                            "path": str(repo_path),
                            "status": "error",
                            "error": f"Repository not found: {repo_name}",
                        }
                    )
                    continue

                # 构建知识图谱（增量更新）
                logger.info(f"Building knowledge graph for repository: {repo_name} (incremental update)")
                graph_info = await self.graph_builder.build_repository_graph(
                    repo_name=repo_name,
                    repo_path=repo_path,
                    db_id=db_id,
                    user_id=user_id,
                    incremental=True,  # 启用增量更新
                )

                # 创建文件记录
                file_id = f"repo_{repo_name}_{user_id or 'default'}"
                self.files_meta[file_id] = {
                    "database_id": db_id,
                    "filename": repo_name,
                    "path": str(repo_path),
                    "file_type": "repository",
                    "status": "done",
                    "created_at": datetime.now().timestamp(),
                    "graph_info": graph_info,
                }

                processed_items_info.append(
                    {
                        "file_id": file_id,
                        "filename": repo_name,
                        "path": str(repo_path),
                        "status": "done",
                        "graph_info": graph_info,
                    }
                )

                logger.info(f"Successfully indexed repository {repo_name}: {graph_info}")

            except Exception as e:
                error_msg = f"Failed to index repository {repo_name}: {str(e)}"
                logger.error(f"{error_msg}\n{traceback.format_exc()}")
                processed_items_info.append(
                    {
                        "file_id": f"repo_{repo_name}",
                        "filename": repo_name,
                        "path": "",
                        "status": "error",
                        "error": error_msg,
                    }
                )

        self._save_metadata()
        return processed_items_info

    async def aquery(self, query_text: str, db_id: str, **kwargs) -> list[dict]:
        """
        异步查询知识库（检索代码仓库结构）

        Args:
            query_text: 查询文本（仓库名、目录路径、文件名等）
            db_id: 数据库ID
            **kwargs: 查询参数

        Returns:
            检索结果列表
        """
        if db_id not in self.databases_meta:
            raise ValueError(f"Database {db_id} not found")

        top_k = kwargs.get("top_k", 10)
        similarity_threshold = kwargs.get("similarity_threshold", 0.0)

        # 使用图数据库查询
        try:
            results = await self.graph_builder.query_repository_structure(
                query_text=query_text,
                db_id=db_id,
                top_k=top_k,
                threshold=similarity_threshold,
            )
            return results
        except Exception as e:
            logger.error(f"Query failed: {e}\n{traceback.format_exc()}")
            return []

    async def delete_file(self, db_id: str, file_id: str) -> None:
        """删除文件（从知识图谱中移除）"""
        if file_id not in self.files_meta:
            return

        file_info = self.files_meta[file_id]
        repo_name = file_info.get("filename", "")

        # 从图数据库中删除
        try:
            await self.graph_builder.delete_repository_from_graph(db_id=db_id, repo_name=repo_name)
        except Exception as e:
            logger.error(f"Failed to delete repository from graph: {e}")

        # 删除文件记录
        del self.files_meta[file_id]
        self._save_metadata()

    async def get_file_basic_info(self, db_id: str, file_id: str) -> dict:
        """获取文件基本信息"""
        if file_id not in self.files_meta:
            raise ValueError(f"File {file_id} not found")

        file_info = self.files_meta[file_id].copy()
        file_info["file_id"] = file_id
        return file_info

    async def get_file_content(self, db_id: str, file_id: str) -> dict:
        """获取文件内容信息（对于仓库，返回结构信息）"""
        if file_id not in self.files_meta:
            raise ValueError(f"File {file_id} not found")

        file_info = self.files_meta[file_id]
        repo_name = file_info.get("filename", "")

        # 获取仓库结构
        try:
            structure = await self.graph_builder.get_repository_structure(
                db_id=db_id, repo_name=repo_name
            )
            return {
                "file_id": file_id,
                "chunks": [],
                "lines": [],
                "structure": structure,
            }
        except Exception as e:
            logger.error(f"Failed to get repository structure: {e}")
            return {
                "file_id": file_id,
                "chunks": [],
                "lines": [],
                "structure": {},
            }

    async def get_file_info(self, db_id: str, file_id: str) -> dict:
        """获取文件完整信息"""
        basic_info = await self.get_file_basic_info(db_id, file_id)
        content_info = await self.get_file_content(db_id, file_id)
        return {**basic_info, **content_info}

    async def update_file_name(self, db_id: str, file_id: str, new_filename: str) -> dict:
        """更新文件名"""
        if file_id not in self.files_meta:
            raise ValueError(f"File {file_id} not found")

        old_filename = self.files_meta[file_id]["filename"]
        self.files_meta[file_id]["filename"] = new_filename
        self._save_metadata()

        return await self.get_file_info(db_id, file_id)

    async def update_chunk_content(self, db_id: str, file_id: str, chunk_id: str, new_content: str) -> dict:
        """更新chunk内容（CodeHub不支持）"""
        raise NotImplementedError("CodeHub knowledge base does not support chunk updates")

