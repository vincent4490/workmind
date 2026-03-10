# -*- coding: utf-8 -*-
"""
安全中间件 —— Prompt 注入检测 + PII 脱敏 + 审计日志
"""
import re
import logging

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """安全校验异常"""
    pass


class SecurityMiddleware:
    """
    安全中间件，在 LLM 调用前后执行安全检查。

    pre_process:  Prompt 注入检测 + PII 脱敏
    post_process: 输出内容策略过滤（预留）
    """

    INJECTION_PATTERNS = [
        r'忽略.{0,10}(以上|之前|所有).{0,10}(指令|规则|提示)',
        r'(ignore|forget|disregard).{0,20}(instructions|rules|prompt)',
        r'(输出|打印|显示|告诉我).{0,10}(系统提示|system prompt|初始指令)',
        r'repeat.{0,10}(system|initial).{0,10}(prompt|instruction)',
        r'(你是|你的角色|你的身份).{0,5}(什么|谁)',
        r'(act as|pretend|role.?play).{0,20}(admin|root|developer)',
    ]

    PII_PATTERNS = {
        'phone': (r'(?<!\d)1[3-9]\d{9}(?!\d)', '手机号'),
        'id_card': (r'(?<!\d)\d{17}[\dXx](?!\d)', '身份证号'),
        'email': (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '邮箱'),
        'bank_card': (r'(?<!\d)\d{16,19}(?!\d)', '银行卡号'),
    }

    def pre_process(self, context: dict) -> dict:
        """
        输入层安全检查。

        Args:
            context: 包含 requirement_input 等字段的请求上下文

        Returns:
            处理后的 context（PII 已脱敏）

        Raises:
            SecurityError: 检测到 Prompt 注入
        """
        text = context.get('requirement_input', '')
        if not text:
            return context

        # 1. Prompt 注入检测
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"[Security] Prompt 注入已拦截: {text[:200]}")
                self._log_event('prompt_injection_blocked', text[:500])
                raise SecurityError("输入内容包含不安全指令，请修改后重试")

        # 2. 安全等级检查
        security_level = context.get('security_level', 'internal')
        if security_level == 'top_secret':
            self._log_event('security_level_reject', f"绝密项目禁止使用AI: {text[:100]}")
            raise SecurityError("绝密项目禁止使用 AI 智能体，请通过人工流程处理")

        # 3. PII 检测与脱敏
        pii_found = {}
        for pii_type, (pattern, label) in self.PII_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                pii_found[label] = len(matches)
                for match in matches:
                    if len(match) > 4:
                        masked = match[:2] + '*' * (len(match) - 4) + match[-2:]
                    else:
                        masked = '****'
                    text = text.replace(match, masked)

        if pii_found:
            logger.info(f"[Security] PII 已脱敏: {pii_found}")
            self._log_event('pii_detected_and_masked', str(pii_found))
            context['_pii_warning'] = f"检测到敏感信息已自动脱敏: {pii_found}"
            context['_pii_detected'] = True

        context['requirement_input'] = text
        return context

    def post_process(self, output):
        """输出层安全过滤（预留，Phase 1 仅做日志）"""
        return output

    def _log_event(self, event_type: str, detail: str):
        """记录安全审计日志（延迟导入避免循环引用）"""
        try:
            from apps.ai_requirement.models import AiAuditLog
            AiAuditLog.objects.create(
                event_type=event_type,
                detail=detail[:500],
            )
        except Exception as e:
            logger.error(f"[Security] 审计日志写入失败: {e}")
