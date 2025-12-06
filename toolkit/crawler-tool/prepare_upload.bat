@echo off
echo 创建上传用的压缩包...

:: 创建临时目录
mkdir crawler-tool-upload 2>nul

:: 复制主要文件
copy *.py crawler-tool-upload\
copy *.bat crawler-tool-upload\
copy *.md crawler-tool-upload\
copy *.json crawler-tool-upload\
copy README.md crawler-tool-upload\ 2>nul

:: 复制assets目录
xcopy /E /Y assets crawler-tool-upload\assets\ 2>nul

echo 文件已准备在 crawler-tool-upload 文件夹中
echo 您可以将此文件夹压缩后手动上传到Gitee
pause