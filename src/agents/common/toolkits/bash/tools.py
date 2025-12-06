"""Bash工具 - 提供bash命令执行功能，用于查看和操作代码仓库"""

import asyncio
import os
import re
import traceback
from pathlib import Path
from typing import Annotated, Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src import config
from src.agents.common.agent_context import get_user_id
from src.utils import logger


class BashCommandModel(BaseModel):
    """Bash命令执行的参数模型"""

    command: str = Field(
        description="要执行的bash命令。命令会在指定的工作目录中执行。",
        example="ls -la",
    )
    work_dir: str | None = Field(
        default=None,
        description="工作目录（可选）。如果不指定，默认在codehub目录下执行。支持相对路径（相对于codehub）或绝对路径。",
        example="my-project",
    )
    restart: bool = Field(
        default=False,
        description="是否重启bash会话（清除之前的状态）",
    )


class _BashSession:
    """Bash会话管理类"""

    _started: bool
    _timed_out: bool
    command: str = "/bin/bash"
    _output_delay: float = 0.2  # seconds
    _timeout: float = 120.0  # seconds
    _sentinel: str = ",,,,bash-command-exit-__ERROR_CODE__-banner,,,,"

    def __init__(self):
        self._started = False
        self._timed_out = False
        self._process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        """启动bash会话"""
        if self._started:
            return

        # Windows兼容性处理
        if os.name != "nt":  # Unix-like systems
            self._process = await asyncio.create_subprocess_shell(
                self.command,
                shell=True,
                bufsize=0,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid,
            )
        else:
            self._process = await asyncio.create_subprocess_shell(
                "cmd.exe /v:on",
                shell=True,
                bufsize=0,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        self._started = True

    async def stop(self) -> None:
        """终止bash会话"""
        if not self._started:
            return

        if self._process is None:
            return

        if self._process.returncode is not None:
            return

        try:
            self._process.terminate()
            stdout, stderr = await asyncio.wait_for(self._process.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            self._process.kill()
            try:
                stdout, stderr = await asyncio.wait_for(self._process.communicate(), timeout=2.0)
            except asyncio.TimeoutError:
                return None
        except Exception:
            return None

    async def run(self, command: str, work_dir: str | None = None) -> dict[str, Any]:
        """在bash会话中执行命令"""
        if not self._started or self._process is None:
            raise RuntimeError("Session has not started.")

        if self._process.returncode is not None:
            return {
                "output": "",
                "error": f"bash会话已退出，返回码: {self._process.returncode}。需要使用restart参数重启。",
                "error_code": self._process.returncode,
            }

        if self._timed_out:
            raise RuntimeError(f"超时: bash在{self._timeout}秒内未返回，需要重启")

        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        error_code = 0
        sentinel_before, pivot, sentinel_after = self._sentinel.partition("__ERROR_CODE__")
        assert pivot == "__ERROR_CODE__"

        errcode_retriever = "!errorlevel!" if os.name == "nt" else "$?"
        command_sep = "&" if os.name == "nt" else ";"

        # 构建完整的命令：切换目录并执行命令
        full_command = command
        if work_dir:
            # 切换到工作目录
            if os.name == "nt":
                full_command = f"cd /d {work_dir} && {command}"
            else:
                full_command = f"cd {work_dir} && {command}"

        # 发送命令到进程
        self._process.stdin.write(
            b"(\n"
            + full_command.encode()
            + f"\n){command_sep} echo {self._sentinel.replace('__ERROR_CODE__', errcode_retriever)}\n".encode()
        )
        await self._process.stdin.drain()

        # 读取输出，直到找到sentinel
        # 使用缓冲区方式（类似参考实现）
        output = ""
        error = ""
        
        try:
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)

                    # 检查stdout缓冲区
                    if hasattr(self._process.stdout, '_buffer'):
                        output = self._process.stdout._buffer.decode(errors='ignore')  # type: ignore[attr-defined]
                    
                    if sentinel_before in output:
                        output, pivot, exit_banner = output.rpartition(sentinel_before)
                        assert pivot
                        
                        error_code_str, pivot, _ = exit_banner.partition(sentinel_after)
                        if pivot and error_code_str.isdecimal():
                            error_code = int(error_code_str)
                            break

        except asyncio.TimeoutError:
            self._timed_out = True
            raise RuntimeError(f"超时: bash在{self._timeout}秒内未返回，需要重启")

        # 读取错误输出
        if hasattr(self._process.stderr, '_buffer'):
            error = self._process.stderr._buffer.decode(errors='ignore')  # type: ignore[attr-defined]

        # 清理输出（移除sentinel和尾随换行）
        if output.endswith("\n"):
            output = output[:-1]
        if error.endswith("\n"):
            error = error[:-1]

        # 清除缓冲区以便下次使用
        if hasattr(self._process.stdout, '_buffer'):
            self._process.stdout._buffer.clear()  # type: ignore[attr-defined]
        if hasattr(self._process.stderr, '_buffer'):
            self._process.stderr._buffer.clear()  # type: ignore[attr-defined]

        return {"output": output, "error": error, "error_code": error_code}


# 全局bash会话存储
_bash_sessions: dict[str, _BashSession] = {}


def _validate_command(command: str) -> tuple[bool, str]:
    """验证命令安全性"""
    if not command or not isinstance(command, str):
        return False, "命令不能为空"

    # 检查危险命令
    dangerous_patterns = [
        r"rm\s+-rf\s+/",  # 删除根目录
        r"mkfs\s+",  # 格式化文件系统
        r"dd\s+if=/dev/",  # 直接磁盘操作
        r">\s+/dev/",  # 重定向到设备
    ]

    command_lower = command.lower().strip()
    for pattern in dangerous_patterns:
        if re.search(pattern, command_lower):
            return False, f"检测到危险的命令模式: {pattern}"

    return True, ""


def _resolve_work_dir(work_dir: str | None) -> Path:
    """解析工作目录路径"""
    # 获取用户ID，实现用户隔离
    user_id = get_user_id()
    if user_id:
        # 每个用户有独立的目录
        codehub_dir = Path(config.save_dir) / "codehub" / f"user_{user_id}"
    else:
        # 如果没有用户ID，使用默认目录（向后兼容）
        codehub_dir = Path(config.save_dir) / "codehub"
    codehub_dir.mkdir(parents=True, exist_ok=True)

    if not work_dir:
        return codehub_dir

    # 解析为Path对象
    work_path = Path(work_dir)
    
    # 如果是绝对路径，检查是否在codehub目录下
    if work_path.is_absolute():
        try:
            # 确保路径在codehub目录下
            work_path.resolve().relative_to(codehub_dir.resolve())
            return work_path
        except ValueError:
            # 如果不在codehub下，使用codehub作为基础
            logger.warning(f"工作目录 {work_dir} 不在codehub下，使用codehub目录")
            return codehub_dir
    
    # 处理相对路径
    # 如果路径已经包含codehub前缀，需要特殊处理
    codehub_str = str(codehub_dir)
    work_dir_str = str(work_dir)
    
    # 如果work_dir已经包含完整的codehub路径（包含用户ID），直接使用
    if work_dir_str.startswith(codehub_str):
        return Path(work_dir_str)
    
    # 如果work_dir以codehub/开头，提取后面的部分
    if work_dir_str.startswith("codehub/"):
        relative_path = work_dir_str[len("codehub/"):]
        return codehub_dir / relative_path
    
    # 如果work_dir以saves/codehub/开头，提取后面的部分
    saves_codehub_prefix = f"{config.save_dir}/codehub/"
    if work_dir_str.startswith(saves_codehub_prefix):
        relative_path = work_dir_str[len(saves_codehub_prefix):]
        # 检查是否已经包含用户ID前缀
        if user_id and not relative_path.startswith(f"user_{user_id}/"):
            # 如果没有用户ID前缀，添加它
            relative_path = f"user_{user_id}/{relative_path}"
        return codehub_dir / relative_path
    
    # 其他情况：相对路径，相对于codehub目录
    return codehub_dir / work_dir


async def _bash_execute_wrapper(
    command: Annotated[str, "要执行的bash命令"],
    work_dir: Annotated[str | None, "工作目录（可选）"] = None,
    restart: Annotated[bool, "是否重启bash会话"] = False,
) -> str:
    """执行bash命令的包装函数"""
    try:
        # 验证命令
        is_valid, error_msg = _validate_command(command)
        if not is_valid:
            logger.error(f"Invalid command: {error_msg}")
            return f"命令验证失败: {error_msg}"

        # 解析工作目录
        resolved_work_dir = _resolve_work_dir(work_dir)
        work_dir_str = str(resolved_work_dir)

        # 检查目录是否存在
        if not resolved_work_dir.exists():
            return f"工作目录不存在: {resolved_work_dir}"

        # 使用工作目录作为会话键
        session_key = work_dir_str

        # 处理重启
        if restart or session_key not in _bash_sessions:
            if session_key in _bash_sessions:
                await _bash_sessions[session_key].stop()
            _bash_sessions[session_key] = _BashSession()
            await _bash_sessions[session_key].start()

        session = _bash_sessions[session_key]

        # 执行命令
        try:
            result = await session.run(command, work_dir_str)

            # 格式化输出
            output_parts = []
            if result["output"]:
                output_parts.append(f"输出:\n{result['output']}")
            if result["error"]:
                output_parts.append(f"错误输出:\n{result['error']}")
            if result["error_code"] != 0:
                output_parts.append(f"返回码: {result['error_code']}")

            if not output_parts:
                return "命令执行完成，无输出"

            return "\n".join(output_parts)

        except RuntimeError as e:
            error_msg = f"执行命令时发生错误: {str(e)}"
            logger.error(error_msg)
            return error_msg

    except Exception as e:
        error_msg = f"执行bash命令时发生错误: {str(e)}"
        logger.error(f"Bash execute error: {error_msg}\n{traceback.format_exc()}")
        return error_msg


def get_bash_tools() -> list[Any]:
    """获取Bash工具列表"""
    bash_tool = StructuredTool.from_function(
        coroutine=_bash_execute_wrapper,
        name="bash",
        description="""在bash shell中执行命令，用于查看和操作代码仓库内容。

使用说明:
* 命令内容不需要XML转义
* 工作目录默认为codehub目录，可以指定相对路径（相对于codehub）或绝对路径（必须在codehub下）
* 会话状态在同一个工作目录下是持久的
* 可以使用restart参数重启会话以清除状态
* 建议避免会产生大量输出的命令
* 长时间运行的命令应在后台运行，例如 'sleep 10 &'
* 查看文件特定行范围可以使用: sed -n 10,25p /path/to/file

示例:
- ls -la  # 列出当前目录文件
- cd my-project && ls -la  # 进入项目目录并列出文件
- cat README.md  # 查看README文件
- find . -name "*.py" | head -20  # 查找Python文件
""",
        args_schema=BashCommandModel,
        metadata={"tag": ["system", "shell"]},
    )

    return [bash_tool]

