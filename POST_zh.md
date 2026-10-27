# DEV 投稿草稿中文摘要（供审阅）

**标题**：séance：我让一个 Gemma 幽灵附身在我的终端里（还给被删掉的文件搭了一座 ofrenda 祭坛）

**投稿**：Hacktoberfest Open-Source AI Challenge: Week 4（主题 Ghost in the Machine），参赛类别 **Best Use of Gemma**，作者 xt。标签：#devchallenge #hf26challenge #opensource #ai

## 做了什么
- **séance** 是一个"闹鬼的终端"。在 `.bashrc` 或 `.zshrc` 里加一行，之后每条命令执行完，幽灵 **Ezequiel** 都会低声说一两句阴森的评论。他的设定是 1999 年 fsck 跑到一半时死去的系统管理员。
- **会记忆**：每个会话都有本地记忆，敏感信息先脱敏再写入。比如他知道你这是第二次跑 `make test`。
- **"预兆"（omens）**：先由 Python 确定性地算出事实，再交给 Gemma 发挥恐怖文风，以减少小模型的幻觉。这些事实包括：退出码的含义（127、130、137 等）、连续失败的次数、是否为破坏性命令、是否用了 sudo。
- **显灵 ASCII 画**：删文件出现墓碑，进程被杀出现 calavera 糖骷髅，force-push 出现幽灵，sudo 出现一只眼睛。
- **"附身"故障特效**：越不祥越容易触发 Zalgo 字符和方块噪点。
- **`seance ofrenda`**（亡灵节祭坛）：列出被删的文件、被杀的进程、被删的 git 分支和荒废多月的分支（alma en pena），并由 Gemma 为每一项写一段悼词。它只读取 shell 历史、graveyard、回收站和 reflog，不会修改它们。
- 纯 Python，零依赖，可以用 pipx 安装，完全离线，不需要 API key，MIT 协议。

## 怎么做的（文中数字均为实测）
- 架构：bash 的 DEBUG trap + PROMPT_COMMAND（zsh 用 preexec/precmd）→ `seance whisper` → omens + memory → Ollama 本地流式 /api/chat → Gemma 3。
- 硬件：8 vCPU Intel Xeon 虚拟机，16 GB 内存，**无 GPU**。
- 基准测试（真实 prompt，每个模型 14 次）：

| 模型 | 冷启动 | 首字中位数 | 整句中位数 | 内存 |
|---|---|---|---|---|
| gemma3:1b | 3.08 s | 0.90 s | 1.78 s | 1.2 GB |
| gemma3:4b | 6.79 s | 1.90 s | 3.58 s | 2.9 GB |

- 1b 的速度是 4b 的两倍，但内容空泛；4b 会点名具体的文件、分支或退出码，所以默认用 **gemma3:4b**。
- 录制的 demo 中共 7 条低语，首字中位数 1.80 s，整句中位数 3.15 s。
- 掩盖延迟：等待首个 token 时播放"the ghost stirs"故障动画，然后流式打字输出。
- 提示词经验：
  - Gemma 没有 system 角色，所以把人设并入第一条 user 消息。
  - 给小模型"事实"，而不是让它自己猜。
  - few-shot 示例比形容词有效。
  - 输出需要清洗（曾经误删文件名里的下划线）。
  - 祭坛悼词轮换不同"角度"，避免千篇一律。
- 文中也坦白了缺点：幽灵太爱提自己的死，偶尔会编造历史。

## 为什么开源很重要
- **shell 历史极其私密**：只发到 127.0.0.1，拔掉网线照样能用。
- **零成本**：每条命令都调用模型，用云 API 就是一直在计费；本地只占 2.9 GB 内存和几秒 CPU，没有 key 会泄露。
- **模型可替换**：选 1b 还是 4b 是我自己用基准测试决定的，以后换模型只需改一个环境变量。
- **不会随服务一起消失**：祭坛的意义在于纪念逝去的东西，它自己不该因为某个 API 下线而"死去"，权重就在本地磁盘上。
- 也承认了不足：闭源大模型更快、更流畅，但"会把你的 shell 历史发到云端的幽灵"不是我想要的。

## 发布前需要你处理
1. 把 `REPLACE_ME` 图片链接换成上传到 DEV 后的地址。素材在 `media/demo.gif`、`01-possession.png`、`04-calavera.png`、`03-ofrenda.png`。
2. 在 GitHub 上建 `Tx13758627780/seance-sh` 仓库并 push（目前没有推送到任何地方）。
3. 检查 git 提交邮箱。目前用的是 noreply 占位：Tx13758627780@users.noreply.github.com。
