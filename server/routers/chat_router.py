import asyncio
import json
import traceback
import uuid
import yaml
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.storage.db.models import User, MessageFeedback, Message, Conversation
from src.storage.conversation import ConversationManager
from server.routers.auth_router import get_admin_user
from server.utils.auth_middleware import get_db, get_required_user
from src import executor
from src import config as conf
from src.agents import agent_manager
from src.agents.common.tools import gen_tool_info, get_buildin_tools
from src.models import select_model
from src.processors.guard import content_guard
from src.utils.logging_config import logger

chat = APIRouter(prefix="/chat", tags=["chat"])


# =============================================================================
# > === 多模态处理辅助函数 ===
# =============================================================================


def is_multimodal_model(model_name: str) -> bool:
    """
    判断模型是否支持多模态（通过模型名称）
    
    Args:
        model_name: 模型名称，格式为 "provider/model_name" 或 "model_name"
    
    Returns:
        bool: 如果模型支持多模态返回True，否则返回False
    """
    if not model_name:
        return False
    
    # 常见的多模态模型名称模式
    multimodal_patterns = [
        # OpenAI
        "gpt-4o",
        "gpt-4-vision",
        # DashScope (阿里云)
        "qwen-vl",
        "qwen2-vl",
        # 智谱AI
        "glm-4v",
        "glm-4-all",
        # DeepSeek
        "deepseek-vl",
        # SiliconFlow常见视觉模型
        "qwen-vl",
        "internvl",
        # 其他常见模式
        "-vl-",
        "-vision",
        "-multimodal",
    ]
    
    model_lower = model_name.lower()
    for pattern in multimodal_patterns:
        if pattern.lower() in model_lower:
            return True
    
    return False


async def process_images_with_vlm(images: list[dict], vlm_provider: str = "dashscope", vlm_model: str = "qwen-vl-max-2025-04-02") -> str:
    """
    使用VLM模型处理图片，生成文本描述
    
    Args:
        images: 图片列表，每个元素包含 {"base64": "...", "name": "...", "mimeType": "..."}
        vlm_provider: VLM模型提供商，默认 "dashscope"
        vlm_model: VLM模型名称，默认 "qwen-vl-max-2025-04-02"
    
    Returns:
        str: 所有图片的描述文本，格式为 "图片1描述\n\n图片2描述..."
    """
    if not images:
        return ""
    
    try:
        # 加载VLM模型
        vlm = select_model(vlm_provider, vlm_model)
        logger.info(f"使用VLM模型 {vlm_provider}/{vlm_model} 处理 {len(images)} 张图片")
    except Exception as e:
        logger.error(f"加载VLM模型失败 ({vlm_provider}/{vlm_model}): {e}")
        logger.debug(traceback.format_exc())
        return f"\n\n[注意：图片处理失败，无法加载VLM模型]"
    
    descriptions = []
    for idx, img in enumerate(images, 1):
        base64_data = img.get("base64", "")
        if not base64_data:
            logger.warning(f"图片 {idx} 缺少base64数据，跳过")
            continue
        
        # 确保base64数据是完整的data URI格式
        if not base64_data.startswith("data:"):
            mime_type = img.get("mimeType", "image/png")
            base64_data = f"data:{mime_type};base64,{base64_data}"
        
        try:
            # 构建多模态消息
            prompt = """请详细描述这张图片的内容。包括：
1. 图片中的主要对象、场景或内容
2. 文字内容（如果有）
3. 图表、表格的结构和数据（如果有）
4. 其他重要细节

请用清晰、准确的中文描述，尽量详细。"""
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": base64_data}}
                    ]
                }
            ]
            
            # 调用VLM进行分析
            logger.debug(f"正在处理第 {idx} 张图片...")
            response = vlm.call(messages, stream=False)
            description = response.content.strip()
            
            if description:
                img_name = img.get("name", f"图片{idx}")
                descriptions.append(f"**{img_name}的描述：**\n{description}")
                logger.debug(f"图片 {idx} 处理完成，描述长度: {len(description)} 字符")
            else:
                logger.warning(f"图片 {idx} 处理结果为空")
                
        except Exception as e:
            logger.error(f"处理图片 {idx} 时出错: {e}")
            logger.debug(traceback.format_exc())
            img_name = img.get("name", f"图片{idx}")
            descriptions.append(f"**{img_name}：** [图片处理失败: {str(e)}]")
    
    if descriptions:
        return "\n\n".join(descriptions)
    else:
        return "\n\n[注意：所有图片处理失败]"


# =============================================================================
# > === 智能体管理分组 ===
# =============================================================================


