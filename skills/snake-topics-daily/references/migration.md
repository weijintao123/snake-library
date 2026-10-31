# 安装到另一台电脑

优先在线安装：在另一台电脑的Codex发送：

> 使用 $skill-installer 安装 https://github.com/weijintao123/snake-library/tree/skill-package/skills/snake-topics-daily

该分支仅含技能，便于快速下载。安装器会写入当前Codex使用的个人技能目录，后续轮次可调用；未出现时重启Codex。官方方式见 https://learn.chatgpt.com/docs/build-skills#install-curated-skills-for-local-use 。本地技能按设备安装；远端照片、索引与接续状态通过GitHub共享。

将完整的 `snake-topics-daily` 文件夹复制到 Codex 的 `skills` 目录：

以下为当前电脑使用的兼容位置。新版Codex可能使用 `~/.agents/skills/`；手工安装应核对该设备的技能搜索路径，在线安装优先交给内置skill-installer。

- 默认：`~/.codex/skills/snake-topics-daily/`
- 已自定义CODEX_HOME：`$CODEX_HOME/skills/snake-topics-daily/`
- Windows默认：用户主目录下的 `.codex\skills\snake-topics-daily\`

`SKILL.md` 应直接位于上述目录，避免多套一层同名目录。已有同名技能时先将旧版备份到skills目录外，再替换。重启Codex后，直接说“更新上次以来的全部蛇照片”，或显式调用 `$snake-topics-daily`。

新电脑分别登录Codex、GitHub以及肥猫识蛇。登录由用户在正常站点界面完成；安装包不携带密码、Cookie、令牌或浏览器会话。GitHub连接应能读取及更新 `weijintao123/snake-library`。肥猫浏览器登录不会为Actions配置Secret。

恢复工作时直接读取GitHub的README、脚本、物种表、图片索引及 `docs/topic_sync_state.json`。从远端 `last_successful_cutoff` 接续，合并远端全部retry_topics。旧电脑的照片镜像、工作目录和本地状态不是恢复前提；线上仓库优先。若状态缺失，按已核验提交及部署证据恢复，不默认最近三天。

本地处理需要Python3.12和Pillow；使用可用的Codex随附环境或正规Python环境，不依赖旧电脑的绝对路径。发布可使用已连接的GitHub工具，或在用户正常认证的本地仓库执行；不要把认证信息写入代码、日志或迁移包。

已有GitHub每天北京时间09:00计划；安装技能不会另建定时任务。无人值守发现依赖仓库安全设置中的SNAKE_TOPIC_TOKEN，须由用户在GitHub维护，不能从浏览器导出会话代填。缺失时每日手动调用本技能仍可通过已登录浏览器完成抓取。
