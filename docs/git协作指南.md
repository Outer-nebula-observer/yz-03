# Git 协作指南（团队共享）

> 适用范围：YZ-03 团队仓库。
> 重要声明：本文的**提交注释规范只是参考模板，不强制、不拦截**——本仓库**不安装 commitlint / husky** 等强制校验，团队按习惯写清楚"改了什么、为什么"即可。

---

## 0. 第一次协作：从 0 到能提交

### 0.1 创建远程仓库并首次推送（由发起人做一次）

```bash
# 在 GitHub 网页新建空仓库，例如 yz-03（不要勾选 README/.gitignore，本地已有）
git init
git add .
git commit -m "chore: 初始化仓库与目录结构"
git branch -M main
git remote add origin https://github.com/<你的用户名>/yz-03.git
git push -u origin main
```

### 0.2 队友克隆并配置身份

```bash
git clone https://github.com/<你的用户名>/yz-03.git
cd yz-03

# 配置身份（换成自己的名字和 GitHub 邮箱）
git config user.name  "张三"
git config user.email "zhangsan@example.com"
```

### 0.3 分支策略（建议）

- `main`：稳定、可演示的版本，只通过合并进入；
- 每人一个 `feature/<姓名>/<功能>` 分支开发，完成后合并回 `main`；
- 2 人小队也可以更简单：直接都在 `main` 上提交，但**先 pull 再 push**、小步提交。

---

## 1. 日常高频命令

| 场景 | 命令 |
|---|---|
| 看改动状态 | `git status` |
| 看改了什么 | `git diff` |
| 拉取远程最新 | `git pull` |
| 暂存并提交 | `git add <文件>` 或 `git add .`，然后 `git commit -m "说明"` |
| 推到远程 | `git push` |
| 看提交历史 | `git log --oneline --graph --all` |
| 新建分支并切换 | `git switch -c feature/张三/记忆进化` |
| 切回 main | `git switch main` |
| 合并分支 | `git merge feature/张三/记忆进化` |
| 临时保存改动 | `git stash` / 恢复 `git stash pop` |
| 撤销未暂存的改动 | `git restore <文件>` |
| 撤销已暂存（不丢改动） | `git restore --staged <文件>` |
| 撤回最近一次提交（保留改动） | `git reset --soft HEAD~1` |

> 新手建议每天只走这条主线：`pull → 改 → add → commit → push`。

---

## 2. 提交注释规范（参考模板，不强制）

**格式**（建议，不强制）：

```
<类型>: <一句话说明>

<可选正文：为什么这么改、影响范围、测试情况>
```

**常用类型**：

| 类型 | 含义 | 示例 |
|---|---|---|
| `feat` | 新功能 | `feat: 记忆进化模块支持遗忘策略` |
| `fix` | 修复 bug | `fix: 修复跨场次经验检索空结果` |
| `docs` | 文档 | `docs: 补充参考文献模块 README` |
| `refactor` | 重构（不改功能） | `refactor: 抽取记忆库统一接口` |
| `test` | 测试 | `test: 新增检索层 Recall@5 单测` |
| `chore` | 杂项/工程配置 | `chore: 添加 .gitignore` |
| `style` | 格式（不影响逻辑） | `style: 统一换行与缩进` |
| `perf` | 性能优化 | `perf: 减少长期记忆重复嵌入` |

**中文示例**：

```
feat: 长期记忆层新增事实/经验双库

- 事实记忆走 SQLite 精确查询，经验记忆走向量召回
- 关联 docs/04 第 2.2 节技术路线
```

> 底线要求只有一条：**说明"改了什么、为什么"**，别只写 `update`、`111`。

---

## 3. 共享与协作方法

### 3.1 GitHub 仓库与权限

1. 发起人创建仓库后，在 **Settings → Collaborators** 添加队友（或用组织仓库统一管理）；
2. 推送代码用 **HTTPS + Personal Access Token**（GitHub 已禁用账号密码推送）或 **SSH Key**；
3. 常用远端命令：
   ```bash
   git remote -v                       # 查看远端
   git fetch origin                    # 只下载、不合并
   git pull origin main                # 下载并合并 main
   ```

### 3.2 任务协作流（推荐 Fork / PR）

- **小团队（2 人）**：直接同仓库、同分支或短命 feature 分支即可；
- **正式流程**：`Fork 仓库 → 在 fork 上开发 → 提 Pull Request → 队友 review 后合并`；
- **任务认领**：用 GitHub **Issues** 记录"谁做什么、进行到哪、卡在哪"。

### 3.3 大文件提示

- 本仓库已含 pptx/pdf（几十 MB），在 GitHub 100MB 单文件限制内，可直接提交；
- 以后若出现 >100MB 的单文件，改用 **Git LFS**：
  ```bash
  git lfs track "*.pptx"
  git add .gitattributes
  ```

---

## 4. 冲突处理

```bash
git pull              # 先拉最新
# 若提示冲突，打开冲突文件，找到 <<<<<<< / ======= / >>>>>>> 手动取舍
git add <冲突文件>
git commit            # 完成合并提交
git push
```

**减少冲突的 4 个习惯**：

1. 每次开工先 `git pull`；
2. 小步提交，别攒一周才提交一次；
3. 分工分文件：A 改 `code/课题3_长短期记忆/`，B 改 `docs/`，尽量不重叠；
4. 二进制文件（pptx/pdf）一次只由一个人改。

---

## 5. 注意事项（安全与卫生）

- **不要提交**：`.env`、密钥、token、模型权重、训练数据（已在 `.gitignore` 排除）；
- 提交前 `git status` 扫一眼，确认没有把临时文件、缓存一起交上去；
- 若误提交了密钥，立即轮换密钥并 `git rm --cached` + 提交，必要时重写历史。

---

## 6. 本仓库常用约定

| 内容 | 目录 |
|---|---|
| 实际开发代码 | `code/`（顶层） |
| 方案与文档 | `docs/` |
| 课题三参考文献（按模块） | `references/` |
| 课程 PPT 原始资料 | `course_materials/` |
| 论文公开代码（参考复现） | `paper_code/` |

> 首次提交前请先读根目录 `README.md`，明确每个目录放什么。
