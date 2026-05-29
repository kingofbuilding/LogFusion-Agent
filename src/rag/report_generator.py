"""
报告生成模块（最小可运行版）：
基于检索结果与风险分数输出中文文本报告。
"""

from datetime import datetime


class ReportGenerator:
    """简易报告生成器。"""

    def generate(self, risk_score: float, retrieved_cases: list, extra: dict = None) -> str:
        level = "低"
        if risk_score >= 0.8:
            level = "高"
        elif risk_score >= 0.5:
            level = "中"

        lines = []
        lines.append("安全日志研判报告")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"风险分数: {risk_score:.4f}")
        lines.append(f"风险等级: {level}")
        lines.append("")
        lines.append("相似历史案例:")
        if not retrieved_cases:
            lines.append("- 无")
        else:
            for i, case in enumerate(retrieved_cases, 1):
                lines.append(f"- 案例{i}: score={case['score']:.4f}, 内容={case['payload']}")

        lines.append("")
        lines.append("处置建议:")
        if level == "高":
            lines.append("- 立即隔离相关主机并审计账号行为。")
            lines.append("- 启动应急响应流程并保留证据。")
        elif level == "中":
            lines.append("- 持续观察可疑源地址与账号。")
            lines.append("- 提升相关系统日志采样粒度。")
        else:
            lines.append("- 暂无高风险行为，建议常规巡检。")

        if extra:
            lines.append("")
            lines.append("补充信息:")
            for k, v in extra.items():
                lines.append(f"- {k}: {v}")

        return "\n".join(lines)
