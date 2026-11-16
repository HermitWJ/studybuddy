# 团队 Git 协作规范

面向团队成员与代码评审者，用于解释「为什么这样提交」以及评审时该检查什么。

## 1. 分支模型

| 分支 | 用途 | 谁能推送 |
| --- | --- | --- |
| `main` | 唯一主干，随时可发布 | 任何人都不直接推送，只接受 PR 合并 |
| `feat/<用户名>` | 成员个人工作分支 | 仅本人 |

规则：

- 每人只有一个长期存在的个人分支 `feat/<GitHub 用户名>`，例如 `feat/HermitWJ`。
- 分支命名严格匹配 `^feat/[A-Za-z0-9._-]+$`，不使用大写 `Feat/`、不使用 `feature/`、不夹带需求编号之外的空格。
- 新分支只能从最新 `origin/main` 迁出。禁止从他人的 `feat/*` 拉出分支，避免把别人的半成品历史带进来。
- 个人分支不长期堆积：PR 合并后删掉远程个人分支，下次从最新 main 重建。

### 新建分支要先确认

任何人在动手建分支前，先看仓库里已有哪些分支，再决定用哪个：

```bash
python skills/team-git-commit/scripts/team_submit.py branches
```

输出会列出当前分支、推荐分支 `feat/<用户名>` 是否存在，以及所有本地/远程分支相对 `origin/main` 的领先与落后提交数。确认方式：

- 已有 `feat/<用户名>`（本地或远程）→ 直接用它，脚本会自动切换或检出；
- 没有 → 与本人确认后再新建，命令加 `--create`；
- 想用别的名字的分支 → 加 `--branch <分支名>`，但必须仍是 `feat/` 前缀。

工具不会在未确认的情况下建分支：分支不存在且没给 `--create` 时，`submit` 以退出码 `2` 退出，提示先和用户沟通。

## 2. 提交前必做

顺序固定，缺一不可：

1. `git fetch origin --prune`
2. `git rebase origin/main`（含冲突解决，冲突未解决完不得推送）
3. 本地自测通过
4. `git push -u origin feat/<用户名>:feat/<用户名>`

关于「先提交还是先 rebase」：把未提交改动先用 `git add -A && git commit` 落到本地个人分支，再 rebase，是安全的等价做法（改动已经进对象库，不会丢）。`team_submit.py submit -m "..."` 就是这样执行的。

### 为什么用 rebase 而不是 merge

个人分支上保持线性历史，main 的合并记录干净、便于 bisect 定位问题。个人分支是私有分支，rebase 改写历史无副作用。

rebase 后远程个人分支历史分叉，必须 `git push --force-with-lease`。只对**自己的** `feat/<用户名>` 分支这么做，永远不要对 main 或其他人的分支强推。

## 3. 禁止事项

- 禁止 `git push origin main` / `git push origin HEAD:main` / `git push --force origin main`。
- 禁止删除远程 `main`（`git push origin --delete main`）。
- 禁止在 main 上直接 `commit` 后强行推送。
- 禁止对他人分支强推。
- 禁止把 `.env`、密钥、数据库文件、`node_modules`、构建产物提交进库；确需提交配置时用 `.env.example`。

本地已安装 `pre-push` 钩子，以上推送会被拦截；仓库管理员还应开启 GitHub 分支保护（Require PR + Require status checks），双层兜底。

## 4. 提交信息规范（Conventional Commits）

```
<type>(<scope>): <简述>

<可选正文：为什么改、影响范围>
```

常用 type：`feat`、`fix`、`docs`、`style`、`refactor`、`perf`、`test`、`chore`、`build`、`ci`。

要求：

- 一行标题不超过 72 个字符，动词开头，不用句号结尾，不复述代码。
- 一个提交只做一件事，禁止「顺手改了一堆」的巨型提交。
- 关联 issue 写在正文或标题尾部，例如 `fix: 修正登录态丢失 (#42)`。

示例：

```
feat(auth): 增加刷新令牌自动续期

令牌过期前 60 秒静默续期，失败时跳转登录页并保留原路径。
```

## 5. Pull Request

- 标题沿用提交信息规范；描述包含：改了什么、为什么改、如何验证、影响范围、回滚方式。
- 只从 `feat/<用户名>` 指向 `main`，不跨 feature 分支合并。
- 提交 PR 前先 rebase 到最新 main，减少评审期间的冲突。
- 至少一位其他成员 Appove 才合并；合并方式统一用 Squash merge，保持 main 单提交线性。
- 合并后立即删除个人远程分支。

## 6. 评审要点

- 分支名是否为 `feat/<用户名>`，是否基于最新 main。
- 是否夹带了无关改动或生成物。
- 冲突解决处是否保留了双方语义（重点看 rebase 涉及的文件）。
- 是否新增了密钥、调试代码、注释掉的死代码。
- 提交信息是否能说明「为什么」。

## 7. 故障恢复

| 场景 | 恢复方式 |
| --- | --- |
| rebase 中途放弃 | `git rebase --abort`（回到 rebase 前） |
| 强推覆盖错了内容 | `git reflog` 找到旧提交，`git reset --hard <sha>` 或 `git push --force-with-lease` 恢复 |
| 误在 main 上提交 | `git branch feat/<用户名>` 保留提交，`git reset --hard origin/main` 回退 main，再切到个人分支 |
| 本地历史彻底乱了 | 备份 `git branch backup/<时间戳>`，重新 `git checkout -b feat/<用户名> --no-track origin/main`，按需 cherry-pick |
| 远程个人分支需要重置 | `git push --force-with-lease origin feat/<用户名>` |

任何恢复操作前先 `git branch backup/<时间戳>` 留一份，任何情况下都不要 `git clean -fdx` 或删除工作区文件。

## 8. 仓库级配置

```bash
git config team.username HermitWJ          # 团队用户名，决定分支名
git config team.branchPrefix feat/         # 分支前缀
git config team.upstream origin/main       # 上游基线
git config pull.rebase true                # 默认 rebase，避免误生成 merge 提交
git config rebase.autoStash true           # rebase 前自动暂存
```

配置写在本地 `.git/config`，不要提交到版本库。
