import os
import base64
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from src.storage.db.models import User
from server.utils.auth_middleware import get_required_user
from src import config, knowledge_base
from src.agents.common.agent_context import get_user_id, set_user_id
from src.utils.logging_config import logger

codehub = APIRouter(prefix="/codehub", tags=["codehub"])


class BuildGraphRequest(BaseModel):
    """构建知识图谱请求模型"""
    db_id: str = Field(..., description="知识库ID", min_length=1)


class SearchRepositoriesRequest(BaseModel):
    """搜索代码仓库请求模型"""
    query: str = Field(..., description="搜索查询", min_length=1)
    db_id: str = Field(..., description="知识库ID", min_length=1)
    top_k: int = Field(10, description="返回结果数量", ge=1, le=100)


def _get_codehub_dir(user_id: Optional[int] = None) -> Path:
    """获取用户的codehub目录"""
    if user_id:
        codehub_dir = Path(config.save_dir) / "codehub" / f"user_{user_id}"
    else:
        codehub_dir = Path(config.save_dir) / "codehub"
    return codehub_dir


@codehub.get("/repositories")
async def list_repositories(current_user: User = Depends(get_required_user)):
    """获取用户的所有代码仓库列表"""
    try:
        user_id = current_user.id
        codehub_dir = _get_codehub_dir(user_id)
        
        if not codehub_dir.exists():
            return {"repositories": []}
        
        repositories = []
        for item in codehub_dir.iterdir():
            if item.is_dir():
                # 检查是否是git仓库
                git_dir = item / ".git"
                is_git_repo = git_dir.exists() and git_dir.is_dir()
                
                # 获取仓库信息
                repo_info = {
                    "name": item.name,
                    "path": str(item.relative_to(codehub_dir)),
                    "full_path": str(item),
                    "is_git_repo": is_git_repo,
                }
                
                # 如果是git仓库，尝试获取更多信息
                if is_git_repo:
                    try:
                        # 读取.git/config获取远程URL
                        git_config = item / ".git" / "config"
                        if git_config.exists():
                            with open(git_config, "r", encoding="utf-8") as f:
                                config_content = f.read()
                                # 简单解析remote URL
                                for line in config_content.split("\n"):
                                    if "url = " in line:
                                        repo_info["remote_url"] = line.split("url = ")[-1].strip()
                                        break
                    except Exception as e:
                        logger.debug(f"读取git配置失败: {e}")
                
                repositories.append(repo_info)
        
        return {"repositories": sorted(repositories, key=lambda x: x["name"])}
    except Exception as e:
        logger.error(f"获取仓库列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取仓库列表失败: {str(e)}")


@codehub.get("/repositories/{repo_name}/tree")
async def get_repository_tree(
    repo_name: str,
    path: str = Query("", description="相对路径，默认为根目录"),
    current_user: User = Depends(get_required_user),
):
    """获取仓库的文件树结构"""
    try:
        user_id = current_user.id
        codehub_dir = _get_codehub_dir(user_id)
        repo_path = codehub_dir / repo_name
        
        if not repo_path.exists() or not repo_path.is_dir():
            raise HTTPException(status_code=404, detail=f"仓库不存在: {repo_name}")
        
        # 构建目标路径
        target_path = repo_path / path if path else repo_path
        
        # 安全检查：确保路径在仓库内
        try:
            target_path.resolve().relative_to(repo_path.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="路径不安全")
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="路径不存在")
        
        # 如果是文件，返回文件信息
        if target_path.is_file():
            return {
                "type": "file",
                "name": target_path.name,
                "path": path,
                "size": target_path.stat().st_size,
            }
        
        # 如果是目录，返回目录树
        tree = []
        for item in sorted(target_path.iterdir()):
            # 跳过.git目录
            if item.name == ".git":
                continue
            
            item_info = {
                "name": item.name,
                "path": str(item.relative_to(repo_path)) if path else item.name,
                "type": "directory" if item.is_dir() else "file",
            }
            
            if item.is_file():
                item_info["size"] = item.stat().st_size
            
            tree.append(item_info)
        
        return {
            "type": "directory",
            "path": path,
            "tree": sorted(tree, key=lambda x: (x["type"] == "file", x["name"])),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件树失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件树失败: {str(e)}")


@codehub.get("/repositories/{repo_name}/file")
async def get_file_content(
    repo_name: str,
    path: str = Query(..., description="文件相对路径"),
    current_user: User = Depends(get_required_user),
):
    """获取文件内容"""
    try:
        user_id = current_user.id
        codehub_dir = _get_codehub_dir(user_id)
        repo_path = codehub_dir / repo_name
        
        if not repo_path.exists() or not repo_path.is_dir():
            raise HTTPException(status_code=404, detail=f"仓库不存在: {repo_name}")
        
        file_path = repo_path / path
        
        # 安全检查：确保文件在仓库内
        try:
            file_path.resolve().relative_to(repo_path.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="路径不安全")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="路径不是文件")
        
        # 检查文件大小（限制为10MB）
        file_size = file_path.stat().st_size
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件太大（超过10MB）")
        
        # 读取文件内容
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            
            # 尝试以文本方式读取
            try:
                text_content = content.decode("utf-8")
                is_binary = False
            except UnicodeDecodeError:
                # 二进制文件，返回base64编码
                text_content = base64.b64encode(content).decode("utf-8")
                is_binary = True
            
            return {
                "path": path,
                "name": file_path.name,
                "content": text_content,
                "is_binary": is_binary,
                "size": file_size,
            }
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件内容失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件内容失败: {str(e)}")


