# PowerShell脚本上传到Gitee
Write-Host "正在准备上传文件到Gitee..." -ForegroundColor Green

# 设置变量
$repoUrl = "https://gitee.com/floating-stop/stack-solve.git"
$tempDir = "temp_gitee_upload"
$targetPath = "toolkit/crawler-tool"

# 创建临时目录
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# 进入临时目录
Set-Location $tempDir

try {
    # 克隆仓库
    Write-Host "克隆仓库..." -ForegroundColor Yellow
    git clone $repoUrl
    
    # 进入仓库目录
    Set-Location "stack-solve"
    
    # 创建目标目录
    if (!(Test-Path $targetPath)) {
        New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
    }
    
    # 复制文件（排除大文件）
    Write-Host "复制文件..." -ForegroundColor Yellow
    $sourceDir = "..\..\..\"
    $excludePatterns = @("__pycache__", "*.log", "osredm_projects_output", "markdown", "*.zip", "*.pdf", "红山图片pdf")
    
    Get-ChildItem $sourceDir -Recurse | Where-Object {
        $exclude = $false
        foreach ($pattern in $excludePatterns) {
            if ($_.FullName -like "*$pattern*") {
                $exclude = $true
                break
            }
        }
        !$exclude
    } | ForEach-Object {
        $relativePath = $_.FullName.Replace((Resolve-Path $sourceDir).Path, "")
        $destPath = Join-Path $targetPath $relativePath
        
        if ($_.PSIsContainer) {
            if (!(Test-Path $destPath)) {
                New-Item -ItemType Directory -Path $destPath -Force | Out-Null
            }
        } else {
            $destDir = Split-Path $destPath -Parent
            if (!(Test-Path $destDir)) {
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            }
            Copy-Item $_.FullName $destPath -Force
        }
    }
    
    # Git操作
    Write-Host "添加文件到Git..." -ForegroundColor Yellow
    git add $targetPath
    
    $commitMsg = Read-Host "请输入提交信息"
    git commit -m $commitMsg
    
    Write-Host "推送到远程仓库..." -ForegroundColor Yellow
    git push origin master
    
    Write-Host "上传完成！" -ForegroundColor Green
    
} catch {
    Write-Host "错误: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    # 返回原目录并清理
    Set-Location ..\..\
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}

Read-Host "按Enter键退出"