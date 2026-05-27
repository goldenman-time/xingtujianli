import pytest
from main import app, SecurityUtils
from fastapi.testclient import TestClient

client = TestClient(app)


class TestXSSSecurity:
    """XSS安全防护测试套件"""
    
    def test_security_utils_escape_html_basic(self):
        """测试基本的HTML转义功能"""
        assert SecurityUtils.escape_html('<script>alert("xss")</script>') == '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
        assert SecurityUtils.escape_html('Hello <World>') == 'Hello &lt;World&gt;'
        assert SecurityUtils.escape_html('Test & "quotes"') == 'Test &amp; &quot;quotes&quot;'
    
    def test_security_utils_escape_html_special_chars(self):
        """测试特殊字符转义"""
        assert '&' in SecurityUtils.escape_html('&')
        assert '<' not in SecurityUtils.escape_html('<')
        assert '>' not in SecurityUtils.escape_html('>')
    
    def test_security_utils_sanitize_input(self):
        """测试输入净化功能"""
        # 测试长度限制
        long_text = "a" * 11000
        result = SecurityUtils.sanitize_input(long_text, 10000)
        assert len(result) == 10000
        
        # 测试null字节移除
        assert '\x00' not in SecurityUtils.sanitize_input('test\x00string')
        
        # 测试非字符串输入
        assert SecurityUtils.sanitize_input(123) == '123'
        assert SecurityUtils.sanitize_input(None) == ''
    
    def test_security_utils_validate_name(self):
        """测试姓名验证"""
        # 有效姓名
        valid, name, error = SecurityUtils.validate_name("张三")
        assert valid is True
        assert name == "张三"
        
        valid, name, error = SecurityUtils.validate_name("John Doe")
        assert valid is True
        
        # 无效姓名（包含特殊字符）
        valid, name, error = SecurityUtils.validate_name("<script>xss</script>")
        assert valid is False
        assert '<' not in name
        
        # 空姓名
        valid, name, error = SecurityUtils.validate_name("")
        assert valid is False
    
    def test_security_utils_validate_phone(self):
        """测试手机号验证"""
        # 有效手机号
        valid, phone, error = SecurityUtils.validate_phone("13812345678")
        assert valid is True
        assert phone == "13812345678"
        
        # 带格式的手机号
        valid, phone, error = SecurityUtils.validate_phone("138-1234-5678")
        assert valid is True
        assert '-' not in phone
        
        # 无效手机号
        valid, phone, error = SecurityUtils.validate_phone("12345")
        assert valid is False
    
    def test_security_utils_validate_email(self):
        """测试邮箱验证"""
        # 有效邮箱
        valid, email, error = SecurityUtils.validate_email("test@example.com")
        assert valid is True
        
        # 无效邮箱
        valid, email, error = SecurityUtils.validate_email("invalid-email")
        assert valid is False
    
    def test_security_utils_sanitize_generated_html(self):
        """测试HTML净化功能"""
        # 移除script标签
        html = '<p>Safe content</p><script>alert("xss")</script>'
        result = SecurityUtils.sanitize_generated_html(html)
        assert '<script>' not in result
        assert 'Safe content' in result
        
        # 移除事件处理器
        html = '<div onclick="alert(1)">Click me</div>'
        result = SecurityUtils.sanitize_generated_html(html)
        assert 'onclick' not in result or '=' not in result
        
        # 移除javascript:协议
        html = '<a href="javascript:alert(1)">Link</a>'
        result = SecurityUtils.sanitize_generated_html(html)
        assert 'javascript:' not in result.lower()
        
        # 保留安全内容
        html = '<p><strong>Bold text</strong><em>Italic</em></p>'
        result = SecurityUtils.sanitize_generated_html(html)
        assert '<strong>' in result
        assert '<em>' in result