@chat.get("/default_agent")
async def get_default_agent(current_user: User = Depends(get_required_user)):
    """获取默认智能体ID（需要登录）"""
    try:
        default_agent_id = conf.default_agent_id
        # 如果没有设置默认智能体，尝试获取第一个可用的智能体
        if not default_agent_id:
            agents = await agent_manager.get_agents_info()
            if agents:
                default_agent_id = agents[0].get("id", "")

        return {"default_agent_id": default_agent_id}
    except Exception as e:
        logger.error(f"获取默认智能体出错: {e}")
        raise HTTPException(status_code=500, detail=f"获取默认智能体出错: {str(e)}")


@chat.post("/set_default_agent")
async def set_default_agent(request_data: dict = Body(...), current_user=Depends(get_admin_user)):
    """设置默认智能体ID (仅管理员)"""
    try:
        agent_id = request_data.get("agent_id")
        if not agent_id:
            raise HTTPException(status_code=422, detail="缺少必需的 agent_id 字段")

        # 验证智能体是否存在
        agents = await agent_manager.get_agents_info()
        agent_ids = [agent.get("id", "") for agent in agents]

        if agent_id not in agent_ids:
            raise HTTPException(status_code=404, detail=f"智能体 {agent_id} 不存在")

        # 设置默认智能体ID
        conf.default_agent_id = agent_id
        # 保存配置
        conf.save()

        return {"success": True, "default_agent_id": agent_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"设置默认智能体出错: {e}")
        raise HTTPException(status_code=500, detail=f"设置默认智能体出错: {str(e)}")


# =============================================================================
# > === 对话分组 ===
# =============================================================================


@chat.post("/call")
async def call(query: str = Body(...), meta: dict = Body(None), current_user: User = Depends(get_required_user)):
    """调用模型进行简单问答（需要登录）"""
    meta = meta or {}
    model = select_model(model_provider=meta.get("model_provider"), model_name=meta.get("model_name"))

    async def call_async(query):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, model.call, query)

    response = await call_async(query)
    logger.debug({"query": query, "response": response.content})

    return {"response": response.content}


@chat.get("/agent")
async def get_agent(current_user: User = Depends(get_required_user)):
    """获取所有可用智能体（需要登录）"""
    agents = await agent_manager.get_agents_info()
    # logger.debug(f"agents: {agents}")
    metadata = {}
    if Path("src/config/static/agents_meta.yaml").exists():
        with open("src/config/static/agents_meta.yaml") as f:
            metadata = yaml.safe_load(f)
    return {"agents": agents, "metadata": metadata}


