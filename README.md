# cli-demo

Python CLI Demo，支持：
- Chat CLI
- 渐进式 grep 记忆
- Skills：`weather` / `file_search` / `file_read` / `summarize` / `email`
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

## 4. 测试

```bash
pytest
```
