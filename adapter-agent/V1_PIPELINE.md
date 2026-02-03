# V1 Pipeline（多工具识别与自动部署）

## 目标
在 V0 的基础上扩展为“多工具 + 多框架 + 多部署方式”的通用 pipeline：
1) 扫描项目技术栈与部署方式
2) 评估并推荐安全工具（OpenGuardrails / NeMo / LlamaGuard / GuardrailsAI 等）
3) 生成集成代码与配置
4) 可选：自动部署 + 验证 + 修复

## 使用方法

```bash
cd /Users/zhiyuan/compatibility_agent/adapter-agent

python -m adapter_agent.cli v1 \
  --project-path /path/to/target_project \
  --output-dir /path/to/target_project \
  --deploy
```

### 多工具协同
```bash
python -m adapter_agent.cli v1 \
  --project-path /path/to/target_project \
  --tools openguardrails,llama_firewall \
  --deploy
```

### 参数说明
- `--project-path`：目标项目路径（必须）
- `--output-dir`：生成文件输出目录（默认同项目路径）
- `--tool`：强制指定工具（如 `openguardrails` / `nemo_guardrails` / `llama_guard`）
- `--tools`：多工具协同（逗号分隔），优先于 `--tool`
- `--deploy/--no-deploy`：是否自动部署
- `--dry-run`：仅生成，不写入文件
- `--mode`：部署模式（`direct`/`staged`/`container`/`dry_run`）
- `--validate/--no-validate`：部署后验证（默认开启）
- `--auto-fix/--no-auto-fix`：验证失败时尝试自动修复
- `--lifecycle/--no-lifecycle`：是否写入生命周期检查点（默认开启）

## 输出说明
CLI 输出 JSON 包含：
- `profile`：扫描结果（框架/LLM/部署方式等）
- `recommendations`：工具推荐列表（含评分）
- `selected_tool`：实际选中的工具
- `generated`：生成的文件与依赖
- `deployment`：部署结果（若开启）
- `validation`：验证结果（若开启）
- `fixes`：自动修复结果（若开启）
- `pipeline`：多工具编排结果（若使用 `--tools`）
- `lifecycle`：生命周期状态（包含检查点记录）
