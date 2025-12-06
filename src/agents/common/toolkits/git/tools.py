"""Git工具 - 提供git clone等功能"""

import asyncio
import os
import re
import subprocess
import traceback
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src import config, knowledge_base
from src.agents.common.agent_context import get_user_id, set_user_id
from src.utils import logger


class GitCloneModel(BaseModel):
    """Git clone的参数模型"""

    repository_url: str = Field(
        description="Git仓库的URL，支持HTTPS、SSH或Git协议。例如: https://github.com/user/repo.git",
        example="https://github.com/user/repo.git",
    )
    target_dir: str | None = Field(
        default=None,
        description="目标目录名称（可选）。如果不提供，将使用仓库名作为目录名",
        example="my-project",
    )


def _validate_git_url(url: str) -> tuple[bool, str]:
    """
    验证Git URL是否安全

    Returns:
        (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL不能为空"

    # 检查URL格式
    parsed = urlparse(url)
    if not parsed.scheme:
        return False, "URL格式不正确，必须包含协议（如 https:// 或 git@）"

    # 允许的协议
    allowed_schemes = ["https", "http", "git", "ssh"]
    if parsed.scheme not in allowed_schemes and not url.startswith("git@"):
        return False, f"不支持的协议: {parsed.scheme}，支持的协议: {', '.join(allowed_schemes)}"

    # 检查是否有危险的字符或路径遍历
    dangerous_patterns = [
        r"\.\./",  # 路径遍历
        r"\.\.\\",  # Windows路径遍历
        r"%2e%2e",  # URL编码的..
        r"%2E%2E",  # URL编码的..
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False, f"URL包含不安全的字符: {pattern}"

    return True, ""


def _sanitize_dir_name(dir_name: str) -> str:
    """清理目录名，移除不安全的字符"""
    # 移除路径分隔符和其他危险字符
    dir_name = re.sub(r'[<>:"|?*\x00-\x1f]', "", dir_name)
    # 移除前导和尾随的点号和空格
    dir_name = dir_name.strip(". ")
    # 如果为空，使用默认名称
    if not dir_name:
        dir_name = "repository"
    return dir_name


def _extract_repo_name(url: str) -> str:
    """从URL中提取仓库名称"""
    parsed = urlparse(url)
    if parsed.path:
        # 移除.git后缀和路径分隔符
        repo_name = parsed.path.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        return repo_name if repo_name else "repository"
    elif url.startswith("git@"):
        # SSH格式: git@github.com:user/repo.git
        parts = url.split(":")
        if len(parts) > 1:
            repo_name = parts[-1].rstrip("/")
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            return repo_name if repo_name else "repository"
    return "repository"


def _auto_build_knowledge_graph(repo_name: str, user_id: str | None) -> None:
    """
    自动为克隆的仓库构建知识图谱
    
    Args:
        repo_name: 仓库名称
        user_id: 用户ID
    """
    try:
        # 设置用户上下文
        if user_id:
            set_user_id(str(user_id))
        
        # 获取默认CodeHub知识库ID
        default_db_id = knowledge_base.get_default_codehub_database_id()
        
        if not default_db_id:
            logger.warning("没有找到默认CodeHub知识库，跳过自动构建知识图谱")
            return
        
        logger.info(f"找到默认CodeHub知识库 ({default_db_id})，开始自动构建知识图谱")
        
        # 为默认CodeHub知识库构建知识图谱
        async def build_for_default_database():
            try:
                logger.info(f"为默认CodeHub知识库构建仓库 {repo_name} 的知识图谱")
                result = await knowledge_base.add_content(default_db_id, [repo_name])
                logger.info(f"成功构建知识图谱: {result}")
            except Exception as e:
                logger.error(f"构建知识图谱失败: {e}")
        
        # 运行异步任务
        try:
            # 尝试获取当前事件循环
            try:
                loop = asyncio.get_running_loop()
                # 如果事件循环正在运行，创建后台任务（不等待）
                loop.create_task(build_for_default_database())
                logger.info("已在后台启动知识图谱构建任务")
            except RuntimeError:
                # 如果没有运行中的事件循环，创建新的并运行
                asyncio.run(build_for_default_database())
        except Exception as e:
            logger.error(f"启动知识图谱构建任务失败: {e}")
        
    except Exception as e:
        logger.error(f"自动构建知识图谱时发生错误: {e}\n{traceback.format_exc()}")


@tool(args_schema=GitCloneModel)
def git_clone(
    repository_url: Annotated[str, "Git仓库的URL，支持HTTPS、SSH或Git协议"],
    target_dir: Annotated[str | None, "目标目录名称（可选）"] = None,
) -> str:
    """克隆Git仓库到codehub目录

    这个工具可以将Git仓库克隆到本地的codehub目录下。
    支持常见的Git协议（HTTPS、SSH等）。

    参数:
    - repository_url: Git仓库的URL
    - target_dir: 可选的目录名称，如果不提供则使用仓库名

    返回:
    - 成功时返回克隆的目录路径
    - 失败时返回错误信息
    """
    try:
        # 验证URL
        is_valid, error_msg = _validate_git_url(repository_url)
        if not is_valid:
            logger.error(f"Invalid git URL: {error_msg}")
            return f"❌ URL验证失败: {error_msg}"

        # 获取用户ID，实现用户隔离
        user_id = get_user_id()
        if user_id:
            # 每个用户有独立的目录
            codehub_dir = Path(config.save_dir) / "codehub" / f"user_{user_id}"
        else:
            # 如果没有用户ID，使用默认目录（向后兼容）
            codehub_dir = Path(config.save_dir) / "codehub"
        codehub_dir.mkdir(parents=True, exist_ok=True)

        # 确定目标目录名
        if target_dir:
            target_dir_name = _sanitize_dir_name(target_dir)
        else:
            target_dir_name = _sanitize_dir_name(_extract_repo_name(repository_url))

        target_path = codehub_dir / target_dir_name

        # 检查目录是否已存在
        if target_path.exists():
            logger.warning(f"目标目录已存在: {target_path}")
            return f"⚠️ 目标目录已存在: {target_path}\n如果目录是空的或想重新克隆，请先删除该目录或指定不同的目录名。"

        logger.info(f"Cloning repository {repository_url} to {target_path}")

        # 执行git clone
        try:
            # 设置自定义User-Agent，避免被Gitee等平台的反爬虫机制拦截
            # 使用浏览器风格的User-Agent，提高兼容性
            env = os.environ.copy()
            env["GIT_HTTP_USER_AGENT"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            result = subprocess.run(
                ["git", "clone", repository_url, str(target_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                check=True,
                env=env,
            )

            logger.info(f"Successfully cloned {repository_url} to {target_path}")
            
            # 自动构建知识图谱
            try:
                _auto_build_knowledge_graph(target_dir_name, user_id)
            except Exception as e:
                logger.warning(f"自动构建知识图谱失败: {e}")
                # 不影响克隆成功的返回
            
            return f"✅ 成功克隆仓库到: {target_path}\n仓库URL: {repository_url}"

        except subprocess.TimeoutExpired:
            error_msg = f"❌ Git clone超时（超过5分钟）。可能是仓库太大或网络连接慢。"
            logger.error(error_msg)
            # 清理可能部分创建的目录
            if target_path.exists():
                import shutil

                shutil.rmtree(target_path, ignore_errors=True)
            return error_msg

        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Git clone失败: {e.stderr or e.stdout or str(e)}"
            logger.error(f"Git clone error: {error_msg}")
            # 清理可能部分创建的目录
            if target_path.exists():
                import shutil

                shutil.rmtree(target_path, ignore_errors=True)
            return error_msg

        except FileNotFoundError:
            error_msg = "❌ 未找到git命令。请确保系统已安装Git。"
            logger.error(error_msg)
            return error_msg

    except Exception as e:
        error_msg = f"❌ 克隆仓库时发生错误: {str(e)}"
        logger.error(f"Git clone error: {error_msg}\n{traceback.format_exc()}")
        return error_msg


def get_git_tools() -> list[Any]:
    """获取Git工具列表"""
    return [git_clone]

