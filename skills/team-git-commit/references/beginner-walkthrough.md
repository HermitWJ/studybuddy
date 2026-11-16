# 初学者完整使用过程（真实演练记录）

## 这份文档是什么

这不是示意，是在真实仓库里跑出来的一次完整演练：两个克隆、一个远程裸仓库、真实的 squash 合并、真实的冲突。

用来回答一个问题：**一个不懂 git 协作的同事装上这个技能后，她实际会经历什么。**

每一段都分成三层：

- **她说**：她的原话，只需要表达意图。
- **她看到**：助手回给她的人话，含原理讲解。
- **后台实际执行**：助手跑的脚本和真实输出（她看不到这些，也不需要看）。

---

## 出场与初始状态

小美，后端新人，第一次参与团队协作。仓库 `studybuddy`，远程只有一条 `main` 分支。

一次性配置（助手在后台完成，她不参与）：

```text
$ python skills/team-git-commit/scripts/team_submit.py set-user xiaomei
[OK  ] 已写入 git config team.username = xiaomei
[OK  ] 以后提交将使用分支 feat/xiaomei
```

---

## 阶段一：第一天开工

**她说**：「我要开始做登录功能了。」

**她看到**：

> 我先看下你现在在哪个分支。
>
> 你现在在 `main` 上，还没有自己的分支。
>
> 团队规定每人一条 `feat/xiaomei` 分支：各改各的互不干扰，`main` 是大家共用的稳定线，只接受评审过的合并 —— 这样你写坏了也只影响自己那条线。
>
> 要帮你新建 `feat/xiaomei` 吗？还是你想用已有的某条分支？

**后台实际执行**：

```text
$ python skills/team-git-commit/scripts/team_submit.py check
[OK  ] 团队用户名：xiaomei  ->  目标分支：feat/xiaomei
[OK  ] 远程引用已更新
[WARN] 当前在受保护分支 main 上，提交前需切到 feat/xiaomei
[INFO] 相对 origin/main：领先 0 个提交，落后 0 个提交
[OK  ] 工作区干净
```

```text
$ python skills/team-git-commit/scripts/team_submit.py branches
当前分支：main
推荐分支：feat/xiaomei  ——  不存在，需要新建

本地分支（相对 origin/main，+领先 / -落后）
  * main                               +0/-0    受保护

远程分支（相对 origin/main，+领先 / -落后）
    origin/main                        +0/-0    受保护
```

**她说**：「新建一个吧。」

**她看到**：

> 建好了。你现在在 `feat/xiaomei` 上，代码是从最新 `main` 拉出来的。
>
> 为什么开工要先同步 main：你晚一天同步，后面合并冲突就多一分；现在同步，冲突只会在你还没写代码时出现，代价最小。
>
> 可以开始写了。两点建议：完成一个小功能就提交一次，别攒一整天；写的时候别切回 `main`。

**后台实际执行**（先跑一次不带 `--create` 的，验证脚本不会擅自建分支）：

```text
$ python skills/team-git-commit/scripts/team_submit.py start
[WAIT] 本地和远程都没有分支 feat/xiaomei。
新建分支会改变当前工作位置，必须先和用户确认，脚本不会自行创建。
  • 用户同意新建 feat/xiaomei：加 --create 重跑
```

```text
$ python skills/team-git-commit/scripts/team_submit.py start --create
[OK  ] 已从 origin/main 新建分支 feat/xiaomei
[OK  ] 已是最新，无需 rebase（origin/main 无新提交）

[OK  ] 开工就绪：当前分支 feat/xiaomei，代码已基于最新 origin/main
# 退出码 0
```

---

## 阶段二：写完了，提交

**她说**：「写完了，帮我提交。」

**她看到**：

> 我看下你改了什么 —— 新增了 `backend/auth.py` 和 `backend/test_auth.py`。
>
> 提交信息我拟成 `feat(auth): 增加登录接口与单元测试`，这样描述准确吗？
>
> （她确认后）提交信息是留给三个月后的人看的，很可能就是你自己。写清「改了什么、为什么」，出问题能快速定位到那一次。
>
> 已经推到你自己的远程分支了。

**后台实际执行**：