@chat.post("/agent/{agent_id}")
async def chat_agent(
    agent_id: str,
    query: str = Body(...),
    config: dict = Body({}),
    meta: dict = Body({}),
    content: dict = Body(None),  # 多模态内容
    hasImages: bool = Body(False),  # 是否包含图片
    files: list = Body(None),  # 文件列表（用于前端显示）
    current_user: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    """使用特定智能体进行对话（需要登录）"""

    logger.info(f"agent_id: {agent_id}, query: {query}, hasImages: {hasImages}, config: {config}, meta: {meta}")

    meta.update(
        {
            "query": query,
            "agent_id": agent_id,
            "server_model_name": config.get("model", agent_id),
            "thread_id": config.get("thread_id"),
            "user_id": current_user.id,
        }
    )

    # 将meta和thread_id整合到config中
    def make_chunk(content=None, **kwargs):
        return (
            json.dumps(
                {"request_id": meta.get("request_id"), "response": content, **kwargs}, ensure_ascii=False
            ).encode("utf-8")
            + b"\n"
        )

    async def save_messages_from_langgraph_state(
        agent_instance,
        conversation,
        conv_mgr,
        config_dict,
    ):
        """
        从 LangGraph state 中读取完整消息并保存到数据库
        这样可以获得完整的 tool_calls 参数
        """
        try:
            graph = await agent_instance.get_graph()
            state = await graph.aget_state(config_dict)

            if not state or not state.values:
                logger.warning("No state found in LangGraph")
                return

            messages = state.values.get("messages", [])
            logger.debug(f"Retrieved {len(messages)} messages from LangGraph state")

            # 获取已保存的消息数量，避免重复保存
            existing_messages = conv_mgr.get_messages(conversation.id)
            existing_count = len(existing_messages)

            # 只保存新增的消息
            new_messages = messages[existing_count:]

            for msg in new_messages:
                msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else {}
                msg_type = msg_dict.get("type", "unknown")

                if msg_type == "human":
                    # 用户消息（理论上已经保存过了，跳过）
                    continue

                elif msg_type == "ai":
                    # AI 消息
                    content = msg_dict.get("content", "")
                    tool_calls_data = msg_dict.get("tool_calls", [])

                    # 格式清洗
                    if finish_reason := msg_dict.get("response_metadata", {}).get("finish_reason"):
                        if "tool_call" in finish_reason and len(finish_reason) > len("tool_call") :
                            model_name = msg_dict.get("response_metadata", {}).get("model_name", "")
                            repeat_count = len(finish_reason) // len("tool_call")
                            msg_dict["response_metadata"]["finish_reason"] = "tool_call"
                            msg_dict["response_metadata"]["model_name"] = model_name[:len(model_name)//repeat_count]

                    # 保存 AI 消息
                    ai_msg = conv_mgr.add_message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=content,
                        message_type="text",
                        extra_metadata=msg_dict,  # 保存原始 model_dump
                    )

                    # 保存 tool_calls（如果有）- 使用 LangGraph 的 tool_call_id
                    if tool_calls_data:
                        logger.debug(f"Saving {len(tool_calls_data)} tool calls from AI message")
                        for tc in tool_calls_data:
                            conv_mgr.add_tool_call(
                                message_id=ai_msg.id,
                                tool_name=tc.get("name", "unknown"),
                                tool_input=tc.get("args", {}),  # 完整的参数
                                status="pending",  # 工具还未执行
                                langgraph_tool_call_id=tc.get("id"),  # 保存 LangGraph tool_call_id
                            )

                    logger.debug(f"Saved AI message {ai_msg.id} with {len(tool_calls_data)} tool calls")

                elif msg_type == "tool":
                    # 工具执行结果消息 - 使用 tool_call_id 精确匹配
                    tool_call_id = msg_dict.get("tool_call_id")
                    content = msg_dict.get("content", "")
                    name = msg_dict.get("name", "")

                    if tool_call_id:
                        # 确保tool_output是字符串类型，避免SQLite不支持列表类型
                        if isinstance(content, list):
                            tool_output = json.dumps(content) if content else ""
                        else:
                            tool_output = str(content)

                        # 通过 LangGraph tool_call_id 精确匹配并更新
                        updated_tc = conv_mgr.update_tool_call_output(
                            langgraph_tool_call_id=tool_call_id,
                            tool_output=tool_output,
                            status="success",
                        )
                        if updated_tc:
                            logger.debug(f"Updated tool_call {tool_call_id} ({name}) with output")
                        else:
                            logger.warning(f"Tool call {tool_call_id} not found for update")

                logger.debug(f"Processed message type={msg_type}")

            logger.info(f"Saved {len(new_messages)} new messages from LangGraph state")

        except Exception as e:
            logger.error(f"Error saving messages from LangGraph state: {e}")
            logger.error(traceback.format_exc())

    async def stream_messages():
        # 获取agent实例
        try:
            agent = agent_manager.get_agent(agent_id)
        except Exception as e:
            logger.error(f"Error getting agent {agent_id}: {e}, {traceback.format_exc()}")
            yield make_chunk(message=f"Error getting agent {agent_id}: {e}", status="error")
            return

        # 获取agent使用的模型名称
        agent_config = await agent.get_config()
        # Context对象是dataclass，直接访问属性
        model_name = getattr(agent_config, "model", "") if agent_config else ""
        logger.debug(f"Agent使用的模型: {model_name}")

        # 构建前端显示用的原始消息内容（只显示用户的原始提问，不包含文件内容）
        # query字段是用户的原始提问，用于前端显示
        display_message_content = query
        
        # 如果有图片，构建多模态消息内容（用于前端显示）
        if hasImages and content and isinstance(content, dict) and content.get("images"):
            content_parts = []
            # 前端显示只使用原始提问，不包含文件内容
            if query:
                content_parts.append({"type": "text", "text": query})
            
            # 添加图片
            for img in content["images"]:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": img.get("base64")}
                })
            
            display_message_content = content_parts
        
        # 先发送用户消息给前端（只显示原始提问和图片，不显示文件内容）
        human_msg = HumanMessage(content=display_message_content)
        msg_dump = human_msg.model_dump()
        
        # 确保消息类型正确，并添加必要的字段
        msg_dump["type"] = "human"
        msg_dump["role"] = "user"
        
        # 如果没有id，生成一个临时id
        if "id" not in msg_dump:
            import time
            msg_dump["id"] = f"human-{int(time.time() * 1000)}"
        
        # 如果有文件，添加到消息的extra_metadata中，用于前端显示
        if files and isinstance(files, list) and len(files) > 0:
            if "extra_metadata" not in msg_dump:
                msg_dump["extra_metadata"] = {}
            msg_dump["extra_metadata"]["files"] = files
            logger.debug(f"添加文件信息到消息: {len(files)} 个文件")
        
        yield make_chunk(status="init", meta=meta, msg=msg_dump)

        # Input guard (只检查文本部分)
        if conf.enable_content_guard and query and content_guard.check(query):
            yield make_chunk(status="error", message="输入内容包含敏感词", meta=meta)
            return

        # 构建实际发送给LLM的消息内容
        # 如果content存在，使用content中的完整文本（包含文件内容）
        # 如果content是字符串，直接使用；如果是字典，使用content.text
        if content:
            if isinstance(content, dict):
                # content是字典，使用content.text（包含文件内容）
                backend_text = content.get("text", query) or query
            elif isinstance(content, str):
                # content是字符串，直接使用（包含文件内容）
                backend_text = content
            else:
                backend_text = query
        else:
            backend_text = query
        
        message_content = backend_text
        images_processed_with_vlm = False
        
        if hasImages and content and isinstance(content, dict) and content.get("images"):
            # 检查模型是否支持多模态
            supports_multimodal = is_multimodal_model(model_name)
            logger.info(f"模型 {model_name} 是否支持多模态: {supports_multimodal}")
            
            if supports_multimodal:
                # 模型支持多模态，构建多模态消息
                content_parts = []
                if backend_text:
                    content_parts.append({"type": "text", "text": backend_text})
                
                # 添加图片
                for img in content["images"]:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": img.get("base64")}
                    })
                
                message_content = content_parts
            else:
                # 模型不支持多模态，使用VLM处理图片
                logger.info(f"模型 {model_name} 不支持多模态，使用VLM处理图片")
                # 发送"正在回答"状态，让前端显示响应动画
                yield make_chunk(status="loading", content="", meta=meta)
                
                try:
                    # 使用VLM处理图片
                    image_descriptions = await process_images_with_vlm(content["images"])
                    
                    # 将图片描述添加到文本消息中（仅用于后端传递给LLM）
                    if image_descriptions:
                        message_content = f"{backend_text}\n\n{image_descriptions}"
                    else:
                        message_content = backend_text
                    
                    images_processed_with_vlm = True
                    logger.info(f"VLM处理完成，已将图片描述添加到消息中")
                except Exception as e:
                    logger.error(f"VLM处理图片失败: {e}, {traceback.format_exc()}")
                    # 如果VLM处理失败，至少保留原始文本
                    message_content = backend_text
                    yield make_chunk(status="warning", message=f"图片处理失败: {str(e)}，将仅使用文本内容", meta=meta)

        # 构建LangChain消息格式（使用实际发送给LLM的内容）
        messages = [{"role": "user", "content": message_content}]

        # 构造运行时配置，如果没有thread_id则生成一个
        user_id = str(current_user.id)
        thread_id = config.get("thread_id")

        input_context = {"user_id": user_id, "thread_id": thread_id}

        # Initialize conversation manager
        conv_manager = ConversationManager(db)

        # Get or create conversation
        conversation = None
        if thread_id:
            conversation = conv_manager.get_conversation_by_thread_id(thread_id)
            if not conversation:
                try:
                    # Auto-create conversation for existing thread
                    conversation = conv_manager.create_conversation(
                        user_id=user_id,
                        agent_id=agent_id,
                        title=(query[:50] + "..." if len(query) > 50 else query) if query else "新的对话",
                        thread_id=thread_id,
                    )
                    logger.info(f"Auto-created conversation for thread_id {thread_id}")
                except Exception as e:
                    logger.error(f"Failed to auto-create conversation: {e}")
                    conversation = None

        # Save user message（始终保存原始的多模态内容，用于前端显示）
        if conversation:
            try:
                # 准备额外的metadata
                extra_meta = {"raw_message": human_msg.model_dump()}
                if hasImages and content:
                    extra_meta["has_images"] = True
                    extra_meta["image_count"] = len(content.get("images", []))
                    extra_meta["images_processed_with_vlm"] = images_processed_with_vlm
                    if images_processed_with_vlm:
                        extra_meta["model_used"] = model_name
                        extra_meta["vlm_used"] = True
                        # 保存VLM处理后的内容到metadata中（仅用于记录，不用于前端显示）
                        extra_meta["vlm_processed_content"] = message_content
                
                # 保存文件信息（用于前端显示）
                if files and isinstance(files, list) and len(files) > 0:
                    extra_meta["files"] = files
                    extra_meta["file_count"] = len(files)
                
                # 保存消息内容：content字段保存文本部分，完整的多模态内容保存在extra_metadata中
                # 这样前端可以从extra_metadata中读取完整的多模态内容进行显示
                saved_content = query if query else "[图片]"
                
                conv_manager.add_message(
                    conversation_id=conversation.id,
                    role="user",
                    content=saved_content,
                    message_type="multimodal" if hasImages else "text",
                    extra_metadata=extra_meta,
                )
            except Exception as e:
                logger.error(f"Error saving user message: {e}")

        try:
            # Stream messages (only for display, don't save yet)
            async for msg, metadata in agent.stream_messages(messages, input_context=input_context):
                if isinstance(msg, AIMessageChunk):
                    # Content guard
                    if conf.enable_content_guard and content_guard.check(msg.content):
                        logger.warning("Sensitive content detected in stream")
                        yield make_chunk(message="检测到敏感内容，已中断输出", status="error")
                        return

                    yield make_chunk(content=msg.content, msg=msg.model_dump(), metadata=metadata, status="loading")

                elif isinstance(msg, ToolMessage):
                    yield make_chunk(msg=msg.model_dump(), metadata=metadata, status="loading")
                else:
                    yield make_chunk(msg=msg.model_dump(), metadata=metadata, status="loading")

            yield make_chunk(status="finished", meta=meta)

            # After streaming finished, save all messages from LangGraph state
            if conversation:
                langgraph_config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}
                await save_messages_from_langgraph_state(
                    agent_instance=agent,
                    conversation=conversation,
                    conv_mgr=conv_manager,
                    config_dict=langgraph_config,
                )
        except (asyncio.CancelledError, ConnectionError) as e:
            # 客户端主动中断连接，尝试保存已生成的部分内容
            logger.info(f"Client disconnected for thread {thread_id}: {e}")
            try:
                if conversation:
                    langgraph_config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}
                    await save_messages_from_langgraph_state(
                        agent_instance=agent,
                        conversation=conversation,
                        conv_mgr=conv_manager,
                        config_dict=langgraph_config,
                    )
            except Exception as save_error:
                logger.error(f"Error saving partial messages after disconnect: {save_error}")
            # 通知前端中断（可能发送不到，但用于一致性）
            try:
                yield make_chunk(status="interrupted", message="对话已中断", meta=meta)
            except Exception:
                pass
            return
        except Exception as e:
            logger.error(f"Error streaming messages: {e}, {traceback.format_exc()}")
            yield make_chunk(message=f"Error streaming messages: {e}", status="error")

    return StreamingResponse(stream_messages(), media_type="application/json")