@codehub.get("/repositories/{repo_name}/assets/{path:path}")
async def get_asset_file(
    repo_name: str,
    path: str,
    current_user: User = Depends(get_required_user),
):
    """获取仓库中的资源文件（如图片等）"""
    try:
        user_id = current_user.id
        codehub_dir = _get_codehub_dir(user_id)
        repo_path = codehub_dir / repo_name
        
        if not repo_path.exists() or not repo_path.is_dir():
            raise HTTPException(status_code=404, detail=f"仓库不存在: {repo_name}")
        
        # 处理路径中的 URL 编码和路径规范化
        import urllib.parse
        decoded_path = urllib.parse.unquote(path)
        # 规范化路径，移除多余的斜杠和相对路径组件
        path_parts = [p for p in decoded_path.split('/') if p and p != '.']
        # 处理 .. 组件
        normalized_parts = []
        for part in path_parts:
            if part == '..':
                if normalized_parts:
                    normalized_parts.pop()
            else:
                normalized_parts.append(part)
        
        file_path = repo_path
        for part in normalized_parts:
            file_path = file_path / part
        
        # 安全检查：确保文件在仓库内
        try:
            file_path.resolve().relative_to(repo_path.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="路径不安全")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"文件不存在: {decoded_path}")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="路径不是文件")
        
        # 检查文件大小（限制为50MB）
        file_size = file_path.stat().st_size
        if file_size > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件太大（超过50MB）")
        
        # 读取文件并返回
        with open(file_path, "rb") as f:
            content = f.read()
        
        # 根据文件扩展名确定媒体类型
        import mimetypes
        media_type, _ = mimetypes.guess_type(str(file_path))
        if not media_type:
            media_type = "application/octet-stream"
        
        return Response(content=content, media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取资源文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取资源文件失败: {str(e)}")


@codehub.delete("/repositories/{repo_name}")
async def delete_repository(
    repo_name: str,
    current_user: User = Depends(get_required_user),
):
    """删除代码仓库"""
    try:
        import shutil
        
        user_id = current_user.id
        codehub_dir = _get_codehub_dir(user_id)
        repo_path = codehub_dir / repo_name
        
        if not repo_path.exists() or not repo_path.is_dir():
            raise HTTPException(status_code=404, detail=f"仓库不存在: {repo_name}")
        
        # 安全检查：确保路径在codehub目录内
        try:
            repo_path.resolve().relative_to(codehub_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="路径不安全")
        
        # 删除目录
        shutil.rmtree(repo_path)
        
        return {"message": f"仓库 {repo_name} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除仓库失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除仓库失败: {str(e)}")


# =============================================================================
# === 知识图谱相关API ===
# =============================================================================


@codehub.post("/repositories/{repo_name}/build-graph")
async def build_repository_graph(
    repo_name: str,
    request: BuildGraphRequest,
    current_user: User = Depends(get_required_user),
):
    """为代码仓库构建知识图谱"""
    try:
        user_id = current_user.id
        codehub_dir = _get_codehub_dir(user_id)
        repo_path = codehub_dir / repo_name

        if not repo_path.exists() or not repo_path.is_dir():
            raise HTTPException(status_code=404, detail=f"仓库不存在: {repo_name}")

        # 验证知识库ID
        if not request.db_id or not request.db_id.strip():
            raise HTTPException(status_code=422, detail="知识库ID不能为空")

        db_id = request.db_id.strip()

        # 设置用户上下文
        set_user_id(str(user_id))

        # 添加仓库到知识库
        try:
            result = await knowledge_base.add_content(db_id, [repo_name])
        except ValueError as e:
            # 数据库不存在或其他验证错误
            error_msg = str(e)
            if "not found" in error_msg.lower():
                raise HTTPException(status_code=404, detail=f"知识库不存在: {db_id}")
            raise HTTPException(status_code=400, detail=f"知识库操作失败: {error_msg}")

        # 需要重新加载所有智能体，因为工具刷新了
        from src.agents import agent_manager

        await agent_manager.reload_all()

        return {
            "message": f"成功为仓库 {repo_name} 构建知识图谱",
            "result": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"构建知识图谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"构建知识图谱失败: {str(e)}")


@codehub.post("/repositories/search")
async def search_repositories(
    request: SearchRepositoriesRequest,
    current_user: User = Depends(get_required_user),
):
    """搜索代码仓库结构"""
    try:
        # 设置用户上下文
        set_user_id(str(current_user.id))

        # 查询知识库
        results = await knowledge_base.aquery(request.query, db_id=request.db_id, top_k=request.top_k)

        return {
            "query": request.query,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"搜索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

