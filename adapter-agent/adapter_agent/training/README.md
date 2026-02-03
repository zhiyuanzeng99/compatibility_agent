# V0 训练快速开始（4×4090）

这是兼容性 Agent 的最小训练路径：先做 SFT，再做工具调用训练。基于 4×4090，
使用 QLoRA + DeepSpeed ZeRO-3。

## 0) 安装训练依赖

```bash
cd /path/to/adapter-agent
pip install -e ".[training]"
```

## 1) 准备数据

数据格式说明：`adapter_agent/training/data_formats.md`

最小数据种子：
- `adapter_agent/training/data/seed_sft.jsonl`
- `adapter_agent/training/data/seed_tool.jsonl`

生成更多工具调用数据：

```bash
python -m adapter_agent.training.generate_tool_data \
  --output ./data/tool_data.jsonl \
  --repeat 50
```

## 2) SFT 训练

```bash
export CUDA_VISIBLE_DEVICES=0,1,2,3

deepspeed --num_gpus=4 -m adapter_agent.training.train_sft \
  --model_name_or_path Qwen/Qwen2.5-32B-Instruct \
  --train_data ./adapter_agent/training/data/seed_sft.jsonl \
  --output_dir ./output/sft_v0 \
  --use_qlora --bf16 \
  --max_seq_length 4096 \
  --gradient_accumulation_steps 8 \
  --deepspeed ./configs/deepspeed_zero3.json
```

## 3) 工具调用训练（同脚本）

```bash
export CUDA_VISIBLE_DEVICES=0,1,2,3

deepspeed --num_gpus=4 -m adapter_agent.training.train_sft \
  --model_name_or_path ./output/sft_v0 \
  --train_data ./adapter_agent/training/data/seed_tool.jsonl \
  --output_dir ./output/tool_v0 \
  --use_qlora --bf16 \
  --max_seq_length 4096 \
  --gradient_accumulation_steps 8 \
  --deepspeed ./configs/deepspeed_zero3.json
```

说明：
- `train_sft.py` 同时支持 `conversations` 和 `messages` 的 JSONL。
- 工具调用数据会优先使用模型的 chat template 转成文本，
  若模型没有 template，则使用简化格式。

