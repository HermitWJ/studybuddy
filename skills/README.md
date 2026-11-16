# skills —— 团队技能库

本目录存放项目级 CodeBuddy 技能（skills），随仓库提交，所有成员克隆后可直接复用。
每个技能是一个独立目录，内含必需的 `SKILL.md` 与可选的 `scripts/`、`references/`、`assets/`。

## 目录约定

```
skills/
├── README.md             本文件：管理规范
├── sync_skills.py        同步脚本：把技能部署到 .codebuddy/skills/
└── <skill-name>/         单个技能，目录名用 kebab-case
    ├── SKILL.md          YAML frontmatter + 正文（必需）
    ├── scripts/          可直接执行的脚本（可选）
    ├── references/       按需加载的详细文档（可选）
    └── assets/           输出用模板/资源（可选）
```

## 现有技能

| 技能 | 用途 | 详细文档 |
| --- | --- | --- |
| [spec-dev-sop](spec-dev-sop/SKILL.md) | 规范开发 SOP：需求澄清 → 开发方案 → 开发文档 → 编码 → 单测补全 → 质量体检，两道确认关卡，产物落 `docs/dev/<需求名>/`，文档按 `需求名.文档类型.md` 命名；自带 `sop.py`（scaffold / status / audit / test） | [用户使用说明书](spec-dev-sop/user-guide.html)（浏览器打开） · [需求澄清清单](spec-dev-sop/references/discovery-questions.md) · [单测手册](spec-dev-sop/references/testing-playbook.md) · [体检手册](spec-dev-sop/references/audit-playbook.md) |
| [team-git-commit](team-git-commit/SKILL.md) | 引导式执行「开工 → 开发 → 提交」，边做边讲原理；强制 `feat/<用户名>`、rebase 最新 main、禁止推送 main | [用户使用说明书](team-git-commit/user-guide.html)（浏览器打开） · [团队规范](team-git-commit/references/team-branch-policy.md) · [Git 原理速查](team-git-commit/references/git-primer.md) · [初学者体验实录](team-git-commit/references/beginner-walkthrough.md) |

两个技能配合使用：`spec-dev-sop` 管「写什么、写对没、写完体检」，`team-git-commit` 管「怎么提交上去」。体检结论为「可提交」后再进提交流程。

## 为什么有两份目录

CodeBuddy 只从 `.codebuddy/skills/` 加载项目级技能，而该目录被 `.gitignore` 忽略（它是派生产物）。

因此约定：

- **`skills/` 是唯一源码**，进版本库、可评审、可分享；
- **`.codebuddy/skills/` 是同步出来的副本**，只供 CodeBuddy 运行时读取，不进版本库。

克隆仓库或修改技能后执行：

```bash
python skills/sync_skills.py             # 同步到 .codebuddy/skills/
python skills/sync_skills.py --check     # 只检查是否一致，不一致返回 1（可用于 CI）
python skills/sync_skills.py --clean     # 同步并清理目标中残留的旧文件
python skills/sync_skills.py --list      # 列出已发现的技能
```

同步后重启会话或重新打开工作区，CodeBuddy 才会加载新版本。

## 新增技能

1. 在 `skills/` 下新建目录，命名用 kebab-case，例如 `pdf-tools`。
2. 写 `SKILL.md`，frontmatter 必含：
   - `name`：与目录名一致；
   - `description`：说明「做什么」和「什么时候用」，不要出现尖括号（打包校验会失败）。
3. 只有需要确定性执行逻辑时才加 `scripts/`；长文档放 `references/`；模板放 `assets/`。
4. 执行 `python skills/sync_skills.py` 部署，再实际跑一遍验证。
5. 提交到 `feat/<用户名>` 分支，走 Pull Request。

## 修改技能

**只改 `skills/<name>/`，不要直接改 `.codebuddy/skills/`** —— 后者会被下次同步覆盖，且不会进入版本库。

改完执行同步，用 `git diff skills/` 检查改动，确认无误后再提交。

## 打包分发

需要把技能发给仓库外的人时，用 CodeBuddy 自带的 skill-creator 打包脚本生成 zip：

```bash
python "<CodeBuddy 内置目录>/skill-creator/scripts/package_skill.py" skills/<name> skills/dist
```

`skills/dist/` 下的 zip 被 `*.zip` 规则忽略，只作临时分发，不提交。

## 评审要点

- `description` 是否说清了触发场景，第三人称、具体；
- `SKILL.md` 正文是否足够精炼，细节是否已下沉到 `references/`；
- 脚本能否直接运行，有无硬编码的绝对路径、个人目录、密钥；
- 是否依赖仅本机存在的配置（应改为读取 `git config` 或环境变量，并在文档里说明默认值）；
- 新增或修改后是否执行了 `sync_skills.py --check`。
