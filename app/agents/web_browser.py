"""
Web Browser Tool - Uses Jina Reader API to crawl and extract markdown from URLs.
Zero-configuration, AI-friendly web reader.
"""
import httpx
from typing import Optional

class WebBrowserTool:
    """
    Tool for reading web pages and converting them to Markdown using Jina Reader.
    """
    
    JINA_PREFIX = "https://r.jina.ai/"
    
    @classmethod
    async def read_url(cls, url: str) -> str:
        """
        Read the content of a URL and return it as Markdown.
        
        Args:
            url: The URL to visit
            
        Returns:
            Markdown content of the page
        """
        if not url:
            return "❌ URL không hợp lệ."
            
        target_url = f"{cls.JINA_PREFIX}{url}"
        
        try:
            async with httpx.AsyncClient() as client:
                # Add headers to look like a real browser or polite bot
                headers = {"User-Agent": "MenuGreenBot/1.0"}
                response = await client.get(target_url, headers=headers, timeout=20)
                
                if response.status_code != 200:
                    return f"❌ Lỗi khi đọc trang (Status: {response.status_code}): {response.text[:100]}"
                
                content = response.text
                
                # Basic cleanup if needed (Jina usually returns clean MD)
                if not content.strip():
                    return "⚠️ Trang web không có nội dung hoặc không thể đọc được."
                    
                return content
                
        except Exception as e:
            return f"❌ Lỗi kết nối: {str(e)}"

# Standalone function for easy import
async def browse_url(url: str) -> str:
    return await WebBrowserTool.read_url(url)
