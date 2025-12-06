"""
OSRedm 深度爬取模式
增强版全站爬虫，支持多轮深度爬取和持续监控
"""
import asyncio
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from main import OSRedmCrawler
    
    async def deep_crawl_mode():
        """深度爬取模式 - 持续多轮深度爬取"""
        print("🚀 OSRedm 深度爬取模式启动")
        print("=" * 60)
        print("📈 此模式将进行多轮深度爬取，发现更多内容")
        print("⏱️ 预计运行时间：数小时")
        print("💾 所有内容将保存到 markdown 文件夹")
        print("🔄 支持中断后继续（断点续爬）")
        print("=" * 60)
        
        # 确认开始
        response = input("是否开始深度爬取？(y/N): ").lower().strip()
        if response != 'y':
            print("取消爬取")
            return
        
        # 创建爬虫实例
        crawler = OSRedmCrawler(
            base_url="https://www.osredm.com/",
            output_dir=r"D:\HuaweiMoveData\Users\21438\Desktop\红山网络怕爬虫"
        )
        
        # 深度爬取参数
        await crawler.start_crawling(
            max_pages=1000,    # 大幅增加最大页面数
            batch_size=2,      # 保持小批次避免检测
            max_rounds=20      # 多轮次确保深度覆盖
        )
        
    async def continuous_monitor():
        """持续监控模式 - 定期检查新内容"""
        print("🔄 持续监控模式")
        print("此模式将每隔一段时间检查网站是否有新内容")
        
        crawler = OSRedmCrawler(
            base_url="https://www.osredm.com/",
            output_dir=r"D:\HuaweiMoveData\Users\21438\Desktop\红山网络怕爬虫"
        )
        
        round_count = 1
        
        while True:
            try:
                print(f"\n🔍 第 {round_count} 轮监控检查")
                
                # 每轮爬取少量新内容
                await crawler.start_crawling(
                    max_pages=50,      # 每轮少量页面
                    batch_size=1,      # 单个页面避免检测
                    max_rounds=3       # 短轮次
                )
                
                # 等待间隔（1小时）
                print("⏰ 等待 1 小时后进行下一轮检查...")
                await asyncio.sleep(3600)  # 1小时 = 3600秒
                
                round_count += 1
                
            except KeyboardInterrupt:
                print("\n用户中断监控")
                break
            except Exception as e:
                print(f"监控出错: {e}")
                print("等待 10 分钟后重试...")
                await asyncio.sleep(600)  # 10分钟后重试
        
    async def main():
        print("🎯 OSRedm 高级爬取系统")
        print("=" * 40)
        print("请选择运行模式:")
        print("1. 深度爬取模式 (推荐)")
        print("2. 持续监控模式")
        print("3. 退出")
        
        choice = input("\n请输入选择 (1-3): ").strip()
        
        if choice == "1":
            await deep_crawl_mode()
        elif choice == "2":
            await continuous_monitor()
        elif choice == "3":
            print("退出程序")
        else:
            print("无效选择")
        
    if __name__ == "__main__":
        asyncio.run(main())
        
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("💡 请先运行 fix_all_issues.bat 修复环境")
    input("按回车键退出...")
except Exception as e:
    print(f"❌ 运行错误: {e}")
    print("💡 如有问题请检查环境设置")
    input("按回车键退出...")