# =============================================================================
# > === 模型管理分组 ===
# =============================================================================


@chat.get("/models")
async def get_chat_models(model_provider: str, current_user: User = Depends(get_admin_user)):
    """获取指定模型提供商的模型列表（需要登录）"""
    model = select_model(model_provider=model_provider)
    return {"models": model.get_models()}


@chat.post("/models/update")
async def update_chat_models(model_provider: str, model_names: list[str], current_user=Depends(get_admin_user)):
    """更新指定模型提供商的模型列表 (仅管理员)"""
    conf.model_names[model_provider]["models"] = model_names
    conf._save_models_to_file()
    return {"models": conf.model_names[model_provider]["models"]}


@chat.post("/extract-file")
async def extract_file_content(
    file: UploadFile = File(...),
    ocr_method: str = Body("disable"),  # 默认不使用OCR
    current_user: User = Depends(get_required_user)
):
    """
    提取上传文件的文本内容用于对话（需要登录）
    
    Args:
        file: 上传的文件
        ocr_method: OCR处理方式
            - "disable": 不使用OCR（默认，适合纯文本PDF）
            - "mineru_ocr": 使用MinerU（高质量，需要GPU）
            - "paddlex_ocr": 使用PaddleX（专业，需要GPU）
            - "unstructured": 使用Unstructured（智能解析，支持复杂表格）
    """
    import os
    import tempfile
    from src.knowledge.indexing import process_file_to_markdown
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    # 获取文件扩展名
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    # 支持的文件类型
    supported_formats = [
        '.pdf', '.txt', '.md', '.doc', '.docx',
        '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif',
        '.html', '.htm', '.csv', '.xls', '.xlsx', '.json'
    ]
    
    if file_ext not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}。支持的格式: {', '.join(supported_formats)}"
        )
    
    # 验证OCR方法
    valid_ocr_methods = ["disable", "mineru_ocr", "paddlex_ocr", "unstructured"]
    if ocr_method not in valid_ocr_methods:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的OCR方法: {ocr_method}。支持的方法: {', '.join(valid_ocr_methods)}"
        )
    
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # 提取文件内容
        try:
            # 将OCR方法传递给处理函数
            # 如果是 unstructured 方法，保存元数据用于可视化
            params = {
                "enable_ocr": ocr_method,
                "save_metadata": (ocr_method == "unstructured")
            }
            extracted_text = await process_file_to_markdown(temp_file_path, params=params)
            
            # 如果是 unstructured 且是 PDF，读取元数据
            metadata = None
            pdf_base64 = None
            if ocr_method == "unstructured" and file_ext == '.pdf':
                metadata_path = temp_file_path + ".unstructured_metadata.json"
                if os.path.exists(metadata_path):
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                    
                    # 读取 PDF 文件并编码为 Base64
                    with open(temp_file_path, "rb") as f:
                        import base64
                        pdf_base64 = base64.b64encode(f.read()).decode('utf-8')
                    
                    # 清理元数据文件
                    os.remove(metadata_path)
            
            return {
                "success": True,
                "filename": file.filename,
                "extracted_text": extracted_text,
                "file_type": file_ext,
                "ocr_method": ocr_method,
                "metadata": metadata,
                "pdf_base64": pdf_base64,
                "has_visualization": metadata is not None,
                "message": "文件内容提取成功"
            }
        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except Exception as e:
        logger.error(f"文件内容提取失败: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"文件内容提取失败: {str(e)}"
        )


