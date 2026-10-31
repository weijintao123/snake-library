# 蛇照片更新技能

## 在线安装（推荐）

另一台电脑打开Codex，发送这一句话：

> 使用 $skill-installer 安装 https://github.com/weijintao123/snake-library/tree/skill-package/skills/snake-topics-daily

此在线分支只包含技能，安装器不需要下载整个照片图库。安装后的下一轮可用；未出现时重启Codex。然后说“使用 $snake-topics-daily 更新上次以来的全部蛇照片”。照片和断点通过GitHub共享，本地技能需要在每台电脑安装一次。

官方说明：https://learn.chatgpt.com/docs/build-skills#install-curated-skills-for-local-use

## 离线复制

解压后，将完整的snake-topics-daily文件夹放到新电脑的用户主目录：

`~/.codex/skills/snake-topics-daily/`

Windows为用户主目录下的 `.codex\skills\snake-topics-daily\`。如果配置了CODEX_HOME，则放到该目录的skills子目录。确认其中直接包含SKILL.md。重启Codex。

新版Codex可能使用用户主目录下的 `.agents/skills/`；在线安装会由内置skill-installer选择当前环境的安装位置。

在新电脑登录Codex、GitHub和肥猫识蛇，然后说：

> 使用 $snake-topics-daily 更新上次以来的全部蛇照片。

技能会读取GitHub上的最新成功断点，补抓期间全部话题并重试历史待处理项；核验后更新图片、索引及网站。可靠的新蛇种自动新建目录，152种不是上限。

本包不含密码、Cookie、令牌、GitHub Secret或浏览器登录会话。新电脑需要正常重新登录。图片和断点从线上仓库恢复，无需复制旧电脑全部照片。

仓库：https://github.com/weijintao123/snake-library

图库：https://weijintao123.github.io/snake-library/

安装包版本：2026-11-01。当前数据数量和截止时间始终以远端状态文件为准。
