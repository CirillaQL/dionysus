from config.config import get_config
from crawler.simpcity.simpcity import crawler, sync
from cookies.cookies import BrowserCookies

def main():
    config = get_config("config.yaml")
    browser_cookies = config.get("cookies")
    
    # 将浏览器格式的cookies转换为requests格式
    cookies_manager = BrowserCookies()
    cookies_manager.add_cookies_from_dict(browser_cookies)
    requests_cookies = cookies_manager.to_requests_cookies("simpcity.su")
    
    print(f"已加载 {len(requests_cookies)} 个cookies")
    
    
    # 完整爬取并存储到数据库
    # result = crawler(
    #     thread_url="https://simpcity.su/threads/volcanicblossom-pufffypink.20508",
    #     cookies=requests_cookies,
    #     thread_title="pufffypink",
    #     enable_reactions=False,
    #     save_to_db=True
    # )
    
    # print("爬取结果:")
    # print(f"成功: {result['success']}")
    # print(f"总帖子数: {result['total_posts']}")
    # print(f"数据库记录数: {result['db_records']}")
    # if result['error']:
    #     print(f"错误: {result['error']}")

    # 同步帖子
    result = sync(
        thread_url="https://simpcity.su/threads/volcanicblossom-pufffypink.20508",
        cookies=requests_cookies,
        thread_title="pufffypink",
        enable_reactions=False,
        save_to_db=True
    )
    print("同步结果:")
    print(f"成功: {result['success']}")
    print(f"总帖子数: {result['total_posts']}")
    print(f"数据库记录数: {result['db_records']}")
    if result['error']:
        print(f"错误: {result['error']}")

if __name__ == "__main__":
    main()

