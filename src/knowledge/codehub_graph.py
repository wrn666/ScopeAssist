"""代码仓库知识图谱构建器 - 将代码仓库结构构建为知识图谱"""

import os
import traceback
from pathlib import Path
from typing import Any

from src import config
from src.knowledge.graph import GraphDatabase
from src.models import select_embedding_model
from src.utils import logger


class CodeHubGraphBuilder:
    """代码仓库知识图谱构建器"""

    def __init__(self):
        """初始化构建器"""
        self.graph_db = GraphDatabase()
        if not self.graph_db.is_running():
            self.graph_db.start()

        # 使用与图数据库相同的嵌入模型
        embed_model_name = os.getenv("GRAPH_EMBED_MODEL_NAME") or "siliconflow/BAAI/bge-m3"
        self.embed_model = select_embedding_model(embed_model_name)

    def _get_kgdb_name(self, db_id: str) -> str:
        """获取图数据库名称"""
        return f"codehub_{db_id}"

    async def build_repository_graph(
        self, repo_name: str, repo_path: Path, db_id: str, user_id: int | None = None, incremental: bool = True
    ) -> dict:
        """
        构建代码仓库的知识图谱（支持增量更新）

        Args:
            repo_name: 仓库名称
            repo_path: 仓库路径
            db_id: 数据库ID
            user_id: 用户ID
            incremental: 是否增量更新（如果为True，先删除旧节点再添加新节点）

        Returns:
            构建信息字典
        """
        kgdb_name = self._get_kgdb_name(db_id)

        # 确保图数据库存在
        if not self.graph_db.is_running():
            self.graph_db.start()

        # 创建或使用图数据库
        self.graph_db.create_graph_database(kgdb_name)
        self.graph_db.use_database(kgdb_name)

        # 如果是增量更新，先删除该仓库的旧节点
        if incremental:
            try:
                await self._delete_repository_nodes(kgdb_name, repo_name)
            except Exception as e:
                logger.warning(f"Failed to delete old nodes for {repo_name}: {e}")

        # 构建仓库结构
        triples = []
        nodes_info = {}

        def _traverse_directory(dir_path: Path, parent_node: str | None = None, depth: int = 0):
            """递归遍历目录，构建节点和关系"""
            if depth > 20:  # 限制深度，避免过深
                return

            # 创建目录节点
            rel_path = dir_path.relative_to(repo_path)
            dir_node_name = f"{repo_name}:{rel_path}" if str(rel_path) != "." else repo_name

            if dir_node_name not in nodes_info:
                nodes_info[dir_node_name] = {
                    "type": "directory",
                    "path": str(rel_path),
                    "name": dir_path.name if str(rel_path) != "." else repo_name,
                }

            # 添加目录到父目录的关系
            if parent_node:
                triples.append(
                    {
                        "h": parent_node,
                        "r": "contains",
                        "t": dir_node_name,
                    }
                )

            # 遍历子项
            try:
                for item in sorted(dir_path.iterdir()):
                    # 跳过.git目录
                    if item.name == ".git":
                        continue

                    if item.is_dir():
                        # 递归处理子目录
                        _traverse_directory(item, dir_node_name, depth + 1)
                    elif item.is_file():
                        # 创建文件节点
                        file_rel_path = item.relative_to(repo_path)
                        file_node_name = f"{repo_name}:{file_rel_path}"

                        if file_node_name not in nodes_info:
                            nodes_info[file_node_name] = {
                                "type": "file",
                                "path": str(file_rel_path),
                                "name": item.name,
                                "extension": item.suffix,
                                "size": item.stat().st_size,
                            }

                        # 添加文件到目录的关系
                        triples.append(
                            {
                                "h": dir_node_name,
                                "r": "contains",
                                "t": file_node_name,
                            }
                        )
            except PermissionError:
                logger.warning(f"Permission denied: {dir_path}")

        # 创建仓库根节点
        repo_node_name = repo_name
        nodes_info[repo_node_name] = {
            "type": "repository",
            "path": ".",
            "name": repo_name,
            "full_path": str(repo_path),
        }

        # 遍历仓库结构
        _traverse_directory(repo_path, repo_node_name)

        # 添加仓库元数据关系
        if user_id:
            user_node_name = f"user_{user_id}"
            triples.append(
                {
                    "h": user_node_name,
                    "r": "owns",
                    "t": repo_node_name,
                }
            )

        # 将节点和关系添加到图数据库
        if triples:
            logger.info(f"Adding {len(triples)} triples to graph database {kgdb_name}")
            await self.graph_db.txt_add_vector_entity(triples, kgdb_name=kgdb_name)

        return {
            "nodes_count": len(nodes_info),
            "triples_count": len(triples),
            "repository": repo_name,
        }

    async def query_repository_structure(
        self, query_text: str, db_id: str, top_k: int = 10, threshold: float = 0.0
    ) -> list[dict]:
        """
        查询代码仓库结构

        Args:
            query_text: 查询文本（仓库名、目录路径、文件名等）
            db_id: 数据库ID
            top_k: 返回结果数量
            threshold: 相似度阈值

        Returns:
            检索结果列表
        """
        kgdb_name = self._get_kgdb_name(db_id)

        if not self.graph_db.is_running():
            self.graph_db.start()

        self.graph_db.use_database(kgdb_name)

        # 使用图数据库查询节点
        try:
            query_results = self.graph_db.query_node(
                keyword=query_text,
                threshold=max(threshold, 0.3),  # 至少0.3的阈值
                kgdb_name=kgdb_name,
                hops=2,
                max_entities=top_k,
                return_format="graph",
            )

            # 格式化结果
            results = []
            seen_nodes = set()
            
            # 从nodes中提取节点信息
            for node in query_results.get("nodes", [])[:top_k]:
                # 节点可能是dict或字符串
                if isinstance(node, dict):
                    node_name = node.get("name", "")
                    node_id = node.get("id", "")
                else:
                    node_name = str(node)
                    node_id = node_name
                
                if not node_name or node_id in seen_nodes:
                    continue
                
                seen_nodes.add(node_id)

                # 解析节点名称，提取仓库和路径信息
                if ":" in node_name:
                    repo_name, path = node_name.split(":", 1)
                else:
                    repo_name = node_name
                    path = "."

                # 确定节点类型
                node_type = "unknown"
                if "repository" in node_name.lower() or path == ".":
                    node_type = "repository"
                elif path.endswith("/") or not Path(path).suffix:
                    node_type = "directory"
                else:
                    node_type = "file"

                # 构建结果
                bash_path = f"{repo_name}/{path}" if path != "." else repo_name
                result_dict = {
                    "content": (
                        f"代码仓库: {repo_name}\n"
                        f"路径: {path}\n"
                        f"类型: {node_type}\n"
                        f"使用bash工具查看: bash工具的工作目录设置为 '{bash_path}'，然后执行命令查看内容"
                    ),
                    "source": f"codehub://{repo_name}/{path}",
                    "metadata": {
                        "repository": repo_name,
                        "path": path,
                        "node_name": node_name,
                        "type": node_type,
                        "bash_path": bash_path,  # 用于bash工具的路径
                    },
                    "score": 0.8,  # 默认分数
                }

                results.append(result_dict)

            return results

        except Exception as e:
            logger.error(f"Query repository structure failed: {e}\n{traceback.format_exc()}")
            return []

    async def get_repository_structure(self, db_id: str, repo_name: str) -> dict:
        """
        获取仓库的完整结构

        Args:
            db_id: 数据库ID
            repo_name: 仓库名称

        Returns:
            仓库结构字典
        """
        kgdb_name = self._get_kgdb_name(db_id)

        if not self.graph_db.is_running():
            self.graph_db.start()

        self.graph_db.use_database(kgdb_name)

        # 查询仓库的所有节点和关系
        try:
            with self.graph_db.driver.session(database="neo4j") as session:
                query = """
                MATCH (repo:Entity {name: $repo_name, kgdb_id: $kgdb_id})
                OPTIONAL MATCH (repo)-[*1..5]-(related:Entity {kgdb_id: $kgdb_id})
                RETURN DISTINCT repo, collect(DISTINCT related) as related_nodes
                LIMIT 1000
                """
                result = session.run(query, repo_name=repo_name, kgdb_id=kgdb_name)

                nodes = []
                for record in result:
                    repo_node = record["repo"]
                    if repo_node:
                        nodes.append({"name": repo_node["name"], "type": "repository"})

                    related = record["related_nodes"]
                    for node in related[:100]:  # 限制数量
                        nodes.append({"name": node["name"], "type": "unknown"})

                return {"repository": repo_name, "nodes": nodes}

        except Exception as e:
            logger.error(f"Get repository structure failed: {e}\n{traceback.format_exc()}")
            return {"repository": repo_name, "nodes": []}

    async def delete_repository_from_graph(self, db_id: str, repo_name: str) -> None:
        """
        从图数据库中删除仓库

        Args:
            db_id: 数据库ID
            repo_name: 仓库名称
        """
        kgdb_name = self._get_kgdb_name(db_id)

        if not self.graph_db.is_running():
            self.graph_db.start()

        self.graph_db.use_database(kgdb_name)

        await self._delete_repository_nodes(kgdb_name, repo_name)

    async def _delete_repository_nodes(self, kgdb_name: str, repo_name: str) -> None:
        """
        删除指定仓库的所有节点

        Args:
            kgdb_name: 知识库ID
            repo_name: 仓库名称
        """
        try:
            with self.graph_db.driver.session(database="neo4j") as session:
                # 删除仓库及其所有相关节点（包括以repo_name:开头的节点），且属于指定知识库
                query = """
                MATCH (n:Entity)
                WHERE n.kgdb_id = $kgdb_id AND (n.name = $repo_name OR n.name STARTS WITH $repo_prefix)
                OPTIONAL MATCH (n)-[r]-()
                DELETE r, n
                """
                repo_prefix = f"{repo_name}:"
                result = session.run(query, kgdb_id=kgdb_name, repo_name=repo_name, repo_prefix=repo_prefix)
                summary = result.consume()
                deleted_count = summary.counters.nodes_deleted
                logger.info(f"Deleted {deleted_count} nodes for repository {repo_name} from knowledge base {kgdb_name}")

        except Exception as e:
            logger.error(f"Delete repository nodes failed: {e}\n{traceback.format_exc()}")
            raise