@chat.post("/visualize-unstructured")
async def visualize_unstructured(
    file: UploadFile = File(...),
    current_user: User = Depends(get_required_user)
):
    """
    处理文件并返回 Unstructured 可视化元数据（需要登录）
    返回文档元素的坐标信息用于前端绘制标注框
    """
    import os
    import tempfile
    import base64
    from src.processors import ocr
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in ['.pdf']:
        raise HTTPException(
            status_code=400,
            detail=f"可视化功能仅支持 PDF 文件"
        )
    
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # 使用 unstructured 处理并保存元数据
            params = {"save_metadata": True}
            extracted_text = ocr.process_file_unstructured(temp_file_path, params=params)
            
            # 读取保存的元数据
            metadata_path = temp_file_path + ".unstructured_metadata.json"
            if not os.path.exists(metadata_path):
                raise HTTPException(
                    status_code=500,
                    detail="元数据文件未生成"
                )
            
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            # 读取 PDF 文件并编码为 Base64
            with open(temp_file_path, "rb") as f:
                pdf_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            return {
                "success": True,
                "filename": file.filename,
                "pdf_base64": pdf_base64,
                "metadata": metadata,
                "extracted_text": extracted_text,
                "message": "文件处理成功"
            }
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            metadata_path = temp_file_path + ".unstructured_metadata.json"
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
                
    except Exception as e:
        logger.error(f"Unstructured 可视化失败: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Unstructured 可视化失败: {str(e)}"
        )


