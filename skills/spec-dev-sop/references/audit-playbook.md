# 质量体检手册

阶段 6 使用。脚本查「可机械判定」的，你查「需要判断」的。

## 怎么读报告

```bash
python skills/spec-dev-sop/scripts/sop.py audit --diff          # 只扫本次改动（默认用这个）
python skills/spec-dev-sop/scripts/sop.py audit                  # 全项目基线
python skills/spec-dev-sop/scripts/sop.py audit --only secrets    # 只查某类
python skills/spec-dev-sop/scripts/sop.py audit --json            # 给自动化用
```

严重度：

| 级别 | 含义 | 处理 |
| --- | --- | --- |
| blocker | 泄露、崩溃、语法错误级 | 必须修，修完重跑 |
| warning | 大概率的真问题 | 逐条判断，真问题就修 |
| info | 提示与风格 | 扫一眼，本次不处理就记进质量体检文档的遗留项 |

退出码：有 blocker 返回 1；加 `--strict` 时 warning 也返回 1。

## 四类检查覆盖什么

**敏感信息**：硬编码口令/密钥、私钥块、带密码的连接串、AWS/Google/GitHub/Slack token、`SECRET_KEY`、疑似 JWT/身份证/手机号、硬编码 IP、`.env` 是否被 git 跟踪、是否缺 `.env.example`。

**冗余**：连续被注释掉的代码块、跨文件重复代码块、未使用的 Python/JS import、超长函数（>60 行）、只有 `pass` 的空实现、超长文件（>800 行）。

**结构完整性**：`import` 的第三方包是否在 `requirements.txt` 声明、`package.json` 依赖与 import 是否双向一致、Django app 是否缺 `__init__.py`/`migrations/`/`tests.py`、`DEBUG=True` 与 `ALLOWED_HOSTS=['*']`、孤儿 Python 模块（默认关闭）。

**代码规范**：超长行、行尾空白、缺尾换行、Python Tab/空格混用、BOM。

## 处理误报：改规则，别改代码

发现误报时，**不要为了让报告变干净去改被检查的代码**，也不要删规则。按优先级：

1. **加 `allow_pattern`**：命中该正则的行直接跳过。适合「同一模式在本项目里合法」的情况。
2. **加 `exclude_glob`**：整类文件不查。适合测试夹具、mock 数据、生成代码。
3. **调阈值**：`max_function_lines`、`max_line_length` 这类。
4. **降级 severity**：确实长期存在但可接受的问题，从 warning 降到 info。
5. **关掉开关**：`structure.check_orphans` 这类噪声大的默认关闭。

示例：`test_settings.py` 里的假密钥被误报。

```json
{
  "id": "hardcoded-credential",
  "allow_pattern": "(os\\.environ|test|fixture|dummy|fake)"
}
```

示例：整个 `scripts/` 目录允许 `print`。

```json
{
  "id": "python-print",
  "exclude_glob": ["scripts/**"]
}
```

## 新增一条检查

在 `scripts/audit_rules.json` 对应段落追加一项即可，不用改 `sop.py`：

```json
{
  "id": "my-rule",
  "severity": "warning",
  "langs": ["python"],
  "skip_tests": true,
  "pattern": "你的正则",
  "allow_pattern": "误报压制正则",
  "message": "人话说明怎么修"
}
```

字段说明：

| 字段 | 适用范围 | 说明 |
| --- | --- | --- |
| `id` | 全部 | 短横线小写，报告里显示 |
| `severity` | 全部 | `blocker` / `warning` / `info` |
| `pattern` | 全部 | Python 正则，JSON 里反斜杠要写两个 |
| `allow_pattern` | 全部 | 命中则跳过该行 |
| `exclude_glob` | secrets | 整类文件不查，支持 `**` |
| `langs` | debug | `["python"]` / `["js"]`，按扩展名判定 |
| `skip_tests` | debug | 测试文件不查 |
| `message` | 全部 | 说清「怎么修」，不要只写「有问题」 |

`redundancy` / `structure` / `style` 段是配置项不是规则列表，字段含义见 JSON 内注释与代码里的 `check_*` 函数。

## 迭代节奏（脚本是活文档）

- **每次被误报烦到**，当场改规则并提交，规则集才会越长越准。
- **每季度**跑一次全项目 `audit`，看新增了哪类问题，据此决定加规则还是加规范。
- 规则一定要进版本库（`skills/` 下），别只改本机 `.codebuddy/` 副本。
- 规则文件改完用 `python skills/sync_skills.py` 同步。

## 脚本查不到、必须人工看的

1. **业务语义冗余**：自己写了 `format_date`，而项目里已有 `utils.date.fmt`。同义工具的重造只有人看得出来。
2. **抽象过度**：只被调用一次的 service 层、只为「以后扩展」而加的接口与基类。
3. **结构断裂**：新增了文件但没接进路由/注册表；删了逻辑但常量、文案、文档没跟着删。
4. **分层破坏**：视图里直接写 ORM 聚合、组件里直接拼 URL。
5. **交付一致性**：代码与开发文档不一致却没有回写文档。这种「文档骗人」比代码有 bug 更麻烦。
6. **日志与异常**：日志打印了敏感字段、`except` 里 `pass` 掉、异常堆栈直传前端。

## 结案标准

质量体检文档只允许两种结论：

- **可提交**：无 blocker，warning 已逐条解释，人工复核五项都过。
- **需返工（列明项）**：写清哪几项、谁修、什么时候。

写「基本没问题」「应该可以」视为未完成。