```text
$ python skills/team-git-commit/scripts/team_submit.py submit -m "feat(auth): 增加登录接口与单元测试"
[OK  ] 当前分支符合规范：feat/xiaomei
[OK  ] 已创建本地提交：feat(auth): 增加登录接口与单元测试
[OK  ] 已是最新，无需 rebase（origin/main 无新提交）
[OK  ] 分支基线正确：首个独有提交 9cdfb44d 的父提交在 origin/main 历史中
[INFO] 推送：git push -u origin feat/xiaomei:feat/xiaomei
[OK  ] 已推送到 origin/feat/xiaomei
# 退出码 0
```

---

## 阶段三：撞上冲突

同事把 README 那一行改成「已接入 MySQL」，她也改了同一行，而且同事先推了 main。

**她看到**：

> 停一下 —— 有冲突，还没推上去。
>
> 原因：你和李四改了 README 的同一行。git 只认文本、不懂业务，它不敢替你决定保留哪句，所以停下来问你。
>
> 冲突文件是 `README.md`，你打开会看到三组标记：`<<<<<<<` 到 `=======` 之间是你的版本，`=======` 到 `>>>>>>>` 之间是 main 上的版本。
>
> 我们看一下：你写的是「已接入 Redis 缓存」，李四写的是「已接入 MySQL」。这两句都对，应该合并成「已接入 MySQL 与 Redis 缓存」。

**她看到文件里的样子**：

```text
# StudyBuddy

<<<<<<< HEAD
基础工程，已接入 MySQL。
=======
基础工程，已接入 Redis 缓存。
>>>>>>> a29ab34 (docs: 补充缓存说明)
```

**后台实际执行**：

```text
$ python skills/team-git-commit/scripts/team_submit.py submit -m "docs: 补充缓存说明"
[OK  ] 已创建本地提交：docs: 补充缓存说明
[INFO] 落后 origin/main 1 个提交，开始 rebase
[FAIL] rebase 到 origin/main 发生冲突，已阻止本次推送
  冲突文件：
    - README.md
  解决步骤：
    1) 打开上面列出的文件，处理 <<<<<<< / ======= / >>>>>>> 标记
    2) git add <已解决的文件>
    3) git rebase --continue
    4) 冲突全部解决后重跑：python skills/team-git-commit/scripts/team_submit.py submit -m "..."
    放弃本次 rebase：git rebase --abort
# 退出码 3
```

改完重新执行同一条命令：

```text
$ python skills/team-git-commit/scripts/team_submit.py submit -m "docs: 补充缓存说明"
[OK  ] 分支基线正确：首个独有提交 8652de6f 的父提交在 origin/main 历史中
[OK  ] 工作区干净，无需新建提交
[OK  ] 已是最新，无需 rebase（origin/main 无新提交）
[WARN] 历史已分叉，使用 --force-with-lease 更新你自己的分支 feat/xiaomei
[INFO] 推送：git push --force-with-lease -u origin feat/xiaomei:feat/xiaomei
[OK  ] 已推送到 origin/feat/xiaomei
# 退出码 0
```

**她看到**：

> 推上去了。刚才动了你的提交历史，所以用了一次「带保险的强制推送」——它只覆盖你自己的 `feat/xiaomei`，一旦发现别人往这条分支推过东西就会拒绝，不会误伤别人。
>
> 冲突没解决完之前，脚本不会推送，所以 main 上永远不会出现半成品。

---

## 阶段四：PR 合并后的第二天

同事把她的分支 squash 合并进 main，并按惯例删掉了远程 `feat/xiaomei`。她本地还留着那条分支和两个已经进 main 的提交。

**她说**：「继续写登录那块。」

**她看到**：

> 先等一下 —— 你这条分支上的 2 个提交都已经进了 main，说明上次那个 PR 已经合并完了。
>
> 如果直接在这上面继续写，这两个旧提交会被重新贴到 main 上，等于把已经合并的东西再交一遍，PR 里会出现莫名其妙的重复改动。
>
> 建议从最新 main 重建：旧分支我会先备份成 `backup/feat-xiaomei-20261116-140310`，随时能找回来。要这么做吗？

**她说**：「好，重建吧。」