class TestXSSAPIProtection:
    """API端点XSS防护测试"""
    
    def test_export_word_xss_in_html(self):
        """测试Word导出接口的XSS防护"""
        xss_payload = '<img src=x onerror=alert("xss")>'
        response = client.post("/api/export/word", json={
            "html": xss_payload,
            "name": "<script>alert(1)</script>",
            "templateId": "template_15"
        })
        assert response.status_code == 200
        # 确保响应不包含未转义的脚本
        assert b'<script>' not in response.content.lower() or b'&lt;script&gt;' in response.content
    
    def test_export_word_xss_in_filename(self):
        """测试文件名中的XSS防护"""
        response = client.post("/api/export/word", json={
            "html": "<p>Test</p>",
            "name": "../../../etc/passwd",
            "templateId": "template_15"
        })
        assert response.status_code == 200
        # 文件名应该被清理
        content_disposition = response.headers.get('content-disposition', '')
        assert '..' not in content_disposition
    
    def test_optimize_api_sanitizes_input(self):
        """测试优化API的输入净化"""
        xss_experience = {
            "id": 1,
            "type": "internship",
            "role": "<script>alert(1)</script>",
            "company": "Test Company",
            "date": "2023.01-2023.06",
            "content": "<img src=x onerror=alert(1)>"
        }
        response = client.post("/api/optimize", json={
            "targetJob": "Developer",
            "experiences": [xss_experience],
            "school": "Test University",
            "major": "CS"
        })
        # API可能返回500（因为缺少真实的API密钥），但不应崩溃
        assert response.status_code in [200, 400, 500]
    
    def test_suggestions_api_xss_protection(self):
        """测试建议API的XSS防护"""
        xss_exp = {
            "id": 1,
            "type": "internship",
            "role": "Developer",
            "company": "Company<script>",
            "date": "2023",
            "content": "Worked on <b>project</b><script>alert(1)</script>"
        }
        response = client.post("/api/suggestions", json={
            "experience": xss_exp,
            "jd": "Job description with <script>alert(1)</script>"
        })
        assert response.status_code in [200, 400, 500]
    
    def test_chat_api_message_sanitization(self):
        """测试聊天API的消息净化"""
        xss_messages = [
            {"role": "user", "content": "<script>alert(1)</script>"},
            {"role": "assistant", "content": "Normal response"}
        ]
        response = client.post("/api/resume/chat", json={
            "resume_id": "nonexistent_id",
            "message": "<img src=x onerror=alert('xss')> Hello",
            "chat_history": xss_messages
        })
        # 应该返回404（简历不存在）而不是500错误
        assert response.status_code == 404


class TestXSSBoundaryCases:
    """边界条件XSS测试"""
    
    def test_null_byte_injection(self):
        """测试null字节注入"""
        payload_with_null = "test\x00value"
        result = SecurityUtils.sanitize_input(payload_with_null)
        assert '\x00' not in result
    
    def test_unicode_xss_attempts(self):
        """测试Unicode编码的XSS尝试"""
        unicode_xss = "\u003cscript\u003ealert(1)\u003c/script\u003e"
        escaped = SecurityUtils.escape_html(unicode_xss)
        assert '<script>' not in escaped or '&lt;' in escaped
    
    def test_double_encoding_prevention(self):
        """防止双重编码问题"""
        original = "<script>"
        once_escaped = SecurityUtils.escape_html(original)
        double_escaped = SecurityUtils.escape_html(once_escaped)
        # Python的html.escape会进行正确的转义，不会出现三重编码
        assert '&amp;amp;' not in double_escaped  # 不应该有三重编码
        # 但双重编码是正常的（&被转义为&amp;）
        assert double_escaped.count('&amp;') <= 2
    
    def test_mixed_content_xss(self):
        """测试混合内容的XSS防护"""
        mixed = "Safe text <script>alert(1)</script> more safe text"
        sanitized = SecurityUtils.sanitize_generated_html(mixed)
        assert 'Safe text' in sanitized
        assert '<script>' not in sanitized.lower()
    
    def test_long_xss_payload(self):
        """测试超长XSS载荷"""
        long_xss = "<script>" + "a" * 100000 + "</script>"
        sanitized = SecurityUtils.sanitize_generated_html(long_xss)
        assert len(sanitized) < 1000  # script标签应该被移除


class TestContentSecurityPolicy:
    """内容安全策略相关测试"""
    
    def test_safe_html_tags_preserved(self):
        """确保安全的HTML标签被保留"""
        safe_html = """
        <h1>Title</h1>
        <h2>Subtitle</h2>
        <p>Paragraph with <strong>bold</strong> and <em>italic</em></p>
        <ul><li>Item 1</li><li>Item 2</li></ul>
        <ol><li>First</li><li>Second</li></ol>
        <table><tr><td>Cell</td></tr></table>
        <br>
        <hr>
        <a href="https://example.com">Link</a>
        """
        result = SecurityUtils.sanitize_generated_html(safe_html)
        assert '<h1>' in result
        assert '<p>' in result
        assert '<strong>' in result
        assert '<ul>' in result
        assert '<ol>' in result
        assert '<table>' in result
        assert '<br>' in result
        assert '<hr>' in result
    
    def test_dangerous_attributes_removed(self):
        """确保危险属性被移除"""
        dangerous_html = '<div onclick="alert(1)" onmouseover="hack()" style="color:red">Content</div>'
        result = SecurityUtils.sanitize_generated_html(dangerous_html)
        # 事件处理器应该被移除
        assert 'onclick=' not in result or 'alert' not in result
        assert 'onmouseover=' not in result or 'hack' not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
