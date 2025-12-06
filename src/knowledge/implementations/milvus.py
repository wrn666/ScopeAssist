import asyncio
import json
import os
import traceback
from functools import partial
from typing import Any

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, db, utility

from src.knowledge.base import KnowledgeBase
from src.knowledge.indexing import process_file_to_markdown, process_url_to_markdown
from src.knowledge.utils.kb_utils import (
    get_embedding_config,
    prepare_item_metadata,
    split_text_into_chunks,
)
from src.models.embed import OtherEmbedding
from src.utils import hashstr, logger

MILVUS_AVAILABLE = True


class MilvusKB(KnowledgeBase):
    """基于 Milvus 的生产级向量知识库实现"""

    def __init__(self, work_dir: str, **kwargs):
        """
        初始化 Milvus 知识库

        Args:
            work_dir: 工作目录
            **kwargs: 其他配置参数
        """
        super().__init__(work_dir)

        if not MILVUS_AVAILABLE:
            raise ImportError("pymilvus is not installed. Please install it with: pip install pymilvus")

        # Milvus 配置
        # self.milvus_host = kwargs.get('milvus_host', os.getenv('MILVUS_HOST', 'localhost'))
        # self.milvus_port = kwargs.get('milvus_port', int(os.getenv('MILVUS_PORT', '19530')))
        self.milvus_token = kwargs.get("milvus_token", os.getenv("MILVUS_TOKEN", ""))
        self.milvus_uri = kwargs.get("milvus_uri", os.getenv("MILVUS_URI", "http://localhost:19530"))
        self.milvus_db = kwargs.get("milvus_db", "yuxi_know")

        # 连接名称
        self.connection_alias = f"milvus_{hashstr(work_dir, 6)}"

        # 存储集合映射 {db_id: Collection}
        self.collections: dict[str, Any] = {}

        # 分块配置
        self.chunk_size = kwargs.get("chunk_size", 1000)
        self.chunk_overlap = kwargs.get("chunk_overlap", 200)

        # 元数据锁
        self._metadata_lock = asyncio.Lock()

        # 初始化连接
        self._init_connection()

        logger.info("MilvusKB initialized")

    @property
    def kb_type(self) -> str:
        """知识库类型标识"""
        return "milvus"

    def _init_connection(self):
        """初始化 Milvus 连接"""
        try:
            # 连接到 Milvus
            connections.connect(alias=self.connection_alias, uri=self.milvus_uri, token=self.milvus_token)

            # 创建数据库（如果不存在）
            try:
                if self.milvus_db not in db.list_database():
                    db.create_database(self.milvus_db)
                db.using_database(self.milvus_db)
            except Exception as e:
                logger.warning(f"Database operation failed, using default: {e}")

            logger.info(f"Connected to Milvus at {self.milvus_uri}")

        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise

    async def _create_kb_instance(self, db_id: str, kb_config: dict) -> Any:
        """创建 Milvus 集合"""
        logger.info(f"Creating Milvus collection for {db_id}")

        if db_id not in self.databases_meta:
            raise ValueError(f"Database {db_id} not found")

        embed_info = self.databases_meta[db_id].get("embed_info", {})
        collection_name = db_id

        try:
            # 检查集合是否存在
            if utility.has_collection(collection_name, using=self.connection_alias):
                collection = Collection(name=collection_name, using=self.connection_alias)

                # 检查嵌入模型是否匹配
                description = collection.description
                expected_model = embed_info.get("name") if embed_info else "default"

                if expected_model not in description:
                    logger.warning(f"Collection {collection_name} model mismatch, recreating...")
                    utility.drop_collection(collection_name, using=self.connection_alias)
                    raise Exception("Model mismatch, recreating collection")

                logger.info(f"Retrieved existing collection: {collection_name}")
            else:
                raise Exception("Collection not found, creating new one")

        except Exception:
            # 创建新集合
            embedding_dim = embed_info.get("dimension", 1024) if embed_info else 1024
            model_name = embed_info.get("name", "default") if embed_info else "default"

            # 定义集合Schema
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embedding_dim),
            ]

            schema = CollectionSchema(
                fields=fields, description=f"Knowledge base collection for {db_id} using {model_name}"
            )

            # 创建集合
            collection = Collection(name=collection_name, schema=schema, using=self.connection_alias)

            # 创建索引
            index_params = {"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 1024}}
            collection.create_index("embedding", index_params)

            logger.info(f"Created new Milvus collection: {collection_name}")

        return collection

    async def _initialize_kb_instance(self, instance: Any) -> None:
        """初始化 Milvus 集合（加载到内存）"""
        try:
            instance.load()
            logger.info("Milvus collection loaded into memory")
        except Exception as e:
            logger.warning(f"Failed to load collection into memory: {e}")

    def _get_async_embedding_function(self, embed_info: dict):
        """获取 embedding 函数"""
        config_dict = get_embedding_config(embed_info)
        embedding_model = OtherEmbedding(
            model=config_dict.get("model"),
            base_url=config_dict.get("base_url"),
            api_key=config_dict.get("api_key"),
        )

        return partial(embedding_model.abatch_encode, batch_size=40)

    def _get_embedding_function(self, embed_info: dict):
        """获取 embedding 函数"""
        config_dict = get_embedding_config(embed_info)
        embedding_model = OtherEmbedding(
            model=config_dict.get("model"),
            base_url=config_dict.get("base_url"),
            api_key=config_dict.get("api_key"),
        )

        return partial(embedding_model.batch_encode, batch_size=40)

    async def _get_milvus_collection(self, db_id: str):
        """获取或创建 Milvus 集合"""
        if db_id in self.collections:
            return self.collections[db_id]

        if db_id not in self.databases_meta:
            return None

        try:
            # 创建集合
            collection = await self._create_kb_instance(db_id, {})
            await self._initialize_kb_instance(collection)

            self.collections[db_id] = collection
            return collection

        except Exception as e:
            logger.error(f"Failed to create Milvus collection for {db_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _split_text_into_chunks(self, text: str, file_id: str, filename: str, params: dict) -> list[dict]:
        """将文本分割成块"""
        return split_text_into_chunks(text, file_id, filename, params)

    async def add_content(self, db_id: str, items: list[str], params: dict | None = {}) -> list[dict]:
        """添加内容（文件/URL）"""
        if db_id not in self.databases_meta:
            raise ValueError(f"Database {db_id} not found")

        collection = await self._get_milvus_collection(db_id)
        if not collection:
            raise ValueError(f"Failed to get Milvus collection for {db_id}")

        embed_info = self.databases_meta[db_id].get("embed_info", {})
        embedding_function = self._get_async_embedding_function(embed_info)

        content_type = params.get("content_type", "file") if params else "file"
        processed_items_info = []

        for item in items:
            metadata = prepare_item_metadata(item, content_type, db_id)
            file_id = metadata["file_id"]
            filename = metadata["filename"]

            file_record = metadata.copy()
            del file_record["file_id"]
            async with self._metadata_lock:
                self.files_meta[file_id] = file_record
                self._save_metadata()

            file_record["file_id"] = file_id

            # 添加到处理队列
            self._add_to_processing_queue(file_id)
            logger.debug(f"[{file_id}] 文件已添加到处理队列，开始处理文件: {filename}")

            try:
                logger.debug(f"[{file_id}] 开始处理文件到 Markdown，文件路径: {item}, 内容类型: {content_type}")
                if content_type == "file":
                    markdown_content = await process_file_to_markdown(item, params=params)
                    pdf_path = None
                else:
                    # 对于URL，如果转换为PDF，需要保存PDF文件到知识库目录
                    upload_dir = self.get_db_upload_path(db_id)
                    os.makedirs(upload_dir, exist_ok=True)
                    # 生成PDF文件名（使用URL本身）
                    from src.utils import url_to_filename
                    pdf_filename = url_to_filename(item)
                    target_pdf_path = os.path.join(upload_dir, pdf_filename)
                    
                    markdown_content, pdf_path = await process_url_to_markdown(item, params=params, target_pdf_path=target_pdf_path)
                    
                    # 如果PDF文件已保存，更新元数据中的文件路径
                    if pdf_path and os.path.exists(pdf_path):
                        async with self._metadata_lock:
                            self.files_meta[file_id]["path"] = pdf_path
                            self.files_meta[file_id]["file_type"] = "pdf"
                            self.files_meta[file_id]["filename"] = pdf_filename
                            self._save_metadata()
                        logger.info(f"[{file_id}] PDF文件已保存到: {pdf_path}")
                
                logger.debug(f"[{file_id}] 文件处理完成，Markdown 内容长度: {len(markdown_content)} 字符")

                logger.debug(f"[{file_id}] 开始将文本分割成 chunks")
                chunks = self._split_text_into_chunks(markdown_content, file_id, filename, params)
                logger.info(f"Split {filename} into {len(chunks)} chunks")
                logger.debug(f"[{file_id}] 文本分割完成，共生成 {len(chunks)} 个 chunks")

                if chunks:
                    texts = [chunk["content"] for chunk in chunks]
                    logger.info(f"开始对 {len(texts)} 个文本块进行向量编码")
                    logger.debug(f"[{file_id}] 准备调用 embedding 函数，文本块数量: {len(texts)}")
                    embeddings = await embedding_function(texts)
                    logger.info(f"向量编码完成，准备插入 Milvus")
                    logger.debug(f"[{file_id}] Embedding 生成完成，向量数量: {len(embeddings) if isinstance(embeddings, list) else 'N/A'}")

                    entities = [
                        [chunk["id"] for chunk in chunks],
                        [chunk["content"] for chunk in chunks],
                        [chunk["source"] for chunk in chunks],
                        [chunk["chunk_id"] for chunk in chunks],
                        [chunk["file_id"] for chunk in chunks],
                        [chunk["chunk_index"] for chunk in chunks],
                        embeddings,
                    ]

                    logger.info(f"开始将 {len(chunks)} 个向量块插入 Milvus collection")
                    logger.debug(f"[{file_id}] 准备构建实体数据，chunks 数量: {len(chunks)}")
                    logger.debug(f"[{file_id}] 实体数据构建完成，准备执行插入操作")
                    def _insert():
                        logger.info("执行 collection.insert() 操作...")
                        logger.debug(f"[{file_id}] 正在执行 Milvus collection.insert() 操作...")
                        result = collection.insert(entities)
                        logger.info(f"Insert 操作完成，返回结果: {result}")
                        logger.debug(f"[{file_id}] Milvus insert 操作完成，返回结果: {result}")
                        return result

                    insert_result = await asyncio.to_thread(_insert)
                    logger.info(f"成功插入 {len(chunks)} 个向量块到 Milvus（Milvus 将自动持久化数据）")
                    logger.debug(f"[{file_id}] 向量块插入 Milvus 完成")

                logger.info(f"Inserted {content_type} {item} into Milvus. Done.")
                logger.debug(f"[{file_id}] 文件处理流程完成，开始更新状态为 done")

                async with self._metadata_lock:
                    self.files_meta[file_id]["status"] = "done"
                    self._save_metadata()
                file_record["status"] = "done"
                logger.debug(f"[{file_id}] 文件状态已更新为 done，准备从处理队列移除")
                # 从处理队列中移除
                self._remove_from_processing_queue(file_id)
                logger.debug(f"[{file_id}] 文件已从处理队列移除，处理完成")

            except Exception as e:
                logger.error(f"处理{content_type} {item} 失败: {e}, {traceback.format_exc()}")
                logger.debug(f"[{file_id}] 文件处理失败，错误信息: {str(e)}")
                async with self._metadata_lock:
                    self.files_meta[file_id]["status"] = "failed"
                    self._save_metadata()
                file_record["status"] = "failed"
                logger.debug(f"[{file_id}] 文件状态已更新为 failed，准备从处理队列移除")
                # 从处理队列中移除
                self._remove_from_processing_queue(file_id)
                logger.debug(f"[{file_id}] 文件已从处理队列移除（失败状态）")
            finally:
                pass

            processed_items_info.append(file_record)

        return processed_items_info

    async def aquery(self, query_text: str, db_id: str, **kwargs) -> list[dict]:
        """异步查询知识库"""
        collection = await self._get_milvus_collection(db_id)
        if not collection:
            raise ValueError(f"Database {db_id} not found")

        try:
            top_k = kwargs.get("top_k", 30)
            similarity_threshold = kwargs.get("similarity_threshold", 0.2)
            
            # 从集合的索引信息中获取实际的度量类型
            # 这样可以确保查询时使用的度量类型与索引创建时一致
            try:
                # 尝试获取 embedding 字段的索引
                embedding_index = collection.index("embedding")
                if embedding_index:
                    # 获取索引参数
                    index_params = embedding_index.params
                    # index_params 可能是字符串格式的 JSON，也可能是字典
                    if isinstance(index_params, dict):
                        metric_type = index_params.get("metric_type", "COSINE")
                    elif isinstance(index_params, str):
                        try:
                            params_dict = json.loads(index_params)
                            metric_type = params_dict.get("metric_type", "COSINE")
                        except:
                            metric_type = "COSINE"
                    else:
                        # 如果无法解析，使用默认值
                        metric_type = "COSINE"
                else:
                    metric_type = "COSINE"
            except Exception as e:
                logger.warning(f"Failed to get metric_type from collection index: {e}, using COSINE")
                # 如果无法获取索引信息，使用默认的 COSINE（因为创建索引时使用的是 COSINE）
                metric_type = "COSINE"
            
            # 验证用户传入的 metric_type 是否与索引匹配
            user_metric_type = kwargs.get("metric_type")
            if user_metric_type and user_metric_type != metric_type:
                logger.warning(
                    f"User requested metric_type '{user_metric_type}' but collection uses '{metric_type}'. "
                    f"Using collection's metric_type '{metric_type}' to avoid errors."
                )

            embed_info = self.databases_meta[db_id].get("embed_info", {})
            embedding_function = self._get_embedding_function(embed_info)
            query_embedding = embedding_function([query_text])

            search_params = {"metric_type": metric_type, "params": {"nprobe": 10}}
            results = collection.search(
                data=query_embedding,
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["content", "source", "chunk_id", "file_id", "chunk_index"],
            )

            if not results or len(results) == 0 or len(results[0]) == 0:
                return []

            retrieved_chunks = []
            # 用于检查文件是否有可视化数据
            files_with_viz = set()
            
            for hit in results[0]:
                similarity = hit.distance if metric_type == "COSINE" else 1 / (1 + hit.distance)

                if similarity < similarity_threshold:
                    continue

                entity = hit.entity
                file_id = entity.get("file_id")
                metadata = {
                    "source": entity.get("source", "未知来源"),
                    "chunk_id": entity.get("chunk_id"),
                    "file_id": file_id,
                    "chunk_index": entity.get("chunk_index"),
                    "database_id": db_id,  # 添加数据库ID供前端使用
                }

                # 检查是否有可视化数据（不加载图片，只检查标记）
                # 这样避免将大量 Base64 图片数据发送给 LLM
                if file_id and file_id not in files_with_viz:
                    viz_exists = self._check_visualization_exists(file_id)
                    if viz_exists:
                        files_with_viz.add(file_id)
                        metadata["has_visualization"] = True
                        # 前端会根据 file_id 单独请求可视化数据
                
                retrieved_chunks.append(
                    {"content": entity.get("content", ""), "metadata": metadata, "score": similarity}
                )

            logger.debug(f"Milvus query response: {len(retrieved_chunks)} chunks found (after similarity filtering)")
            return retrieved_chunks

        except Exception as e:
            logger.error(f"Milvus query error: {e}, {traceback.format_exc()}")
            return []

    async def delete_file(self, db_id: str, file_id: str) -> None:
        """删除文件"""
        collection = await self._get_milvus_collection(db_id)

        if collection:
            # 先查询文件是否存在，避免不必要的删除操作
            try:
                expr = f'file_id == "{file_id}"'
                results = collection.query(expr=expr, output_fields=["id"], limit=1)

                if not results:
                    logger.info(f"File {file_id} not found in Milvus, skipping delete operation")
                else:
                    # 只有在文件确实存在时才执行删除
                    def _delete_from_milvus():
                        try:
                            collection.delete(expr)
                            logger.info(f"Deleted chunks for file {file_id} from Milvus")
                        except Exception as e:
                            logger.error(f"Error deleting file {file_id} from Milvus: {e}")

                    await asyncio.to_thread(_delete_from_milvus)
            except Exception as e:
                logger.error(f"Error checking file existence in Milvus: {e}")
        # 使用锁确保元数据操作的原子性
        async with self._metadata_lock:
            if file_id in self.files_meta:
                del self.files_meta[file_id]
                self._save_metadata()

    async def get_file_basic_info(self, db_id: str, file_id: str) -> dict:
        """获取文件基本信息（仅元数据）"""
        if file_id not in self.files_meta:
            raise Exception(f"File not found: {file_id}")

        return {"meta": self.files_meta[file_id]}

    async def get_file_content(self, db_id: str, file_id: str) -> dict:
        """获取文件内容信息（chunks和lines）"""
        if file_id not in self.files_meta:
            raise Exception(f"File not found: {file_id}")

        # 使用 Milvus 获取chunks
        content_info = {"lines": []}
        collection = await self._get_milvus_collection(db_id)
        if collection:
            try:
                # 查询文档的所有chunks
                expr = f'file_id == "{file_id}"'
                results = collection.query(
                    expr=expr,
                    output_fields=["content", "chunk_id", "chunk_index"],
                    limit=10000,  # 假设单个文件不会超过10000个chunks
                )

                # 构建chunks数据
                doc_chunks = []
                for result in results:
                    chunk_data = {
                        "id": result.get("chunk_id", ""),
                        "content": result.get("content", ""),
                        "chunk_order_index": result.get("chunk_index", 0),
                    }
                    doc_chunks.append(chunk_data)

                # 按 chunk_order_index 排序
                doc_chunks.sort(key=lambda x: x.get("chunk_order_index", 0))
                content_info["lines"] = doc_chunks
                return content_info

            except Exception as e:
                logger.error(f"Failed to get file content from Milvus: {e}")
                content_info["lines"] = []
                return content_info

        return content_info

    async def get_file_info(self, db_id: str, file_id: str) -> dict:
        """获取文件完整信息（基本信息+内容信息）- 保持向后兼容"""
        if file_id not in self.files_meta:
            raise Exception(f"File not found: {file_id}")

        # 合并基本信息和内容信息
        basic_info = await self.get_file_basic_info(db_id, file_id)
        content_info = await self.get_file_content(db_id, file_id)

        return {**basic_info, **content_info}

    async def update_file_name(self, db_id: str, file_id: str, new_filename: str) -> dict:
        """更新文件名"""
        if file_id not in self.files_meta:
            raise Exception(f"File not found: {file_id}")

        # 验证文件属于该数据库
        if self.files_meta[file_id].get("database_id") != db_id:
            raise Exception(f"File {file_id} does not belong to database {db_id}")

        # 使用锁确保元数据操作的原子性
        async with self._metadata_lock:
            self.files_meta[file_id]["filename"] = new_filename
            self._save_metadata()

        return await self.get_file_basic_info(db_id, file_id)

    async def update_chunk_content(self, db_id: str, file_id: str, chunk_id: str, new_content: str) -> dict:
        """更新chunk内容"""
        if file_id not in self.files_meta:
            raise Exception(f"File not found: {file_id}")

        # 验证文件属于该数据库
        if self.files_meta[file_id].get("database_id") != db_id:
            raise Exception(f"File {file_id} does not belong to database {db_id}")

        collection = await self._get_milvus_collection(db_id)
        if not collection:
            raise Exception(f"Database {db_id} not found")

        try:
            # 查询chunk是否存在
            expr = f'chunk_id == "{chunk_id}" AND file_id == "{file_id}"'
            results = collection.query(expr=expr, output_fields=["id", "content", "chunk_id", "file_id", "chunk_index", "source"], limit=1)

            if not results:
                raise Exception(f"Chunk {chunk_id} not found")

            # 获取要删除的chunk的ID
            old_chunk = results[0]
            chunk_primary_id = old_chunk["id"]

            # 获取embedding函数
            embed_info = self.databases_meta[db_id].get("embed_info", {})
            embedding_function = self._get_async_embedding_function(embed_info)

            # 重新生成embedding
            new_embedding = await embedding_function([new_content])
            
            if not new_embedding:
                raise Exception("Failed to generate embedding for new content: embedding is None or empty")
            
            if not isinstance(new_embedding, list):
                raise Exception(f"Failed to generate embedding: expected list, got {type(new_embedding)}")
            
            if len(new_embedding) == 0:
                raise Exception("Failed to generate embedding: embedding list is empty")
            
            # embedding_function返回的是列表的列表，需要取第一个元素
            embedding_vector = new_embedding[0]
            if not isinstance(embedding_vector, list):
                raise Exception(f"Failed to extract embedding vector: expected list, got {type(embedding_vector)}")

            # 更新向量数据库
            def _update_milvus():
                try:
                    # 先删除旧数据
                    delete_expr = f'id == "{chunk_primary_id}"'
                    collection.delete(delete_expr)
                    
                    # 插入新数据，使用相同的ID
                    entities = [
                        [chunk_primary_id],
                        [new_content],
                        [old_chunk.get("source", file_id)],
                        [chunk_id],
                        [file_id],
                        [old_chunk.get("chunk_index", 0)],
                        [embedding_vector],
                    ]
                    collection.insert(entities)
                except Exception as e:
                    logger.error(f"Error updating chunk in Milvus: {e}, {traceback.format_exc()}")
                    raise

            await asyncio.to_thread(_update_milvus)
            
            logger.info(f"Successfully updated chunk {chunk_id} content")

            return {
                "chunk_id": chunk_id,
                "content": new_content,
                "file_id": file_id,
            }

        except Exception as e:
            logger.error(f"Failed to update chunk content: {e}, {traceback.format_exc()}")
            raise

    def delete_database(self, db_id: str) -> dict:
        """删除数据库，同时清除Milvus中的集合"""
        # Drop Milvus collection
        try:
            if utility.has_collection(db_id, using=self.connection_alias):
                utility.drop_collection(db_id, using=self.connection_alias)
                logger.info(f"Dropped Milvus collection for {db_id}")
            else:
                logger.info(f"Milvus collection {db_id} does not exist, skipping")
        except Exception as e:
            logger.error(f"Failed to drop Milvus collection {db_id}: {e}")

        # Call base method to delete local files and metadata
        return super().delete_database(db_id)

    def __del__(self):
        """清理连接"""
        try:
            if hasattr(self, "connection_alias"):
                connections.disconnect(self.connection_alias)
        except Exception:  # noqa: S110
            pass