**后台实际执行**：

```text
$ python skills/team-git-commit/scripts/team_submit.py start
[OK  ] 当前分支符合规范：feat/xiaomei
[WARN] feat/xiaomei 上的 2 个提交都已并入 origin/main（之前那次 PR 应该已合并）
[WARN] 继续在这个分支上开发，旧提交会被重放到 main 上，应该从最新 main 重建

[WAIT] 这个分支已经用过了，需要确认下一步：
  • 从最新 origin/main 重建，旧分支自动备份：加 --recreate
# 退出码 2
```

```text
$ python skills/team-git-commit/scripts/team_submit.py start --recreate
[OK  ] 已从 origin/main 重建 feat/xiaomei，旧状态备份为 backup/feat-xiaomei-20261116-140310

[OK  ] 开工就绪：当前分支 feat/xiaomei，代码已基于最新 origin/main
# 退出码 0
```

**她看到**：

> 重建好了，现在这条分支和 main 完全对齐，旧状态在 `backup/feat-xiaomei-20261116-140310` 里。可以重新开始了。

注：这里能识别出来，是因为脚本除了比对 patch-id，还会比对「分支改过的文件内容和 main 是否已经一致」—— 后者专门覆盖 GitHub 默认的 squash 合并（多个提交压成一个，patch-id 全变）。

---

## 阶段五：她想直接推到 main

**她说**：「我直接把改动推到 main 吧，快一点。」

**她看到**：

> 不行，团队不允许推 main —— 这条线要一直保持能跑，所有改动都得走 `feat/<你的名字>` 加 PR 评审。
>
> 而且你本地装了钩子，现在推会被直接拦下，不用等到服务器拒绝。

**后台实际执行**：

```text
$ python skills/team-git-commit/scripts/install_hooks.py
[ OK ] 已安装 pre-push -> .../.git/hooks/pre-push
```

```text
$ git push origin main
[team-git-commit] 已阻止：禁止推送到远程分支 main
[team-git-commit] 所有改动必须提交到你自己的分支：feat/<用户名>，例如 feat/HermitWJ
[team-git-commit] 正确做法：
[team-git-commit]   git checkout -b feat/<用户名> origin/main
[team-git-commit]   python skills/team-git-commit/scripts/team_submit.py submit -m "说明"
[team-git-commit]   -> 然后在 GitHub 上发起 Pull Request 合入 main

[team-git-commit] 推送已中止。
# 退出码 1
```

---

## 全程她只需要做这些决定

| 时机 | 助手问什么 | 她回答 |
| --- | --- | --- |
| 开工前 | 用已有分支还是新建 | 「新建一个」 |
| 提交前 | 提交信息是否准确 | 「可以」或改成自己的说法 |
| 冲突时 | 这一处保留哪边 / 还是都要 | 「两句都留」 |
| 分支已合并 | 是否从最新 main 重建 | 「重建吧」 |
| 想推 main | —（直接拒绝并解释） | — |

其余全部由助手执行。她从头到尾没有敲过一条 git 命令，也没有看过一行原始日志。

## 效果总结

- **她理解的是原理**：为什么每人一条分支、为什么开工要同步、冲突为什么必须她本人决定、force-with-lease 为什么安全。
- **她不需要记命令**：所有操作由助手执行，她只需要表达意图和做业务判断。
- **危险动作有硬拦截**：推 main 被本地钩子拦；分支不存在不会被擅自创建；分支已合并不会继续往上堆提交；冲突未解决不会推送。
- **出错有兜底**：旧分支自动备份为 `backup/...`，历史改写只作用于她自己的分支。

## 已知边界

| 情况 | 现状 |
| --- | --- |
| 她把文件删了又想让助手恢复 | 走 `git checkout -- <文件>`，技能不覆盖这一层 |
| 团队多人同时改同一分支 | 技能假设个人分支只本人推，同名分支会被 `--force-with-lease` 保护但语义上不建议 |
| PR 评审、CI 失败 | 属于 GitHub 侧流程，技能只负责把代码安全送上去 |
| `main` 之外的基线（如 `develop`） | 通过 `git config team.upstream origin/develop` 可改，默认 `origin/main` |