@chat.post("/visualize-unstructured-by-path")
async def visualize_unstructured_by_path(
    request_body: dict = Body(...),
    current_user: User = Depends(get_required_user)
):
    """
    读取文件的 Unstructured 可视化数据（需要登录）
    用于知识库中已存在的文件
    注意：可视化数据在文件处理时自动生成并保存
    """
    import os
    
    file_path = request_body.get("file_path")
    if not file_path:
        raise HTTPException(status_code=400, detail="缺少 file_path 参数")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
    
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext not in ['.pdf']:
        raise HTTPException(
            status_code=400,
            detail=f"可视化功能仅支持 PDF 文件"
        )
    
    try:
        # 读取已保存的可视化数据
        visualization_path = file_path + ".visualization.json"
        
        if os.path.exists(visualization_path):
            # 优先使用已保存的数据
            with open(visualization_path, "r", encoding="utf-8") as f:
                visualization_data = json.load(f)
            
            logger.info(f"从缓存加载可视化数据: {os.path.basename(file_path)}")
            
            return {
                "success": True,
                "filename": visualization_data.get("filename", os.path.basename(file_path)),
                "total_pages": visualization_data.get("total_pages", 0),
                "annotated_pages": visualization_data.get("annotated_pages", []),
                "created_at": visualization_data.get("created_at"),
                "message": "可视化数据加载成功"
            }
        
        else:
            # 若无缓存则实时生成，以兼容旧版本文件
            logger.info(f"可视化数据不存在，实时生成: {os.path.basename(file_path)}")
            
            from src.processors import ocr
            from src.processors._ocr import OCRPlugin
            
            ocr_plugin = OCRPlugin()
            
            # 先处理文件并保存元数据
            params = {"save_metadata": True}
            extracted_text = ocr_plugin.process_file_unstructured(file_path, params=params)
            
            # 检查是否生成了可视化数据
            if os.path.exists(visualization_path):
                with open(visualization_path, "r", encoding="utf-8") as f:
                    visualization_data = json.load(f)
                
                return {
                    "success": True,
                    "filename": visualization_data.get("filename", os.path.basename(file_path)),
                    "total_pages": visualization_data.get("total_pages", 0),
                    "annotated_pages": visualization_data.get("annotated_pages", []),
                    "created_at": visualization_data.get("created_at"),
                    "message": "可视化数据生成成功"
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail="生成可视化数据失败，请检查服务器日志"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"可视化数据处理失败: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"可视化数据处理失败: {str(e)}"
        )


@chat.get("/tools")
async def get_tools(agent_id: str, current_user: User = Depends(get_required_user)):
    """获取所有可用工具（需要登录）"""
    # 获取Agent实例和配置类
    if not (agent := agent_manager.get_agent(agent_id)):
        raise HTTPException(status_code=404, detail=f"智能体 {agent_id} 不存在")

    if hasattr(agent, "get_tools"):
        tools = agent.get_tools()
    else:
        tools = get_buildin_tools()

    tools_info = gen_tool_info(tools)
    return {"tools": {tool["id"]: tool for tool in tools_info}}


