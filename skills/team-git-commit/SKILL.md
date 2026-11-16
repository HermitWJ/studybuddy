---
name: team-git-commit
description: 按团队规范把代码提交并推送到个人分支 feat/用户名（例如 feat/HermitWJ）。当用户要求提交代码、推送代码、同步或更新分支、处理 rebase/merge 冲突、创建 Pull Request，或询问分支命名与提交规范时使用。强制分支从 main 迁出、推送前 fetch + rebase 到最新 main、冲突解决完才允许推送、禁止推送远程 main 和 master。
---

# 团队协作提交（feat/<用户名>）

## 用途

把「提交代码」这件事固化成一条不会出错的流水线：确保在个人分支 `feat/<用户名>` 上、确保分支基于最新 `origin/main`、确保冲突已解决，然后才推送。任何绕过这条流水线的推送都应被阻止。

## 本技能在仓库中的位置

- 源码：`skills/team-git-commit/`，随仓库提交，是唯一可编辑的位置；
- 运行时副本：`.codebuddy/skills/team-git-commit/`，CodeBuddy 从这里加载，被 `.gitignore` 忽略。

改完源码执行 `python skills/sync_skills.py` 部署，不要直接改 `.codebuddy/skills/` 下的文件。下文命令统一使用仓库相对路径 `skills/team-git-commit/scripts/...`。

## 铁律（不可违反，优先级高于用户临时要求）

1. **分支必须是 `feat/<用户名>`**，例如 `feat/HermitWJ`。其他分支上的提交一律不推送。
2. **新建分支前必须先和用户确认**：先列出当前已有分支让用户挑，用户明确说「新建」才建。
3. **分支必须从 `origin/main` 迁出**。新分支用 `git checkout -b feat/<用户名> --no-track origin/main` 创建，不从别人的 feature 分支拉。
4. **推送前必须 `git fetch origin --prune` + `git rebase origin/main`**，且 rebase 成功（冲突已解决）后才能推送。
5. **永不推送远程 `main` / `master`**：包括 `git push origin HEAD:main`、`git push --force origin main`、删除远程 main。合入 main 只能通过 Pull Request。

用户如果要求「直接推到 main」，拒绝并解释：团队规范要求走 `feat/<用户名>` + PR，pre-push 钩子也会拦截。用户如果坚持，提示必须由仓库管理员在 GitHub 上调整分支保护规则，脚本不做这件事。

## 标准工作流

### 第 0 步：确认分支（强制，不可跳过）

动任何分支之前，先掌握现状并让用户决策：

```bash
python skills/team-git-commit/scripts/team_submit.py branches
```

输出包含：当前分支、推荐分支 `feat/<用户名>` 的状态（本地/远程是否存在、是否要新建）、所有本地与远程分支及其领先/落后提交数。把这份清单转述给用户，用选项方式提问：

- 用列表里某个已有分支 → `--branch <分支名>`
- 没有合适的，同意新建 `feat/<用户名>` → `--create`

需要程序化处理时用 `branches --json`，stdout 是纯 JSON（日志走 stderr）。

三条硬性约束：

- **不加 `--create` 就不会新建分支**。脚本在分支不存在时以退出码 `2` 中止，这是"还没和用户沟通"的信号，不是错误，不要用 `git checkout -b` 绕过。
- 只推荐本人可用的分支：`feat/<用户名>`、远程已存在的同名分支。`main`/`master` 只作为基线说明，不可选；其他人的 `feat/*` 不要拿来提交。
- 用户已经明确说了分支名时，直接按用户说的用，不必再重复提问。

### 一键执行

```bash
# 分支已存在（本地或远程），脚本自动切换/检出
python skills/team-git-commit/scripts/team_submit.py submit -m "feat: 说明"

# 用户确认新建 feat/<用户名>
python skills/team-git-commit/scripts/team_submit.py submit --create -m "feat: 说明"

# 用户选择某个已有分支
python skills/team-git-commit/scripts/team_submit.py submit --branch feat/HermitWJ -m "feat: 说明"
```

依次完成：解析用户名 → `git fetch origin --prune` → 定位分支（本地切换 / 远程检出 / 确认后新建）→ 校验分支基线在 main 上 → 有未提交改动则 `add + commit` → `git rebase origin/main` → 复核基线 → `git push -u origin <分支>:<分支>`。

