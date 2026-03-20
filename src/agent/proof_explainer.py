"""Proof explanation using LLM to translate Lean proofs to natural language."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..llm_module.client import LLMConfig

logger = logging.getLogger(__name__)


class ProofExplainer:
    """Explain Lean proofs in natural language using LLM.

    This class translates Lean proof code into user-understandable explanations,
    focusing on the mathematical meaning rather than syntax.
    """

    SYSTEM_PROMPT_ZH = """你是一位专业的数学证明助手。你的任务是将Lean 4证明代码解释成普通用户能理解的中文说明。

指南：
1. 解释每个证明步骤的数学含义，而不是语法细节
2. 用清晰的中文解释所使用的数学概念和推理
3. 将Lean的策略（如 rw, simp, exact, apply）与数学推理对应起来
4. 保持解释简洁但完整
5. 强调证明的核心思想和关键步骤

回复格式：
- 首先给出证明的整体思路
- 然后逐步解释每个关键步骤
- 最后总结证明完成的内容
"""

    SYSTEM_PROMPT_EN = """You are a professional mathematical proof assistant. Your task is to explain Lean 4 proof code in plain English that general users can understand.

Guidelines:
1. Explain the mathematical meaning of each proof step, not syntax details
2. Use clear English to explain the mathematical concepts and reasoning
3. Map Lean tactics (rw, simp, exact, apply) to mathematical reasoning
4. Keep explanations concise but complete
5. Highlight the core ideas and key steps of the proof

Response format:
- First give the overall proof strategy
- Then explain each key step
- Finally summarize what the proof establishes
"""

    EXPLANATION_TEMPLATE_ZH = """## 定理
```
{Theorem_name} : {theorem_statement}
```

## Lean 证明代码
```lean
{lean_proof}
```

## 任务
请将上述Lean证明解释成用户易懂的中文说明。

请按以下格式回复：
### 证明思路
[简要说明证明的整体方法和核心思想]

### 步骤解释
[逐个解释关键步骤及其数学含义]

### 结论
[证明完成的内容及其意义]
"""

    EXPLANATION_TEMPLATE_EN = """## Theorem
```
{Theorem_name} : {theorem_statement}
```

## Lean Proof Code
```lean
{lean_proof}
```

## Task
Please explain the above Lean proof in plain English.

Please respond in the following format:
### Proof Strategy
[Briefly describe the overall approach and core ideas]

### Step-by-Step Explanation
[Explain each key step and its mathematical meaning]

### Conclusion
[What the proof establishes and its significance]
"""

    def __init__(
        self,
        llm_client: Any,
        config: Optional[LLMConfig] = None,
    ):
        """Initialize the proof explainer.

        Args:
            llm_client: Client for calling LLM API.
            config: LLM configuration.
        """
        self.llm_client = llm_client
        self.config = config or LLMConfig()

    def explain(
        self,
        theorem_name: str,
        theorem_statement: str,
        lean_proof: str,
        language: str = "en",
    ) -> str:
        """Generate user-friendly explanation of a Lean proof.

        Args:
            theorem_name: Name of the theorem.
            theorem_statement: Statement of the theorem.
            lean_proof: The Lean proof code.
            language: Language code ('zh' for Chinese, 'en' for English).

        Returns:
            User-friendly explanation in the specified language.
        """
        if language == "zh":
            system_prompt = self.SYSTEM_PROMPT_ZH
            template = self.EXPLANATION_TEMPLATE_ZH
        else:
            system_prompt = self.SYSTEM_PROMPT_EN
            template = self.EXPLANATION_TEMPLATE_EN

        prompt = template.format(
            Theorem_name=theorem_name,
            theorem_statement=theorem_statement,
            lean_proof=lean_proof,
        )

        logger.info(f"Generating proof explanation in {language} for: {theorem_name}")

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.config.model,
                temperature=0.3,  # Lower temperature for more consistent explanations
                max_tokens=self.config.max_tokens,
            )
            content = response.content if hasattr(response, "content") else response
            logger.info(f"Explanation generated successfully for: {theorem_name}")
            return content
        except Exception as e:
            logger.error(f"Explanation generation failed: {e}")
            return self._fallback_explanation(theorem_statement, language)

    def _fallback_explanation(self, theorem_statement: str, language: str) -> str:
        """Generate a basic explanation when LLM fails.

        Args:
            theorem_statement: The theorem statement.
            language: Language code.

        Returns:
            Basic explanation string.
        """
        if language == "zh":
            return f"""## 证明解释

### 证明思路
该定理的证明已经通过Lean验证器确认。

### 结论
定理陈述 "{theorem_statement}" 已被证明成立。

---
*注：详细的步骤解释目前无法生成，请参考上面的Lean代码。*
"""
        else:
            return f"""## Proof Explanation

### Proof Strategy
The proof of this theorem has been verified by the Lean verifier.

### Conclusion
The theorem statement "{theorem_statement}" has been proven valid.

---
*Note: A detailed step-by-step explanation could not be generated. Please refer to the Lean code above.*
"""