@chat.post("/agent/{agent_id}/config")
async def save_agent_config(agent_id: str, config: dict = Body(...), current_user: User = Depends(get_required_user)):
    """保存智能体配置到YAML文件（需要登录）"""
    try:
        # 获取Agent实例和配置类
        if not (agent := agent_manager.get_agent(agent_id)):
            raise HTTPException(status_code=404, detail=f"智能体 {agent_id} 不存在")

        # 使用配置类的save_to_file方法保存配置
        result = agent.context_schema.save_to_file(config, agent.module_name)

        if result:
            return {"success": True, "message": f"智能体 {agent.name} 配置已保存"}
        else:
            raise HTTPException(status_code=500, detail="保存智能体配置失败")

    except Exception as e:
        logger.error(f"保存智能体配置出错: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"保存智能体配置出错: {str(e)}")


@chat.get("/agent/{agent_id}/history")
async def get_agent_history(
    agent_id: str, thread_id: str, current_user: User = Depends(get_required_user), db: Session = Depends(get_db)
):
    """获取智能体历史消息（需要登录）- NEW STORAGE ONLY"""
    try:
        # 获取Agent实例验证
        if not agent_manager.get_agent(agent_id):
            raise HTTPException(status_code=404, detail=f"智能体 {agent_id} 不存在")

        # Use new storage system ONLY
        conv_manager = ConversationManager(db)
        messages = conv_manager.get_messages_by_thread_id(thread_id)

        # Convert to frontend-compatible format
        history = []
        for msg in messages:
            # Map role to type that frontend expects
            role_type_map = {"user": "human", "assistant": "ai", "tool": "tool", "system": "system"}

            msg_dict = {
                "id": msg.id,  # Include message ID for feedback
                "type": role_type_map.get(msg.role, msg.role),  # human/ai/tool/system
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }

            # Add extra_metadata if present (contains raw_message with images for multimodal messages)
            if msg.extra_metadata:
                msg_dict["extra_metadata"] = msg.extra_metadata

            # Add tool calls if present (for AI messages)
            if msg.tool_calls and len(msg.tool_calls) > 0:
                msg_dict["tool_calls"] = [
                    {
                        "id": str(tc.id),
                        "name": tc.tool_name,
                        "function": {"name": tc.tool_name},  # Frontend compatibility
                        "args": tc.tool_input or {},
                        "tool_call_result": {"content": tc.tool_output} if tc.tool_output else None,
                        "status": tc.status,
                    }
                    for tc in msg.tool_calls
                ]

            history.append(msg_dict)

        logger.info(f"Loaded {len(history)} messages from new storage for thread {thread_id}")
        return {"history": history}

    except Exception as e:
        logger.error(f"获取智能体历史消息出错: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取智能体历史消息出错: {str(e)}")


@chat.get("/agent/{agent_id}/config")
async def get_agent_config(agent_id: str, current_user: User = Depends(get_required_user)):
    """从YAML文件加载智能体配置（需要登录）"""
    try:
        # 检查智能体是否存在
        if not (agent := agent_manager.get_agent(agent_id)):
            raise HTTPException(status_code=404, detail=f"智能体 {agent_id} 不存在")

        config = await agent.get_config()
        logger.debug(f"config: {config}, ContextClass: {agent.context_schema=}")
        return {"success": True, "config": config}

    except Exception as e:
        logger.error(f"加载智能体配置出错: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"加载智能体配置出错: {str(e)}")


# ==================== 线程管理 API ====================


class ThreadCreate(BaseModel):
    title: str | None = None
    agent_id: str
    metadata: dict | None = None


class ThreadResponse(BaseModel):
    id: str
    user_id: str
    agent_id: str
    title: str | None = None
    created_at: str
    updated_at: str


# =============================================================================
# > === 会话管理分组 ===
# =============================================================================


@chat.post("/thread", response_model=ThreadResponse)
async def create_thread(
    thread: ThreadCreate, db: Session = Depends(get_db), current_user: User = Depends(get_required_user)
):
    """创建新对话线程 (使用新存储系统)"""
    thread_id = str(uuid.uuid4())
    logger.debug(f"thread.agent_id: {thread.agent_id}")

    # Create conversation using new storage system
    conv_manager = ConversationManager(db)
    conversation = conv_manager.create_conversation(
        user_id=str(current_user.id),
        agent_id=thread.agent_id,
        title=thread.title or "新的对话",
        thread_id=thread_id,
        metadata=thread.metadata,
    )

    logger.info(f"Created conversation with thread_id: {thread_id}")

    return {
        "id": conversation.thread_id,
        "user_id": conversation.user_id,
        "agent_id": conversation.agent_id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


@chat.get("/threads", response_model=list[ThreadResponse])
async def list_threads(agent_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_required_user)):
    """获取用户的所有对话线程 (使用新存储系统)"""
    assert agent_id, "agent_id 不能为空"

    logger.debug(f"agent_id: {agent_id}")

    # Use new storage system
    conv_manager = ConversationManager(db)
    conversations = conv_manager.list_conversations(
        user_id=str(current_user.id),
        agent_id=agent_id,
        status="active",
    )

    return [
        {
            "id": conv.thread_id,
            "user_id": conv.user_id,
            "agent_id": conv.agent_id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        }
        for conv in conversations
    ]


@chat.delete("/thread/{thread_id}")
async def delete_thread(thread_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_required_user)):
    """删除对话线程 (使用新存储系统)"""
    # Use new storage system
    conv_manager = ConversationManager(db)
    conversation = conv_manager.get_conversation_by_thread_id(thread_id)

    if not conversation or conversation.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="对话线程不存在")

    # Soft delete
    success = conv_manager.delete_conversation(thread_id, soft_delete=True)

    if not success:
        raise HTTPException(status_code=500, detail="删除失败")

    return {"message": "删除成功"}


