"""
SFT Trainer - 监督微调训练器

针对 4x RTX 4090 (96GB VRAM) 优化

硬件配置:
- 4x RTX 4090, 每张 24GB VRAM
- 推荐使用 Qwen2.5-32B-Instruct 作为基础模型
- 使用 DeepSpeed ZeRO-3 + QLoRA 进行训练
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class ModelSize(Enum):
    """模型规模"""
    SMALL_7B = "7b"
    MEDIUM_14B = "14b"
    LARGE_32B = "32b"
    XLARGE_72B = "72b"


@dataclass
class HardwareConfig:
    """4x RTX 4090 硬件配置"""
    num_gpus: int = 4
    gpu_memory_gb: int = 24
    total_memory_gb: int = 96
    gpu_model: str = "RTX 4090"
    cuda_visible_devices: str = "0,1,2,3"
    mixed_precision: str = "bf16"


@dataclass
class LoRAConfig:
    """LoRA 配置"""
    r: int = 64
    lora_alpha: int = 128
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ])
    lora_dropout: float = 0.05
    bias: str = "none"


@dataclass
class QLoRAConfig(LoRAConfig):
    """QLoRA 配置"""
    load_in_4bit: bool = True
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_use_double_quant: bool = True


@dataclass
class DeepSpeedZeRO3Config:
    """DeepSpeed ZeRO-3 配置 (4x4090优化)"""

    def to_dict(self) -> Dict:
        return {
            "bf16": {"enabled": True},
            "zero_optimization": {
                "stage": 3,
                "offload_optimizer": {"device": "cpu", "pin_memory": True},
                "offload_param": {"device": "none"},
                "overlap_comm": True,
                "contiguous_gradients": True,
                "reduce_bucket_size": "auto",
                "stage3_prefetch_bucket_size": "auto",
                "stage3_param_persistence_threshold": "auto",
                "stage3_gather_16bit_weights_on_model_save": True
            },
            "gradient_accumulation_steps": 8,
            "gradient_clipping": 1.0,
            "train_micro_batch_size_per_gpu": 1
        }


@dataclass
class SFTConfig:
    """SFT 训练配置 - 4x4090 优化"""
    # 模型
    base_model: str = "Qwen/Qwen2.5-32B-Instruct"
    model_size: ModelSize = ModelSize.LARGE_32B

    # 硬件
    hardware: HardwareConfig = field(default_factory=HardwareConfig)

    # LoRA
    use_lora: bool = True
    use_qlora: bool = True
    lora_config: LoRAConfig = field(default_factory=QLoRAConfig)

    # DeepSpeed
    use_deepspeed: bool = True
    deepspeed_config: DeepSpeedZeRO3Config = field(default_factory=DeepSpeedZeRO3Config)

    # 训练参数 (4x4090)
    num_epochs: int = 3
    per_device_train_batch_size: int = 1
    per_device_eval_batch_size: int = 1
    gradient_accumulation_steps: int = 8  # 有效批量 = 1*4*8 = 32
    learning_rate: float = 2e-5
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    max_seq_length: int = 4096
    max_grad_norm: float = 1.0

    # 数据
    train_data_path: str = ""
    eval_data_path: str = ""

    # 保存
    output_dir: str = "./output/sft"
    save_steps: int = 500
    save_total_limit: int = 3
    logging_steps: int = 10
    eval_steps: int = 500


class SFTTrainer:
    """SFT 训练器"""

    def __init__(self, config: Optional[SFTConfig] = None):
        self.config = config or SFTConfig()
        self._model = None
        self._tokenizer = None

    def prepare_model(self):
        """准备模型"""
        print(f"准备模型: {self.config.base_model}")
        print(f"QLoRA: {self.config.use_qlora}")
        print(f"DeepSpeed ZeRO-3: {self.config.use_deepspeed}")

    def train(self):
        """开始训练"""
        hw = self.config.hardware
        effective_batch = (
            self.config.per_device_train_batch_size *
            hw.num_gpus *
            self.config.gradient_accumulation_steps
        )
        print("=" * 60)
        print("开始 SFT 训练")
        print(f"硬件: {hw.num_gpus}x {hw.gpu_model} ({hw.total_memory_gb}GB)")
        print(f"模型: {self.config.base_model}")
        print(f"有效批量: {effective_batch}")
        print(f"最大序列长度: {self.config.max_seq_length}")
        print("=" * 60)

    def get_launch_command(self) -> str:
        """获取启动命令"""
        return f"""
# 4x RTX 4090 SFT 训练

export CUDA_VISIBLE_DEVICES=0,1,2,3

deepspeed --num_gpus=4 train_sft.py \\
    --model_name_or_path {self.config.base_model} \\
    --output_dir {self.config.output_dir} \\
    --num_train_epochs {self.config.num_epochs} \\
    --per_device_train_batch_size {self.config.per_device_train_batch_size} \\
    --gradient_accumulation_steps {self.config.gradient_accumulation_steps} \\
    --learning_rate {self.config.learning_rate} \\
    --max_seq_length {self.config.max_seq_length} \\
    --lora_r 64 --lora_alpha 128 \\
    --bf16 True \\
    --deepspeed ds_config_zero3.json
"""


def get_recommended_config_for_4x4090(model_size: ModelSize) -> SFTConfig:
    """获取 4x4090 推荐配置"""
    config = SFTConfig()

    if model_size == ModelSize.SMALL_7B:
        config.base_model = "Qwen/Qwen2.5-7B-Instruct"
        config.use_qlora = False
        config.per_device_train_batch_size = 4
        config.gradient_accumulation_steps = 4
        config.max_seq_length = 8192

    elif model_size == ModelSize.MEDIUM_14B:
        config.base_model = "Qwen/Qwen2.5-14B-Instruct"
        config.per_device_train_batch_size = 2
        config.gradient_accumulation_steps = 8
        config.max_seq_length = 4096

    elif model_size == ModelSize.LARGE_32B:
        # 推荐配置
        config.base_model = "Qwen/Qwen2.5-32B-Instruct"
        config.use_qlora = True
        config.per_device_train_batch_size = 1
        config.gradient_accumulation_steps = 8
        config.max_seq_length = 4096

    elif model_size == ModelSize.XLARGE_72B:
        config.base_model = "Qwen/Qwen2.5-72B-Instruct"
        config.use_qlora = True
        config.per_device_train_batch_size = 1
        config.gradient_accumulation_steps = 16
        config.max_seq_length = 2048

    return config
