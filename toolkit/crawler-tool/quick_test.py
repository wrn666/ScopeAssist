"""
简化启动脚本 - 用于快速测试和调试
"""
import asyncio
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from main import OSRedmCrawler
    
    async def quick_test():
        """快速测试模式 - 只爬取首页和少量页面"""
        print("🔧 快速测试模式启动")
        print("📝 此模式只爬取少量页面用于测试")
        
        crawler = OSRedmCrawler(
            base_url="https://www.osredm.com/",
            output_dir=r"D:\HuaweiMoveData\Users\21438\Desktop\红山网络怕爬虫"
        )
        
        # 测试模式参数
        await crawler.start_crawling(
            max_pages=5,    # 只爬取5个页面
            batch_size=1    # 一次只处理1个页面
        )
        
    if __name__ == "__main__":
        asyncio.run(quick_test())
        
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("💡 请先运行 install_requirements.bat 安装依赖")
    input("按回车键退出...")
except Exception as e:
    print(f"❌ 运行错误: {e}")
    input("按回车键退出...")