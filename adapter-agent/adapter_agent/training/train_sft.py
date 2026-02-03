"""
SFT training script (V0).

Supports JSONL in either:
  - {"conversations":[{"role":"user","content":"..."}, ...]}
  - {"messages":[{"role":"user","content":"..."}, ...]}
  - {"prompt":"...","response":"..."}

Usage example:
  python -m adapter_agent.training.train_sft \
    --model_name_or_path Qwen/Qwen2.5-32B-Instruct \
    --train_data ./adapter_agent/training/data/seed_sft.jsonl \
    --output_dir ./output/sft_v0 \
    --use_qlora --bf16 \
    --deepspeed ./configs/deepspeed_zero3.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _require(pkg: str):
    try:
        return __import__(pkg)
    except Exception as exc:  # pragma: no cover - user environment
        raise SystemExit(
            f"Missing dependency: {pkg}. Install training extras:\n"
            f"  pip install -e '.[training]'\n"
        ) from exc


def _extract_messages(example: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    if "messages" in example:
        return example["messages"]
    if "conversations" in example:
        return example["conversations"]
    if "prompt" in example and "response" in example:
        return [
            {"role": "user", "content": example["prompt"]},
            {"role": "assistant", "content": example["response"]},
        ]
    return None


def _render_messages(messages: List[Dict[str, Any]], tokenizer) -> str:
    # Prefer model chat template when available.
    if getattr(tokenizer, "chat_template", None):
        try:
            return tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )
        except Exception:
            pass

    # Fallback to a simple text format.
    rendered = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "assistant" and "tool_calls" in msg:
            rendered.append(
                "Assistant tool_calls: " + json.dumps(msg["tool_calls"], ensure_ascii=True)
            )
            continue
        if role == "tool":
            rendered.append("Tool: " + str(msg.get("content", "")))
            continue
        rendered.append(f"{role.capitalize()}: {msg.get('content', '')}")
    return "\n".join(rendered)


def _load_dataset(train_path: str, eval_path: Optional[str]):
    datasets = _require("datasets")
    data_files = {"train": train_path}
    if eval_path:
        data_files["validation"] = eval_path
    return datasets.load_dataset("json", data_files=data_files)


def main() -> None:
    parser = argparse.ArgumentParser(description="SFT training (V0).")
    parser.add_argument("--model_name_or_path", required=True)
    parser.add_argument("--train_data", required=True)
    parser.add_argument("--eval_data")
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--max_seq_length", type=int, default=4096)
    parser.add_argument("--per_device_train_batch_size", type=int, default=1)
    parser.add_argument("--per_device_eval_batch_size", type=int, default=1)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=8)
    parser.add_argument("--learning_rate", type=float, default=2e-5)
    parser.add_argument("--num_train_epochs", type=int, default=3)
    parser.add_argument("--lora_r", type=int, default=64)
    parser.add_argument("--lora_alpha", type=int, default=128)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument("--target_modules", default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj")
    parser.add_argument("--use_qlora", action="store_true")
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--deepspeed", default=None)
    parser.add_argument("--logging_steps", type=int, default=10)
    parser.add_argument("--save_steps", type=int, default=500)
    parser.add_argument("--save_total_limit", type=int, default=3)
    parser.add_argument("--eval_steps", type=int, default=500)
    parser.add_argument("--packing", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--trust_remote_code", action="store_true")
    parser.add_argument("--gradient_checkpointing", action="store_true")
    args = parser.parse_args()

    transformers = _require("transformers")
    trl = _require("trl")
    peft = _require("peft")
    torch = _require("torch")

    transformers.set_seed(args.seed)

    tokenizer = transformers.AutoTokenizer.from_pretrained(
        args.model_name_or_path, use_fast=True, trust_remote_code=args.trust_remote_code
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant_config = None
    if args.use_qlora:
        bnb = _require("bitsandbytes")
        quant_config = transformers.BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16 if args.bf16 else torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )

    model = transformers.AutoModelForCausalLM.from_pretrained(
        args.model_name_or_path,
        device_map="auto",
        torch_dtype=torch.bfloat16 if args.bf16 else torch.float16,
        quantization_config=quant_config,
        trust_remote_code=args.trust_remote_code,
    )

    if args.use_qlora:
        model = peft.prepare_model_for_kbit_training(model)

    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()

    lora_config = peft.LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=[m.strip() for m in args.target_modules.split(",") if m.strip()],
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = peft.get_peft_model(model, lora_config)

    dataset = _load_dataset(args.train_data, args.eval_data)

    def _format_example(example: Dict[str, Any]) -> Dict[str, str]:
        messages = _extract_messages(example) or []
        text = _render_messages(messages, tokenizer)
        return {"text": text}

    dataset = dataset.map(_format_example, remove_columns=dataset["train"].column_names)

    training_args = transformers.TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        bf16=args.bf16,
        fp16=not args.bf16,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        evaluation_strategy="steps" if args.eval_data else "no",
        eval_steps=args.eval_steps if args.eval_data else None,
        deepspeed=args.deepspeed,
        report_to=[],
        optim="paged_adamw_8bit" if args.use_qlora else "adamw_torch",
    )

    trainer = trl.SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset.get("validation"),
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        packing=args.packing,
        args=training_args,
    )

    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    main()

