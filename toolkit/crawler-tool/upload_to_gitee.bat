@echo off
echo 正在准备上传文件到Gitee...

:: 创建临时目录
mkdir temp_upload 2>nul
cd temp_upload

:: 克隆仓库
echo 克隆Gitee仓库...
git clone https://gitee.com/floating-stop/stack-solve.git

:: 进入仓库目录
cd stack-solve

:: 创建目标目录
mkdir toolkit\crawler-tool 2>nul

:: 复制文件（排除一些大文件和临时文件）
echo 复制文件...
xcopy /E /Y "..\..\" "toolkit\crawler-tool\" /EXCLUDE:exclude_list.txt

:: 添加到Git
echo 添加文件到Git...
git add toolkit/crawler-tool/

:: 提交
set /p commit_msg=请输入提交信息: 
git commit -m "%commit_msg%"

:: 推送
echo 推送到远程仓库...
git push origin master

echo 上传完成！
pause