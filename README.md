# cli-demo

Python CLI Demo，支持：
- Chat CLI
- Chat 流式输出（可在会话内开关）
- 渐进式 grep 记忆
- 基于模型理解的自动记忆抽取（非规则）
- Agent Skills：`weather` / `time` / `file_search` / `file_read` / `summarize` / `email`
- OpenAI v1 compatible SDK
- 默认配置文件 + `.env` 环境变量

## 1. 安装

```bash
python3 -m pip install .
python3 -m pip install -r requirements-dev.txt
```

## 2. 配置 `.env`

复制示例文件并按需填写：

```bash
cp .env.example .env
```

当前会自动加载以下位置的 `.env`：
- `claw_demo/config/.env`
- 项目根目录 `.env`（当前工作目录）

默认不会覆盖系统中已存在的同名环境变量。

可选配置：
- `WORKSPACE_DIR`：`file_search` / `file_read` 的工作目录
  - 未配置时，默认使用“运行目录同级”的 `workspace/`
  - 例如在 `/path/cli-demo` 运行时，默认是 `/path/workspace`
- `SMTP_FROM`：邮件发件人地址（对应 `email.smtp.from`）

记忆抽取说明：
- 自动记忆抽取由 LLM 完成（自由理解后存储）
- 内部流程为 `propose -> verify -> commit`，先产出候选记忆，再审核后写入
- `episode` 默认按关键词触发（如“进展/今天做了/刚完成/决定/总结/会议/计划”）
- `episode` 仅保留最近 N 天（默认 14 天），写入 `episodes/YYYY-MM-DD-episode.md`
- 检索时对 `episode` 使用时间衰减函数（半衰期可配），近期加权更高、陈旧记忆自动衰减
- 需要可用的 `OPENAI_API_KEY`（或你的兼容网关 key）
- 无 key 时不会自动写入长期记忆（手动 `claw mem add` 仍可用）

技能执行说明：
- 技能定义文件位于 `claw_demo/skills/agents/*/SKILL.md`
- 执行流程为 Agent 运行时：模型根据技能说明自由规划，按需调用工具，最后输出结果
- 无 key 时 Agent Skills 不执行（会返回错误并提示配置 `llm.api_key`）
- 支持外部技能导入：在配置中设置 `skills.import_dirs`，目录支持
  - `<dir>/agents/<skill>/SKILL.md`
  - `<dir>/<skill>/SKILL.md`

邮件配置说明（`email.smtp`）：
- `use_ssl=true`：使用 `SMTP_SSL`（如 465）
- `use_tls=true` 且 `use_ssl=false`：使用 `SMTP + STARTTLS`（如 587）
- `timeout`：SMTP 连接超时秒数

## 3. 运行

```bash
python3 -m claw_demo.main skill list
python3 -m claw_demo.main mem search "Python CLI"
python3 -m claw_demo.main workspace show
python3 -m claw_demo.main workspace set ./workspace
python3 -m claw_demo.main chat
```

或安装脚本后：

```bash
claw skill list
claw chat
```

Chat 内命令：
- `/help` 查看命令帮助
- `/command help <命令>` 查看某个命令详细使用
- `/memtype` 查看当前会话记忆类型
- `/memtype auto|profile|fact|episode` 切换记忆类型
- `/trace` 查看最近一次工作流轨迹
- `/trace on|off` 开关自动显示工作流轨迹
- `/stream on|off` 开关流式输出
- `/dryrun on|off` 开关邮件 dry-run

## 4. 测试

```bash
pytest
```
