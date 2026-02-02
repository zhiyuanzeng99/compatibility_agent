"""
DPO Trainer - Direct Preference Optimization

针对 4x RTX 4090 优化的偏好对齐训练
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from .sft_trainer import HardwareConfig, QLoRAConfig, DeepSpeedZeRO3Config


@dataclass
class DPODataItem:
    """DPO 训练数据"""
    prompt: str
    chosen: str
    rejected: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DPOConfig:
    """DPO 配置 - 4x4090"""
    model_path: str = "./output/sft/final"
    ref_model_path: Optional[str] = None

    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    use_lora: bool = True
    lora_config: QLoRAConfig = field(default_factory=QLoRAConfig)
    use_deepspeed: bool = True
    deepspeed_config: DeepSpeedZeRO3Config = field(default_factory=DeepSpeedZeRO3Config)

    # DPO 参数
    beta: float = 0.1
    loss_type: str = "sigmoid"

    # 训练参数
    num_epochs: int = 1
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 8
    learning_rate: float = 5e-7
    max_seq_length: int = 2048
    max_prompt_length: int = 1024

    output_dir: str = "./output/dpo"
    save_steps: int = 200


class PreferenceJudge:
    """偏好评判器"""

    DIMENSIONS = [
        "code_correctness",
        "code_quality",
        "performance",
        "error_handling",
        "security",
        "maintainability",
    ]

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def judge(self, prompt: str, a: str, b: str) -> Dict:
        return {"winner": "a", "reason": ""}

    async def generate_dpo_pairs(
        self,
        prompts: List[str],
        responses: List[List[str]]
    ) -> List[DPODataItem]:
        items = []
        for prompt, resps in zip(prompts, responses):
            if len(resps) >= 2:
                result = await self.judge(prompt, resps[0], resps[1])
                if result["winner"] == "a":
                    items.append(DPODataItem(prompt, resps[0], resps[1]))
                elif result["winner"] == "b":
                    items.append(DPODataItem(prompt, resps[1], resps[0]))
        return items


class DPOTrainer:
    """DPO 训练器"""

    def __init__(self, config: Optional[DPOConfig] = None):
        self.config = config or DPOConfig()

    def train(self):
        print("=" * 60)
        print("开始 DPO 训练")
        print(f"Beta: {self.config.beta}")
        print(f"学习率: {self.config.learning_rate}")
        print("=" * 60)

    def get_launch_command(self) -> str:
        return f"""
# 4x RTX 4090 DPO 训练

export CUDA_VISIBLE_DEVICES=0,1,2,3

accelerate launch --config_file accelerate_zero3.yaml train_dpo.py \\
    --model_path {self.config.model_path} \\
    --output_dir {self.config.output_dir} \\
    --beta {self.config.beta} \\
    --learning_rate {self.config.learning_rate} \\
    --per_device_train_batch_size {self.config.per_device_train_batch_size} \\
    --gradient_accumulation_steps {self.config.gradient_accumulation_steps} \\
    --bf16 True
"""