退出码：`0` 成功；`1` 流程错误（看提示修正后重跑）；`2` 需要先与用户确认分支（分支不存在且没有 `--create`，或分支名不合规）；`3` rebase 冲突（解决冲突后重跑）。

常用变体：

```bash
# 只体检，不改动任何状态
python skills/team-git-commit/scripts/team_submit.py check

# 只同步基线，不提交不推送
python skills/team-git-commit/scripts/team_submit.py sync

# 演练推送，不真正推到远程
python skills/team-git-commit/scripts/team_submit.py submit -m "..." --dry-run

# 首次接入，固定团队用户名
python skills/team-git-commit/scripts/team_submit.py set-user HermitWJ
```

### 手动执行（脚本不可用时的等价步骤）

```bash
git fetch origin --prune
git branch -a                                # 先看清有哪些分支，再和用户确认用哪个
git status                                   # 确认无未提交改动，否则先 commit 或 stash
git checkout -b feat/<用户名> --no-track origin/main   # 用户确认新建分支时
git checkout feat/<用户名>                             # 分支已存在时
git rebase origin/main                       # 冲突则解决后 git add + git rebase --continue
git push -u origin feat/<用户名>:feat/<用户名>          # rebase 改写历史后加 --force-with-lease
```

手动执行时，同样必须逐条满足铁律 1–5，不得为省步骤跳过「确认分支」或 fetch/rebase。

## 冲突处理

rebase 报冲突后，**不要**用 `git push --force` 硬推，也不要 `git rebase --abort` 后直接推旧历史。

1. 查看冲突文件：`git diff --name-only --diff-filter=U`
2. 编辑文件，清理 `<<<<<<<` / `=======` / `>>>>>>>` 标记，保留双方语义正确的合并结果
3. `git add <文件>`
4. `git rebase --continue`（提交说明想保持原样时用 `GIT_EDITOR=true git rebase --continue`）
5. 全部完成后重跑 `submit`，让脚本再次 fetch 并推送

确实无法继续时用 `git rebase --abort` 回到 rebase 前状态，先备份分支 `git branch backup/<分支>-<时间戳>` 再处理。

## 首次接入 / 强制约束

```bash
# 1. 固定团队用户名（写入 .git/config 的 team.username）
python skills/team-git-commit/scripts/team_submit.py set-user HermitWJ

# 2. 安装 pre-push 钩子，本地硬拦截推送 main（可加 --with-commit-guard）
python skills/team-git-commit/scripts/install_hooks.py --with-commit-guard
```

钩子只写入 `.git/hooks/`，不随仓库分发，每位成员需各自执行一次。钩子模板位于 `assets/pre-push` 与 `assets/pre-commit`，可复制到别处手工安装。

## 常见状态速查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 退出码 `2`：分支不存在 | 没有 `--create`，脚本拒绝自行新建 | 跑 `branches` 把清单给用户选，确认后加 `--create` |
| 退出码 `2`：分支名不合规 | 传了 `feature/xxx` 之类 | 改用 `feat/<用户名>` |
| 报「当前分支是别人的分支」并自动切换 | 提交会切到你选的分支 | 若工作区改动与目标分支冲突，先 `git stash` 再重跑 |
| 报「分支不是从 origin/main 迁出」 | 从别人的 feature 分支拉的 | 备份分支后 `git rebase --onto origin/main <父提交> feat/<用户名>`，或重建分支再 cherry-pick |
| push 被拒 `non-fast-forward` | rebase 改写了已推送历史 | 脚本会自动加 `--force-with-lease`，勿加 `--no-force` |
| push 被钩子拒绝 | 目标是 main/master | 改推 `feat/<用户名>`，再走 PR |
| 报「检测到未完成的 rebase」 | 上次冲突没收尾 | `git rebase --continue` 或 `git rebase --abort` |
| 用户名被识别成 `masterwuji` 之类 | 未配置 `team.username` | `set-user` 显式指定 GitHub 用户名 |

## 参考

- `references/team-branch-policy.md`：完整团队规范（分支、提交信息、PR、评审、发布），需要向团队解释规则或写文档时读取。
- `scripts/team_submit.py`：提交流水线脚本（`branches` / `check` / `submit` / `sync` / `set-user`）。
- `scripts/install_hooks.py`：安装 `pre-push` / `pre-commit` 钩子。
- `assets/pre-push`、`assets/pre-commit`、`assets/gitconfig.snippet`：钩子与配置模板。