class ThreadUpdate(BaseModel):
    title: str | None = None


@chat.put("/thread/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str,
    thread_update: ThreadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """更新对话线程信息 (使用新存储系统)"""
    # Use new storage system
    conv_manager = ConversationManager(db)
    conversation = conv_manager.get_conversation_by_thread_id(thread_id)

    if not conversation or conversation.user_id != str(current_user.id) or conversation.status == "deleted":
        raise HTTPException(status_code=404, detail="对话线程不存在")

    # Update conversation
    updated_conv = conv_manager.update_conversation(
        thread_id=thread_id,
        title=thread_update.title,
    )

    if not updated_conv:
        raise HTTPException(status_code=500, detail="更新失败")

    return {
        "id": updated_conv.thread_id,
        "user_id": updated_conv.user_id,
        "agent_id": updated_conv.agent_id,
        "title": updated_conv.title,
        "created_at": updated_conv.created_at.isoformat(),
        "updated_at": updated_conv.updated_at.isoformat(),
    }


# =============================================================================
# > === 消息反馈分组 ===
# =============================================================================


class MessageFeedbackRequest(BaseModel):
    rating: str  # 'like' or 'dislike'
    reason: str | None = None  # Optional reason for dislike


class MessageFeedbackResponse(BaseModel):
    id: int
    message_id: int
    rating: str
    reason: str | None
    created_at: str


@chat.post("/message/{message_id}/feedback", response_model=MessageFeedbackResponse)
async def submit_message_feedback(
    message_id: int,
    feedback_data: MessageFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Submit user feedback for a specific message"""
    try:
        # Validate rating
        if feedback_data.rating not in ["like", "dislike"]:
            raise HTTPException(status_code=422, detail="Rating must be 'like' or 'dislike'")

        # Verify message exists and get conversation to check permissions
        message = db.query(Message).filter_by(id=message_id).first()

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Verify user has access to this message (through conversation)
        conversation = db.query(Conversation).filter_by(id=message.conversation_id).first()
        if not conversation or conversation.user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if feedback already exists (user can only submit once)
        existing_feedback = (
            db.query(MessageFeedback).filter_by(message_id=message_id, user_id=str(current_user.id)).first()
        )

        if existing_feedback:
            raise HTTPException(status_code=409, detail="Feedback already submitted for this message")

        # Create new feedback
        new_feedback = MessageFeedback(
            message_id=message_id,
            user_id=str(current_user.id),
            rating=feedback_data.rating,
            reason=feedback_data.reason,
        )

        db.add(new_feedback)
        db.commit()
        db.refresh(new_feedback)

        logger.info(f"User {current_user.id} submitted {feedback_data.rating} feedback for message {message_id}")

        return MessageFeedbackResponse(
            id=new_feedback.id,
            message_id=new_feedback.message_id,
            rating=new_feedback.rating,
            reason=new_feedback.reason,
            created_at=new_feedback.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting message feedback: {e}, {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


@chat.get("/message/{message_id}/feedback")
async def get_message_feedback(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Get feedback status for a specific message (for current user)"""
    try:
        # Get user's feedback for this message
        feedback = db.query(MessageFeedback).filter_by(message_id=message_id, user_id=str(current_user.id)).first()

        if not feedback:
            return {"has_feedback": False, "feedback": None}

        return {
            "has_feedback": True,
            "feedback": {
                "id": feedback.id,
                "rating": feedback.rating,
                "reason": feedback.reason,
                "created_at": feedback.created_at.isoformat(),
            },
        }

    except Exception as e:
        logger.error(f"Error getting message feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get feedback: {str(e)}")
